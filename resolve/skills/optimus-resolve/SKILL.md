---
name: optimus-resolve
description: "Resolves merge conflicts in optimus-tasks.md caused by parallel structural edits. Since status and branch data live in state.json (gitignored), optimus-tasks.md conflicts are rare — they only occur when structural changes (new tasks, dependency edits, version moves) happen concurrently. This skill detects, parses, and resolves those conflicts — each task's row is independent."
trigger: >
  - When optimus-tasks.md has merge conflict markers (<<<<<<, ======, >>>>>>)
  - When user says "resolve optimus-tasks.md conflict" or "fix tasks conflict"
  - When git merge/rebase fails due to optimus-tasks.md conflict
  - After merging a PR when another feature branch has diverged
skip_when: >
  - No conflict markers exist in optimus-tasks.md
  - Conflict is in a file other than optimus-tasks.md (use standard git tools)
prerequisite: >
  - optimus-tasks.md exists and contains merge conflict markers
NOT_skip_when: >
  - "I can resolve it manually" -- Manual resolution risks losing structural changes (dependencies, versions).
  - "It's just one line" -- Even one-line conflicts can silently lose data.
examples:
  - name: Resolve after merge
    invocation: "Resolve optimus-tasks.md conflict"
    expected_flow: >
      1. Detect conflict markers in optimus-tasks.md
      2. Parse both sides of each conflict
      3. Resolve structural columns using field-specific merge rules
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
    - Each task's structural fields correctly merged
    - Format validation passes after resolution
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

**Legacy file check:** If `<TASKS_DIR>/tasks.md` exists with the optimus format
marker but `<TASKS_DIR>/optimus-tasks.md` does not, warn the user: "Detected legacy
`<TASKS_DIR>/tasks.md`. Run any other Optimus skill (e.g., /optimus-tasks) once to
trigger the rename, then retry /optimus-resolve."
Do NOT auto-rename from /optimus-resolve since the file may be in a conflict state.
For the rename context, see AGENTS.md Protocol: Rename tasks.md to optimus-tasks.md.
Also check legacy migration — see AGENTS.md Protocol: Migrate tasks.md to tasksDir.

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

### Step 2.2: Resolve Each Conflicted Task

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

### Step 2.3: Handle Structural Conflicts

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

Run `/optimus-report` to verify the dashboard looks correct.
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

### Protocol: Migrate tasks.md to tasksDir

**Referenced by:** import, tasks, plan, build, review, done, resume, report, quick-report, batch, resolve, pr-check

Detects and migrates projects that have a legacy `.optimus/tasks.md` (versioned inside
`.optimus/`) to the new location `<tasksDir>/optimus-tasks.md`.

**Detection (run at the start of every skill that reads/writes the tasks tracking file):**

```bash
# Requires Protocol: Resolve Tasks Git Scope to have been executed first
# (TASKS_DIR, TASKS_FILE, TASKS_GIT_SCOPE, tasks_git available).
LEGACY_FILE=".optimus/tasks.md"
if [ -f "$LEGACY_FILE" ] && [ -f "$TASKS_FILE" ]; then
  # Partial/failed migration OR manual copy. Use new location but WARN the user.
  echo "WARNING: Both legacy ($LEGACY_FILE) and new ($TASKS_FILE) tracking files exist." >&2
  echo "         This indicates a partial prior migration or manual copy." >&2
  echo "         Using $TASKS_FILE. After confirming contents, remove the legacy file." >&2
  NEEDS_MIGRATION=0
elif [ -f "$LEGACY_FILE" ] && [ ! -f "$TASKS_FILE" ]; then
  NEEDS_MIGRATION=1
else
  NEEDS_MIGRATION=0
fi
```

**Dry-run mode:** If the skill is running in dry-run (per Dry-Run Mode section above),
DO NOT offer migration and DO NOT execute any migration step. Emit the plan and proceed:

```
[DRY-RUN] Migration would be offered for this task:
[DRY-RUN]   Legacy: $LEGACY_FILE
[DRY-RUN]   New:    $TASKS_FILE
[DRY-RUN]   Scope:  $TASKS_GIT_SCOPE
[DRY-RUN]   Would use: git mv (same-repo) OR cp + two commits (separate-repo)
```

**Config.json team-shared values warning:** If `.optimus/config.json` is currently tracked
in git and contains values (e.g., `defaultScope`), migration will untrack it. The values
are preserved locally but no longer shared via git. Warn user BEFORE untracking:

```bash
if git ls-files --error-unmatch .optimus/config.json >/dev/null 2>&1; then
  if [ -f .optimus/config.json ]; then
    CONFIG_KEYS=$(jq -r 'keys | join(", ")' .optimus/config.json 2>/dev/null || echo "unknown")
    echo "WARNING: .optimus/config.json is currently tracked with values: $CONFIG_KEYS" >&2
    echo "         Untracking will make these per-user. Team members need to re-apply locally." >&2
    # AskUser: Proceed with untrack? / Keep tracked (deviates from Optimus convention)
  fi
fi
```

**If `NEEDS_MIGRATION=1`, ask the user via `AskUser`:**

```
A legacy tasks.md was found at .optimus/tasks.md. The new location is ${TASKS_FILE} (optimus-tasks.md).
Migrate now? (Recommended — keeping the old location will break other skills.)
```

Options:
- **Migrate now** — copy → add in target repo → remove from project repo
- **Skip this time** — continue with the legacy file (emit warning; this will break)
- **Abort** — stop the current command so you can migrate manually

**Migration flow (when user chooses "Migrate now"):**

**Symlink safety (HARD BLOCK):** refuse to migrate if source or destination is a symlink
(prevents arbitrary file-write via symlink target). Must run BEFORE the checkpoint write
so we don't leave an orphan marker if a symlink is detected:
```bash
if [ -L "$LEGACY_FILE" ] || [ -L "$TASKS_FILE" ]; then
  echo "ERROR: Source or destination is a symlink — refusing to migrate." >&2
  exit 1
fi
```

Checkpoint file: write `.optimus/.migration-in-progress` BEFORE starting. This marker
lets subsequent invocations detect interrupted migrations:

```bash
mkdir -p .optimus
printf '%s\n' "$TASKS_FILE" > .optimus/.migration-in-progress
```

**Scope-branched migration:** explicit `if` so the agent executes the correct branch:

