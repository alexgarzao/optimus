---
name: optimus-quick-report
description: "Compact daily status dashboard. Shows version progress, active tasks with criteria progress, ready-to-start, and blocked tasks. Read-only -- this agent NEVER modifies any files."
trigger: >
  - When user asks for a quick project overview (e.g., "quick report", "quick status", "daily report", "resumo rapido")
  - When user wants a fast, compact status check without velocity or dependency graphs
skip_when: >
  - No tasks.md exists in the project
  - User wants the full dashboard with dependency graph, velocity, and workspace health (use optimus-cycle-report instead)
prerequisite: >
  - .optimus/tasks.md exists in the project
NOT_skip_when: >
  - "I already know the status" -- A quick glance catches tasks you forgot about.
  - "There's only one task" -- Even one task benefits from criteria progress visibility.
examples:
  - name: Daily status
    invocation: "Quick report"
    expected_flow: >
      1. Find and parse tasks.md
      2. Compute version progress, classify tasks
      3. Present compact dashboard
  - name: Resumo rapido
    invocation: "Resumo rapido"
    expected_flow: >
      1. Parse tasks.md
      2. Present compact dashboard
related:
  complementary:
    - optimus-cycle-report
  differentiation:
    - name: optimus-cycle-report
      difference: >
        optimus-cycle-report is the full dashboard with dependency graph, velocity
        metrics, workspace health, parallelization opportunities, and warnings.
        optimus-quick-report is a compact daily view focused on actionable status
        (what's active, what's ready, what's blocked) without git operations.
verification:
  manual:
    - Dashboard displays correctly
    - Criteria progress counts match tasks.md checkboxes
    - Blocked tasks correctly identified
---

# Quick Report

Compact daily status dashboard. Parses `tasks.md` and presents a focused overview:
version progress, active tasks with acceptance criteria progress, ready-to-start tasks,
and blocked tasks.

**CRITICAL:** This agent NEVER modifies any files. It only reads and reports.

---

## Phase 1: Parse tasks.md

### Step 1.1: Locate and Validate

Look for `.optimus/tasks.md`. If not found, inform the user and suggest `/optimus-cycle-migrate`.

Check the first line for `<!-- optimus:tasks-v1 -->`. If missing, warn but attempt best-effort parsing.

### Step 1.2: Parse Tables

1. Parse the `## Versions` table (Version, Status, Description)
2. Parse the tasks table (ID, Title, Tipo, Status, Depends, Priority, Version, Branch, Estimate)
3. Identify the `Ativa` version

### Step 1.3: Parse Criteria Progress

For each task with status other than `Pendente`, `**DONE**`, and `Cancelado`:
1. Find the detail section (`## T-NNN: Title`)
2. Count total checkboxes (`- [ ]` + `- [x]`)
3. Count checked checkboxes (`- [x]`)
4. Record as `checked/total`

---

## Phase 2: Classify Tasks

For each task:

- **Done:** Status is `**DONE**`
- **Cancelled:** Status is `Cancelado`
- **Active:** Status is `Validando Spec`, `Em Andamento`, `Validando Impl`, or `Revisando PR`
- **Ready:** Status is `Pendente` AND all dependencies are `**DONE**` (or Depends is `-`)
- **Blocked:** Status is `Pendente` AND at least one dependency is NOT `**DONE**`

---

## Phase 3: Present Dashboard

Present a compact text dashboard. No json-render, no ASCII art graphs.

### Format

```
PROJECT STATUS: <active-version> (<status>) — X/Y done (Z%)

ACTIVE (N):
  T-NNN <status>       — <title>              — X/Y criteria
  T-NNN <status>       — <title>              — X/Y criteria

READY (N):
  T-NNN [<priority>]   <title>
  T-NNN [<priority>]   <title>

BLOCKED (N):
  T-NNN <title>        ← T-XXX (<dep-status>)
  T-NNN <title>        ← T-XXX (<dep-status>), T-YYY (<dep-status>)
```

### Rules

1. **Version progress** shows the `Ativa` version. Progress = Done / (Total - Cancelled).
   If other versions have non-done tasks, show a one-line summary after the main status:
   ```
   Also: v2 (0/6), Futuro (0/3)
   ```

2. **Active tasks** are sorted by status advancement (Revisando PR first, then Validando Impl,
   Em Andamento, Validando Spec). Show criteria progress from Step 1.3.

3. **Ready tasks** are sorted by Priority (`Alta` > `Media` > `Baixa`), then by ID.

4. **Blocked tasks** show which dependency is blocking and its current status. If a blocker
   has status `Cancelado`, append `(Cancelado — remove dep via /optimus-cycle-crud)`.

5. **Omit empty sections.** If there are no active tasks, skip the ACTIVE section entirely.
   Same for READY and BLOCKED.

6. **If ALL tasks are done**, show:
   ```
   PROJECT STATUS: <version> — ALL DONE (X/X)
   ```

---

## Rules

- **NEVER modify any files** — read-only
- **NEVER run git commands** — this skill avoids git operations for speed
- **NEVER invoke other skills** — only report
- Present the dashboard even if there's only 1 task
- If tasks.md has no table or invalid format, suggest `/optimus-cycle-migrate`
