---
description: Import Ring pre-dev artifacts into optimus format. Reads task specs and subtasks, creates optimus-tasks.md with TaskSpec column linking to Ring source. Re-runnable — only imports what's new. Never deletes original files.
---

# Ring Pre-Dev Importer

Reads Ring pre-dev artifacts and creates the optimus tracking layer: a `optimus-tasks.md` file
with a `TaskSpec` column linking each task to its Ring source. Never copies content
from Ring — only references it via the TaskSpec column.

**CRITICAL:** This agent NEVER deletes original Ring files. It creates/updates optimus-tasks.md,
leaving Ring pre-dev artifacts untouched.

**NOTE:** Configuration is stored in `.optimus/config.json` (gitignored, per-user):
- `tasksDir`: path to Ring pre-dev artifacts root (default: `docs/pre-dev`)
- Tasks file is always at `<tasksDir>/optimus:tasks.md` (derived from tasksDir)
- `tasksDir` may point to a directory in the same repo as the project, OR to a
  path in a separate git repo (for teams that keep task tracking independent from code)

---

## Phase 1: Discovery

### Step 1.1: Resolve tasksDir and Git Scope

Execute Protocol: Resolve Tasks Git Scope (see AGENTS.md) to obtain `TASKS_DIR`,
`TASKS_FILE`, `TASKS_GIT_SCOPE`, `TASKS_GIT_REL`, and the `tasks_git` helper.

If `TASKS_DIR` could not be auto-resolved from config and the default (`docs/pre-dev`)
does not match the user's preference, ask via `AskUser`:

```
Where are the Ring pre-dev artifacts located?
```

Options via `AskUser`:
- **docs/pre-dev** (default)
- **Custom path** — user specifies (can be absolute or relative; may live in a
  separate git repo)

If the user picks a non-default path, persist it to `.optimus/config.json` (see Step 3.3).

**Validate path exists:** If the directory does not exist, offer to create it:
```bash
if [ ! -d "$TASKS_DIR" ]; then
  # AskUser: tasksDir does not exist. Create it?
  mkdir -p "$TASKS_DIR"
fi
```
If the user refuses, **STOP**: "tasksDir path `<TASKS_DIR>` does not exist."

### Step 1.2: Scan for Ring Pre-Dev Artifacts

Check for Ring pre-dev output in `<TASKS_DIR>/tasks/`:

```bash
ls "$TASKS_DIR/tasks/"*.md 2>/dev/null
```

**If `<TASKS_DIR>/tasks/` does not exist or is empty:**
**STOP** — "No Ring pre-dev artifacts found at `<TASKS_DIR>/tasks/`. Run Ring pre-dev
workflow first (`ring:pre-dev-full` or `ring:pre-dev-feature`) to generate task specs."

**If found**, scan all task files:
1. Read each `.md` file
2. Extract the title from the first heading (`### T-NNN: <title>` or `# T-NNN: <title>`)
3. Extract acceptance criteria (checklist items)
4. Check if a subtasks directory exists at `<TASKS_DIR>/subtasks/T-NNN/`
5. If subtasks exist, list all `.md` files and read their headings

### Step 1.3: Check Existing optimus-tasks.md

Check if `<TASKS_DIR>/optimus:tasks.md` exists (the new standard location).

**If optimus-tasks.md exists in optimus format** (first line is `<!-- optimus:tasks-v1 -->`):
- Read existing tasks from the table
- Filter out Ring pre-dev tasks that are already imported (match by `TaskSpec` column
  value, not by title or ID)
- If ALL Ring tasks are already imported → "No new Ring artifacts to import." and **STOP**
- If some are new → continue with only the new tasks

**If optimus-tasks.md does not exist at the configured/default path**, scan the entire project
for any file named `optimus-tasks.md` or legacy `tasks.md`:

```bash
find . \( -name optimus-tasks.md -o -name tasks.md \) ! -path '*/node_modules/*' ! -path '*/.git/*' 2>/dev/null
```

For each file found, check the first line for the optimus format marker
(`<!-- optimus:tasks-v1 -->`). Present ALL results to the user:

```
I found N task files in this project:

| # | Path | Optimus format? | Tasks |
|---|------|-----------------|-------|
| 1 | docs/pre-dev/optimus:tasks.md | Yes | 42 tasks (27 done, 15 pending) |

How should I proceed?
```

Options (via `AskUser`):
- **Use #N** — adopt the optimus-format file as the source for existing task data
- **Ignore all** — create from scratch (all tasks start as Pendente with no dependencies, version will be asked in Step 1.5)

