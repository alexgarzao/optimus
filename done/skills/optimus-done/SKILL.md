---
name: optimus-done
description: "Stage 4 of the task lifecycle. Requires PR in final state (merged or closed) before marking task as done. Cleans up worktree and branch interactively."
trigger: >
  - After the PR has been merged or closed
  - When user requests closing a task (e.g., "close T-012", "mark T-012 as done")
skip_when: >
  - Task has not been through at least review yet
  - Task is already done
  - PR is still open (hard block — merge or close the PR first)
prerequisite: >
  - Task exists in tasks.md with status "Validando Impl" in state.json
  - review has completed
  - PR must be in final state (MERGED or CLOSED) or not exist
NOT_skip_when: >
  - "The PR was already merged" -- Still need to mark DONE and clean up worktree/branch.
  - "It's a small task" -- All tasks need the same close verification.
examples:
  - name: Close after PR merged
    invocation: "Close task T-012"
    expected_flow: >
      1. Confirm task ID
      2. Validate status and gates (uncommitted, unpushed, PR final)
      3. Mark as DONE
      4. Clean up worktree and branch
  - name: PR still open
    invocation: "Close task T-012"
    expected_flow: >
      1. Confirm task ID
      2. Gate 3 fails — PR #N is still open
      3. STOP — inform user to merge/close PR first
related:
  complementary:
    - optimus-pr-check
    - optimus-review
  sequence:
    after:
      - optimus-review
      - optimus-pr-check
verification:
  manual:
    - All 3 gates passed
    - Task status updated to DONE in state.json
    - Worktree and branch cleaned up
---

# Task Closer

Stage 4 of the task lifecycle. Verifies all prerequisites before marking a task as done.

---

## Phase 1: Identify and Validate Task

### Step 1.0: Verify GitHub CLI (HARD BLOCK)

Verify GitHub CLI — see AGENTS.md Protocol: GitHub CLI Check.

### Step 1.0.1: Find and Validate tasks.md

**HARD BLOCK:** Find and validate tasks.md — see AGENTS.md Protocol: tasks.md Validation.

### Step 1.0.2: Resolve Workspace (HARD BLOCK)
Resolve workspace — see AGENTS.md Protocol: Workspace Auto-Navigation. Branch-task cross-validation is included in this protocol.

### Step 1.0.3: Identify Task to Close

**If the user specified a task ID** (e.g., "close T-012"):
- Use the provided task ID
- Confirm with the user using `AskUser`: "I'll close task T-012: [task title]. Correct?"

**If the user did NOT specify a task ID:**
1. Look for tasks with status `Validando Impl`
2. If exactly one found, suggest it
3. If multiple found, ask the user which one to close
4. If none found, inform the user there are no tasks ready to close

**BLOCKING**: Do NOT proceed until the user confirms which task to close.

### Step 1.0.3.1: Check Session State

Execute session state protocol — see AGENTS.md Protocol: Session State. Use stage=`done`, status=`DONE`.

**On marking DONE** (Phase 3): delete the session file and restore terminal title.

### Step 1.0.3.2: Set Terminal Title

**CRITICAL:** Set the terminal title so the user can identify this terminal at a glance. Execute this command NOW:

```bash
printf '\033]0;optimus: DONE %s — %s\007' "$TASK_ID" "$TASK_TITLE"
```

**On stage completion or exit**, restore the title:

```bash
printf '\033]0;\007'
```

### Step 1.1: Validate Task Status

**HARD BLOCK:** This step is mandatory. Do NOT skip it.

1. Read `tasks.md` and find the row for the confirmed task ID
2. Read the task's status from state.json — see AGENTS.md Protocol: State Management.
   - If status is `Validando Impl` → proceed (review has completed)
   - If status is `Pendente` → **STOP**: "Task T-XXX is in 'Pendente'. It must go through plan, build, and review first."
   - If status is `Validando Spec` → **STOP**: "Task T-XXX is in 'Validando Spec'. Run build and review first."
   - If status is `Em Andamento` → **STOP**: "Task T-XXX is in 'Em Andamento'. Run review first."
   - If status is `DONE` → **STOP**: "Task T-XXX is already done. Re-execution of done is not supported."
   - If status is `Cancelado` → **STOP**: "Task T-XXX was cancelled. Cannot close a cancelled task."
