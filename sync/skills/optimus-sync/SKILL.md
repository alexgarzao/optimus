---
name: optimus-sync
description: "Sync all Optimus plugins — install new, update existing, remove orphaned. Supports Droid (Factory) and Claude Code simultaneously."
trigger: >
  - When user says "sync", "sync plugins", "update plugins", or "optimus sync"
  - When user wants to install/update all Optimus plugins at once
  - After a new Optimus release
skip_when: >
  - User wants to install a single specific plugin (use `droid plugin install` directly)
prerequisite: >
  - At least one supported platform: droid CLI installed OR ~/.claude/skills/ directory exists
  - jq installed and available
  - For Droid: Optimus marketplace registered (`droid plugin marketplace add https://github.com/alexgarzao/optimus`)
  - For Claude Code: git installed (for repo cache clone/update)
NOT_skip_when: >
  - "I'll update plugins manually" -- optimus-sync handles scope conflicts and orphan removal automatically.
  - "Only one plugin needs updating" -- sync is optimized for batch operations and ensures consistency.
examples:
  - name: Sync all plugins
    invocation: "/optimus-sync"
    expected_flow: >
      1. Detect available platforms (Droid, Claude Code, or both)
      2. Update marketplace / repo cache
      3. Calculate changes per platform (new/orphaned/existing)
      4. Execute each operation with progress
      5. Show per-platform summary
related:
  complementary:
    - optimus-help
  sequence:
    after:
      - optimus-help
verification:
  manual:
    - At least one platform detected
    - New plugins installed successfully
    - Orphaned plugins removed
    - Existing plugins updated (or skipped if unchanged on Claude Code)
    - Per-platform summary shows correct counts
---

# Optimus Sync

Syncs installed Optimus plugins with the marketplace. Installs new plugins, removes
orphaned ones, and updates all existing plugins — with real-time progress.

Supports **dual-platform sync**: Droid (Factory) and Claude Code. Detects which
platforms are available and syncs both in a single run.

---

## Phase 1: Prerequisites

Check that at least one supported platform is available.

### Step 1.1: Detect platforms

```bash
HAS_DROID=false; HAS_CLAUDE_CODE=false
command -v droid >/dev/null 2>&1 && HAS_DROID=true
[ -d "$HOME/.claude/skills" ] && HAS_CLAUDE_CODE=true
echo "Droid: $HAS_DROID | Claude Code: $HAS_CLAUDE_CODE"
```

If both are `false`, **STOP**: "No supported platform found. Install Droid from https://docs.factory.ai or create ~/.claude/skills/ for Claude Code support."

### Step 1.2: Check jq

```bash
command -v jq >/dev/null 2>&1
```

If `jq` is not found, **STOP**: "jq is required but not installed."

---

## Phase 2: Update Sources

### Step 2.1: Droid marketplace (if available)

```bash
droid plugin marketplace update optimus 2>&1 || echo "WARNING: Could not update marketplace. Proceeding with cached version."
```

### Step 2.2: Claude Code repo cache (if available)

The repo cache lives at `~/.optimus/repo/` (configurable via `OPTIMUS_CACHE_DIR`).

- If cache exists: `git -C ~/.optimus/repo fetch --depth 1 origin main && git -C ~/.optimus/repo reset --hard origin/main`
- If no cache: `git clone --depth 1 https://github.com/alexgarzao/optimus ~/.optimus/repo`
- If clone/fetch fails: warn and skip Claude Code sync

Show the result to the user before proceeding.

---

## Phase 3: Calculate Changes

### Step 3.1: Find marketplace file

The script resolves the marketplace JSON from multiple sources (in priority order):
1. Droid marketplace cache (`~/.factory/marketplaces/optimus/`)
2. Optimus repo cache (`~/.optimus/repo/.factory-plugin/marketplace.json`)
3. Running from inside the optimus repo (relative path)

### Step 3.2: Get expected plugins

```bash
jq -r '.plugins[].name' "$MARKETPLACE_FILE" | sort
```

Store the output as `EXPECTED` (one plugin name per line, shared across platforms).

If `EXPECTED` is empty, **STOP**: "No plugins found in marketplace."

### Step 3.3: Get installed state per platform

**Droid:**
```bash
droid plugin list 2>/dev/null | grep -F "@optimus" | awk '{print $1}' | sed 's/@optimus$//' | sort
```

**Claude Code:**
```bash
find ~/.claude/skills/default -maxdepth 1 -type d -name 'optimus-*' -exec basename {} \; | sed 's/^optimus-//' | sort
```

### Step 3.4: Calculate diffs per platform

Compare `EXPECTED` vs each platform's `INSTALLED` to determine three lists per platform:

- **NEW_PLUGINS**: in EXPECTED but not in INSTALLED (to install)
- **ORPHANED_PLUGINS**: in INSTALLED but not in EXPECTED (to remove)
- **EXISTING_PLUGINS**: in both (to update)

---

## Phase 4: Execute

Run the sync shell script. The script detects platforms, syncs both, and prints
a per-platform summary.

Resolve script path (prefer local repo, fall back to cache):

```bash
SCRIPT="${OPTIMUS_CACHE_DIR:-$HOME/.optimus/repo}/sync/scripts/sync-user-plugins.sh"
[ -f sync/scripts/sync-user-plugins.sh ] && SCRIPT="sync/scripts/sync-user-plugins.sh"
bash "$SCRIPT" 2>&1
```

Use a 90-second timeout for the entire Execute call.

---

## Phase 5: Summary

Present the final summary using `<json-render>` with **per-platform** metrics:

```
=== Sync Complete ===

Droid — Added: N | Updated: N | Removed: N | Failed: N
Claude Code — Added: N | Updated: N | Removed: N | Failed: N | Unchanged: N
```

Only show platforms that were detected and synced.

---

## Rules

- All Droid plugin operations run in **parallel** via a single Execute call — no separate
  calls per plugin. This makes sync complete in ~6-8 seconds instead of ~2 minutes.
- Claude Code operations are sequential (filesystem copies are fast enough).
- If a plugin operation fails, the script logs it and continues. Do NOT stop
  the entire sync on a single failure.
- If the user cancels mid-sync or the session is interrupted, inform them:
  "Sync interrupted. Some plugins may be partially updated. Re-run `/optimus-sync` to complete."
- The `make sync-plugins` target in the project Makefile runs `sync/scripts/sync-user-plugins.sh`
  directly. Both the agent skill and CLI use the same parallel script.
- Claude Code sync **only** touches `optimus-*` directories under `~/.claude/skills/default/`.
  It never modifies other skill directories (e.g., `ring:*`, user-created skills).
- Command aliases (`/sp`, `/bd`, etc.) are **not supported** on Claude Code — only
  `/optimus-<name>` invocations work. This is a platform limitation.
