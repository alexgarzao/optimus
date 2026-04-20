---
name: optimus-cycle-report
description: >
  Task status dashboard. Reads tasks.md, computes dependency graph, and presents
  a comprehensive project status report. Shows progress, active tasks, blocked tasks,
  ready-to-start tasks, dependency graph, and parallelization opportunities.
  Read-only — this agent NEVER modifies any files.
trigger: >
  - When user asks for project status (e.g., "show tasks", "project status", "what's ready?")
  - When user wants to know what can be parallelized
  - When user asks "what should I work on next?"
  - Before starting a new task (to see the full picture)
skip_when: >
  - No tasks.md exists in the project
  - User wants to run a specific stage agent (use that agent directly)
prerequisite: >
  - tasks.md exists in the project root or docs/ directory
NOT_skip_when: >
  - "I already know the status" → The dashboard shows dependencies and parallelization you might miss.
  - "There's only one task" → Even single tasks benefit from status verification.
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

## Phase 0: Find and Parse tasks.md

### Step 0.1: Locate tasks.md

Search for `tasks.md` in these locations (in order):
1. Project root: `./tasks.md` — **preferred**
2. Docs directory: `./docs/tasks.md` — fallback

If not found, inform the user and suggest: "No tasks.md found. Run `/optimus-cycle-migrate` to create one from existing task files, or create it manually following the optimus format."

### Step 0.1.1: Validate Format Marker

Check that the **first line** of `tasks.md` is `<!-- optimus:tasks-v1 -->`.

If missing, warn the user: "tasks.md exists but is not in optimus format (missing `<!-- optimus:tasks-v1 -->` marker). Run `/optimus-cycle-migrate` to convert it."

The report agent still ATTEMPTS to parse and display data even without the marker (best effort), but shows the warning prominently.

### Step 0.2: Parse the Tasks Table

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

### Step 0.2.1: Parse Versions Table

Read the `## Versions` section and extract the versions table. Expected columns:
- Version (name), Status (`Ativa`, `Próxima`, `Planejada`, `Backlog`, `Concluída`), Description

Identify the version with Status `Ativa` — this is the **active version** used for default filtering.

For each task, also check if an H2 section exists below the table (`## T-NNN: Title`) to verify completeness.

### Step 0.3: Validate Dependencies

For each task with dependencies:
1. Verify all referenced task IDs exist in the table
2. Check for circular dependencies (A→B→A)
3. If invalid dependencies found, report them as warnings in the dashboard

---

## Phase 1: Classify Tasks

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

## Phase 1.5: Version Filtering

**Default behavior:** If a `## Versions` section exists and a version has Status `Ativa`,
the dashboard shows **only tasks from the active version** by default.

**Override:** If the user specifies a version (e.g., "show status for v2") or asks for
"all tasks", show accordingly. If the user says "show all", display all versions.

**When filtering by a specific version:**
- All subsequent phases (dependency graph, parallelization, dashboard tables) only include
  tasks from that version
- Cross-version dependencies are shown as external references (e.g., "depends on T-001 [MVP, DONE]")

---

## Phase 1.6: Version Progress Summary

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

## Phase 2: Compute Dependency Graph

Build a directed acyclic graph (DAG) from the Depends column.

For the ASCII art graph:
- Use `✓` for done tasks
- Use `●` for active tasks
- Use `○` for ready-to-start tasks
- Use `⊘` for blocked tasks
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

Legend: ✓=Done ●=Active ◐=Validating ○=Ready ⊘=Blocked
```

For trees with depth > 3 levels, simplify by showing only the critical path and noting "N more tasks omitted".

---

## Phase 3: Identify Parallelization Opportunities

### Currently Parallelizable
Tasks that are `Pendente` with all dependencies `**DONE**`. These can ALL start right now, in parallel.

### Next Wave
For each active task, identify which blocked tasks it would unlock when completed.
Group by: "After T-XXX completes, these unlock: ..."

---

## Phase 4: Present Dashboard

Present the full dashboard using the format below. Use the `<json-render>` format when available for richer display, otherwise use the ASCII art format.

### ASCII Art Format

```
╔══════════════════════════════════════════════════════╗
║                  PROJECT STATUS                      ║
╠══════════════════════════════════════════════════════╣
║  Total: NN  │  Done: NN  │  Active: NN  │  Pending: NN  ║
╚══════════════════════════════════════════════════════╝

Progress: ████████░░░░░░░░░░░░ XX% (done/total)

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
│          ○=Ready ⊘=Blocked                       │
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
```

### json-render Format

Also generate a `<json-render>` dashboard with these components:
- **Heading**: "Project Status"
- **ProgressBar**: overall completion (done/total)
- **Metric**: Total, Done, Active, Pending counts
- **Table**: Active tasks (columns: ID, Title, Version, Status)
- **Table**: Ready to start (columns: ID, Title, Version, Priority)
- **Table**: Blocked (columns: ID, Title, Version, Blocked by)
- **List**: Parallelization opportunities
- **StatusLine**: one per active task (success=done, info=active, warning=blocked, error=failed)

Present BOTH formats: the ASCII art first (always readable), then the json-render (for rich terminal).

---

## Phase 5: Warnings and Recommendations

After the dashboard, present any issues found:

### Warnings
- Tasks with missing H2 detail sections
- Circular dependencies
- Invalid dependency references (pointing to non-existent task IDs)
- Tasks stuck in the same status for too long (if git log shows no commits on their branch)

### Recommendations
- Suggest which ready tasks to start next (highest priority first)
- If multiple tasks are parallelizable, mention it explicitly
- If a single active task is blocking many others, highlight it as a bottleneck

---

## Rules

- **NEVER modify any files** — this agent is strictly read-only
- **NEVER change task status** — only report current state
- **NEVER invoke other stage agents** — only recommend
- Present the full dashboard even if there's only 1 task
- If tasks.md has no table or invalid format, suggest running `/optimus-cycle-migrate` to convert it to the standard format
- If tasks.md does not exist, suggest running `/optimus-cycle-migrate` to create one from existing task files
- Always show the dependency graph, even for small projects — it reveals parallelization opportunities
