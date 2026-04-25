---
name: optimus-quick-report
description: "Compact daily status dashboard. Shows version progress, active tasks with current status, ready-to-start, and blocked tasks. Read-only -- this agent NEVER modifies any files."
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

**CRITICAL:** This agent NEVER modifies any files. It only reads and reports.

---

## Phase 1: Parse optimus-tasks.md

### Step 1.0: Resolve Paths and Git Scope

Execute AGENTS.md Protocol: Resolve Tasks Git Scope. This obtains `TASKS_DIR`,
`TASKS_FILE`, `TASKS_GIT_SCOPE`, `TASKS_GIT_REL`, and the `tasks_git` helper.

Execute AGENTS.md Protocol: Migrate tasks.md to tasksDir.
Informational only in read-only skills — emit a warning if a legacy
`.optimus/tasks.md` exists without a new location; do NOT auto-migrate from a
read-only skill.

Also check tasks.md → optimus-tasks.md rename — see AGENTS.md Protocol: Rename tasks.md to optimus-tasks.md.
Informational only in read-only skills — emit a warning if `<TASKS_DIR>/tasks.md`
exists with the optimus format marker but `<TASKS_DIR>/optimus-tasks.md` does not;
do NOT auto-rename from a read-only skill.

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
   CONFIG_FILE=".optimus/config.json"
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
   CONFIG_FILE=".optimus/config.json"
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


### Protocol: Migrate tasks.md to tasksDir

**Referenced by:** import, tasks, plan, build, review, done, resume, report, quick-report, batch, resolve, pr-check

Detects and migrates projects that have a legacy `.optimus/tasks.md` (versioned inside
`.optimus/`) to the new location `<tasksDir>/optimus-tasks.md`.

**Detection (run at the start of every skill that reads/writes the tasks tracking file):**

```bash
# Requires Protocol: Resolve Tasks Git Scope to have been executed first
# (TASKS_DIR, TASKS_FILE, TASKS_GIT_SCOPE, tasks_git available).
LEGACY_FILE=".optimus/tasks.md"
if [ -f "$LEGACY_FILE" ] && [ -f "$TASKS_FILE" ]; then
  # Partial/failed migration OR manual copy. Use new location but WARN the user.
  echo "WARNING: Both legacy ($LEGACY_FILE) and new ($TASKS_FILE) tracking files exist." >&2
  echo "         This indicates a partial prior migration or manual copy." >&2
  echo "         Using $TASKS_FILE. After confirming contents, remove the legacy file." >&2
  NEEDS_MIGRATION=0
elif [ -f "$LEGACY_FILE" ] && [ ! -f "$TASKS_FILE" ]; then
  NEEDS_MIGRATION=1
else
  NEEDS_MIGRATION=0
fi
```

**Dry-run mode:** If the skill is running in dry-run (per Dry-Run Mode section above),
DO NOT offer migration and DO NOT execute any migration step. Emit the plan and proceed:

```
[DRY-RUN] Migration would be offered for this task:
[DRY-RUN]   Legacy: $LEGACY_FILE
[DRY-RUN]   New:    $TASKS_FILE
[DRY-RUN]   Scope:  $TASKS_GIT_SCOPE
[DRY-RUN]   Would use: git mv (same-repo) OR cp + two commits (separate-repo)
```

**Config.json team-shared values warning:** If `.optimus/config.json` is currently tracked
in git and contains values (e.g., `defaultScope`), migration will untrack it. The values
are preserved locally but no longer shared via git. Warn user BEFORE untracking:

```bash
if git ls-files --error-unmatch .optimus/config.json >/dev/null 2>&1; then
  if [ -f .optimus/config.json ]; then
    CONFIG_KEYS=$(jq -r 'keys | join(", ")' .optimus/config.json 2>/dev/null || echo "unknown")
    echo "WARNING: .optimus/config.json is currently tracked with values: $CONFIG_KEYS" >&2
    echo "         Untracking will make these per-user. Team members need to re-apply locally." >&2
    # AskUser: Proceed with untrack? / Keep tracked (deviates from Optimus convention)
  fi
fi
```

**If `NEEDS_MIGRATION=1`, ask the user via `AskUser`:**

```
A legacy tasks.md was found at .optimus/tasks.md. The new location is ${TASKS_FILE} (optimus-tasks.md).
Migrate now? (Recommended — keeping the old location will break other skills.)
```

Options:
- **Migrate now** — copy → add in target repo → remove from project repo
- **Skip this time** — continue with the legacy file (emit warning; this will break)
- **Abort** — stop the current command so you can migrate manually

**Migration flow (when user chooses "Migrate now"):**

