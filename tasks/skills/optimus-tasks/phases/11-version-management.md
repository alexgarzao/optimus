# Phase 11: Version Management

Loaded for version CRUD: create, edit, remove, reorder versions. Enforces 'exactly one Ativa' and 'at most one Próxima'.

### Step 11.0: Determine Version Operation

| Sub-operation | Triggers |
|---------------|----------|
| **Create** | "create version", "add version", "new version" |
| **Edit** | "edit version", "change version status", "rename version" |
| **Remove** | "remove version", "delete version" |
| **Reorder** | "reorder versions" |

### Step 11.1: Create Version

Ask the user for:
1. **Name** (required): Version name (e.g., `v3`, `Sprint 4`, `Futuro`)
2. **Status** (required): `Ativa`, `Próxima`, `Planejada`, `Backlog`, or `Concluída`. Default: `Planejada`
3. **Description** (required): Short description of the version's scope

**Validation:**
- If the name already exists in the Versions table → **STOP**: "Version '<name>' already exists."
- If the user sets Status to `Ativa` and another version is already `Ativa` → ask via `AskUser`:
  "Version '<existing>' is currently Ativa. Change it to Próxima and set '<new>' as Ativa?"
- If the user sets Status to `Próxima` and another version is already `Próxima` → ask via `AskUser`:
  "Version '<existing>' is currently Próxima. Change it to Planejada and set '<new>' as Próxima?"

Add the row to the Versions table and commit: `chore(tasks): create version <name>`

### Step 11.2: Edit Version

Editable fields:

| Field | Notes |
|-------|-------|
| Name | Updates the Versions table AND all tasks referencing this version |
| Status | Must be valid. See validation rules below |
| Description | Free text |

**Status change validation:**
- If setting to `Ativa` and another version is already `Ativa` → ask via `AskUser`:
  "Version '<existing>' is currently Ativa. Change it to Próxima and set '<name>' as Ativa?"
- If setting to `Próxima` and another version is already `Próxima` → ask via `AskUser`:
  "Version '<existing>' is currently Próxima. Change it to Planejada and set '<name>' as Próxima?"
- If setting to `Concluída`:
  - **If this version is currently `Ativa`:** check if a `Próxima` version exists:
    - If yes → ask via `AskUser`: "Version '<name>' is the active version. Setting it to
      Concluída will leave no active version unless '<próxima-version>' is promoted to
      Ativa. Promote '<próxima-version>' to Ativa automatically?"
    - If no → **STOP**: "Version '<name>' is the only active version. Before marking it
      Concluída, set another version to Ativa via 'edit version <name>, set to Ativa'."
  - Check tasks in this version:
    - Classify non-DONE tasks into two groups:
      - **In progress:** tasks with status other than `DONE` or `Cancelado` (e.g., Pendente, Em Andamento, etc.)
      - **Cancelled:** tasks with status `Cancelado`
    - If no in-progress AND no cancelled → proceed (all DONE)
    - If no in-progress BUT some cancelled → softer warning via `AskUser`:
      "Version '<name>' has all active tasks DONE, but N tasks were cancelled:
      - T-XXX: <title> (Cancelado)
      Mark as Concluída anyway?"
    - If any in-progress → stronger warning via `AskUser`:
      "Version '<name>' has N tasks still in progress:
      - T-XXX: <title> (Status: <status>)
      - T-YYY: <title> (Status: <status>)
      [And M cancelled tasks, if any]
      Mark as Concluída anyway?"
    - **BLOCKING:** Do NOT proceed without user confirmation

Commit: `chore(tasks): update version <name>`

### Step 11.3: Remove Version

**HARD BLOCK:** Check if this is the only version:
```
Count the rows in the Versions table
```
If only one version exists → **STOP**: "Cannot remove the only version. Create another version first."

**HARD BLOCK:** Check if any task references this version:
```
Scan the Version column of ALL tasks for references to <version-name>
```

If any task references it:
```
Cannot remove version '<name>' — the following tasks reference it:
- T-XXX: <title>
- T-YYY: <title>

Move these tasks to another version first.
```

If no tasks reference it, remove the row from the Versions table.
Commit: `chore(tasks): remove version <name>`

### Step 11.4: Reorder Versions

Rearrange rows in the Versions table. Does NOT change any values — only visual order.
