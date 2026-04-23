---
name: optimus-tasks
description: "Administrative task management for tasks.md. Create, edit, remove, reorder, and cancel tasks. Manage versions (create, edit, remove, reorder) and move tasks between versions. Validates format, dependencies, and ID uniqueness. Runs on any branch -- this is an administrative skill, not an execution skill."
trigger: >
  - When user wants to add a new task (e.g., "add task", "create task", "new task")
  - When user wants to edit a task (e.g., "change priority of T-003", "rename T-005")
  - When user wants to remove a task (e.g., "remove T-004", "delete task")
  - When user wants to reorder tasks (e.g., "move T-005 before T-003")
  - When user wants to cancel a task (e.g., "cancel T-004", "abandon T-004", "won't do T-004")
  - When user wants to reopen a done task (e.g., "reopen T-004", "undo done T-004")
  - When user wants to advance or demote a task status manually (e.g., "advance T-004", "demote T-004")
  - When user wants to manage versions (e.g., "create version", "add version v2", "edit version MVP")
  - When user wants to move tasks between versions (e.g., "move T-003 to v2")
  - When user says "manage tasks" or "edit tasks.md"
skip_when: >
  - User wants to execute a task (use plan instead)
  - User wants to change task status through the lifecycle (status is managed by stage agents -- except cancellation, which is handled here)
prerequisite: >
  - .optimus/tasks.md exists in the project
NOT_skip_when: >
  - "I can edit tasks.md manually" -- This agent validates format, dependencies, and IDs automatically.
  - "It's just a small change" -- Even small changes can break format or create circular dependencies.
examples:
  - name: Add a new task
    invocation: "Add a task: implement password reset"
    expected_flow: >
      1. Parse tasks.md
      2. Generate next ID (T-NNN)
      3. Ask for details (priority, dependencies)
      4. Add row to table with TaskSpec column
      5. Validate and save
  - name: Edit task priority
    invocation: "Change T-003 priority to Alta"
    expected_flow: >
      1. Parse tasks.md
      2. Find T-003 row
      3. Update Priority column
      4. Save
  - name: Remove a task
    invocation: "Remove T-004"
    expected_flow: >
      1. Parse tasks.md
      2. Check no other tasks depend on T-004
      3. Remove row from table
      4. Save
related:
  complementary:
    - optimus-import
    - optimus-report
verification:
  manual:
    - After any operation, verify tasks.md still has valid format marker
    - Verify no duplicate IDs exist
    - Verify no broken dependency references
---

# optimus-tasks

Administrative CRUD operations for tasks in `tasks.md`.

**Classification:** Administrative skill — runs on any branch, never modifies code.

## Phase 1: Initialize

### Step 1.0: Verify GitHub CLI (conditional)

Operations that interact with GitHub (cancel with PR/branch cleanup, reopen) require `gh`:

```bash
gh auth status 2>/dev/null
```

If this command fails and the requested operation involves PR or branch cleanup (cancel, reopen), **STOP** immediately:
```
GitHub CLI (gh) is not authenticated. Run `gh auth login` to authenticate before proceeding.
```

For operations that do not use `gh` (create, edit, remove, reorder, version management), skip this check.

### Step 1.0.1: Find and Validate tasks.md

1. **Find tasks.md:** Resolve the path using the AGENTS.md Protocol: tasks.md Validation
   (tasks.md is always at `.optimus/tasks.md`).

   If not found, ask the user via `AskUser`:

   "No tasks.md found. What should I do?"
   - **(a) Create at .optimus/tasks.md** (standard location)
   - **(c) Run import** — use this if you already have task files in another format

   If the user chooses to create:
   1. Determine the path (`TASKS_FILE`) — default or custom
   2. Ask for an initial version name via `AskUser` (e.g., "MVP", "v1")
   4. Write `TASKS_FILE` with:
      ```markdown
      <!-- optimus:tasks-v1 -->
      # Tasks

      ## Versions
      | Version | Status | Description |
      |---------|--------|-------------|
      | <user-provided> | Ativa | <ask user for description> |

      | ID | Title | Tipo | Depends | Priority | Version | Estimate | TaskSpec |
      |----|-------|------|---------|----------|---------|----------|----------|
      ```
   5. Initialize .optimus directory — see AGENTS.md Protocol: Initialize .optimus Directory.
   6. Commit: `chore(tasks): initialize tasks.md`

2. **Validate format (HARD BLOCK):** See AGENTS.md Protocol: tasks.md Validation.

### Step 1.1: Determine Operation

Parse the user's request to determine which operation to perform:

| Operation | Triggers |
|-----------|----------|
| **Create** | "add task", "create task", "new task" |
| **Edit** | "edit T-XXX", "change T-XXX", "update T-XXX", "rename T-XXX" |
| **Remove** | "remove T-XXX", "delete T-XXX" |
| **Reorder** | "move T-XXX before/after T-YYY", "reorder tasks" |
| **Cancel** | "cancel T-XXX", "abandon T-XXX", "won't do T-XXX" |
| **Reopen** | "reopen T-XXX", "undo done T-XXX", "unclose T-XXX" |
| **Advance status** | "advance T-XXX", "set T-XXX to Em Andamento", "skip stage for T-XXX" |
| **Demote status** | "demote T-XXX", "move T-XXX back", "reset T-XXX status" |
| **Version** | "create version", "add version", "edit version", "remove version" |
| **Move version** | "move tasks to v2", "move T-XXX to Futuro" |