**Only optimus-format files are selectable.** Non-optimus files are shown for
transparency but cannot be selected.

**If the user chooses "Use #N":**
- Parse the selected file's task table into a lookup map keyed by TaskSpec column:
  `{task_spec_path → {ID, Status, Depends, Priority, Version, Branch, Estimate}}`
- If the existing file does not have a TaskSpec column, match tasks by title similarity
  (>80% keyword overlap) as a fallback. Present potential matches to the user for confirmation
- Parse the Versions table and carry it over to the new optimus-tasks.md
- Store this as `EXISTING_DATA` for use in Step 1.4
- Store the source file path as `EXISTING_FILE` for cleanup in Step 3.4

**If no optimus-tasks.md files are found**, continue (will create from scratch).

### Step 1.4: Build Task Inventory

For each Ring pre-dev task not yet imported:

| Field | Source | Default |
|-------|--------|---------|
| **ID** | Generate next available `T-NNN` | Sequential |
| **Title** | From Ring task spec heading | Required |
| **Tipo** | Infer from title prefix (`feat:` → Feature, `fix:` → Fix, etc.) | `Feature` |
| **Depends** | From `EXISTING_DATA` if available, else `-` | `-` |
| **Priority** | From `EXISTING_DATA` if available, else `Media` | `Media` |
| **Version** | From `EXISTING_DATA` if available, else user-chosen (Step 1.5) | Required |
| **Estimate** | From `EXISTING_DATA` if available, else `-` | `-` |
| **TaskSpec** | Path to Ring task spec, relative to `TASKS_DIR` | Required |

**NOTE:** Status and Branch are NOT stored in optimus-tasks.md. They live in `.optimus/state.json`
(gitignored). See AGENTS.md Protocol: State Management.

**When `EXISTING_DATA` is available** (from Step 1.3), match Ring pre-dev tasks to
existing tasks by TaskSpec path. For matched tasks,
carry over Depends, Priority, Version, and Estimate into optimus-tasks.md.

**Migration of Status/Branch from legacy format:** If `EXISTING_DATA` has columns named
"Status" or "Branch" (from an older optimus-tasks.md format), migrate them to state.json:
```bash
# For each task with non-Pendente status or non-empty branch in EXISTING_DATA:
# Resolve main worktree first — see AGENTS.md Protocol: Resolve Main Worktree Path.
MAIN_WORKTREE="$(git worktree list --porcelain 2>/dev/null | awk '/^worktree / {print $2; exit}')"
if [ -z "$MAIN_WORKTREE" ]; then
  echo "ERROR: Cannot determine main worktree — not in a git repository." >&2
  exit 1
fi
STATE_FILE="${MAIN_WORKTREE}/.optimus/state.json"
if [ ! -f "$STATE_FILE" ]; then echo '{}' > "$STATE_FILE"; fi
if [ -z "$TASK_ID" ]; then
  echo "WARNING: Skipping migration for task with empty ID."
else
  # Validate legacy status against current valid set; default unknowns to Pendente.
  # Canonical list comes from AGENTS.md "Valid Status Values":
  # Pendente | Validando Spec | Em Andamento | Validando Impl | DONE | Cancelado.
  case "$LEGACY_STATUS" in
    Pendente|"Validando Spec"|"Em Andamento"|"Validando Impl"|DONE|Cancelado)
      NORMALIZED_STATUS="$LEGACY_STATUS"
      ;;
    "")
      NORMALIZED_STATUS="Pendente"
      ;;
    *)
      echo "  ⚠ Legacy status '${LEGACY_STATUS}' for ${TASK_ID} not recognized — defaulting to Pendente" >&2
      echo "    (was likely a removed status like 'Revisando PR'; recorded in migration summary)" >&2
      NORMALIZED_STATUS="Pendente"
      # Track normalized tasks for the summary report.
      NORMALIZED_TASKS="${NORMALIZED_TASKS:+$NORMALIZED_TASKS$'\n'}  - ${TASK_ID}: '${LEGACY_STATUS}' → 'Pendente'"
      ;;
  esac
  if jq --arg id "$TASK_ID" --arg status "$NORMALIZED_STATUS" --arg branch "$LEGACY_BRANCH" \
    --arg ts "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
    '.[$id] = {status: $status, branch: $branch, updated_at: $ts}' \
    "$STATE_FILE" > "${STATE_FILE}.tmp"; then
    mv "${STATE_FILE}.tmp" "$STATE_FILE"
  else
    rm -f "${STATE_FILE}.tmp"
    echo "ERROR: jq failed to update state.json during migration."
  fi
fi
```
After migration, inform the user: "Migrated N task statuses from legacy format to state.json."

