---
name: optimus-import
description: "Import Ring pre-dev artifacts into optimus format. Reads task specs and subtasks, creates tasks.md with TaskSpec column linking to Ring source. Re-runnable — only imports what's new. Never deletes original files."
trigger: >
  - When user wants to adopt the optimus task pipeline on a project with Ring pre-dev output
  - When user says "import tasks", "import pre-dev", "migrate tasks", "setup task pipeline"
  - When plan can't find a valid tasks.md
skip_when: >
  - Project already has a valid tasks.md AND no new Ring pre-dev artifacts to import
  - No Ring pre-dev output exists (run Ring pre-dev first)
prerequisite: >
  - Ring pre-dev has been run (task specs exist in the configured tasksDir)
NOT_skip_when: >
  - "The project is small" -- Even small projects benefit from standardized task tracking.
  - "I'll just create tasks.md manually" -- Use /optimus-tasks for ad-hoc tasks; this skill is for Ring pre-dev import.
examples:
  - name: Import Ring pre-dev artifacts
    invocation: "Import pre-dev"
    expected_flow: >
      1. Resolve tasksDir from .optimus/config.json (or ask user)
      2. Discover task specs in <tasksDir>/tasks/
      3. Present inventory of Ring tasks found
      4. User confirms and chooses version assignment
      5. Create tasks.md with TaskSpec column
      6. Commit after approval
  - name: Re-run to import new Ring tasks
    invocation: "Import tasks"
    expected_flow: >
      1. Detect existing tasks.md in optimus format
      2. Discover new Ring pre-dev tasks not yet imported
      3. Present only new tasks
      4. Add to existing tasks.md
      5. Commit after approval
related:
  complementary:
    - optimus-report
    - optimus-plan
  sequence:
    after:
      - ring:pre-dev-full
      - ring:pre-dev-feature
    before:
      - optimus-report
      - optimus-plan
verification:
  manual:
    - All Ring pre-dev tasks discovered and presented
    - Proposal shown before any changes
    - tasks.md generated with TaskSpec column linking to Ring source
    - Original Ring files NOT deleted
---

# Ring Pre-Dev Importer

Reads Ring pre-dev artifacts and creates the optimus tracking layer: a `tasks.md` file
with a `TaskSpec` column linking each task to its Ring source. Never copies content
from Ring — only references it via the TaskSpec column.

**CRITICAL:** This agent NEVER deletes original Ring files. It creates/updates tasks.md,
leaving Ring pre-dev artifacts untouched.

**NOTE:** Configuration is stored in `.optimus/config.json` (gitignored, per-user):
- `tasksDir`: path to Ring pre-dev artifacts root (default: `docs/pre-dev`)
- Tasks file is always at `<tasksDir>/tasks.md` (derived from tasksDir)
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

### Step 1.3: Check Existing tasks.md

Check if `<TASKS_DIR>/tasks.md` exists (the new standard location).

**Migration check (HARD BLOCK):** Execute AGENTS.md Protocol: Migrate tasks.md to tasksDir.
If a legacy `.optimus/tasks.md` exists and `<TASKS_DIR>/tasks.md` does not, the protocol
offers migration before proceeding.

**If tasks.md exists in optimus format** (first line is `<!-- optimus:tasks-v1 -->`):
- Read existing tasks from the table
- Filter out Ring pre-dev tasks that are already imported (match by `TaskSpec` column
  value, not by title or ID)
- If ALL Ring tasks are already imported → "No new Ring artifacts to import." and **STOP**
- If some are new → continue with only the new tasks

**If tasks.md does not exist at the configured/default path**, scan the entire project
for any file named `tasks.md`:

```bash
find . -name tasks.md ! -path '*/node_modules/*' ! -path '*/.git/*' 2>/dev/null
```

For each file found, check the first line for the optimus format marker
(`<!-- optimus:tasks-v1 -->`). Present ALL results to the user:

