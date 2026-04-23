#!/usr/bin/env bash
set -euo pipefail

# Syncs installed Optimus plugins with the marketplace.
# - Installs new plugins that were added to the marketplace
# - Removes orphaned plugins that were removed from the marketplace
# - Updates all existing plugins (with uninstall+reinstall fallback for scope conflicts)

_error() { echo "ERROR: $*" >&2; }
_warn() { echo "WARNING: $*" >&2; }

trap 'echo ""; _warn "Sync interrupted. Re-run /optimus-sync to complete."; exit 130' INT TERM

readonly MARKETPLACE_NAME="${OPTIMUS_MARKETPLACE_NAME:-optimus}"
readonly DROID_TIMEOUT="${OPTIMUS_DROID_TIMEOUT:-60}"
if ! [[ "$DROID_TIMEOUT" =~ ^[1-9][0-9]*$ ]]; then
  _error "OPTIMUS_DROID_TIMEOUT must be a positive integer (got: '$DROID_TIMEOUT')"
  exit 1
fi

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

echo "=== Optimus Plugin Sync ==="
echo ""

# Check dependencies
if ! command -v droid >/dev/null 2>&1; then
  _error "droid CLI is required but not installed."
  echo "  Install from: https://docs.factory.ai" >&2
  exit 1
fi

if ! command -v jq >/dev/null 2>&1; then
  _error "jq is required but not installed."
  exit 1
fi

# Step 1: Update marketplace
echo "Updating marketplace..."
if ! _droid plugin marketplace update "$MARKETPLACE_NAME" 2>/dev/null; then
  _warn "Could not update marketplace. Proceeding with cached version."
fi

# Step 2: Get expected plugins from marketplace
MARKETPLACE_FILE=$(find ~/.factory -path "*/marketplaces/${MARKETPLACE_NAME}/.factory-plugin/marketplace.json" -type f 2>/dev/null | head -1)
if [ -z "$MARKETPLACE_FILE" ]; then
  _error "Marketplace '${MARKETPLACE_NAME}' not found. Register it first:"
  echo "  droid plugin marketplace add https://github.com/alexgarzao/optimus" >&2
  exit 1
fi

EXPECTED=$(jq -r '.plugins[].name' "$MARKETPLACE_FILE" | sort)
if [ -z "$EXPECTED" ]; then
  _error "No plugins found in marketplace."
  exit 1
fi

# Step 3: Get installed optimus plugins
INSTALLED=$(_droid plugin list 2>/dev/null \
  | grep -F "@${MARKETPLACE_NAME}" \
  | awk '{print $1}' \
  | while IFS= read -r _line; do echo "${_line%@"${MARKETPLACE_NAME}"}"; done \
  | sort) || true

# Step 4: Calculate diffs
if [ -z "$INSTALLED" ]; then
  # First-time install — all plugins are new, nothing to remove or update
  NEW_PLUGINS="$EXPECTED"
  ORPHANED_PLUGINS=""
  EXISTING_PLUGINS=""
else
  # comm -23: lines only in EXPECTED (new plugins to install)
  NEW_PLUGINS=$(comm -23 <(echo "$EXPECTED") <(echo "$INSTALLED"))
  # comm -13: lines only in INSTALLED (orphaned plugins to remove)
  ORPHANED_PLUGINS=$(comm -13 <(echo "$EXPECTED") <(echo "$INSTALLED"))
  # comm -12: lines in both (existing plugins to update)
  EXISTING_PLUGINS=$(comm -12 <(echo "$EXPECTED") <(echo "$INSTALLED"))
fi

# All operations run in parallel using temp dir for result collection
RESULTS_DIR=$(mktemp -d)
_cleanup() { rm -rf "$RESULTS_DIR"; }
trap '_cleanup; echo ""; _warn "Sync interrupted. Re-run /optimus-sync to complete."; exit 130' INT TERM
trap '_cleanup' EXIT

