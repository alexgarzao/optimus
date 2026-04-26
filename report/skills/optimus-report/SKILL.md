---
name: optimus-report
description: "Task status dashboard. Reads optimus-tasks.md, computes dependency graph, and presents a comprehensive project status report. Shows progress, active tasks, blocked tasks, ready-to-start tasks, dependency graph, and parallelization opportunities. Read-only -- this agent NEVER modifies any files."
trigger: >
  - When user asks for project status (e.g., "show tasks", "project status", "what's ready?")
  - When user wants to know what can be parallelized
  - When user asks "what should I work on next?"
  - Before starting a new task (to see the full picture)
  - When user asks "quick status", "what am I working on?", "current task"
skip_when: >
  - No optimus-tasks.md exists in the project
  - User wants to run a specific stage agent (use that agent directly)
prerequisite: >
  - <tasksDir>/optimus-tasks.md exists in the project (default tasksDir: docs/pre-dev)
NOT_skip_when: >
  - "I already know the status" -- The dashboard shows dependencies and parallelization you might miss.
  - "There's only one task" -- Even single tasks benefit from status verification.
examples:
  - name: Full project status
    invocation: "Show project status"
    expected_flow: >
      1. Find and parse optimus-tasks.md
      2. Compute dependency graph
      3. Classify tasks (done, active, ready, blocked)
      4. Present dashboard with all sections
  - name: What to work on next
    invocation: "What can I work on next?"
    expected_flow: >
      1. Parse optimus-tasks.md
      2. Find tasks with status Pendente and all dependencies DONE
      3. Present ready-to-start tasks with priority ordering
  - name: Quick status check
    invocation: "Quick status" or "What am I working on?"
    expected_flow: >
      1. Parse optimus-tasks.md
      2. Show only: current active task, its progress status, and next-up
      3. Skip dependency graph, parallelization, velocity, and completed tasks
related:
  complementary:
    - optimus-plan
    - optimus-build
verification:
  manual:
    - Dashboard displays correctly
    - Dependency graph is accurate
    - Blocked tasks correctly identified
    - Parallelization opportunities are valid
---

# Task Status Dashboard

Read-only agent that parses `optimus-tasks.md` and presents a comprehensive project status report.

**CRITICAL:** This agent is effectively read-only. It may write ONLY to
`.optimus/config.json` (`defaultScope`) and to `.optimus/reports/` (exports), and only
when the user explicitly opts in. It never modifies `optimus-tasks.md`, `state.json`, code, or
any other project file.

---

## Phase 1: Find and Parse optimus-tasks.md

### Step 1.0: Resolve Paths and Git Scope

Execute AGENTS.md Protocol: Resolve Tasks Git Scope. This obtains `TASKS_DIR`,
`TASKS_FILE`, `TASKS_GIT_SCOPE`, `TASKS_GIT_REL`, and the `tasks_git` helper.

### Step 1.1: Locate optimus-tasks.md

Tasks file is always at `<tasksDir>/optimus-tasks.md` (derived from `tasksDir`, default `docs/pre-dev`).

If not found, inform the user and suggest: "No optimus-tasks.md found. Run `/optimus-import` to create one from existing task files, or create it manually following the optimus format."

### Step 1.1.1: Validate Format Marker

Check that the **first line** of `optimus-tasks.md` is `<!-- optimus:tasks-v1 -->`.

If missing, warn the user: "optimus-tasks.md exists but is not in optimus format (missing `<!-- optimus:tasks-v1 -->` marker). Run `/optimus-import` to convert it."

The report agent still ATTEMPTS to parse and display data even without the marker (best effort), but shows the warning prominently.

### Step 1.1.2: Default Branch Warning

Detect if the report is being run on the default branch:

```bash
DEFAULT_BRANCH=$(git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's@^refs/remotes/origin/@@')
if [ -z "$DEFAULT_BRANCH" ]; then
  DEFAULT_BRANCH=$(git branch --list main master 2>/dev/null | head -1 | tr -d ' *')
fi
CURRENT_BRANCH=$(git branch --show-current 2>/dev/null)
```

If `CURRENT_BRANCH` equals `DEFAULT_BRANCH` (or is `main`/`master`):

Since status lives in `.optimus/state.json` (local), it is always up-to-date regardless
of which branch is checked out. No branch-specific warning is needed.

Skip this step silently.

### Step 1.2: Parse the Tasks Table