**Surface normalized statuses in the import summary.** If `NORMALIZED_TASKS` is non-empty
after the migration loop, include a section like:

```
⚠ Status normalization (legacy values not in current valid set):
  - T-XXX: 'Revisando PR' → 'Pendente'
  - T-YYY: '<other-legacy>' → 'Pendente'

These tasks were defaulted to 'Pendente'. Use /optimus:tasks advance to move
them forward if work was already in progress.
```

For unmatched tasks (new in Ring but not in existing data), use defaults.

**IMPORTANT:** Do NOT match by task ID. IDs between Optimus and Ring are independent
(Optimus T-038 may reference Ring T-020). Always match by the Ring source file path.

**Note:** Tasks that exist in `EXISTING_DATA` but NOT in Ring pre-dev are carried over
as-is (they may have been created manually via `/optimus:tasks`). Present these to the
user in the discovery summary as "Additional tasks (not in Ring pre-dev)" so the user
can decide whether to include them.

### Step 1.5: Version Setup

**If `EXISTING_DATA` provides a Versions table**, carry it over — skip the version
question. All tasks inherit their Version from the existing data.

**If creating from scratch (no `EXISTING_DATA`)**, ask the user:

```
What version should I assign to the imported tasks?
```

Options via `AskUser`:
- **User-provided name** (e.g., "MVP", "v1") — creates it as `Ativa`
- **Backlog** — creates a "Backlog" version with Status `Backlog`

If optimus-tasks.md already exists, use the `Ativa` version by default. Ask via `AskUser`
if the user wants a different version.

### Step 1.6: Generate Specs for Tasks Without TaskSpec

If `EXISTING_DATA` contains tasks with `TaskSpec = -` (created via `/optimus:tasks`
without Ring pre-dev specs):

1. Count tasks without specs
2. Ask via `AskUser`:
   ```
   N tasks have no Ring pre-dev spec. How should I proceed?
   ```
   Options:
   - **Generate all via Ring** — invoke `ring:pre-dev-feature` for each task
   - **Generate selectively** — for each task, ask Generate via Ring / Link existing spec / Defer (per-task choice)
   - **Skip all** — keep TaskSpec as `-` for all; the next `/optimus:plan T-XXX` will offer to resolve
3. If "Generate all via Ring":
   - For each task, invoke `ring:pre-dev-feature` via the `Skill` tool. The Skill tool has no argument channel — state the task title and tipo in conversation context immediately before the invocation (e.g., "Generating spec for T-XXX: <title> (Tipo: <tipo>)"). Ring will read these from context.
   - After Ring generates the spec, update the task's TaskSpec value.
   - If Ring fails for a task, warn the user and keep that task's TaskSpec as `-` (the next `/optimus:plan T-XXX` will offer to resolve).
4. If "Generate selectively":
   - For each task with `TaskSpec = -`, ask via `AskUser`:
     ```
     [topic] (X/N) Task T-XXX (<title>) — how should I handle the spec?
     ```
     Options:
     - **Generate via Ring** (recommended) — invoke `ring:pre-dev-feature`
     - **Link existing spec** — search `<TASKS_DIR>/tasks/*.md`; pick from top 5 matches; **HARD BLOCK** validate the chosen path: (a) exists, (b) is a regular file (NOT a symlink), (c) resolves inside `<TASKS_DIR>` with no intermediate symlink components, (d) contains no pipe (`|`), control characters, newlines. Apply the realpath/case-glob/symlink rejection block from AGENTS.md Protocol: TaskSpec Resolution.
     - **Defer** — keep TaskSpec as `-`; the next `/optimus:plan T-XXX` will offer to resolve.
5. If "Skip all":
   - Keep TaskSpec as `-` for every task; inform the user that `/optimus:plan T-XXX` will offer to generate or link a spec when they next plan that task.
6. If Ring is not available at any point, warn and keep TaskSpec as `-` for the affected tasks.

---

## Phase 2: Present Inventory

### Step 2.1: Show Discovery Summary