```bash
if [ "$TASKS_GIT_SCOPE" = "same-repo" ]; then
  # Same-repo: atomic git mv in a single commit (preserves history via rename-detect).
  mkdir -p "$TASKS_DIR"
  if ! git mv "$LEGACY_FILE" "$TASKS_FILE"; then
    echo "ERROR: git mv failed. Migration aborted — no changes made." >&2
    rm -f .optimus/.migration-in-progress
    exit 1
  fi
  COMMIT_MSG_FILE=$(mktemp -t optimus.XXXXXX) || { echo "ERROR: mktemp failed" >&2; exit 1; }
  chmod 600 "$COMMIT_MSG_FILE"
  printf '%s' "chore(tasks): migrate legacy .optimus/tasks.md to ${TASKS_DIR}/optimus-tasks.md" > "$COMMIT_MSG_FILE"
  if ! git commit -F "$COMMIT_MSG_FILE"; then
    echo "ERROR: Commit failed. Reverting git mv..." >&2
    # Revert: restore legacy from HEAD, remove new from working tree
    git reset HEAD -- "$LEGACY_FILE" "$TASKS_FILE" 2>/dev/null
    git checkout HEAD -- "$LEGACY_FILE" 2>/dev/null
    rm -f "$TASKS_FILE"
    rm -f "$COMMIT_MSG_FILE" .optimus/.migration-in-progress
    exit 1
  fi
  rm -f "$COMMIT_MSG_FILE"
else
  # Separate-repo: two commits in two repos. Rollback is per-repo on failure.
  mkdir -p "$TASKS_DIR"
  if ! cp "$LEGACY_FILE" "$TASKS_FILE"; then
    echo "ERROR: cp failed. Migration aborted." >&2
    rm -f .optimus/.migration-in-progress
    exit 1
  fi
  # Commit #1: in tasks repo
  if ! tasks_git add "$TASKS_GIT_REL"; then
    echo "ERROR: tasks_git add failed. Rolling back..." >&2
    rm -f "$TASKS_FILE"
    rm -f .optimus/.migration-in-progress
    exit 1
  fi
  COMMIT_MSG_FILE=$(mktemp -t optimus.XXXXXX) || { echo "ERROR: mktemp failed" >&2; exit 1; }
  chmod 600 "$COMMIT_MSG_FILE"
  printf '%s' "chore(tasks): migrate legacy .optimus/tasks.md to ${TASKS_DIR}/optimus-tasks.md" > "$COMMIT_MSG_FILE"
  if ! tasks_git commit -F "$COMMIT_MSG_FILE"; then
    echo "ERROR: tasks_git commit failed. Rolling back..." >&2
    tasks_git reset HEAD -- "$TASKS_GIT_REL" 2>/dev/null
    rm -f "$TASKS_FILE"
    rm -f "$COMMIT_MSG_FILE" .optimus/.migration-in-progress
    exit 1
  fi
  rm -f "$COMMIT_MSG_FILE"
  # Commit #2: in project repo
  if ! git rm "$LEGACY_FILE"; then
    echo "ERROR: git rm failed in project repo. Tasks repo already committed." >&2
    echo "Manual cleanup needed: rm $LEGACY_FILE && git add -A && git commit" >&2
    rm -f .optimus/.migration-in-progress
    exit 1
  fi
  COMMIT_MSG_FILE=$(mktemp -t optimus.XXXXXX) || { echo "ERROR: mktemp failed" >&2; exit 1; }
  chmod 600 "$COMMIT_MSG_FILE"
  printf '%s' "chore(tasks): remove legacy .optimus/tasks.md (moved to separate tasks repo at ${TASKS_DIR})" > "$COMMIT_MSG_FILE"
  if ! git commit -F "$COMMIT_MSG_FILE"; then
    echo "ERROR: Commit failed in project repo. Tasks repo already committed." >&2
    echo "Manual cleanup needed: git commit after resolving." >&2
    rm -f "$COMMIT_MSG_FILE" .optimus/.migration-in-progress
    exit 1
  fi
  rm -f "$COMMIT_MSG_FILE"
fi
```

**Untrack `.optimus/config.json` if previously versioned** (legacy projects). Check
commit exit code; restore index on failure:

```bash
if git ls-files --error-unmatch .optimus/config.json >/dev/null 2>&1; then
  git rm --cached .optimus/config.json
  COMMIT_MSG_FILE=$(mktemp -t optimus.XXXXXX) || { echo "ERROR: mktemp failed" >&2; exit 1; }
  chmod 600 "$COMMIT_MSG_FILE"
  printf '%s' "chore: untrack .optimus/config.json (now gitignored)" > "$COMMIT_MSG_FILE"
  if ! git commit -F "$COMMIT_MSG_FILE"; then
    # Restore to index so user can retry
    git reset HEAD .optimus/config.json 2>/dev/null
    rm -f "$COMMIT_MSG_FILE"
    echo "ERROR: Failed to untrack config.json. Index restored." >&2
    # Do not exit — migration of optimus-tasks.md already succeeded; user can retry untrack
  else
    rm -f "$COMMIT_MSG_FILE"
  fi
fi
```

**Ensure `.gitignore` includes the operational-files block:**
Execute Protocol: Initialize .optimus Directory. Commit if `.gitignore` was modified.

**Post-migration validation:** Verify the migrated optimus-tasks.md still passes Format
Validation (see AGENTS.md Format Validation section). If it fails (e.g., legacy
file was manually edited and lacks a `## Versions` section), inform user and suggest
running `/optimus-import` to rebuild:

```bash
if ! grep -q '^<!-- optimus:tasks-v1 -->' "$TASKS_FILE"; then
  echo "WARNING: Migrated optimus-tasks.md does not have the optimus format marker." >&2
  echo "         Run /optimus-import to rebuild in the correct format." >&2
fi
if ! grep -q '^## Versions' "$TASKS_FILE"; then
  echo "WARNING: Migrated optimus-tasks.md has no ## Versions section." >&2
  echo "         Run /optimus-import to rebuild in the correct format." >&2
fi
```

**Migration success: clear checkpoint marker and log each step.**
```bash
rm -f .optimus/.migration-in-progress
echo "INFO: Migration completed successfully:" >&2
echo "  - Legacy location: $LEGACY_FILE" >&2
echo "  - New location:    $TASKS_FILE" >&2
echo "  - Git scope:       $TASKS_GIT_SCOPE" >&2
```

**Report success:**
```
Migration complete. optimus-tasks.md is now at ${TASKS_FILE}.
Remember to push both repos (project + tasks) when you're ready.
```

**Interrupted migration recovery (on skill startup):**

```bash
if [ -f .optimus/.migration-in-progress ]; then
  INTERRUPTED_FILE=$(cat .optimus/.migration-in-progress 2>/dev/null)
  echo "WARNING: Previous migration was interrupted. Expected target: $INTERRUPTED_FILE" >&2
  # AskUser: Retry migration / Clear marker / Abort
fi
```

**If user chose "Skip this time":** Emit a warning and proceed using the legacy location
for this invocation only. The skill MUST use `$LEGACY_FILE` as `$TASKS_FILE` for the
remainder of this execution.

**If user chose "Abort":** **STOP** the current command.

Skills reference this as: "Check legacy tasks.md migration — see AGENTS.md Protocol: Migrate tasks.md to tasksDir."


### Protocol: Rename tasks.md to optimus-tasks.md

**Referenced by:** import, tasks, plan, build, review, done, resume, report, quick-report, batch, resolve, pr-check

Detects and renames projects whose Optimus tracking file is at `<tasksDir>/tasks.md`
(the prior default name) to `<tasksDir>/optimus-tasks.md`. The format marker
(`<!-- optimus:tasks-v1 -->`) is unchanged — this protocol only renames the file on disk.

**Detection (run at the start of every skill that reads/writes the tasks tracking file,
AFTER Protocol: Migrate tasks.md to tasksDir):**

```bash
# Requires Protocol: Resolve Tasks Git Scope to have been executed first
# (TASKS_DIR, TASKS_FILE, TASKS_GIT_SCOPE, TASKS_GIT_REL, tasks_git available).
# TASKS_FILE already points to <tasksDir>/optimus-tasks.md.
OLD_TASKS_FILE="${TASKS_DIR}/tasks.md"
NEEDS_RENAME=0

# Symlink HARD BLOCK — refuse to inspect or operate on symlinked paths.
# Must run BEFORE detection (head -n 1 follows symlinks).
if [ -L "$OLD_TASKS_FILE" ] || [ -L "$TASKS_FILE" ]; then
  echo "ERROR: $OLD_TASKS_FILE or $TASKS_FILE is a symlink — refusing to inspect or rename." >&2
  exit 1
fi

if [ -f "$OLD_TASKS_FILE" ] && [ -f "$TASKS_FILE" ]; then
  if ! head -n 1 "$OLD_TASKS_FILE" 2>/dev/null | grep -q '^<!-- optimus:tasks-v1 -->'; then
    # OLD lacks the optimus marker — it is an unrelated file (Ring pre-dev's
    # Gate 7 tasks.md, etc.). The actual Optimus file is already at TASKS_FILE.
    NEEDS_RENAME=0
  else
    echo "ERROR: Both ${OLD_TASKS_FILE} and ${TASKS_FILE} exist and both appear to be Optimus tracking files." >&2
    echo "       Confirm which is current, remove the stale one, and re-run the skill." >&2
    exit 1
  fi
elif [ -f "$OLD_TASKS_FILE" ] && [ ! -f "$TASKS_FILE" ]; then
  # Only proceed if the legacy file actually has the optimus format marker — otherwise
  # it is some other unrelated tasks.md (e.g., Ring pre-dev's Gate 7 tasks.md) and
  # MUST NOT be touched.
  if head -n 1 "$OLD_TASKS_FILE" 2>/dev/null | grep -q '^<!-- optimus:tasks-v1 -->'; then
    NEEDS_RENAME=1
  fi
fi
```

