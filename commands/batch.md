---
description: Chains stages 1-4 for one or more tasks sequentially. Instead of invoking each stage manually, the user specifies which tasks and stages to run, and this skill orchestrates the pipeline with user checkpoints between stages.
---

# Batch Pipeline Executor

Chains stages 1-4 for one or more tasks with user checkpoints between stages.

**Classification:** Administrative skill — orchestrates execution stages, delegates workspace creation and code modification to stage skills.

---

## Phase 1: Plan the Batch

### Step 1.0: Verify GitHub CLI (HARD BLOCK)

**HARD BLOCK:** Verify GitHub CLI — see AGENTS.md Protocol: GitHub CLI Check.

### Step 1.1: Resolve and Validate optimus-tasks.md

1. **Find optimus-tasks.md:** Resolve the path using the AGENTS.md Protocol: optimus-tasks.md Validation.
2. **Validate format:** First line must be `<!-- optimus:tasks-v1 -->`. Full format validation.

If validation fails, **STOP** and suggest `/optimus:import`.

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
2. Check that all dependencies are `DONE` (read Depends from optimus-tasks.md, status for each dependency from state.json — collect them into a `DEP_STATUSES` array)
3. **Check all-deps-cancelled** — see AGENTS.md Protocol: All-Dependencies-Cancelled Resolution.
4. If any task is blocked, report it and exclude from the batch

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
  "T-003": {"worktree": "<repo>/.worktrees/feat/t-003-user-auth", "branch": "feat/t-003-user-auth"},
  "T-004": {"worktree": "<repo>/.worktrees/feat/t-004-login-page", "branch": "feat/t-004-login-page"}
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
  {"tasks": ["T-003", "T-004", "T-005"], "completed": ["T-003"], "current": "T-004", "current_stage": 3, "worktrees": {"T-003": "<repo>/.worktrees/feat/t-003-user-auth", "T-004": "<repo>/.worktrees/feat/t-004-login-page"}}
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

### File Location (summarized)

> **Summary inlined here. Full recipe at `AGENTS.md -> File Location`.**

**Summary:** Defines where Optimus operational files live: `${MAIN_WORKTREE}/.optimus/{state.json, stats.json, sessions/, reports/, logs/}` (gitignored, per-user) vs `<tasksDir>/optimus:tasks.md` + `<tasksDir>/{tasks,subtasks}/` (versioned, project-team-shared, propagated by git). Also: `${MAIN_WORKTREE}/.gitignore` (versioned), `${MAIN_WORKTREE}/.worktrees/` (gitignored linked-worktree dir). Critical contract: `.optimus/*` paths NEVER propagate across linked worktrees (gitignored = not shared by `git worktree add`); use `${MAIN_WORKTREE}/` prefix consistently. See full table in AGENTS.md.

Optimus splits its files into two trees:

### Valid Status Values (stored in state.json) (summarized)

> **Summary inlined here. Full recipe at `AGENTS.md -> Valid Status Values (stored in state.json)`.**

**Summary:** state.json status values: `Pendente` (implicit, no entry), `Validando Spec` (plan), `Em Andamento` (build), `Validando Impl` (review), `DONE` (done), `Cancelado` (tasks/done). Administrative ops (Reopen, Advance, Demote, Cancel) require explicit user confirmation. See full table + transitions in AGENTS.md.

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

### Format Validation (summarized)

> **Summary inlined here. Full recipe at `AGENTS.md -> Format Validation`.**

**Summary:** 15-rule validation for `<tasksDir>/optimus:tasks.md` enforced at Step 1.0.1 of every stage agent (1-4): format marker `<!-- optimus:tasks-v1 -->` present; `## Versions` table with valid columns; all Version Status values valid (`Ativa`/`Próxima`/`Planejada`/`Backlog`/`Concluída`); exactly one `Ativa`, at most one `Próxima`; tasks table columns correct (Status/Branch live in state.json, NOT here); IDs match `T-NNN`; Tipo ∈ {Feature, Fix, Refactor, Chore, Docs, Test}; Priority ∈ {Alta, Media, Baixa}; Depends resolves to existing task rows; Version cells reference existing version rows; no duplicate IDs; no circular dependencies; no unescaped pipes; empty-table guard. HARD BLOCK on any failure — STOP and suggest `/optimus:import`. See full 15-item enumeration in AGENTS.md.

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
running `/optimus:import` to fix the format. Do NOT attempt to interpret malformed data.

14. No unescaped pipe characters (`|`) in task titles (breaks markdown table parsing)
15. **Empty table handling:** If the tasks table exists but has zero data rows (only headers),
format validation PASSES. Stage agents (1-4) MUST check for this condition immediately after
format validation and before task identification. If zero data rows: **STOP** and inform the
user: "No tasks found in optimus-tasks.md. Use `/optimus:tasks` to create a task or `/optimus:import`
to import from Ring pre-dev." Do NOT proceed to task identification with an empty table.

### Protocol: Resolve Tasks Git Scope (summarized)

> **Summary inlined here. Full recipe at `AGENTS.md -> Protocol: Resolve Tasks Git Scope`.**

