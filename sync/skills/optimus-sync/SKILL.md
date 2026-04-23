---
name: optimus-sync
description: "Sync all Optimus plugins — install new, update existing, remove orphaned. Recommended after new releases."
trigger: >
  - When user says "sync", "sync plugins", "update plugins", or "optimus sync"
  - When user wants to install/update all Optimus plugins at once
  - After a new Optimus release
skip_when: >
  - User wants to install a single specific plugin (use `droid plugin install` directly)
prerequisite: >
  - droid CLI installed and available
  - jq installed and available
  - Optimus marketplace registered (`droid plugin marketplace add https://github.com/alexgarzao/optimus`)
NOT_skip_when: >
  - "I'll update plugins manually" -- optimus-sync handles scope conflicts and orphan removal automatically.
  - "Only one plugin needs updating" -- sync is optimized for batch operations and ensures consistency.
examples:
  - name: Sync all plugins
    invocation: "/optimus-sync"
    expected_flow: >
      1. Update marketplace
      2. Calculate changes (new/orphaned/existing)
      3. Show plan and ask for confirmation
      4. Execute each operation with progress
      5. Show summary
related:
  complementary:
    - optimus-help
  sequence:
    after:
      - optimus-help
verification:
  manual:
    - Marketplace update completed
    - New plugins installed successfully
    - Orphaned plugins removed
    - Existing plugins updated
    - Summary shows correct counts
---

# Optimus Sync

Syncs installed Optimus plugins with the marketplace. Installs new plugins, removes
orphaned ones, and updates all existing plugins — with real-time progress.

---

## Phase 1: Prerequisites

Check that required tools are available.

### Step 1.1: Check droid CLI

```bash
command -v droid >/dev/null 2>&1
```

If `droid` is not found, **STOP**: "droid CLI is required but not installed. Install from: https://docs.factory.ai"

### Step 1.2: Check jq

```bash
command -v jq >/dev/null 2>&1
```

If `jq` is not found, **STOP**: "jq is required but not installed."

---

## Phase 2: Update Marketplace

Run:

```bash
droid plugin marketplace update optimus 2>&1 || echo "WARNING: Could not update marketplace. Proceeding with cached version."
```

Show the result to the user before proceeding.

---

## Phase 3: Calculate Changes

### Step 3.1: Find marketplace file

```bash
MARKETPLACE_FILE=$(find ~/.factory -path "*/marketplaces/optimus/.factory-plugin/marketplace.json" -type f 2>/dev/null | head -1)
echo "$MARKETPLACE_FILE"
```

If empty, **STOP**: "Marketplace 'optimus' not found. Register it first: `droid plugin marketplace add https://github.com/alexgarzao/optimus`"

Validate the marketplace JSON is parseable:

```bash
jq empty "$MARKETPLACE_FILE" 2>/dev/null
```

If this fails, **STOP**: "Marketplace JSON is malformed. Re-run `droid plugin marketplace update optimus` to fix."

### Step 3.2: Get expected plugins

```bash
jq -r '.plugins[].name' "$MARKETPLACE_FILE" | sort
```

Store the output as `EXPECTED` (one plugin name per line).

If `EXPECTED` is empty, **STOP**: "No plugins found in marketplace. The marketplace may be empty or corrupted."

### Step 3.3: Get installed plugins

```bash
droid plugin list 2>/dev/null | grep -F "@optimus" | awk '{print $1}' | sed 's/@optimus$//' | sort
```

Store the output as `INSTALLED` (one plugin name per line). May be empty (first-time install).

### Step 3.4: Calculate diffs

Compare `EXPECTED` vs `INSTALLED` to determine three lists:

- **NEW_PLUGINS**: in EXPECTED but not in INSTALLED (to install)
- **ORPHANED_PLUGINS**: in INSTALLED but not in EXPECTED (to remove)
- **EXISTING_PLUGINS**: in both (to update)

---

## Phase 4: Show Plan

Present the plan to the user before executing. Show:

1. Total counts: `Expected: N | Installed: N | New: N | Orphaned: N | Update: N`
2. If there are new plugins, list them with `+` prefix
3. If there are orphaned plugins, list them with `-` prefix
4. If there are existing plugins, list them with `*` prefix

Use `<json-render>` with a Table component for clear display.

Then ask the user via `AskUser`:

```
Ready to sync N plugins (X new, Y remove, Z update). Proceed?
```

Options:
- **Proceed** — execute all operations
- **Cancel** — abort sync

If **Cancel**, **STOP**.

---

## Phase 5: Execute

Run all operations in a **single Execute call** using the sync shell script. The script
runs all plugin operations in parallel (remove, install, update simultaneously) and
prints a summary with per-plugin results.

```bash
bash sync/scripts/sync-user-plugins.sh 2>&1
```

If not running inside the Optimus repo (script not available), construct an equivalent
single command that runs all `droid plugin update` calls in parallel:

```bash
RESULTS_DIR=$(mktemp -d)
for plugin in <space-separated list of all plugins>; do
  (
    if droid plugin update "${plugin}@optimus" >/dev/null 2>&1; then
      echo "OK" > "$RESULTS_DIR/$plugin"
    else
      droid plugin uninstall "${plugin}@optimus" >/dev/null 2>&1 || true
      if droid plugin install "${plugin}@optimus" >/dev/null 2>&1; then
        echo "REINSTALLED" > "$RESULTS_DIR/$plugin"
      else
        echo "FAIL" > "$RESULTS_DIR/$plugin"
      fi
    fi
  ) &
done
wait
for plugin in <space-separated list>; do
  result=$(cat "$RESULTS_DIR/$plugin" 2>/dev/null || echo "FAIL")
  echo "  * $plugin ... $result"
done
rm -rf "$RESULTS_DIR"
```

Use a 90-second timeout for the entire Execute call (all plugins run in parallel,
so total time is ~6-8 seconds for 16 plugins).

---

## Phase 6: Summary

Present the final summary using `<json-render>` with metrics:

- Added: N
- Updated: N
- Removed: N
- Failed: N (only show if > 0)

---

## Rules

- All plugin operations run in **parallel** via a single Execute call — no separate
  calls per plugin. This makes sync complete in ~6-8 seconds instead of ~2 minutes.
- If a plugin operation fails, the script logs it and continues. Do NOT stop
  the entire sync on a single failure.
- If the user cancels mid-sync or the session is interrupted, inform them:
  "Sync interrupted. Some plugins may be partially updated. Re-run `/optimus-sync` to complete."
- The `make sync-plugins` target in the project Makefile runs `sync/scripts/sync-user-plugins.sh`
  directly. Both the agent skill and CLI use the same parallel script.