**Symlink safety (HARD BLOCK):** refuse to migrate if source or destination is a symlink
(prevents arbitrary file-write via symlink target). Must run BEFORE the checkpoint write
so we don't leave an orphan marker if a symlink is detected:
```bash
if [ -L "$LEGACY_FILE" ] || [ -L "$TASKS_FILE" ]; then
  echo "ERROR: Source or destination is a symlink — refusing to migrate." >&2
  exit 1
fi
```

Checkpoint file: write `.optimus/.migration-in-progress` BEFORE starting. This marker
lets subsequent invocations detect interrupted migrations:

```bash
mkdir -p .optimus
printf '%s\n' "$TASKS_FILE" > .optimus/.migration-in-progress
```

**Scope-branched migration:** explicit `if` so the agent executes the correct branch:

```bash
if [ "$TASKS_GIT_SCOPE" = "same-repo" ]; then
  # Same-repo: atomic git mv in a single commit (preserves history via rename-detect).
  mkdir -p "$TASKS_DIR"
  if ! git mv "$LEGACY_FILE" "$TASKS_FILE"; then
    echo "ERROR: git mv failed. Migration aborted — no changes made." >&2
    rm -f .optimus/.migration-in-progress
    exit 1
  fi
  COMMIT_MSG_FILE=$(mktemp -t optimus.XXXXXX) || { echo "ERROR: mktemp failed" >&2; exit 1; }
  chmod 600 "$COMMIT_MSG_FILE"
  printf '%s' "chore(tasks): migrate legacy .optimus/tasks.md to ${TASKS_DIR}/optimus-tasks.md" > "$COMMIT_MSG_FILE"
  if ! git commit -F "$COMMIT_MSG_FILE"; then
    echo "ERROR: Commit failed. Reverting git mv..." >&2
    # Revert: restore legacy from HEAD, remove new from working tree
    git reset HEAD -- "$LEGACY_FILE" "$TASKS_FILE" 2>/dev/null
    git checkout HEAD -- "$LEGACY_FILE" 2>/dev/null
    rm -f "$TASKS_FILE"
    rm -f "$COMMIT_MSG_FILE" .optimus/.migration-in-progress
    exit 1
  fi
  rm -f "$COMMIT_MSG_FILE"
else
  # Separate-repo: two commits in two repos. Rollback is per-repo on failure.
  mkdir -p "$TASKS_DIR"
  if ! cp "$LEGACY_FILE" "$TASKS_FILE"; then
    echo "ERROR: cp failed. Migration aborted." >&2
    rm -f .optimus/.migration-in-progress
    exit 1
  fi
  # Commit #1: in tasks repo
  if ! tasks_git add "$TASKS_GIT_REL"; then
    echo "ERROR: tasks_git add failed. Rolling back..." >&2
    rm -f "$TASKS_FILE"
    rm -f .optimus/.migration-in-progress
    exit 1
  fi
  COMMIT_MSG_FILE=$(mktemp -t optimus.XXXXXX) || { echo "ERROR: mktemp failed" >&2; exit 1; }
  chmod 600 "$COMMIT_MSG_FILE"
  printf '%s' "chore(tasks): migrate legacy .optimus/tasks.md to ${TASKS_DIR}/optimus-tasks.md" > "$COMMIT_MSG_FILE"
  if ! tasks_git commit -F "$COMMIT_MSG_FILE"; then
    echo "ERROR: tasks_git commit failed. Rolling back..." >&2
    tasks_git reset HEAD -- "$TASKS_GIT_REL" 2>/dev/null
    rm -f "$TASKS_FILE"
    rm -f "$COMMIT_MSG_FILE" .optimus/.migration-in-progress
    exit 1
  fi
  rm -f "$COMMIT_MSG_FILE"
  # Commit #2: in project repo
  if ! git rm "$LEGACY_FILE"; then
    echo "ERROR: git rm failed in project repo. Tasks repo already committed." >&2
    echo "Manual cleanup needed: rm $LEGACY_FILE && git add -A && git commit" >&2
    rm -f .optimus/.migration-in-progress
    exit 1
  fi
  COMMIT_MSG_FILE=$(mktemp -t optimus.XXXXXX) || { echo "ERROR: mktemp failed" >&2; exit 1; }
  chmod 600 "$COMMIT_MSG_FILE"
  printf '%s' "chore(tasks): remove legacy .optimus/tasks.md (moved to separate tasks repo at ${TASKS_DIR})" > "$COMMIT_MSG_FILE"
  if ! git commit -F "$COMMIT_MSG_FILE"; then
    echo "ERROR: Commit failed in project repo. Tasks repo already committed." >&2
    echo "Manual cleanup needed: git commit after resolving." >&2
    rm -f "$COMMIT_MSG_FILE" .optimus/.migration-in-progress
    exit 1
  fi
  rm -f "$COMMIT_MSG_FILE"
fi
```

