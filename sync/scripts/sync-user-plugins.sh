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
#   - Droid:        bare names (e.g. `plan`, `build`, `sync`) — matches `.factory-plugin/marketplace.json`
#   - Claude Code:  prefixed names (e.g. `optimus-plan`) — matches `.claude-plugin/marketplace.json`
#   - The EXPECTED list returned by `_resolve_expected_plugins` is in BARE form (legacy contract).
#     `_sync_claude_code` adds the `optimus-` prefix when building Claude Code commands.

_error() { echo "ERROR: $*" >&2; }
_warn() { echo "WARNING: $*" >&2; }

trap 'echo ""; _warn "Sync interrupted. Re-run /optimus-sync to complete."; exit 130' INT TERM

# ─── Configurable constants ───────────────────────────────────────────────────
readonly MARKETPLACE_NAME="${OPTIMUS_MARKETPLACE_NAME:-optimus}"
readonly DROID_TIMEOUT="${OPTIMUS_DROID_TIMEOUT:-60}"
readonly OPTIMUS_REPO_URL="${OPTIMUS_REPO_URL:-https://github.com/alexgarzao/optimus}"
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

_read_result() {
  local file="$1"
  cat "$file" 2>/dev/null || echo "FAIL"
}

# _compute_diffs <expected> <installed>
# Sets globals: NEW_PLUGINS, ORPHANED_PLUGINS, EXISTING_PLUGINS
_compute_diffs() {
  local expected="$1"
  local installed="$2"
  if [ -z "$installed" ]; then
    NEW_PLUGINS="$expected"
    ORPHANED_PLUGINS=""
    EXISTING_PLUGINS=""
  else
    NEW_PLUGINS=$(comm -23 <(echo "$expected") <(echo "$installed"))
    ORPHANED_PLUGINS=$(comm -13 <(echo "$expected") <(echo "$installed"))
    EXISTING_PLUGINS=$(comm -12 <(echo "$expected") <(echo "$installed"))
  fi
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

  # Get installed optimus plugins
  local installed
  installed=$(_droid plugin list 2>/dev/null \
    | grep -F "@${MARKETPLACE_NAME}" \
    | awk '{print $1}' \
    | while IFS= read -r _line; do echo "${_line%@"${MARKETPLACE_NAME}"}"; done \
    | sort) || true

  # Calculate diffs
  _compute_diffs "$expected" "$installed"
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
      if [ "$(_read_result "$results_dir/remove-${plugin}")" = "RETRY" ]; then
        retry_removals="${retry_removals}${plugin}
"
      fi
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
      if [ "$(_read_result "$results_dir/install-${plugin}")" = "RETRY" ]; then
        retry_installs="${retry_installs}${plugin}
"
      fi
    done <<< "$new_plugins"
  fi

  # Update existing plugins (parallel)
  if [ -n "$existing_plugins" ]; then
    echo "Updating existing plugins..."
    while IFS= read -r plugin; do
      [ -z "$plugin" ] && continue
      (
        if _droid plugin update "${plugin}@${MARKETPLACE_NAME}" >/dev/null 2>&1; then
          echo "OK" > "$results_dir/update-${plugin}"
        else
          echo "RETRY" > "$results_dir/update-${plugin}"
        fi
      ) &
    done <<< "$existing_plugins"
    wait
    while IFS= read -r plugin; do
      [ -z "$plugin" ] && continue
      if [ "$(_read_result "$results_dir/update-${plugin}")" = "RETRY" ]; then
        retry_updates="${retry_updates}${plugin}
"
      fi
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
    while IFS= read -r plugin; do
      [ -z "$plugin" ] && continue
      if _droid plugin update "${plugin}@${MARKETPLACE_NAME}" >/dev/null 2>&1; then
        echo "OK" > "$results_dir/update-${plugin}"
        continue
      fi
      _droid plugin uninstall "${plugin}@${MARKETPLACE_NAME}" >/dev/null 2>&1 || true
      if _droid plugin install "${plugin}@${MARKETPLACE_NAME}" >/dev/null 2>&1; then
        echo "REINSTALLED" > "$results_dir/update-${plugin}"
      else
        echo "FAIL" > "$results_dir/update-${plugin}"
      fi
    done <<< "$retry_updates"
  fi

  # Collect results
  local removed=0 added=0 updated=0 failed=0
  local result

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
        OK)          echo "  * $plugin ... OK";            updated=$((updated + 1)) ;;
        REINSTALLED) echo "  * $plugin ... OK (reinstalled)"; updated=$((updated + 1)) ;;
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
#       "version": "1.0.0",
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
  local expected="$1"  # bare plugin names, one per line, sorted
  local marketplace="${2:-$MARKETPLACE_NAME}"

  echo "── Claude Code ──"
  echo ""

  # Get currently installed optimus plugins (bare names, sorted)
  local installed=""
  installed=$(claude plugin list --json 2>/dev/null \
    | jq -r --arg mp "@${marketplace}" '.[] | select(.id | endswith($mp)) | .id | sub("@.*$"; "") | sub("^optimus-"; "")' \
    | sort) || true

  # Calculate diffs
  _compute_diffs "$expected" "$installed"
  local new_plugins="$NEW_PLUGINS"
  local orphaned_plugins="$ORPHANED_PLUGINS"
  local existing_plugins="$EXISTING_PLUGINS"

  local added=0 updated=0 removed=0 failed=0

  # Install new plugins
  if [ -n "$new_plugins" ]; then
    while IFS= read -r plugin; do
      [ -z "$plugin" ] && continue
      if claude plugin install "optimus-${plugin}@${marketplace}" --scope user >/dev/null 2>&1; then
        echo "  + $plugin ... OK"
        added=$((added + 1))
      else
        echo "  + $plugin ... FAIL"
        failed=$((failed + 1))
      fi
    done <<< "$new_plugins"
  fi

  # Update existing plugins
  if [ -n "$existing_plugins" ]; then
    while IFS= read -r plugin; do
      [ -z "$plugin" ] && continue
      if claude plugin update "optimus-${plugin}@${marketplace}" >/dev/null 2>&1; then
        echo "  * $plugin ... OK"
        updated=$((updated + 1))
      else
        echo "  * $plugin ... FAIL"
        failed=$((failed + 1))
      fi
    done <<< "$existing_plugins"
  fi

  # Remove orphaned plugins
  if [ -n "$orphaned_plugins" ]; then
    while IFS= read -r plugin; do
      [ -z "$plugin" ] && continue
      if claude plugin uninstall "optimus-${plugin}@${marketplace}" >/dev/null 2>&1; then
        echo "  - $plugin ... OK"
        removed=$((removed + 1))
      else
        echo "  - $plugin ... FAIL"
        failed=$((failed + 1))
      fi
    done <<< "$orphaned_plugins"
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
_default_url="https://github.com/alexgarzao/optimus"
if [ "$OPTIMUS_REPO_URL" != "$_default_url" ]; then
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
  claude plugin marketplace update "$MARKETPLACE_NAME" >/dev/null 2>&1 || _warn "Could not update Claude Code marketplace. Using cached version."
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
