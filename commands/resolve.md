---
description: Resolves merge conflicts in optimus-tasks.md caused by parallel structural edits. Since status and branch data live in state.json (gitignored), optimus-tasks.md conflicts are rare — they only occur when structural changes (new tasks, dependency edits, version moves) happen concurrently. This skill detects, parses, and resolves those conflicts — each task's row is independent.
---

# optimus-tasks.md Conflict Resolver

Resolves merge conflicts in `optimus-tasks.md` caused by parallel structural edits across feature branches.
Since Status and Branch live in state.json (gitignored), conflicts are limited to structural columns.

**Classification:** Administrative skill — runs on any branch.

**CRITICAL:** Status and Branch live in state.json (gitignored) — they are NOT in optimus-tasks.md
and cannot cause merge conflicts. This skill only resolves structural column conflicts
(Title, Tipo, Depends, Priority, Version, Estimate, TaskSpec).

---

## Phase 1: Detect and Parse Conflicts

### Step 1.1: Resolve Paths and Verify Conflict Exists

Execute AGENTS.md Protocol: Resolve Tasks Git Scope. This obtains `TASKS_FILE`,
`TASKS_GIT_SCOPE`, `TASKS_GIT_REL`, and the `tasks_git` helper. In `separate-repo`
scope, merge conflicts are resolved inside the tasks repo (not the project repo).

Check if `optimus-tasks.md` has merge conflict markers:

```bash
# TASKS_FILE was set by Protocol: Resolve Tasks Git Scope
grep -c '<<<<<<<' "$TASKS_FILE" 2>/dev/null
```

If no conflict markers found:
- Check if a merge/rebase is in progress in the correct repo:
  - Same-repo: `git status` in project repo
  - Separate-repo: `tasks_git status` in tasks repo
- If no merge in progress → **STOP**: "No conflicts found in optimus-tasks.md. Nothing to resolve."
- If merge in progress but optimus-tasks.md is not conflicted → **STOP**: "optimus-tasks.md is not conflicted. Use `git mergetool` for other files."

**Pre-merge legacy schema check:** Before resolving structural conflicts in
optimus-tasks.md, verify that NEITHER side of the merge contains the legacy
Status/Branch columns. A long-lived feature branch from before the post-redesign
migration may still carry the legacy schema and try to merge those columns back
in. If detected, the merge cannot proceed safely — the legacy columns must be
migrated first via `/optimus:import`.

```bash
# TASKS_GIT_REL was set by Protocol: Resolve Tasks Git Scope (the path of
# optimus-tasks.md relative to the git scope's root). Use tasks_git so that
# separate-repo scope queries the tasks repo, not the project repo.
LEGACY_RE='\| Status \|.*\| Branch \|'
for ref in HEAD MERGE_HEAD; do
  if tasks_git show "${ref}:${TASKS_GIT_REL}" 2>/dev/null | head -20 | grep -qE "$LEGACY_RE"; then
    echo "ERROR: ${ref} carries the legacy Status/Branch columns in optimus-tasks.md." >&2
    echo "  This is the pre-redesign legacy schema. Status and Branch live in" >&2
    echo "  state.json now (gitignored) and must NOT appear as table columns." >&2
    echo "  Run /optimus:import on each side separately to migrate, then retry." >&2
    exit 1
  fi
done
```