**Untrack `.optimus/config.json` if previously versioned** (legacy projects). Check
commit exit code; restore index on failure:

```bash
if git ls-files --error-unmatch .optimus/config.json >/dev/null 2>&1; then
  git rm --cached .optimus/config.json
  COMMIT_MSG_FILE=$(mktemp -t optimus.XXXXXX) || { echo "ERROR: mktemp failed" >&2; exit 1; }
  chmod 600 "$COMMIT_MSG_FILE"
  printf '%s' "chore: untrack .optimus/config.json (now gitignored)" > "$COMMIT_MSG_FILE"
  if ! git commit -F "$COMMIT_MSG_FILE"; then
    # Restore to index so user can retry
    git reset HEAD .optimus/config.json 2>/dev/null
    rm -f "$COMMIT_MSG_FILE"
    echo "ERROR: Failed to untrack config.json. Index restored." >&2
    # Do not exit — migration of optimus-tasks.md already succeeded; user can retry untrack
  else
    rm -f "$COMMIT_MSG_FILE"
  fi
fi
```

**Ensure `.gitignore` includes the operational-files block:**
Execute Protocol: Initialize .optimus Directory. Commit if `.gitignore` was modified.

**Post-migration validation:** Verify the migrated optimus-tasks.md still passes Format
Validation (see AGENTS.md Format Validation section). If it fails (e.g., legacy
file was manually edited and lacks a `## Versions` section), inform user and suggest
running `/optimus-import` to rebuild:

```bash
if ! grep -q '^<!-- optimus:tasks-v1 -->' "$TASKS_FILE"; then
  echo "WARNING: Migrated optimus-tasks.md does not have the optimus format marker." >&2
  echo "         Run /optimus-import to rebuild in the correct format." >&2
fi
if ! grep -q '^## Versions' "$TASKS_FILE"; then
  echo "WARNING: Migrated optimus-tasks.md has no ## Versions section." >&2
  echo "         Run /optimus-import to rebuild in the correct format." >&2
fi
```

**Migration success: clear checkpoint marker and log each step.**
```bash
rm -f .optimus/.migration-in-progress
echo "INFO: Migration completed successfully:" >&2
echo "  - Legacy location: $LEGACY_FILE" >&2
echo "  - New location:    $TASKS_FILE" >&2
echo "  - Git scope:       $TASKS_GIT_SCOPE" >&2
```

**Report success:**
```
Migration complete. optimus-tasks.md is now at ${TASKS_FILE}.
Remember to push both repos (project + tasks) when you're ready.
```

**Interrupted migration recovery (on skill startup):**

```bash
if [ -f .optimus/.migration-in-progress ]; then
  INTERRUPTED_FILE=$(cat .optimus/.migration-in-progress 2>/dev/null)
  echo "WARNING: Previous migration was interrupted. Expected target: $INTERRUPTED_FILE" >&2
  # AskUser: Retry migration / Clear marker / Abort
fi
```

**If user chose "Skip this time":** Emit a warning and proceed using the legacy location
for this invocation only. The skill MUST use `$LEGACY_FILE` as `$TASKS_FILE` for the
remainder of this execution.

**If user chose "Abort":** **STOP** the current command.

Skills reference this as: "Check legacy tasks.md migration — see AGENTS.md Protocol: Migrate tasks.md to tasksDir."


### Protocol: Rename tasks.md to optimus-tasks.md

**Referenced by:** import, tasks, plan, build, review, done, resume, report, quick-report, batch, resolve, pr-check

Detects and renames projects whose Optimus tracking file is at `<tasksDir>/tasks.md`
(the prior default name) to `<tasksDir>/optimus-tasks.md`. The format marker
(`<!-- optimus:tasks-v1 -->`) is unchanged — this protocol only renames the file on disk.

**Detection (run at the start of every skill that reads/writes the tasks tracking file,
AFTER Protocol: Migrate tasks.md to tasksDir):**