If `NEEDS_RENAME=0`, the protocol is a no-op (either the new name already exists, the
legacy file is unrelated to optimus, or neither exists).

**Dry-run mode:** If the skill is running in dry-run (per Dry-Run Mode section above),
DO NOT execute the rename. Emit the plan and proceed:

```
[DRY-RUN] Rename would be offered for this task:
[DRY-RUN]   Old name: $OLD_TASKS_FILE
[DRY-RUN]   New name: $TASKS_FILE
[DRY-RUN]   Scope:    $TASKS_GIT_SCOPE
[DRY-RUN]   Would use: git mv (same-repo) OR tasks_git mv (separate-repo)
```

**If `NEEDS_RENAME=1`, ask the user via `AskUser`:**

```
The Optimus tracking file at $OLD_TASKS_FILE uses the previous default name.
Rename to $TASKS_FILE now? (Recommended — Ring pre-dev also produces a tasks.md
in this directory, so the previous name causes a collision.)
```

Options:
- **Rename now** — perform the rename and commit
- **Skip this time** — continue with the legacy name (emit warning; this will collide with Ring pre-dev)
- **Abort** — stop the current command so you can rename manually

**Rename flow (when user chooses "Rename now"):**

Checkpoint file: write `.optimus/.rename-in-progress` BEFORE starting. This marker
lets subsequent invocations detect interrupted renames:

```bash
mkdir -p .optimus
printf '%s\n' "$TASKS_FILE" > .optimus/.rename-in-progress
```

**Scope-branched rename:** explicit `if` so the agent executes the correct branch:

```bash
if [ "$TASKS_GIT_SCOPE" = "same-repo" ]; then
  # Same-repo: atomic git mv in a single commit (preserves history via rename-detect).
  if ! git mv "$OLD_TASKS_FILE" "$TASKS_FILE"; then
    echo "ERROR: git mv failed. Rename aborted — no changes made." >&2
    rm -f .optimus/.rename-in-progress
    exit 1
  fi
  COMMIT_MSG_FILE=$(mktemp -t optimus.XXXXXX) || { echo "ERROR: mktemp failed" >&2; exit 1; }
  chmod 600 "$COMMIT_MSG_FILE"
  printf '%s' "chore(tasks): rename tasks.md to optimus-tasks.md" > "$COMMIT_MSG_FILE"
  if ! git commit -F "$COMMIT_MSG_FILE"; then
    echo "ERROR: Commit failed. Reverting git mv..." >&2
    # Revert: restore old name from HEAD, remove new name from working tree
    git reset HEAD -- "$OLD_TASKS_FILE" "$TASKS_FILE" 2>/dev/null
    git checkout HEAD -- "$OLD_TASKS_FILE" 2>/dev/null
    rm -f "$TASKS_FILE"
    rm -f "$COMMIT_MSG_FILE" .optimus/.rename-in-progress
    exit 1
  fi
  rm -f "$COMMIT_MSG_FILE"
else
  # Separate-repo: rename via tasks_git mv, single commit in tasks repo.
  OLD_TASKS_GIT_REL=$(python3 -c "import os,sys; print(os.path.relpath(sys.argv[1], sys.argv[2]))" \
    "$OLD_TASKS_FILE" "$TASKS_REPO_ROOT" 2>/dev/null)
  if [ -z "$OLD_TASKS_GIT_REL" ]; then
    echo "ERROR: Failed to compute path for legacy file relative to tasks repo." >&2
    rm -f .optimus/.rename-in-progress
    exit 1
  fi
  if ! tasks_git mv "$OLD_TASKS_GIT_REL" "$TASKS_GIT_REL"; then
    echo "ERROR: tasks_git mv failed. Rename aborted — no changes made." >&2
    rm -f .optimus/.rename-in-progress
    exit 1
  fi
  COMMIT_MSG_FILE=$(mktemp -t optimus.XXXXXX) || { echo "ERROR: mktemp failed" >&2; exit 1; }
  chmod 600 "$COMMIT_MSG_FILE"
  printf '%s' "chore(tasks): rename tasks.md to optimus-tasks.md" > "$COMMIT_MSG_FILE"
  if ! tasks_git commit -F "$COMMIT_MSG_FILE"; then
    echo "ERROR: Commit failed in tasks repo. Manual cleanup needed:" >&2
    echo "  cd $TASKS_DIR && git reset HEAD -- $OLD_TASKS_GIT_REL $TASKS_GIT_REL" >&2
    echo "  git checkout HEAD -- $OLD_TASKS_GIT_REL && rm -f $TASKS_GIT_REL" >&2
    rm -f "$COMMIT_MSG_FILE" .optimus/.rename-in-progress
    exit 1
  fi
  rm -f "$COMMIT_MSG_FILE"
fi
```