If unclear, ask the user via `AskUser`:

"What would you like to do?"
- (a) Create a new task
- (b) Edit an existing task
- (c) Remove a task
- (d) Reorder tasks
- (e) Cancel a task (mark as abandoned)
- (f) Reopen a done task (revert to in-progress)
- (g) Advance or demote task status manually
- (h) Manage versions (create, edit, remove)
- (i) Move tasks between versions

## Phase 2: Create Task

### Step 2.0: Gather Task Information

**Option A: From template.** Ask the user if they want to use a template via `AskUser`:

```
Create from a template or from scratch?
```
Options:
- **API Endpoint** — pre-fills Feature tipo
- **Bug Fix** — pre-fills Fix tipo
- **UI Component** — pre-fills Feature tipo
- **Chore/Infra** — pre-fills Chore tipo
- **Refactor** — pre-fills Refactor tipo
- **Documentation** — pre-fills Docs tipo
- **Test** — pre-fills Test tipo
- **From scratch** — manual entry (no template)

#### Built-in Templates

Templates pre-fill Tipo and Priority. The task creation flow delegates to Ring
pre-dev to generate the spec (Step 2.3.1).

**API Endpoint template:** Tipo: `Feature`, Priority: `Alta`
**Bug Fix template:** Tipo: `Fix`, Priority: `Alta`
**UI Component template:** Tipo: `Feature`, Priority: `Media`
**Chore/Infra template:** Tipo: `Chore`, Priority: `Media`
**Refactor template:** Tipo: `Refactor`, Priority: `Media`
**Documentation template:** Tipo: `Docs`, Priority: `Baixa`
**Test template:** Tipo: `Test`, Priority: `Media`

When a template is selected, pre-fill the Tipo and Priority.
The user can then modify any field before confirming.

**Option B: From scratch.** Ask the user for task details using `AskUser` (one question at a time or batch if info provided):

1. **Title** (required): Short description of the task
2. **Tipo** (required): `Feature`, `Fix`, `Refactor`, `Chore`, `Docs`, or `Test`
3. **Priority** (required): `Alta`, `Media`, or `Baixa`
4. **Estimate** (optional): Task size estimate (`S`, `M`, `L`, `XL`, `2h`, `1d`, etc.). Default: `-`
5. **Version** (required): Must match a version in the Versions table. Default: the version with Status `Ativa`
6. **Dependencies** (optional): Comma-separated task IDs (e.g., `T-001, T-003`) or `-` for none
7. **Ring pre-dev reference** (required): Link to Ring pre-dev task spec. If not provided by the user, Ring pre-dev discovery (Step 2.3.1) will search for a match. A task cannot be created without a Ring reference.

If the user provided some of these in the initial request, use them and ask only for missing fields.

### Step 2.1: Check for Similar Tasks (duplicate detection)

Before creating, search existing tasks for potential duplicates:

1. **Compare by title:** For each existing task, check if the new title shares 2+ significant
   keywords with an existing title (ignore articles, prepositions, and generic words like
   "implement", "add", "create", "update", "fix")
2. **Compare by Ring source:** If a Ring pre-dev task was linked, check if any existing task's
   `TaskSpec` column already references the same Ring task spec file

If similar tasks are found, present them to the user via `AskUser`:

```
I found N existing tasks that look similar to your new task:

| ID | Title | Version | Status | Ring Source |
|----|-------|---------|--------|------------|
| T-003 | User login page | MVP | Pendente | task_005.md |
| T-008 | Auth login flow | v2 | Em Andamento | task_005.md |

Your new task: "<new title>"

Create anyway?
```

Options:
- **Create anyway** — the new task is different enough
- **Cancel** — one of the existing tasks already covers this

If no similar tasks are found, proceed silently.

### Step 2.1.1: Validate Title Characters

**HARD BLOCK:** The task title must not contain unescaped pipe characters (`|`) because
tasks.md uses markdown tables where `|` is the column delimiter.

If the title contains `|`:
- Automatically replace `|` with `—` (em dash) or `\|` (escaped pipe)
- Inform the user: "Title contained pipe characters which would break the tasks.md table format. Replaced with '—'."

Also reject titles longer than 120 characters — longer titles break table formatting.
If too long, ask the user to shorten it.

### Step 2.2: Generate Task ID

Collect IDs from ALL sources to avoid collisions with parallel branches:

1. **Local:** Parse all existing task IDs from the current branch's tasks.md table
2. **Remote:** Fetch and parse IDs from the default branch on origin:
   ```bash
   DEFAULT_BRANCH=$(git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's@^refs/remotes/origin/@@')
   if [ -z "$DEFAULT_BRANCH" ]; then
     DEFAULT_BRANCH=$(git branch --list main master 2>/dev/null | head -1 | tr -d ' *')
   fi
   if [ -n "$DEFAULT_BRANCH" ]; then
     git fetch origin "$DEFAULT_BRANCH" --quiet 2>/dev/null
     git show "origin/$DEFAULT_BRANCH:$TASKS_FILE" 2>/dev/null | grep -oE 'T-[0-9]+'
   fi
   ```
   If DEFAULT_BRANCH is empty or fetch fails, warn the user: "Could not determine
   default branch or reach remote — ID may collide with tasks created on other
   branches. Continuing with local IDs only."
