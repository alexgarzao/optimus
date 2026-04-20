---
name: optimus-cycle-crud
description: >
  Administrative task management for tasks.md. Create, edit, remove, and reorder tasks.
  Validates format, dependencies, and ID uniqueness. Runs on any branch — this is an
  administrative skill, not an execution skill.
trigger: >
  - When user wants to add a new task (e.g., "add task", "create task", "new task")
  - When user wants to edit a task (e.g., "change priority of T-003", "rename T-005")
  - When user wants to remove a task (e.g., "remove T-004", "delete task")
  - When user wants to reorder tasks (e.g., "move T-005 before T-003")
  - When user says "manage tasks" or "edit tasks.md"
skip_when: >
  - User wants to execute a task (use cycle-spec-stage-1 instead)
  - User wants to change task status (status is managed by stage agents only)
prerequisite: >
  - tasks.md exists in the project root or docs/ directory
NOT_skip_when: >
  - "I can edit tasks.md manually" → This agent validates format, dependencies, and IDs automatically.
  - "It's just a small change" → Even small changes can break format or create circular dependencies.
examples:
  - name: Add a new task
    invocation: "Add a task: implement password reset"
    expected_flow: >
      1. Parse tasks.md
      2. Generate next ID (T-NNN)
      3. Ask for details (priority, dependencies)
      4. Add row to table and create detail section
      5. Validate and save
  - name: Edit task priority
    invocation: "Change T-003 priority to Alta"
    expected_flow: >
      1. Parse tasks.md
      2. Find T-003 row
      3. Update Priority column
      4. Save
  - name: Remove a task
    invocation: "Remove T-004"
    expected_flow: >
      1. Parse tasks.md
      2. Check no other tasks depend on T-004
      3. Remove row and detail section
      4. Save
related:
  complementary:
    - optimus-cycle-migrate
    - optimus-cycle-report
verification:
  manual:
    - After any operation, verify tasks.md still has valid format marker
    - Verify no duplicate IDs exist
    - Verify no broken dependency references
---

# optimus-cycle-crud

Administrative CRUD operations for tasks in `tasks.md`.

**Classification:** Administrative skill — runs on any branch, never modifies code.

## Phase 0: Initialize

### Step 0.0: Find and Validate tasks.md

1. **Find tasks.md:** Look in `./tasks.md` (project root). If not found, look in `./docs/tasks.md`. If not found in either location, ask the user via `AskUser`:

   "No tasks.md found. What should I do?"
   - **(a) Create a new tasks.md** — creates an empty tasks.md in the project root with the optimus format marker and empty table
   - **(b) Run cycle-migrate** — use this if you already have task files in another format

   If the user chooses to create, write `./tasks.md` with:
   ```markdown
   <!-- optimus:tasks-v1 -->
   # Tasks

   | ID | Title | Tipo | Status | Depends | Priority | Branch |
   |----|-------|------|--------|---------|----------|--------|
   ```
   Then commit: `chore(tasks): initialize tasks.md`

2. **Validate format (HARD BLOCK):**
   - **First line** must be `<!-- optimus:tasks-v1 -->` (format marker). If missing → **STOP**.
   - A markdown table exists with columns: ID, Title, Tipo, Status, Depends, Priority, Branch
   - All task IDs match `T-NNN` pattern
   - All Tipo values are valid (`Feature`, `Fix`, `Refactor`, `Chore`, `Docs`, `Test`)
   - All Status values are valid (`Pendente`, `Validando Spec`, `Em Andamento`, `Validando Impl`, `Revisando PR`, `**DONE**`)
   - All Depends values are `-` or comma-separated valid task IDs
   - No duplicate task IDs

If validation fails, **STOP** and suggest: "tasks.md is not in valid optimus format. Run `/optimus-cycle-migrate` to fix it."

### Step 0.1: Determine Operation

Parse the user's request to determine which operation to perform:

| Operation | Triggers |
|-----------|----------|
| **Create** | "add task", "create task", "new task" |
| **Edit** | "edit T-XXX", "change T-XXX", "update T-XXX", "rename T-XXX" |
| **Remove** | "remove T-XXX", "delete T-XXX" |
| **Reorder** | "move T-XXX before/after T-YYY", "reorder tasks" |

If unclear, ask the user via `AskUser`:

"What would you like to do?"
- (a) Create a new task
- (b) Edit an existing task
- (c) Remove a task
- (d) Reorder tasks

## Phase 1: Create Task

### Step 1.0: Gather Task Information

Ask the user for task details using `AskUser` (one question at a time or batch if info provided):

1. **Title** (required): Short description of the task
2. **Tipo** (required): `Feature`, `Fix`, `Refactor`, `Chore`, `Docs`, or `Test`
3. **Priority** (required): `Alta`, `Media`, or `Baixa`
4. **Dependencies** (optional): Comma-separated task IDs (e.g., `T-001, T-003`) or `-` for none
5. **Objective** (required): What the task achieves (for the detail section)
6. **Acceptance criteria** (required): Checklist items (for the detail section)

If the user provided some of these in the initial request, use them and ask only for missing fields.

### Step 1.1: Check for Similar Tasks (duplicate detection)

Before creating, search existing tasks for potential duplicates:

1. **Compare by title:** For each existing task, check if the new title shares 2+ significant
   keywords with an existing title (ignore articles, prepositions, and generic words like
   "implement", "add", "create", "update", "fix")
2. **Compare by objective:** If the user provided an objective, check if any existing task's
   **Objetivo** section describes the same goal (semantic similarity — same entity, same action)

If similar tasks are found, present them to the user via `AskUser`:

```
I found N existing tasks that look similar to your new task:

| ID | Title | Status | Objetivo (excerpt) |
|----|-------|--------|--------------------|
| T-003 | User login page | Pendente | Implement login with JWT... |
| T-008 | Auth login flow | Em Andamento | Create the login screen... |

Your new task: "<new title>"

Create anyway?
```

Options:
- **Create anyway** — the new task is different enough
- **Cancel** — one of the existing tasks already covers this

If no similar tasks are found, proceed silently.

### Step 1.2: Generate Task ID

1. Parse all existing task IDs from the table
2. Find the highest numeric value (e.g., if T-012 exists, next is T-013)
3. Format as `T-NNN` with zero-padding to 3 digits

### Step 1.3: Validate Dependencies

If the user specified dependencies:
1. Verify each dependency ID exists in the table
2. Check for circular dependencies: if T-NEW depends on T-X, and T-X (directly or transitively) would depend on T-NEW → reject
3. If any dependency ID is invalid → ask the user to correct it

### Step 1.4: Add to tasks.md

1. Add a new row to the table:
   ```
   | T-NNN | <title> | <tipo> | Pendente | <depends> | <priority> | - |
   ```
2. Add a detail section at the end of the file:
   ```markdown
   ## T-NNN: <title>

   **Objetivo:** <objective>

   **Critérios de Aceite:**
   - [ ] <criterion 1>
   - [ ] <criterion 2>
   ```
3. Save the file

### Step 1.5: Confirm

Show the user the added task:
```
Created task T-NNN: <title>
  Tipo: <tipo>
  Priority: <priority>
  Depends on: <depends>
  Status: Pendente
```

## Phase 2: Edit Task

### Step 2.0: Identify Task and Field

1. Parse the task ID from the user's request
2. Find the task row in the table
3. If task not found → **STOP**: "Task T-XXX not found in tasks.md"

Determine which field(s) to edit. Editable fields:

| Field | Allowed? | Notes |
|-------|----------|-------|
| Title | Yes | Updates both table and H2 section header |
| Tipo | Yes | Must be `Feature`, `Fix`, `Refactor`, `Chore`, `Docs`, or `Test` |
| Priority | Yes | Must be `Alta`, `Media`, or `Baixa` |
| Depends | Yes | Must validate references and check circular deps |
| Status | **No** | Status is managed ONLY by stage agents |
| Branch | **No** | Branch is managed ONLY by stage-1 and close |
| ID | **No** | IDs are immutable |
| Objective | Yes | Updates the detail section |
| Acceptance criteria | Yes | Updates the detail section checklist |

**HARD BLOCK:** If the user tries to change Status or Branch, refuse:
```
Status is managed by the cycle stage agents (spec, impl, review, close).
Use the appropriate stage agent to change task status.
```

### Step 2.1: Apply Changes

1. Update the relevant column(s) in the table row
2. If Title changed, also update the H2 section header (`## T-NNN: <new title>`)
3. If Depends changed, validate all references exist and no circular dependencies
4. If Objective or acceptance criteria changed, update the detail section
5. Save the file

### Step 2.2: Confirm

Show the user the changes:
```
Updated T-XXX:
  <field>: <old value> → <new value>
```

## Phase 3: Remove Task

### Step 3.0: Identify Task

1. Parse the task ID from the user's request
2. Find the task row in the table
3. If task not found → **STOP**: "Task T-XXX not found in tasks.md"

### Step 3.1: Validate Removal

**HARD BLOCK:** Check if any other task depends on this task:

```
Scan Depends column of ALL tasks for references to T-XXX
```

If any task depends on T-XXX:
```
Cannot remove T-XXX — the following tasks depend on it:
- T-YYY: <title>
- T-ZZZ: <title>

Remove or update the dependencies first.
```

**Warning:** If the task has status other than `Pendente`, warn the user:
```
Task T-XXX has status '<status>'. Removing a task that is in progress or done
may cause data loss. Are you sure?
```

Use `AskUser` for confirmation.

### Step 3.2: Remove from tasks.md

1. Remove the table row for T-XXX
2. Remove the detail section (`## T-XXX: ...` and all content until the next `## T-` or end of file)
3. Save the file

**NOTE:** Do NOT renumber remaining task IDs. IDs are permanent identifiers.

### Step 3.3: Confirm

```
Removed task T-XXX: <title>
```

## Phase 4: Reorder Tasks

### Step 4.0: Determine New Order

Reordering changes the visual order of rows in the table. It does NOT change IDs or dependencies.

Options:
- **Move task:** "Move T-005 before T-003" → reposition one row
- **Full reorder:** "Reorder by priority" → sort all rows by priority (Alta → Media → Baixa)
- **Custom:** User provides a new order

### Step 4.1: Apply Reorder

1. Rearrange table rows according to the requested order
2. Do NOT change any cell values (ID, Title, Tipo, Status, Depends, Priority, Branch stay the same)
3. Do NOT reorder the detail sections (they follow the original ID order for consistency)
4. Save the file

### Step 4.2: Confirm

Show the new table order.

## Phase 5: Batch Operations

If the user provides multiple tasks to create at once (e.g., a list of tasks), process them sequentially:

1. Generate IDs for all tasks first (to allow cross-references in dependencies)
2. Validate all dependencies
3. Add all rows and detail sections
4. Show summary of all created tasks

## Rules

1. **Never modify Status or Branch columns** — those are managed exclusively by stage agents
2. **Always validate format** after any modification (re-check marker, columns, IDs, deps)
3. **IDs are permanent** — never renumber or reuse deleted IDs
4. **Circular dependency detection is mandatory** — check before saving
5. **Confirm destructive operations** (remove) with the user before executing
6. **Preserve format marker** — first line must always be `<!-- optimus:tasks-v1 -->`
7. **Commit changes** — after any modification, commit with message: `chore(tasks): <operation> T-XXX`