Read `optimus-tasks.md` and extract the markdown table. Expected columns:

| Column | Description |
|--------|-------------|
| ID | Task identifier (e.g., T-001) |
| Title | Short description |
| Tipo | Task type: Feature, Fix, Refactor, Chore, Docs, or Test |
| Depends | Comma-separated dependency IDs, or `-` for none |
| Priority | Alta, Media, or Baixa |
| Version | Version/milestone this task belongs to |
| Estimate | Task size estimate (S, M, L, XL, etc.), or `-` |
| TaskSpec | Path to Ring pre-dev task spec (optional — `-` if not linked) |

**Status and Branch** are read from `.optimus/state.json` — see AGENTS.md Protocol: State Management.
Tasks with no entry in state.json are `Pendente`.

### Step 1.2.1: Parse Versions Table

Read the `## Versions` section and extract the versions table. Expected columns:
- Version (name), Status (`Ativa`, `Próxima`, `Planejada`, `Backlog`, `Concluída`), Description

Identify the version with Status `Ativa` — this is the **active version** used for default filtering.

For each task, check if the `TaskSpec` column has a value (not `-`) to verify completeness.

### Step 1.3: Validate Dependencies

For each task with dependencies:
1. Verify all referenced task IDs exist in the table
2. Check for circular dependencies (A→B→A)
3. If invalid dependencies found, report them as warnings in the dashboard

---

## Phase 2: Quick Status Mode Detection

If the user's invocation matches quick status triggers ("quick status", "what am I working on?",
"current task", "status rápido"):

1. Parse optimus-tasks.md (Phase 1 still runs fully)
2. Find tasks with status other than `Pendente`, `DONE`, and `Cancelado` (active tasks)
3. For each active task, read its Ring source via the `TaskSpec` column for context
4. Present ONLY:

```
Quick Status:
  Active: T-XXX — [title] (Em Andamento)
  Next up: T-YYY — [title] (Pendente, ready to start)
```

5. **STOP here** — do NOT proceed to the remaining phases (dependency graph, parallelization, velocity, etc.)

If the invocation does NOT match quick status triggers, proceed to Phase 3 normally.

---

## Phase 3: Classify Tasks

Classify each task into one of these categories:

### Done
Status is `DONE`.

### Cancelled
Status is `Cancelado`. These tasks were abandoned and will not be implemented.
Show in a separate section — do NOT count them in progress calculations.

### Active
Status is anything other than `Pendente`, `DONE`, or `Cancelado`:
- `Validando Spec` (plan running)
- `Em Andamento` (build running)
- `Validando Impl` (check running)

### Ready to Start
Status is `Pendente` AND all dependencies are `DONE` (or no dependencies).

### Blocked
Status is `Pendente` AND at least one dependency is NOT `DONE` or is `Cancelado`.
Record which dependencies are blocking (note if a blocker is `Cancelado` — the dependency
should be removed or replaced).

---

## Phase 4: Version Filtering

### Step 4.1: Determine Version Scope

Resolve the effective scope in this order — see AGENTS.md Protocol: Default Scope Resolution.

1. **Invocation wins.** If the user specified a scope in the invocation (e.g.,
   "report ativa", "report all", "report v2", "report upcoming"), use that scope
   directly. Skip sub-steps 2-4.

   **Force-ask keywords:** If the invocation contains `ask` or `menu` (e.g.,
   "report ask", "report menu"), skip sub-step 2 and go straight to the AskUser prompt
   (sub-step 3). Use this to override a saved default and optionally overwrite it.

2. **Config fallback.** If `.optimus/config.json` has a `defaultScope` key, use it
   without prompting. Validate the value (`ativa`, `upcoming`, `all`, or an existing
   version name). If invalid, warn and fall through to sub-step 3.

3. **Ask user.** Via `AskUser`:

   ```
   Which version scope do you want to see?
   ```
   Options:
   - **Ativa** — only tasks from the active version (<active_version_name>)
   - **Upcoming** — active + planned versions (Ativa, Próxima, Planejada — excludes Backlog and Concluída)
   - **All** — all tasks across all versions
   - **Specific version** — pick one version by name

   If the user selects **Specific version**, follow up with `AskUser` listing available
   version names as options.

