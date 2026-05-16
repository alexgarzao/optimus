# Phase 3: Edit Task

Loaded when user wants to edit a task field (Priority, Depends, Version, Estimate, Tipo, Title, TaskSpec). Status changes are restricted — Edit cannot change status.

### Step 3.0: Identify Task and Field

1. Parse the task ID from the user's request
2. Find the task row in the table
3. If task not found → **STOP**: "Task T-XXX not found in optimus-tasks.md"

Determine which field(s) to edit. Editable fields:

| Field | Allowed? | Notes |
|-------|----------|-------|
| Title | Yes | Updates table row |
| Tipo | Yes | Must be `Feature`, `Fix`, `Refactor`, `Chore`, `Docs`, or `Test` |
| Priority | Yes | Must be `Alta`, `Media`, or `Baixa` |
| Version | Yes | Must reference a version in the Versions table |
| Depends | Yes | Must validate references and check circular deps |
| Estimate | Yes | Free text (S, M, L, XL, 2h, 1d) or `-` |
| Status | **No** | Status is managed ONLY by stage agents |
| Branch | **No** | Branch is managed ONLY by plan and done |
| ID | **No** | IDs are immutable |
| Ring reference | **No** | Managed by import and task creation only |

**HARD BLOCK:** If the user tries to change Status or Branch, refuse:
```
Status is managed by the cycle stage agents (plan, build, review, done).
To change status manually, use the Advance or Demote operations in this skill
(e.g., "advance T-XXX" or "demote T-XXX"). To reopen a completed or cancelled
task, use "reopen T-XXX".
```

### Step 3.1: Apply Edit

1. Update the relevant column(s) in the table row in optimus-tasks.md
2. If Depends changed, validate all references exist and no circular dependencies
3. Save the file
4. **Re-validate after mutation** — see AGENTS.md Protocol: optimus-tasks.md Validation.
   If validation fails, abort and revert the in-memory edits; do not commit.

### Step 3.2: Confirm

Show the user the changes:
```
Updated T-XXX:
  <field>: <old value> → <new value>
```