3. **Worktrees:** Scan parallel worktrees for IDs:
   ```bash
   git worktree list --porcelain 2>/dev/null | grep "^worktree " | while read _ path; do
     cat "$path/$TASKS_FILE" 2>/dev/null | grep -oE 'T-[0-9]+'
   done
   ```
4. **Next ID:** `max(local, remote, worktrees) + 1`
5. Format as `T-NNN` with zero-padding to 3 digits

### Step 2.3: Validate Dependencies

If the user specified dependencies:
1. **Self-reference check:** If any dependency ID matches the task's own ID → **STOP** immediately: "Task cannot depend on itself."
2. Verify each dependency ID exists in the table
3. Check for circular dependencies: if T-NEW depends on T-X, and T-X (directly or transitively) would depend on T-NEW → reject
4. If any dependency ID is invalid → ask the user to correct it

### Step 2.3.1: Generate Ring Pre-Dev Spec

Delegate to Ring to generate the task spec:

1. Invoke `ring:pre-dev-feature` via `Skill` tool, passing the task title and type
2. Ring generates the spec file in `<TASKS_DIR>/tasks/`
3. After Ring completes, capture the generated spec file path (relative to `TASKS_DIR`)
4. Store as the `TaskSpec` value for this task

**If Ring pre-dev is not available** (skill not installed), ask via `AskUser`:
```
Ring pre-dev skill is not available. How should I proceed?
```
Options:
- **Link existing spec** — search `<TASKS_DIR>/tasks/` for matching specs
- **Create with empty TaskSpec** — set TaskSpec to `-`, link later

**If "Link existing spec"**, search `<TASKS_DIR>/tasks/*.md` for task files, present
matches based on keyword overlap with the task title, and let the user select one.

### Step 2.4: Add to tasks.md

1. Add a new row to the table:
   ```
   | T-NNN | <title> | <tipo> | <depends> | <priority> | <version> | <estimate or -> | <taskspec or -> |
   ```
2. Save the file

### Step 2.5: Confirm

Show the user the added task:
```
Created task T-NNN: <title>
  Tipo: <tipo>
  Priority: <priority>
  Version: <version>
  Depends on: <depends>
  Status: Pendente
```

## Phase 3: Edit Task

### Step 3.0: Identify Task and Field

1. Parse the task ID from the user's request
2. Find the task row in the table
3. If task not found → **STOP**: "Task T-XXX not found in tasks.md"

Determine which field(s) to edit. Editable fields:

| Field | Allowed? | Notes |
|-------|----------|-------|
| Title | Yes | Updates table row |
| Tipo | Yes | Must be `Feature`, `Fix`, `Refactor`, `Chore`, `Docs`, or `Test` |
| Priority | Yes | Must be `Alta`, `Media`, or `Baixa` |
| Version | Yes | Must reference a version in the Versions table |
| Depends | Yes | Must validate references and check circular deps |
| Estimate | Yes | Free text (S, M, L, XL, 2h, 1d) or `-` |
| Status | **No** | Status is managed ONLY by stage agents |
| Branch | **No** | Branch is managed ONLY by stage-1 and close |
| ID | **No** | IDs are immutable |
| Ring reference | **No** | Managed by import and task creation only |

**HARD BLOCK:** If the user tries to change Status or Branch, refuse:
```
Status is managed by the cycle stage agents (spec, impl, review, close).
To change status manually, use the Advance or Demote operations in this skill
(e.g., "advance T-XXX" or "demote T-XXX"). To reopen a completed or cancelled
task, use "reopen T-XXX".
```

### Step 3.1: Apply Changes

1. Update the relevant column(s) in the table row in tasks.md
2. If Depends changed, validate all references exist and no circular dependencies
3. Save the file

### Step 3.2: Confirm

Show the user the changes:
```
Updated T-XXX:
  <field>: <old value> → <new value>
```

## Phase 4: Remove Task

### Step 4.0: Identify Task

1. Parse the task ID from the user's request
2. Find the task row in the table
3. If task not found → **STOP**: "Task T-XXX not found in tasks.md"

### Step 4.1: Validate Removal

**HARD BLOCK:** Check if any other task depends on this task:

```
Scan Depends column of ALL tasks for references to T-XXX
```

If any task depends on T-XXX:
```
Cannot remove T-XXX — the following tasks depend on it:
- T-YYY: <title>
- T-ZZZ: <title>

Remove or update the dependencies first.
```

**Warning:** If the task has status other than `Pendente`, warn the user:
```
Task T-XXX has status '<status>'. Removing a task that is in progress or done
may cause data loss. Are you sure?
```

Use `AskUser` for confirmation.

### Step 4.2: Remove from tasks.md

1. Remove the table row for T-XXX from tasks.md
2. Save

**NOTE:** Do NOT renumber remaining task IDs. IDs are permanent identifiers.

### Step 4.3: Confirm

```
Removed task T-XXX: <title>
```

## Phase 5: Reorder Tasks

### Step 5.0: Determine New Order

Reordering changes the visual order of rows in the table. It does NOT change IDs or dependencies.