4. **Offer to persist (only when sub-step 3 ran).** After the user picks a scope, ask:

   ```
   Save "<chosen_scope>" as the default in .optimus/config.json?
   You can still override per-invocation (e.g., "report all") or use
   "report ask" to be prompted again.
   ```
   Options:
   - **Save as default** — write `defaultScope` to `.optimus/config.json`
   - **Just this time** — do not persist

   **Exception to the read-only rule:** writing `defaultScope` to `.optimus/config.json`
   is the ONLY side-effect this skill is allowed to perform, and only when the user
   explicitly chooses "Save as default".

### Step 4.2: Apply Filter

**Scope mapping:**

| Scope | Versions included |
|-------|-------------------|
| `ativa` | Only the version with Status `Ativa` |
| `upcoming` | Versions with Status `Ativa`, `Próxima`, or `Planejada` |
| `all` | All versions |
| `<version_name>` | Only the named version |

**When filtering:**
- All subsequent phases (dependency graph, parallelization, dashboard tables) only include
  tasks from the selected version(s)
- Cross-version dependencies are shown as external references (e.g., "depends on T-001 [MVP, DONE]")

---

## Phase 5: Version Progress Summary

Compute progress for each version, regardless of filtering.
**Cancelled tasks are excluded from progress calculations** — they do not count toward
the total, done, active, or pending numbers. Progress = Done / (Total - Cancelled).
**If (Total - Cancelled) == 0** (all tasks cancelled or no tasks exist), show progress as
"N/A — all tasks cancelled" instead of computing a division.

```
┌──────────────────────────────────────────────────────────────┐
│ VERSION PROGRESS                                              │
├─────────┬────────┬──────┬────────┬─────────┬──────────┬──────┤
│ Version │ Status │ Done │ Active │ Pending │ Canceld. │ Prog │
├─────────┼────────┼──────┼────────┼─────────┼──────────┼──────┤
│ MVP     │ Ativa  │ 5    │ 2      │ 4       │ 1        │ 45%  │
│ v2      │ Próxima│ 0    │ 0      │ 6       │ 0        │ 0%   │
│ Futuro  │ Backlog│ 0    │ 0      │ 3       │ 0        │ 0%   │
└─────────┴────────┴──────┴────────┴─────────┴──────────┴──────┘
```

This section is ALWAYS shown (even when filtering by a specific version) to give the
user the full project overview.

---

## Phase 6: Compute Dependency Graph

Build a directed acyclic graph (DAG) from the Depends column.

For the ASCII art graph:
- Use `✓` for done tasks
- Use `⚙` for active tasks
- Use `◇` for ready-to-start tasks
- Use `⊘` for blocked tasks
- Use `✗` for cancelled tasks
- Use `─►` for dependency arrows
- Use `┬`, `├`, `└` for branching

Example:
```
T-001 ✓ ─┬─► T-002 ✓ ─┬─► T-004 ◇
          │             │
          ├─► T-003 ◇   ├─► T-005 ⚙
          │             │
          └─► T-006 ◇   └─► T-008 ◇

T-007 ⚙ ────► T-009 ⊘ ────► T-010 ⊘

Legend: ✓=Done ⚙=Active ◇=Ready ⊘=Blocked ✗=Cancelled
```

For trees with depth > 3 levels, simplify by showing only the critical path and noting "N more tasks omitted".

---

## Phase 7: Identify Parallelization Opportunities

### Currently Parallelizable
Tasks that are `Pendente` with all dependencies `DONE`. These can ALL start right now, in parallel.

### Next Wave
For each active task, identify which blocked tasks it would unlock when completed.
Group by: "After T-XXX completes, these unlock: ..."

---

## Phase 8: Present Dashboard

Present the full dashboard using the format below. Use the `<json-render>` format when available for richer display, otherwise use the ASCII art format.

### ASCII Art Format

