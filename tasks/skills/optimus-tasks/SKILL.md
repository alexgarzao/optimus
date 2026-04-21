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
  - docs/tasks.md exists in the project
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
      4. Add row to table and create overlay file
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
      3. Remove row and overlay file
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
   (reads `tasksFile` from `.optimus.json`, falls back to `docs/tasks.md`).

   If not found, ask the user via `AskUser`:

   "No tasks.md found. What should I do?"
   - **(a) Create at docs/tasks.md** (default location)
   - **(b) Create at a custom path** — user specifies (e.g., `project/tasks.md`)
   - **(c) Run import** — use this if you already have task files in another format

   If the user chooses to create:
   1. Determine the path (`TASKS_FILE`) — default or custom
   2. Initialize the tasks directory (see AGENTS.md Protocol: Initialize Tasks Directory)
   3. Ask for an initial version name via `AskUser` (e.g., "MVP", "v1")
   4. Write `TASKS_FILE` with:
      ```markdown
      <!-- optimus:tasks-v1 -->
      # Tasks

      ## Versions
      | Version | Status | Description |
      |---------|--------|-------------|
      | <user-provided> | Ativa | <ask user for description> |

      | ID | Title | Tipo | Status | Depends | Priority | Version | Branch | Estimate |
      |----|-------|------|--------|---------|----------|---------|--------|----------|
      ```
   5. If `TASKS_FILE` is not the default (`docs/tasks.md`), register it in `.optimus.json`:
      ```bash
      if [ ! -f .optimus.json ]; then echo '{}' > .optimus.json; fi
      jq --arg path "$TASKS_FILE" '.tasksFile = $path' .optimus.json > .optimus.json.tmp && mv .optimus.json.tmp .optimus.json
      ```
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
- **API Endpoint** — pre-fills Feature tipo, standard API progress items
- **Bug Fix** — pre-fills Fix tipo, standard debugging progress items
- **UI Component** — pre-fills Feature tipo, standard frontend progress items
- **Chore/Infra** — pre-fills Chore tipo, standard infrastructure progress items
- **Refactor** — pre-fills Refactor tipo, standard refactoring progress items
- **Documentation** — pre-fills Docs tipo, standard documentation progress items
- **Test** — pre-fills Test tipo, standard testing progress items
- **From scratch** — manual entry (no template)

#### Built-in Templates

Templates pre-fill `## Progresso` items in the overlay file. When a Ring pre-dev
reference is linked (Step 2.3.1), the template items are replaced by subtask
headings from the Ring source.

**API Endpoint template:**
- Tipo: `Feature`, Priority: `Alta`
- Progresso:
  - [ ] Endpoint implemented with correct HTTP method and path
  - [ ] Request validation (required fields, types, constraints)
  - [ ] Success response format matches API contract
  - [ ] Error responses with appropriate HTTP status codes
  - [ ] Authentication/authorization enforced
  - [ ] Unit tests for handler (happy path + error paths)
  - [ ] Integration tests for repository layer
  - [ ] Documentation updated (if applicable)

**Bug Fix template:**
- Tipo: `Fix`, Priority: `Alta`
- Progresso:
  - [ ] Root cause identified and documented
  - [ ] Fix implemented with minimal scope
  - [ ] Regression test added (reproduces the bug, passes after fix)
  - [ ] No unrelated changes included
  - [ ] Unit tests passing

**UI Component template:**
- Tipo: `Feature`, Priority: `Media`
- Progresso:
  - [ ] Component renders correctly in all states (empty, loading, error, success)
  - [ ] Responsive design (mobile, tablet, desktop)
  - [ ] Accessibility (keyboard navigation, ARIA labels, screen reader)
  - [ ] Unit tests for component logic
  - [ ] Visual matches design spec

**Chore/Infra template:**
- Tipo: `Chore`, Priority: `Media`
- Progresso:
  - [ ] Configuration/infrastructure change applied
  - [ ] No regression in existing functionality
  - [ ] Documentation updated (if applicable)

**Refactor template:**
- Tipo: `Refactor`, Priority: `Media`
- Progresso:
  - [ ] Refactoring applied without changing external behavior
  - [ ] All existing tests still pass
  - [ ] No new warnings introduced
  - [ ] Code review confirms improvement in readability/maintainability