Options:
- **Move task:** "Move T-005 before T-003" → reposition one row
- **Full reorder:** "Reorder by priority" → sort all rows by priority (Alta → Media → Baixa)
- **Custom:** User provides a new order

### Step 5.1: Apply Reorder

1. Rearrange table rows according to the requested order
2. Do NOT change any cell values (ID, Title, Tipo, Status, Depends, Priority, Branch stay the same)
3. Save the file

### Step 5.2: Confirm

Show the new table order.

## Phase 6: Cancel Task

### Step 6.0: Identify Task

1. Parse the task ID from the user's request
2. Find the task row in the table
3. If task not found → **STOP**: "Task T-XXX not found in tasks.md"

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

   ```bash
   git worktree list | grep -iF "T-XXX"
   ```

   If a worktree is found, ask via `AskUser`:
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
2. Remove the `branch` field from the task's entry in state.json (if branch was deleted in Step 6.1).
4. **Invoke notification hooks (if present):**
   ```bash
   _optimus_sanitize() { printf '%s' "$1" | tr -cd '[:alnum:][:space:]-_./:'; }
   HOOKS_FILE=$(test -f ./tasks-hooks.sh && echo ./tasks-hooks.sh || (test -f ./docs/tasks-hooks.sh && echo ./docs/tasks-hooks.sh))
   if [ -n "$HOOKS_FILE" ] && [ -x "$HOOKS_FILE" ]; then
     "$HOOKS_FILE" task-cancelled "$(_optimus_sanitize "T-XXX")" "$(_optimus_sanitize "<old status>")" "$(_optimus_sanitize "Cancelado")" 2>/dev/null &
   fi
   ```
5. **Fire `task-blocked` hook for affected dependents:** For each non-cancelled task that
   depends on T-XXX (identified in Step 6.1, item 3), fire the `task-blocked` hook:
   ```bash
   if [ -n "$HOOKS_FILE" ] && [ -x "$HOOKS_FILE" ]; then
     "$HOOKS_FILE" task-blocked "$(_optimus_sanitize "T-YYY")" "$(_optimus_sanitize "<dep-status>")" "$(_optimus_sanitize "<dep-status>")" "$(_optimus_sanitize "blocked by T-XXX (Cancelado)")" 2>/dev/null &
   fi
   ```

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

## Phase 7: Reopen Task

### Step 7.0: Identify Task

1. Parse the task ID from the user's request
2. Find the task row in the table
3. If task not found → **STOP**: "Task T-XXX not found in tasks.md"

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
   - From `Cancelado`: remove entry from state.json (= `Pendente`, must restart from stage-1)
2. If reopening from `Cancelado`, also remove the `branch` field from state.json (any previous
   branch is stale and should not be reused)
3. Clean stale session state: `rm -f ".optimus/sessions/session-${TASK_ID}.json"`
4. **Invoke notification hooks (if present):**
   ```bash
   _optimus_sanitize() { printf '%s' "$1" | tr -cd '[:alnum:][:space:]-_./:'; }
   HOOKS_FILE=$(test -f ./tasks-hooks.sh && echo ./tasks-hooks.sh || (test -f ./docs/tasks-hooks.sh && echo ./docs/tasks-hooks.sh))
   if [ -n "$HOOKS_FILE" ] && [ -x "$HOOKS_FILE" ]; then
     "$HOOKS_FILE" status-change "$(_optimus_sanitize "T-XXX")" "$(_optimus_sanitize "DONE")" "$(_optimus_sanitize "<target status>")" 2>/dev/null &
   fi
   ```

### Step 7.3: Confirm

```
Reopened task T-XXX: <title>
  Previous status: [DONE | Cancelado]
  New status: <target status>
  Reason: <user's reason>
  Next step: [run /optimus-plan | switch to branch and run /optimus-build]
```

---

## Phase 8: Advance Status

Manually advance a task's status to skip a stage (e.g., when the user implemented
code manually without using stage-2).

### Step 8.0: Identify Task and Target Status

1. Parse the task ID from the user's request
2. Find the task row in the table
3. If task not found → **STOP**: "Task T-XXX not found in tasks.md"
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
2. **Check dependencies (HARD BLOCK):** same rules as stage agents — all dependencies must be `DONE`.
3. **Workspace check (warning):** If the target status is `Validando Spec` or later, verify
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
4. Warn via `AskUser`:
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
2. **Invoke notification hooks (if present):**
   ```bash
   _optimus_sanitize() { printf '%s' "$1" | tr -cd '[:alnum:][:space:]-_./:'; }
   HOOKS_FILE=$(test -f ./tasks-hooks.sh && echo ./tasks-hooks.sh || (test -f ./docs/tasks-hooks.sh && echo ./docs/tasks-hooks.sh))
   if [ -n "$HOOKS_FILE" ] && [ -x "$HOOKS_FILE" ]; then
     "$HOOKS_FILE" status-change "$(_optimus_sanitize "T-XXX")" "$(_optimus_sanitize "<old status>")" "$(_optimus_sanitize "<target status>")" 2>/dev/null &
   fi
   ```

---

## Phase 9: Demote Status

Move a task back to a previous status (e.g., when stage-3 review identifies
that significant rework is needed and the task should go back to implementation).

### Step 9.0: Identify Task and Target Status

