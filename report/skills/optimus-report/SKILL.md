---
name: optimus-report
description: "Task status dashboard. Reads tasks.md, computes dependency graph, and presents a comprehensive project status report. Shows progress, active tasks, blocked tasks, ready-to-start tasks, dependency graph, and parallelization opportunities. Read-only -- this agent NEVER modifies any files."
trigger: >
  - When user asks for project status (e.g., "show tasks", "project status", "what's ready?")
  - When user wants to know what can be parallelized
  - When user asks "what should I work on next?"
  - Before starting a new task (to see the full picture)
  - When user asks "quick status", "what am I working on?", "current task"
skip_when: >
  - No tasks.md exists in the project
  - User wants to run a specific stage agent (use that agent directly)
prerequisite: >
  - .optimus/tasks.md exists in the project
NOT_skip_when: >
  - "I already know the status" -- The dashboard shows dependencies and parallelization you might miss.
  - "There's only one task" -- Even single tasks benefit from status verification.
examples:
  - name: Full project status
    invocation: "Show project status"
    expected_flow: >
      1. Find and parse tasks.md
      2. Compute dependency graph
      3. Classify tasks (done, active, ready, blocked)
      4. Present dashboard with all sections
  - name: What to work on next
    invocation: "What can I work on next?"
    expected_flow: >
      1. Parse tasks.md
      2. Find tasks with status Pendente and all dependencies DONE
      3. Present ready-to-start tasks with priority ordering
  - name: Quick status check
    invocation: "Quick status" or "What am I working on?"
    expected_flow: >
      1. Parse tasks.md
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

Read-only agent that parses `tasks.md` and presents a comprehensive project status report.

**CRITICAL:** This agent NEVER modifies any files. It only reads and reports.

---

## Phase 1: Find and Parse tasks.md

### Step 1.1: Locate tasks.md

Tasks file is always at `.optimus/tasks.md`.

If not found, inform the user and suggest: "No tasks.md found. Run `/optimus-import` to create one from existing task files, or create it manually following the optimus format."

### Step 1.1.1: Validate Format Marker

Check that the **first line** of `tasks.md` is `<!-- optimus:tasks-v1 -->`.

If missing, warn the user: "tasks.md exists but is not in optimus format (missing `<!-- optimus:tasks-v1 -->` marker). Run `/optimus-import` to convert it."

The report agent still ATTEMPTS to parse and display data even without the marker (best effort), but shows the warning prominently.

### Step 1.1.2: Default Branch Warning

Detect if the report is being run on the default branch:

```bash
DEFAULT_BRANCH=$(git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's@^refs/remotes/origin/@@')
CURRENT_BRANCH=$(git branch --show-current)
```

If `CURRENT_BRANCH` equals `DEFAULT_BRANCH` (or is `main`/`master`):

Since status lives in `.optimus/state.json` (local), it is always up-to-date regardless
of which branch is checked out. No branch-specific warning is needed.

Skip this step silently.

### Step 1.2: Parse the Tasks Table

Read `tasks.md` and extract the markdown table. Expected columns:

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

1. Parse tasks.md (Phase 1 still runs fully)
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
- `Revisando PR` (pr-check running)

### Ready to Start
Status is `Pendente` AND all dependencies are `DONE` (or no dependencies).

### Blocked
Status is `Pendente` AND at least one dependency is NOT `DONE` or is `Cancelado`.
Record which dependencies are blocking (note if a blocker is `Cancelado` — the dependency
should be removed or replaced).

---

## Phase 4: Version Filtering

### Step 4.1: Determine Version Scope

**If the user specified a scope in the invocation** (e.g., "report ativa", "report all",
"report v2", "report upcoming"), use that scope directly — skip the AskUser prompt.

**If the user did NOT specify a scope** (e.g., just "report" or "show project status"),
ask via `AskUser`:

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
STATE_FILE=".optimus/state.json"
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
progressed through multiple stages. If `stats.json` has `last_plan` and `last_check`
timestamps, use those for more precise stage duration estimates.

