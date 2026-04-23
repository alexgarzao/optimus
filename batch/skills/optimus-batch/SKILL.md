---
name: optimus-batch
description: "Chains stages 1-4 for one or more tasks sequentially. Instead of invoking each stage manually, the user specifies which tasks and stages to run, and this skill orchestrates the pipeline with user checkpoints between stages."
trigger: >
  - When user says "run all stages for T-003"
  - When user says "process T-003 through T-006"
  - When user says "batch execute", "run pipeline", "full cycle"
skip_when: >
  - User wants to run a single specific stage (use that stage directly)
  - No tasks.md exists
prerequisite: >
  - tasks.md exists in valid optimus format
  - At least one task is eligible (Pendente or in-progress)
NOT_skip_when: >
  - "I can run stages one by one" -- Batch mode saves context-switching and ensures no stage is skipped.
  - "Only one task" -- Even a single task benefits from automated stage chaining.
examples:
  - name: Full pipeline for one task
    invocation: "Run all stages for T-003"
    expected_flow: >
      1. Validate T-003 is eligible
      2. Run stage-1 (spec validation)
      3. Checkpoint -- user approves continuing
      4. Run stage-2 (implementation)
      5. Checkpoint -- user approves continuing
      6. Run stage-3 (impl review)
      7. Checkpoint -- user approves continuing
      8. Run stage-4 (close)
  - name: Multiple tasks sequentially
    invocation: "Process T-003, T-004, T-005"
    expected_flow: >
      1. Validate all tasks, compute dependency order
      2. Process each task through the pipeline in dependency order
      3. Checkpoint between tasks
related:
  complementary:
    - optimus-plan
    - optimus-build
    - optimus-check
    - optimus-pr-check
    - optimus-done
verification:
  manual:
    - All specified stages ran for each task
    - User had checkpoint between every stage
    - Task status correctly advanced through pipeline
---

# Batch Pipeline Executor

Chains stages 1-4 for one or more tasks with user checkpoints between stages.

**Classification:** Administrative skill — orchestrates execution stages, delegates workspace creation and code modification to stage skills.

---

## Phase 1: Plan the Batch

### Step 1.0: Verify GitHub CLI (HARD BLOCK)

**HARD BLOCK:** Verify GitHub CLI — see AGENTS.md Protocol: GitHub CLI Check.

### Step 1.1: Find and Validate tasks.md

1. **Find tasks.md:** Resolve the path using the AGENTS.md Protocol: tasks.md Validation.
2. **Validate format:** First line must be `<!-- optimus:tasks-v1 -->`. Full format validation.

If validation fails, **STOP** and suggest `/optimus-import`.

### Step 1.2: Identify Tasks and Stages

Parse the user's request to determine:

