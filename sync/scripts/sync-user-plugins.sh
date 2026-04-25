#!/usr/bin/env bash
set -euo pipefail

# Syncs installed Optimus plugins with the marketplace.
# Supports two platforms:
#   - Droid (Factory): uses `droid plugin install/update/uninstall`
#   - Claude Code: copies SKILL.md files to ~/.claude/skills/default/optimus-<name>/
#
# Detects which platforms are available and syncs both in a single run.
# - Installs new plugins that were added to the marketplace
# - Removes orphaned plugins that were removed from the marketplace
# - Updates all existing plugins (with uninstall+reinstall fallback for Droid scope conflicts)

_error() { echo "ERROR: $*" >&2; }
_warn() { echo "WARNING: $*" >&2; }

trap 'echo ""; _warn "Sync interrupted. Re-run /optimus-sync to complete."; exit 130' INT TERM

# ─── Configurable constants ───────────────────────────────────────────────────
readonly MARKETPLACE_NAME="${OPTIMUS_MARKETPLACE_NAME:-optimus}"
readonly DROID_TIMEOUT="${OPTIMUS_DROID_TIMEOUT:-60}"
readonly OPTIMUS_CACHE_DIR="${OPTIMUS_CACHE_DIR:-$HOME/.optimus/repo}"
readonly CLAUDE_SKILLS_DIR="${CLAUDE_SKILLS_DIR:-$HOME/.claude/skills/default}"
readonly OPTIMUS_REPO_URL="${OPTIMUS_REPO_URL:-https://github.com/alexgarzao/optimus}"

# ─── Platform detection ───────────────────────────────────────────────────────
HAS_DROID=false
HAS_CLAUDE=false
command -v droid >/dev/null 2>&1 && HAS_DROID=true
[ -d "$HOME/.claude" ] && HAS_CLAUDE=true

# ─── Validate inputs ─────────────────────────────────────────────────────────
if [ "$HAS_DROID" = true ]; then
  if ! [[ "$DROID_TIMEOUT" =~ ^[1-9][0-9]*$ ]]; then
    _error "OPTIMUS_DROID_TIMEOUT must be a positive integer (got: '$DROID_TIMEOUT')"
    exit 1
  fi
fi

if [ "$HAS_DROID" = false ] && [ "$HAS_CLAUDE" = false ]; then
  _error "No supported platform found."
  echo "  Install Droid from: https://docs.factory.ai" >&2
  echo "  Or create ~/.claude/ for Claude Code support." >&2
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

_count_lines() {
  echo "$1" | grep -c . 2>/dev/null || echo 0
}

_read_result() {
  local file="$1"
  cat "$file" 2>/dev/null || echo "FAIL"
}

# ─── Get expected plugins from marketplace JSON ──────────────────────────────
# Resolves marketplace.json from: Droid cache, Optimus repo cache, or repo root.
# Returns the list of expected plugin names (sorted, one per line) via stdout.

_resolve_expected_plugins() {
  local marketplace_file=""

  # Source 1: Droid marketplace cache
  if [ "$HAS_DROID" = true ]; then
    marketplace_file=$(find ~/.factory -path "*/marketplaces/${MARKETPLACE_NAME}/.factory-plugin/marketplace.json" -type f 2>/dev/null | head -1)
  fi

  # Source 2: Optimus repo cache
  if [ -z "$marketplace_file" ] && [ -f "$OPTIMUS_CACHE_DIR/.factory-plugin/marketplace.json" ]; then
    marketplace_file="$OPTIMUS_CACHE_DIR/.factory-plugin/marketplace.json"
  fi

  # Source 3: Running from inside the optimus repo
  if [ -z "$marketplace_file" ]; then
    local script_dir
    script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    local repo_root
    repo_root="$(cd "$script_dir/../.." && pwd)"
    if [ -f "$repo_root/.factory-plugin/marketplace.json" ]; then
      marketplace_file="$repo_root/.factory-plugin/marketplace.json"
    fi
  fi

  if [ -z "$marketplace_file" ]; then
    _error "Marketplace '${MARKETPLACE_NAME}' not found. Register it first:"
    echo "  droid plugin marketplace add ${OPTIMUS_REPO_URL}" >&2
    echo "  Or run: git clone --depth 1 ${OPTIMUS_REPO_URL} ${OPTIMUS_CACHE_DIR}" >&2
    return 1
  fi

  local expected
  expected=$(jq -r '.plugins[].name' "$marketplace_file" | sort)
  if [ -z "$expected" ]; then
    _error "No plugins found in marketplace."
    return 1
  fi

  echo "$expected"
}

