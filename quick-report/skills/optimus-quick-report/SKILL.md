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
2. Parse the tasks table (ID, Title, Tipo, Depends, Priority, Version, Estimate, TaskSpec)
3. Read status and branch for each task from `.optimus/state.json` — see AGENTS.md Protocol: State Management. Tasks with no entry are `Pendente`.
4. Identify the `Ativa` version

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

- **NEVER modify any files** — read-only
- **NEVER run git commands** — this skill avoids git operations for speed
- **NEVER invoke other skills** — only report
- Present the dashboard even if there's only 1 task
- If tasks.md has no table or invalid format, suggest `/optimus-import`

<!-- INLINE-PROTOCOLS:START -->
## Shared Protocols (from AGENTS.md)

The following protocols are referenced by this skill. They are
extracted from the Optimus AGENTS.md to make this plugin self-contained.

### File Location

All Optimus files live in the `.optimus/` directory at the project root:

```
.optimus/
├── config.json          # versionado — tasksDir
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
| `DONE` | done | Completed |
| `Cancelado` | tasks, done | Task abandoned, will not be implemented |

**Administrative status operations** (managed by tasks, not by stage agents):
- **Reopen:** `DONE` → `Pendente` (remove entry from state.json) or `Em Andamento` (if worktree exists) — when a bug is found after close. Also accepts `Cancelado` → `Pendente` — when a cancellation decision is reversed.
- **Advance:** move forward one stage — when work was done manually outside the pipeline
- **Demote:** move backward one stage — when rework is needed after review
- **Cancel:** any non-terminal → `Cancelado` — task will not be implemented

These operations require explicit user confirmation.


### Protocol: State Management

**Referenced by:** all stage agents (1-4), tasks, report, quick-report, import, batch

All status and branch data is stored in `.optimus/state.json` (gitignored).

**Prerequisites:**

```bash
if ! command -v jq >/dev/null 2>&1; then
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
