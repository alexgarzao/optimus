---
name: optimus-batch
description: "Chains stages 1-5 for one or more tasks sequentially. Instead of invoking each stage manually, the user specifies which tasks and stages to run, and this skill orchestrates the pipeline with user checkpoints between stages."
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
      7. Checkpoint -- user chooses stage-4 or skip to stage-5
      8. Run stage-5 (close)
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

Chains stages 1-5 for one or more tasks with user checkpoints between stages.

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
2. **Which stages:** "all" (1-5), specific range ("stages 1-3"), or "from current" (resume from task's current status)

If the user said "all ready tasks", scan for tasks with status `Pendente` and all
dependencies `DONE`. Prioritize by version (`Ativa` first), then priority, then ID.

### Step 1.3: Validate Eligibility

For each task:
1. Check that the task's status allows the requested starting stage
   - **Exclude tasks with status `Cancelado`** — cancelled tasks cannot be processed through the pipeline
2. Check that all dependencies are `DONE`
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
| 1 | T-003 | User auth | Pendente | Stage 1 | Stage 5 |
| 2 | T-004 | Login page | Pendente | Stage 1 | Stage 5 |
| 3 | T-005 | E2E tests | Pendente | Stage 1 | Stage 5 |

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

**Before invoking stages 2-5 for a task**, the orchestrator MUST:
1. Check if the task has a worktree (from stage-1 output or `branch` field in state.json)
2. If worktree exists, switch to it: `cd <worktree-path>`
3. Verify the correct branch is checked out: `git branch --show-current`
4. Only then invoke the stage skill

**After completing all stages for a task**, return to the original directory before
starting the next task.

---

## Phase 2: Execute Pipeline

For each task in the execution order:

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
| 4 (optional) | `optimus-pr-check` | "review PR for T-XXX" (via Skill tool) | Revisando PR |
| 5 | `optimus-done` | "close T-XXX" (via Skill tool) | DONE |

**Worktree context switch:** Before invoking stages 2-5, switch to the task's worktree
directory (from Step 1.5 tracking). Stage-1 may create the worktree — capture its output
path and record it in the tracking map.

Each stage skill handles its own validation, status changes, and user interactions.
The batch orchestrator does NOT duplicate any stage logic — it only chains them and
manages worktree context.

### Step 2.2: Checkpoint Between Stages

After each stage completes, present a checkpoint via `AskUser`:

```
Stage X completed for T-NNN: [title]
  Status: <current status>
  
What's next?
```

Options:
- **Continue to Stage X+1** — proceed with the next stage
- **Skip to Stage 5 (close)** — skip remaining stages and close
- **Stop here** — pause the batch, user will resume later
- **Skip Stage 4 (PR review)** — go directly from Stage 3 to Stage 5

**BLOCKING:** Do NOT advance to the next stage without user approval.

**If stage-4 (PR review):** Always ask whether to include it:
```
Stage 3 (impl review) completed. Stage 4 (PR review) is optional.
```
Options:
- **Run Stage 4** — review PR comments from Codacy/DeepSource/CodeRabbit/humans
- **Skip to Stage 5** — go directly to close

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

1. Re-read `tasks.md` to get current statuses
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

After all tasks are processed (or the user stops):

```markdown
## Batch Execution Summary

### Completed
| # | Task | Title | Final Status | Stages Run |
|---|------|-------|-------------|------------|
| 1 | T-003 | User auth | DONE | 1-5 |
| 2 | T-004 | Login page | DONE | 1-3, 5 |

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
  On next invocation, if this file exists, offer to resume from where it stopped.
- Stage 4 (PR review) is always offered as optional, never forced
- Respect dependency order — never process a task before its dependencies are DONE
- Each stage creates its own commits — the batch orchestrator does NOT commit anything