# Step 5: Remove orphaned plugins (parallel)
if [ -n "$ORPHANED_PLUGINS" ]; then
  echo ""
  echo "Removing orphaned plugins..."
  while IFS= read -r plugin; do
    [ -z "$plugin" ] && continue
    (
      if _droid plugin uninstall "${plugin}@${MARKETPLACE_NAME}" >/dev/null 2>&1; then
        echo "OK" > "$RESULTS_DIR/remove-${plugin}"
      else
        echo "FAIL" > "$RESULTS_DIR/remove-${plugin}"
      fi
    ) &
  done <<< "$ORPHANED_PLUGINS"
  wait
fi

# Step 6: Install new plugins (parallel)
if [ -n "$NEW_PLUGINS" ]; then
  echo "Installing new plugins..."
  while IFS= read -r plugin; do
    [ -z "$plugin" ] && continue
    (
      if _droid plugin install "${plugin}@${MARKETPLACE_NAME}" >/dev/null 2>&1; then
        echo "OK" > "$RESULTS_DIR/install-${plugin}"
      else
        echo "FAIL" > "$RESULTS_DIR/install-${plugin}"
      fi
    ) &
  done <<< "$NEW_PLUGINS"
  wait
fi

# Step 7: Update existing plugins (parallel)
if [ -n "$EXISTING_PLUGINS" ]; then
  echo "Updating existing plugins..."
  while IFS= read -r plugin; do
    [ -z "$plugin" ] && continue
    (
      if _droid plugin update "${plugin}@${MARKETPLACE_NAME}" >/dev/null 2>&1; then
        echo "OK" > "$RESULTS_DIR/update-${plugin}"
      else
        _droid plugin uninstall "${plugin}@${MARKETPLACE_NAME}" >/dev/null 2>&1 || true
        if _droid plugin install "${plugin}@${MARKETPLACE_NAME}" >/dev/null 2>&1; then
          echo "REINSTALLED" > "$RESULTS_DIR/update-${plugin}"
        else
          echo "FAIL" > "$RESULTS_DIR/update-${plugin}"
        fi
      fi
    ) &
  done <<< "$EXISTING_PLUGINS"
  wait
fi

# Step 8: Collect results and print summary
REMOVED=0; ADDED=0; UPDATED=0; FAILED=0

if [ -n "$ORPHANED_PLUGINS" ]; then
  while IFS= read -r plugin; do
    [ -z "$plugin" ] && continue
    result=$(cat "$RESULTS_DIR/remove-${plugin}" 2>/dev/null || echo "FAIL")
    if [ "$result" = "OK" ]; then
      echo "  - $plugin ... OK"
      REMOVED=$((REMOVED + 1))
    else
      echo "  - $plugin ... FAIL"
      FAILED=$((FAILED + 1))
    fi
  done <<< "$ORPHANED_PLUGINS"
fi

if [ -n "$NEW_PLUGINS" ]; then
  while IFS= read -r plugin; do
    [ -z "$plugin" ] && continue
    result=$(cat "$RESULTS_DIR/install-${plugin}" 2>/dev/null || echo "FAIL")
    if [ "$result" = "OK" ]; then
      echo "  + $plugin ... OK"
      ADDED=$((ADDED + 1))
    else
      echo "  + $plugin ... FAIL"
      FAILED=$((FAILED + 1))
    fi
  done <<< "$NEW_PLUGINS"
fi

if [ -n "$EXISTING_PLUGINS" ]; then
  while IFS= read -r plugin; do
    [ -z "$plugin" ] && continue
    result=$(cat "$RESULTS_DIR/update-${plugin}" 2>/dev/null || echo "FAIL")
    case "$result" in
      OK)          echo "  * $plugin ... OK";            UPDATED=$((UPDATED + 1)) ;;
      REINSTALLED) echo "  * $plugin ... OK (reinstalled)"; UPDATED=$((UPDATED + 1)) ;;
      *)           echo "  * $plugin ... FAIL";           FAILED=$((FAILED + 1)) ;;
    esac
  done <<< "$EXISTING_PLUGINS"
fi

echo ""
echo "=== Sync Complete ==="
echo "  Added:   $ADDED"
echo "  Updated: $UPDATED"
echo "  Removed: $REMOVED"
if [ "$FAILED" -gt 0 ]; then
  echo "  Failed:  $FAILED"
  exit 1
fi
