---
name: optimus-import
description: "Import external task artifacts into optimus format. Discovers existing task files, ring pre-dev artifacts (task specs, subtasks), and converts/links them. Re-runnable — only imports what's new. Never deletes original files."
trigger: >
  - When user wants to adopt the optimus task pipeline on an existing project
  - When user says "import tasks", "import pre-dev", "migrate tasks", "convert tasks", "setup task pipeline"
  - When plan can't find a valid tasks.md
skip_when: >
  - Project already has a valid tasks.md AND no new external artifacts to import
  - User wants to create tasks from scratch (just create the file manually)
prerequisite: >
  - Project has some form of task tracking (files, markdown, etc.)
NOT_skip_when: >
  - "The project is small" -- Even small projects benefit from standardized task tracking.
  - "I'll just create tasks.md manually" -- This agent handles edge cases you'd miss.
  - "Tasks are already in markdown" -- Markdown != optimus format. Columns, dependencies, and status need standardizing.
examples:
  - name: Import from index-only tasks.md
    invocation: "Import tasks to optimus format"
    expected_flow: >
      1. Discover tasks.md is an index (links to other files)
      2. Follow links, read individual task files
      3. Present inventory
      4. Propose consolidated tasks.md
      5. Apply after approval
  - name: Import from tasks/ directory with subtasks
    invocation: "Setup task pipeline"
    expected_flow: >
      1. Discover tasks/ directory with individual task files
      2. Discover subtasks/ directory
      3. Present inventory with subtask mapping
      4. Propose tasks.md with ring pre-dev references
      5. Apply after approval
  - name: Import ring pre-dev artifacts
    invocation: "Import pre-dev"
    expected_flow: >
      1. Discover docs/pre-dev/tasks/ and docs/pre-dev/subtasks/
      2. Match ring tasks to optimus tasks by keyword similarity
      3. Present matches for user confirmation
      4. Add Referencia Pre-Dev sections to detail files
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
    - All existing tasks discovered and presented
    - Conversion proposal shown before any changes
    - tasks.md generated in correct optimus format
    - Original files NOT deleted
---

# Task Importer

Discovers existing task files and ring pre-dev artifacts, converts them to the standard
optimus `tasks.md` format, and links rich pre-dev references (task specs, subtasks,
execution plans). Re-runnable — only imports what's new.

**CRITICAL:** This agent NEVER deletes original files. It creates/updates tasks.md
and leaves originals untouched. The user decides whether to remove them later.

**NOTE:** The output location is configurable. If `.optimus.json` has a `tasksFile` key,
use that path. Otherwise, default to `docs/tasks.md`. After import, register the
chosen path in `.optimus.json` so all agents find it.

---

## Phase 1: Discovery

### Step 1.1: Scan for Task Files

Search the project for any form of task tracking. First check `.optimus.json` for a
configured path, then scan known locations, then search recursively.

**Step 1 — Check configured path:**
```bash
CONFIGURED=$(cat .optimus.json 2>/dev/null | jq -r '.tasksFile // empty')
```
If `CONFIGURED` is set and the file exists with the optimus format marker, note it as
the target file. Do NOT stop — continue scanning for new external artifacts (ring
pre-dev refs, unlinked subtasks) that can be imported into the existing tasks.md.
If after full discovery no new artifacts are found, inform the user:
"Found configured tasks.md at `<path>`. No new artifacts to import." and **STOP**.

**Step 2 — Check known locations (in order):**
```
docs/tasks.md
./tasks.md
./docs/pre-dev/tasks.md
./TODO.md
./TASKS.md
./backlog.md
```

**Step 3 — Recursive search for any tasks.md:**
```bash
find . -name "tasks.md" -not -path "*/.git/*" -not -path "*/node_modules/*" -not -path "*/.optimus/*" 2>/dev/null
```

If multiple `tasks.md` files are found, present ALL to the user via `AskUser`:
```
Multiple tasks.md files found:
  1. docs/tasks.md (optimus format detected)
  2. project/tasks.md (plain markdown)
  3. src/tasks.md (checklist format)

Which one should be the primary tasks.md? (The others will be treated as import sources)
```

