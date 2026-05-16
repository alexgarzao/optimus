# Phase 1: Prerequisites

Loaded by `SKILL.md` first. Sanity checks before doing any work: jq availability, optimus-tasks.md validation, jq integrity guard on state.json, MAIN_WORKTREE resolution.

### Step 1.1: Check jq (HARD BLOCK)

```bash
command -v jq >/dev/null 2>&1
```

If `jq` is not available, **STOP**: "jq is required by /optimus-resume. Install it and retry."

### Step 1.2: Resolve and Validate optimus-tasks.md (HARD BLOCK)

Find and validate optimus-tasks.md — see AGENTS.md Protocol: optimus-tasks.md Validation.

### Step 1.3: Reject Empty Tasks Table (HARD BLOCK)

AGENTS.md Format Validation item 15 requires checking for zero-data-row tables. A valid
but empty `optimus-tasks.md` would otherwise surface as a misleading "No in-progress tasks found"
message in Step 2.2.

```bash
# Step 1.2 resolved TASKS_FILE via Protocol: optimus-tasks.md Validation (which calls
# Protocol: Resolve Tasks Git Scope). If TASKS_FILE is unset here, that means
# Step 1.2 did NOT execute — surface the control-flow bug immediately instead
# of masking it with a silent fallback (which would produce misleading
# "docs/pre-dev/optimus-tasks.md not found" errors for users who customized tasksDir).
if [ -z "${TASKS_FILE:-}" ]; then
  echo "ERROR: TASKS_FILE is unset — Step 1.2 (optimus-tasks.md Validation) did not execute." >&2
  echo "Protocol: Resolve Tasks Git Scope must run before Step 1.3." >&2
  exit 1
fi
if [ ! -f "$TASKS_FILE" ]; then
  echo "ERROR: $TASKS_FILE not found. Run /optimus-import to create it."
  # STOP
fi
TASK_ROWS=$(grep -cE '^\| T-[0-9]+ \|' "$TASKS_FILE" || echo 0)
if ! [[ "$TASK_ROWS" =~ ^[0-9]+$ ]] || [ "$TASK_ROWS" -eq 0 ]; then
  echo "ERROR: No tasks found in $TASKS_FILE. Use /optimus-tasks to create a task or /optimus-import to import from Ring pre-dev."
  # STOP
fi
```

### Step 1.4: Validate state.json Integrity (HARD BLOCK) — Single Authoritative Check

All subsequent steps reference `$STATE_JSON` (cached) instead of re-reading or
re-validating `$STATE_FILE`. This is the ONLY place where resume does integrity checks
on state.json — downstream steps trust this.

```bash
# Resolve main worktree so .optimus/* paths are not isolated to a linked worktree.
# All .optimus/* state lives in the main worktree; linked worktrees do not propagate it.
MAIN_WORKTREE="$(git worktree list --porcelain 2>/dev/null | awk '/^worktree / {print $2; exit}')"
if [ -z "$MAIN_WORKTREE" ]; then
  echo "ERROR: Cannot determine main worktree — not in a git repository." >&2
  exit 1
fi

STATE_FILE="${MAIN_WORKTREE}/.optimus/state.json"
STATE_JSON=""
if [ -f "$STATE_FILE" ]; then
  if ! jq empty "$STATE_FILE" 2>/dev/null; then
    echo "ERROR: state.json is corrupted and cannot be parsed."
    echo "Resume is read-only and will NOT apply the destructive 'rm -f' recovery described in the inlined Protocol: State Management."
    echo "Run /optimus-tasks to rebuild the operational state, or restore state.json from backup."
    # STOP
  fi
  STATE_JSON=$(cat "$STATE_FILE")
fi
# STATE_JSON is now either valid JSON or the empty string (no state.json yet).
```

---
