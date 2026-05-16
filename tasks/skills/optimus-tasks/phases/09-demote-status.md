# Phase 9: Demote Status

Loaded when user wants to manually move a task backward one stage (rework needed after review).

Move a task back to a previous status (e.g., when stage-3 review identifies
that significant rework is needed and the task should go back to implementation).

### Step 9.0: Identify Task and Target Status

1. Parse the task ID from the user's request
2. Find the task row in the table
3. If task not found → **STOP**: "Task T-XXX not found in optimus-tasks.md"
4. Determine the target status. If the user specified one, use it. Otherwise, demote
   to the previous status in the lifecycle:

   | Current Status | Previous Status |
   |---------------|----------------|
   | `Validando Spec` | `Pendente` |
   | `Em Andamento` | `Validando Spec` |
   | `Validando Impl` | `Em Andamento` |
   | `Pendente` | (already at start) |
   | `DONE` | (use Reopen instead) |
   | `Cancelado` | (terminal, cannot demote) |

### Step 9.1: Validate Demotion

1. **If status is `Pendente`** → **STOP**: "Task T-XXX is already at the initial status."
2. **If status is `DONE` or `Cancelado`** → **STOP**: "Task T-XXX is in terminal status '<status>'. Use 'reopen' for DONE tasks."
3. Require justification via `AskUser`:
   ```
   You are demoting task T-XXX status backward.

   **T-XXX: [title]**
   Current: <current status> → New: <target status>

   Why is this task being sent back? (This is logged for audit trail)
   ```
   Options:
   - **Rework needed** — implementation needs significant changes
   - **Spec incomplete** — spec needs more detail before continuing
   - **Wrong approach** — need to restart with a different strategy
   - **Cancel** — keep current status

   **BLOCKING:** Do NOT proceed without confirmation and justification.

### Step 9.2: Apply Demotion

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
   Demotion only writes to state.json (gitignored), but invariants can drift if a
   prior structural edit was deferred. If validation fails, surface the violation and
   refuse the demote until it is fixed; do not stage/commit any pending edit.