```
I found N tasks.md files in this project:

| # | Path | Optimus format? | Tasks |
|---|------|-----------------|-------|
| 1 | docs/pre-dev/tasks.md | Yes | 42 tasks (27 done, 15 pending) |
| 2 | .optimus/tasks.md | Yes | Legacy location — will migrate |

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
- Parse the Versions table and carry it over to the new tasks.md
- Store this as `EXISTING_DATA` for use in Step 1.4
- Store the source file path as `EXISTING_FILE` for cleanup in Step 3.4

**If no tasks.md files are found**, continue (will create from scratch).

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

**NOTE:** Status and Branch are NOT stored in tasks.md. They live in `.optimus/state.json`
(gitignored). See AGENTS.md Protocol: State Management.

**When `EXISTING_DATA` is available** (from Step 1.3), match Ring pre-dev tasks to
existing tasks by TaskSpec path. For matched tasks,
carry over Depends, Priority, Version, and Estimate into tasks.md.

**Migration of Status/Branch from legacy format:** If `EXISTING_DATA` has columns named
"Status" or "Branch" (from an older tasks.md format), migrate them to state.json:
```bash
# For each task with non-Pendente status or non-empty branch in EXISTING_DATA:
STATE_FILE=".optimus/state.json"
if [ ! -f "$STATE_FILE" ]; then echo '{}' > "$STATE_FILE"; fi
if [ -z "$TASK_ID" ] || [ -z "$LEGACY_STATUS" ]; then
  echo "WARNING: Skipping migration for task with empty ID or status."
else
  if jq --arg id "$TASK_ID" --arg status "$LEGACY_STATUS" --arg branch "$LEGACY_BRANCH" \
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

For unmatched tasks (new in Ring but not in existing data), use defaults.

**IMPORTANT:** Do NOT match by task ID. IDs between Optimus and Ring are independent
(Optimus T-038 may reference Ring T-020). Always match by the Ring source file path.

**Note:** Tasks that exist in `EXISTING_DATA` but NOT in Ring pre-dev are carried over
as-is (they may have been created manually via `/optimus-tasks`). Present these to the
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

If tasks.md already exists, use the `Ativa` version by default. Ask via `AskUser`
if the user wants a different version.

### Step 1.6: Generate Specs for Tasks Without TaskSpec

If `EXISTING_DATA` contains tasks with `TaskSpec = -` (created via `/optimus-tasks`
without Ring pre-dev specs):

1. Count tasks without specs
2. Ask via `AskUser`:
   ```
   N tasks have no Ring pre-dev spec. Generate specs now?
   ```
   Options:
   - **Generate all** — invoke `ring:pre-dev-feature` for each task
   - **Skip** — keep TaskSpec as `-`, generate specs later
3. If "Generate all":
   - For each task, invoke `ring:pre-dev-feature` passing title and tipo
   - After Ring generates the spec, update the task's TaskSpec value
4. If Ring is not available, warn and keep TaskSpec as `-`

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

### Step 3.2: Write tasks.md

**If creating from scratch:**

Create `<TASKS_DIR>/tasks.md` (typically `docs/pre-dev/tasks.md`) with:
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
  if [ ! -f .optimus/config.json ]; then
    echo '{}' > .optimus/config.json
  fi
  if jq --arg dir "$TASKS_DIR" '.tasksDir = $dir' .optimus/config.json > .optimus/config.json.tmp; then
    mv .optimus/config.json.tmp .optimus/config.json
  else
    rm -f .optimus/config.json.tmp
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
    # Remove the existing file using the correct repo (project-repo for legacy
    # .optimus/tasks.md, tasks-repo for existing files inside tasksDir).
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
specs (via `/optimus-tasks` or re-running import), the old file can be removed by
re-running import.

Commit tasks.md using `tasks_git` (may be a different repo than the project repo in
separate-repo scope):