3. **Check dependencies (HARD BLOCK):** Read the Depends column for this task from tasks.md.
   - If Depends is `-` → proceed (no dependencies)
   - For each dependency ID listed, read its status from state.json:
     - If ALL dependencies have status `DONE` → proceed
     - If ANY dependency is NOT `DONE`:
       - Invoke notification hooks (event=`task-blocked`) — see AGENTS.md Protocol: Notification Hooks.
       - If the dependency has status `Cancelado` → **STOP**: `"T-YYY was cancelled (Cancelado). Consider removing this dependency via /optimus-tasks."`
       - Otherwise → **STOP**: `"Task T-XXX depends on T-YYY (status: '<status>'). T-YYY must be DONE first."`
3.1. **Active version guard:** Check active version guard — see AGENTS.md Protocol: Active Version Guard.
4. **Expanded confirmation before status change:**
   - **If the user did NOT specify the task ID explicitly** (auto-detect):
     - Present to the user via `AskUser`:
       ```
       I'm about to close task T-XXX and mark it as DONE (from '<current>').

       **T-XXX: [title]**
       **Version:** [version from table]

       Confirm close?
       ```
     - **BLOCKING:** Do NOT proceed to the close checklist until the user confirms
   - **If the user specified the task ID explicitly** (e.g., "close T-012"):
     - Skip expanded confirmation (user already has context)

   **NOTE:** done does not support re-execution (status always changes to `DONE`), so the re-execution skip does not apply here.

### Step 1.2: Check tasks.md Divergence (warning)

Check tasks.md divergence — see AGENTS.md Protocol: Divergence Warning.

---

## Phase 2: Close Gates

Run gates sequentially. Each gate is a **HARD BLOCK** — if it fails, STOP immediately.

### Gate 1: No Uncommitted Changes

```bash
git status --porcelain
```

- **PASS:** Output is empty → proceed to Gate 2
- **FAIL → HARD BLOCK:**
  ```
  Uncommitted changes found:
    M src/handler.go
    ?? new_file.go

  Commit or discard these changes before running done.
  ```
  **STOP** — do NOT proceed.

### Gate 2: No Unpushed Commits

```bash
git rev-parse --abbrev-ref @{u} 2>/dev/null
```

- **If no upstream:** HARD BLOCK — "Branch has no upstream. Run `git push -u origin \"$(git branch --show-current)\"` first."
- **If upstream exists:**
  ```bash
  git log @{u}..HEAD --oneline
  ```
  - **PASS:** Output is empty → proceed to Gate 3
  - **FAIL → HARD BLOCK:** "N unpushed commits. Run `git push` first."

### Gate 3: PR in Final State

```bash
HEAD_BRANCH=$(git branch --show-current 2>/dev/null)
if [ -z "$HEAD_BRANCH" ]; then
  echo "ERROR: Cannot determine current branch. Checkout the task branch first."
  # STOP — HARD BLOCK
fi
PR_JSON=$(gh pr list --head "$HEAD_BRANCH" --json number,state --jq '.[0]')
if [ $? -ne 0 ]; then
  echo "ERROR: GitHub CLI failed. Check network and run 'gh auth status'."
  # STOP — HARD BLOCK (cannot verify PR state)
fi
```

- **gh command failed (non-zero exit):** HARD BLOCK — cannot verify PR state
- **No PR exists** (PR_JSON is empty or "null"): PASS → proceed (task went directly to default branch)
- **PR state is MERGED:** PASS → proceed
- **PR state is CLOSED (not merged):** Ask via `AskUser`:
  ```
  PR #N was closed without merging. How should this task be marked?
  ```
  Options:
  - **Mark as DONE** — task is complete despite PR closure (e.g., changes landed another way)
  - **Mark as Cancelado** — task was abandoned
  - **Cancel** — stop, do not change status
