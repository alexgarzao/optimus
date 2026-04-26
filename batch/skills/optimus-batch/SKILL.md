---
name: optimus-batch
description: "Chains stages 1-4 for one or more tasks sequentially. Instead of invoking each stage manually, the user specifies which tasks and stages to run, and this skill orchestrates the pipeline with user checkpoints between stages."
trigger: >
  - When user says "run all stages for T-003"
  - When user says "process T-003 through T-006"
  - When user says "batch execute", "run pipeline", "full cycle"
skip_when: >
  - User wants to run a single specific stage (use that stage directly)
  - No optimus-tasks.md exists
prerequisite: >
  - optimus-tasks.md exists in valid optimus format
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
    - optimus-review
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

### Step 1.1: Resolve and Validate optimus-tasks.md

1. **Rename check:** Check tasks.md → optimus-tasks.md rename — see AGENTS.md Protocol: Rename tasks.md to optimus-tasks.md.
2. **Find optimus-tasks.md:** Resolve the path using the AGENTS.md Protocol: optimus-tasks.md Validation.
3. **Validate format:** First line must be `<!-- optimus:tasks-v1 -->`. Full format validation.

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
2. Check that all dependencies are `DONE` (read Depends from optimus-tasks.md, status for each dependency from state.json)
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

Set terminal title — see AGENTS.md Protocol: Terminal Identification. Use stage=`BATCH` and include the current task ID in the title (e.g., `optimus: BATCH T-003 — User Auth JWT`). Update the title each time the task changes.

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
| 3 | `optimus-review` | "validate T-XXX" (via Skill tool) | Validando Impl |
| 4 | `optimus-done` | "close T-XXX" (via Skill tool) | DONE |

**Worktree context switch:** Before invoking stages 2-4, switch to the task's worktree
directory (from Step 1.5 tracking). Stage-1 may create the worktree — capture its output
path and record it in the tracking map.

Each stage skill handles its own validation, status changes, and user interactions.
The batch orchestrator does NOT duplicate any stage logic — it only chains them and
manages worktree context.

**Re-run Guard:** If plan or review presents a Re-run Guard prompt during batch execution,
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

1. Re-read `optimus-tasks.md` for structural data and `state.json` for current statuses
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

After all tasks are processed (or the user stops), restore the terminal title via `_optimus_set_title ""` (see Protocol: Terminal Identification for the function definition):

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

Optimus splits its files into two trees:

**Operational tree (`.optimus/`) — 100% gitignored, per-user/per-machine:**

```
.optimus/
├── config.json          # gitignored — optional overrides (tasksDir, defaultScope)
├── state.json           # gitignored — operational state (status, branch per task)
├── stats.json           # gitignored — stage execution counters per task
├── sessions/            # gitignored — session state for crash recovery
└── reports/             # gitignored — exported reports
```

**Planning tree (`<tasksDir>/`) — versioned, shared with the team:**

```
<tasksDir>/              # default: docs/pre-dev/
├── optimus-tasks.md     # versioned — structural task data (NO status, NO branch)
├── tasks/               # versioned — Ring pre-dev task specs (task_001.md, ...)
└── subtasks/            # versioned — Ring pre-dev subtask specs (T-001/, ...)
```

**Configuration** (optional) is stored in `.optimus/config.json`:

```json
{
  "tasksDir": "docs/pre-dev",
  "defaultScope": "ativa"
}
```

- **`tasksDir`** (optional): Path to the Ring pre-dev artifacts root. Default:
  `docs/pre-dev`. The import and stage agents look for `optimus-tasks.md`, `tasks/`, and
  `subtasks/` inside this directory. Can point to a path inside the project repo
  (default case) OR to a path in a separate git repo (for teams that separate task
  tracking from code).
- **`defaultScope`** (optional): Default version scope used by `report` and `quick-report`
  when the user does not specify one in the invocation. Valid values: `ativa`, `upcoming`,
  `all`, or a specific version name (must exist in the Versions table). When set, skills
  skip the "Which version scope do you want to see?" prompt. See Protocol: Default Scope
  Resolution.

Since `config.json` is gitignored, it exists ONLY when the user overrides a default.
Projects using the defaults do not need a `config.json`.

**Tasks file** is always at `<tasksDir>/optimus-tasks.md` (derived from `tasksDir`).

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
- Stage agents read and write this file — never optimus-tasks.md — for status changes.
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
1. **Read `.optimus/config.json`** for `tasksDir` if it exists. Fallback: `docs/pre-dev`.
2. **Tasks file:** `${tasksDir}/optimus-tasks.md` (derived, not configurable separately).
3. **If `<tasksDir>/optimus-tasks.md` not found:** **STOP** and suggest running `import` to create one.

