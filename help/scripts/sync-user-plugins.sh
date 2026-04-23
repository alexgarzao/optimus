#!/usr/bin/env bash
set -euo pipefail

# Syncs installed Optimus plugins with the marketplace.
# - Installs new plugins that were added to the marketplace
# - Removes orphaned plugins that were removed from the marketplace
# - Updates all existing plugins (with uninstall+reinstall fallback for scope conflicts)

trap 'echo ""; echo "WARNING: Sync interrupted. Re-run /optimus-sync to complete."; exit 130' INT TERM

readonly MARKETPLACE_NAME="${OPTIMUS_MARKETPLACE_NAME:-optimus}"
readonly DROID_TIMEOUT="${OPTIMUS_DROID_TIMEOUT:-60}"

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
  echo "ERROR: droid CLI is required but not installed."
  echo "  Install from: https://docs.factory.ai"
  exit 1
fi

if ! command -v jq >/dev/null 2>&1; then
  echo "ERROR: jq is required but not installed."
  exit 1
fi

# Step 1: Update marketplace
echo "Updating marketplace..."
if ! _droid plugin marketplace update "$MARKETPLACE_NAME" 2>/dev/null; then
  echo "WARNING: Could not update marketplace. Proceeding with cached version."
fi

# Step 2: Get expected plugins from marketplace
MARKETPLACE_FILE=$(find ~/.factory -path "*/marketplaces/${MARKETPLACE_NAME}/.factory-plugin/marketplace.json" -type f 2>/dev/null | head -1)
if [ -z "$MARKETPLACE_FILE" ]; then
  echo "ERROR: Marketplace '${MARKETPLACE_NAME}' not found. Register it first:"
  echo "  droid plugin marketplace add https://github.com/alexgarzao/optimus"
  exit 1
fi

EXPECTED=$(jq -r '.plugins[].name' "$MARKETPLACE_FILE" | sort)
if [ -z "$EXPECTED" ]; then
  echo "ERROR: No plugins found in marketplace."
  exit 1
fi

# Step 3: Get installed optimus plugins
INSTALLED=$(_droid plugin list 2>/dev/null \
  | grep -F "@${MARKETPLACE_NAME}" \
  | awk '{print $1}' \
  | sed "s/@${MARKETPLACE_NAME}//" \
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

# Step 5: Remove orphaned plugins
REMOVED=0
FAILED=0
if [ -n "$ORPHANED_PLUGINS" ]; then
  TOTAL=$(_count_lines "$ORPHANED_PLUGINS")
  CURRENT=0
  echo ""
  echo "Removing orphaned plugins..."
  while IFS= read -r plugin; do
    [ -z "$plugin" ] && continue
    CURRENT=$((CURRENT + 1))
    echo "  - ($CURRENT/$TOTAL) $plugin"
    if _droid plugin uninstall "${plugin}@${MARKETPLACE_NAME}" 2>/dev/null; then
      REMOVED=$((REMOVED + 1))
    else
      echo "    WARNING: Failed to remove ${plugin}"
      FAILED=$((FAILED + 1))
    fi
  done <<< "$ORPHANED_PLUGINS"
fi

# Step 6: Install new plugins
ADDED=0
if [ -n "$NEW_PLUGINS" ]; then
  TOTAL=$(_count_lines "$NEW_PLUGINS")
  CURRENT=0
  echo ""
  echo "Installing new plugins..."
  while IFS= read -r plugin; do
    [ -z "$plugin" ] && continue
    CURRENT=$((CURRENT + 1))
    echo "  + ($CURRENT/$TOTAL) $plugin"
    if _droid plugin install "${plugin}@${MARKETPLACE_NAME}" 2>/dev/null; then
      ADDED=$((ADDED + 1))
    else
      echo "    WARNING: Failed to install ${plugin}"
      FAILED=$((FAILED + 1))
    fi
  done <<< "$NEW_PLUGINS"
fi

# Step 7: Update existing plugins
UPDATED=0
if [ -n "$EXISTING_PLUGINS" ]; then
  TOTAL=$(_count_lines "$EXISTING_PLUGINS")
  CURRENT=0
  echo ""
  echo "Updating existing plugins..."
  while IFS= read -r plugin; do
    [ -z "$plugin" ] && continue
    CURRENT=$((CURRENT + 1))
    echo "  * ($CURRENT/$TOTAL) $plugin"
    if _droid plugin update "${plugin}@${MARKETPLACE_NAME}" 2>/dev/null; then
      UPDATED=$((UPDATED + 1))
    else
      # Scope conflict — uninstall and reinstall
      echo "    ! scope conflict, reinstalling..."
      _droid plugin uninstall "${plugin}@${MARKETPLACE_NAME}" 2>/dev/null || true
      if _droid plugin install "${plugin}@${MARKETPLACE_NAME}" 2>/dev/null; then
        UPDATED=$((UPDATED + 1))
      else
        echo "    ERROR: Failed to reinstall ${plugin}"
        FAILED=$((FAILED + 1))
      fi
    fi
  done <<< "$EXISTING_PLUGINS"
fi

# Step 8: Summary
echo ""
echo "=== Sync Complete ==="
echo "  Added:   $ADDED"
echo "  Updated: $UPDATED"
echo "  Removed: $REMOVED"
if [ "$FAILED" -gt 0 ]; then
  echo "  Failed:  $FAILED"
  exit 1
fi