- **PR state is OPEN → HARD BLOCK:**
  ```
  PR #N is still open. Merge or close the PR before running done.
  Lint, tests, and CI validation happen in the PR pipeline — not in done.
  ```
  **STOP** — do NOT proceed.

---

## Phase 3: Mark Task as Done

All gates passed. Mark the task:

1. Update status to `DONE` (or `Cancelado` if user chose that in Gate 3) in state.json — see AGENTS.md Protocol: State Management.
2. Invoke notification hooks (event=`status-change`) — see AGENTS.md Protocol: Notification Hooks.
3. If DONE: invoke notification hooks (event=`task-done`).
   If Cancelado: invoke notification hooks (event=`task-cancelled`).
4. Proceed to Phase 4 (cleanup).

---

## Phase 4: Cleanup (after marking DONE)

This phase runs ONLY after the task has been marked as `DONE` (or `Cancelado`).

### Step 4.1: Check for Task Worktree

**IMPORTANT:** Worktree must be removed BEFORE attempting branch deletion.

```bash
git worktree list | grep -iF "T-XXX"
```

If a worktree is found, ask via `AskUser`:
```
Task T-XXX is done. A worktree still exists at '<path>'. What should I do?
```
Options:
- **Remove worktree**: `git worktree remove <path>`
- **Keep**: Leave the worktree as is

**Edge case — running INSIDE the worktree:** If the agent's current working directory IS
the worktree being removed, `cd` to the main repository first:
1. Identify the main repository path from `git worktree list` (first entry)
2. `cd <main-repo-path>`
3. Then `git worktree remove <worktree-path>`

### Step 4.2: Check for Task Branch

Identify the task's branch:

```bash
TASK_BRANCH=$(jq -r --arg id "$TASK_ID" '.[$id].branch // ""' .optimus/state.json 2>/dev/null)
if [ -z "$TASK_BRANCH" ]; then
  TASK_BRANCH=$(git branch --list "*$(echo "$TASK_ID" | tr '[:upper:]' '[:lower:]')*" 2>/dev/null | head -1 | tr -d ' *')
fi
```

If the branch exists (locally and/or remotely), ask via `AskUser`:
```
Task T-XXX is done. The branch '<branch>' still exists. What should I do?
```
Options:
- **Delete local and remote**: switch to default branch, pull, then delete
- **Delete local only**: switch to default branch, delete local
- **Keep**: Leave the branch as is

**Final confirmation for destructive options:** If the user selects "Delete local and remote"
or "Delete local only", present a final confirmation via `AskUser`:
"This will permanently delete branch `<branch>`. Are you sure?" Options: Yes, delete / Cancel.

**Before deleting:** switch to the default branch first:
```bash
DEFAULT_BRANCH=$(git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's@^refs/remotes/origin/@@')
if [ -z "$DEFAULT_BRANCH" ]; then
  DEFAULT_BRANCH=$(git branch --list main master 2>/dev/null | head -1 | tr -d ' *')
fi
if [ -z "$DEFAULT_BRANCH" ]; then
  echo "ERROR: Cannot determine default branch. Set it with: git remote set-head origin <branch>"
  # STOP — do not proceed with branch deletion
fi
git checkout "$DEFAULT_BRANCH"
git pull
git branch -d "$TASK_BRANCH" 2>/dev/null || git branch -D "$TASK_BRANCH"
# If also deleting remote:
git push origin --delete "$TASK_BRANCH"
```

### Step 4.3: Cleanup Summary

```markdown
## Cleanup Summary for T-XXX

| Resource | Status | Action Taken |
|----------|--------|-------------|
| Worktree `/path/to/wt` | Found | Removed / Kept |
| Branch `<tipo>/t-xxx-...` (local) | Found | Deleted / Kept |
| Branch `<tipo>/t-xxx-...` (remote) | Found | Deleted / Kept |
```

---

## Rules