Everything inside `.optimus/` is gitignored. The planning tree (`<tasksDir>/optimus-tasks.md`,
`<tasksDir>/tasks/`, `<tasksDir>/subtasks/`) is versioned (structural data shared with
the team) — but the repo that versions it depends on `tasksDir`: if `tasksDir` is inside
the project repo, it is committed alongside the code; if `tasksDir` is in a separate
repo, it is committed there.


### Valid Status Values (stored in state.json)

Status lives in `.optimus/state.json`, NOT in optimus-tasks.md. A task with no entry in
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

Every stage agent (1-4) MUST validate the optimus-tasks.md format before operating:
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
user: "No tasks found in optimus-tasks.md. Use `/optimus-tasks` to create a task or `/optimus-import`
to import from Ring pre-dev." Do NOT proceed to task identification with an empty table.

**NOTE:** For circular dependency detection (item 13), trace the full dependency chain for
each task. If any task appears twice in the chain, a cycle exists. Report ALL tasks involved
in the cycle so the user can fix it with `/optimus-tasks`.


### Protocol: Resolve Tasks Git Scope

**Referenced by:** all stage agents (1-4), tasks, batch, resolve, import, resume, report, quick-report

Resolves `TASKS_DIR` (Ring pre-dev root) and `TASKS_FILE` (`<tasksDir>/optimus-tasks.md`), then
detects whether `tasksDir` lives in the same git repo as the project code or in a
**separate** git repo. Exposes a `tasks_git` helper function so skills can run git
commands on optimus-tasks.md uniformly regardless of scope.