If no `MERGE_HEAD` exists (e.g., during a rebase rather than a merge), substitute
the appropriate ref pair (`HEAD` and `REBASE_HEAD` or the rebase's onto target).

### Step 1.2: Parse Conflict Regions

Read `optimus-tasks.md` and identify each conflict region:

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
| **Task table rows** | Lines matching `\| T-\d+ \|` pattern | Per-task structural merge |
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

## Phase 2: Resolve Structural Conflicts

Since Status and Branch live in state.json (gitignored, not in optimus-tasks.md), conflicts
are limited to structural columns: ID, Title, Tipo, Depends, Priority, Version,
Estimate, TaskSpec. No status ordering or "most-advanced-status rule" is needed.

### Step 2.1: Resolve Each Conflicted Task

For each task that differs between current and incoming:

**NOTE:** Status and Branch are NOT in optimus-tasks.md — they live in state.json (gitignored).
Conflicts in optimus-tasks.md are limited to structural columns only.

1. Compare the **Estimate** column:
   - If one side has a value and the other has `-` → keep the non-empty value
   - If both have different non-empty values → keep the more specific one (prefer values with units like `2h` over generic `M`)
   - If both are `-` or identical → keep as-is

2. All other columns (Title, Tipo, Priority, Version, Depends, TaskSpec):
   - If unchanged on both sides → keep as-is
   - If changed on one side → keep the change
   - If changed on BOTH sides → flag for user decision (cannot auto-resolve)

### Step 2.2: Handle Structural Conflicts

Since Status and Branch live in state.json (not optimus-tasks.md), conflicts are limited to
structural fields. If both sides changed the same structural field (e.g., Priority or
Version), flag for user decision via `AskUser`.

---

## Phase 3: Present Resolution

### Step 3.1: Show Resolution Summary

```markdown
## optimus-tasks.md Conflict Resolution

### Conflict Regions: N
### Auto-Resolved: M
### Needs User Decision: K

### Auto-Resolved Tasks
| ID | Field | Current | Incoming | Resolved To | Reason |
|----|-------|---------|----------|-------------|--------|
| T-003 | Estimate | - | M | M | Non-empty wins |
| T-005 | TaskSpec | - | tasks/task_005.md | tasks/task_005.md | Non-empty wins |

### Needs User Decision
| ID | Field | Current | Incoming | Conflict |
|----|-------|---------|----------|----------|
| T-009 | Title | "Auth API" | "Auth Service" | Both sides edited |
| T-009 | Priority | Alta | Media | Both sides edited |
```

### Step 3.2: Collect Decisions

For each task that needs user decision, present via `AskUser` with the two options
and the context of what changed on each side.

**BLOCKING:** Do NOT apply any resolution until ALL decisions are collected.

### Step 3.3: Preview Resolved File

Present the full resolved `optimus-tasks.md` content (or a diff of changes) to the user:

```
Here is the resolved optimus-tasks.md. Review before applying:
```

Ask via `AskUser`:
- **Apply** — write the resolved content and stage for commit
- **Edit** — let me adjust something first
- **Cancel** — abort, keep conflict markers

**BLOCKING:** Do NOT write the file until the user approves.

---

## Phase 4: Apply Resolution

### Step 4.1: Write Resolved File

Write the fully resolved `optimus-tasks.md` (no conflict markers remaining).

### Step 4.2: Validate Format

**Validate the resolved file** — see AGENTS.md Protocol: optimus-tasks.md Validation.

This protocol enforces all 15 format-validation rules (format marker, exactly-one-Ativa,
at-most-one-Próxima, valid Tipo/Priority/Status enumerations, all Version/Depends
references resolve to existing rows, no duplicates, no circular dependencies, no
unescaped pipes, no empty table). Failing validation aborts the apply phase.

If validation fails, inform the user and offer to fix or abort.

### Step 4.3: Stage the File

Use `tasks_git` so the file is staged in the correct repo (project or tasks repo):

```bash
tasks_git add "$TASKS_GIT_REL"
```

### Step 4.4: Inform Next Steps

```markdown
## Resolution Complete

- Conflicts resolved: N
- Auto-resolved: M
- User decisions: K
- optimus-tasks.md staged for commit

### Next Steps
If you were resolving a merge conflict:
  `git commit` — to complete the merge

If you were resolving during a rebase:
  `git rebase --continue` — to continue the rebase

Run `/optimus:report` to verify the dashboard looks correct.
```

---

## Rules

- **NEVER lose structural data** — when both sides changed the same field, always ask the user
- **NEVER write the file without user approval** — always preview first
- **NEVER commit automatically** — only stage the file, let the user commit
- Each task row is independent — resolve conflicts per-task, not per-region
- If a conflict involves non-status columns (Title, Priority, Depends) changed on BOTH
  sides, always ask the user — do not guess
- Validate the resolved file before staging — catch format errors before they propagate
- This skill is read-then-write — it modifies ONLY optimus-tasks.md, never any other file

<!-- INLINE-PROTOCOLS:START -->
## Shared Protocols (from AGENTS.md)

The following protocols are referenced by this skill. They are
extracted from the Optimus AGENTS.md to make this plugin self-contained.

<!-- INLINE-PROTOCOLS:END -->