```markdown
## Ring Pre-Dev Discovery

### Tasks Found
| # | Ring Source | Title | Subtasks |
|---|-----------|-------|----------|
| 1 | tasks/task_001.md | Database & Migration Foundation | 5 files in subtasks/T-001/ |
| 2 | tasks/task_002.md | Backend API Framework Setup | 8 files in subtasks/T-002/ |
| 3 | tasks/task_003.md | User Authentication | 3 files in subtasks/T-003/ |
| ... | ... | ... | ... |

### Summary
- **Ring tasks found:** N
- **Already imported:** M
- **New to import:** N-M
```

### Step 2.2: Confirm

Use `AskUser`:

```
I found N new Ring pre-dev tasks to import. Proceed?
```

Options:
- **Import all** — create tracking entries for all tasks
- **Select specific** — let me choose which tasks to import
- **Cancel** — don't import anything

**BLOCKING:** Do NOT write any file until the user approves.

---

## Phase 3: Create Tracking Layer

### Step 3.1: Initialize .optimus Directory

Initialize .optimus directory — see AGENTS.md Protocol: Initialize .optimus Directory.

### Step 3.2: Write optimus-tasks.md

**If creating from scratch:**

Create `<TASKS_DIR>/optimus:tasks.md` (typically `docs/pre-dev/optimus:tasks.md`) with:
1. Format marker: `<!-- optimus:tasks-v1 -->` (MUST be the first line)
2. H1 heading: `# Tasks`
3. `## Versions` section with the versions table (from Step 1.5)
4. The tasks table with all imported tasks, including the `TaskSpec` column

Ensure the directory exists first:
```bash
mkdir -p "$TASKS_DIR"
```

**If appending to existing:**

Add new rows to the existing table. Do not modify existing rows.

### Step 3.3: Register in .optimus/config.json (only if non-default)

`config.json` is gitignored and optional. Only create/update it if `TASKS_DIR` differs
from the hardcoded default (`docs/pre-dev`). If the user kept the default, skip this
step — skills resolve the default automatically:

```bash
if [ "$TASKS_DIR" != "docs/pre-dev" ]; then
  # Initialize .optimus directory — see AGENTS.md Protocol: Initialize .optimus Directory.
  # MAIN_WORKTREE was resolved in Step 1.3 (see line ~195); re-assert here so config.json
  # writes always land in the main worktree, not in a linked worktree's isolated copy.
  MAIN_WORKTREE="${MAIN_WORKTREE:-$(git worktree list --porcelain 2>/dev/null | awk '/^worktree / {print $2; exit}')}"
  MAIN_WORKTREE="${MAIN_WORKTREE:?MAIN_WORKTREE not resolved — not in a git repository}"
  if [ ! -f "${MAIN_WORKTREE}/.optimus/config.json" ]; then
    echo '{}' > "${MAIN_WORKTREE}/.optimus/config.json"
  fi
  if jq --arg dir "$TASKS_DIR" '.tasksDir = $dir' "${MAIN_WORKTREE}/.optimus/config.json" > "${MAIN_WORKTREE}/.optimus/config.json.tmp"; then
    mv "${MAIN_WORKTREE}/.optimus/config.json.tmp" "${MAIN_WORKTREE}/.optimus/config.json"
  else
    rm -f "${MAIN_WORKTREE}/.optimus/config.json.tmp"
    echo "ERROR: Failed to update config.json"
  fi
fi
```

### Step 3.4: Cleanup and Commit

**If `EXISTING_FILE` was used as source** (from Step 1.3), check if all tasks have
a TaskSpec before deleting the old file:

```bash
if [ -n "$EXISTING_FILE" ] && [ "$EXISTING_FILE" != "$TASKS_FILE" ]; then
  # Count tasks with TaskSpec = -
  MISSING_SPECS=$(grep -cE '\| -\s*\|\s*$' "$TASKS_FILE" 2>/dev/null || echo 0)
  if [ "$MISSING_SPECS" -gt 0 ]; then
    echo "WARNING: $MISSING_SPECS tasks still have no TaskSpec (TaskSpec = -)."
    echo "Keeping old file as reference until all specs are generated."
  else
    EXISTING_TASKS_DIR="$(dirname "$EXISTING_FILE")/tasks"
    # Remove the existing file using the correct repo: tasks-repo when the
    # file lives inside tasksDir, project-repo otherwise.
    PROJECT_ROOT=$(git rev-parse --show-toplevel)
    TASKS_REPO_ROOT=""
    if [ "$TASKS_GIT_SCOPE" = "separate-repo" ]; then
      TASKS_REPO_ROOT=$(git -C "$TASKS_DIR" rev-parse --show-toplevel 2>/dev/null || echo "")
    fi
    # Decide which repo owns EXISTING_FILE and EXISTING_TASKS_DIR based on
    # whether the path is inside PROJECT_ROOT or TASKS_REPO_ROOT.
    _remove_path() {
      local p="$1"
      case "$p" in
        "$PROJECT_ROOT"/*|"./"*)
          git rm -r "$p" 2>/dev/null || rm -rf "$p"
          ;;
        *)
          if [ -n "$TASKS_REPO_ROOT" ]; then
            case "$p" in
              "$TASKS_REPO_ROOT"/*)
                tasks_git rm -r "$p" 2>/dev/null || rm -rf "$p"
                ;;
              *)
                echo "ERROR: Path outside known repos — refusing to delete '$p'" >&2
                return 1
                ;;
            esac
          else
            echo "ERROR: Path outside project root — refusing to delete '$p'" >&2
            return 1
          fi
          ;;
      esac
    }
    _remove_path "$EXISTING_FILE" || true
    if [ -d "$EXISTING_TASKS_DIR" ]; then
      _remove_path "$EXISTING_TASKS_DIR" || true
    fi
  fi
fi
```

