---
name: optimus-resolve
description: "Resolves merge conflicts in tasks.md caused by parallel structural edits. Since status and branch data live in state.json (gitignored), tasks.md conflicts are rare — they only occur when structural changes (new tasks, dependency edits, version moves) happen concurrently. This skill detects, parses, and resolves those conflicts — each task's row is independent."
trigger: >
  - When tasks.md has merge conflict markers (<<<<<<, ======, >>>>>>)
  - When user says "resolve tasks.md conflict" or "fix tasks conflict"
  - When git merge/rebase fails due to tasks.md conflict
  - After merging a PR when another feature branch has diverged
skip_when: >
  - No conflict markers exist in tasks.md
  - Conflict is in a file other than tasks.md (use standard git tools)
prerequisite: >
  - tasks.md exists and contains merge conflict markers
NOT_skip_when: >
  - "I can resolve it manually" -- Manual resolution risks reverting a task's status backward.
  - "It's just one line" -- Even one-line conflicts can silently lose a DONE status.
examples:
  - name: Resolve after merge
    invocation: "Resolve tasks.md conflict"
    expected_flow: >
      1. Detect conflict markers in tasks.md
      2. Parse both sides of each conflict
      3. Apply most-advanced-status rule per task
      4. Present resolution to user
      5. Apply after approval
  - name: Resolve during rebase
    invocation: "Fix tasks conflict"
    expected_flow: >
      1. Detect conflict markers
      2. Parse and resolve
      3. Stage resolved file
      4. User continues rebase
related:
  complementary:
    - optimus-report
    - optimus-tasks
verification:
  manual:
    - All conflict markers removed
    - Each task retains its most advanced status
    - No task status was reverted backward
    - Format validation passes after resolution
---

# Tasks.md Conflict Resolver

Resolves merge conflicts in `tasks.md` caused by parallel task execution across feature branches.

**Classification:** Administrative skill — runs on any branch.

**CRITICAL:** This skill NEVER reverts a task's status backward. The resolution rule is
always "most advanced status wins" for each task independently.

---

## Phase 1: Detect and Parse Conflicts

### Step 1.1: Verify Conflict Exists

Check if `tasks.md` has merge conflict markers:

```bash
TASKS_FILE=".optimus/tasks.md"
grep -c '<<<<<<<' "$TASKS_FILE" 2>/dev/null
```

If no conflict markers found:
- Check if a merge/rebase is in progress: `git status` (look for "You have unmerged paths")
- If no merge in progress → **STOP**: "No conflicts found in tasks.md. Nothing to resolve."
- If merge in progress but tasks.md is not conflicted → **STOP**: "tasks.md is not conflicted. Use `git mergetool` for other files."

### Step 1.2: Parse Conflict Regions

Read `tasks.md` and identify each conflict region:

```
<<<<<<< HEAD (or current branch)
[current version of conflicted lines]
=======
[incoming version of conflicted lines]
>>>>>>> <branch-name or commit>
```

**Multi-way conflict detection:** If a conflict region contains more than one `=======` marker (indicating an N-way merge), warn: "This is a multi-way merge conflict. This skill only handles 2-way conflicts. Manual resolution required for this region." Present the raw conflict region for manual review and skip auto-resolution for that region.

For each 2-way conflict region, classify its content:

| Content Type | How to Detect | Resolution Strategy |
|-------------|---------------|---------------------|
| **Task table rows** | Lines matching `\| T-\d+ \|` pattern | Per-task most-advanced-status |
| **Versions table** | Lines in the `## Versions` section | Merge both — keep all versions; deduplicate by name. Rules: same name + different status → keep higher status (Ativa > Próxima > Planejada > Backlog > Concluída); same name + same status + different description → present to user for decision; new version on one side only → keep it (additive merge) |
| **TaskSpec column** | `TaskSpec` values in task rows | Keep either (should be identical on both sides) |
| **Format marker / headers** | First line, `# Tasks`, table headers | Keep either (identical) |

### Step 1.3: Parse Task Rows From Both Sides

For each conflict region containing task table rows:

1. Extract ALL task rows from the **current** side (HEAD / ours)
2. Extract ALL task rows from the **incoming** side (theirs)
3. Build a map: `{task_id → {current_row, incoming_row}}`

For tasks that appear on ONLY ONE side, determine whether the task was ADDED on one branch or DELETED on the other:
- **If the task exists in the non-conflicted portion of the file on the other branch** → it was likely deleted. Present to user via `AskUser`: "Task T-XXX exists on one side but was removed on the other. Keep or remove?" User decides — this is NOT auto-resolved.
- **If the task does not exist anywhere on the other branch** → it was added. Keep as-is.

For tasks that appear on BOTH sides with different values, proceed to Phase 2.

---

## Phase 2: Resolve Using Most-Advanced-Status Rule

### Step 2.1: Define Status Ordering

