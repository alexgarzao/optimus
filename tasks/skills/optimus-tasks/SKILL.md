---
name: optimus-tasks
description: "Administrative task management for optimus-tasks.md. Create, edit, remove, reorder, cancel, and reopen tasks. Manage versions (create, edit, remove, reorder) and move tasks between versions. Validates format, dependencies, and ID uniqueness. Runs on any branch -- this is an administrative skill, not an execution skill."
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
  - When user says "manage tasks" or "edit optimus-tasks.md"
skip_when: >
  - User wants to execute a task (use plan instead)
  - User wants to change task status through the lifecycle (status is managed by stage agents -- except cancellation, which is handled here)
prerequisite: >
  - <tasksDir>/optimus-tasks.md exists in the project (default tasksDir: docs/pre-dev)
NOT_skip_when: >
  - "I can edit optimus-tasks.md manually" -- This agent validates format, dependencies, and IDs automatically.
  - "It's just a small change" -- Even small changes can break format or create circular dependencies.
examples:
  - name: Add a new task
    invocation: "Add a task: implement password reset"
    expected_flow: >
      1. Parse optimus-tasks.md
      2. Generate next ID (T-NNN)
      3. Ask for details (priority, dependencies)
      4. Add row to table with TaskSpec column
      5. Validate and save
  - name: Edit task priority
    invocation: "Change T-003 priority to Alta"
    expected_flow: >
      1. Parse optimus-tasks.md
      2. Find T-003 row
      3. Update Priority column
      4. Save
  - name: Remove a task
    invocation: "Remove T-004"
    expected_flow: >
      1. Parse optimus-tasks.md
      2. Check no other tasks depend on T-004
      3. Remove row from table
      4. Save
related:
  complementary:
    - optimus-import
    - optimus-report
verification:
  manual:
    - After any operation, verify optimus-tasks.md still has valid format marker
    - Verify no duplicate IDs exist
    - Verify no broken dependency references
---

# optimus-tasks

Administrative CRUD operations for tasks in `optimus-tasks.md`.

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

### Step 1.0.1: Find and Validate optimus-tasks.md

1. **Resolve paths and git scope:** Execute AGENTS.md Protocol: Resolve Tasks Git Scope.
   This obtains `TASKS_DIR`, `TASKS_FILE`, `TASKS_GIT_SCOPE`, `TASKS_GIT_REL`, and the
   `tasks_git` helper.

2. **Find optimus-tasks.md:** Resolve the path using the AGENTS.md Protocol: optimus-tasks.md Validation.
   The file is at `<TASKS_DIR>/optimus-tasks.md` (default: `docs/pre-dev/optimus-tasks.md`).

   If not found, ask the user via `AskUser`:

   "No optimus-tasks.md found. What should I do?"
   - **(a) Create at <TASKS_DIR>/optimus-tasks.md** (standard location)
   - **(b) Run import** — use this if you already have task files in another format

   If the user chooses to create:
   1. Ask for an initial version name via `AskUser` (e.g., "MVP", "v1")
   2. Ensure the directory exists: `mkdir -p "$TASKS_DIR"`
   3. Write `TASKS_FILE` with:
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
   4. Initialize .optimus directory — see AGENTS.md Protocol: Initialize .optimus Directory.
   5. Commit using `tasks_git` (lands in same-repo or separate-repo as resolved):
      ```bash
      tasks_git add "$TASKS_GIT_REL"
      COMMIT_MSG_FILE=$(mktemp)
      printf '%s' "chore(tasks): initialize optimus-tasks.md" > "$COMMIT_MSG_FILE"
      tasks_git commit -F "$COMMIT_MSG_FILE"
      rm -f "$COMMIT_MSG_FILE"
      ```

3. **Validate format (HARD BLOCK):** See AGENTS.md Protocol: optimus-tasks.md Validation.

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

Templates pre-fill Tipo and Priority. The task creation flow delegates to Step 2.3.1 (Resolve TaskSpec for the New Task) which offers Generate/Link/Defer.

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
2. **Tipo** (required): `Feature`, `Fix`, `Refactor`, `Chore`, `Docs`, or `Test`. The Tipo determines the Conventional Commits prefix used downstream by `plan` (branch name), `build` (commit messages), and `review` (PR title) — see AGENTS.md "Valid Tipo Values" table for the full mapping.
3. **Priority** (required): `Alta`, `Media`, or `Baixa`
4. **Estimate** (optional): Task size estimate (`S`, `M`, `L`, `XL`, `2h`, `1d`, etc.). Default: `-`
5. **Version** (required): Must match a version in the Versions table. Default: the version with Status `Ativa`
6. **Dependencies** (optional): Comma-separated task IDs (e.g., `T-001, T-003`) or `-` for none
7. **Ring pre-dev reference** (optional): If not provided, Step 2.3.1 will offer to generate via Ring, link an existing spec, or defer (TaskSpec=-).

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
optimus-tasks.md uses markdown tables where `|` is the column delimiter.

