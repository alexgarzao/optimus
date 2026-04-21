---
name: optimus-cycle-report
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
      2. Show only: current active task, its acceptance criteria progress, and next-up
      3. Skip dependency graph, parallelization, velocity, and completed tasks
related:
  complementary:
    - optimus-cycle-spec-stage-1
    - optimus-cycle-impl-stage-2
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

Look for `.optimus/tasks.md`. There are no fallback locations.

If not found, inform the user and suggest: "No .optimus/tasks.md found. Run `/optimus-cycle-migrate` to create one from existing task files, or create it manually following the optimus format."

### Step 1.1.1: Validate Format Marker

Check that the **first line** of `tasks.md` is `<!-- optimus:tasks-v1 -->`.

If missing, warn the user: "tasks.md exists but is not in optimus format (missing `<!-- optimus:tasks-v1 -->` marker). Run `/optimus-cycle-migrate` to convert it."

The report agent still ATTEMPTS to parse and display data even without the marker (best effort), but shows the warning prominently.

### Step 1.1.2: Default Branch Warning

Detect if the report is being run on the default branch:

```bash
DEFAULT_BRANCH=$(git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's@^refs/remotes/origin/@@')
CURRENT_BRANCH=$(git branch --show-current)
```

If `CURRENT_BRANCH` equals `DEFAULT_BRANCH` (or is `main`/`master`):

1. **Check for active feature branches:** Scan the Branch column of all tasks in the table.
   For each task where Branch is NOT `-`, check if that branch exists locally:
   ```bash
   git branch --list "<branch>"
   ```
2. **If any active branches are found**, display a warning at the TOP of the dashboard
   (before any tables or metrics):
   ```
   WARNING: You are on the default branch (main). Status changes made on feature
   branches are not visible here until their PRs are merged. The following tasks
   may have a more advanced status on their feature branches:
   ```
   Then list each task with an active branch, marking it with `*`:
   ```
   - T-003 (Pendente*) — branch feat/t-003-user-auth exists locally
   - T-005 (Pendente*) — branch fix/t-005-login-bug exists locally
   ```
3. **In all dashboard tables**, append `*` to the Status of any task that has an active
   feature branch. Example: `Pendente*` instead of `Pendente`.
4. **Add a legend** to the dashboard: `* = task has an active feature branch; status may be more advanced there`

If NOT on the default branch, skip this step silently.

### Step 1.2: Parse the Tasks Table

Read `tasks.md` and extract the markdown table. Expected columns:

| Column | Description |
|--------|-------------|
| ID | Task identifier (e.g., T-001) |
| Title | Short description |
| Tipo | Task type: Feature, Fix, Refactor, Chore, Docs, or Test |
| Status | Current status (Pendente, Validando Spec, Em Andamento, Validando Impl, Revisando PR, **DONE**, Cancelado) |
| Depends | Comma-separated dependency IDs, or `-` for none |
| Priority | Alta, Media, or Baixa |
| Version | Version/milestone this task belongs to |
| Branch | Git branch name, or `-` |
| Estimate | Task size estimate (S, M, L, XL, etc.), or `-` |

### Step 1.2.1: Parse Versions Table

Read the `## Versions` section and extract the versions table. Expected columns:
- Version (name), Status (`Ativa`, `Próxima`, `Planejada`, `Backlog`, `Concluída`), Description

Identify the version with Status `Ativa` — this is the **active version** used for default filtering.

For each task, also check if an H2 section exists below the table (`## T-NNN: Title`) to verify completeness.

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
2. Find tasks with status other than `Pendente`, `**DONE**`, and `Cancelado` (active tasks)
3. For each active task, read its detail section and count checked vs total acceptance criteria
4. Present ONLY:

```
Quick Status:
  Active: T-XXX — [title] (Em Andamento) — 3/5 criteria done
  Next up: T-YYY — [title] (Pendente, ready to start)
```

5. **STOP here** — do NOT proceed to the remaining phases (dependency graph, parallelization, velocity, etc.)

If the invocation does NOT match quick status triggers, proceed to Phase 3 normally.

---

## Phase 3: Classify Tasks

Classify each task into one of these categories:

### Done
Status is `**DONE**`.

### Cancelled
Status is `Cancelado`. These tasks were abandoned and will not be implemented.
Show in a separate section — do NOT count them in progress calculations.

### Active
Status is anything other than `Pendente`, `**DONE**`, or `Cancelado`:
- `Validando Spec` (cycle-spec-stage-1 running)
- `Em Andamento` (cycle-impl-stage-2 running)
- `Validando Impl` (cycle-impl-review-stage-3 running)
- `Revisando PR` (cycle-pr-review-stage-4 running)

### Ready to Start
Status is `Pendente` AND all dependencies are `**DONE**` (or no dependencies).

### Blocked
Status is `Pendente` AND at least one dependency is NOT `**DONE**` or is `Cancelado`.
Record which dependencies are blocking (note if a blocker is `Cancelado` — the dependency
should be removed or replaced).

---

## Phase 4: Version Filtering

**Default behavior:** If a `## Versions` section exists and a version has Status `Ativa`,
the dashboard shows **only tasks from the active version** by default.

**Override:** If the user specifies a version (e.g., "show status for v2") or asks for
"all tasks", show accordingly. If the user says "show all", display all versions.

**When filtering by a specific version:**
- All subsequent phases (dependency graph, parallelization, dashboard tables) only include
  tasks from that version