```bash
tasks_git add "$TASKS_GIT_REL"
COMMIT_MSG_FILE=$(mktemp)
printf 'chore(tasks): import Ring pre-dev tasks to optimus format\n\nImported N tasks from %s/tasks/.\nOriginal Ring files preserved.' "$TASKS_DIR" > "$COMMIT_MSG_FILE"
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
- **Tracking created:** <TASKS_DIR>/tasks.md
- **tasksDir:** <TASKS_DIR> (<same-repo|separate-repo>)
- **Ring files:** NOT modified

### Next Steps
1. Run `/optimus-tasks` to adjust dependencies and priorities
2. Run `/optimus-report` to see the dashboard
3. Run `/optimus-plan` on the first pending task
```

---

## Rules

- **NEVER delete or modify Ring pre-dev files** — only create/update tasks.md
- **NEVER copy content from Ring into tasks.md** — only reference via TaskSpec column
- **NEVER apply changes without user approval** — always present and confirm first
- **NEVER invent task content** — only extract titles from Ring source
- Ring pre-dev is the ONLY import source — generic formats (YAML, checklist, index) are not supported
- IDs between optimus and Ring are independent — Optimus T-038 may reference Ring T-020
- Task IDs must be unique — if duplicates found, warn the user before proceeding

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
├── tasks.md             # versioned — structural task data (NO status, NO branch)
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
  `docs/pre-dev`. The import and stage agents look for `tasks.md`, `tasks/`, and
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

**Tasks file** is always at `<tasksDir>/tasks.md` (derived from `tasksDir`).

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
2. **Tasks file:** `${tasksDir}/tasks.md` (derived, not configurable separately).
3. **If `<tasksDir>/tasks.md` not found:** **STOP** and suggest running `import` to create one.

Everything inside `.optimus/` is gitignored. The planning tree (`<tasksDir>/tasks.md`,
`<tasksDir>/tasks/`, `<tasksDir>/subtasks/`) is versioned (structural data shared with
the team) — but the repo that versions it depends on `tasksDir`: if `tasksDir` is inside
the project repo, it is committed alongside the code; if `tasksDir` is in a separate
repo, it is committed there.


### Valid Status Values (stored in state.json)

Status lives in `.optimus/state.json`, NOT in tasks.md. A task with no entry in
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


### Protocol: Initialize .optimus Directory

**Referenced by:** import, tasks, report (export), quick-report, batch, pr-check, deep-review, coderabbit-review, all stage agents (1-4) for session files

Before creating ANY file inside `.optimus/`, ensure the directory structure exists
and that the entire `.optimus/` tree is gitignored (it is 100% operational/per-user).

