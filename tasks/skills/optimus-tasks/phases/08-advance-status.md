# Phase 8: Advance Status

Loaded when user wants to manually move a task forward one stage (work was done outside the pipeline). Writes to state.json.

Manually advance a task's status to skip a stage (e.g., when the user implemented
code manually without using stage-2).

### Step 8.0: Identify Task and Target Status

1. Parse the task ID from the user's request
2. Find the task row in the table
3. If task not found → **STOP**: "Task T-XXX not found in optimus-tasks.md"
4. Determine the target status. If the user specified one, use it. Otherwise, advance
   to the next status in the lifecycle:

   | Current Status | Next Status |
   |---------------|-------------|
   | `Pendente` | `Validando Spec` |
   | `Validando Spec` | `Em Andamento` |
   | `Em Andamento` | `Validando Impl` |
   | `Validando Impl` | (use done to mark DONE) |
   | `DONE` | (use Reopen instead) |
   | `Cancelado` | (use Reopen or create new task) |

### Step 8.1: Validate Advance

1. **Target status validation (check first):**
   - If target status is `DONE` → **STOP**: "Cannot advance to DONE manually. Use `/optimus-done` which verifies PR state and runs close gates."
   - If target status is `Cancelado` → **STOP**: "Cannot advance to Cancelado. Use the cancel operation (`cancel T-XXX`) which handles cleanup."
2. **Current status validation:**
   - If status is `DONE` or `Cancelado` → **STOP**: "Task T-XXX is in terminal status '<status>'. Use 'reopen' for DONE tasks."
3. **Check dependencies (HARD BLOCK):** same rules as stage agents — all dependencies must be `DONE`.
4. **Workspace check (warning):** If the target status is `Validando Spec` or later, verify
   that a workspace exists for this task (stage-1 normally creates the workspace when
   setting `Validando Spec` — advancing manually bypasses this):
   - Read the `branch` field from state.json for the task (or search by task ID pattern)
   - If no branch found → warn via `AskUser`:
     ```
     Task T-XXX has no workspace (branch). Advancing to '<target status>' without a
     workspace means execution stages (2-5) will fail when they verify the workspace.

     Options:
     - Advance anyway (I'll create the workspace manually)
     - Cancel (run /optimus-plan first to create the workspace)
     ```
5. Warn via `AskUser`:
   ```
   You are manually advancing task T-XXX status.

   **T-XXX: [title]**
   Current: <current status> → New: <target status>

   WARNING: This skips the validation that the corresponding stage agent provides.
   Only do this if you've already performed the work outside the pipeline
   (e.g., manual implementation, external review).

   Confirm?
   ```
   **BLOCKING:** Do NOT proceed without confirmation.

### Step 8.2: Apply Advance

1. Update the status in state.json to the target status — see AGENTS.md Protocol: State Management.
2. **Invoke notification hooks (if present)** — see AGENTS.md Protocol: Notification Hooks:
   ```bash
   if [ -f ./tasks-hooks.sh ]; then
     HOOKS_FILE="./tasks-hooks.sh"
   elif [ -f ./docs/tasks-hooks.sh ]; then
     HOOKS_FILE="./docs/tasks-hooks.sh"
   else
     HOOKS_FILE=""
   fi
   if [ -n "$HOOKS_FILE" ] && [ -x "$HOOKS_FILE" ]; then
     "$HOOKS_FILE" status-change "$(_optimus_sanitize "T-XXX")" "$(_optimus_sanitize "<old status>")" "$(_optimus_sanitize "<target status>")" 2>/dev/null &
   fi
   ```
3. **Re-validate after mutation** — see AGENTS.md Protocol: optimus-tasks.md Validation.
   Advance only writes to state.json (gitignored), but invariants can drift if a
   prior structural edit was deferred. If validation fails, surface the violation and
   refuse the advance until it is fixed; do not stage/commit any pending edit.

