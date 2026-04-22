---
name: optimus-quick-report
description: "Compact daily status dashboard. Shows version progress, active tasks with current status, ready-to-start, and blocked tasks. Read-only -- this agent NEVER modifies any files."
trigger: >
  - When user asks for a quick project overview (e.g., "quick report", "quick status", "daily report", "resumo rapido")
  - When user wants a fast, compact status check without velocity or dependency graphs
skip_when: >
  - No tasks.md exists in the project
  - User wants the full dashboard with dependency graph, velocity, and workspace health (use optimus-report instead)
prerequisite: >
  - .optimus/tasks.md exists in the project
NOT_skip_when: >
  - "I already know the status" -- A quick glance catches tasks you forgot about.
  - "There's only one task" -- Even one task benefits from status visibility.
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
    - optimus-report
  differentiation:
    - name: optimus-report
      difference: >
        optimus-report is the full dashboard with dependency graph, velocity
        metrics, workspace health, parallelization opportunities, and warnings.
        optimus-quick-report is a compact daily view focused on actionable status
        (what's active, what's ready, what's blocked) without git operations.
verification:
  manual:
    - Dashboard displays correctly
    - Blocked tasks correctly identified
---

# Quick Report

Compact daily status dashboard. Parses `tasks.md` and presents a focused overview:
version progress, active tasks with current status, ready-to-start tasks,
and blocked tasks.

**CRITICAL:** This agent NEVER modifies any files. It only reads and reports.

---

## Phase 1: Parse tasks.md

### Step 1.1: Locate and Validate

Tasks file is always at `.optimus/tasks.md`. If not found, inform the user and suggest `/optimus-import`.

Check the first line for `<!-- optimus:tasks-v1 -->`. If missing, warn but attempt best-effort parsing.

### Step 1.2: Parse Tables

1. Parse the `## Versions` table (Version, Status, Description)
2. Parse the tasks table (ID, Title, Tipo, Status, Depends, Priority, Version, Branch, Estimate, TaskSpec)
3. Identify the `Ativa` version

---

## Phase 2: Filter by Version and Classify Tasks

### Step 2.1: Determine Version Scope

**If the user specified a scope in the invocation** (e.g., "quick report ativa",
"quick report all", "quick report v2", "quick report upcoming"), use that scope
directly — skip the AskUser prompt.

**If the user did NOT specify a scope** (e.g., just "quick report" or "resumo rapido"),
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

### Step 2.2: Apply Filter

**Scope mapping:**

| Scope | Versions included |
|-------|-------------------|
| `ativa` | Only the version with Status `Ativa` |
| `upcoming` | Versions with Status `Ativa`, `Próxima`, or `Planejada` |
| `all` | All versions |
| `<version_name>` | Only the named version |

Filter the task list to include only tasks whose **Version** column matches the selected
scope. Tasks from other versions are excluded from the ACTIVE, READY, BLOCKED,
and DONE sections below.

**Cross-version dependencies:** When a filtered task depends on a task from another version,
show the dependency with its version in brackets (e.g., `T-001 [MVP, DONE]`).

### Step 2.3: Classify Filtered Tasks

For each task **in the filtered set**:

- **Done:** Status is `DONE`
- **Cancelled:** Status is `Cancelado`
- **Active:** Status is `Validando Spec`, `Em Andamento`, `Validando Impl`, or `Revisando PR`
- **Ready:** Status is `Pendente` AND all dependencies are `DONE` (or Depends is `-`)
- **Blocked:** Status is `Pendente` AND at least one dependency is NOT `DONE`

---

## Phase 3: Present Dashboard

Present a compact ASCII art dashboard. No json-render. Use box-drawing characters and
visual indicators to make task status immediately scannable.

### Version Progress Bar

Build an ASCII progress bar for the `Ativa` version. Width = 20 characters.
Filled chars = round(done / effective_total * 20). Effective total = Total - Cancelled.

```
═══════════════════════════════════════════════════
  <version> (<status>)  [████████████░░░░░░░░] Z% (X/Y)
═══════════════════════════════════════════════════
```

If other versions have non-done tasks, show a one-line summary below:
```
  Also: v2 (0/6), Futuro (0/3)
```

If ALL tasks are done:
```
═══════════════════════════════════════════════════
  <version>  [████████████████████] 100% (X/X) ALL DONE
═══════════════════════════════════════════════════
```

### Status Indicators

Each section uses a distinct ASCII symbol for instant visual recognition:

- **Active:** `⚙` (work in progress)
- **Ready:** `◇` (available, waiting to start)
- **Blocked:** `⊘` (cannot proceed)
- **Done:** `✓` (completed)

### Stage Progress Mini-Bar

For active tasks, render a mini progress bar (5 chars wide) showing how far the task
has advanced through the 5-stage pipeline. The mapping is:

| Status | Stage | Filled chars |
|--------|-------|-------------|
| `Validando Spec` | 1/5 | 1 |
| `Em Andamento` | 2/5 | 2 |
| `Validando Impl` | 3/5 | 3 |
| `Revisando PR` | 4/5 | 4 |

Examples: `[█░░░░] 1/5`, `[██░░░] 2/5`, `[███░░] 3/5`, `[████░] 4/5`

### Section Format

```
  ⚙ ACTIVE (N)
    T-NNN <status>       — <title>              [██░░░] 2/5
    T-NNN <status>       — <title>              [███░░] 3/5

  ◇ READY (N)
    T-NNN [<priority>]   <title>
    T-NNN [<priority>]   <title>

  ⊘ BLOCKED (N)
    T-NNN <title>
        ├── T-XXX [⚙ <dep-status>]
        └── T-YYY [◇ <dep-status>]
    T-NNN <title>
        └── T-XXX [✓ DONE pending refresh]

  ✓ DONE (N)
    T-NNN <title>
    T-NNN <title>
```

### Rules

1. **Version progress** shows the `Ativa` version. Progress = Done / (Total - Cancelled).
   The progress bar counts only tasks from the active version.

2. **All sections (ACTIVE, READY, BLOCKED, DONE)** show only tasks from the filtered
   version(s) selected in Step 2.2.

3. **Active tasks** are sorted by status advancement (Revisando PR first, then Validando Impl,
   Em Andamento, Validando Spec). Show stage progress mini-bar next to each task.

4. **Ready tasks** are sorted by Priority (`Alta` > `Media` > `Baixa`), then by ID.

5. **Blocked tasks** render dependencies as a tree using box-drawing characters.
   Each dependency appears on its own line with the appropriate status indicator symbol
   (`⚙` active, `◇` pending, `✓` done, `⊘` blocked, `✗` cancelled).
   Use `├──` for intermediate dependencies and `└──` for the last one.
   If a blocker has status `Cancelado`, show as `[✗ Cancelado — remove dep via /optimus-tasks]`.
   If a dependency is from another version, append the version: `[⚙ Em Andamento, v2]`.
   Example with multiple blockers:
   ```
     T-004 Password reset flow
         ├── T-002 [⚙ Em Andamento]
         └── T-003 [◇ Pendente]
   ```

6. **Omit empty sections.** If there are no active tasks, skip the ACTIVE section entirely.
   Same for READY, BLOCKED, and DONE.

7. **Progress bar characters:** Use `█` for filled and `░` for empty in the version
   progress bar (20 chars).

---

## Rules

- **NEVER modify any files** — read-only
- **NEVER run git commands** — this skill avoids git operations for speed
- **NEVER invoke other skills** — only report
- Present the dashboard even if there's only 1 task
- If tasks.md has no table or invalid format, suggest `/optimus-import`