**Rename success: clear checkpoint marker and log.**
```bash
rm -f .optimus/.rename-in-progress
echo "INFO: Rename completed successfully:" >&2
echo "  - Old name:  $OLD_TASKS_FILE" >&2
echo "  - New name:  $TASKS_FILE" >&2
echo "  - Git scope: $TASKS_GIT_SCOPE" >&2
```

**Post-rename validation:** Verify the moved file still passes Format Validation (see
AGENTS.md Format Validation section). If it fails (e.g., the legacy file was manually
edited and lost the marker), inform user and suggest running `/optimus-import` to rebuild:

```bash
# Post-rename validation — verify the moved file still passes Format Validation.
if ! grep -q '^<!-- optimus:tasks-v1 -->' "$TASKS_FILE"; then
  echo "WARNING: Renamed optimus-tasks.md does not have the optimus format marker." >&2
  echo "         Run /optimus-import to rebuild in the correct format." >&2
fi
if ! grep -q '^## Versions' "$TASKS_FILE"; then
  echo "WARNING: Renamed optimus-tasks.md has no ## Versions section." >&2
  echo "         Run /optimus-import to rebuild in the correct format." >&2
fi
```

**Report success:**
```
Rename complete. The tracking file is now at ${TASKS_FILE}.
Remember to push the tasks repo when you're ready.
```

**Interrupted rename recovery (on skill startup):**

```bash
if [ -f .optimus/.rename-in-progress ]; then
  INTERRUPTED_FILE=$(cat .optimus/.rename-in-progress 2>/dev/null)
  echo "WARNING: Previous rename was interrupted. Expected target: $INTERRUPTED_FILE" >&2
  # AskUser: Retry rename / Clear marker / Abort
fi
```

**If user chose "Skip this time":** Emit a warning and proceed using the legacy name
for this invocation only. The skill MUST use `$OLD_TASKS_FILE` as `$TASKS_FILE` for the
remainder of this execution.

**If user chose "Abort":** **STOP** the current command.

Skills reference this as: "Check optimus-tasks.md rename — see AGENTS.md Protocol: Rename tasks.md to optimus-tasks.md."


### Protocol: Resolve Tasks Git Scope

**Referenced by:** all stage agents (1-4), tasks, batch, resolve, import, resume, report, quick-report