```
╔══════════════════════════════════════════════════════╗
║                  PROJECT STATUS                      ║
╠══════════════════════════════════════════════════════╣
║  Total: NN  │  Done: NN  │  Active: NN  │  Pending: NN  │  Cancelled: NN  ║
╚══════════════════════════════════════════════════════╝

Progress: ████████░░░░░░░░░░░░ XX% (done / (total - cancelled))

┌──────────────────────────────────────────────────────────┐
│ ACTIVE TASKS                                              │
├────────┬──────────────────────┬──────────┬────────────────┤
│ ID     │ Title                │ Version  │ Status         │
├────────┼──────────────────────┼──────────┼────────────────┤
│ T-005  │ User registration    │ MVP      │ Em Andamento   │
│ T-007  │ Login page           │ MVP      │ Validando Impl │
└────────┴──────────────────────┴──────────┴────────────────┘

┌──────────────────────────────────────────────────────────┐
│ READY TO START (dependencies satisfied)                   │
├────────┬──────────────────────┬──────────┬────────────────┤
│ ID     │ Title                │ Version  │ Priority       │
├────────┼──────────────────────┼──────────┼────────────────┤
│ T-006  │ Password reset       │ v2       │ Alta           │
│ T-008  │ E2E auth tests       │ MVP      │ Media          │
└────────┴──────────────────────┴──────────┴────────────────┘

┌──────────────────────────────────────────────────────────┐
│ BLOCKED (waiting for dependencies)                        │
├────────┬──────────────────────┬──────────┬────────────────┤
│ ID     │ Title                │ Version  │ Blocked by     │
├────────┼──────────────────────┼──────────┼────────────────┤
│ T-009  │ Admin dashboard      │ MVP      │ T-007          │
│ T-010  │ Role management      │ v2       │ T-009          │
└────────┴──────────────────────┴──────────┴────────────────┘

┌─────────────────────────────────────────────────┐
│ DEPENDENCY GRAPH                                 │
├─────────────────────────────────────────────────┤
│                                                  │
│  [insert computed graph here]                    │
│                                                  │
│  Legend: ✓=Done ⚙=Active ◇=Ready                 │
│          ⊘=Blocked ✗=Cancelled                   │
└─────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────┐
│ PARALLELIZATION OPPORTUNITIES                    │
├─────────────────────────────────────────────────┤
│ Can start RIGHT NOW (in parallel):               │
│                                                  │
│  ┌─ T-006: Password reset          [Alta]        │
│  ├─ T-008: E2E auth tests          [Media]       │
│  └─ T-003: Login page              [Alta]        │
│                                                  │
│ After T-007 completes, also unlock:              │
│  └─ T-009: Admin dashboard         [Alta]        │
│                                                  │
│ After T-009 completes, also unlock:              │
│  └─ T-010: Role management         [Media]       │
└─────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────┐
│ COMPLETED                                        │
├────────┬──────────────────────────────────────────┤
│ T-001  │ Setup auth module                        │
│ T-002  │ User registration API                    │
└────────┴──────────────────────────────────────────┘

┌─────────────────────────────────────────────────┐
│ CANCELLED                                        │
├────────┬──────────────────────────────────────────┤
│ T-011  │ Legacy migration script                  │
└────────┴──────────────────────────────────────────┘
```

### Estimate Summary

If any tasks have Estimate values (non-`-`), show an estimate breakdown by status:

```
┌─────────────────────────────────────────────────┐
│ ESTIMATE BREAKDOWN                               │
├──────────┬────────────────────────────────────────┤
│ Status   │ Estimates                              │
├──────────┼────────────────────────────────────────┤
│ Active   │ 2S, 1M, 1L                            │
│ Ready    │ 1M, 2L                                 │
│ Blocked  │ 1S, 1XL                                │
│ Done     │ 3S, 2M, 1L                            │
└──────────┴────────────────────────────────────────┘
```

If no tasks have Estimate values, skip this section.

### json-render Format

Also generate a `<json-render>` dashboard with these components:
- **Heading**: "Project Status"
- **ProgressBar**: overall completion (done / (total - cancelled))
- **Metric**: Total, Done, Active, Pending, Cancelled counts
- **Table**: Active tasks (columns: ID, Title, Version, Status)
- **Table**: Ready to start (columns: ID, Title, Version, Priority)
- **Table**: Blocked (columns: ID, Title, Version, Blocked by)
- **List**: Parallelization opportunities
- **StatusLine**: one per active task (success=done, info=active, warning=blocked, error=failed)

Present BOTH formats: the ASCII art first (always readable), then the json-render (for rich terminal).

---

## Phase 9: Velocity and History Metrics

After the dashboard, compute velocity metrics from `state.json` timestamps. These provide
trend data that a static snapshot (Phase 8) cannot show.

**NOTE:** Status lives in `.optimus/state.json` (gitignored), not in git commits.
Velocity is derived from the `updated_at` timestamps of tasks with status `DONE`.

### Step 9.1: Compute Task Completion History

Read `.optimus/state.json` and extract all tasks with status `DONE`:

```bash
# Resolve main worktree so .optimus/* paths are not isolated to a linked worktree.
# All .optimus/* state lives in the main worktree; linked worktrees do not propagate it.
MAIN_WORKTREE="$(git worktree list --porcelain 2>/dev/null | awk '/^worktree / {print $2; exit}')"
if [ -z "$MAIN_WORKTREE" ]; then
  echo "ERROR: Cannot determine main worktree — not in a git repository." >&2
  exit 1
fi

STATE_FILE="${MAIN_WORKTREE}/.optimus/state.json"
if [ -f "$STATE_FILE" ] && jq empty "$STATE_FILE" 2>/dev/null; then
  jq -r 'to_entries[] | select(.value.status == "DONE") | "\(.key) \(.value.updated_at)"' "$STATE_FILE"
fi
```

For each completed task, extract: task ID and completion date (from `updated_at`).
Group completions by week (last 4 weeks) for the velocity chart.

**If state.json is missing or has no DONE tasks**, show:
```
Velocity: No completed tasks found in state.json. Complete a task to start tracking.
```

### Step 9.2: Present Velocity Dashboard

```
┌─────────────────────────────────────────────────┐
│ VELOCITY (last 4 weeks)                          │
├─────────────────────────────────────────────────┤
│ Tasks completed:                                 │
│   Week -4: ██░░░░░░░░ 2                         │
│   Week -3: ████░░░░░░ 4                         │
│   Week -2: ███░░░░░░░ 3                         │
│   Week -1: █████░░░░░ 5                         │
│                                                  │
│ Average: 3.5 tasks/week                          │
│ Trend: ↑ accelerating                            │
│                                                  │
│ At current pace:                                 │
│   Remaining tasks (active version): N            │
│   Estimated completion: ~X weeks                 │
└─────────────────────────────────────────────────┘
```

### Step 9.3: Average Time Per Stage

If enough data exists (3+ completed tasks with `updated_at` timestamps in state.json),
compute approximate stage durations by comparing `updated_at` values of tasks that
progressed through multiple stages. If `stats.json` has `last_plan` and `last_review`
timestamps, use those for more precise stage duration estimates.

Present as:
```
Average time per stage (from N completed tasks):
  Validando Spec:  ~2h
  Em Andamento:    ~1.5 days
  Validando Impl:  ~3h
  Close:           ~15min
```

---

## Phase 9.4: Stage Execution Stats (Churn Metrics)

Read `.optimus/stats.json` to display stage execution counters. If the file does not
exist, skip this phase silently.

### Step 9.4.1: Load Stats

```bash
# MAIN_WORKTREE was resolved earlier (Step 9.1); reuse it. If somehow unset,
# resolve again to keep this block independent.
if [ -z "${MAIN_WORKTREE:-}" ]; then
  MAIN_WORKTREE="$(git worktree list --porcelain 2>/dev/null | awk '/^worktree / {print $2; exit}')"
  if [ -z "$MAIN_WORKTREE" ]; then
    echo "ERROR: Cannot determine main worktree — not in a git repository." >&2
    exit 1
  fi
fi

STATS_FILE="${MAIN_WORKTREE}/.optimus/stats.json"
if [ -f "$STATS_FILE" ]; then
  if jq empty "$STATS_FILE" 2>/dev/null; then
    cat "$STATS_FILE"
  else
    echo "WARNING: stats.json is corrupted. Skipping churn metrics."
  fi
fi
```

### Step 9.4.2: Present Churn Dashboard

Only show this section if stats.json exists AND has at least one task entry.

**Highlight tasks with above-average churn** — tasks where `plan_runs > avg_plan_runs`
or `review_runs > avg_review_runs` are flagged as high-churn.

```
┌─────────────────────────────────────────────────┐
│ STAGE EXECUTION STATS                            │
├─────────────────────────────────────────────────┤
│ Average plan runs:  1.5 per task                 │
│ Average review runs: 2.0 per task                │
│                                                  │
│ High-churn tasks:                                │
│   T-003: plan ×4, review ×3  ← spec issues?     │
│   T-007: plan ×1, review ×5  ← review cycles?   │
│                                                  │
│ All tasks:                                       │
│   T-001: plan ×1, review ×1                      │
│   T-002: plan ×2, review ×2                      │
│   T-003: plan ×4, review ×3  ⚠                  │
│   T-007: plan ×1, review ×5  ⚠                  │
└─────────────────────────────────────────────────┘
```