- Gates are sequential hard blocks — stop at the first failure
- Do NOT change task status unless ALL gates pass
- After marking as done, update state.json (no commit needed — it's gitignored)
- Lint, tests, and CI are the responsibility of the PR pipeline — done does NOT run them
- To cancel a task without going through gates, use `/optimus-tasks cancel`
- **Next step suggestion:** After the cleanup summary, inform the user: "Task T-XXX is done.
  Run `/optimus-report` to see updated project status and what to work on next."

### Dry-Run Mode
If the user requests a dry-run (e.g., "dry-run close T-012", "preview close"):
- Run ALL 3 gates normally (Phase 2)
- Present results as information only
- **Do NOT change task status**
- **Do NOT run cleanup** — skip Phase 4 entirely

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
  "T-001": { "plan_runs": 2, "review_runs": 3, "last_plan": "2025-01-15T10:30:00Z", "last_review": "2025-01-16T14:00:00Z" },
  "T-002": { "plan_runs": 1, "review_runs": 0 }
}
```

- Each key is a task ID. Values track how many times `plan` and `review` executed on the task.
- A high `plan_runs` signals unclear or problematic specs. A high `review_runs` signals
  complex review cycles or specification gaps.
- The file is created on first use by `plan` or `review`. If missing, agents treat all
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
| `Validando Impl` | review | Implementation being reviewed |
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


### Protocol: Active Version Guard

**Referenced by:** all stage agents (1-4)

After the task ID is confirmed and dependencies are validated, check if the task belongs
to the `Ativa` version. If not, present options before proceeding.

1. Read the task's **Version** column from `tasks.md`
2. Read the **Versions** table and find the version with Status `Ativa`
   - **If no version has Status `Ativa`** → **STOP**: "No active version found in the Versions table. Run `/optimus-tasks` to set a version as Ativa before proceeding."
3. **If the task's version matches the `Ativa` version** → proceed silently
4. **If the task's version does NOT match the `Ativa` version** → present via `AskUser`:
   ```
   Task T-XXX is in version '<task_version>' (<version_status>),
   but the active version is '<active_version>'.
   To execute this task, it must be moved to the active version first.
   ```
   Options:
   - **Move to active version and continue** — updates the Version column to the active version, commits, and proceeds
   - **Cancel** — stops execution

5. **If "Move to active version and continue":**
   - Update the task's Version column in `tasks.md` to the `Ativa` version name
   - Commit:
     ```bash
     git add "$TASKS_FILE"
     COMMIT_MSG_FILE=$(mktemp)
     printf '%s' "chore(tasks): move T-XXX to active version <active_version>" > "$COMMIT_MSG_FILE"
     git commit -F "$COMMIT_MSG_FILE"
     rm -f "$COMMIT_MSG_FILE"
     ```
   - Proceed with the stage

6. **If "Cancel":** **STOP** — do not proceed with the stage

Skills reference this as: "Check active version guard — see AGENTS.md Protocol: Active Version Guard."


### Protocol: Divergence Warning

**Referenced by:** all stage agents (1-4)

Since status and branch data live in state.json (gitignored), tasks.md rarely changes
on feature branches. This protocol detects the uncommon case where tasks.md WAS modified
(e.g., Active Version Guard moved a task).

```bash
DEFAULT_BRANCH=$(git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's@^refs/remotes/origin/@@')
if [ -z "$DEFAULT_BRANCH" ]; then
  DEFAULT_BRANCH=$(git branch --list main master 2>/dev/null | head -1 | tr -d ' *')
fi
if [ -z "$DEFAULT_BRANCH" ]; then
  echo "WARNING: Cannot determine default branch. Skipping divergence check."
  # Skip — this is a warning, not a HARD BLOCK
else
  TASKS_FILE=".optimus/tasks.md"
  if ! git fetch origin "$DEFAULT_BRANCH" --quiet 2>/dev/null; then
    echo "WARNING: Could not fetch from origin. Divergence check may use stale data."
  fi
  git diff "origin/$DEFAULT_BRANCH" -- "$TASKS_FILE" 2>/dev/null | head -20
