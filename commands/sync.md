---
description: Sync all Optimus plugins — install new, update existing, remove orphaned. Supports Droid (Factory) and Claude Code simultaneously.
---

# Optimus Sync

Syncs installed Optimus plugins with the marketplace. Installs new plugins, removes
orphaned ones, and updates all existing plugins — with real-time progress.

Supports **dual-platform sync**: Droid (Factory) and Claude Code. Detects which
platforms are available and syncs both in a single run.

The two platforms package the same SKILLs differently:

- **Droid:** 17 individual plugins (`plan@optimus`, `build@optimus`, ...).
  Each is installed/updated/removed separately. Invoked as `/<plugin>` or
  `/<alias>` (Droid does not support a `/<plugin>:<command>` namespace).
- **Claude Code:** ONE plugin (`optimus@optimus`) sourced from the repo
  root. The 17 commands surface as `/optimus:<command>` from the top-level
  `commands/` directory inside the plugin. Aliases like `/optimus:sp` and
  `/optimus:bd` are namespaced too — there is no longer a per-skill
  `/optimus-<name>:<alias>` form.

The sync script normalizes these conventions: the Droid branch installs the
17 bare-name plugins; the Claude branch installs a single `optimus@optimus`
and silently uninstalls any legacy `optimus-<name>@optimus` entries left
over from the pre-2.0 layout.

---

## Phase 1: Prerequisites

Check that at least one supported platform is available.

### Step 1.1: Detect platforms

```bash
HAS_DROID=false; HAS_CLAUDE_CODE=false
command -v droid >/dev/null 2>&1 && HAS_DROID=true
command -v claude >/dev/null 2>&1 && HAS_CLAUDE_CODE=true
echo "Droid: $HAS_DROID | Claude Code: $HAS_CLAUDE_CODE"
```

If both are `false`, **STOP**: "No supported platform found. Install Droid from https://docs.factory.ai or install Claude Code from https://docs.anthropic.com/claude-code."

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

### Step 2.2: Claude Code marketplace (if available)

```bash
claude plugin marketplace update optimus 2>&1 || echo "WARNING: Could not update Claude Code marketplace. Proceeding with cached version."
```

If the marketplace is not registered, the user must register it once with:
`claude plugin marketplace add https://github.com/alexgarzao/optimus`

---

## Phase 3: Calculate Changes

### Step 3.1: Find marketplace file

The script resolves the marketplace JSON from multiple sources (in priority order):
1. Droid marketplace cache (`~/.factory/marketplaces/optimus/`)
2. Claude Code marketplace cache (`~/.claude/plugins/marketplaces/optimus/.claude-plugin/marketplace.json`)
3. Running from inside the optimus repo (`.factory-plugin/marketplace.json` or `.claude-plugin/marketplace.json`)

Plugin names returned by the resolver are always in BARE form (e.g. `plan`,
`build`, `sync`). When the source is a Claude Code marketplace (which uses
`optimus-<name>`), the resolver strips the `optimus-` prefix.

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
claude plugin list --json 2>/dev/null \
  | jq -r '.[] | select(.id | endswith("@optimus")) | .id' \
  | sort
```

The Claude branch reads the full ids (no `optimus-` prefix stripping) so it can
distinguish `optimus@optimus` (the single new plugin) from any legacy
`optimus-<name>@optimus` entries left behind by pre-2.0 installations.

### Step 3.4: Calculate diffs per platform

**Droid:** Compare `EXPECTED` (the bare names from the marketplace) against
the installed bare names to derive three lists:

- **NEW_PLUGINS**: in EXPECTED but not in INSTALLED (to install)
- **ORPHANED_PLUGINS**: in INSTALLED but not in EXPECTED (to remove)
- **EXISTING_PLUGINS**: in both (to update)

**Claude Code:** No diff over EXPECTED is needed — the marketplace defines a
single `optimus` plugin. The branch installs `optimus@optimus` if missing
(or updates it if present) and uninstalls every other `*@optimus` plugin it
finds (legacy per-skill installs from the pre-2.0 layout).

---

## Phase 4: Execute

Run the sync shell script. The script detects platforms, syncs both, and prints
a per-platform summary.

Resolve script path with this fallback order:
1. Inside the optimus repo (developer running locally)
2. Legacy `~/.optimus/repo/` clone (PR #9 era — backwards compat for Droid users)
3. Claude Code plugin install path — discovered dynamically via `claude plugin list --json`
   so we never hardcode the version. Falls back to a versioned path if the dynamic
   lookup fails (e.g. `claude` not on PATH).

```bash
SCRIPT=""