If the title contains `|`:
- Automatically replace `|` with `—` (em dash) or `\|` (escaped pipe)
- Inform the user: "Title contained pipe characters which would break the optimus-tasks.md table format. Replaced with '—'."

Also reject titles longer than 120 characters — longer titles break table formatting.
If too long, ask the user to shorten it.

### Step 2.2: Generate Task ID

Collect IDs from ALL sources to avoid collisions with parallel branches:

1. **Local:** Parse all existing task IDs from the current branch's optimus-tasks.md table
2. **Remote:** Fetch and parse IDs from the tasks repo's default branch on origin
   (uses `tasks_git` so it works in both same-repo and separate-repo scopes):
   ```bash
   if [ "$TASKS_GIT_SCOPE" = "separate-repo" ]; then
     TASKS_DEFAULT_BRANCH=$(tasks_git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's@^refs/remotes/origin/@@')
     if [ -z "$TASKS_DEFAULT_BRANCH" ]; then
       TASKS_DEFAULT_BRANCH=$(tasks_git branch --list main master 2>/dev/null | head -1 | tr -d ' *')
     fi
   else
     TASKS_DEFAULT_BRANCH=$(git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's@^refs/remotes/origin/@@')
     if [ -z "$TASKS_DEFAULT_BRANCH" ]; then
       TASKS_DEFAULT_BRANCH=$(git branch --list main master 2>/dev/null | head -1 | tr -d ' *')
     fi
   fi
   if [ -n "$TASKS_DEFAULT_BRANCH" ]; then
     tasks_git fetch origin "$TASKS_DEFAULT_BRANCH" --quiet 2>/dev/null
     tasks_git show "origin/${TASKS_DEFAULT_BRANCH}:${TASKS_GIT_REL}" 2>/dev/null | grep -oE 'T-[0-9]+'
   fi
   ```
   If `TASKS_DEFAULT_BRANCH` is empty or fetch fails, warn the user: "Could not determine
   default branch or reach remote — ID may collide with tasks created on other
   branches. Continuing with local IDs only."