```bash
# Step 0: Resolve main worktree — see AGENTS.md Protocol: Resolve Main Worktree Path.
# Required because .optimus/config.json is gitignored and lives only in the main
# worktree's filesystem; resolving it relative to PWD would miss it from a linked
# worktree.
MAIN_WORKTREE="$(git worktree list --porcelain 2>/dev/null | awk '/^worktree / {print $2; exit}')"
if [ -z "$MAIN_WORKTREE" ]; then
  echo "ERROR: Cannot determine main worktree — not in a git repository." >&2
  exit 1
fi
# Step 1: Resolve tasksDir from config.json (if present) or fall back to default.
CONFIG_FILE="${MAIN_WORKTREE}/.optimus/config.json"
if [ -f "$CONFIG_FILE" ] && jq empty "$CONFIG_FILE" 2>/dev/null; then
  TASKS_DIR=$(jq -r '.tasksDir // "docs/pre-dev"' "$CONFIG_FILE")
else
  TASKS_DIR="docs/pre-dev"
fi
# Reject "null" (jq -r prints literal "null" for JSON null) or empty string.
case "$TASKS_DIR" in
  ""|"null") TASKS_DIR="docs/pre-dev" ;;
esac
# Security: reject TASKS_DIR values starting with "-" (git option injection via
# `git -C --exec-path=...` or similar). Trust boundary: config.json is now gitignored,
# but a user could still receive a malicious config via Slack/email.
case "$TASKS_DIR" in
  -*)
    echo "ERROR: tasksDir cannot start with '-' (security)." >&2
    exit 1
    ;;
esac

# Step 2: Derive TASKS_FILE.
TASKS_FILE="${TASKS_DIR}/optimus-tasks.md"

# Step 3: Detect git scope.
PROJECT_ROOT=$(git rev-parse --show-toplevel 2>/dev/null)
if [ -z "$PROJECT_ROOT" ]; then
  echo "ERROR: Not inside a git repository — optimus requires git." >&2
  exit 1
fi

TASKS_REPO_ROOT=""
if [ -d "$TASKS_DIR" ]; then
  TASKS_REPO_ROOT=$(git -C "$TASKS_DIR" rev-parse --show-toplevel 2>/dev/null || echo "")
fi

if [ -z "$TASKS_REPO_ROOT" ]; then
  if [ -d "$TASKS_DIR" ]; then
    # Directory exists but is NOT inside a git repository — this is a
    # misconfiguration. Without this guard, operations would silently target
    # the project repo and fail confusingly.
    echo "ERROR: tasksDir '$TASKS_DIR' exists but is not inside a git repository." >&2
    echo "Options:" >&2
    echo "  1. Initialize git in tasksDir: git -C \"$TASKS_DIR\" init" >&2
    echo "  2. Point tasksDir to an existing git repo." >&2
    echo "  3. Remove tasksDir to let optimus create it inside the project repo." >&2
    exit 1
  fi
  # Fresh project: tasksDir does not exist yet — assume same-repo.
  # Skills that create optimus-tasks.md will mkdir -p "$TASKS_DIR" first.
  TASKS_GIT_SCOPE="same-repo"
elif [ "$TASKS_REPO_ROOT" = "$PROJECT_ROOT" ]; then
  TASKS_GIT_SCOPE="same-repo"
else
  TASKS_GIT_SCOPE="separate-repo"
fi

# Step 4: Compute the path to pass to git commands.
# In same-repo, git runs from project root and we pass TASKS_FILE as is.
# In separate-repo, git runs with -C "$TASKS_DIR" so paths are relative to TASKS_DIR.
if [ "$TASKS_GIT_SCOPE" = "separate-repo" ]; then
  # python3 is REQUIRED in separate-repo mode to compute the path from the tasks
  # repo root. A naive "optimus-tasks.md" fallback would be wrong when TASKS_DIR is a
  # subdir of the tasks repo (e.g., `tasks-repo/project-alfa/`), because
  # `git show origin/main:optimus-tasks.md` resolves from repo root, not CWD.
  if ! command -v python3 >/dev/null 2>&1; then
    echo "ERROR: python3 is required for separate-repo mode (path computation)." >&2
    echo "Install python3 or point tasksDir inside the project repo." >&2
    exit 1
  fi
  TASKS_GIT_REL=$(python3 -c "import os,sys; print(os.path.relpath(sys.argv[1], sys.argv[2]))" \
    "$TASKS_FILE" "$TASKS_REPO_ROOT" 2>/dev/null)
  if [ -z "$TASKS_GIT_REL" ]; then
    echo "ERROR: Failed to compute TASKS_GIT_REL for '$TASKS_FILE' relative to '$TASKS_REPO_ROOT'." >&2
    exit 1
  fi
else
  TASKS_GIT_REL="$TASKS_FILE"
fi

# Step 5: Resolve the tasks repo's default branch once (used by tasks_git
# operations that reference origin/$DEFAULT). This is DIFFERENT from
# $DEFAULT_BRANCH (the project repo's default).
if [ "$TASKS_GIT_SCOPE" = "separate-repo" ]; then
  TASKS_DEFAULT_BRANCH=$(git -C "$TASKS_DIR" symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's@^refs/remotes/origin/@@')
  if [ -z "$TASKS_DEFAULT_BRANCH" ]; then
    # Fallback: check origin/main vs origin/master existence (deterministic,
    # unlike `git branch --list main master` which can return either arbitrarily).
    if git -C "$TASKS_DIR" show-ref --verify refs/remotes/origin/main >/dev/null 2>&1; then
      TASKS_DEFAULT_BRANCH="main"
    elif git -C "$TASKS_DIR" show-ref --verify refs/remotes/origin/master >/dev/null 2>&1; then
      TASKS_DEFAULT_BRANCH="master"
    fi
  fi
else
  TASKS_DEFAULT_BRANCH=$(git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's@^refs/remotes/origin/@@')
  if [ -z "$TASKS_DEFAULT_BRANCH" ]; then
    if git show-ref --verify refs/remotes/origin/main >/dev/null 2>&1; then
      TASKS_DEFAULT_BRANCH="main"
    elif git show-ref --verify refs/remotes/origin/master >/dev/null 2>&1; then
      TASKS_DEFAULT_BRANCH="master"
    fi
  fi
fi

# Security: reject malformed branch names (prevents injection via
# `git diff origin/<weird>`).
if [ -n "$TASKS_DEFAULT_BRANCH" ] && ! [[ "$TASKS_DEFAULT_BRANCH" =~ ^[a-zA-Z0-9._/-]+$ ]]; then
  echo "ERROR: Invalid TASKS_DEFAULT_BRANCH format: '$TASKS_DEFAULT_BRANCH'" >&2
  exit 1
fi

# Step 6: Define the tasks_git helper.
tasks_git() {
  if [ "$TASKS_GIT_SCOPE" = "separate-repo" ]; then
    git -C "$TASKS_DIR" "$@"
  else
    git "$@"
  fi
}
```

**Usage:**
```bash
tasks_git add "$TASKS_GIT_REL"
tasks_git commit -F "$COMMIT_MSG_FILE"
# IMPORTANT: use $TASKS_DEFAULT_BRANCH (tasks repo default) — NOT $DEFAULT_BRANCH
# (project repo default). They are the same in same-repo mode but may differ in
# separate-repo mode (e.g., tasks repo is `master`, project repo is `main`).
tasks_git diff "origin/$TASKS_DEFAULT_BRANCH" -- "$TASKS_GIT_REL"
tasks_git show "origin/$TASKS_DEFAULT_BRANCH:$TASKS_GIT_REL"
```

**Rule:** Skills MUST use `tasks_git` (never raw `git`) when operating on `$TASKS_FILE`.
Raw `git` on `$TASKS_FILE` breaks in separate-repo mode.

