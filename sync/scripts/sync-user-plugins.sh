#!/usr/bin/env bash
set -euo pipefail

# Syncs installed Optimus plugins with the marketplace.
# Supports two platforms:
#   - Droid (Factory): uses `droid plugin install/update/uninstall`
#   - Claude Code: uses `claude plugin install/update/uninstall` (native plugin system)
#
# Detects which platforms are available and syncs both in a single run.
# - Installs new plugins that were added to the marketplace
# - Removes orphaned plugins that were removed from the marketplace
# - Updates all existing plugins (with uninstall+reinstall fallback for Droid scope conflicts)
#
# Plugin name conventions:
#   - Droid:        17 bare-name plugins (`plan`, `build`, `sync`, ...) — listed
#                   in `.factory-plugin/marketplace.json`. Each is installed
#                   individually via `droid plugin install <name>@optimus`.
#   - Claude Code:  ONE plugin (`optimus`) — listed in `.claude-plugin/marketplace.json`.
#                   The 17 commands surface as `/optimus:<command>` via the
#                   top-level `commands/` directory inside the single plugin.
#                   Installed once via `claude plugin install optimus@optimus`.
#                   Legacy per-plugin `optimus-<name>@optimus` installs from the
#                   pre-2.0 layout are detected and uninstalled silently.
#   - The EXPECTED list returned by `_resolve_expected_plugins` is in BARE form
#     (legacy contract used by the Droid branch).

_error() { echo "ERROR: $*" >&2; }
_warn() { echo "WARNING: $*" >&2; }

trap 'echo ""; _warn "Sync interrupted. Re-run /optimus-sync to complete."; exit 130' INT TERM

# ─── Configurable constants ───────────────────────────────────────────────────
readonly MARKETPLACE_NAME="${OPTIMUS_MARKETPLACE_NAME:-optimus}"
if ! [[ "$MARKETPLACE_NAME" =~ ^[a-z0-9][a-z0-9_-]*$ ]]; then
  _error "OPTIMUS_MARKETPLACE_NAME must match ^[a-z0-9][a-z0-9_-]*\$ (got: '$MARKETPLACE_NAME')"
  exit 1
fi
readonly DROID_TIMEOUT="${OPTIMUS_DROID_TIMEOUT:-60}"
readonly CLAUDE_TIMEOUT="${OPTIMUS_CLAUDE_TIMEOUT:-60}"
readonly OPTIMUS_REPO_DEFAULT_URL="https://github.com/alexgarzao/optimus"
readonly OPTIMUS_REPO_URL="${OPTIMUS_REPO_URL:-$OPTIMUS_REPO_DEFAULT_URL}"
readonly CLAUDE_MARKETPLACE_FILE="${CLAUDE_MARKETPLACE_FILE:-$HOME/.claude/plugins/marketplaces/${MARKETPLACE_NAME}/.claude-plugin/marketplace.json}"

# ─── Platform detection ───────────────────────────────────────────────────────
HAS_DROID=false
HAS_CLAUDE_CODE=false
command -v droid >/dev/null 2>&1 && HAS_DROID=true
command -v claude >/dev/null 2>&1 && HAS_CLAUDE_CODE=true

# ─── Validate inputs ─────────────────────────────────────────────────────────
if [ "$HAS_DROID" = true ]; then
  if ! [[ "$DROID_TIMEOUT" =~ ^[1-9][0-9]*$ ]]; then
    _error "OPTIMUS_DROID_TIMEOUT must be a positive integer (got: '$DROID_TIMEOUT')"
    exit 1
  fi
fi

if [ "$HAS_CLAUDE_CODE" = true ]; then
  if ! [[ "$CLAUDE_TIMEOUT" =~ ^[1-9][0-9]*$ ]]; then
    _error "OPTIMUS_CLAUDE_TIMEOUT must be a positive integer (got: '$CLAUDE_TIMEOUT')"
    exit 1
  fi
fi