**Step 4 — Check known directories:**
```
./tasks/
./docs/tasks/
./docs/pre-dev/tasks/
./subtasks/
./docs/subtasks/
./docs/pre-dev/subtasks/
```

For each file/directory found, read its contents and classify it.

### Step 1.2: Classify Each Source

For each discovered file, determine its type:

| Type | How to detect | Example |
|------|--------------|---------|
| **Index-only** | tasks.md with links/references to other files but no task details inline | `- [T-001](./tasks/t-001.md)` |
| **Inline tasks** | tasks.md with full task descriptions (objectives, criteria) inside | H2 sections with content (legacy format) |
| **Table-only** | tasks.md with a markdown table but no detail sections | Just a table, no detail files |
| **Individual files** | tasks/ directory with one .md file per task | `tasks/t-001.md`, `tasks/t-002.md` |
| **Subtask files** | subtasks/ directory with subtask .md files | `subtasks/t-001-subtasks.md` |
| **YAML frontmatter** | Task files with YAML frontmatter (taskmd format) | `---\nid: "001"\nstatus: pending\n---` |
| **Checklist** | Simple TODO list with checkboxes | `- [ ] Implement auth\n- [x] Setup DB` |
| **Optimus format** | First line is `<!-- optimus:tasks-v1 -->` with standard table + `docs/tasks/T-NNN.md` detail files | Valid optimus tasks.md |

### Step 1.3: Extract Task Data

For each task found (regardless of format), extract:

| Field | How to find it | If missing |
|-------|---------------|------------|
| **ID** | Explicit ID (T-001), filename (001-task.md), heading number | Generate: T-001, T-002, ... |
| **Title** | H1/H2 heading, YAML `title:`, filename | Use first line of content |
| **Tipo** | YAML `type:`, labels, title prefix ("fix:", "feat:"), file naming | Default: `Feature` (see inference rules below) |
| **Status** | YAML `status:`, column in table, checkbox state | Default: `Pendente` |
| **Dependencies** | YAML `dependencies:`, "Depends on" text, "After T-XXX" | Default: `-` (none) |
| **Priority** | YAML `priority:`, explicit mention, position in file | Default: `Media` |
| **Version** | YAML `milestone:`, `version:`, labels, folder structure | Default: user-chosen version (see Step 1.5) |
| **Branch** | YAML `branch:`, git branch naming convention | Default: `-` |
| **Estimate** | YAML `estimate:`, `size:`, `effort:`, or explicit mention | Default: `-` |
| **Objective** | H2/H3 "Objetivo", "Objective", "Description" section | Use title as fallback |
| **Acceptance Criteria** | Checklist items, "Criteria", "Tasks" section | Leave empty, warn user |
| **Subtasks** | Files in subtasks/ referencing this task, nested checklists | Merge into criteria |

#### Status Inference Rules

When no explicit status exists, infer from available signals:

| Signal | Inferred status |
|--------|----------------|
| All checkboxes checked (`- [x]`) | `DONE` |
| Some checkboxes checked | `Em Andamento` |
| No checkboxes checked | `Pendente` |
| File mentions "completed", "done", "finished" | `DONE` |
| File mentions "in progress", "working on" | `Em Andamento` |
| YAML `status: done/completed/closed` | `DONE` |
| YAML `status: in_progress/active/started` | `Em Andamento` |
| YAML `status: pending/todo/backlog` | `Pendente` |
| File mentions "cancelled", "abandoned", "won't do" | `Cancelado` |
| YAML `status: cancelled/abandoned/wontfix/wont_do` | `Cancelado` |

#### Tipo Inference Rules

When no explicit type exists, infer from available signals:

| Signal | Inferred Tipo |
|--------|--------------|
| Title starts with "fix:", "bug:", "corrigir" | `Fix` |
| Title starts with "feat:", "add:", "implement" | `Feature` |
| Title starts with "refactor:", "refatorar", "melhorar" | `Refactor` |
| Title starts with "chore:", "config:", "ci:", "infra" | `Chore` |
| Title starts with "docs:", "documentar", "doc:" | `Docs` |
| Title starts with "test:", "testes", "e2e:" | `Test` |
| YAML `type: feature/feat/new` | `Feature` |
| YAML `type: bug/fix/hotfix` | `Fix` |
| YAML `type: refactor/improvement` | `Refactor` |
| YAML `type: chore/infra/ci/config` | `Chore` |
| YAML `type: docs/documentation` | `Docs` |
| YAML `type: test/testing` | `Test` |
| No signal found | `Feature` (default) |