- Cross-version dependencies are shown as external references (e.g., "depends on T-001 [MVP, DONE]")

---

## Phase 5: Version Progress Summary

Compute progress for each version, regardless of filtering.
**Cancelled tasks are excluded from progress calculations** — they do not count toward
the total, done, active, or pending numbers. Progress = Done / (Total - Cancelled).

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
- Use `●` for active tasks
- Use `○` for ready-to-start tasks
- Use `⊘` for blocked tasks
- Use `✗` for cancelled tasks
- Use `─►` for dependency arrows
- Use `┬`, `├`, `└` for branching

Example:
```
T-001 ✓ ─┬─► T-002 ✓ ─┬─► T-004 ○
          │             │
          ├─► T-003 ○   ├─► T-005 ●
          │             │
          └─► T-006 ○   └─► T-008 ○

T-007 ◐ ────► T-009 ⊘ ────► T-010 ⊘

Legend: ✓=Done ●=Active ◐=Validating ○=Ready ⊘=Blocked ✗=Cancelled
```

For trees with depth > 3 levels, simplify by showing only the critical path and noting "N more tasks omitted".

---

## Phase 7: Identify Parallelization Opportunities

### Currently Parallelizable
Tasks that are `Pendente` with all dependencies `**DONE**`. These can ALL start right now, in parallel.

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
│  Legend: ✓=Done ●=Active ◐=Validating            │
│          ○=Ready ⊘=Blocked ✗=Cancelled           │
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

After the dashboard, compute velocity metrics from git history. These provide trend
data that a static snapshot (Phase 8) cannot show.

### Step 9.1: Compute Task Completion History

Search git log for task completion commits using multiple patterns to catch various
commit message formats:

```bash
# Pattern 1: Standard optimus format
git log --oneline --all --grep="chore(tasks): mark T-" --since="4 weeks ago" --format="%H %ai %s"

# Pattern 2: Keyword-based (mark + done)
git log --oneline --all --grep="mark T-" --grep="done" --all-match --since="4 weeks ago" --format="%H %ai %s"

# Pattern 3: Force-close format
git log --oneline --all --grep="force-close T-" --since="4 weeks ago" --format="%H %ai %s"

# Pattern 4: Status contains DONE
git log --oneline --all --grep="T-[0-9]" --grep="DONE" --all-match --since="4 weeks ago" --format="%H %ai %s"
```

Merge and deduplicate results from all patterns (same commit SHA = same event).

For each completed task found, extract: task ID, completion date.

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

**If no completion history is found** (new project, no tasks completed yet), show:
```
Velocity: No completed tasks in the last 4 weeks. Complete a task to start tracking.
```

### Step 9.3: Average Time Per Stage

If enough data exists (3+ completed tasks), compute average time spent in each stage
by analyzing git log timestamps for status change commits:

```bash
git log --oneline --all --grep="chore(tasks):" --format="%H %ai %s" | head -50
```

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

## Phase 10: Warnings and Recommendations

After the dashboard, present any issues found:

### Warnings
- Tasks with missing H2 detail sections
- Circular dependencies
- Invalid dependency references (pointing to non-existent task IDs)
- Tasks blocked by a cancelled dependency (see "Blocked by Cancelled" section below)
- Tasks stuck in the same status for too long (if git log shows no commits on their branch)

### Blocked by Cancelled Dependencies (guided resolution)

For each task that is blocked because a dependency has status `Cancelado`, present a
dedicated resolution guide:

```markdown
### Blocked by Cancelled Dependency

T-YYY depends on T-XXX, but T-XXX was cancelled (Cancelado).
Cancelled tasks do NOT satisfy dependencies — T-YYY cannot start.

**Resolution options (run `/optimus-cycle-crud` to apply):**
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
2. Find the corresponding task in tasks.md (match by Branch column)
3. Check the task's Status

Flag worktrees as potentially orphaned if:
- The task is `**DONE**` — worktree should have been cleaned up by cycle-close-stage-5
- The task is `Cancelado` — worktree should have been cleaned up by cycle-crud cancel
- The task is `Pendente` — worktree exists but task was never started or was reset
- No matching task found — worktree has no corresponding task in tasks.md

```
┌─────────────────────────────────────────────────┐
│ WORKSPACE HEALTH                                 │
├─────────────────────────────────────────────────┤
│ Active worktrees: N                              │
│                                                  │
│ ⚠ Potentially orphaned:                         │
│   /path/to/wt-t-003  →  T-003 (**DONE**)        │
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

```bash
mkdir -p .optimus
```

Write to `.optimus/report-<date>.md`:

```markdown
# Project Status Report — <date>

Generated by optimus-cycle-report

[full dashboard content]
```

Inform the user: "Report exported to `.optimus/report-<date>.md`"

**NOTE:** This is the ONLY case where cycle-report writes a file. The export file is
an artifact in `.optimus/` (gitignored), not a project file.

---

## Rules

- **NEVER modify project files** — this agent is strictly read-only (except export to `.optimus/`)
- **NEVER change task status** — only report current state
- **NEVER invoke other stage agents** — only recommend
- Present the full dashboard even if there's only 1 task
- If tasks.md has no table or invalid format, suggest running `/optimus-cycle-migrate` to convert it to the standard format
- If tasks.md does not exist, suggest running `/optimus-cycle-migrate` to create one from existing task files
- Always show the dependency graph, even for small projects — it reveals parallelization opportunities