1. Parse the task ID from the user's request
2. Find the task row in the table
3. If task not found → **STOP**: "Task T-XXX not found in tasks.md"
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
3. **Invoke notification hooks (if present):**
   ```bash
   _optimus_sanitize() { printf '%s' "$1" | tr -cd '[:alnum:][:space:]-_./:'; }
   HOOKS_FILE=$(test -f ./tasks-hooks.sh && echo ./tasks-hooks.sh || (test -f ./docs/tasks-hooks.sh && echo ./docs/tasks-hooks.sh))
   if [ -n "$HOOKS_FILE" ] && [ -x "$HOOKS_FILE" ]; then
     "$HOOKS_FILE" status-change "$(_optimus_sanitize "T-XXX")" "$(_optimus_sanitize "<old status>")" "$(_optimus_sanitize "<target status>")" 2>/dev/null &
   fi
   ```

---

## Phase 10: Batch Operations

If the user provides multiple tasks to create at once (e.g., a list of tasks), process them sequentially:

1. Generate IDs for all tasks first (to allow cross-references in dependencies)
2. Validate all dependencies
3. Add all rows to tasks.md
4. Show summary of all created tasks

## Phase 11: Version Management

### Step 11.0: Determine Version Operation

| Sub-operation | Triggers |
|---------------|----------|
| **Create** | "create version", "add version", "new version" |
| **Edit** | "edit version", "change version status", "rename version" |
| **Remove** | "remove version", "delete version" |
| **Reorder** | "reorder versions" |

### Step 11.1: Create Version

Ask the user for:
1. **Name** (required): Version name (e.g., `v3`, `Sprint 4`, `Futuro`)
2. **Status** (required): `Ativa`, `Próxima`, `Planejada`, `Backlog`, or `Concluída`. Default: `Planejada`
3. **Description** (required): Short description of the version's scope

**Validation:**
- If the name already exists in the Versions table → **STOP**: "Version '<name>' already exists."
- If the user sets Status to `Ativa` and another version is already `Ativa` → ask via `AskUser`:
  "Version '<existing>' is currently Ativa. Change it to Próxima and set '<new>' as Ativa?"
- If the user sets Status to `Próxima` and another version is already `Próxima` → ask via `AskUser`:
  "Version '<existing>' is currently Próxima. Change it to Planejada and set '<new>' as Próxima?"

Add the row to the Versions table and commit: `chore(tasks): create version <name>`

### Step 11.2: Edit Version

Editable fields:

| Field | Notes |
|-------|-------|
| Name | Updates the Versions table AND all tasks referencing this version |
| Status | Must be valid. See validation rules below |
| Description | Free text |

**Status change validation:**
- If setting to `Ativa` and another version is already `Ativa` → ask via `AskUser`:
  "Version '<existing>' is currently Ativa. Change it to Próxima and set '<name>' as Ativa?"
- If setting to `Próxima` and another version is already `Próxima` → ask via `AskUser`:
  "Version '<existing>' is currently Próxima. Change it to Planejada and set '<name>' as Próxima?"
- If setting to `Concluída`:
  - **If this version is currently `Ativa`:** check if a `Próxima` version exists:
    - If yes → ask via `AskUser`: "Version '<name>' is the active version. Setting it to
      Concluída will leave no active version unless '<próxima-version>' is promoted to
      Ativa. Promote '<próxima-version>' to Ativa automatically?"
    - If no → **STOP**: "Version '<name>' is the only active version. Before marking it
      Concluída, set another version to Ativa via 'edit version <name>, set to Ativa'."
  - Check tasks in this version:
    - Classify non-DONE tasks into two groups:
      - **In progress:** tasks with status other than `DONE` or `Cancelado` (e.g., Pendente, Em Andamento, etc.)
      - **Cancelled:** tasks with status `Cancelado`
    - If no in-progress AND no cancelled → proceed (all DONE)
    - If no in-progress BUT some cancelled → softer warning via `AskUser`:
      "Version '<name>' has all active tasks DONE, but N tasks were cancelled:
      - T-XXX: <title> (Cancelado)
      Mark as Concluída anyway?"
    - If any in-progress → stronger warning via `AskUser`:
      "Version '<name>' has N tasks still in progress:
      - T-XXX: <title> (Status: <status>)
      - T-YYY: <title> (Status: <status>)
      [And M cancelled tasks, if any]
      Mark as Concluída anyway?"
    - **BLOCKING:** Do NOT proceed without user confirmation

Commit: `chore(tasks): update version <name>`

### Step 11.3: Remove Version

**HARD BLOCK:** Check if this is the only version:
```
Count the rows in the Versions table
```
If only one version exists → **STOP**: "Cannot remove the only version. Create another version first."

**HARD BLOCK:** Check if any task references this version:
```
Scan the Version column of ALL tasks for references to <version-name>
```

If any task references it:
```
Cannot remove version '<name>' — the following tasks reference it:
- T-XXX: <title>
- T-YYY: <title>

Move these tasks to another version first.
```

If no tasks reference it, remove the row from the Versions table.
Commit: `chore(tasks): remove version <name>`

### Step 11.4: Reorder Versions

Rearrange rows in the Versions table. Does NOT change any values — only visual order.

## Phase 12: Move Tasks Between Versions

Move one or more tasks from one version to another.

### Step 12.0: Parse Move Request

