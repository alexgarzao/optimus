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
  - "I can resolve it manually" -- Manual resolution risks losing structural changes (dependencies, versions).
  - "It's just one line" -- Even one-line conflicts can silently lose data.
examples:
  - name: Resolve after merge
    invocation: "Resolve tasks.md conflict"
    expected_flow: >
      1. Detect conflict markers in tasks.md
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

# Tasks.md Conflict Resolver

Resolves merge conflicts in `tasks.md` caused by parallel structural edits across feature branches.
Since Status and Branch live in state.json (gitignored), conflicts are limited to structural columns.

**Classification:** Administrative skill — runs on any branch.

**CRITICAL:** Status and Branch live in state.json (gitignored) — they are NOT in tasks.md
and cannot cause merge conflicts. This skill only resolves structural column conflicts
(Title, Tipo, Depends, Priority, Version, Estimate, TaskSpec).

---

## Phase 1: Detect and Parse Conflicts

### Step 1.1: Resolve Paths and Verify Conflict Exists

Execute AGENTS.md Protocol: Resolve Tasks Git Scope. This obtains `TASKS_FILE`,
`TASKS_GIT_SCOPE`, `TASKS_GIT_REL`, and the `tasks_git` helper. In `separate-repo`
scope, merge conflicts are resolved inside the tasks repo (not the project repo).

Check if `tasks.md` has merge conflict markers:

```bash
# TASKS_FILE was set by Protocol: Resolve Tasks Git Scope
grep -c '<<<<<<<' "$TASKS_FILE" 2>/dev/null
```

If no conflict markers found:
- Check if a merge/rebase is in progress in the correct repo:
  - Same-repo: `git status` in project repo
  - Separate-repo: `tasks_git status` in tasks repo
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

Since Status and Branch live in state.json (gitignored, not in tasks.md), conflicts
are limited to structural columns: ID, Title, Tipo, Depends, Priority, Version,
Estimate, TaskSpec. No status ordering or "most-advanced-status rule" is needed.

### Step 2.2: Resolve Each Conflicted Task

For each task that differs between current and incoming:

**NOTE:** Status and Branch are NOT in tasks.md — they live in state.json (gitignored).
Conflicts in tasks.md are limited to structural columns only.

1. Compare the **Estimate** column:
   - If one side has a value and the other has `-` → keep the non-empty value
   - If both have different non-empty values → keep the more specific one (prefer values with units like `2h` over generic `M`)
   - If both are `-` or identical → keep as-is

2. All other columns (Title, Tipo, Priority, Version, Depends, TaskSpec):
   - If unchanged on both sides → keep as-is
   - If changed on one side → keep the change
   - If changed on BOTH sides → flag for user decision (cannot auto-resolve)

### Step 2.3: Handle Structural Conflicts

Since Status and Branch live in state.json (not tasks.md), conflicts are limited to
structural fields. If both sides changed the same structural field (e.g., Priority or
Version), flag for user decision via `AskUser`.

---

## Phase 3: Present Resolution

### Step 3.1: Show Resolution Summary

```markdown
## tasks.md Conflict Resolution

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

- **NEVER lose structural data** — when both sides changed the same field, always ask the user
- **NEVER write the file without user approval** — always preview first
- **NEVER commit automatically** — only stage the file, let the user commit
- Each task row is independent — resolve conflicts per-task, not per-region
- If a conflict involves non-status columns (Title, Priority, Depends) changed on BOTH
  sides, always ask the user — do not guess
- Validate the resolved file before staging — catch format errors before they propagate
- This skill is read-then-write — it modifies ONLY tasks.md, never any other file

<!-- INLINE-PROTOCOLS:START -->
## Shared Protocols (from AGENTS.md)

The following protocols are referenced by this skill. They are
extracted from the Optimus AGENTS.md to make this plugin self-contained.

### Protocol: Resolve Tasks Git Scope

**Referenced by:** all stage agents (1-4), tasks, batch, resolve, import, resume, report, quick-report

Resolves `TASKS_DIR` (Ring pre-dev root) and `TASKS_FILE` (`<tasksDir>/tasks.md`), then
detects whether `tasksDir` lives in the same git repo as the project code or in a
**separate** git repo. Exposes a `tasks_git` helper function so skills can run git
commands on tasks.md uniformly regardless of scope.

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
TASKS_FILE="${TASKS_DIR}/tasks.md"

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
  # Skills that create tasks.md will mkdir -p "$TASKS_DIR" first.
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
  # repo root. A naive "tasks.md" fallback would be wrong when TASKS_DIR is a
  # subdir of the tasks repo (e.g., `tasks-repo/project-alfa/`), because
  # `git show origin/main:tasks.md` resolves from repo root, not CWD.
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
