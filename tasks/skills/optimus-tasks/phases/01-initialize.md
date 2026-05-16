# Phase 1: Initialize

Loaded by SKILL.md first. Sanity setup: optional gh check (only for ops that interact with GitHub), tasks.md location, format validation, ID/version scan.

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