The user may say:
- "move T-003 to v2" → single task
- "move T-003, T-005 to Futuro" → multiple specific tasks
- "move all Pendente from MVP to v2" → batch by status + source version
- "move all from MVP to v2" → batch by source version (all statuses except DONE)

### Step 12.1: Validate Target Version

Verify the target version exists in the Versions table. If not → **STOP**: "Version '<name>' does not exist. Create it first."

### Step 12.2: Identify Tasks to Move

For batch moves, list the tasks that match the criteria and present to the user via `AskUser`:

```
Tasks to move from <source> to <target>:

| ID | Title | Status | Priority |
|----|-------|--------|----------|
| T-003 | Login page | Pendente | Alta |
| T-005 | E2E tests | Pendente | Media |

Confirm move?
```

**BLOCKING:** Do NOT proceed without confirmation.

### Step 12.3: Apply Move

1. Update the Version column for each identified task
2. Do NOT change Status, Branch, Depends, Priority, or any other field
3. Save and commit: `chore(tasks): move N tasks from <source> to <target>`

## Rules

1. **Status changes are restricted** — the Edit operation cannot change status (use Reopen, Advance, or Demote operations instead, which write to state.json). Status and Branch live in state.json, not in tasks.md.
2. **Always validate format** after any modification (re-check marker, columns, IDs, deps, versions)
3. **IDs are permanent** — never renumber or reuse deleted IDs
4. **Circular dependency detection is mandatory** — check before saving
5. **Confirm destructive operations** (remove) with the user before executing
6. **Preserve format marker** — first line must always be `<!-- optimus:tasks-v1 -->`
7. **Commit changes** — after any structural modification to tasks.md, commit with message: `chore(tasks): <operation> T-XXX`. Status changes (state.json) are NOT committed — state.json is gitignored.
8. **Version validation** — every task must reference a version that exists in the Versions table
9. **Exactly one Ativa version** — when setting a version to `Ativa`, the current `Ativa` must be demoted (ask user)
10. **At most one Próxima version** — when setting a version to `Próxima`, the current `Próxima` must be demoted to `Planejada` (ask user)

<!-- INLINE-PROTOCOLS:START -->
## Shared Protocols (from AGENTS.md)

The following protocols are referenced by this skill. They are
extracted from the Optimus AGENTS.md to make this plugin self-contained.

### File Location

All Optimus files live in the `.optimus/` directory at the project root:

```
.optimus/
├── config.json          # versionado — tasksDir
├── tasks.md             # versionado — structural task data (NO status, NO branch)
├── state.json           # gitignored — operational state (status, branch per task)
├── stats.json           # gitignored — stage execution counters per task
├── sessions/            # gitignored — session state for crash recovery
└── reports/             # gitignored — exported reports
```

**Configuration** is stored in `.optimus/config.json`:

```json
{
  "tasksDir": "docs/pre-dev"
}
```

- **`tasksDir`**: Path to the Ring pre-dev artifacts root. Default: `docs/pre-dev`.
  The import and stage agents look for task specs at `<tasksDir>/tasks/` and subtasks
  at `<tasksDir>/subtasks/`.

**Tasks file** is always `.optimus/tasks.md` — not configurable.

**Operational state** is stored in `.optimus/state.json` (gitignored):

```json
{
  "T-001": { "status": "DONE", "branch": "feat/t-001-setup-auth", "updated_at": "2025-01-15T10:30:00Z" },
  "T-003": { "status": "Em Andamento", "branch": "feat/t-003-user-registration", "updated_at": "2025-01-16T14:00:00Z" }
}
```

- Each key is a task ID. A task with no entry is `Pendente` (implicit default).
- `status`: current pipeline stage (see Valid Status Values).
- `branch`: the derived branch name, stored for quick reference (always re-derivable).
- Stage agents read and write this file — never tasks.md — for status changes.
- If state.json is lost, status can be reconstructed: task with a worktree = in progress,
  without = Pendente. The agent asks the user to confirm before proceeding.

**Stage execution stats** are stored in `.optimus/stats.json` (gitignored):

```json
{
  "T-001": { "plan_runs": 2, "check_runs": 3, "last_plan": "2025-01-15T10:30:00Z", "last_check": "2025-01-16T14:00:00Z" },
  "T-002": { "plan_runs": 1, "check_runs": 0 }
}
```

- Each key is a task ID. Values track how many times `plan` and `check` executed on the task.
- A high `plan_runs` signals unclear or problematic specs. A high `check_runs` signals
  complex review cycles or specification gaps.
- The file is created on first use by `plan` or `check`. If missing, agents treat all
  counters as 0.
- `report` reads this file to display churn metrics.

Agents resolve paths:
1. **Read `.optimus/config.json`** for `tasksDir`. Fallback: `docs/pre-dev`.
2. **Tasks file:** `.optimus/tasks.md` (fixed path).
3. **If tasks.md not found:** **STOP** and suggest running `import` to create one.

The `.optimus/state.json`, `.optimus/stats.json`, `.optimus/sessions/`, and
`.optimus/reports/` are gitignored (operational/temporary state).
The `.optimus/config.json` and `.optimus/tasks.md` are versioned (structural data).


### Valid Status Values (stored in state.json)

Status lives in `.optimus/state.json`, NOT in tasks.md. A task with no entry in
state.json is implicitly `Pendente`.