if [ "$HAS_DROID" = false ] && [ "$HAS_CLAUDE_CODE" = false ]; then
  _error "No supported platform found."
  echo "  Install Droid from: https://docs.factory.ai" >&2
  echo "  Or install Claude Code: https://docs.anthropic.com/claude-code" >&2
  exit 1
fi

if ! command -v jq >/dev/null 2>&1; then
  _error "jq is required but not installed."
  exit 1
fi

# ─── Shared helpers ───────────────────────────────────────────────────────────

_droid() {
  if command -v timeout >/dev/null 2>&1; then
    timeout "$DROID_TIMEOUT" droid "$@"
  elif command -v gtimeout >/dev/null 2>&1; then
    gtimeout "$DROID_TIMEOUT" droid "$@"
  else
    droid "$@"
  fi
}

_claude() {
  # Wraps `claude` invocations with a timeout (mirrors _droid() pattern).
  # OPTIMUS_CLAUDE_TIMEOUT is the per-invocation budget in seconds (default 60).
  if command -v timeout >/dev/null 2>&1; then
    timeout "$CLAUDE_TIMEOUT" claude "$@"
  elif command -v gtimeout >/dev/null 2>&1; then
    gtimeout "$CLAUDE_TIMEOUT" claude "$@"
  else
    claude "$@"
  fi
}

_claude_retry_once() {
  # Usage: _claude_retry_once <description> <cmd> [args...]
  # Runs cmd; on failure, sleeps briefly and retries once. Returns final exit code.
  # The caller is responsible for any stdout/stderr suppression on the inner cmd.
  local description="$1"; shift
  local rc=0
  "$@" || rc=$?
  if [ "$rc" -eq 0 ]; then
    return 0
  fi
  echo "  ⚠ $description failed (exit=$rc); retrying once..." >&2
  sleep 1
  rc=0
  "$@" || rc=$?
  return "$rc"
}

_claude_quiet() {
  # Helper to invoke `_claude` while suppressing stdout/stderr. Used together
  # with `_claude_retry_once` so retries get the same suppression.
  _claude "$@" >/dev/null 2>&1
}

_read_result() {
  # Reads single-line result token from $1; emits the token, or:
  #   "MISSING" if file does not exist (no result was written)
  #   "ERROR"   if file exists but is unreadable (permission/IO)
  # Uses bash builtin read (no fork).
  local file="$1" line=""
  if [ ! -f "$file" ]; then
    echo "MISSING"
    return
  fi
  if ! IFS= read -r line < "$file" 2>/dev/null; then
    if [ -r "$file" ]; then
      # File exists, readable, but empty — return empty token.
      echo ""
      return
    fi
    echo "ERROR"
    return
  fi
  echo "$line"
}

# _compute_diffs <expected> <installed>
# Computes diff between expected and installed plugin lists.
# Prints three lines on stdout for the caller to eval-import into local vars:
#   NEW_PLUGINS=<shell-quoted>
#   ORPHANED_PLUGINS=<shell-quoted>
#   EXISTING_PLUGINS=<shell-quoted>
# Caller usage:
#   eval "$(_compute_diffs "$expected" "$installed")"
# Returns non-zero (caller's `set -e` propagates) if `expected` is empty.
_compute_diffs() {
  local expected="$1" installed="$2"
  if [ -z "$expected" ]; then
    _error "BUG: _compute_diffs called with empty expected list"
    return 1
  fi
  local new orphan exist
  if [ -z "$installed" ]; then
    new="$expected"
    orphan=""
    exist=""
  else
    new=$(comm -23 <(printf '%s\n' "$expected" | sort -u) <(printf '%s\n' "$installed" | sort -u))
    orphan=$(comm -13 <(printf '%s\n' "$expected" | sort -u) <(printf '%s\n' "$installed" | sort -u))
    exist=$(comm -12 <(printf '%s\n' "$expected" | sort -u) <(printf '%s\n' "$installed" | sort -u))
  fi
  # Print on stdout for caller eval. `printf %q` does shell-safe quoting;
  # values are already validated plugin names by upstream regex so they're safe.
  printf 'NEW_PLUGINS=%q\n' "$new"
  printf 'ORPHANED_PLUGINS=%q\n' "$orphan"
  printf 'EXISTING_PLUGINS=%q\n' "$exist"
}

