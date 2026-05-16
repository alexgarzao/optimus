# Phase 6: Cancel Task

Loaded when user wants to abandon a task. Sets status=Cancelado in state.json, optionally cleans up worktree/branch/PR. Reversible via Reopen.

### Step 6.0: Identify Task

1. Parse the task ID from the user's request
2. Find the task row in the table
3. If task not found → **STOP**: "Task T-XXX not found in optimus-tasks.md"

### Step 6.1: Validate Cancellation

1. **If status is `DONE`** → **STOP**: "Task T-XXX is already done. Cannot cancel a completed task."
2. **If status is `Cancelado`** → **STOP**: "Task T-XXX is already cancelled."
2.1. **Mid-pipeline warning:** If status is `Validando Spec`, `Em Andamento`, or `Validando Impl`, warn via `AskUser`:
   ```
   Task T-XXX is currently in stage '<status>'. Cancelling mid-pipeline may leave
   uncommitted work in the worktree. Check for local changes before proceeding.
   ```
   Options:
   - **Continue** — I've checked, proceed with cancellation
   - **Cancel** — let me check first
3. **Check for dependents:** Scan the Depends column of ALL tasks for references to T-XXX.
   If any non-cancelled task depends on T-XXX, warn via `AskUser`:
   ```
   Task T-XXX has dependents that are not cancelled:
   - T-YYY: <title> (Status: <status>)
   - T-ZZZ: <title> (Status: <status>)

   Cancelling T-XXX will block these tasks (Cancelado does NOT satisfy dependencies).
   Cancel anyway?
   ```
   **BLOCKING:** Do NOT proceed without user confirmation.
4. **If task has a worktree**, check and offer to remove it:

   **IMPORTANT:** Worktree must be removed BEFORE attempting branch deletion (step 5b).
   Git refuses to delete a branch that is checked out in a worktree.

   Resolve the worktree by branch (source-of-truth from state.json) with a
   kebab-anchored fallback. Never `grep -iF "T-XXX"` directly — that would
   match `T-1` against `T-10`/`T-100`:

   ```bash
   # Source-of-truth: branch from state.json.
   TASK_BRANCH=$(jq -r --arg id "$TASK_ID" '.[$id].branch // ""' \
     "${MAIN_WORKTREE}/.optimus/state.json" 2>/dev/null)
   WORKTREE_PATH=""
   if [ -n "$TASK_BRANCH" ]; then
     WORKTREE_PATH=$(git worktree list --porcelain 2>/dev/null | awk -v br="refs/heads/$TASK_BRANCH" '
       /^worktree / { path=$2 }
       /^branch /   { if ($2 == br) { print path; exit } }
     ')
   fi
   if [ -z "$WORKTREE_PATH" ]; then
     TASK_KEBAB="-$(echo "$TASK_ID" | tr '[:upper:]' '[:lower:]')-"
     WORKTREE_PATH=$(git worktree list --porcelain 2>/dev/null \
       | awk -v anchor="$TASK_KEBAB" '/^worktree / { path=$2; if (index(tolower(path), anchor) > 0) { print path; exit } }')
   fi
   ```

   If a worktree is found (`WORKTREE_PATH` non-empty), ask via `AskUser`:
   ```
   Task T-XXX has a worktree at '<path>'. What should I do with it?
   ```
   Options:
   - **Remove worktree** — `git worktree remove <path>`
   - **Keep** — leave the worktree as is

   **Edge case — running INSIDE the worktree:** If the agent's current working directory
   IS the worktree being removed, `git worktree remove` will fail. Before removing:
   1. Identify the main repository path from `git worktree list` (the first entry)
   2. Change working directory to the main repository: `cd <main-repo-path>`
   3. Then run `git worktree remove <worktree-path>`

5. **If task has a branch** (read `branch` field from state.json or search `git branch --list "*t-xxx*"`):
   a. **Check for open PR:**
      ```bash
      gh pr list --head "<branch>" --json number,state,url --jq '.[] | select(.state == "OPEN")'
      ```
      If an open PR exists, ask via `AskUser`:
      ```
      Task T-XXX has an open PR (#N). What should I do with it?
      ```
      Options:
      - **Close PR without merging** — `gh pr close <number>`
      - **Keep PR open** — leave it for manual handling
   b. **Ask about branch cleanup** via `AskUser`:
      ```
      Task T-XXX has branch '<branch>'. What should I do with it?
      ```
      Options:
      - **Delete local and remote** — clean up the branch
      - **Keep** — leave the branch as is
      **NOTE:** If an open PR was kept in step (a), skip branch deletion — deleting the branch would orphan the PR.

### Step 6.2: Apply Cancellation

1. Update the status to `Cancelado` in state.json — see AGENTS.md Protocol: State Management.
2. If the underlying branch was deleted in Step 6.1, set the state.json entry's `branch`
   field to empty string `""` via the State Management writer (the standard writer
   template already produces `{status: "Cancelado", branch: "", updated_at: ...}`).
   Do NOT remove the `branch` field — see AGENTS.md "Cancelado state.json shape contract".
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
     "$HOOKS_FILE" task-cancelled "$(_optimus_sanitize "T-XXX")" "$(_optimus_sanitize "<old status>")" "$(_optimus_sanitize "Cancelado")" 2>/dev/null &
   fi
   ```
4. **Fire `task-blocked` hook for affected dependents:** For each non-cancelled task that
   depends on T-XXX (identified in Step 6.1, item 3), fire the `task-blocked` hook:
   ```bash
   if [ -n "$HOOKS_FILE" ] && [ -x "$HOOKS_FILE" ]; then
     "$HOOKS_FILE" task-blocked "$(_optimus_sanitize "T-YYY")" "$(_optimus_sanitize "<dep-status>")" "$(_optimus_sanitize "blocked by T-XXX (Cancelado)")" 2>/dev/null &
   fi
   ```
5. **Re-validate after mutation** — see AGENTS.md Protocol: optimus-tasks.md Validation.
   Cancellation only writes to state.json (gitignored), but invariants can drift if a
   prior structural edit was deferred. If validation fails, surface the violation and
   refuse the cancel until it is fixed; do not stage/commit any pending edit.

### Step 6.3: Confirm

```
Cancelled task T-XXX: <title>
  Previous status: <old status>
  Branch: <deleted / kept / none>
```

**Proactive dependent notification:** If any non-cancelled tasks depend on T-XXX
(identified in Step 6.1, item 3), display them with resolution guidance:

```markdown
### Affected Dependents (now blocked)

The following tasks depend on T-XXX and are now blocked:

| ID | Title | Status | Resolution Options |
|----|-------|--------|--------------------|
| T-YYY | <title> | <status> | Remove dependency / Replace / Cancel |

To resolve, run `/optimus-tasks`:
  - "edit T-YYY, remove T-XXX from dependencies"
  - "edit T-YYY, replace T-XXX with T-ZZZ in dependencies"
  - "cancel T-YYY"
```