fi
```

- If diff output is non-empty → warn via `AskUser`:
  ```
  tasks.md has diverged between your branch and <default_branch>.
  This may cause merge conflicts when the PR is merged.
  ```
  Options:
  - **Sync now** — run `git merge origin/<default_branch>` to incorporate changes
  - **Continue without syncing** — I'll handle conflicts later
- If diff output is empty → proceed silently (files are in sync)
- **NOTE:** This is a warning, not a HARD BLOCK. The user may choose to continue.

Skills reference this as: "Check tasks.md divergence — see AGENTS.md Protocol: Divergence Warning."


### Protocol: GitHub CLI Check (HARD BLOCK)

**Referenced by:** all stage agents (1-4), tasks, batch

```bash
gh auth status 2>/dev/null
```

If this command fails (exit code != 0), **STOP** immediately:
```
GitHub CLI (gh) is not authenticated. Run `gh auth login` to authenticate before proceeding.
```


### Protocol: Notification Hooks

**Referenced by:** all stage agents (1-4), tasks

After writing a status change to state.json, invoke notification hooks if present.

**IMPORTANT — Capture timing:** Read the current status from state.json and store it as
`OLD_STATUS` BEFORE writing the new status. The sequence is:
1. Read current status: `OLD_STATUS=$(jq -r --arg id "$TASK_ID" '.[$id].status // "Pendente"' "$STATE_FILE")`
2. Write new status to state.json
3. Invoke hooks with `OLD_STATUS` and new status

**IMPORTANT:** Always quote all arguments and sanitize user-derived values to prevent
shell injection. Hook scripts MUST NOT pass their arguments to `eval` or shell
interpretation — treat all arguments as untrusted data.

```bash
_optimus_sanitize() { printf '%s' "$1" | tr -cd '[:alnum:][:space:]-_./:'; }
HOOKS_FILE=$(test -f ./tasks-hooks.sh && echo ./tasks-hooks.sh || (test -f ./docs/tasks-hooks.sh && echo ./docs/tasks-hooks.sh))
if [ -n "$HOOKS_FILE" ] && [ -x "$HOOKS_FILE" ]; then
  "$HOOKS_FILE" "$(_optimus_sanitize "$event")" "$(_optimus_sanitize "$task_id")" "$(_optimus_sanitize "$old_status")" "$(_optimus_sanitize "$new_status")" 2>/dev/null &
fi
```

Events and their parameter signatures:

| Event | Parameters | Description |
|-------|-----------|-------------|
| `status-change` | `event task_id old_status new_status` | Any status transition |
| `task-done` | `event task_id old_status "DONE"` | Task marked as done |
| `task-cancelled` | `event task_id old_status "Cancelado"` | Task cancelled |
| `task-blocked` | `event task_id current_status current_status reason` | Dependency check failed (5 args — includes reason) |

When a dependency check fails:
```bash
if [ -n "$HOOKS_FILE" ] && [ -x "$HOOKS_FILE" ]; then
  "$HOOKS_FILE" "task-blocked" "$(_optimus_sanitize "$task_id")" "$(_optimus_sanitize "$current_status")" "$(_optimus_sanitize "$current_status")" "$(_optimus_sanitize "blocked by $dep_id ($dep_status)")" 2>/dev/null &
