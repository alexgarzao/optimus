---
name: optimus-import
description: "Import Ring pre-dev artifacts into optimus format. Reads task specs and subtasks from Ring's pre-dev output, creates tracking overlays (tasks.md + T-NNN.md). Re-runnable — only imports what's new. Never deletes original files."
trigger: >
  - When user wants to adopt the optimus task pipeline on a project with Ring pre-dev output
  - When user says "import tasks", "import pre-dev", "migrate tasks", "setup task pipeline"
  - When plan can't find a valid tasks.md
skip_when: >
  - Project already has a valid tasks.md AND no new Ring pre-dev artifacts to import
  - No Ring pre-dev output exists (run Ring pre-dev first)
prerequisite: >
  - Ring pre-dev has been run (docs/pre-dev/tasks/ exists with task specs)
NOT_skip_when: >
  - "The project is small" -- Even small projects benefit from standardized task tracking.
  - "I'll just create tasks.md manually" -- Use /optimus-tasks for ad-hoc tasks; this skill is for Ring pre-dev import.
examples:
  - name: Import Ring pre-dev artifacts
    invocation: "Import pre-dev"
    expected_flow: >
      1. Discover docs/pre-dev/tasks/ and docs/pre-dev/subtasks/
      2. Present inventory of Ring tasks found
      3. User confirms and chooses version assignment
      4. Create tasks.md + overlay T-NNN.md files
      5. Commit after approval
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
    - tasks.md generated in correct optimus format
    - Overlay T-NNN.md files created with Fonte links
    - Original Ring files NOT deleted
---

# Ring Pre-Dev Importer

Reads Ring pre-dev artifacts (`docs/pre-dev/tasks/`, `docs/pre-dev/subtasks/`) and creates
the optimus tracking layer: `tasks.md` (status table) + `T-NNN.md` overlay files (Fonte
links). Never copies content from Ring — only references it.

**CRITICAL:** This agent NEVER deletes original files. It creates/updates tasks.md
and overlay files, leaving Ring pre-dev artifacts untouched.

**NOTE:** The output location is configurable. If `.optimus.json` has a `tasksFile` key,
use that path. Otherwise, default to `docs/tasks.md`. After import, register the
chosen path in `.optimus.json` so all agents find it.

---

## Phase 1: Discovery

### Step 1.1: Scan for Ring Pre-Dev Artifacts

Check for Ring pre-dev output:

```bash
ls docs/pre-dev/tasks/*.md 2>/dev/null
ls docs/pre-dev/subtasks/ 2>/dev/null
```

**If `docs/pre-dev/tasks/` does not exist or is empty:**
**STOP** — "No Ring pre-dev artifacts found. Run Ring pre-dev workflow first
(`ring:pre-dev-full` or `ring:pre-dev-feature`) to generate task specs."

**If found**, scan all task files in `docs/pre-dev/tasks/`:
1. Read each `.md` file
2. Extract the title from the first heading (`### T-NNN: <title>` or `# T-NNN: <title>`)
3. Extract acceptance criteria (checklist items)
4. Check if a subtasks directory exists at `docs/pre-dev/subtasks/T-NNN/`
5. If subtasks exist, list all `.md` files and read their headings

### Step 1.2: Check Existing tasks.md

Read `.optimus.json` for configured path, fallback to `docs/tasks.md`.

**If tasks.md exists in optimus format** (first line is `<!-- optimus:tasks-v1 -->`):
- Read existing task IDs from the table
- Filter out Ring pre-dev tasks that are already imported (match by Fonte link
  in existing `T-NNN.md` files, not by title or ID)
- If ALL Ring tasks are already imported → "No new Ring artifacts to import." and **STOP**
- If some are new → continue with only the new tasks

**If tasks.md does not exist at the configured/default path**, scan the entire project
for any file named `tasks.md`:

```bash
find . -name tasks.md -not -path '*/node_modules/*' -not -path '*/.git/*' 2>/dev/null
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
- **Ignore all** — create from scratch (all tasks start as Pendente with no dependencies, version will be asked in Step 1.4)

**Only optimus-format files are selectable.** Non-optimus files are shown for
transparency but cannot be selected.

**If the user chooses "Use #N":**
- Parse the selected file's task table and overlay files into a lookup map keyed by Ring source: `{ring_task_spec_path → {ID, Status, Depends, Priority, Version, Branch, Estimate}}`
  - For each task in the table, read its overlay file and extract the `## Fonte` → `Task spec` path
  - Tasks without an overlay or without a Fonte link are keyed by their ID as fallback
- Parse the Versions table and carry it over to the new tasks.md
- Store this as `EXISTING_DATA` for use in Step 1.3
- The existing file is NOT modified or deleted — only read

**If no tasks.md files are found**, continue (will create from scratch).

### Step 1.3: Build Task Inventory

For each Ring pre-dev task not yet imported:

| Field | Source | Default |
|-------|--------|---------|
| **ID** | Generate next available `T-NNN` | Sequential |
| **Title** | From Ring task spec heading | Required |
| **Tipo** | Infer from title prefix (`feat:` → Feature, `fix:` → Fix, etc.) | `Feature` |
| **Status** | From `EXISTING_DATA` if available, else `Pendente` | `Pendente` |
| **Depends** | From `EXISTING_DATA` if available, else `-` | `-` |
| **Priority** | From `EXISTING_DATA` if available, else `Media` | `Media` |
| **Version** | From `EXISTING_DATA` if available, else user-chosen (Step 1.4) | Required |
| **Branch** | From `EXISTING_DATA` if available, else `-` | `-` |
| **Estimate** | From `EXISTING_DATA` if available, else `-` | `-` |