# ─── Get expected plugins from marketplace JSON ──────────────────────────────
# Resolves marketplace.json from one of three sources, preferring fresher caches.
# Returns the list of expected plugin names in BARE form (one per line, sorted)
# via stdout. Both Droid (`.factory-plugin/marketplace.json`) and Claude Code
# (`.claude-plugin/marketplace.json`) sources are supported; for Claude Code the
# `optimus-` prefix is stripped so the contract stays bare across platforms.

_resolve_expected_plugins() {
  local marketplace_file=""
  local strip_prefix=false

  # Source 1: Droid marketplace cache
  if [ "$HAS_DROID" = true ]; then
    marketplace_file=$(find ~/.factory -path "*/marketplaces/${MARKETPLACE_NAME}/.factory-plugin/marketplace.json" -type f 2>/dev/null | head -1)
  fi

  # Source 2: Claude Code marketplace cache
  if [ -z "$marketplace_file" ] && [ "$HAS_CLAUDE_CODE" = true ] && [ -f "$CLAUDE_MARKETPLACE_FILE" ]; then
    marketplace_file="$CLAUDE_MARKETPLACE_FILE"
    strip_prefix=true
  fi

  # Source 3: Running from inside the optimus repo
  if [ -z "$marketplace_file" ]; then
    local script_dir
    script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    local repo_root
    repo_root="$(cd "$script_dir/../.." && pwd)"
    if [ -f "$repo_root/AGENTS.md" ] && [ -f "$repo_root/sync/scripts/sync-user-plugins.sh" ]; then
      if [ -f "$repo_root/.factory-plugin/marketplace.json" ]; then
        marketplace_file="$repo_root/.factory-plugin/marketplace.json"
      elif [ -f "$repo_root/.claude-plugin/marketplace.json" ]; then
        marketplace_file="$repo_root/.claude-plugin/marketplace.json"
        strip_prefix=true
      fi
    fi
  fi

  if [ -z "$marketplace_file" ]; then
    _error "Marketplace '${MARKETPLACE_NAME}' not found. Register it first:"
    if [ "$HAS_DROID" = true ]; then
      echo "  droid plugin marketplace add ${OPTIMUS_REPO_URL}" >&2
    fi
    if [ "$HAS_CLAUDE_CODE" = true ]; then
      echo "  claude plugin marketplace add ${OPTIMUS_REPO_URL}" >&2
    fi
    return 1
  fi

  local expected
  if [ "$strip_prefix" = true ]; then
    # Claude Code marketplace uses `optimus-<name>` — strip prefix to get bare names.
    expected=$(jq -r '.plugins[].name' "$marketplace_file" | sed 's/^optimus-//' | sort)
  else
    expected=$(jq -r '.plugins[].name' "$marketplace_file" | sort)
  fi
  if [ -z "$expected" ]; then
    _error "No plugins found in marketplace."
    return 1
  fi

  # Validate plugin names (path-traversal defense)
  local p
  while IFS= read -r p; do
    [ -z "$p" ] && continue
    if ! [[ "$p" =~ ^[a-z0-9][a-z0-9_-]*$ ]]; then
      _error "Invalid plugin name in marketplace.json: '$p' (must match ^[a-z0-9][a-z0-9_-]*\$)"
      return 1
    fi
  done <<< "$expected"

  echo "$expected"
}

# ═══════════════════════════════════════════════════════════════════════════════
# Droid Sync
# ═══════════════════════════════════════════════════════════════════════════════

