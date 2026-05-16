# Phase 5: Reorder Tasks

Loaded when user wants to reorder tasks within a version. Validates dependencies (cannot move a task before its dependencies).

### Step 5.0: Determine New Order

Reordering changes the visual order of rows in the table. It does NOT change IDs or dependencies.

Options:
- **Move task:** "Move T-005 before T-003" → reposition one row
- **Full reorder:** "Reorder by priority" → sort all rows by priority (Alta → Media → Baixa)
- **Custom:** User provides a new order

### Step 5.1: Apply Reorder

1. Rearrange table rows according to the requested order
2. Do NOT change any cell values (ID, Title, Tipo, Status, Depends, Priority, Branch stay the same)
3. Save the file
4. **Re-validate after mutation** — see AGENTS.md Protocol: optimus-tasks.md Validation.
   If validation fails, abort and revert the in-memory edits; do not commit.

### Step 5.2: Confirm

Show the new table order.

