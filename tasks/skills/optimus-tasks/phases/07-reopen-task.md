# Phase 7: Reopen Task

Loaded when user wants to undo a DONE/Cancelado state. Restores to Pendente (or Em Andamento if worktree exists).

### Step 7.0: Identify Task

1. Parse the task ID from the user's request
2. Find the task row in the table
3. If task not found → **STOP**: "Task T-XXX not found in optimus-tasks.md"

### Step 7.1: Validate Reopen

1. **If status is NOT `DONE` and NOT `Cancelado`** → **STOP**: "Task T-XXX is in status '<status>'. Only completed or cancelled tasks can be reopened."
2. **Determine target status based on current status and workspace availability:**
   - **If reopening from `Cancelado`:** Target status is always `Pendente` (task must restart
     from the beginning via plan).
   - **If reopening from `DONE`:**
     - Read the `branch` field from state.json (or search `git branch --list "*<task-id>*"`)
     - If a branch exists locally:
       - Target status: `Em Andamento` (workspace exists, can resume implementation)
     - If no branch found:
       - Target status: `Pendente` (workspace must be recreated via plan)
3. Warn via `AskUser`:
   ```
   Task T-XXX is marked as DONE. Reopening will set it to '<target status>'.

   **T-XXX: [title]**
   **Version:** [version]
   **Branch:** [branch value or "deleted"]
   **Previous status:** [DONE or Cancelado]
   **Target status:** <target status>
   **Reason:** <see below>

   [If reopening from Cancelado]: Task was cancelled. After reopening, run
   `/optimus-plan` to create a workspace, then proceed through
   the normal pipeline.

   [If reopening from DONE with Pendente target]: The original branch was deleted.
   After reopening, run `/optimus-plan` to create a new workspace,
   then `/optimus-build` to resume implementation.

   [If reopening from DONE with Em Andamento target]: The branch still exists.
   After reopening, switch to it and run `/optimus-build` to resume
   implementation.

   Why are you reopening this task? (This is logged for audit trail)
   ```
   Options:
   - **Bug found** — implementation has a defect
   - **Incomplete** — not all acceptance criteria were actually met
   - **Requirements changed** — spec was updated after close
   - **Decision reversed** — cancellation decision was reconsidered (only for Cancelado)
   - **Cancel** — keep current status

   **BLOCKING:** Do NOT proceed without user confirmation and justification.

### Step 7.2: Apply Reopen

1. Update the status in state.json to the target status determined in Step 7.1:
   - From `DONE`: `Em Andamento` if workspace exists, remove entry (= `Pendente`) if not
   - From `Cancelado`: remove entry from state.json (= `Pendente`, must restart from plan)
   When reopening from `Cancelado` via entry removal, any previous `branch` value is
   discarded with the entry — there is no separate field-removal step.
2. Clean stale session state: `rm -f ".optimus/sessions/session-${TASK_ID}.json"`
3. **Invoke notification hooks (if present)** — see AGENTS.md Protocol: Notification Hooks:
   ```bash
   if [ -f ./tasks-hooks.sh ]; then
     HOOKS_FILE="./tasks-hooks.sh"
   elif [ -f ./docs/tasks-hooks.sh ]; then
     HOOKS_FILE="./docs/tasks-hooks.sh"
   else
     HOOKS_FILE=""
   fi
   if [ -n "$HOOKS_FILE" ] && [ -x "$HOOKS_FILE" ]; then
     "$HOOKS_FILE" status-change "$(_optimus_sanitize "T-XXX")" "$(_optimus_sanitize "DONE")" "$(_optimus_sanitize "<target status>")" 2>/dev/null &
   fi
   ```
4. **Re-validate after mutation** — see AGENTS.md Protocol: optimus-tasks.md Validation.
   Reopen only writes to state.json (gitignored), but invariants can drift if a
   prior structural edit was deferred. If validation fails, surface the violation and
   refuse the reopen until it is fixed; do not stage/commit any pending edit.

### Step 7.3: Confirm

```
Reopened task T-XXX: <title>
  Previous status: [DONE | Cancelado]
  New status: <target status>
  Reason: <user's reason>
  Next step: [run /optimus-plan | switch to branch and run /optimus-build]
```