_sync_droid() {
  local expected="$1"
  echo "── Droid (Factory) ──"
  echo ""

  # Get installed optimus plugins. Single awk pass: filter to lines starting
  # with [a-z0-9] whose first field ends with @MARKETPLACE_NAME, then strip
  # that suffix and emit the bare name.
  local installed
  installed=$(_droid plugin list 2>/dev/null \
    | awk -v mp="@${MARKETPLACE_NAME}" '
        /^[a-z0-9]/ && index($1, mp) == length($1) - length(mp) + 1 {
          sub(mp"$", "", $1)
          print $1
        }
      ' \
    | sort -u) || true

  # Calculate diffs. _compute_diffs prints NEW_PLUGINS=, ORPHANED_PLUGINS=,
  # EXISTING_PLUGINS= on stdout; eval imports them into local vars.
  local NEW_PLUGINS ORPHANED_PLUGINS EXISTING_PLUGINS
  eval "$(_compute_diffs "$expected" "$installed")"
  local new_plugins="$NEW_PLUGINS"
  local orphaned_plugins="$ORPHANED_PLUGINS"
  local existing_plugins="$EXISTING_PLUGINS"

  # All operations run in parallel using temp dir for result collection
  local results_dir
  results_dir=$(mktemp -d)
  local _saved_trap
  _saved_trap=$(trap -p INT TERM)
  # shellcheck disable=SC2064
  trap "rm -rf '$results_dir'; echo ''; _warn 'Sync interrupted. Re-run /optimus-sync to complete.'; exit 130" INT TERM
  local retry_removals="" retry_installs="" retry_updates=""
  local result

  # Remove orphaned plugins (parallel)
  if [ -n "$orphaned_plugins" ]; then
    echo "Removing orphaned plugins..."
    while IFS= read -r plugin; do
      [ -z "$plugin" ] && continue
      (
        if _droid plugin uninstall "${plugin}@${MARKETPLACE_NAME}" >/dev/null 2>&1; then
          echo "OK" > "$results_dir/remove-${plugin}"
        else
          echo "RETRY" > "$results_dir/remove-${plugin}"
        fi
      ) &
    done <<< "$orphaned_plugins"
    wait
    while IFS= read -r plugin; do
      [ -z "$plugin" ] && continue
      result=$(_read_result "$results_dir/remove-${plugin}")
      case "$result" in
        OK)         ;;  # success
        RETRY)      retry_removals+="${plugin}"$'\n' ;;
        MISSING)    echo "  ⚠ $plugin: result file missing (worker did not complete)" >&2; retry_removals+="${plugin}"$'\n' ;;
        ERROR)      echo "  ⚠ $plugin: result file unreadable" >&2; retry_removals+="${plugin}"$'\n' ;;
        *)          retry_removals+="${plugin}"$'\n' ;;  # any other token treated as retry
      esac
    done <<< "$orphaned_plugins"
  fi

  # Install new plugins (parallel)
  if [ -n "$new_plugins" ]; then
    echo "Installing new plugins..."
    while IFS= read -r plugin; do
      [ -z "$plugin" ] && continue
      (
        if _droid plugin install "${plugin}@${MARKETPLACE_NAME}" >/dev/null 2>&1; then
          echo "OK" > "$results_dir/install-${plugin}"
        else
          echo "RETRY" > "$results_dir/install-${plugin}"
        fi
      ) &
    done <<< "$new_plugins"
    wait
    while IFS= read -r plugin; do
      [ -z "$plugin" ] && continue
      result=$(_read_result "$results_dir/install-${plugin}")
      case "$result" in
        OK)         ;;  # success
        RETRY)      retry_installs+="${plugin}"$'\n' ;;
        MISSING)    echo "  ⚠ $plugin: result file missing (worker did not complete)" >&2; retry_installs+="${plugin}"$'\n' ;;
        ERROR)      echo "  ⚠ $plugin: result file unreadable" >&2; retry_installs+="${plugin}"$'\n' ;;
        *)          retry_installs+="${plugin}"$'\n' ;;  # any other token treated as retry
      esac
    done <<< "$new_plugins"
  fi

  # Refresh existing plugins (parallel) via uninstall+install.
  #
  # NOTE: We do NOT call `droid plugin update` here. Optimus ships SKILL prose
  # changes without bumping marketplace.json's `version` field on every PR;
  # `droid plugin update` can be a no-op in that case (mirrors the bug fixed
  # for Claude in PR #44). Uninstall + reinstall guarantees a fresh fetch
  # from the marketplace cache so the user gets the latest committed prose.
  # Cost: one extra round-trip per plugin (~1s); acceptable since the outer
  # loop runs in parallel.
  if [ -n "$existing_plugins" ]; then
    echo "Refreshing existing plugins..."
    while IFS= read -r plugin; do
      [ -z "$plugin" ] && continue
      (
        _droid plugin uninstall "${plugin}@${MARKETPLACE_NAME}" >/dev/null 2>&1 || true
        if _droid plugin install "${plugin}@${MARKETPLACE_NAME}" >/dev/null 2>&1; then
          echo "OK" > "$results_dir/update-${plugin}"
        else
          echo "RETRY" > "$results_dir/update-${plugin}"
        fi
      ) &
    done <<< "$existing_plugins"
    wait
    while IFS= read -r plugin; do
      [ -z "$plugin" ] && continue
      result=$(_read_result "$results_dir/update-${plugin}")
      case "$result" in
        OK)         ;;  # success
        RETRY)      retry_updates+="${plugin}"$'\n' ;;
        MISSING)    echo "  ⚠ $plugin: result file missing (worker did not complete)" >&2; retry_updates+="${plugin}"$'\n' ;;
        ERROR)      echo "  ⚠ $plugin: result file unreadable" >&2; retry_updates+="${plugin}"$'\n' ;;
        *)          retry_updates+="${plugin}"$'\n' ;;  # any other token treated as retry
      esac
    done <<< "$existing_plugins"
  fi

  # Retry transient failures serially
  if [ -n "$retry_removals$retry_installs$retry_updates" ]; then
    echo "Retrying failed plugin operations serially..."
  fi

  if [ -n "$retry_removals" ]; then
    while IFS= read -r plugin; do
      [ -z "$plugin" ] && continue
      if _droid plugin uninstall "${plugin}@${MARKETPLACE_NAME}" >/dev/null 2>&1; then
        echo "OK" > "$results_dir/remove-${plugin}"
      else
        echo "FAIL" > "$results_dir/remove-${plugin}"
      fi
    done <<< "$retry_removals"
  fi

  if [ -n "$retry_installs" ]; then
    while IFS= read -r plugin; do
      [ -z "$plugin" ] && continue
      if _droid plugin install "${plugin}@${MARKETPLACE_NAME}" >/dev/null 2>&1; then
        echo "OK" > "$results_dir/install-${plugin}"
      else
        echo "FAIL" > "$results_dir/install-${plugin}"
      fi
    done <<< "$retry_installs"
  fi

  if [ -n "$retry_updates" ]; then
    # Serial retry of the uninstall+install refresh path. The parallel pass
    # may have lost a race (e.g. plugin daemon contention); doing it serially
    # gives each plugin a clean shot.
    while IFS= read -r plugin; do
      [ -z "$plugin" ] && continue
      _droid plugin uninstall "${plugin}@${MARKETPLACE_NAME}" >/dev/null 2>&1 || true
      if _droid plugin install "${plugin}@${MARKETPLACE_NAME}" >/dev/null 2>&1; then
        echo "OK" > "$results_dir/update-${plugin}"
      else
        echo "FAIL" > "$results_dir/update-${plugin}"
      fi
    done <<< "$retry_updates"
  fi

  # Collect results
  local removed=0 added=0 updated=0 failed=0

  if [ -n "$orphaned_plugins" ]; then
    while IFS= read -r plugin; do
      [ -z "$plugin" ] && continue
      result=$(_read_result "$results_dir/remove-${plugin}")
      if [ "$result" = "OK" ]; then
        echo "  - $plugin ... OK"
        removed=$((removed + 1))
      else
        echo "  - $plugin ... FAIL"
        failed=$((failed + 1))
      fi
    done <<< "$orphaned_plugins"
  fi

  if [ -n "$new_plugins" ]; then
    while IFS= read -r plugin; do
      [ -z "$plugin" ] && continue
      result=$(_read_result "$results_dir/install-${plugin}")
      if [ "$result" = "OK" ]; then
        echo "  + $plugin ... OK"
        added=$((added + 1))
      else
        echo "  + $plugin ... FAIL"
        failed=$((failed + 1))
      fi
    done <<< "$new_plugins"
  fi

  if [ -n "$existing_plugins" ]; then
    while IFS= read -r plugin; do
      [ -z "$plugin" ] && continue
      result=$(_read_result "$results_dir/update-${plugin}")
      case "$result" in
        OK)          echo "  * $plugin ... OK (refreshed)"; updated=$((updated + 1)) ;;
        *)           echo "  * $plugin ... FAIL";           failed=$((failed + 1)) ;;
      esac
    done <<< "$existing_plugins"
  fi

  rm -rf "$results_dir"
  eval "${_saved_trap:-trap - INT TERM}"

  echo ""
  echo "  Droid — Added: $added | Updated: $updated | Removed: $removed | Failed: $failed"

  local rc=0
  [ "$failed" -gt 0 ] && rc=1
  return $rc
}