The status lifecycle defines a strict ordering from least to most advanced:

```
Pendente < Validando Spec < Em Andamento < Validando Impl < Revisando PR < DONE
```

`Cancelado` is a terminal status — it is NOT "more advanced" than any status. It is
a lateral state change (a decision, not progress). See Step 2.3 for handling.

### Step 2.2: Resolve Each Conflicted Task

For each task that differs between current and incoming:

1. Compare the **Status** column:
   - If one side has a more advanced status → use that entire row
   - If both sides have the same status → compare other columns (Branch, Depends)
     and keep the row with more information (non-`-` Branch wins over `-`)

1b. Compare the **Estimate** column:
   - If one side has a value and the other has `-` → keep the non-empty value
   - If both have different non-empty values → keep the more specific one (prefer values with units like `2h` over generic `M`)
   - If both are `-` or identical → keep as-is

2. Compare the **Branch** column:
   - If one side has a branch name and the other has `-` → keep the branch name
   - If both have different branch names → keep the one matching the more advanced status

3. All other columns (Title, Tipo, Priority, Version, Depends):
   - If unchanged on both sides → keep as-is
   - If changed on one side → keep the change
   - If changed on BOTH sides → flag for user decision (cannot auto-resolve)

### Step 2.3: Handle Cancelado Conflicts

If one side has `Cancelado` and the other has a non-terminal status:

- This is ambiguous — someone cancelled while someone else was working.
- **Do NOT auto-resolve.** Present to the user via `AskUser`:
  ```
  Task T-XXX has conflicting statuses:
    Current branch: <status A>
    Incoming branch: <status B> (one is Cancelado)

  Which should I keep?
  ```
  Options:
  - **Keep Cancelado** — the task was intentionally cancelled
  - **Keep <other status>** — the cancellation was premature, work continues

---

## Phase 3: Present Resolution

### Step 3.1: Show Resolution Summary

```markdown
## tasks.md Conflict Resolution

### Conflict Regions: N
### Auto-Resolved: M (using most-advanced-status rule)
### Needs User Decision: K

### Auto-Resolved Tasks
| ID | Current Status | Incoming Status | Resolved To | Reason |
|----|---------------|-----------------|-------------|--------|
| T-003 | Pendente | Em Andamento | Em Andamento | More advanced status |
| T-005 | Em Andamento | DONE | DONE | More advanced status |

### Needs User Decision
| ID | Current | Incoming | Conflict |
|----|---------|----------|----------|
| T-007 | Em Andamento | Cancelado | Terminal vs active |
| T-009 | Title changed | Priority changed | Both sides edited |
```

### Step 3.2: Collect Decisions

For each task that needs user decision, present via `AskUser` with the two options
and the context of what changed on each side.

**BLOCKING:** Do NOT apply any resolution until ALL decisions are collected.

### Step 3.3: Preview Resolved File

Present the full resolved `tasks.md` content (or a diff of changes) to the user:

```
Here is the resolved tasks.md. Review before applying:
```

Ask via `AskUser`:
- **Apply** — write the resolved content and stage for commit
- **Edit** — let me adjust something first
- **Cancel** — abort, keep conflict markers

**BLOCKING:** Do NOT write the file until the user approves.

---

## Phase 4: Apply Resolution

### Step 4.1: Write Resolved File

Write the fully resolved `tasks.md` (no conflict markers remaining).

### Step 4.2: Validate Format

Run the standard format validation (from AGENTS.md) on the resolved file:
1. Format marker present (`<!-- optimus:tasks-v1 -->`)
2. Versions table valid
3. Task table columns correct
4. All IDs, statuses, types, priorities valid
5. No circular dependencies
6. No duplicate IDs
7. No unescaped pipe characters in titles

If validation fails, inform the user and offer to fix or abort.

### Step 4.3: Stage the File

```bash
git add "$TASKS_FILE"
```

### Step 4.4: Inform Next Steps

```markdown
## Resolution Complete

- Conflicts resolved: N
- Auto-resolved: M
- User decisions: K
- tasks.md staged for commit

### Next Steps
If you were resolving a merge conflict:
  `git commit` — to complete the merge

If you were resolving during a rebase:
  `git rebase --continue` — to continue the rebase

Run `/optimus-report` to verify the dashboard looks correct.
```

---

## Rules

- **NEVER revert a task's status backward** — always keep the most advanced status
- **NEVER auto-resolve Cancelado conflicts** — always ask the user
- **NEVER write the file without user approval** — always preview first
- **NEVER commit automatically** — only stage the file, let the user commit
- Each task row is independent — resolve conflicts per-task, not per-region
- If a conflict involves non-status columns (Title, Priority, Depends) changed on BOTH
  sides, always ask the user — do not guess
- Validate the resolved file before staging — catch format errors before they propagate
- This skill is read-then-write — it modifies ONLY tasks.md, never any other file