3. **Worktrees:** Scan parallel worktrees of the tasks repo for IDs (in separate-repo,
   worktrees are per-tasks-repo; in same-repo, worktrees are the project's):
   ```bash
   tasks_git worktree list --porcelain 2>/dev/null | grep "^worktree " | while read _ path; do
     # In separate-repo, path is absolute to tasks repo; append TASKS_GIT_REL
     # In same-repo, path is absolute to project repo; append TASKS_GIT_REL as well
     cat "$path/$TASKS_GIT_REL" 2>/dev/null | grep -oE 'T-[0-9]+'
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

### Step 2.3.1: Resolve TaskSpec for the New Task

Ask the user how to handle the spec for this task. Always ask, even when Ring is available — the user may want to defer spec generation (e.g., creating multiple tasks in a row, batch-generating specs later).

> Note: This prompt offers Defer (not Cancel) because task creation can succeed without an immediate spec; the next `/optimus-plan T-XXX` will offer to resolve.

Ask via `AskUser`:

```
[topic] (1/1) How should I handle the spec for this task?
```

Options:
- **Generate via Ring** (recommended) — invoke `ring:pre-dev-feature` now
- **Link existing spec** — search `<TASKS_DIR>/tasks/` for matching specs
- **Defer** — set TaskSpec to `-`. The next `/optimus-plan T-XXX` run will offer to generate it later.

**If "Generate via Ring":**

1. **Choose the Ring track.** Read the task's `Estimate` column (the value the user just provided for this new task) and apply the auto-suggestion rule below to pick the recommended default. Ask via `AskUser`:

   ```
   [topic] (1/1) Which Ring track for T-XXX? (Estimate: <estimate>)
   ```

   Options (mark the auto-suggested one with " (recommended)"):
   - **Lightweight** (`ring:pre-dev-feature`) — 4 gates, for tasks <2 days
   - **Full** (`ring:pre-dev-full`) — 9 gates, for tasks ≥2 days or multi-component features

   Save the user's choice as `RING_TRACK` ∈ {`feature`, `full`}. The selected skill name is `ring:pre-dev-feature` (when `feature`) or `ring:pre-dev-full` (when `full`).

   **Auto-suggestion rule** (suggest the matching option as "(recommended)"; the user can always override):

   | Estimate value | Suggested default |
   |----------------|-------------------|
   | `S`, `M` | Lightweight |
   | `L`, `XL` | Full |
   | Hour-based (e.g. `2h`, `8h`) | Lightweight |
   | `1d` | Lightweight |
   | Multi-day (`2d`, `3d`, `1w`, etc.) | Full |
   | `-` or unknown | Lightweight |

2. Verify the chosen Ring skill (`ring:pre-dev-feature` OR `ring:pre-dev-full`) is available. If unavailable → fall back to the OTHER track if it is available; if neither is available → warn and fall back to "Link existing spec" automatically.
3. Invoke the chosen Ring skill via the `Skill` tool. The Skill tool has no argument channel — state the task title and tipo in conversation context immediately before the invocation (e.g., "Generating spec for T-XXX: <title> (Tipo: <tipo>)"). Ring will read these from context.
4. **If Ring fails or returns no spec path:**
   - Warn the user: "Ring failed to generate the spec: <error>."
   - Re-prompt with `Link existing spec` / `Defer`. Do NOT silently fall through.
5. **If Ring succeeds:**
   - Ring generates the spec file in `<TASKS_DIR>/tasks/`.
   - Capture the generated spec file path (relative to `TASKS_DIR`).
   - Store as the `TaskSpec` value for this task.
6. **Record the chosen Ring track in state.json** — see AGENTS.md Protocol: State Management. If `.optimus/` does not yet exist, see AGENTS.md Protocol: Initialize .optimus Directory first. The snippet below performs an idempotent merge into the task's existing record (preserving any `status`, `branch`, `updated_at` fields):

   ```bash
   # Record the chosen Ring track (idempotent merge into existing record)
   if [ ! -f "$STATE_FILE" ]; then echo '{}' > "$STATE_FILE"; fi
   UPDATED_AT=$(date -u +%Y-%m-%dT%H:%M:%SZ)
   if jq --arg id "$TASK_ID" --arg track "$RING_TRACK" --arg ts "$UPDATED_AT" \
     '.[$id] = ((.[$id] // {}) + {ring_track: $track, ring_track_recorded_at: $ts})' \
     "$STATE_FILE" > "${STATE_FILE}.tmp"; then
     if jq empty "${STATE_FILE}.tmp" 2>/dev/null; then
       mv "${STATE_FILE}.tmp" "$STATE_FILE"
     else
       rm -f "${STATE_FILE}.tmp"
       echo "ERROR: jq produced invalid JSON — state.json unchanged" >&2
       exit 1
     fi
   else
     rm -f "${STATE_FILE}.tmp"
     echo "ERROR: jq failed to update state.json" >&2
     exit 1
   fi
   ```

**If "Link existing spec":**

1. Search `<TASKS_DIR>/tasks/*.md` for task files.
2. Rank candidates by keyword overlap with the task title; present the top 5 matches via `AskUser`.
3. User picks one or types a custom relative path under `<TASKS_DIR>/tasks/`.
4. **HARD BLOCK** — Validate the chosen path: (a) exists, (b) is a regular file (NOT a symlink), (c) resolves inside `<TASKS_DIR>` with no intermediate symlink components, (d) contains no pipe (`|`), control characters, newlines. Apply the realpath/case-glob/symlink rejection block from AGENTS.md Protocol: TaskSpec Resolution. If validation fails, do NOT write to optimus-tasks.md; loop back to the picker.
5. Store the chosen path as the `TaskSpec` value for this task.

**If "Defer":**

1. Set TaskSpec to `-`.
2. Note to user: "Task created without spec. Run `/optimus-plan T-XXX` later to generate or link one."

### Step 2.4: Apply Create

1. Add a new row to the table:
   ```
   | T-NNN | <title> | <tipo> | <depends> | <priority> | <version> | <estimate or -> | <taskspec or -> |
   ```
2. Save the file
3. **Re-validate after mutation** — see AGENTS.md Protocol: optimus-tasks.md Validation.
   If validation fails, abort and revert the in-memory edits; do not commit.

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
3. If task not found → **STOP**: "Task T-XXX not found in optimus-tasks.md"

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
| Branch | **No** | Branch is managed ONLY by plan and done |
| ID | **No** | IDs are immutable |
| Ring reference | **No** | Managed by import and task creation only |

**HARD BLOCK:** If the user tries to change Status or Branch, refuse:
```
Status is managed by the cycle stage agents (plan, build, review, done).
To change status manually, use the Advance or Demote operations in this skill
(e.g., "advance T-XXX" or "demote T-XXX"). To reopen a completed or cancelled
task, use "reopen T-XXX".
```

### Step 3.1: Apply Edit

1. Update the relevant column(s) in the table row in optimus-tasks.md
2. If Depends changed, validate all references exist and no circular dependencies
3. Save the file
4. **Re-validate after mutation** — see AGENTS.md Protocol: optimus-tasks.md Validation.
   If validation fails, abort and revert the in-memory edits; do not commit.

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
3. If task not found → **STOP**: "Task T-XXX not found in optimus-tasks.md"

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

### Step 4.2: Apply Remove

1. Remove the table row for T-XXX from optimus-tasks.md
2. Save
3. **Re-validate after mutation** — see AGENTS.md Protocol: optimus-tasks.md Validation.
   If validation fails, abort and revert the in-memory edits; do not commit.

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
4. **Re-validate after mutation** — see AGENTS.md Protocol: optimus-tasks.md Validation.
   If validation fails, abort and revert the in-memory edits; do not commit.

### Step 5.2: Confirm

Show the new table order.

## Phase 6: Cancel Task

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

## Phase 7: Reopen Task

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

---

## Phase 8: Advance Status

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

---

## Phase 9: Demote Status

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

---

## Phase 10: Batch Operations

If the user provides multiple tasks to create at once (e.g., a list of tasks), process them sequentially:

1. Generate IDs for all tasks first (to allow cross-references in dependencies)
2. Validate all dependencies
3. Add all rows to optimus-tasks.md
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
3. Save the file
4. **Re-validate after mutation** — see AGENTS.md Protocol: optimus-tasks.md Validation.
   If validation fails, abort and revert the in-memory edits; do not commit.
5. Commit: `chore(tasks): move N tasks from <source> to <target>`

## Rules

1. **Status changes are restricted** — the Edit operation cannot change status (use Reopen, Advance, or Demote operations instead, which write to state.json). Status and Branch live in state.json, not in optimus-tasks.md.
2. **Always validate format** after any modification (re-check marker, columns, IDs, deps, versions)
3. **IDs are permanent** — never renumber or reuse deleted IDs
4. **Circular dependency detection is mandatory** — check before saving
5. **Confirm destructive operations** (remove) with the user before executing
6. **Preserve format marker** — first line must always be `<!-- optimus:tasks-v1 -->`
7. **Commit changes** — after any structural modification to optimus-tasks.md, commit with message: `chore(tasks): <operation> T-XXX`. Status changes (state.json) are NOT committed — state.json is gitignored.
8. **Version validation** — every task must reference a version that exists in the Versions table
9. **Exactly one Ativa version** — when setting a version to `Ativa`, the current `Ativa` must be demoted (ask user)
10. **At most one Próxima version** — when setting a version to `Próxima`, the current `Próxima` must be demoted to `Planejada` (ask user)

<!-- INLINE-PROTOCOLS:START -->
## Shared Protocols (from AGENTS.md)

The following protocols are referenced by this skill. They are
extracted from the Optimus AGENTS.md to make this plugin self-contained.

### Task Spec Resolution

Every task SHOULD have a Ring pre-dev reference in the `TaskSpec` column. Tasks may be created with `TaskSpec=-` (deferred); the next `/optimus-plan` run will offer to generate or link a spec. Stage agents
(plan, build, review) resolve the full path as `<tasksDir>/<TaskSpec>` and read the
referenced file for objective, acceptance criteria, and implementation details.

The subtasks directory is derived automatically from the TaskSpec path:
- TaskSpec: `tasks/task_001.md` → Subtasks: `<tasksDir>/subtasks/T-001/`
- The `T-NNN` identifier is extracted from the task spec filename convention

Agents read objective and acceptance criteria directly from the Ring source files.
The optimus-tasks.md table only tracks structural data (dependencies, versions, priorities)
— it does NOT duplicate content from Ring.


<!-- INLINE-PROTOCOLS:END -->
