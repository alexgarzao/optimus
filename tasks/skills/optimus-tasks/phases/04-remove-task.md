# Phase 4: Remove Task

Loaded when user wants to remove a task entirely. Checks no other tasks depend on it before removal. Destructive — requires explicit user confirmation.

### Step 4.0: Identify Task

1. Parse the task ID from the user's request
2. Find the task row in the table
3. If task not found → **STOP**: "Task T-XXX not found in optimus-tasks.md"

### Step 4.1: Validate Removal

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

### Step 4.2: Apply Remove

1. Remove the table row for T-XXX from optimus-tasks.md
2. Save
3. **Re-validate after mutation** — see AGENTS.md Protocol: optimus-tasks.md Validation.
   If validation fails, abort and revert the in-memory edits; do not commit.

**NOTE:** Do NOT renumber remaining task IDs. IDs are permanent identifiers.

### Step 4.3: Confirm

```
Removed task T-XXX: <title>
```