**If only 1-2 tasks exist**, skip the averages and high-churn section — just show the
per-task counts.

---

## Phase 10: Warnings and Recommendations

After the dashboard, present any issues found:

### Warnings
- Tasks with missing TaskSpec (column value is `-`)
- Circular dependencies
- Invalid dependency references (pointing to non-existent task IDs)
- Tasks blocked by a cancelled dependency (see "Blocked by Cancelled" section below)
- Tasks stuck in the same status for too long (check `updated_at` timestamp in state.json — if older than 7 days, flag as potentially stale)

### Blocked by Cancelled Dependencies (guided resolution)

For each task that is blocked because a dependency has status `Cancelado`, present a
dedicated resolution guide:

```markdown
### Blocked by Cancelled Dependency

T-YYY depends on T-XXX, but T-XXX was cancelled (Cancelado).
Cancelled tasks do NOT satisfy dependencies — T-YYY cannot start.

**Resolution options (run `/optimus-tasks` to apply):**
1. **Remove the dependency** — edit T-YYY to remove T-XXX from Depends
   Command: "edit T-YYY, remove T-XXX from dependencies"
2. **Replace with another task** — if another task covers what T-XXX was supposed to deliver
   Command: "edit T-YYY, replace T-XXX with T-ZZZ in dependencies"
3. **Cancel T-YYY too** — if T-YYY no longer makes sense without T-XXX
   Command: "cancel T-YYY"
```

This section is shown for EACH blocked-by-cancelled case, not just as a generic warning.

### Workspace Health

Check for orphaned or stale worktrees by listing all git worktrees and cross-referencing
with task status:

```bash
git worktree list
```

For each worktree (excluding the main repository entry):
1. Extract the branch name from the worktree entry
2. Match to a task by searching for the task ID pattern in the branch name (e.g., `t-003` in `feat/t-003-user-auth`)
3. Read the task's status from state.json

Flag worktrees as potentially orphaned if:
- The task is `DONE` — worktree should have been cleaned up by done
- The task is `Cancelado` — worktree should have been cleaned up by tasks cancel
- The task is `Pendente` — worktree exists but task was never started or was reset
- No matching task found — worktree has no corresponding task in optimus-tasks.md

```
┌─────────────────────────────────────────────────┐
│ WORKSPACE HEALTH                                 │
├─────────────────────────────────────────────────┤
│ Active worktrees: N                              │
│                                                  │
│ ⚠ Potentially orphaned:                         │
│   /path/to/wt-t-003  →  T-003 (DONE)        │
│   /path/to/wt-t-007  →  T-007 (Cancelado)       │
│   /path/to/wt-unknown →  no matching task        │
│                                                  │
│ To clean up, run:                                │
│   git worktree remove <path>                     │
└─────────────────────────────────────────────────┘
```

If no orphaned worktrees are found, show: "Workspace Health: OK — no orphaned worktrees."

### Recommendations
- Suggest which ready tasks to start next (highest priority first)
- If multiple tasks are parallelizable, mention it explicitly
- If a single active task is blocking many others, highlight it as a bottleneck

---

## Phase 11: Export (optional)

If the user requests an export (e.g., "export report", "save report", "report to file"):

### Step 11.1: Generate Markdown Export

Compile the full dashboard into a single markdown file including all sections:
- Project status summary (progress bar, counts)
- Version progress table
- Active / Ready / Blocked tables
- Dependency graph (ASCII art)
- Parallelization opportunities
- Velocity metrics
- Workspace health
- Warnings and recommendations

### Step 11.2: Write File

Initialize the .optimus directory (see AGENTS.md Protocol: Initialize .optimus Directory)
for temporary state files.

Resolve the main-worktree report directory (so reports are not isolated to a linked
worktree, which would lose them on cleanup):

```bash
if [ -z "${MAIN_WORKTREE:-}" ]; then
  MAIN_WORKTREE="$(git worktree list --porcelain 2>/dev/null | awk '/^worktree / {print $2; exit}')"
  if [ -z "$MAIN_WORKTREE" ]; then
    echo "ERROR: Cannot determine main worktree — not in a git repository." >&2
    exit 1
  fi
fi
REPORT_DIR="${MAIN_WORKTREE}/.optimus/reports"
mkdir -p "$REPORT_DIR"
REPORT_FILE="${REPORT_DIR}/report-$(date +%Y-%m-%d).md"
```

