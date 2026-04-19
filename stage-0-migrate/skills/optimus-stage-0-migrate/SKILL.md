---
name: optimus-stage-0-migrate
description: >
  Task format migrator. Discovers existing task files in any format (index-only,
  inline tasks, individual files, subtask folders) and converts them to the
  standard optimus tasks.md format. Presents the current state, proposes the
  conversion, and only applies after user approval. Never deletes original files.
trigger: >
  - When user wants to adopt the optimus task pipeline on an existing project
  - When user says "migrate tasks", "convert tasks", "setup task pipeline"
  - When stage-1-spec can't find a valid tasks.md
skip_when: >
  - Project already has a valid tasks.md in optimus format
  - User wants to create tasks from scratch (just create the file manually)
prerequisite: >
  - Project has some form of task tracking (files, markdown, etc.)
NOT_skip_when: >
  - "The project is small" → Even small projects benefit from standardized task tracking.
  - "I'll just create tasks.md manually" → This agent handles edge cases you'd miss.
  - "Tasks are already in markdown" → Markdown != optimus format. Columns, dependencies, and status need standardizing.
examples:
  - name: Migrate from index-only tasks.md
    invocation: "Migrate tasks to optimus format"
    expected_flow: >
      1. Discover tasks.md is an index (links to other files)
      2. Follow links, read individual task files
      3. Present inventory
      4. Propose consolidated tasks.md
      5. Apply after approval
  - name: Migrate from tasks/ directory with subtasks
    invocation: "Setup task pipeline"
    expected_flow: >
      1. Discover tasks/ directory with individual task files
      2. Discover subtasks/ directory
      3. Present inventory with subtask mapping
      4. Propose tasks.md with subtasks as checklist items
      5. Apply after approval
related:
  complementary:
    - optimus-stage-0-report
    - optimus-stage-1-spec
  sequence:
    before:
      - optimus-stage-0-report
      - optimus-stage-1-spec
verification:
  manual:
    - All existing tasks discovered and presented
    - Conversion proposal shown before any changes
    - tasks.md generated in correct optimus format
    - Original files NOT deleted
---

# Task Format Migrator

Discovers existing task files and converts them to the standard optimus `tasks.md` format.

**CRITICAL:** This agent NEVER deletes original files. It creates/updates `tasks.md` and
leaves originals untouched. The user decides whether to remove them later.

---

## Phase 0: Discovery

### Step 0.1: Scan for Task Files

Search the project for any form of task tracking. Check ALL of these locations:

```
# Files to check (in order)
./tasks.md
./docs/tasks.md
./docs/pre-dev/tasks.md
./TODO.md
./TASKS.md
./backlog.md

# Directories to check
./tasks/
./docs/tasks/
./docs/pre-dev/tasks/
./subtasks/
./docs/subtasks/
./docs/pre-dev/subtasks/
```

For each file/directory found, read its contents and classify it.

### Step 0.2: Classify Each Source

For each discovered file, determine its type:

| Type | How to detect | Example |
|------|--------------|---------|
| **Index-only** | tasks.md with links/references to other files but no task details inline | `- [T-001](./tasks/t-001.md)` |
| **Inline tasks** | tasks.md with full task descriptions (objectives, criteria) inside | H2 sections with content |
| **Table-only** | tasks.md with a markdown table but no detail sections | Just a table, no H2s |
| **Individual files** | tasks/ directory with one .md file per task | `tasks/t-001.md`, `tasks/t-002.md` |
| **Subtask files** | subtasks/ directory with subtask .md files | `subtasks/t-001-subtasks.md` |
| **YAML frontmatter** | Task files with YAML frontmatter (taskmd format) | `---\nid: "001"\nstatus: pending\n---` |
| **Checklist** | Simple TODO list with checkboxes | `- [ ] Implement auth\n- [x] Setup DB` |
| **Optimus format** | Already has the standard table + H2 sections | Valid optimus tasks.md |

### Step 0.3: Extract Task Data

For each task found (regardless of format), extract:

| Field | How to find it | If missing |
|-------|---------------|------------|
| **ID** | Explicit ID (T-001), filename (001-task.md), heading number | Generate: T-001, T-002, ... |
| **Title** | H1/H2 heading, YAML `title:`, filename | Use first line of content |
| **Status** | YAML `status:`, column in table, checkbox state | Default: `Pendente` |
| **Dependencies** | YAML `dependencies:`, "Depends on" text, "After T-XXX" | Default: `-` (none) |
| **Priority** | YAML `priority:`, explicit mention, position in file | Default: `Media` |
| **Branch** | YAML `branch:`, git branch naming convention | Default: `-` |
| **Objective** | H2/H3 "Objetivo", "Objective", "Description" section | Use title as fallback |
| **Acceptance Criteria** | Checklist items, "Criteria", "Tasks" section | Leave empty, warn user |
| **Subtasks** | Files in subtasks/ referencing this task, nested checklists | Merge into criteria |

#### Status Inference Rules

When no explicit status exists, infer from available signals:

| Signal | Inferred status |
|--------|----------------|
| All checkboxes checked (`- [x]`) | `**DONE**` |
| Some checkboxes checked | `Em Andamento` |
| No checkboxes checked | `Pendente` |
| File mentions "completed", "done", "finished" | `**DONE**` |
| File mentions "in progress", "working on" | `Em Andamento` |
| YAML `status: done/completed/closed` | `**DONE**` |
| YAML `status: in_progress/active/started` | `Em Andamento` |
| YAML `status: pending/todo/backlog` | `Pendente` |