#### Dependency Inference

When no explicit dependencies exist, look for implicit signals:
- "After T-001", "Requires T-003", "Blocked by T-002"
- Sequential numbering (T-001 before T-002) is NOT a dependency — don't infer from order
- If nothing found, set to `-` and let the user add dependencies manually

### Step 1.4: Handle Subtasks

Classify each subtask file by richness:

- **Simple subtasks** (< 20 lines AND no code blocks): merge as checklist items
  in the parent task's acceptance criteria section (inline).
- **Rich subtasks** (>= 20 lines OR contains code blocks/fenced blocks `` ``` ``):
  do NOT inline. These are handled in Step 1.4.1 as ring pre-dev references.

A file with code blocks (`` ``` ``) is always treated as rich regardless of line count.

**Simple subtasks example:**

**Before (subtasks/t-001-subtasks.md, 8 lines):**
```markdown
## Subtasks for T-001
- [ ] Define tables
- [ ] Add migrations
- [ ] Setup ORM
```

**After (inside detail file T-001.md):**
```markdown
**Critérios de Aceite:**
- [ ] Define tables
- [ ] Add migrations
- [ ] Setup ORM
```

### Step 1.4.1: Discover Ring Pre-Dev Artifacts

For each task discovered, search for rich pre-dev artifacts from the ring ecosystem:

**Step A — Search for matching ring task specs:**

1. Scan `docs/pre-dev/tasks/*.md` for task files
2. For each ring task file, extract the title from the first heading (`### T-NNN: <title>`)
3. Extract 3-5 significant keywords from the optimus task title (ignore articles,
   prepositions, and generic verbs like "criar", "implementar", "resolver", "add", "create")
4. Calculate keyword overlap between the optimus title and each ring title
5. Sort by number of matching keywords (descending)

**Step B — Present matches to user:**

If matches found (1+ keyword in common):
```
Task T-NNN: "<optimus title>"

Found ring pre-dev tasks that may be related:
  [1] task_020.md — "Painel UI Redesign (Sidebar + Topbar)" (3 keywords)
      Subtasks: 13 files in docs/pre-dev/subtasks/T-020/
  [2] task_022.md — "Formularios Responsivos com Abas" (1 keyword)

Link to one of these?
```
Options via `AskUser`:
- **[N] task_NNN.md** — link this ring task
- **Show all ring tasks** — list every task in docs/pre-dev/tasks/ for manual selection
- **None** — create without ring reference

If no matches found:
```
No ring pre-dev tasks found with similar title.
Link to an existing ring task?
```
Options:
- **Show all ring tasks** — list every task for manual selection
- **None** — create without ring reference

**Step C — "Show all" flow:**

If the user chooses "Show all ring tasks", present the complete list:
```
Ring pre-dev tasks (docs/pre-dev/tasks/):

  [ 1] task_001.md — "Database & Migration Foundation"
  [ 2] task_002.md — "Backend API Framework Setup"
  ...
  [35] task_035.md — "Resolver Issues Pendentes do DeepSource"

Which task to link? (number or "none")
```

**Step D — Generate reference section:**

When a ring task is linked:
1. Read the selected ring task file for title and metadata
2. Check if a subtasks directory exists at `docs/pre-dev/subtasks/T-NNN/`
3. If subtasks exist, read the heading (`# ST-NNN-NN: ...`) of each `.md` file
4. Check if `PARALLEL-PLAN.md` exists in the subtasks directory
5. Add a `## Referencia Pre-Dev` section to the detail file:

```markdown
## Referencia Pre-Dev

**Task spec:** `docs/pre-dev/tasks/task_NNN.md`
**Subtasks:** `docs/pre-dev/subtasks/T-NNN/`
**Plano de execucao:** `docs/pre-dev/subtasks/T-NNN/PARALLEL-PLAN.md`

| Fase | Arquivo | Descricao |
|------|---------|-----------|
| 0 | ST-NNN-01-design-tokens.md | Design Tokens — Brand + Severidade |
| 1 | ST-NNN-02-counter-card.md | CounterCard variantes |
| ... | ... | ... |
```