# ═══════════════════════════════════════════════════════════════════════════════
# Droid Sync
# ═══════════════════════════════════════════════════════════════════════════════

_sync_droid() {
  local expected="$1"
  echo "── Droid (Factory) ──"
  echo ""

  # Update marketplace
  echo "Updating marketplace..."
  if ! _droid plugin marketplace update "$MARKETPLACE_NAME" 2>/dev/null; then
    _warn "Could not update marketplace. Proceeding with cached version."
  fi

  # Get installed optimus plugins
  local installed
  installed=$(_droid plugin list 2>/dev/null \
    | grep -F "@${MARKETPLACE_NAME}" \
    | awk '{print $1}' \
    | while IFS= read -r _line; do echo "${_line%@"${MARKETPLACE_NAME}"}"; done \
    | sort) || true

  # Calculate diffs
  local new_plugins orphaned_plugins existing_plugins
  if [ -z "$installed" ]; then
    new_plugins="$expected"
    orphaned_plugins=""
    existing_plugins=""
  else
    new_plugins=$(comm -23 <(echo "$expected") <(echo "$installed"))
    orphaned_plugins=$(comm -13 <(echo "$expected") <(echo "$installed"))
    existing_plugins=$(comm -12 <(echo "$expected") <(echo "$installed"))
  fi

  # All operations run in parallel using temp dir for result collection
  local results_dir
  results_dir=$(mktemp -d)
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

  echo ""
  echo "  Droid — Added: $added | Updated: $updated | Removed: $removed | Failed: $failed"

  [ "$failed" -gt 0 ] && return 1
  return 0
}

# ═══════════════════════════════════════════════════════════════════════════════
# Repo Cache Management (used by Claude Code sync and as marketplace fallback)
# ═══════════════════════════════════════════════════════════════════════════════

# Track whether repo cache is usable (set by _ensure_repo_cache)
_REPO_CACHE_OK=false

_ensure_repo_cache() {
  local repo_dir="$OPTIMUS_CACHE_DIR"

  if [ -d "$repo_dir/.git" ]; then
    echo "Updating repo cache..."
    if ! git -C "$repo_dir" fetch --depth 1 origin main 2>/dev/null; then
      _warn "Could not fetch latest. Using cached version."
    else
      git -C "$repo_dir" reset --hard origin/main 2>/dev/null || true
    fi
    _REPO_CACHE_OK=true
  else
    echo "Cloning repo cache..."
    if git clone --depth 1 "$OPTIMUS_REPO_URL" "$repo_dir" 2>/dev/null; then
      _REPO_CACHE_OK=true
    else
      _warn "Could not clone repo. Claude Code sync requires a repo cache."
      echo "  Run: git clone --depth 1 ${OPTIMUS_REPO_URL} ${repo_dir}" >&2
      _REPO_CACHE_OK=false
    fi
  fi
}

# ═══════════════════════════════════════════════════════════════════════════════
# Claude Code Sync
# ═══════════════════════════════════════════════════════════════════════════════