```bash
mkdir -p .optimus/sessions .optimus/reports .optimus/logs
if ! grep -q '^# optimus-operational-files' .gitignore 2>/dev/null; then
  printf '\n# optimus-operational-files\n.optimus/config.json\n.optimus/state.json\n.optimus/stats.json\n.optimus/sessions/\n.optimus/reports/\n.optimus/logs/\n' >> .gitignore
fi
# Log retention (idempotent — fires once per init): age-based + count-cap prune.
# Also duplicated in Protocol: Session State so stage agents (which call Session
# State but not Initialize Directory) get pruning at every phase transition.
# Both prune sites are no-ops on clean directories; running both is harmless.
find .optimus/logs -type f -name '*.log' -mtime +30 -delete 2>/dev/null
if [ -d .optimus/logs ]; then
  ls -1t .optimus/logs/*.log 2>/dev/null | tail -n +501 \
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
separately at `<tasksDir>/tasks.md` (and `<tasksDir>/tasks/`, `<tasksDir>/subtasks/`
for Ring specs) — see the File Location section above.

**NOTE:** If a legacy project has `.optimus/config.json` tracked in git (from before
this change), skills running the migration helper (see Protocol: Migrate tasks.md to
tasksDir) will offer to run `git rm --cached .optimus/config.json` so the local file
is preserved but untracked.

Skills reference this as: "Initialize .optimus directory — see AGENTS.md Protocol: Initialize .optimus Directory."


### Protocol: Migrate tasks.md to tasksDir

**Referenced by:** import, tasks, plan, build, review, done, resume, report, quick-report, batch

Detects and migrates projects that have a legacy `.optimus/tasks.md` (versioned inside
`.optimus/`) to the new location `<tasksDir>/tasks.md`.

**Detection (run at the start of every skill that reads/writes tasks.md):**

```bash
# Requires Protocol: Resolve Tasks Git Scope to have been executed first
# (TASKS_DIR, TASKS_FILE, TASKS_GIT_SCOPE, tasks_git available).
LEGACY_FILE=".optimus/tasks.md"
BOTH_EXIST=0
if [ -f "$LEGACY_FILE" ] && [ -f "$TASKS_FILE" ]; then
  # Partial/failed migration OR manual copy. Use new location but WARN the user.
  echo "WARNING: Both legacy ($LEGACY_FILE) and new ($TASKS_FILE) tasks.md exist." >&2
  echo "         This indicates a partial prior migration or manual copy." >&2
  echo "         Using $TASKS_FILE. After confirming contents, remove the legacy file." >&2
  NEEDS_MIGRATION=0
  BOTH_EXIST=1
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
A legacy tasks.md was found at .optimus/tasks.md. The new location is ${TASKS_FILE}.
Migrate now? (Recommended — keeping the old location will break other skills.)
```

Options:
- **Migrate now** — copy → add in target repo → remove from project repo
- **Skip this time** — continue with the legacy file (emit warning; this will break)
- **Abort** — stop the current command so you can migrate manually

**Migration flow (when user chooses "Migrate now"):**

Checkpoint file: write `.optimus/.migration-in-progress` BEFORE starting. This marker
lets subsequent invocations detect interrupted migrations:

```bash
mkdir -p .optimus
printf '%s\n' "$TASKS_FILE" > .optimus/.migration-in-progress
```

**Symlink safety (HARD BLOCK):** refuse to migrate if source or destination is a symlink
(prevents arbitrary file-write via symlink target):
```bash
if [ -L "$LEGACY_FILE" ] || [ -L "$TASKS_FILE" ]; then
  echo "ERROR: Source or destination is a symlink — refusing to migrate." >&2
  rm -f .optimus/.migration-in-progress
  exit 1
fi
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
  printf '%s' "chore(tasks): move tasks.md to tasksDir" > "$COMMIT_MSG_FILE"
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
  printf '%s' "chore(tasks): migrate tasks.md to tasksDir" > "$COMMIT_MSG_FILE"
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
  printf '%s' "chore: move tasks.md to separate tasks repo (${TASKS_DIR})" > "$COMMIT_MSG_FILE"
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
    # Do not exit — migration of tasks.md already succeeded; user can retry untrack
  else
    rm -f "$COMMIT_MSG_FILE"
  fi
fi
```

**Ensure `.gitignore` includes the operational-files block:**
Execute Protocol: Initialize .optimus Directory. Commit if `.gitignore` was modified.

**Post-migration validation:** Verify the migrated tasks.md still passes Format
Validation (see AGENTS.md Format Validation section). If it fails (e.g., legacy
file was manually edited and lacks a `## Versions` section), inform user and suggest
running `/optimus-import` to rebuild:

```bash
if ! grep -q '^<!-- optimus:tasks-v1 -->' "$TASKS_FILE"; then
  echo "WARNING: Migrated tasks.md does not have the optimus format marker." >&2
  echo "         Run /optimus-import to rebuild in the correct format." >&2
fi
if ! grep -q '^## Versions' "$TASKS_FILE"; then
  echo "WARNING: Migrated tasks.md has no ## Versions section." >&2
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
Migration complete. tasks.md is now at ${TASKS_FILE}.
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

Skills reference this as: "Check tasks.md migration — see AGENTS.md Protocol: Migrate tasks.md to tasksDir."


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
# TASKS_FILE is resolved via Protocol: Resolve Tasks Git Scope (<tasksDir>/tasks.md).
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