**When `EXISTING_DATA` is available** (from Step 1.2), match Ring pre-dev tasks to
existing tasks by Fonte link — the Ring task spec path referenced in the overlay's
`## Fonte` section (e.g., `docs/pre-dev/tasks/task_001.md`). For matched tasks,
carry over Status, Depends, Priority, Version, Branch, and Estimate. For unmatched
tasks (new in Ring but not in existing data), use defaults.

**IMPORTANT:** Do NOT match by task ID. IDs between Optimus and Ring are independent
(Optimus T-038 may reference Ring T-020). Always match by the Ring source file path.

**Note:** Tasks that exist in `EXISTING_DATA` but NOT in Ring pre-dev are carried over
as-is (they may have been created manually via `/optimus-tasks`). Present these to the
user in the discovery summary as "Additional tasks (not in Ring pre-dev)" so the user
can decide whether to include them.

### Step 1.4: Version Setup

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

---

## Phase 2: Present Inventory

### Step 2.1: Show Discovery Summary

```markdown
## Ring Pre-Dev Discovery

### Tasks Found
| # | Ring Source | Title | Subtasks |
|---|-----------|-------|----------|
| 1 | task_001.md | Database & Migration Foundation | 5 files in T-001/ |
| 2 | task_002.md | Backend API Framework Setup | 8 files in T-002/ |
| 3 | task_003.md | User Authentication | 3 files in T-003/ |
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

### Step 3.1: Choose Output Location (first run only)

If tasks.md does not exist yet, ask via `AskUser`:

```
Where should I create tasks.md?
```

Options:
- **docs/tasks.md** (default)
- **Custom path** — user specifies

Store the chosen path as `TASKS_FILE`. Derive `TASKS_DIR = dirname(TASKS_FILE) + "/tasks/"`.

### Step 3.2: Write tasks.md

First initialize the tasks directory (see AGENTS.md Protocol: Initialize Tasks Directory).

**If creating from scratch:**

Create `TASKS_FILE` with:
1. Format marker: `<!-- optimus:tasks-v1 -->` (MUST be the first line)
2. H1 heading: `# Tasks`
3. `## Versions` section with the versions table (from Step 1.4)
4. The tasks table with all imported tasks

**If appending to existing:**

Add new rows to the existing table. Do not modify existing rows.

### Step 3.3: Create Overlay Files

For each imported task, create `TASKS_DIR/T-NNN.md`:

```markdown
# T-NNN: <title from Ring task spec>

## Fonte
**Task spec:** `docs/pre-dev/tasks/task_NNN.md`
**Subtasks:** `docs/pre-dev/subtasks/T-NNN/`
**Plano:** `docs/pre-dev/subtasks/T-NNN/PARALLEL-PLAN.md`

```

**Rules for overlay creation:**
- `## Fonte` links to Ring source files — paths are relative to project root
- If no subtasks directory exists, omit the Subtasks line
- If no PARALLEL-PLAN.md exists, omit that line

**IMPORTANT:** The overlay does NOT contain Objetivo or Critérios de Aceite. Agents
read those from the Ring source via the Fonte links.

### Step 3.4: Register in .optimus.json

If `TASKS_FILE` is NOT the default (`docs/tasks.md`), register it:

```bash
if [ ! -f .optimus.json ]; then
  echo '{}' > .optimus.json
fi
jq --arg path "$TASKS_FILE" '.tasksFile = $path' .optimus.json > .optimus.json.tmp && mv .optimus.json.tmp .optimus.json
```

### Step 3.5: Commit

```bash
git add "$TASKS_FILE" "$TASKS_DIR/" .optimus.json
git commit -m "chore: import Ring pre-dev tasks to optimus format

Imported N tasks from docs/pre-dev/tasks/.
Tasks file: $TASKS_FILE
Original Ring files preserved."
```

### Step 3.6: Final Summary

```markdown
## Import Complete

- **Tasks imported:** N
- **Ring source:** docs/pre-dev/tasks/ (N task specs, M subtask files)
- **Tracking created:** <TASKS_FILE> + <TASKS_DIR>/T-NNN.md overlays
- **Registered in:** .optimus.json
- **Ring files:** NOT modified

### Next Steps
1. Run `/optimus-tasks` to adjust dependencies and priorities
2. Run `/optimus-report` to see the dashboard
3. Run `/optimus-plan` on the first pending task
```

---

## Rules

- **NEVER delete or modify Ring pre-dev files** — only create optimus tracking files
- **NEVER copy content from Ring into overlay files** — only reference via Fonte links
- **NEVER apply changes without user approval** — always present and confirm first
- **NEVER invent task content** — only extract titles and subtask headings from Ring source
- Ring pre-dev is the ONLY import source — generic formats (YAML, checklist, index) are not supported
- IDs between optimus and Ring are independent — Optimus T-038 may reference Ring T-020
- Task IDs must be unique — if duplicates found, warn the user before proceeding