Present as:
```
Average time per stage (from N completed tasks):
  Validando Spec:  ~2h
  Em Andamento:    ~1.5 days
  Validando Impl:  ~3h
  Revisando PR:    ~1h
  Close:           ~15min
```

---

## Phase 9.4: Stage Execution Stats (Churn Metrics)

Read `.optimus/stats.json` to display stage execution counters. If the file does not
exist, skip this phase silently.

### Step 9.4.1: Load Stats

```bash
STATS_FILE=".optimus/stats.json"
if [ -f "$STATS_FILE" ]; then
  cat "$STATS_FILE"
fi
```

### Step 9.4.2: Present Churn Dashboard

Only show this section if stats.json exists AND has at least one task entry.

**Highlight tasks with above-average churn** — tasks where `plan_runs > avg_plan_runs`
or `check_runs > avg_check_runs` are flagged as high-churn.

```
┌─────────────────────────────────────────────────┐
│ STAGE EXECUTION STATS                            │
├─────────────────────────────────────────────────┤
│ Average plan runs:  1.5 per task                 │
│ Average check runs: 2.0 per task                 │
│                                                  │
│ High-churn tasks:                                │
│   T-003: plan ×4, check ×3  ← spec issues?      │
│   T-007: plan ×1, check ×5  ← review cycles?    │
│                                                  │
│ All tasks:                                       │
│   T-001: plan ×1, check ×1                       │
│   T-002: plan ×2, check ×2                       │
│   T-003: plan ×4, check ×3  ⚠                   │
│   T-007: plan ×1, check ×5  ⚠                   │
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
- No matching task found — worktree has no corresponding task in tasks.md

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

Write to `.optimus/reports/report-<date>.md`:

```markdown
# Project Status Report — <date>

Generated by optimus-report

[full dashboard content]
```

Inform the user: "Report exported to `.optimus/reports/report-<date>.md`"

**NOTE:** This is the ONLY case where report writes a file. The export file is
an artifact in `.optimus/reports/` (gitignored), not a project file.

---

## Rules

- **NEVER modify project files** — this agent is strictly read-only (except export to `.optimus/reports/`)
- **NEVER change task status** — only report current state
- **NEVER invoke other stage agents** — only recommend
- Present the full dashboard even if there's only 1 task
- If tasks.md has no table or invalid format, suggest running `/optimus-import` to convert it to the standard format
- If tasks.md does not exist, suggest running `/optimus-import` to create one from existing task files
- Always show the dependency graph, even for small projects — it reveals parallelization opportunities


<!-- INLINE-PROTOCOLS:START -->
## Shared Protocols (from AGENTS.md)

The following protocols are referenced by this skill. They are
extracted from the Optimus AGENTS.md to make this plugin self-contained.

### File Location

All Optimus files live in the `.optimus/` directory at the project root:

```
.optimus/
├── config.json          # versionado — tasksDir, commands
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
| `Revisando PR` | pr-check | PR being reviewed (optional stage) |
| `DONE` | done | Completed |
| `Cancelado` | tasks | Task abandoned, will not be implemented |

**Administrative status operations** (managed by tasks, not by stage agents):
- **Reopen:** `DONE` → `Pendente` (remove entry from state.json) or `Em Andamento` (if worktree exists) — when a bug is found after close. Also accepts `Cancelado` → `Pendente` — when a cancellation decision is reversed.
- **Advance:** move forward one stage — when work was done manually outside the pipeline
- **Demote:** move backward one stage — when rework is needed after review
- **Cancel:** any non-terminal → `Cancelado` — task will not be implemented

These operations require explicit user confirmation.


### Protocol: Initialize .optimus Directory

**Referenced by:** import, tasks, report (export), all stage agents (1-5) for session files

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

**Referenced by:** all stage agents (1-5), tasks, report, quick-report

All status and branch data is stored in `.optimus/state.json` (gitignored).

**Prerequisites:**

```bash
if ! command -v jq &>/dev/null; then
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


<!-- INLINE-PROTOCOLS:END -->