# 1. Local repo
if [ -f sync/scripts/sync-user-plugins.sh ]; then
  SCRIPT="sync/scripts/sync-user-plugins.sh"
fi

# 2. Legacy ~/.optimus/repo clone
if [ -z "$SCRIPT" ]; then
  CANDIDATE="${OPTIMUS_CACHE_DIR:-$HOME/.optimus/repo}/sync/scripts/sync-user-plugins.sh"
  [ -f "$CANDIDATE" ] && SCRIPT="$CANDIDATE"
fi

# 3. Claude Code plugin install path (version-agnostic via JSON lookup)
# The single `optimus@optimus` plugin is sourced from the repo root, so the
# sync script lives at `<install>/sync/scripts/sync-user-plugins.sh`.
if [ -z "$SCRIPT" ] && command -v claude >/dev/null 2>&1; then
  INSTALL_PATH=$(claude plugin list --json 2>/dev/null \
    | jq -r '.[] | select(.id == "optimus@optimus") | .installPath' \
    | head -1)
  if [ -n "$INSTALL_PATH" ] && [ -f "$INSTALL_PATH/sync/scripts/sync-user-plugins.sh" ]; then
    SCRIPT="$INSTALL_PATH/sync/scripts/sync-user-plugins.sh"
  fi
fi

# 3b. Versioned-path fallback if `claude plugin list --json` failed.
# NOTE: 2.0.0 is the version pinned in .claude-plugin/marketplace.json. If that
# version changes, update this fallback too — but the dynamic lookup above is
# the preferred resolver and should normally make this unnecessary.
if [ -z "$SCRIPT" ]; then
  CANDIDATE="$HOME/.claude/plugins/cache/optimus/optimus/2.0.0/sync/scripts/sync-user-plugins.sh"
  [ -f "$CANDIDATE" ] && SCRIPT="$CANDIDATE"
fi

if [ -z "$SCRIPT" ]; then
  echo "ERROR: Could not locate sync-user-plugins.sh" >&2
  exit 1
fi

bash "$SCRIPT" 2>&1
```

Use a 90-second timeout for the entire Execute call.

---

## Phase 5: Summary

Present the final summary using `<json-render>` with **per-platform** metrics:

```
=== Sync Complete ===

Droid — Added: N | Updated: N | Removed: N | Failed: N
Claude Code — Added: N | Updated: N | Removed: N | Failed: N
```

Only show platforms that were detected and synced.

---

## Rules

- All Droid plugin operations run in **parallel** via a single Execute call — no separate
  calls per plugin. This makes sync complete in ~6-8 seconds instead of ~2 minutes.
- Claude Code operations are sequential (one `claude plugin install/update/uninstall`
  call per plugin). Claude Code's plugin daemon owns the cache, so parallelizing
  is unnecessary and risks contention on shared state.
- If a plugin operation fails, the script logs it and continues. Do NOT stop
  the entire sync on a single failure.
- If the user cancels mid-sync or the session is interrupted, inform them:
  "Sync interrupted. Some plugins may be partially updated. Re-run `/optimus:sync` to complete."
- The `make sync-plugins` target in the project Makefile runs `sync/scripts/sync-user-plugins.sh`
  directly. Both the agent skill and CLI use the same script.
- Claude Code sync **only** touches `*@optimus` plugins via the native plugin
  system: it installs/updates the single `optimus@optimus` plugin and prunes any
  legacy `optimus-<name>@optimus` entries. Other marketplaces and user-created
  skills are untouched.
- Command aliases on Claude Code are namespaced (`/optimus:sp`, `/optimus:bd`,
  ...) since the plugin owns the `optimus:` namespace. On Droid the bare
  invocations (`/sp`, `/bd`) work directly — Droid does not support the
  `<plugin>:<command>` namespace syntax.