fi
```

Hooks run in background (`&`) and their failure does NOT block the pipeline.
If `tasks-hooks.sh` does not exist, hooks are silently skipped.

Skills reference this as: "Invoke notification hooks — see AGENTS.md Protocol: Notification Hooks."


### Protocol: Session State

**Referenced by:** all stage agents (1-4)

Stage agents write a session state file to track progress. This enables resumption
when a session is interrupted (agent crash, user closes terminal, context window limit).

**IMPORTANT — Write timing:** The session file MUST be written **immediately after the
status change in state.json** (before any work begins). This ensures crash recovery has
a record even if the agent fails before producing any output. Do NOT wait until
"key phase transitions" to write the initial session file.

**Session file location:** `.optimus/sessions/session-<task-id>.json` (gitignored).
Each task gets its own file (e.g., `.optimus/sessions/session-T-003.json`).

```json
{
  "task_id": "T-003",
  "stage": "<stage-name>",
  "status": "<stage-output-status>",
  "branch": "feat/t-003-user-auth",
  "started_at": "2025-01-15T10:30:00Z",
  "updated_at": "2025-01-15T11:45:00Z",
  "phase": "Phase 1: Implementation",
  "convergence_round": 0,
  "findings_count": 0,
  "notes": "Implementation in progress"
}
```

**Convergence checkpoint:** During the convergence loop, update `convergence_round` and
`findings_count` after each round completes. On resume, skip to the last completed round
rather than restarting the entire analysis.

**On stage start (after task ID is known):**

```bash
SESSION_FILE=".optimus/sessions/session-${TASK_ID}.json"
if [ -f "$SESSION_FILE" ]; then
  if ! jq empty "$SESSION_FILE" 2>/dev/null; then
    echo "WARNING: Session file is corrupted. Deleting and proceeding fresh."
    rm -f "$SESSION_FILE"
  else
    cat "$SESSION_FILE"
  fi
fi
```

- If the file exists AND the task's status in `state.json` matches the session's `status`:
  - Present via `AskUser`:
    ```
    Previous session found:
      Task: T-XXX — [title]
      Stage: <stage-name>
      Last active: <time since updated_at>
      Progress: <phase from session>
    Resume this session?
    ```
    Options: Resume / Start fresh (delete session) / Continue (keep session file)
  - If **Resume**: skip to the phase indicated in the session file
  - If **Start fresh (delete session)**: delete the session file and proceed from the beginning
  - If **Continue (keep session file)**: proceed from the beginning without deleting the session file
- If the file is stale (>24h) or the task status has changed → delete and proceed normally.
  **Staleness check example:**
  ```bash
  UPDATED=$(jq -r '.updated_at // empty' "$SESSION_FILE" 2>/dev/null)
  if [ -n "$UPDATED" ]; then
    NOW_EPOCH=$(date +%s)
    if [ "$(uname)" = "Darwin" ]; then
      UPDATED_EPOCH=$(date -j -f "%Y-%m-%dT%H:%M:%SZ" "$UPDATED" +%s 2>/dev/null || echo 0)
    else
      UPDATED_EPOCH=$(date -d "$UPDATED" +%s 2>/dev/null || echo 0)
    fi
    AGE=$(( NOW_EPOCH - UPDATED_EPOCH ))
    if [ "$AGE" -gt 86400 ]; then
      echo "Session file is stale (>24h). Deleting."
      rm -f "$SESSION_FILE"
    fi
  fi
  ```
- **External status change detection:** If the session file exists AND the task's status
  does NOT match the session's `status`, check if the difference is explainable by normal
  stage progression (e.g., session says `Em Andamento` but task is now `Validando Impl` —
  the task was advanced externally via `/optimus-tasks`). If the status change is NOT
  explainable by forward progression, treat the session as stale and delete it.
- If no file exists → proceed normally

**On stage progress (at key phase transitions):**

```bash
# Initialize .optimus directory — see AGENTS.md Protocol: Initialize .optimus Directory.
mkdir -p .optimus/sessions .optimus/reports
BRANCH_NAME=$(git branch --show-current 2>/dev/null || echo "detached")
jq -n \
  --arg task_id "${TASK_ID}" --arg stage "<stage-name>" --arg status "<status>" \
  --arg branch "${BRANCH_NAME}" --arg started "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --arg updated "$(date -u +%Y-%m-%dT%H:%M:%SZ)" --arg phase "<current-phase>" \
  --arg notes "<progress>" \
  '{task_id: $task_id, stage: $stage, status: $status, branch: $branch,
    started_at: $started, updated_at: $updated, phase: $phase, notes: $notes}' \
  > ".optimus/sessions/session-${TASK_ID}.json"