_sync_claude_code() {
  local expected="$1"
  echo "── Claude Code ──"
  echo ""

  local repo_dir="$OPTIMUS_CACHE_DIR"

  if [ "$_REPO_CACHE_OK" = false ]; then
    echo "  Claude Code — Added: 0 | Updated: 0 | Removed: 0 | Failed: 0 (skipped)"
    return 0
  fi

  local skills_dir="$CLAUDE_SKILLS_DIR"
  mkdir -p "$skills_dir"

  # Step 3: Get currently installed optimus skills
  local installed=""
  if [ -d "$skills_dir" ]; then
    installed=$(find "$skills_dir" -maxdepth 1 -type d -name 'optimus-*' -exec basename {} \; 2>/dev/null | sed 's/^optimus-//' | sort) || true
  fi

  # Step 4: Calculate diffs
  local new_plugins orphaned_plugins existing_plugins
  if [ -z "$installed" ]; then
    new_plugins="$expected"
    orphaned_plugins=""
    existing_plugins=""
  else
    new_plugins=$(comm -23 <(echo "$expected") <(echo "$installed"))
    orphaned_plugins=$(comm -13 <(echo "$expected") <(echo "$installed"))
    existing_plugins=$(comm -12 <(echo "$expected") <(echo "$installed"))
  fi

  local added=0 updated=0 removed=0 failed=0 unchanged=0

  # Step 5: Install new plugins
  if [ -n "$new_plugins" ]; then
    while IFS= read -r plugin; do
      [ -z "$plugin" ] && continue
      local src="$repo_dir/${plugin}/skills/optimus-${plugin}/SKILL.md"
      local dest_dir="$skills_dir/optimus-${plugin}"
      if [ -f "$src" ]; then
        mkdir -p "$dest_dir"
        cp "$src" "$dest_dir/SKILL.md"
        echo "  + $plugin ... OK"
        added=$((added + 1))
      else
        echo "  + $plugin ... FAIL (source not found)"
        failed=$((failed + 1))
      fi
    done <<< "$new_plugins"
  fi

  # Step 6: Update existing plugins (skip if unchanged)
  if [ -n "$existing_plugins" ]; then
    while IFS= read -r plugin; do
      [ -z "$plugin" ] && continue
      local src="$repo_dir/${plugin}/skills/optimus-${plugin}/SKILL.md"
      local dest="$skills_dir/optimus-${plugin}/SKILL.md"
      if [ ! -f "$src" ]; then
        echo "  * $plugin ... FAIL (source not found)"
        failed=$((failed + 1))
        continue
      fi
      if [ -f "$dest" ] && diff -q "$src" "$dest" >/dev/null 2>&1; then
        echo "  * $plugin ... unchanged"
        unchanged=$((unchanged + 1))
      else
        mkdir -p "$skills_dir/optimus-${plugin}"
        cp "$src" "$dest"
        echo "  * $plugin ... OK"
        updated=$((updated + 1))
      fi
    done <<< "$existing_plugins"
  fi

  # Step 7: Remove orphaned plugins (ONLY optimus- prefixed)
  if [ -n "$orphaned_plugins" ]; then
    while IFS= read -r plugin; do
      [ -z "$plugin" ] && continue
      local target_dir="$skills_dir/optimus-${plugin}"
      if [ -d "$target_dir" ]; then
        rm -rf "$target_dir"
        echo "  - $plugin ... OK"
        removed=$((removed + 1))
      fi
    done <<< "$orphaned_plugins"
  fi

  echo ""
  local summary="Claude Code — Added: $added | Updated: $updated | Removed: $removed | Failed: $failed"
  if [ "$unchanged" -gt 0 ]; then
    summary="$summary | Unchanged: $unchanged"
  fi
  echo "  $summary"

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
if [ "$HAS_CLAUDE" = true ]; then platforms="${platforms}Claude Code "; fi
echo "Platforms: $platforms"
echo ""

# Ensure repo cache is populated (needed for Claude Code sync and marketplace fallback)
if [ "$HAS_CLAUDE" = true ]; then
  _ensure_repo_cache
  echo ""
fi

# Resolve expected plugins (shared across platforms)
EXPECTED=$(_resolve_expected_plugins) || exit 1

# Run sync per platform
droid_rc=0
claude_rc=0

if [ "$HAS_DROID" = true ]; then
  _sync_droid "$EXPECTED" || droid_rc=$?
  echo ""
fi

if [ "$HAS_CLAUDE" = true ]; then
  _sync_claude_code "$EXPECTED" || claude_rc=$?
  echo ""
fi

echo "=== Sync Complete ==="

# Exit with failure if any platform had failures
if [ "$droid_rc" -gt 0 ] || [ "$claude_rc" -gt 0 ]; then
  exit 1
fi