| Status | Set by | Meaning |
|--------|--------|---------|
| `Pendente` | Initial (implicit) | Not started — no entry in state.json |
| `Validando Spec` | plan | Spec being validated |
| `Em Andamento` | build | Implementation in progress |
| `Validando Impl` | check | Implementation being reviewed |
| `DONE` | done | Completed |
| `Cancelado` | tasks, done | Task abandoned, will not be implemented |

**Administrative status operations** (managed by tasks, not by stage agents):
- **Reopen:** `DONE` → `Pendente` (remove entry from state.json) or `Em Andamento` (if worktree exists) — when a bug is found after close. Also accepts `Cancelado` → `Pendente` — when a cancellation decision is reversed.
- **Advance:** move forward one stage — when work was done manually outside the pipeline
- **Demote:** move backward one stage — when rework is needed after review
- **Cancel:** any non-terminal → `Cancelado` — task will not be implemented

These operations require explicit user confirmation.


### Format Validation

Every stage agent (1-4) MUST validate the tasks.md format before operating:
1. **First line** is `<!-- optimus:tasks-v1 -->` (format marker)
2. A `## Versions` section exists with a table containing columns: Version, Status, Description
3. All Version Status values are valid (`Ativa`, `Próxima`, `Planejada`, `Backlog`, `Concluída`)
4. Exactly one version has Status `Ativa`
5. At most one version has Status `Próxima`
6. A markdown table exists with columns: ID, Title, Tipo, Depends, Priority, Version (Estimate and TaskSpec are optional — tables without them are still valid). **Status and Branch columns are NOT expected** — they live in state.json.
7. All task IDs follow the `T-NNN` pattern
8. All Tipo values are one of: `Feature`, `Fix`, `Refactor`, `Chore`, `Docs`, `Test`
9. All Depends values are either `-` or comma-separated valid task IDs that exist as rows in the tasks table (not just matching `T-NNN` pattern — the referenced task must actually exist)
10. All Priority values are one of: `Alta`, `Media`, `Baixa`
11. All Version values reference a version name that exists in the Versions table
12. No duplicate task IDs
13. No circular dependencies in the dependency graph (e.g., T-001 → T-002 → T-001)

If the format marker is missing or validation fails, the agent must **STOP** and suggest
running `/optimus-import` to fix the format. Do NOT attempt to interpret malformed data.

14. No unescaped pipe characters (`|`) in task titles (breaks markdown table parsing)
15. **Empty table handling:** If the tasks table exists but has zero data rows (only headers),
format validation PASSES. Stage agents (1-4) MUST check for this condition immediately after
format validation and before task identification. If zero data rows: **STOP** and inform the
user: "No tasks found in tasks.md. Use `/optimus-tasks` to create a task or `/optimus-import`
to import from Ring pre-dev." Do NOT proceed to task identification with an empty table.

**NOTE:** For circular dependency detection (item 13), trace the full dependency chain for
each task. If any task appears twice in the chain, a cycle exists. Report ALL tasks involved
in the cycle so the user can fix it with `/optimus-tasks`.


### Protocol: Initialize .optimus Directory

**Referenced by:** import, tasks, report (export), quick-report, batch, all stage agents (1-4) for session files

Before creating ANY file inside `.optimus/`, ensure the directory structure exists
and operational/temporary files are gitignored:

```bash
mkdir -p .optimus/sessions .optimus/reports
if ! grep -q '^# optimus-operational-files' .gitignore 2>/dev/null; then
  printf '\n# optimus-operational-files\n.optimus/state.json\n.optimus/stats.json\n.optimus/sessions/\n.optimus/reports/\n' >> .gitignore
fi
```

The `.optimus/config.json` and `.optimus/tasks.md` are versioned (structural data).
The `.optimus/state.json`, `.optimus/stats.json`, `sessions/`, and `reports/` are
gitignored (operational/temporary state).

Skills reference this as: "Initialize .optimus directory — see AGENTS.md Protocol: Initialize .optimus Directory."


### Protocol: State Management

**Referenced by:** all stage agents (1-4), tasks, report, quick-report, import, batch

All status and branch data is stored in `.optimus/state.json` (gitignored).

**Prerequisites:**

```bash
if ! command -v jq >/dev/null 2>&1; then
  echo "ERROR: jq is required for state management but not installed."
  # STOP — do not proceed
fi
```

**Reading state:**

```bash
STATE_FILE=".optimus/state.json"
if [ -f "$STATE_FILE" ]; then
  # Validate JSON integrity before reading
  if ! jq empty "$STATE_FILE" 2>/dev/null; then
    echo "WARNING: state.json is corrupted. Running reconciliation."
    rm -f "$STATE_FILE"
    # Fall through to missing-file handling below
  fi
fi
# One-time migration: Revisando PR → Validando Impl (status removed)
if [ -f "$STATE_FILE" ] && jq -e 'to_entries[] | select(.value.status == "Revisando PR")' "$STATE_FILE" >/dev/null 2>&1; then
  jq 'with_entries(if .value.status == "Revisando PR" then .value.status = "Validando Impl" else . end)' "$STATE_FILE" > "${STATE_FILE}.tmp" \
    && mv "${STATE_FILE}.tmp" "$STATE_FILE"
  echo "NOTE: Migrated tasks from 'Revisando PR' to 'Validando Impl' (status removed in this version)."
fi
if [ -f "$STATE_FILE" ]; then
  TASK_STATUS=$(jq -r --arg id "$TASK_ID" '.[$id].status // "Pendente"' "$STATE_FILE")
  TASK_BRANCH=$(jq -r --arg id "$TASK_ID" '.[$id].branch // ""' "$STATE_FILE")
else
  TASK_STATUS="Pendente"
  TASK_BRANCH=""
fi
```

