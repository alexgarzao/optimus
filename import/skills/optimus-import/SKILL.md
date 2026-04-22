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

**NOTE:** Configuration is stored in `.optimus/config.json`:
- `tasksDir`: path to Ring pre-dev artifacts root (default: `docs/pre-dev`)
- Tasks file is always `.optimus/tasks.md` (not configurable)

---

## Phase 1: Discovery

### Step 1.1: Resolve tasksDir

Read `.optimus/config.json` for `tasksDir`. If not configured, ask the user:

```
Where are the Ring pre-dev artifacts located?
```

Options via `AskUser`:
- **docs/pre-dev** (default)
- **Custom path** — user specifies

Store as `TASKS_DIR`.

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

Check if `.optimus/tasks.md` exists.

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
| 1 | .optimus/tasks.md | Yes | 42 tasks (27 done, 15 pending) |
| 2 | docs/pre-dev/tasks.md | No | (Ring Gate 7 output) |

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
- If the existing file uses the old overlay format (no TaskSpec column), read each
  task's overlay file and extract `## Fonte` → `Task spec` path as the key instead
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
| **Status** | From `EXISTING_DATA` if available, else `Pendente` | `Pendente` |
| **Depends** | From `EXISTING_DATA` if available, else `-` | `-` |
| **Priority** | From `EXISTING_DATA` if available, else `Media` | `Media` |
| **Version** | From `EXISTING_DATA` if available, else user-chosen (Step 1.5) | Required |
| **Branch** | From `EXISTING_DATA` if available, else `-` | `-` |
| **Estimate** | From `EXISTING_DATA` if available, else `-` | `-` |
| **TaskSpec** | Path to Ring task spec, relative to `TASKS_DIR` | Required |

**When `EXISTING_DATA` is available** (from Step 1.3), match Ring pre-dev tasks to
existing tasks by TaskSpec path (or Fonte link for old-format files). For matched tasks,
carry over Status, Depends, Priority, Version, Branch, and Estimate. For unmatched
tasks (new in Ring but not in existing data), use defaults.

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

Create `.optimus/tasks.md` with:
1. Format marker: `<!-- optimus:tasks-v1 -->` (MUST be the first line)
2. H1 heading: `# Tasks`
3. `## Versions` section with the versions table (from Step 1.5)
4. The tasks table with all imported tasks, including the `TaskSpec` column

**If appending to existing:**

Add new rows to the existing table. Do not modify existing rows.

### Step 3.3: Register in .optimus/config.json

Register `tasksDir`:

```bash
if [ ! -f .optimus/config.json ]; then
  echo '{}' > .optimus/config.json
fi
jq --arg dir "$TASKS_DIR" '.tasksDir = $dir' .optimus/config.json > .optimus/config.json.tmp && mv .optimus/config.json.tmp .optimus/config.json
```

### Step 3.4: Cleanup and Commit

**If `EXISTING_FILE` was used as source** (from Step 1.3), check if all tasks have
a TaskSpec before deleting the old file:

```bash
if [ -n "$EXISTING_FILE" ] && [ "$EXISTING_FILE" != ".optimus/tasks.md" ]; then
  # Count tasks with TaskSpec = -
  MISSING_SPECS=$(grep -c '| - |$' .optimus/tasks.md 2>/dev/null || echo 0)
  if [ "$MISSING_SPECS" -gt 0 ]; then
    echo "WARNING: $MISSING_SPECS tasks still have no TaskSpec (TaskSpec = -)."
    echo "Keeping old file as reference until all specs are generated."
  else
    EXISTING_OVERLAY_DIR="$(dirname "$EXISTING_FILE")/tasks"
    git rm -r "$EXISTING_FILE" 2>/dev/null || rm -f "$EXISTING_FILE"
    git rm -r "$EXISTING_OVERLAY_DIR" 2>/dev/null || rm -rf "$EXISTING_OVERLAY_DIR"
  fi
fi
```

**The old file is only deleted when ALL tasks have a TaskSpec.** If any task has
`TaskSpec = -`, the old file is preserved as reference. After generating the missing
specs (via `/optimus-tasks` or re-running import), the old file can be removed by
re-running import.

```bash
git add .optimus/
git commit -m "chore: import Ring pre-dev tasks to optimus format

Imported N tasks from $TASKS_DIR/tasks/.
Original Ring files preserved."
```

### Step 3.5: Final Summary

```markdown
## Import Complete

- **Tasks imported:** N
- **Ring source:** <TASKS_DIR>/tasks/ (N task specs, M subtask files)
- **Tracking created:** .optimus/tasks.md
- **Registered in:** .optimus/config.json (tasksDir)
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