Write to `${REPORT_FILE}` (i.e., `<main-worktree>/.optimus/reports/report-<date>.md`):

```markdown
# Project Status Report — <date>

Generated by optimus-report

[full dashboard content]
```

Inform the user: "Report exported to `${REPORT_FILE}`" (display the resolved path,
e.g., `<main-worktree>/.optimus/reports/report-<date>.md`).

**NOTE:** This is the ONLY case where report writes a file. The export file is
an artifact in `.optimus/reports/` (gitignored), not a project file.

---

## Rules

- **NEVER modify project files** — this agent is strictly read-only with two allow-listed
  exceptions: (a) exports to `.optimus/reports/` (gitignored), and (b) writing
  `defaultScope` to `.optimus/config.json` when the user opts in (see Step 4.1, sub-step 4).
- **NEVER change task status** — only report current state
- **NEVER invoke other stage agents** — only recommend
- Present the full dashboard even if there's only 1 task
- If optimus-tasks.md has no table or invalid format, suggest running `/optimus-import` to convert it to the standard format
- If optimus-tasks.md does not exist, suggest running `/optimus-import` to create one from existing task files
- Always show the dependency graph, even for small projects — it reveals parallelization opportunities

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


### Protocol: Default Scope Resolution

**Referenced by:** report, quick-report

Both `report` and `quick-report` support a version scope filter (`ativa`, `upcoming`,
`all`, or a specific version name). Resolve the effective scope in this order:

1. **Invocation wins.** If the user specified a scope in the invocation (e.g.,
   "quick report all", "report v2", "report upcoming"), use that scope directly.
   Skip steps 2-3.

   **Force-ask keywords:** If the invocation contains `ask` or `menu`
   (e.g., "quick report ask", "report menu"), skip step 2 and go straight to step 3
   (the AskUser prompt). This lets the user override the saved default for a single run
   and optionally overwrite it.

2. **Config fallback.** If `.optimus/config.json` has a `defaultScope` key, use it:
   ```bash
   CONFIG_FILE="${MAIN_WORKTREE}/.optimus/config.json"
   if [ -f "$CONFIG_FILE" ] && jq -e '.defaultScope' "$CONFIG_FILE" >/dev/null 2>&1; then
     SCOPE=$(jq -r '.defaultScope' "$CONFIG_FILE")
   fi
   ```
   **Validation:** `SCOPE` must be `ativa`, `upcoming`, `all`, or match a version name in
   the `## Versions` table of `optimus-tasks.md`. If invalid (empty, unknown keyword, or a version
   name that no longer exists), warn the user and fall through to step 3.
   ```
   WARNING: .optimus/config.json has defaultScope="<value>" but it is not valid
   (must be ativa/upcoming/all or an existing version name). Falling back to prompt.
   ```

3. **Ask user.** Present the standard AskUser prompt:
   ```
   Which version scope do you want to see?
   ```
   Options:
   - **Ativa** — only tasks from the active version (`<active_version_name>`)
   - **Upcoming** — active + planned (Ativa, Próxima, Planejada — excludes Backlog and Concluída)
   - **All** — all tasks across all versions
   - **Specific version** — pick one version by name (follow-up AskUser lists versions)

4. **Offer to persist (only when step 3 ran).** After the user picks a scope in step 3,
   ask a follow-up via AskUser:
   ```
   Save "<chosen_scope>" as the default in .optimus/config.json?
   You can still override per-invocation (e.g., "quick report all") or
   use "quick report ask" to be prompted again.
   ```
   Options:
   - **Save as default** — write `defaultScope` to `.optimus/config.json`
   - **Just this time** — do not persist

5. **Persist the scope (if user chose to save):**
   ```bash
   # Initialize .optimus directory — see AGENTS.md Protocol: Initialize .optimus Directory.
   CONFIG_FILE="${MAIN_WORKTREE}/.optimus/config.json"
   if [ ! -f "$CONFIG_FILE" ]; then
     echo '{}' > "$CONFIG_FILE"
   fi
   if jq --arg s "$SCOPE" '.defaultScope = $s' "$CONFIG_FILE" > "${CONFIG_FILE}.tmp"; then
     if jq empty "${CONFIG_FILE}.tmp" 2>/dev/null; then
       mv "${CONFIG_FILE}.tmp" "$CONFIG_FILE"
     else
       rm -f "${CONFIG_FILE}.tmp"
       echo "ERROR: jq produced invalid JSON — config.json unchanged"
     fi
   else
     rm -f "${CONFIG_FILE}.tmp"
     echo "ERROR: jq failed to update config.json"
   fi
   ```
   **NOTE:** `config.json` is gitignored (per-user preference). The saved `defaultScope`
   affects only the local environment — each user can choose their own default. These
   skills are read-only for code/tasks — writing to `config.json` is the single allowed
   side-effect, and only when the user explicitly agrees.