**Documentation template:**
- Tipo: `Docs`, Priority: `Baixa`
- Progresso:
  - [ ] Documentation written/updated
  - [ ] Examples included (if applicable)
  - [ ] Links and references verified
  - [ ] Spelling and grammar checked

**Test template:**
- Tipo: `Test`, Priority: `Media`
- Progresso:
  - [ ] Test scenarios identified and documented
  - [ ] Tests implemented and passing
  - [ ] Coverage improved for target area
  - [ ] No flaky tests introduced

When a template is selected, pre-fill the Tipo, Priority, and Progresso items.
The user can then modify any field before confirming.

**Option B: From scratch.** Ask the user for task details using `AskUser` (one question at a time or batch if info provided):

1. **Title** (required): Short description of the task
2. **Tipo** (required): `Feature`, `Fix`, `Refactor`, `Chore`, `Docs`, or `Test`
3. **Priority** (required): `Alta`, `Media`, or `Baixa`
4. **Estimate** (optional): Task size estimate (`S`, `M`, `L`, `XL`, `2h`, `1d`, etc.). Default: `-`
5. **Version** (required): Must match a version in the Versions table. Default: the version with Status `Ativa`
6. **Dependencies** (optional): Comma-separated task IDs (e.g., `T-001, T-003`) or `-` for none
7. **Progress items** (optional): Checklist items for `## Progresso` in the overlay file. If omitted, Ring pre-dev discovery (Step 2.3.1) will populate them.

If the user provided some of these in the initial request, use them and ask only for missing fields.

### Step 2.1: Check for Similar Tasks (duplicate detection)

Before creating, search existing tasks for potential duplicates:

1. **Compare by title:** For each existing task, check if the new title shares 2+ significant
   keywords with an existing title (ignore articles, prepositions, and generic words like
   "implement", "add", "create", "update", "fix")