# ═══════════════════════════════════════════════════════════════════════════════
# Claude Code Sync
# ═══════════════════════════════════════════════════════════════════════════════
#
# Schema observed for `claude plugin list --json` (Claude Code 2.1.x):
#   [
#     {
#       "id": "<plugin-name>@<marketplace-name>",
#       "version": "<semver>",
#       "scope": "user",
#       "enabled": true,
#       "installPath": "/Users/.../.claude/plugins/cache/<marketplace>/<plugin>/<version>",
#       "installedAt": "2026-...",
#       "lastUpdated": "2026-...",
#       "gitCommitSha": "..."   // optional
#       "mcpServers": {...}     // optional
#     },
#     ...
#   ]
# We filter by marketplace via `select(.id | endswith("@<marketplace>"))`.

_sync_claude_code() {
  # The first arg (the bare-plugin EXPECTED list) is consumed by the Droid
  # branch only — Claude installs a SINGLE plugin (`optimus`) regardless of
  # how many bare plugins the marketplace lists. We accept and ignore it so
  # the call sites stay symmetric.
  local _expected_unused="${1:-}"
  local marketplace="${2:-$MARKETPLACE_NAME}"
  : "$_expected_unused"  # avoid SC2034

  echo "── Claude Code ──"
  echo ""

  # Get currently installed optimus-marketplace plugins. Two cohorts can
  # coexist:
  #   - The single `optimus@optimus` plugin (the new layout).
  #   - Legacy `optimus-<name>@optimus` installs from the pre-2.0 layout.
  # We sync the new plugin first, then sweep any legacy entries.
  local installed_ids=""
  installed_ids=$(_claude plugin list --json 2>/dev/null \
    | jq -r --arg mp "@${marketplace}" '.[] | select(.id | endswith($mp)) | .id' \
    | sort) || true

  local single_installed=false
  local legacy_plugins=""
  if [ -n "$installed_ids" ]; then
    while IFS= read -r id; do
      [ -z "$id" ] && continue
      local bare="${id%@"${marketplace}"}"
      if [ "$bare" = "optimus" ]; then
        single_installed=true
      else
        legacy_plugins="${legacy_plugins}${bare}
"
      fi
    done <<< "$installed_ids"
  fi

  local added=0 updated=0 removed=0 failed=0

  # Install or refresh the single `optimus` plugin. Each call has one retry on
  # transient failure (no parallelism — Claude's plugin daemon owns the cache).
  #
  # NOTE: When the plugin is already installed we uninstall + reinstall instead
  # of `claude plugin update`. Reason: `claude plugin update` is a no-op when
  # the plugin's `version` field in marketplace.json hasn't changed, even if
  # the underlying source files in the repo have. Since Optimus ships SKILL
  # changes without bumping the marketplace version on every PR, `update` would
  # leave users on stale cached SKILL.md content (e.g. the cache at
  # `~/.claude/plugins/cache/optimus/optimus/2.0.0/...` would not refresh).
  # Uninstall + install forces a fresh fetch from the marketplace cache,
  # guaranteeing the user runs the latest committed prose. Cost: one extra
  # round-trip to the plugin daemon (~1s); acceptable.
  if [ "$single_installed" = false ]; then
    if _claude_retry_once "install optimus@${marketplace}" \
        _claude_quiet plugin install "optimus@${marketplace}" --scope user; then
      echo "  + optimus ... OK"
      added=$((added + 1))
    else
      echo "  + optimus ... FAIL"
      failed=$((failed + 1))
    fi
  else
    # Force-refresh path: uninstall (best-effort) then reinstall. If the
    # uninstall fails for a transient reason, the reinstall path will still
    # try to install over whatever state remains — `claude plugin install`
    # handles "already installed" gracefully when scopes match.
    _claude_quiet plugin uninstall "optimus@${marketplace}" || true
    if _claude_retry_once "reinstall optimus@${marketplace}" \
        _claude_quiet plugin install "optimus@${marketplace}" --scope user; then
      echo "  * optimus ... OK (refreshed)"
      updated=$((updated + 1))
    else
      echo "  * optimus ... FAIL (reinstall)"
      failed=$((failed + 1))
    fi
  fi

  # Sweep legacy per-plugin installs. They no longer back any active
  # marketplace entry, so unconditional removal is correct.
  if [ -n "$legacy_plugins" ]; then
    while IFS= read -r plugin; do
      [ -z "$plugin" ] && continue
      if _claude_retry_once "uninstall ${plugin}@${marketplace}" \
          _claude_quiet plugin uninstall "${plugin}@${marketplace}"; then
        echo "  - $plugin (legacy) ... OK"
        removed=$((removed + 1))
      else
        echo "  - $plugin (legacy) ... FAIL"
        failed=$((failed + 1))
      fi
    done <<< "$legacy_plugins"
  fi

  echo ""
  echo "  Claude Code — Added: $added | Updated: $updated | Removed: $removed | Failed: $failed"

  [ "$failed" -gt 0 ] && return 1
  return 0
}