**NOTE:** Scope names are case-insensitive for user input. Normalize to lowercase for
`ativa`/`upcoming`/`all`, but preserve the original casing when the scope is a specific
version name (version names are case-sensitive to match the Versions table).

Skills reference this as: "Resolve default scope — see AGENTS.md Protocol: Default Scope Resolution."


### Protocol: Initialize .optimus Directory

**Referenced by:** import, tasks, report (export), quick-report, batch, pr-check, deep-review, coderabbit-review, all stage agents (1-4) for session files

Before creating ANY file inside `.optimus/`, ensure the directory structure exists
and that the entire `.optimus/` tree is gitignored (it is 100% operational/per-user).

```bash
# Requires Protocol: Resolve Main Worktree Path to have run first
# (or resolve inline; see that protocol).
MAIN_WORKTREE="$(git worktree list --porcelain 2>/dev/null | awk '/^worktree / {print $2; exit}')"
mkdir -p "${MAIN_WORKTREE}/.optimus/sessions" "${MAIN_WORKTREE}/.optimus/reports" "${MAIN_WORKTREE}/.optimus/logs"
if ! grep -q '^# optimus-operational-files' .gitignore 2>/dev/null; then
  printf '\n# optimus-operational-files\n.optimus/config.json\n.optimus/state.json\n.optimus/stats.json\n.optimus/sessions/\n.optimus/reports/\n.optimus/logs/\n' >> .gitignore
fi
# Linked worktrees managed by Optimus live at ${MAIN_WORKTREE}/.worktrees/
# (see Worktree Location Convention). Add the gitignore entry idempotently
# on a separate marker so existing projects whose `.gitignore` already
# carries the operational-files block still get the worktree exclusion.
# Refuse symlinked .gitignore (defense against link-following file-write).
if [ -L .gitignore ]; then
  echo "ERROR: .gitignore is a symlink — refusing to append (potential symlink attack)." >&2
  exit 1
fi
if ! grep -q '^# optimus-operational-worktrees' .gitignore 2>/dev/null; then
  printf '\n# optimus-operational-worktrees\n.worktrees/\n' >> .gitignore
fi
# Log retention (idempotent — fires once per init): age-based + count-cap prune.
# Also duplicated in Protocol: Session State so stage agents (which call Session
# State but not Initialize Directory) get pruning at every phase transition.
# Both prune sites are no-ops on clean directories; running both is harmless.
find "${MAIN_WORKTREE}/.optimus/logs" -type f -name '*.log' -mtime +30 -delete 2>/dev/null
if [ -d "${MAIN_WORKTREE}/.optimus/logs" ]; then
  ls -1t "${MAIN_WORKTREE}/.optimus/logs"/*.log 2>/dev/null | tail -n +501 \
    | while IFS= read -r _log_to_rm; do rm -f -- "$_log_to_rm"; done
fi
```

**Log retention** for `.optimus/logs/` runs at TWO sites for full coverage:
- **Protocol: Initialize .optimus Directory** (this protocol) — fires when
  admin/standalone skills (`import`, `tasks`, `report`, `quick-report`, `batch`,
  `pr-check`, `deep-review`, `coderabbit-review`) initialize `.optimus/`.
- **Protocol: Session State** — fires at every stage agent (`plan`, `build`,
  `review`, `done`) phase transition.

Both sites are idempotent (no-op on clean directories) and use the same prune
logic (30-day age cap + 500-file count cap). Running both per session is a
harmless cheap operation.

Everything inside `.optimus/` is gitignored. The planning tree is versioned
separately at `<tasksDir>/optimus-tasks.md` (and `<tasksDir>/tasks/`, `<tasksDir>/subtasks/`
for Ring specs) — see the File Location section above.

Skills reference this as: "Initialize .optimus directory — see AGENTS.md Protocol: Initialize .optimus Directory."


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


<!-- INLINE-PROTOCOLS:END -->