**Summary:** Resolves `TASKS_DIR` (from `.optimus/config.json` `tasksDir` key, default `docs/pre-dev`) and `TASKS_FILE` (`<tasksDir>/optimus:tasks.md`), then detects whether tasksDir lives inside the project repo (`same-repo`) or a separate git repo (`separate-repo`). Sets `TASKS_REPO_ROOT`, `TASKS_GIT_REL`, `TASKS_DEFAULT_BRANCH`, and exposes a `tasks_git()` helper that wraps `git -C "$TASKS_DIR"` in separate-repo mode. Hard guards: reject `tasksDir` starting with `-` (git-option injection), require `python3` for separate-repo path computation, validate `TASKS_DEFAULT_BRANCH` against `^[a-zA-Z0-9._/-]+$`. Skills MUST use `tasks_git` (never raw `git`) on `$TASKS_FILE`. See full recipe in AGENTS.md.

### Protocol: Resolve Main Worktree Path (summarized)

> **Summary inlined here. Full recipe at `AGENTS.md -> Protocol: Resolve Main Worktree Path`.**

**Summary:** Resolve `MAIN_WORKTREE` once via `git worktree list --porcelain | awk '/^worktree / {print $2; exit}'` with `${MAIN_WORKTREE:?…}` defensive guard. Use `${MAIN_WORKTREE}/.optimus/...` for ALL `.optimus/` paths (gitignored, so doesn't propagate across linked worktrees). See full recipe in AGENTS.md.

### Protocol: All-Dependencies-Cancelled Resolution (summarized)

> **Summary inlined here. Full recipe at `AGENTS.md -> Protocol: All-Dependencies-Cancelled Resolution`.**

**Summary:** When every dependency in a task's `Depends:` column has status `Cancelado`, emit a multi-option resolution message AFTER the per-dep status check loop populates the `DEP_STATUSES` array. Recipe: iterate `DEP_STATUSES`, set `ALL_CANCELLED=true` if every entry equals `Cancelado`; when `ALL_CANCELLED=true` AND the array is non-empty, print three options to stderr — (a) remove all dependencies, (b) replace with alternative task IDs, (c) cancel the task itself — each with the corresponding `/optimus:tasks` invocation, then `exit 1`. If the array is empty or any dep is non-Cancelado, fall through to per-dep error. Variable contract: `DEP_STATUSES` is the canonical name; adapt if existing skill code uses another. See full recipe in AGENTS.md.

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


### Protocol: State Management (summarized)

> **Summary inlined here. Full recipe at `AGENTS.md -> Protocol: State Management`.**

**Summary:** Read/write/delete entries in `${MAIN_WORKTREE}/.optimus/state.json` with `jq`. Schema: `{task_id: {status, branch, updated_at}}`. Status values: `Pendente | Validando Spec | Em Andamento | Validando Impl | DONE | Cancelado`. All writes use `jq --arg id "$TASK_ID" --arg status "$NEW_STATUS" '.[$id] = {...}'` (injection-safe), with a tmp-file + `jq empty` validation step before `mv` to guarantee atomicity. Cancelado entries keep `branch: ""` (empty string, NOT absent — readers must treat both as Cancelado-state). Corrupted state.json is removed and treated as empty (reconciliation via worktree scan). state.json is gitignored; never committed. See full recipe in AGENTS.md for jq templates and reconciliation steps.

### Protocol: Terminal Identification (summarized)

> **Summary inlined here. Full recipe at `AGENTS.md -> Protocol: Terminal Identification`.**

**Summary:** `_optimus_set_title <text>` updates the terminal title for iTerm2-on-macOS via AppleScript (`osascript ... set name of s to newName`) — the only channel that reliably mutates `session.name` in "divorced" iTerm2 sessions where OSC 0/1/2 and SetUserVar are ineffective. Used by stage skills to surface task context (e.g., `optimus: PLAN T-007 — User auth`) so users running multiple Optimus sessions can identify them at a glance. The function is auto-inlined into 6 SKILLs by `inline-protocols.py` (do NOT manually paste the body in SKILL.md — F12f rule). Title is informational; failure to set it is non-fatal (silent no-op outside iTerm2/macOS, in Docker/CI without TTY, or when osascript denied). See full bash function in AGENTS.md.

### Protocol: optimus-tasks.md Validation (HARD BLOCK) (summarized)

> **Summary inlined here. Full recipe at `AGENTS.md -> Protocol: optimus-tasks.md Validation (HARD BLOCK)`.**

**Summary:** At Step 1.0.1 of every stage agent: (1) resolve paths via Protocol: Resolve Tasks Git Scope; (2) check `TASKS_FILE` exists, else STOP and suggest `/optimus:import`; (3) run all 15 Format Validation rules, else STOP and suggest `/optimus:import`. HARD BLOCK on any failure. All subsequent skill steps use the resolved `TASKS_FILE` and `tasks_git` helper. See full enumeration in AGENTS.md.

<!-- INLINE-PROTOCOLS:END -->