```

**On stage completion:** Delete the session file:
```bash
rm -f ".optimus/sessions/session-${TASK_ID}.json"
```

Skills reference this as: "Execute session state protocol from AGENTS.md using stage=`<name>`, status=`<status>`."


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
  if jq empty "${STATE_FILE}.tmp" 2>/dev/null; then
    mv "${STATE_FILE}.tmp" "$STATE_FILE"
  else
    rm -f "${STATE_FILE}.tmp"
    echo "ERROR: jq produced invalid JSON — state.json unchanged"
    # STOP — do not proceed
  fi
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


### Protocol: Workspace Auto-Navigation (HARD BLOCK)

**Referenced by:** stages 2-4

Execution stages (2-4) resolve the correct workspace automatically. The agent MUST
be in the task's worktree before proceeding with any work.

```bash
DEFAULT_BRANCH=$(git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's@^refs/remotes/origin/@@')
if [ -z "$DEFAULT_BRANCH" ]; then
  DEFAULT_BRANCH=$(git branch --list main master 2>/dev/null | head -1 | tr -d ' *')
fi
if [ -z "$DEFAULT_BRANCH" ]; then
  echo "ERROR: Cannot determine default branch. Set it with: git remote set-head origin <branch>"
  # STOP — do not proceed
fi
CURRENT_BRANCH=$(git branch --show-current 2>/dev/null)
if [ -z "$CURRENT_BRANCH" ]; then
  echo "ERROR: Cannot determine current branch (detached HEAD state). Checkout a branch first."
  # STOP — do not proceed
fi
```

**Resolution order:**

1. **Already on a feature branch?**
   - Derive the expected branch name from the task's Tipo + ID + Title (see Protocol:
     Branch Name Derivation). Also read the `branch` field from state.json if available.
   - Cross-validate: check that `CURRENT_BRANCH` matches the expected/derived branch.
   - If matches → proceed silently.
   - If does not match → warn via `AskUser`: "Expected branch `<expected>` for T-XXX,
     but you are on `<current>`. Continue on current branch, or switch?"

2. **On the default branch (auto-navigate)?**
   - Read state.json and list tasks with status compatible with the current stage
     (use the Transition Table to determine which statuses are valid).
     Tasks with no entry in state.json are `Pendente`.
   - **If 0 eligible tasks** → **STOP**: "No tasks in `<expected-status>` found."
   - **If 1 eligible task** → suggest via `AskUser`: "Found task T-XXX — [title] in
     worktree `<path>`. Continue with this task?"
   - **If N eligible tasks** → list all with worktree paths via `AskUser`:
     ```
     Multiple tasks available:
       T-001 — User auth (Em Andamento) → /projeto-t-001-.../
       T-002 — Login page (Em Andamento) → /projeto-t-002-.../
     Which task should I continue?
     ```
   - After task is identified, locate the worktree by task ID:
     ```bash
     git worktree list | grep -iF "<task-id>"
     ```
   - **If worktree found** → change working directory to the worktree path.
   - **If worktree NOT found** → derive the branch name (Protocol: Branch Name Derivation)
     and verify it exists:
     ```bash
     if ! git rev-parse --verify "<branch-name>" >/dev/null 2>&1; then
       # Branch doesn't exist — ask user for recovery
       # AskUser: "No worktree or branch found for T-XXX.
       #   This may indicate stage-1 crashed before creating it.
       #   Options: Create branch from HEAD / Re-run /optimus-plan"
     fi
     ```
     If the branch exists, create the worktree automatically:
     ```bash
     REPO_NAME=$(basename "$(git rev-parse --show-toplevel)")
     WORKTREE_DIR="../${REPO_NAME}-$(echo <task-id> | tr '[:upper:]' '[:lower:]')-<keywords>"
     git worktree add "$WORKTREE_DIR" "<branch-name>"
     ```
     Then change working directory to the new worktree.

Skills reference this as: "Resolve workspace (HARD BLOCK) — see AGENTS.md Protocol: Workspace Auto-Navigation."


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