**The old file is only deleted when ALL tasks have a TaskSpec.** If any task has
`TaskSpec = -`, the old file is preserved as reference. After generating the missing
specs (via `/optimus:tasks` or re-running import), the old file can be removed by
re-running import.

Commit optimus-tasks.md using `tasks_git` (may be a different repo than the project repo in
separate-repo scope):

```bash
tasks_git add "$TASKS_GIT_REL"
COMMIT_MSG_FILE=$(mktemp)
printf 'chore(tasks): import Ring pre-dev tasks to optimus format\n\nImported N tasks into optimus-tasks.md from %s/tasks/.\nOriginal Ring files preserved.' "$TASKS_DIR" > "$COMMIT_MSG_FILE"
tasks_git commit -F "$COMMIT_MSG_FILE"
rm -f "$COMMIT_MSG_FILE"
```

If `config.json` was updated in Step 3.3 (non-default tasksDir), the change is local —
do NOT commit it (it's gitignored).

### Step 3.5: Final Summary

```markdown
## Import Complete

- **Tasks imported:** N
- **Ring source:** <TASKS_DIR>/tasks/ (N task specs, M subtask files)
- **Tracking created:** <TASKS_DIR>/optimus:tasks.md
- **tasksDir:** <TASKS_DIR> (<same-repo|separate-repo>)
- **Ring files:** NOT modified

### Next Steps
1. Run `/optimus:tasks` to adjust dependencies and priorities
2. Run `/optimus:report` to see the dashboard
3. Run `/optimus:plan` on the first pending task
```

---

## Rules

- **NEVER delete or modify Ring pre-dev files** — only create/update optimus-tasks.md
- **NEVER copy content from Ring into optimus-tasks.md** — only reference via TaskSpec column
  (note: Ring's own `tasks.md` is a different file at the same path; renaming the optimus
  tracking file to `optimus-tasks.md` resolves the collision)
- **NEVER apply changes without user approval** — always present and confirm first
- **NEVER invent task content** — only extract titles from Ring source
- Ring pre-dev is the ONLY import source — generic formats (YAML, checklist, index) are not supported
- IDs between optimus and Ring are independent — Optimus T-038 may reference Ring T-020
- Task IDs must be unique — if duplicates found, warn the user before proceeding

<!-- INLINE-PROTOCOLS:START -->
## Shared Protocols (from AGENTS.md)

The following protocols are referenced by this skill. They are
extracted from the Optimus AGENTS.md to make this plugin self-contained.

### File Location (summarized)

> **Summary inlined here. Full recipe at `AGENTS.md -> File Location`.**

**Summary:** Defines where Optimus operational files live: `${MAIN_WORKTREE}/.optimus/{state.json, stats.json, sessions/, reports/, logs/}` (gitignored, per-user) vs `<tasksDir>/optimus:tasks.md` + `<tasksDir>/{tasks,subtasks}/` (versioned, project-team-shared, propagated by git). Also: `${MAIN_WORKTREE}/.gitignore` (versioned), `${MAIN_WORKTREE}/.worktrees/` (gitignored linked-worktree dir). Critical contract: `.optimus/*` paths NEVER propagate across linked worktrees (gitignored = not shared by `git worktree add`); use `${MAIN_WORKTREE}/` prefix consistently. See full table in AGENTS.md.

Optimus splits its files into two trees:

### Valid Status Values (stored in state.json) (summarized)

> **Summary inlined here. Full recipe at `AGENTS.md -> Valid Status Values (stored in state.json)`.**

**Summary:** state.json status values: `Pendente` (implicit, no entry), `Validando Spec` (plan), `Em Andamento` (build), `Validando Impl` (review), `DONE` (done), `Cancelado` (tasks/done). Administrative ops (Reopen, Advance, Demote, Cancel) require explicit user confirmation. See full table + transitions in AGENTS.md.

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

### Task Spec Resolution

Every task SHOULD have a Ring pre-dev reference in the `TaskSpec` column. Tasks may be created with `TaskSpec=-` (deferred); the next `/optimus:plan` run will offer to generate or link a spec. Stage agents
(plan, build, review) resolve the full path as `<tasksDir>/<TaskSpec>` and read the
referenced file for objective, acceptance criteria, and implementation details.

The subtasks directory is derived automatically from the TaskSpec path:
- TaskSpec: `tasks/task_001.md` → Subtasks: `<tasksDir>/subtasks/T-001/`
- The `T-NNN` identifier is extracted from the task spec filename convention

Agents read objective and acceptance criteria directly from the Ring source files.
The optimus-tasks.md table only tracks structural data (dependencies, versions, priorities)
— it does NOT duplicate content from Ring.


### Protocol: Initialize .optimus Directory (summarized)

> **Summary inlined here. Full recipe at `AGENTS.md -> Protocol: Initialize .optimus Directory`.**

**Summary:** Create `${MAIN_WORKTREE}/.optimus/{sessions,reports,logs}/` with `mkdir -p`. Add `# optimus-operational-files` and `# optimus-operational-worktrees` markers to `${MAIN_WORKTREE}/.gitignore` idempotently (grep-anchor before append). Refuse symlinked `.gitignore`. Auto-prune `.optimus/logs/` (30 days, 500 files). See full recipe in AGENTS.md.

### Protocol: Resolve Main Worktree Path (summarized)

> **Summary inlined here. Full recipe at `AGENTS.md -> Protocol: Resolve Main Worktree Path`.**

**Summary:** Resolve `MAIN_WORKTREE` once via `git worktree list --porcelain | awk '/^worktree / {print $2; exit}'` with `${MAIN_WORKTREE:?…}` defensive guard. Use `${MAIN_WORKTREE}/.optimus/...` for ALL `.optimus/` paths (gitignored, so doesn't propagate across linked worktrees). See full recipe in AGENTS.md.

### Protocol: State Management (summarized)

> **Summary inlined here. Full recipe at `AGENTS.md -> Protocol: State Management`.**

**Summary:** Read/write/delete entries in `${MAIN_WORKTREE}/.optimus/state.json` with `jq`. Schema: `{task_id: {status, branch, updated_at}}`. Status values: `Pendente | Validando Spec | Em Andamento | Validando Impl | DONE | Cancelado`. All writes use `jq --arg id "$TASK_ID" --arg status "$NEW_STATUS" '.[$id] = {...}'` (injection-safe), with a tmp-file + `jq empty` validation step before `mv` to guarantee atomicity. Cancelado entries keep `branch: ""` (empty string, NOT absent — readers must treat both as Cancelado-state). Corrupted state.json is removed and treated as empty (reconciliation via worktree scan). state.json is gitignored; never committed. See full recipe in AGENTS.md for jq templates and reconciliation steps.

### Protocol: TaskSpec Resolution (summarized)

> **Summary inlined here. Full recipe at `AGENTS.md -> Protocol: TaskSpec Resolution`.**

**Summary:** Resolves the full path to a task's Ring pre-dev spec file by combining `<TASKS_DIR>` with the task's `TaskSpec` column from `optimus-tasks.md`. If `TaskSpec` is `-`, STOPs with a hint to run `/optimus:plan T-XXX`. HARD BLOCK on path traversal: resolves via `realpath -m` (or python3 `os.path.realpath` fallback) and rejects any result outside `$TASKS_DIR_ABS`. Also rejects symlinks (TOCTOU defence: realpath dereferences transparently, so a post-`-L` check guarantees no symlink in the final path). `TASKS_DIR` itself must be a valid git repo (enforced upstream by Resolve Tasks Git Scope) but is no longer required to live under `PROJECT_ROOT` — separate-repo scope is supported. Subtasks live at `<TASKS_DIR>/subtasks/T-NNN/`. See full recipe in AGENTS.md.

<!-- INLINE-PROTOCOLS:END -->
