# Phase 12: Move Tasks Between Versions

Loaded when user wants to move one or more tasks from one version to another. Validates target version exists and re-validates tasks.md after mutation.

Move one or more tasks from one version to another.

### Step 12.0: Parse Move Request

The user may say:
- "move T-003 to v2" → single task
- "move T-003, T-005 to Futuro" → multiple specific tasks
- "move all Pendente from MVP to v2" → batch by status + source version
- "move all from MVP to v2" → batch by source version (all statuses except DONE)

### Step 12.1: Validate Target Version

Verify the target version exists in the Versions table. If not → **STOP**: "Version '<name>' does not exist. Create it first."

### Step 12.2: Identify Tasks to Move

For batch moves, list the tasks that match the criteria and present to the user via `AskUser`:

```
Tasks to move from <source> to <target>:

| ID | Title | Status | Priority |
|----|-------|--------|----------|
| T-003 | Login page | Pendente | Alta |
| T-005 | E2E tests | Pendente | Media |

Confirm move?
```

**BLOCKING:** Do NOT proceed without confirmation.

### Step 12.3: Apply Move

1. Update the Version column for each identified task
2. Do NOT change Status, Branch, Depends, Priority, or any other field
3. Save the file
4. **Re-validate after mutation** — see AGENTS.md Protocol: optimus-tasks.md Validation.
   If validation fails, abort and revert the in-memory edits; do not commit.
5. Commit: `chore(tasks): move N tasks from <source> to <target>`