#### Dependency Inference

When no explicit dependencies exist, look for implicit signals:
- "After T-001", "Requires T-003", "Blocked by T-002"
- Sequential numbering (T-001 before T-002) is NOT a dependency — don't infer from order
- If nothing found, set to `-` and let the user add dependencies manually

### Step 0.4: Handle Subtasks

Subtasks become checklist items in the parent task's acceptance criteria section:

**Before (subtasks/t-001-subtasks.md):**
```markdown
## Subtasks for T-001

### S-001-1: Create database schema
- [ ] Define tables
- [ ] Add migrations

### S-001-2: Setup ORM
- [ ] Install Prisma
- [ ] Generate client
```

**After (inside tasks.md, section ## T-001):**
```markdown
## T-001: Setup database

**Objetivo:** ...

**Critérios de Aceite:**
- [ ] Create database schema
  - [ ] Define tables
  - [ ] Add migrations
- [ ] Setup ORM
  - [ ] Install Prisma
  - [ ] Generate client
```

Nested subtasks become indented checklist items.

---

## Phase 1: Present Inventory

### Step 1.1: Show Discovery Summary

Present what was found to the user:

```markdown
## Task Discovery Summary

### Sources Found
| # | Location | Type | Tasks Found |
|---|----------|------|-------------|
| 1 | ./tasks.md | Index-only | 8 links |
| 2 | ./tasks/ | Individual files | 8 files |
| 3 | ./subtasks/ | Subtask files | 5 files |

### Tasks Extracted
| ID | Title | Status (inferred?) | Dependencies | Subtasks |
|----|-------|-------------------|-------------|----------|
| T-001 | Setup auth module | **DONE** (inferred from checkboxes) | - | 3 subtasks |
| T-002 | User registration | Pendente (no status found) | T-001 (explicit) | - |
| T-003 | Login page | Pendente (no status found) | T-001 (inferred) | 2 subtasks |
| ... | ... | ... | ... | ... |

### Warnings
- T-004: No acceptance criteria found — section will be empty
- T-006: Duplicate title with T-003 — please review
- subtasks/t-007-subtasks.md: References T-007 which doesn't exist
```

### Step 1.2: Ask for Adjustments

Use `AskUser` to confirm:

```
I found N tasks across M sources. Before converting:

1. Are the inferred statuses correct? (I can list them for review)
2. Should I attempt to infer dependencies from context, or set all to "-"?
3. Any tasks that should be excluded from migration?
```

**BLOCKING:** Wait for user confirmation before proceeding.

---

## Phase 2: Propose Conversion

### Step 2.1: Generate tasks.md Preview

Generate the complete `tasks.md` in optimus format and present it to the user:

```markdown
## Proposed tasks.md

### Table
| ID | Title | Status | Depends | Priority | Branch |
|----|-------|--------|---------|----------|--------|
| T-001 | Setup auth module | **DONE** | - | Alta | - |
| T-002 | User registration | Pendente | T-001 | Alta | - |
| ... | ... | ... | ... | ... | ... |

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

### Step 2.2: Confirm Before Applying

Use `AskUser`:

```
Here's the proposed tasks.md with N tasks. What should I do?
```

Options:
- **Apply**: Create/update tasks.md with this content
- **Edit first**: Let me adjust specific tasks before applying
- **Cancel**: Don't create anything

**BLOCKING:** Do NOT write any file until the user explicitly approves.

---

## Phase 3: Apply Conversion

### Step 3.1: Check for Existing tasks.md

If `tasks.md` already exists in optimus format:
- Ask via `AskUser`: "tasks.md already exists. Merge new tasks into it, or replace entirely?"
- If merge: add only tasks that don't already exist (match by ID or title)
- If replace: backup the existing file content (show it to the user first)

If `tasks.md` exists in non-optimus format:
- Rename to `tasks.md.bak` before creating the new one
- Inform the user: "Backed up original to tasks.md.bak"

### Step 3.2: Write tasks.md

Create `tasks.md` with:
1. H1 heading: `# Tasks`
2. The table (all columns)
3. Empty line
4. H2 sections for each task (with extracted content)

### Step 3.3: Commit

```bash
git add tasks.md
git commit -m "chore: migrate tasks to optimus format (stage-0-migrate)

Migrated N tasks from [sources list].
Original files preserved."
```

### Step 3.4: Final Summary

```markdown
## Migration Complete

- **Tasks migrated:** N
- **Sources processed:** [list]
- **tasks.md created:** ./tasks.md
- **Original files:** NOT deleted (remove manually if desired)

### Next Steps
1. Review tasks.md and adjust dependencies/priorities
2. Run `/optimus-stage-0-report` to see the dashboard
3. Run `/optimus-stage-1-spec` on the first pending task
```

---

## Rules

- **NEVER delete original files** — only create/update tasks.md
- **NEVER apply changes without user approval** — always present and confirm first
- **NEVER invent task content** — only extract what exists in the source files
- **NEVER assume dependencies from task order** — sequential IDs don't imply dependency
- If a task has no content (just a title), create the H2 section with empty Objetivo and Critérios de Aceite, and warn the user
- If status inference is uncertain, mark as `Pendente` and flag as "(inferred)" in the inventory
- If the project already has a valid optimus tasks.md, inform the user and stop (nothing to migrate)
- Subtasks always become checklist items in the parent task — never separate entries in the table
- Task IDs must be unique — if duplicates found, warn the user before proceeding
