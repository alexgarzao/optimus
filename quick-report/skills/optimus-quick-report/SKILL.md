---
name: optimus-quick-report
description: "Compact daily status dashboard. Shows version progress, active tasks with current status, ready-to-start, and blocked tasks. Mostly read-only — only writes .optimus/config.json defaultScope when user opts in."
trigger: >
  - When user asks for a quick project overview (e.g., "quick report", "quick status", "daily report", "resumo rapido")
  - When user wants a fast, compact status check without velocity or dependency graphs
skip_when: >
  - No optimus-tasks.md exists in the project
  - User wants the full dashboard with dependency graph, velocity, and workspace health (use optimus-report instead)
prerequisite: >
  - <tasksDir>/optimus-tasks.md exists in the project (default tasksDir: docs/pre-dev)
NOT_skip_when: >
  - "I already know the status" -- A quick glance catches tasks you forgot about.
  - "There's only one task" -- Even one task benefits from status visibility.
examples:
  - name: Daily status
    invocation: "Quick report"
    expected_flow: >
      1. Find and parse optimus-tasks.md
      2. Compute version progress, classify tasks
      3. Present compact dashboard
  - name: Resumo rapido
    invocation: "Resumo rapido"
    expected_flow: >
      1. Parse optimus-tasks.md
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

Compact daily status dashboard. Parses `optimus-tasks.md` and presents a focused overview:
version progress, active tasks with current status, ready-to-start tasks,
and blocked tasks.

**CRITICAL:** This agent is mostly read-only. The ONE allowed write is
`.optimus/config.json` `defaultScope` when the user explicitly opts in (see
`Protocol: Default Scope Resolution` in AGENTS.md). It NEVER modifies
`optimus-tasks.md`, `state.json`, code, or any other project file.

---

## Phase 1: Parse optimus-tasks.md

### Step 1.0: Resolve Paths and Git Scope

Execute AGENTS.md Protocol: Resolve Tasks Git Scope. This obtains `TASKS_DIR`,
`TASKS_FILE`, `TASKS_GIT_SCOPE`, `TASKS_GIT_REL`, and the `tasks_git` helper.

### Step 1.1: Locate and Validate

Tasks file is always at `<tasksDir>/optimus-tasks.md` (derived from `tasksDir`, default `docs/pre-dev`). If not found, inform the user and suggest `/optimus-import`.

Check the first line for `<!-- optimus:tasks-v1 -->`. If missing, warn but attempt best-effort parsing.

### Step 1.2: Parse Tables

1. Parse the `## Versions` table (Version, Status, Description)
2. Parse the tasks table (ID, Title, Tipo, Depends, Priority, Version, Estimate, TaskSpec)
3. Read status and branch for each task from `.optimus/state.json` — see AGENTS.md Protocol: State Management. Tasks with no entry are `Pendente`.
4. Identify the `Ativa` version

---

## Phase 2: Filter by Version and Classify Tasks

### Step 2.1: Determine Version Scope

Resolve the effective scope in this order — see AGENTS.md Protocol: Default Scope Resolution.

1. **Invocation wins.** If the user specified a scope in the invocation (e.g.,
   "quick report ativa", "quick report all", "quick report v2",
   "quick report upcoming"), use that scope directly. Skip sub-steps 2-4.

   **Force-ask keywords:** If the invocation contains `ask` or `menu` (e.g.,
   "quick report ask", "quick report menu"), skip sub-step 2 and go straight to the
   AskUser prompt (sub-step 3). Use this to override a saved default and optionally
   overwrite it.

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
   You can still override per-invocation (e.g., "quick report all") or use
   "quick report ask" to be prompted again.
   ```
   Options:
   - **Save as default** — write `defaultScope` to `.optimus/config.json`
   - **Just this time** — do not persist

   **Exception to the read-only rule:** writing `defaultScope` to `.optimus/config.json`
   is the ONLY side-effect this skill is allowed to perform, and only when the user
   explicitly chooses "Save as default".

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
- **Active:** Status is `Validando Spec`, `Em Andamento`, or `Validando Impl`
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

For active tasks, render a mini progress bar showing how far the task
has advanced through the pipeline. The mapping is:

| Status | Stage | Filled chars |
|--------|-------|-------------|
| `Validando Spec` | 1/3 | 1 |
| `Em Andamento` | 2/3 | 2 |
| `Validando Impl` | 3/3 | 3 |

Examples: `[█░░] 1/3`, `[██░] 2/3`, `[███] 3/3`

### Section Format

```
  ✓ DONE (N)
    T-NNN <title>
    T-NNN <title>

  ⚙ ACTIVE (N)
    T-NNN <status>       — <title>              [██░] 2/3
    T-NNN <status>       — <title>              [███] 3/3

  ◇ READY (N)
    T-NNN [<priority>]   <title>
    T-NNN [<priority>]   <title>

  ⊘ BLOCKED (N)
    T-NNN <title>
        ├── T-XXX [⚙ <dep-status>]
        └── T-YYY [◇ <dep-status>]
    T-NNN <title>
        └── T-XXX [✓ DONE pending refresh]
```

### Rules

1. **Version progress** shows the `Ativa` version. Progress = Done / (Total - Cancelled).
   The progress bar counts only tasks from the active version.

2. **All sections (DONE, ACTIVE, READY, BLOCKED)** show only tasks from the filtered
   version(s) selected in Step 2.2.

3. **Active tasks** are sorted by status advancement (Validando Impl first, then
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

- **NEVER modify any files** — read-only, with ONE exception: the user may opt in to
  persist their chosen scope to `.optimus/config.json` (see Step 2.1, sub-step 4).
  No other writes are allowed — no optimus-tasks.md, no state.json, no code.
- **NEVER run git commands** — this skill avoids git operations for speed
- **NEVER invoke other skills** — only report
- Present the dashboard even if there's only 1 task
- If optimus-tasks.md has no table or invalid format, suggest `/optimus-import`

<!-- INLINE-PROTOCOLS:START -->
## Shared Protocols (from AGENTS.md)

The following protocols are referenced by this skill. They are
extracted from the Optimus AGENTS.md to make this plugin self-contained.

<!-- INLINE-PROTOCOLS:END -->