If no subtasks directory exists, omit the Subtasks and table lines.
If no PARALLEL-PLAN.md exists, omit that line.

**IMPORTANT:** IDs between optimus and ring are independent. Optimus T-038 may
reference ring T-020. The match is by keyword similarity, never by ID.

### Step 1.5: Version Setup

Since the Versions table is mandatory, ask the user for the default version to assign to imported tasks:

```
The optimus format requires a Versions table. What version should I assign to the imported tasks?
```

Options via `AskUser`:
- **User-provided name** (e.g., "MVP", "v1") — creates it as `Ativa`
- **Backlog** — creates a "Backlog" version with Status `Backlog`

If the source tasks have labels, milestones, or folder-based grouping that suggest version
assignments, infer them and present to the user for confirmation. Create a version for each
distinct group found.

Store the default version for Step 2.1 (tasks without inferred version get this default).

---

## Phase 2: Present Inventory

### Step 2.1: Show Discovery Summary

Present what was found to the user:

```markdown
## Task Discovery Summary

### Sources Found
| # | Location | Type | Tasks Found |
|---|----------|------|-------------|
| 1 | docs/tasks.md | Index-only | 8 links |
| 2 | ./tasks/ | Individual files | 8 files |
| 3 | ./subtasks/ | Subtask files | 5 files |

### Tasks Extracted
| ID | Title | Tipo (inferred?) | Status (inferred?) | Dependencies | Version | Estimate | Subtasks |
|----|-------|-------------------|-------------------|-------------|---------|----------|
| T-001 | Setup auth module | Feature (default) | DONE (inferred from checkboxes) | - | MVP (inferred) | 3 subtasks |
| T-002 | User registration | Feature (default) | Pendente (no status found) | T-001 (explicit) | MVP (default) | - |
| T-003 | Login page | Feature (default) | Pendente (no status found) | T-001 (inferred) | MVP (default) | 2 subtasks |
| ... | ... | ... | ... | ... | ... | ... |

### Warnings
- T-004: No acceptance criteria found — section will be empty
- T-006: Duplicate title with T-003 — please review
- subtasks/t-007-subtasks.md: References T-007 which doesn't exist
```

### Step 2.2: Ask for Adjustments

Use `AskUser` to confirm:

```
I found N tasks across M sources. Before converting:

1. Are the inferred statuses correct? (I can list them for review)
2. Should I attempt to infer dependencies from context, or set all to "-"?
3. Any tasks that should be excluded from migration?
```

**BLOCKING:** Wait for user confirmation before proceeding.

---

## Phase 3: Propose Conversion

### Step 3.1: Generate tasks.md Preview

Generate the complete `tasks.md` in optimus format and present it to the user:

```markdown
## Proposed tasks.md

### Table
| ID | Title | Tipo | Status | Depends | Priority | Version | Branch |
|----|-------|------|--------|---------|----------|---------|--------|
| T-001 | Setup auth module | Feature | DONE | - | Alta | MVP | - |
| T-002 | User registration | Feature | Pendente | T-001 | Alta | MVP | - |
| ... | ... | ... | ... | ... | ... | ... | ... |

### Detail Sections (first 2 shown as preview)

## T-001: Setup auth module

**Objetivo:** [extracted content]

**Critérios de Aceite:**
- [x] JWT middleware configurado
- [x] Testes unitários passando

## T-002: User registration

**Objetivo:** [extracted content]

**Critérios de Aceite:**
- [ ] Endpoint POST /api/users
- [ ] Email validation
```

### Step 3.2: Choose Output Location

Ask via `AskUser` where to write the tasks.md:

```
Where should I create tasks.md?
```

Options:
- **docs/tasks.md** (default) — standard location
- **Custom path** — specify a different location (e.g., `project/tasks.md`)
- If a source tasks.md was found during discovery, offer: **Keep at current location** (`<source-path>`)

Store the chosen path as `TASKS_FILE`. Derive `TASKS_DIR = dirname(TASKS_FILE) + "/tasks/"`.