1. **Which tasks:** specific IDs (T-003, T-004) or "next N tasks" or "all ready tasks"
2. **Which stages:** "all" (1-4), specific range ("stages 1-3"), or "from current" (resume from task's current status)

If the user said "all ready tasks", scan for tasks with status `Pendente` and all
dependencies `DONE`. Prioritize by version (`Ativa` first), then priority, then ID.

### Step 1.3: Validate Eligibility

For each task:
1. **Read status from state.json** — see AGENTS.md Protocol: State Management. Check that the task's status allows the requested starting stage
   - **Exclude tasks with status `Cancelado`** — cancelled tasks cannot be processed through the pipeline
2. Check that all dependencies are `DONE` (read Depends from tasks.md, status for each dependency from state.json)
3. If any task is blocked, report it and exclude from the batch

**NOTE:** Eligibility is re-evaluated after each task completes (Step 2.4). Tasks that
become eligible during batch execution (e.g., because a dependency was just completed)
are added to the plan dynamically.

### Step 1.4: Compute Execution Order

If multiple tasks are specified:
1. Sort by dependency order (tasks that others depend on go first)
2. Within the same dependency level, sort by priority (`Alta` > `Media` > `Baixa`)
3. Present the execution plan to the user:

```markdown
## Batch Execution Plan

| # | Task | Title | Current Status | Start Stage | End Stage |
|---|------|-------|---------------|-------------|-----------|
| 1 | T-003 | User auth | Pendente | Stage 1 | Stage 4 |
| 2 | T-004 | Login page | Pendente | Stage 1 | Stage 4 |
| 3 | T-005 | E2E tests | Pendente | Stage 1 | Stage 4 |

Execution order respects dependencies: T-003 first (T-004, T-005 depend on it).
```

Ask via `AskUser`:
- **Execute this plan**
- **Adjust** — change task order, stages, or exclusions
- **Cancel**

**BLOCKING:** Do NOT start until the user approves.

### Step 1.5: Worktree Model

Each task in the batch may create its own worktree (via stage-1). The batch orchestrator
tracks the working directory for each task and switches context between tasks.

**Working directory tracking:**
```json
{
  "T-003": {"worktree": "../repo-t-003-user-auth", "branch": "feat/t-003-user-auth"},
  "T-004": {"worktree": "../repo-t-004-login-page", "branch": "feat/t-004-login-page"}
}
```

**Before invoking stages 2-4 for a task**, the orchestrator MUST:
1. Check if the task has a worktree (from stage-1 output or `branch` field in state.json)
2. If worktree exists, switch to it: `cd <worktree-path>`
3. Verify the correct branch is checked out: `git branch --show-current`
4. Only then invoke the stage skill

**After completing all stages for a task**, return to the original directory before
starting the next task.

---

## Phase 2: Execute Pipeline

For each task in the execution order:

Set terminal title — see AGENTS.md Protocol: Terminal Identification. Use stage=`batch` and include the current task ID in the title (e.g., `optimus: batch | T-003 — User Auth JWT`). Update the title each time the task changes.

### Step 2.1: Stage Dispatch

**Before dispatching any stage,** verify the stage skill is available. If the skill fails
to load or is not installed, **STOP**: "Stage X skill (optimus-&lt;stage&gt;) is not installed.
Install it with `droid plugin install <stage>@optimus` before running batch."

Invoke each stage sequentially. **CRITICAL:** Always pass the task ID explicitly to each
stage to prevent auto-detect from picking the wrong task.

| Stage | Skill | Invocation | Status After |
|-------|-------|-----------|-------------|
| 1 | `optimus-plan` | "spec T-XXX" (via Skill tool) | Validando Spec |
| 2 | `optimus-build` | "execute T-XXX" (via Skill tool) | Em Andamento |
| 3 | `optimus-check` | "validate T-XXX" (via Skill tool) | Validando Impl |
| 4 | `optimus-done` | "close T-XXX" (via Skill tool) | DONE |

**Worktree context switch:** Before invoking stages 2-4, switch to the task's worktree
directory (from Step 1.5 tracking). Stage-1 may create the worktree — capture its output
path and record it in the tracking map.

Each stage skill handles its own validation, status changes, and user interactions.
The batch orchestrator does NOT duplicate any stage logic — it only chains them and
manages worktree context.

**Re-run Guard:** If plan or check presents a Re-run Guard prompt during batch execution,
the user responds directly to the stage skill. Re-runs are handled internally by the
stage — batch waits until the stage resolves and completes before proceeding to the
checkpoint.

### Step 2.2: Checkpoint Between Stages

After each stage completes, present a checkpoint via `AskUser`:

```
Stage X completed for T-NNN: [title]
  Status: <current status>
  
What's next?
```

Options:
- **Continue to Stage X+1** — proceed with the next stage
- **Skip to Stage 4 (close)** — skip remaining stages and close
- **Stop here** — pause the batch, user will resume later

**BLOCKING:** Do NOT advance to the next stage without user approval.

### Step 2.3: Checkpoint Between Tasks

After completing all stages for a task, before starting the next task:

```
Task T-NNN completed (DONE).
Next: T-MMM — [title]
Remaining: X tasks

Continue with T-MMM?
```

Options:
- **Continue** — start T-MMM
- **Stop** — pause the batch

### Step 2.4: Re-Evaluate Eligibility

After completing a task (all stages done), re-evaluate the remaining task pool:

1. Re-read `tasks.md` for structural data and `state.json` for current statuses
2. Check if any previously ineligible tasks are now eligible (dependencies satisfied by the just-completed task)
3. If new eligible tasks are found, present via `AskUser`:
   ```
   Task T-NNN just completed. The following tasks are now unblocked:
   - T-MMM: [title] (was waiting for T-NNN)
   
   Add to batch?
   ```
   Options:
   - **Add to batch** — include in the remaining plan
   - **Skip** — process only the original plan
4. If added, insert them into the execution order respecting dependencies and priority

---

## Phase 3: Batch Summary

After all tasks are processed (or the user stops), restore terminal title (`printf '\033]0;\007'`):

```markdown
## Batch Execution Summary

### Completed
| # | Task | Title | Final Status | Stages Run |
|---|------|-------|-------------|------------|
| 1 | T-003 | User auth | DONE | 1-4 |
| 2 | T-004 | Login page | DONE | 1-3, 4 |

### Stopped / Remaining
| # | Task | Title | Current Status | Stopped At |
|---|------|-------|---------------|------------|
| 3 | T-005 | E2E tests | Em Andamento | Stage 2 |

### Statistics
- Tasks completed: X of Y
- Total stages executed: N
- Time elapsed: ~Xh Ym
```

---

## Rules

- Follow shell safety guidelines — see AGENTS.md Protocol: Shell Safety Guidelines.
- **NEVER skip user checkpoints** — the user must approve every stage transition
- **NEVER run stages in parallel** — tasks are processed sequentially to avoid conflicts
- **NEVER duplicate stage logic** — this skill only chains stages, each stage skill handles its own validation
- If a stage fails (task blocked, tests failing, etc.):
  1. Write failure to session file: `{"failed_task": "T-XXX", "failed_stage": N, ...}`
  2. Identify remaining tasks that do NOT depend on the failed task
  3. Present via `AskUser`:
     ```
     Stage N failed for T-XXX: [error summary]
     Independent tasks that can still proceed: [list]
     ```
     Options:
     - **Continue with independent tasks** — skip T-XXX and process remaining
     - **Retry failed task** — re-run the failed stage
     - **Stop batch entirely** — pause everything
- If the user stops the batch, write progress to `.optimus/sessions/session-batch.json`:
  ```json
  {"tasks": ["T-003", "T-004", "T-005"], "completed": ["T-003"], "current": "T-004", "current_stage": 3, "worktrees": {"T-003": "../repo-t-003", "T-004": "../repo-t-004"}}
  ```
  On next invocation, if this file exists:
  1. **Check staleness:** If `updated_at` (or file modification time) is older than 24h, delete the file and proceed fresh — project state may have changed significantly.
  2. **Verify task statuses:** Cross-reference remaining tasks' statuses in state.json against the session's `current_stage`. If statuses have changed (tasks progressed through other means), warn the user and suggest starting fresh.
  3. **If not stale and statuses match:** offer to resume from where it stopped.
- Respect dependency order — never process a task before its dependencies are DONE
- Each stage creates its own commits — the batch orchestrator does NOT commit anything

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

Every stage agent (1-5) MUST validate the tasks.md format before operating:
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
format validation PASSES. Stage agents (1-5) MUST check for this condition immediately after
format validation and before task identification. If zero data rows: **STOP** and inform the
user: "No tasks found in tasks.md. Use `/optimus-tasks` to create a task or `/optimus-import`
to import from Ring pre-dev." Do NOT proceed to task identification with an empty table.

**NOTE:** For circular dependency detection (item 13), trace the full dependency chain for
each task. If any task appears twice in the chain, a cycle exists. Report ALL tasks involved
in the cycle so the user can fix it with `/optimus-tasks`.


### Protocol: GitHub CLI Check (HARD BLOCK)

**Referenced by:** all stage agents (1-4), tasks, batch

```bash
gh auth status 2>/dev/null
```

If this command fails (exit code != 0), **STOP** immediately:
```
GitHub CLI (gh) is not authenticated. Run `gh auth login` to authenticate before proceeding.
```


### Protocol: Shell Safety Guidelines

**Referenced by:** plan, batch

All bash examples in AGENTS.md and SKILL.md files are templates that agents execute literally.
Follow these rules to prevent injection and silent failures:

1. **Always quote variables:** Use `"$VAR"` not `$VAR` — especially for paths, branch names, and user-derived values
2. **Check exit codes for critical commands:**
   ```bash
   git add "$TASKS_FILE"
   COMMIT_MSG_FILE=$(mktemp)
   printf '%s' "chore(tasks): $COMMIT_MSG" > "$COMMIT_MSG_FILE"
   if ! git commit -F "$COMMIT_MSG_FILE"; then
     echo "ERROR: git commit failed. Check pre-commit hooks or git config."
     rm -f "$COMMIT_MSG_FILE"
     # STOP — do not proceed
   fi
   rm -f "$COMMIT_MSG_FILE"
   ```
3. **Never interpolate user-derived values directly into shell commands** — task titles,
   branch names, and other user input may contain shell metacharacters
4. **Use `grep -F` for fixed string matching** — never pass branch names or task IDs
   as regex patterns to `grep` without `-F`
5. **Use `grep -E '^\| T-NNN \|'`** to match task rows in tasks.md — plain `grep "T-NNN"`
   matches titles and dependency columns too
6. **Validate tool availability** before use: `command -v jq >/dev/null 2>&1` before running `jq`
7. **Validate JSON files** before parsing: `jq empty "$FILE" 2>/dev/null` before reading keys
8. **Sanitize user-derived values in commit messages** — task titles and descriptions may
   contain shell metacharacters (backticks, `$(...)`, double quotes). **Mandatory pattern:**
   write the commit message to a temporary file and use `git commit -F`:
   ```bash
   COMMIT_MSG_FILE=$(mktemp)
   printf '%s' "chore(tasks): $OPERATION" > "$COMMIT_MSG_FILE"
   git commit -F "$COMMIT_MSG_FILE"
   rm -f "$COMMIT_MSG_FILE"
   ```
   This avoids all shell expansion issues. If using `-m` directly, sanitize with:
   `SAFE_VALUE=$(printf '%s' "$VALUE" | tr -d '`$')` before interpolation.

Skills reference this as: "Follow shell safety guidelines — see AGENTS.md Protocol: Shell Safety Guidelines."


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


### Protocol: Terminal Identification

**Referenced by:** all stage agents (1-4), batch

After the task ID is identified and confirmed, set the terminal title to show the
current stage and task. This allows users running multiple agents in parallel terminals
to identify each terminal at a glance.

**Set title (after task ID is known):**

```bash
printf '\033]0;optimus: %s | %s — %s\007' "<stage-name>" "$TASK_ID" "$TASK_TITLE"
```

Example output in terminal tab: `optimus: check | T-003 — User Auth JWT`

**Restore title (at stage completion or exit):**

```bash
printf '\033]0;\007'
```

**NOTE:** This uses the standard OSC (Operating System Command) escape sequence
supported by iTerm2, Terminal.app, VS Code terminal, tmux, and most modern terminals.
The sequence is silent — it produces no visible output.

Skills reference this as: "Set terminal title — see AGENTS.md Protocol: Terminal Identification."


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