**Rule:** When committing in separate-repo mode, commits land in the tasks repo (not the
project repo). `tasks_git push` pushes the tasks repo. The project repo is unaffected.

Skills reference this as: "Resolve tasks git scope — see AGENTS.md Protocol: Resolve Tasks Git Scope."


### Protocol: Resolve Main Worktree Path

**Referenced by:** all skills that read or write `.optimus/` operational files (state.json, stats.json, sessions, reports, logs, and checkpoint markers).

**Why:** `.optimus/` is gitignored. Git does NOT propagate ignored files across linked worktrees (`git worktree add` creates a sibling working tree but does not share gitignored files). When a skill runs from a linked worktree (the common case for `/optimus-build`, `/optimus-review`, `/optimus-done` which default to the task's worktree), reads and writes against `.optimus/state.json` resolve to the worktree's isolated copy. Updates never reach the main worktree. When the linked worktree is later removed (e.g., by `/optimus-done` cleanup), the writes are lost — silent data loss.

**Recipe:**

```bash
MAIN_WORKTREE="$(git worktree list --porcelain 2>/dev/null | awk '/^worktree / {print $2; exit}')"
if [ -z "$MAIN_WORKTREE" ]; then
  echo "ERROR: Cannot determine main worktree — not in a git repository." >&2
  exit 1
fi
```

The first `worktree` line in `git worktree list --porcelain` is always the main worktree (where the bare `.git/` directory or the repo's HEAD lives), regardless of where the command is run from.

**Path resolution pattern:**

After resolving `MAIN_WORKTREE`, every `.optimus/` path MUST be prefixed:

```bash
# RIGHT (works from any worktree):
STATE_FILE="${MAIN_WORKTREE}/.optimus/state.json"
SESSION_FILE="${MAIN_WORKTREE}/.optimus/sessions/session-${TASK_ID}.json"
STATS_FILE="${MAIN_WORKTREE}/.optimus/stats.json"
mkdir -p "${MAIN_WORKTREE}/.optimus/sessions" \
         "${MAIN_WORKTREE}/.optimus/reports" \
         "${MAIN_WORKTREE}/.optimus/logs"

# WRONG (resolves against PWD, breaks in linked worktrees):
STATE_FILE=".optimus/state.json"
SESSION_FILE=".optimus/sessions/session-${TASK_ID}.json"
STATS_FILE=".optimus/stats.json"
mkdir -p .optimus/sessions .optimus/reports .optimus/logs
```

**What does NOT need this protocol:**

- `<tasksDir>/optimus-tasks.md` and `<tasksDir>/tasks/`, `<tasksDir>/subtasks/` — versioned content, propagated by git across worktrees automatically.
- `.optimus/config.json` — when **versioned** (legacy projects), it propagates via git; when **gitignored** (current default), it suffers the same isolation as state.json. **Treat `.optimus/config.json` as gitignored and resolve via `$MAIN_WORKTREE` for safety in current projects** — the cost is a single `git worktree list` call.
- `.gitignore` itself — versioned, propagated via git.

**Idempotency:** the resolution is read-only against git metadata; safe to call multiple times in the same skill execution. Cache `MAIN_WORKTREE` in a local variable rather than re-running `git worktree list` for each path.

Skills reference this as: "Resolve main worktree — see AGENTS.md Protocol: Resolve Main Worktree Path."


### Protocol: GitHub CLI Check (HARD BLOCK)

**Referenced by:** all stage agents (1-4), tasks, batch

```bash
gh auth status 2>/dev/null
```

If this command fails (exit code != 0), **STOP** immediately:
```
GitHub CLI (gh) is not authenticated. Run `gh auth login` to authenticate before proceeding.
```


### Protocol: Rename tasks.md to optimus-tasks.md

**Referenced by:** import, tasks, plan, build, review, done, resume, report, quick-report, batch, resolve, pr-check

Detects and renames projects whose Optimus tracking file is at `<tasksDir>/tasks.md`
(the prior default name) to `<tasksDir>/optimus-tasks.md`. The format marker
(`<!-- optimus:tasks-v1 -->`) is unchanged — this protocol only renames the file on disk.

**Detection (run at the start of every skill that reads/writes the tasks tracking file
to detect and offer rename of `<tasksDir>/tasks.md` to `<tasksDir>/optimus-tasks.md`):**

```bash
# Requires Protocol: Resolve Tasks Git Scope to have been executed first
# (TASKS_DIR, TASKS_FILE, TASKS_GIT_SCOPE, TASKS_GIT_REL, tasks_git available).
# TASKS_FILE already points to <tasksDir>/optimus-tasks.md.
OLD_TASKS_FILE="${TASKS_DIR}/tasks.md"
NEEDS_RENAME=0

# Symlink HARD BLOCK — refuse to inspect or operate on symlinked paths.
# Must run BEFORE detection (head -n 1 follows symlinks).
if [ -L "$OLD_TASKS_FILE" ] || [ -L "$TASKS_FILE" ]; then
  echo "ERROR: $OLD_TASKS_FILE or $TASKS_FILE is a symlink — refusing to inspect or rename." >&2
  exit 1
fi

if [ -f "$OLD_TASKS_FILE" ] && [ -f "$TASKS_FILE" ]; then
  if ! head -n 1 "$OLD_TASKS_FILE" 2>/dev/null | grep -q '^<!-- optimus:tasks-v1 -->'; then
    # OLD lacks the optimus marker — it is an unrelated file (Ring pre-dev's
    # Gate 7 tasks.md, etc.). The actual Optimus file is already at TASKS_FILE.
    NEEDS_RENAME=0
  else
    echo "ERROR: Both ${OLD_TASKS_FILE} and ${TASKS_FILE} exist and both appear to be Optimus tracking files." >&2
    echo "       Confirm which is current, remove the stale one, and re-run the skill." >&2
    exit 1
  fi
elif [ -f "$OLD_TASKS_FILE" ] && [ ! -f "$TASKS_FILE" ]; then
  # Only proceed if the legacy file actually has the optimus format marker — otherwise
  # it is some other unrelated tasks.md (e.g., Ring pre-dev's Gate 7 tasks.md) and
  # MUST NOT be touched.
  if head -n 1 "$OLD_TASKS_FILE" 2>/dev/null | grep -q '^<!-- optimus:tasks-v1 -->'; then
    NEEDS_RENAME=1
  fi
fi
```

If `NEEDS_RENAME=0`, the protocol is a no-op (either the new name already exists, the
legacy file is unrelated to optimus, or neither exists).

**Dry-run mode:** If the skill is running in dry-run (per Dry-Run Mode section above),
DO NOT execute the rename. Emit the plan and proceed:

```
[DRY-RUN] Rename would be offered for this task:
[DRY-RUN]   Old name: $OLD_TASKS_FILE
[DRY-RUN]   New name: $TASKS_FILE
[DRY-RUN]   Scope:    $TASKS_GIT_SCOPE
[DRY-RUN]   Would use: git mv (same-repo) OR tasks_git mv (separate-repo)
```

**If `NEEDS_RENAME=1`, ask the user via `AskUser`:**

```
The Optimus tracking file at $OLD_TASKS_FILE uses the previous default name.
Rename to $TASKS_FILE now? (Recommended — Ring pre-dev also produces a tasks.md
in this directory, so the previous name causes a collision.)
```

Options:
- **Rename now** — perform the rename and commit
- **Skip this time** — continue with the legacy name (emit warning; this will collide with Ring pre-dev)
- **Abort** — stop the current command so you can rename manually

**Rename flow (when user chooses "Rename now"):**

Checkpoint file: write `${MAIN_WORKTREE}/.optimus/.rename-in-progress` BEFORE starting.
This marker lets subsequent invocations detect interrupted renames:

```bash
# Requires Protocol: Resolve Main Worktree Path to have run first
# (or resolve inline; see that protocol).
MAIN_WORKTREE="$(git worktree list --porcelain 2>/dev/null | awk '/^worktree / {print $2; exit}')"
mkdir -p "${MAIN_WORKTREE}/.optimus"
printf '%s\n' "$TASKS_FILE" > "${MAIN_WORKTREE}/.optimus/.rename-in-progress"
```

**Scope-branched rename:** explicit `if` so the agent executes the correct branch:

```bash
if [ "$TASKS_GIT_SCOPE" = "same-repo" ]; then
  # Same-repo: atomic git mv in a single commit (preserves history via rename-detect).
  if ! git mv "$OLD_TASKS_FILE" "$TASKS_FILE"; then
    echo "ERROR: git mv failed. Rename aborted — no changes made." >&2
    rm -f "${MAIN_WORKTREE}/.optimus/.rename-in-progress"
    exit 1
  fi
  COMMIT_MSG_FILE=$(mktemp -t optimus.XXXXXX) || { echo "ERROR: mktemp failed" >&2; exit 1; }
  chmod 600 "$COMMIT_MSG_FILE"
  printf '%s' "chore(tasks): rename tasks.md to optimus-tasks.md" > "$COMMIT_MSG_FILE"
  if ! git commit -F "$COMMIT_MSG_FILE"; then
    echo "ERROR: Commit failed. Reverting git mv..." >&2
    # Revert: restore old name from HEAD, remove new name from working tree
    git reset HEAD -- "$OLD_TASKS_FILE" "$TASKS_FILE" 2>/dev/null
    git checkout HEAD -- "$OLD_TASKS_FILE" 2>/dev/null
    rm -f "$TASKS_FILE"
    rm -f "$COMMIT_MSG_FILE" "${MAIN_WORKTREE}/.optimus/.rename-in-progress"
    exit 1
  fi
  rm -f "$COMMIT_MSG_FILE"
else
  # Separate-repo: rename via tasks_git mv, single commit in tasks repo.
  OLD_TASKS_GIT_REL=$(python3 -c "import os,sys; print(os.path.relpath(sys.argv[1], sys.argv[2]))" \
    "$OLD_TASKS_FILE" "$TASKS_REPO_ROOT" 2>/dev/null)
  if [ -z "$OLD_TASKS_GIT_REL" ]; then
    echo "ERROR: Failed to compute path for legacy file relative to tasks repo." >&2
    rm -f "${MAIN_WORKTREE}/.optimus/.rename-in-progress"
    exit 1
  fi
  if ! tasks_git mv "$OLD_TASKS_GIT_REL" "$TASKS_GIT_REL"; then
    echo "ERROR: tasks_git mv failed. Rename aborted — no changes made." >&2
    rm -f "${MAIN_WORKTREE}/.optimus/.rename-in-progress"
    exit 1
  fi
  COMMIT_MSG_FILE=$(mktemp -t optimus.XXXXXX) || { echo "ERROR: mktemp failed" >&2; exit 1; }
  chmod 600 "$COMMIT_MSG_FILE"
  printf '%s' "chore(tasks): rename tasks.md to optimus-tasks.md" > "$COMMIT_MSG_FILE"
  if ! tasks_git commit -F "$COMMIT_MSG_FILE"; then
    echo "ERROR: Commit failed in tasks repo. Manual cleanup needed:" >&2
    echo "  cd $TASKS_DIR && git reset HEAD -- $OLD_TASKS_GIT_REL $TASKS_GIT_REL" >&2
    echo "  git checkout HEAD -- $OLD_TASKS_GIT_REL && rm -f $TASKS_GIT_REL" >&2
    rm -f "$COMMIT_MSG_FILE" "${MAIN_WORKTREE}/.optimus/.rename-in-progress"
    exit 1
  fi
  rm -f "$COMMIT_MSG_FILE"
fi
```

**Rename success: clear checkpoint marker and log.**
```bash
rm -f "${MAIN_WORKTREE}/.optimus/.rename-in-progress"
echo "INFO: Rename completed successfully:" >&2
echo "  - Old name:  $OLD_TASKS_FILE" >&2
echo "  - New name:  $TASKS_FILE" >&2
echo "  - Git scope: $TASKS_GIT_SCOPE" >&2
```

**Post-rename validation:** Verify the moved file still passes Format Validation (see
AGENTS.md Format Validation section). If it fails (e.g., the legacy file was manually
edited and lost the marker), inform user and suggest running `/optimus-import` to rebuild:

```bash
# Post-rename validation — verify the moved file still passes Format Validation.
if ! grep -q '^<!-- optimus:tasks-v1 -->' "$TASKS_FILE"; then
  echo "WARNING: Renamed optimus-tasks.md does not have the optimus format marker." >&2
  echo "         Run /optimus-import to rebuild in the correct format." >&2
fi
if ! grep -q '^## Versions' "$TASKS_FILE"; then
  echo "WARNING: Renamed optimus-tasks.md has no ## Versions section." >&2
  echo "         Run /optimus-import to rebuild in the correct format." >&2
fi
```

**Report success:**
```
Rename complete. The tracking file is now at ${TASKS_FILE}.
Remember to push the tasks repo when you're ready.
```

**Interrupted rename recovery (on skill startup):**

```bash
# Requires Protocol: Resolve Main Worktree Path to have run first
# (or resolve inline; see that protocol).
MAIN_WORKTREE="$(git worktree list --porcelain 2>/dev/null | awk '/^worktree / {print $2; exit}')"
if [ -f "${MAIN_WORKTREE}/.optimus/.rename-in-progress" ]; then
  INTERRUPTED_FILE=$(cat "${MAIN_WORKTREE}/.optimus/.rename-in-progress" 2>/dev/null)
  echo "WARNING: Previous rename was interrupted. Expected target: $INTERRUPTED_FILE" >&2
  # AskUser: Retry rename / Clear marker / Abort
fi
```

**If user chose "Skip this time":** Emit a warning and proceed using the legacy name
for this invocation only. The skill MUST use `$OLD_TASKS_FILE` as `$TASKS_FILE` for the
remainder of this execution.

**If user chose "Abort":** **STOP** the current command.

Skills reference this as: "Check optimus-tasks.md rename — see AGENTS.md Protocol: Rename tasks.md to optimus-tasks.md."


### Protocol: Shell Safety Guidelines

**Referenced by:** plan, batch

All bash examples in AGENTS.md and SKILL.md files are templates that agents execute literally.
Follow these rules to prevent injection and silent failures:

1. **Always quote variables:** Use `"$VAR"` not `$VAR` — especially for paths, branch names, and user-derived values
2. **Check exit codes for critical commands:**
   ```bash
   tasks_git add "$TASKS_GIT_REL"
   COMMIT_MSG_FILE=$(mktemp)
   printf '%s' "chore(tasks): $COMMIT_MSG" > "$COMMIT_MSG_FILE"
   if ! tasks_git commit -F "$COMMIT_MSG_FILE"; then
     echo "ERROR: git commit failed. Check pre-commit hooks or git config." >&2
     rm -f "$COMMIT_MSG_FILE"
     exit 1
   fi
   rm -f "$COMMIT_MSG_FILE"
   ```
3. **Never interpolate user-derived values directly into shell commands** — task titles,
   branch names, and other user input may contain shell metacharacters
4. **Use `grep -F` for fixed string matching** — never pass branch names or task IDs
   as regex patterns to `grep` without `-F`
5. **Use `grep -E '^\| T-NNN \|'`** to match task rows in optimus-tasks.md — plain `grep "T-NNN"`
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
  echo "ERROR: jq is required for state management but not installed." >&2
  exit 1
fi
```

**Reading state:**

```bash
# Requires Protocol: Resolve Main Worktree Path to have run first
# (or resolve inline; see that protocol).
MAIN_WORKTREE="$(git worktree list --porcelain 2>/dev/null | awk '/^worktree / {print $2; exit}')"
STATE_FILE="${MAIN_WORKTREE}/.optimus/state.json"
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
# Requires Protocol: Resolve Main Worktree Path to have run first
# (or resolve inline; see that protocol).
MAIN_WORKTREE="$(git worktree list --porcelain 2>/dev/null | awk '/^worktree / {print $2; exit}')"
# Initialize .optimus directory — see AGENTS.md Protocol: Initialize .optimus Directory.
STATE_FILE="${MAIN_WORKTREE}/.optimus/state.json"
if [ ! -f "$STATE_FILE" ]; then
  echo '{}' > "$STATE_FILE"
fi
if [ -z "$TASK_ID" ] || [ -z "$NEW_STATUS" ]; then
  echo "ERROR: Cannot write state — TASK_ID or NEW_STATUS is empty." >&2
  exit 1
fi
UPDATED_AT=$(date -u +%Y-%m-%dT%H:%M:%SZ)
if jq --arg id "$TASK_ID" --arg status "$NEW_STATUS" --arg branch "$BRANCH_NAME" --arg ts "$UPDATED_AT" \
  '.[$id] = {status: $status, branch: $branch, updated_at: $ts}' "$STATE_FILE" > "${STATE_FILE}.tmp"; then
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

**Removing entry (for Pendente reset):**

```bash
# Requires Protocol: Resolve Main Worktree Path to have run first
# (or resolve inline; see that protocol).
MAIN_WORKTREE="$(git worktree list --porcelain 2>/dev/null | awk '/^worktree / {print $2; exit}')"
STATE_FILE="${MAIN_WORKTREE}/.optimus/state.json"
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
# Requires Protocol: Resolve Main Worktree Path to have run first
# (or resolve inline; see that protocol).
MAIN_WORKTREE="$(git worktree list --porcelain 2>/dev/null | awk '/^worktree / {print $2; exit}')"
STATE_FILE="${MAIN_WORKTREE}/.optimus/state.json"
# TASKS_FILE is resolved via Protocol: Resolve Tasks Git Scope (<tasksDir>/optimus-tasks.md).
# Validate state.json if it exists
if [ -f "$STATE_FILE" ] && ! jq empty "$STATE_FILE" 2>/dev/null; then
  echo "WARNING: state.json is corrupted. Treating all tasks as Pendente."
  rm -f "$STATE_FILE"
fi
# Get all task IDs from optimus-tasks.md
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
_optimus_set_title() {
  # iTerm2 AppleScript title updater. Empirical testing showed that Optimus
  # tasks always run in "divorced" iTerm2 sessions where the profile's
  # autoNameFormat is locked to a literal — OSC 0/1/2 and OSC 1337
  # SetUserVar are both ineffective in that state, so AppleScript's
  # `set name of s` is the only channel that actually mutates session.name.
  # The Execute tool runs bash without a controlling TTY, so /dev/tty fails
  # with ENODEV; we resolve the parent process's TTY via ps instead. Walk
  # up to 4 ancestors in case of nested shells. First run triggers a macOS
  # TCC prompt ("droid wants to control iTerm"); approving enables this
  # permanently. Silent no-op outside macOS/iTerm2 or when osascript is
  # unavailable — non-iTerm2 / non-macOS users get no title update.
  local title="$1"
  local pid="$PPID" tty=""
  for _ in 1 2 3 4; do
    [ -z "$pid" ] || [ "$pid" = "1" ] && break
    tty=$(ps -o tty= -p "$pid" 2>/dev/null | tr -d ' ')
    case "$tty" in
      ""|"?"|"??") pid=$(ps -o ppid= -p "$pid" 2>/dev/null | tr -d ' ') ;;
      *) break ;;
    esac
  done
  if { [ "$LC_TERMINAL" = "iTerm2" ] || [ "$TERM_PROGRAM" = "iTerm.app" ]; } \
     && command -v osascript >/dev/null 2>&1 && [ -n "$tty" ] \
     && [ "$tty" != "?" ] && [ "$tty" != "??" ]; then
    osascript \
      -e 'on run argv' \
      -e '  set targetTty to "/dev/" & item 1 of argv' \
      -e '  set newName to item 2 of argv' \
      -e '  tell application "iTerm2"' \
      -e '    repeat with w in windows' \
      -e '      repeat with t in tabs of w' \
      -e '        repeat with s in sessions of t' \
      -e '          if (tty of s as string) is targetTty then' \
      -e '            try' \
      -e '              set name of s to newName' \
      -e '            end try' \
      -e '          end if' \
      -e '        end repeat' \
      -e '      end repeat' \
      -e '    end repeat' \
      -e '  end tell' \
      -e 'end run' \
      -- "$tty" "$title" >/dev/null 2>&1 || true
  fi
}
_optimus_set_title "optimus: <STAGE> $TASK_ID — $TASK_TITLE"
```

Example output in terminal tab: `optimus: REVIEW T-003 — User Auth JWT`

**Why the parent-process TTY:** The Execute tool runs `bash -c` without a controlling
terminal, so `/dev/tty` returns `ENODEV` ("Device not configured"). The resolver above
asks `ps` for the parent's controlling TTY device path and matches it against iTerm2's
session list via AppleScript — that device is connected to the user's real iTerm2
session. If no ancestor has a TTY (Docker/CI) or osascript is unavailable, the
function silently no-ops.

**Restore title (at stage completion or exit):**

```bash
_optimus_set_title ""
```

**NOTE:** This helper is iTerm2-on-macOS only. Optimus tasks always run in
"divorced" iTerm2 sessions, where AppleScript's `set name of s` is the only
channel that reliably mutates `session.name`. Non-iTerm2 / non-macOS users
will not see a title update.

**Troubleshooting iTerm2 (if the title still doesn't update):**

1. **Window > Edit Tab Title** must be empty. A manually-set tab title is
   sticky on the tab label and overrides the session name visually, even
   when `session.name` is updated correctly underneath.
2. The first run on macOS triggers a TCC prompt ("`droid` wants to control
   `iTerm`"). Approve it to enable the helper. Denying makes the helper a
   silent no-op.
3. The helper requires the parent process to have a controlling TTY. Inside
   Docker/CI without a TTY, no ancestor will resolve and the helper will
   silently no-op.

Skills reference this as: "Set terminal title — see AGENTS.md Protocol: Terminal Identification."


### Protocol: optimus-tasks.md Validation (HARD BLOCK)

**Referenced by:** all stage agents (1-4), tasks, batch. Note: resolve performs inline format validation in its own Step 4.2.

Every stage agent MUST validate optimus-tasks.md before operating. The full validation rules are
defined in the "Format Validation" section above (items 1-15). This protocol is the
executable version:

1. **Resolve paths and git scope:** Execute Protocol: Resolve Tasks Git Scope (below) to
   resolve `TASKS_DIR`, `TASKS_FILE`, `TASKS_GIT_SCOPE`, and the `tasks_git` helper.
2. **Find optimus-tasks.md:** Check if `TASKS_FILE` exists. If not found, **STOP** and suggest `/optimus-import`.
3. **Validate format:** Execute all 15 validation checks from the "Format Validation" section. If the format marker is missing or any check fails, **STOP** and suggest `/optimus-import`.

**All subsequent references to `optimus-tasks.md` in the skill use the resolved `TASKS_FILE` path.
All references to Ring pre-dev artifacts use `TASKS_DIR` as the root** — never hardcoded paths.
**All git operations on optimus-tasks.md use the `tasks_git` helper** (which handles both same-repo
and separate-repo scopes).

Skills reference this as: "Find and validate optimus-tasks.md (HARD BLOCK) — see AGENTS.md Protocol: optimus-tasks.md Validation."


<!-- INLINE-PROTOCOLS:END -->