# ═══════════════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════════════

echo "=== Optimus Plugin Sync ==="
echo ""

# Detect platforms
platforms=""
if [ "$HAS_DROID" = true ]; then platforms="${platforms}Droid "; fi
if [ "$HAS_CLAUDE_CODE" = true ]; then platforms="${platforms}Claude Code "; fi
echo "Platforms: $platforms"
echo ""

# Surface a custom OPTIMUS_REPO_URL so users notice it on each run.
if [ "$OPTIMUS_REPO_URL" != "$OPTIMUS_REPO_DEFAULT_URL" ]; then
  echo "Note: using custom OPTIMUS_REPO_URL=$OPTIMUS_REPO_URL"
  echo ""
fi

# Refresh both marketplace sources before resolving EXPECTED
if [ "$HAS_DROID" = true ]; then
  echo "Updating Droid marketplace..."
  _droid plugin marketplace update "$MARKETPLACE_NAME" >/dev/null 2>&1 || _warn "Could not update Droid marketplace. Using cached version."
fi
if [ "$HAS_CLAUDE_CODE" = true ]; then
  echo "Updating Claude Code marketplace..."
  _claude plugin marketplace update "$MARKETPLACE_NAME" >/dev/null 2>&1 || _warn "Could not update Claude Code marketplace. Using cached version."
fi
echo ""

# Resolve expected plugins (shared across platforms)
EXPECTED=$(_resolve_expected_plugins) || exit 1

# Run sync per platform
droid_rc=0
claude_rc=0

if [ "$HAS_DROID" = true ]; then
  _sync_droid "$EXPECTED" || droid_rc=$?
  echo ""
fi

if [ "$HAS_CLAUDE_CODE" = true ]; then
  _sync_claude_code "$EXPECTED" "$MARKETPLACE_NAME" || claude_rc=$?
  echo ""
fi

echo "=== Sync Complete ==="

# Exit with failure if any platform had failures
if [ "$droid_rc" -gt 0 ] || [ "$claude_rc" -gt 0 ]; then
  exit 1
fi