```bash
# Requires Protocol: Resolve Tasks Git Scope to have been executed first
# (TASKS_DIR, TASKS_FILE, TASKS_GIT_SCOPE, TASKS_GIT_REL, tasks_git available).
# TASKS_FILE already points to <tasksDir>/optimus-tasks.md.
OLD_TASKS_FILE="${TASKS_DIR}/tasks.md"
NEEDS_RENAME=0

# Symlink HARD BLOCK — refuse to inspect or operate on symlinked paths.
# Must run BEFORE detection (head -n 1 follows symlinks).
if [ -L "$OLD_TASKS_FILE" ] || [ -L "$TASKS_FILE" ]; then
  echo "ERROR: $OLD_TASKS_FILE or $TASKS_FILE is a symlink — refusing to inspect or rename." >&2
  exit 1
fi

if [ -f "$OLD_TASKS_FILE" ] && [ -f "$TASKS_FILE" ]; then
  if ! head -n 1 "$OLD_TASKS_FILE" 2>/dev/null | grep -q '^<!-- optimus:tasks-v1 -->'; then
    # OLD lacks the optimus marker — it is an unrelated file (Ring pre-dev's
    # Gate 7 tasks.md, etc.). The actual Optimus file is already at TASKS_FILE.
    NEEDS_RENAME=0
  else
    echo "ERROR: Both ${OLD_TASKS_FILE} and ${TASKS_FILE} exist and both appear to be Optimus tracking files." >&2
    echo "       Confirm which is current, remove the stale one, and re-run the skill." >&2
    exit 1
  fi
elif [ -f "$OLD_TASKS_FILE" ] && [ ! -f "$TASKS_FILE" ]; then
  # Only proceed if the legacy file actually has the optimus format marker — otherwise
  # it is some other unrelated tasks.md (e.g., Ring pre-dev's Gate 7 tasks.md) and
  # MUST NOT be touched.
  if head -n 1 "$OLD_TASKS_FILE" 2>/dev/null | grep -q '^<!-- optimus:tasks-v1 -->'; then
    NEEDS_RENAME=1
  fi
fi
```

If `NEEDS_RENAME=0`, the protocol is a no-op (either the new name already exists, the
legacy file is unrelated to optimus, or neither exists).

**Dry-run mode:** If the skill is running in dry-run (per Dry-Run Mode section above),
DO NOT execute the rename. Emit the plan and proceed:

```
[DRY-RUN] Rename would be offered for this task:
[DRY-RUN]   Old name: $OLD_TASKS_FILE
[DRY-RUN]   New name: $TASKS_FILE
[DRY-RUN]   Scope:    $TASKS_GIT_SCOPE
[DRY-RUN]   Would use: git mv (same-repo) OR tasks_git mv (separate-repo)
```

**If `NEEDS_RENAME=1`, ask the user via `AskUser`:**

```
The Optimus tracking file at $OLD_TASKS_FILE uses the previous default name.
Rename to $TASKS_FILE now? (Recommended — Ring pre-dev also produces a tasks.md
in this directory, so the previous name causes a collision.)
```

Options:
- **Rename now** — perform the rename and commit
- **Skip this time** — continue with the legacy name (emit warning; this will collide with Ring pre-dev)
- **Abort** — stop the current command so you can rename manually

**Rename flow (when user chooses "Rename now"):**

Checkpoint file: write `.optimus/.rename-in-progress` BEFORE starting. This marker
lets subsequent invocations detect interrupted renames:

```bash
mkdir -p .optimus
printf '%s\n' "$TASKS_FILE" > .optimus/.rename-in-progress
```

**Scope-branched rename:** explicit `if` so the agent executes the correct branch:

```bash
if [ "$TASKS_GIT_SCOPE" = "same-repo" ]; then
  # Same-repo: atomic git mv in a single commit (preserves history via rename-detect).
  if ! git mv "$OLD_TASKS_FILE" "$TASKS_FILE"; then
    echo "ERROR: git mv failed. Rename aborted — no changes made." >&2
    rm -f .optimus/.rename-in-progress
    exit 1
  fi
  COMMIT_MSG_FILE=$(mktemp -t optimus.XXXXXX) || { echo "ERROR: mktemp failed" >&2; exit 1; }
  chmod 600 "$COMMIT_MSG_FILE"
  printf '%s' "chore(tasks): rename tasks.md to optimus-tasks.md" > "$COMMIT_MSG_FILE"
  if ! git commit -F "$COMMIT_MSG_FILE"; then
    echo "ERROR: Commit failed. Reverting git mv..." >&2
    # Revert: restore old name from HEAD, remove new name from working tree
    git reset HEAD -- "$OLD_TASKS_FILE" "$TASKS_FILE" 2>/dev/null
    git checkout HEAD -- "$OLD_TASKS_FILE" 2>/dev/null
    rm -f "$TASKS_FILE"
    rm -f "$COMMIT_MSG_FILE" .optimus/.rename-in-progress
    exit 1
  fi
  rm -f "$COMMIT_MSG_FILE"
else
  # Separate-repo: rename via tasks_git mv, single commit in tasks repo.
  OLD_TASKS_GIT_REL=$(python3 -c "import os,sys; print(os.path.relpath(sys.argv[1], sys.argv[2]))" \
    "$OLD_TASKS_FILE" "$TASKS_REPO_ROOT" 2>/dev/null)
  if [ -z "$OLD_TASKS_GIT_REL" ]; then
    echo "ERROR: Failed to compute path for legacy file relative to tasks repo." >&2
    rm -f .optimus/.rename-in-progress
    exit 1
  fi
  if ! tasks_git mv "$OLD_TASKS_GIT_REL" "$TASKS_GIT_REL"; then
    echo "ERROR: tasks_git mv failed. Rename aborted — no changes made." >&2
    rm -f .optimus/.rename-in-progress
    exit 1
  fi
  COMMIT_MSG_FILE=$(mktemp -t optimus.XXXXXX) || { echo "ERROR: mktemp failed" >&2; exit 1; }
  chmod 600 "$COMMIT_MSG_FILE"
  printf '%s' "chore(tasks): rename tasks.md to optimus-tasks.md" > "$COMMIT_MSG_FILE"
  if ! tasks_git commit -F "$COMMIT_MSG_FILE"; then
    echo "ERROR: Commit failed in tasks repo. Manual cleanup needed:" >&2
    echo "  cd $TASKS_DIR && git reset HEAD -- $OLD_TASKS_GIT_REL $TASKS_GIT_REL" >&2
    echo "  git checkout HEAD -- $OLD_TASKS_GIT_REL && rm -f $TASKS_GIT_REL" >&2
    rm -f "$COMMIT_MSG_FILE" .optimus/.rename-in-progress
    exit 1
  fi
  rm -f "$COMMIT_MSG_FILE"
fi
```

**Rename success: clear checkpoint marker and log.**
```bash
rm -f .optimus/.rename-in-progress
echo "INFO: Rename completed successfully:" >&2
echo "  - Old name:  $OLD_TASKS_FILE" >&2
echo "  - New name:  $TASKS_FILE" >&2
echo "  - Git scope: $TASKS_GIT_SCOPE" >&2
```

**Post-rename validation:** Verify the moved file still passes Format Validation (see
AGENTS.md Format Validation section). If it fails (e.g., the legacy file was manually
edited and lost the marker), inform user and suggest running `/optimus-import` to rebuild:

```bash
# Post-rename validation — verify the moved file still passes Format Validation.
if ! grep -q '^<!-- optimus:tasks-v1 -->' "$TASKS_FILE"; then
  echo "WARNING: Renamed optimus-tasks.md does not have the optimus format marker." >&2
  echo "         Run /optimus-import to rebuild in the correct format." >&2
fi
if ! grep -q '^## Versions' "$TASKS_FILE"; then
  echo "WARNING: Renamed optimus-tasks.md has no ## Versions section." >&2
  echo "         Run /optimus-import to rebuild in the correct format." >&2
fi
```

**Report success:**
```
Rename complete. The tracking file is now at ${TASKS_FILE}.
Remember to push the tasks repo when you're ready.
```

**Interrupted rename recovery (on skill startup):**

```bash
if [ -f .optimus/.rename-in-progress ]; then
  INTERRUPTED_FILE=$(cat .optimus/.rename-in-progress 2>/dev/null)
  echo "WARNING: Previous rename was interrupted. Expected target: $INTERRUPTED_FILE" >&2
  # AskUser: Retry rename / Clear marker / Abort
fi
```

**If user chose "Skip this time":** Emit a warning and proceed using the legacy name
for this invocation only. The skill MUST use `$OLD_TASKS_FILE` as `$TASKS_FILE` for the
remainder of this execution.

**If user chose "Abort":** **STOP** the current command.

Skills reference this as: "Check optimus-tasks.md rename — see AGENTS.md Protocol: Rename tasks.md to optimus-tasks.md."


### Protocol: Resolve Tasks Git Scope

**Referenced by:** all stage agents (1-4), tasks, batch, resolve, import, resume, report, quick-report

Resolves `TASKS_DIR` (Ring pre-dev root) and `TASKS_FILE` (`<tasksDir>/optimus-tasks.md`), then
detects whether `tasksDir` lives in the same git repo as the project code or in a
**separate** git repo. Exposes a `tasks_git` helper function so skills can run git
commands on optimus-tasks.md uniformly regardless of scope.

```bash
# Step 1: Resolve tasksDir from config.json (if present) or fall back to default.
CONFIG_FILE=".optimus/config.json"
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