### Step 3.3: Confirm Before Applying

Use `AskUser`:

```
Here's the proposed tasks.md with N tasks.
  Location: <TASKS_FILE>
  Detail files: <TASKS_DIR>/T-NNN.md

What should I do?
```

Options:
- **Apply**: Create/update tasks.md with this content
- **Edit first**: Let me adjust specific tasks before applying
- **Cancel**: Don't create anything

**BLOCKING:** Do NOT write any file until the user explicitly approves.

---

## Phase 4: Apply Conversion

### Step 4.1: Check for Existing tasks.md

If `TASKS_FILE` already exists in optimus format:
- Ask via `AskUser`: "`<TASKS_FILE>` already exists. Merge new tasks into it, or replace entirely?"
- If merge: add only tasks that don't already exist (match by ID or title)
- If replace: backup the existing file content (show it to the user first)

If `TASKS_FILE` exists in non-optimus format:
- Rename to `<TASKS_FILE>.bak` before creating the new one
- Inform the user: "Backed up original to `<TASKS_FILE>.bak`"

### Step 4.2: Write tasks.md and detail files

First initialize the tasks directory (see AGENTS.md Protocol: Initialize Tasks Directory).

Create `TASKS_FILE` with:
1. Format marker: `<!-- optimus:tasks-v1 -->` (MUST be the first line)
2. H1 heading: `# Tasks`
3. `## Versions` section with the versions table (from Step 1.5)
4. The tasks table (all columns including Version)

Create individual detail files `TASKS_DIR/T-NNN.md` for each task with:
1. H1 heading: `# T-NNN: <title>`
2. Objective and acceptance criteria (extracted content)

### Step 4.3: Register in .optimus.json

If `TASKS_FILE` is NOT the default (`docs/tasks.md`), register it in `.optimus.json`:

```bash
if [ ! -f .optimus.json ]; then
  echo '{}' > .optimus.json
fi
# Add or update tasksFile key
jq --arg path "$TASKS_FILE" '.tasksFile = $path' .optimus.json > .optimus.json.tmp && mv .optimus.json.tmp .optimus.json
```

If `TASKS_FILE` IS the default (`docs/tasks.md`), registration is optional (the default
is used when `tasksFile` is absent). Still register it if `.optimus.json` already exists
to be explicit.

### Step 4.4: Commit

```bash
git add "$TASKS_FILE" "$TASKS_DIR/" .optimus.json
git commit -m "chore: import tasks to optimus format (import)

Imported N tasks from [sources list].
Tasks file: $TASKS_FILE
Ring pre-dev references: [linked/none]
Original files preserved."
```

### Step 4.5: Final Summary

```markdown
## Import Complete

- **Tasks imported:** N
- **Sources processed:** [list]
- **tasks.md created:** <TASKS_FILE> + <TASKS_DIR>/T-NNN.md files
- **Registered in:** .optimus.json (tasksFile: <TASKS_FILE>)
- **Original files:** NOT deleted (remove manually if desired)

### Next Steps
1. Review tasks.md and adjust dependencies/priorities
2. Run `/optimus-report` to see the dashboard
3. Run `/optimus-plan` on the first pending task
```

---

## Rules

- **NEVER delete original files** — only create/update tasks.md and task detail files at the configured location
- **NEVER apply changes without user approval** — always present and confirm first
- **NEVER invent task content** — only extract what exists in the source files
- **NEVER assume dependencies from task order** — sequential IDs don't imply dependency
- If a task has no content (just a title), create `TASKS_DIR/T-NNN.md` with empty Objetivo and Critérios de Aceite, and warn the user
- If status inference is uncertain, mark as `Pendente` and flag as "(inferred)" in the inventory
- If the project already has a valid tasks.md at the configured/default path (first line is `<!-- optimus:tasks-v1 -->`), inform the user and stop (nothing to import)
- Simple subtasks (< 20 lines AND no code blocks) become checklist items in the parent task — never separate entries in the table
- Rich subtasks (>= 20 lines OR contains code blocks) are linked via `## Referencia Pre-Dev` section — never inlined
- Task IDs must be unique — if duplicates found, warn the user before proceeding