Resolves `TASKS_DIR` (Ring pre-dev root) and `TASKS_FILE` (`<tasksDir>/optimus-tasks.md`), then
detects whether `tasksDir` lives in the same git repo as the project code or in a
**separate** git repo. Exposes a `tasks_git` helper function so skills can run git
commands on optimus-tasks.md uniformly regardless of scope.

```bash
# Step 1: Resolve tasksDir from config.json (if present) or fall back to default.
CONFIG_FILE=".optimus/config.json"
if [ -f "$CONFIG_FILE" ] && jq empty "$CONFIG_FILE" 2>/dev/null; then
  TASKS_DIR=$(jq -r '.tasksDir // "docs/pre-dev"' "$CONFIG_FILE")
else
  TASKS_DIR="docs/pre-dev"
fi
# Reject "null" (jq -r prints literal "null" for JSON null) or empty string.
case "$TASKS_DIR" in
  ""|"null") TASKS_DIR="docs/pre-dev" ;;
esac
# Security: reject TASKS_DIR values starting with "-" (git option injection via
# `git -C --exec-path=...` or similar). Trust boundary: config.json is now gitignored,
# but a user could still receive a malicious config via Slack/email.
case "$TASKS_DIR" in
  -*)
    echo "ERROR: tasksDir cannot start with '-' (security)." >&2
    exit 1
    ;;
esac

# Step 2: Derive TASKS_FILE.
TASKS_FILE="${TASKS_DIR}/optimus-tasks.md"

# Step 3: Detect git scope.
PROJECT_ROOT=$(git rev-parse --show-toplevel 2>/dev/null)
if [ -z "$PROJECT_ROOT" ]; then
  echo "ERROR: Not inside a git repository — optimus requires git." >&2
  exit 1
fi

TASKS_REPO_ROOT=""
if [ -d "$TASKS_DIR" ]; then
  TASKS_REPO_ROOT=$(git -C "$TASKS_DIR" rev-parse --show-toplevel 2>/dev/null || echo "")
fi

if [ -z "$TASKS_REPO_ROOT" ]; then
  if [ -d "$TASKS_DIR" ]; then
    # Directory exists but is NOT inside a git repository — this is a
    # misconfiguration. Without this guard, operations would silently target
    # the project repo and fail confusingly.
    echo "ERROR: tasksDir '$TASKS_DIR' exists but is not inside a git repository." >&2
    echo "Options:" >&2
    echo "  1. Initialize git in tasksDir: git -C \"$TASKS_DIR\" init" >&2
    echo "  2. Point tasksDir to an existing git repo." >&2
    echo "  3. Remove tasksDir to let optimus create it inside the project repo." >&2
    exit 1
  fi
  # Fresh project: tasksDir does not exist yet — assume same-repo.
  # Skills that create optimus-tasks.md will mkdir -p "$TASKS_DIR" first.
  TASKS_GIT_SCOPE="same-repo"
elif [ "$TASKS_REPO_ROOT" = "$PROJECT_ROOT" ]; then
  TASKS_GIT_SCOPE="same-repo"
else
  TASKS_GIT_SCOPE="separate-repo"
fi

# Step 4: Compute the path to pass to git commands.
# In same-repo, git runs from project root and we pass TASKS_FILE as is.
# In separate-repo, git runs with -C "$TASKS_DIR" so paths are relative to TASKS_DIR.
if [ "$TASKS_GIT_SCOPE" = "separate-repo" ]; then
  # python3 is REQUIRED in separate-repo mode to compute the path from the tasks
  # repo root. A naive "optimus-tasks.md" fallback would be wrong when TASKS_DIR is a
  # subdir of the tasks repo (e.g., `tasks-repo/project-alfa/`), because
  # `git show origin/main:optimus-tasks.md` resolves from repo root, not CWD.
  if ! command -v python3 >/dev/null 2>&1; then
    echo "ERROR: python3 is required for separate-repo mode (path computation)." >&2
    echo "Install python3 or point tasksDir inside the project repo." >&2
    exit 1
  fi
  TASKS_GIT_REL=$(python3 -c "import os,sys; print(os.path.relpath(sys.argv[1], sys.argv[2]))" \
    "$TASKS_FILE" "$TASKS_REPO_ROOT" 2>/dev/null)
  if [ -z "$TASKS_GIT_REL" ]; then
    echo "ERROR: Failed to compute TASKS_GIT_REL for '$TASKS_FILE' relative to '$TASKS_REPO_ROOT'." >&2
    exit 1
  fi
else
  TASKS_GIT_REL="$TASKS_FILE"
fi

# Step 5: Resolve the tasks repo's default branch once (used by tasks_git
# operations that reference origin/$DEFAULT). This is DIFFERENT from
# $DEFAULT_BRANCH (the project repo's default).
if [ "$TASKS_GIT_SCOPE" = "separate-repo" ]; then
  TASKS_DEFAULT_BRANCH=$(git -C "$TASKS_DIR" symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's@^refs/remotes/origin/@@')
  if [ -z "$TASKS_DEFAULT_BRANCH" ]; then
    # Fallback: check origin/main vs origin/master existence (deterministic,
    # unlike `git branch --list main master` which can return either arbitrarily).
    if git -C "$TASKS_DIR" show-ref --verify refs/remotes/origin/main >/dev/null 2>&1; then
      TASKS_DEFAULT_BRANCH="main"
    elif git -C "$TASKS_DIR" show-ref --verify refs/remotes/origin/master >/dev/null 2>&1; then
      TASKS_DEFAULT_BRANCH="master"
    fi
  fi
else
  TASKS_DEFAULT_BRANCH=$(git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's@^refs/remotes/origin/@@')
  if [ -z "$TASKS_DEFAULT_BRANCH" ]; then
    if git show-ref --verify refs/remotes/origin/main >/dev/null 2>&1; then
      TASKS_DEFAULT_BRANCH="main"
    elif git show-ref --verify refs/remotes/origin/master >/dev/null 2>&1; then
      TASKS_DEFAULT_BRANCH="master"
    fi
  fi
fi

# Security: reject malformed branch names (prevents injection via
# `git diff origin/<weird>`).
if [ -n "$TASKS_DEFAULT_BRANCH" ] && ! [[ "$TASKS_DEFAULT_BRANCH" =~ ^[a-zA-Z0-9._/-]+$ ]]; then
  echo "ERROR: Invalid TASKS_DEFAULT_BRANCH format: '$TASKS_DEFAULT_BRANCH'" >&2
  exit 1
fi

# Step 6: Define the tasks_git helper.
tasks_git() {
  if [ "$TASKS_GIT_SCOPE" = "separate-repo" ]; then
    git -C "$TASKS_DIR" "$@"
  else
    git "$@"
  fi
}
```

**Usage:**
```bash
tasks_git add "$TASKS_GIT_REL"
tasks_git commit -F "$COMMIT_MSG_FILE"
# IMPORTANT: use $TASKS_DEFAULT_BRANCH (tasks repo default) — NOT $DEFAULT_BRANCH
# (project repo default). They are the same in same-repo mode but may differ in
# separate-repo mode (e.g., tasks repo is `master`, project repo is `main`).
tasks_git diff "origin/$TASKS_DEFAULT_BRANCH" -- "$TASKS_GIT_REL"
tasks_git show "origin/$TASKS_DEFAULT_BRANCH:$TASKS_GIT_REL"
```

**Rule:** Skills MUST use `tasks_git` (never raw `git`) when operating on `$TASKS_FILE`.
Raw `git` on `$TASKS_FILE` breaks in separate-repo mode.

**Rule:** When committing in separate-repo mode, commits land in the tasks repo (not the
project repo). `tasks_git push` pushes the tasks repo. The project repo is unaffected.

Skills reference this as: "Resolve tasks git scope — see AGENTS.md Protocol: Resolve Tasks Git Scope."


<!-- INLINE-PROTOCOLS:END -->