2. **Compare by Ring source:** If a Ring pre-dev task was linked, check if any existing task's
   `## Fonte` already references the same Ring task spec file

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
   git fetch origin "$DEFAULT_BRANCH" --quiet 2>/dev/null
   git show "origin/$DEFAULT_BRANCH:$TASKS_FILE" 2>/dev/null | grep -oE 'T-[0-9]+'
   ```
   If fetch fails (no network), warn the user: "Could not reach remote — ID may
   collide with tasks created on other branches. Continuing with local IDs only."
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
1. Verify each dependency ID exists in the table
2. Check for circular dependencies: if T-NEW depends on T-X, and T-X (directly or transitively) would depend on T-NEW → reject
3. If any dependency ID is invalid → ask the user to correct it

### Step 2.3.1: Link Ring Pre-Dev Artifacts

Search for Ring pre-dev artifacts to link to this task:

1. Scan `docs/pre-dev/tasks/*.md` for task files
2. Extract 3-5 significant keywords from the new task's title
3. Calculate keyword overlap and sort by relevance

**If matches found** (1+ keyword in common), present via `AskUser`:
```
Found ring pre-dev tasks that may be related to "<new task title>":

  [1] task_020.md — "Painel UI Redesign (Sidebar + Topbar)" (3 keywords)
      Subtasks: 13 files in docs/pre-dev/subtasks/T-020/
  [2] task_022.md — "Formularios Responsivos com Abas" (1 keyword)

Link to one of these?
```
Options:
- **[N] task_NNN.md** — link this ring task
- **Show all ring tasks** — list every task for manual selection
- **None** — create without Ring reference (overlay will have empty Progresso)

**If no matches found or `docs/pre-dev/tasks/` does not exist**, ask:
```
No ring pre-dev tasks found. Create task without Ring reference?
```
Options:
- **Show all ring tasks** — list every task for manual selection (if directory exists)
- **Create without reference** — overlay with empty Progresso

### Step 2.4: Add to tasks.md and create overlay file

1. Add a new row to the table in `docs/tasks.md`:
   ```
   | T-NNN | <title> | <tipo> | Pendente | <depends> | <priority> | <version> | - | <estimate or -> |
   ```
2. Create the overlay file `docs/tasks/T-NNN.md`:

   **If linked to Ring pre-dev:**
   ```markdown
   # T-NNN: <title>

   ## Fonte
   **Task spec:** `docs/pre-dev/tasks/task_NNN.md`
   **Subtasks:** `docs/pre-dev/subtasks/T-NNN/`

   ## Progresso
   - [ ] <subtask 1 short title>
   - [ ] <subtask 2 short title>
   ```

   **If no Ring pre-dev linked:**
   ```markdown
   # T-NNN: <title>

   ## Progresso
   ```
3. Save both files

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
| Title | Yes | Updates both table row and `docs/tasks/T-NNN.md` heading |
| Tipo | Yes | Must be `Feature`, `Fix`, `Refactor`, `Chore`, `Docs`, or `Test` |
| Priority | Yes | Must be `Alta`, `Media`, or `Baixa` |
| Version | Yes | Must reference a version in the Versions table |
| Depends | Yes | Must validate references and check circular deps |
| Estimate | Yes | Free text (S, M, L, XL, 2h, 1d) or `-` |
| Status | **No** | Status is managed ONLY by stage agents |
| Branch | **No** | Branch is managed ONLY by stage-1 and close |
| ID | **No** | IDs are immutable |
| Progress items | Yes | Updates `## Progresso` in `docs/tasks/T-NNN.md` |

**HARD BLOCK:** If the user tries to change Status or Branch, refuse:
```
Status is managed by the cycle stage agents (spec, impl, review, close).
To change status manually, use the Advance or Demote operations in this skill
(e.g., "advance T-XXX" or "demote T-XXX"). To reopen a completed or cancelled
task, use "reopen T-XXX".
```

### Step 3.1: Apply Changes

1. Update the relevant column(s) in the table row in `docs/tasks.md`
2. If Title changed, also update the heading in `docs/tasks/T-NNN.md`
3. If Depends changed, validate all references exist and no circular dependencies
4. If Progress items changed, update `## Progresso` in `docs/tasks/T-NNN.md`
5. Save the file(s)

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

### Step 4.2: Remove from tasks.md and delete overlay file

1. Remove the table row for T-XXX from `docs/tasks.md`
2. Delete the overlay file `docs/tasks/T-NNN.md`
3. Save

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
3. Overlay files in `docs/tasks/` are not affected by reordering
4. Save the file

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
   git worktree list | grep -i "T-XXX"
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

5. **If task has a branch** (Branch column is not `-`):
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

1. Update the **Status** column to `Cancelado`
2. Update the **Branch** column to `-` (if branch was deleted in Step 6.1)
3. Save and commit: `chore(tasks): cancel T-XXX`
4. **Invoke notification hooks (if present):**
   ```bash
   HOOKS_FILE=$(test -f ./tasks-hooks.sh && echo ./tasks-hooks.sh || (test -f ./docs/tasks-hooks.sh && echo ./docs/tasks-hooks.sh))
   if [ -n "$HOOKS_FILE" ] && [ -x "$HOOKS_FILE" ]; then
     "$HOOKS_FILE" task-cancelled T-XXX "<old status>" "Cancelado" 2>/dev/null &
   fi
   ```
5. **Fire `task-blocked` hook for affected dependents:** For each non-cancelled task that
   depends on T-XXX (identified in Step 6.1, item 3), fire the `task-blocked` hook:
   ```bash
   if [ -n "$HOOKS_FILE" ] && [ -x "$HOOKS_FILE" ]; then
     "$HOOKS_FILE" task-blocked T-YYY "<dep-status>" "<dep-status>" "blocked by T-XXX (Cancelado)" 2>/dev/null &
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
     - Read the **Branch** column for this task
     - If Branch is NOT `-` AND the branch exists locally (`git branch --list "<branch>"`):
       - Target status: `Em Andamento` (workspace exists, can resume implementation)
     - If Branch is `-` OR the branch no longer exists:
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
   - **Incomplete** — not all progress items were actually met
   - **Requirements changed** — spec was updated after close
   - **Decision reversed** — cancellation decision was reconsidered (only for Cancelado)
   - **Cancel** — keep current status

   **BLOCKING:** Do NOT proceed without user confirmation and justification.

### Step 7.2: Apply Reopen

1. Update the **Status** column to the target status determined in Step 7.1:
   - From `DONE`: `Em Andamento` if workspace exists, `Pendente` if not
   - From `Cancelado`: always `Pendente` (must restart from stage-1)
2. If reopening from `Cancelado`, also clear the **Branch** column to `-` (any previous
   branch is stale and should not be reused)
3. Save and commit: `chore(tasks): reopen T-XXX — <reason> (from <previous status>, now <target status>)`
4. **Invoke notification hooks (if present):**
   ```bash
   HOOKS_FILE=$(test -f ./tasks-hooks.sh && echo ./tasks-hooks.sh || (test -f ./docs/tasks-hooks.sh && echo ./docs/tasks-hooks.sh))
   if [ -n "$HOOKS_FILE" ] && [ -x "$HOOKS_FILE" ]; then
     "$HOOKS_FILE" status-change T-XXX "DONE" "<target status>" 2>/dev/null &
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
   | `Validando Impl` | `Revisando PR` |
   | `Revisando PR` | (use done to mark DONE) |
   | `DONE` | (use Reopen instead) |
   | `Cancelado` | (use Reopen or create new task) |

### Step 8.1: Validate Advance

1. **If status is `DONE` or `Cancelado`** → **STOP**: "Task T-XXX is in terminal status '<status>'. Use 'reopen' for DONE tasks."
1b. **If target status is `DONE`** → **STOP**: "Cannot advance to DONE manually. Use `/optimus-done` which runs the verification checklist."
1c. **If target status is `Cancelado`** → **STOP**: "Cannot advance to Cancelado. Use the cancel operation (`cancel T-XXX`) which handles cleanup."
1d. **If current status is `Revisando PR` and no target was specified** → **STOP**: "Task T-XXX is in 'Revisando PR'. The next step is `/optimus-done`, not manual advance."
2. **Check dependencies (HARD BLOCK):** same rules as stage agents — all dependencies must be `DONE`.
3. **Workspace check (warning):** If the target status is `Em Andamento` or later, verify
   that a workspace exists for this task:
   - Read the Branch column for the task
   - If Branch is `-` or the branch does not exist locally → warn via `AskUser`:
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

1. Update the **Status** column to the target status
2. Save and commit: `chore(tasks): advance T-XXX to <target status> (manual override)`
3. **Invoke notification hooks (if present):**
   ```bash
   HOOKS_FILE=$(test -f ./tasks-hooks.sh && echo ./tasks-hooks.sh || (test -f ./docs/tasks-hooks.sh && echo ./docs/tasks-hooks.sh))
   if [ -n "$HOOKS_FILE" ] && [ -x "$HOOKS_FILE" ]; then
     "$HOOKS_FILE" status-change T-XXX "<old status>" "<target status>" 2>/dev/null &
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
   | `Revisando PR` | `Validando Impl` |
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

1. Update the **Status** column to the target status
2. Save and commit: `chore(tasks): demote T-XXX to <target status> — <reason>`
3. **Invoke notification hooks (if present):**
   ```bash
   HOOKS_FILE=$(test -f ./tasks-hooks.sh && echo ./tasks-hooks.sh || (test -f ./docs/tasks-hooks.sh && echo ./docs/tasks-hooks.sh))
   if [ -n "$HOOKS_FILE" ] && [ -x "$HOOKS_FILE" ]; then
     "$HOOKS_FILE" status-change T-XXX "<old status>" "<target status>" 2>/dev/null &
   fi
   ```

---

## Phase 10: Batch Operations

If the user provides multiple tasks to create at once (e.g., a list of tasks), process them sequentially:

1. Generate IDs for all tasks first (to allow cross-references in dependencies)
2. Validate all dependencies
3. Add all rows to `docs/tasks.md` and create all `docs/tasks/T-NNN.md` overlay files
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
- If setting to `Concluída` → check tasks in this version:
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

1. **Status changes are restricted** — the Edit operation cannot change Status (use Reopen, Advance, or Demote operations instead, which include validation and audit trail). Branch is managed exclusively by stage agents and close cleanup.
2. **Always validate format** after any modification (re-check marker, columns, IDs, deps, versions)
3. **IDs are permanent** — never renumber or reuse deleted IDs
4. **Circular dependency detection is mandatory** — check before saving
5. **Confirm destructive operations** (remove) with the user before executing
6. **Preserve format marker** — first line must always be `<!-- optimus:tasks-v1 -->`
7. **Commit changes** — after any modification, commit with message: `chore(tasks): <operation> T-XXX`
8. **Version validation** — every task must reference a version that exists in the Versions table
9. **Exactly one Ativa version** — when setting a version to `Ativa`, the current `Ativa` must be demoted (ask user)
10. **At most one Próxima version** — when setting a version to `Próxima`, the current `Próxima` must be demoted to `Planejada` (ask user)