A task with no entry in state.json is implicitly `Pendente`.

**Writing state:**

```bash
# Initialize .optimus directory — see AGENTS.md Protocol: Initialize .optimus Directory.
STATE_FILE=".optimus/state.json"
if [ ! -f "$STATE_FILE" ]; then
  echo '{}' > "$STATE_FILE"
fi
if [ -z "$TASK_ID" ] || [ -z "$NEW_STATUS" ]; then
  echo "ERROR: Cannot write state — TASK_ID or NEW_STATUS is empty."
  # STOP — do not proceed
fi
UPDATED_AT=$(date -u +%Y-%m-%dT%H:%M:%SZ)
if jq --arg id "$TASK_ID" --arg status "$NEW_STATUS" --arg branch "$BRANCH_NAME" --arg ts "$UPDATED_AT" \
  '.[$id] = {status: $status, branch: $branch, updated_at: $ts}' "$STATE_FILE" > "${STATE_FILE}.tmp"; then
  mv "${STATE_FILE}.tmp" "$STATE_FILE"
else
  rm -f "${STATE_FILE}.tmp"
  echo "ERROR: jq failed to update state.json"
  # STOP — do not proceed
fi
```

**Removing entry (for Pendente reset):**

```bash
STATE_FILE=".optimus/state.json"
if [ ! -f "$STATE_FILE" ]; then
  echo "state.json does not exist — task is already implicitly Pendente."
else
  if jq --arg id "$TASK_ID" 'del(.[$id])' "$STATE_FILE" > "${STATE_FILE}.tmp"; then
    mv "${STATE_FILE}.tmp" "$STATE_FILE"
  else
    rm -f "${STATE_FILE}.tmp"
    echo "ERROR: jq failed to update state.json"
  fi
fi
```

**Listing all tasks with status (for report/quick-report):**

```bash
STATE_FILE=".optimus/state.json"
TASKS_FILE=".optimus/tasks.md"
# Validate state.json if it exists
if [ -f "$STATE_FILE" ] && ! jq empty "$STATE_FILE" 2>/dev/null; then
  echo "WARNING: state.json is corrupted. Treating all tasks as Pendente."
  rm -f "$STATE_FILE"
fi
# Get all task IDs from tasks.md
TASK_IDS=$(grep -E '^\| T-[0-9]+ \|' "$TASKS_FILE" | awk -F'|' '{print $2}' | tr -d ' ')
# For each task, read status from state.json (default: Pendente)
for TASK_ID in $TASK_IDS; do
  if [ -f "$STATE_FILE" ]; then
    STATUS=$(jq -r --arg id "$TASK_ID" '.[$id].status // "Pendente"' "$STATE_FILE")
  else
    STATUS="Pendente"
  fi
  echo "$TASK_ID: $STATUS"
done
```

**state.json is NEVER committed.** It is gitignored. No `git add` or `git commit`
for state changes.

**Reconciliation (if state.json is lost or empty):**
1. List all worktrees: `git worktree list`
2. For each worktree matching a task ID pattern (e.g., `t-003` in the path),
   infer status as `Em Andamento` (most common in-progress status)
3. Tasks without worktrees are `Pendente`
4. Ask the user to confirm before proceeding

**Automatic mismatch detection:** Stage agents SHOULD check for inconsistencies on startup:
if state.json is missing or empty AND worktrees exist for known task IDs, warn the user
and offer to run reconciliation before proceeding. This prevents tasks from silently
appearing as `Pendente` when they actually have active worktrees.

Skills reference this as: "Read/write state.json — see AGENTS.md Protocol: State Management."


### Protocol: tasks.md Validation (HARD BLOCK)

**Referenced by:** all stage agents (1-4), tasks, batch. Note: resolve performs inline format validation in its own Step 4.2.

Every stage agent MUST validate tasks.md before operating. The full validation rules are
defined in the "Format Validation" section above (items 1-15). This protocol is the
executable version:

1. **Resolve paths:**
   - `TASKS_FILE` is always `.optimus/tasks.md` (fixed path).
   - Read `.optimus/config.json`. If `tasksDir` key exists, use that path. Otherwise, use `docs/pre-dev` (default).
   - Store as `TASKS_FILE` and `TASKS_DIR`.
2. **Find tasks.md:** Check if `TASKS_FILE` exists. If not found, **STOP** and suggest `/optimus-import`.
3. **Validate format:** Execute all 15 validation checks from the "Format Validation" section. If the format marker is missing or any check fails, **STOP** and suggest `/optimus-import`.

**All subsequent references to `tasks.md` in the skill use the resolved `TASKS_FILE` path.
All references to Ring pre-dev artifacts use `TASKS_DIR` as the root** — never hardcoded paths.

Skills reference this as: "Find and validate tasks.md (HARD BLOCK) — see AGENTS.md Protocol: tasks.md Validation."


<!-- INLINE-PROTOCOLS:END -->
