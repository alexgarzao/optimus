---
description: Stage 4 of the task lifecycle. Validates the PR's review feedback (Gate 3) and final state (Gate 4) before marking task as done. If reviewers flagged unresolved comments, suggests /optimus:pr-check before proceeding. Cleans up worktree and branch interactively.
---

# Task Closer

Stage 4 of the task lifecycle. Verifies all prerequisites before marking a task as done.

---

## Phase 1: Identify and Validate Task

### Step 1.0: Verify GitHub CLI (HARD BLOCK)

Verify GitHub CLI — see AGENTS.md Protocol: GitHub CLI Check.

### Step 1.0.1: Resolve and Validate optimus-tasks.md

**HARD BLOCK:** Find and validate optimus-tasks.md — see AGENTS.md Protocol: optimus-tasks.md Validation.

<a id="step-resolve-current-workspace"></a>
### Step 1.0.2: Resolve Current Workspace (HARD BLOCK)

Use the Workspace Auto-Navigation guardrails, but for `done` apply a stricter rule:
when the user does **not** specify a task ID, close only the task from the **current**
feature branch/worktree. Never offer a list of multiple tasks to close.

1. If the user specified a task ID explicitly, resolve that task and perform the usual
   branch-task cross-validation.
2. If the user did **not** specify a task ID:
   - If the current branch is a task feature branch/worktree, resolve the task from the
     current branch and continue.
   - If the current branch is the default branch (or the workspace does not map to exactly
     one task), **STOP** and tell the user:
     ```
     /optimus:done only closes the current task from the current branch.
     Switch to the task branch/worktree first, or run `/optimus:done T-XXX`.
     ```
3. Do NOT scan all `Validando Impl` tasks and do NOT present a multi-task chooser.

### Step 1.0.2.1: Refuse Default Branch (HARD BLOCK)

Refuse to run on default branch — see AGENTS.md Protocol: Default Branch Refusal.

Defense-in-depth: even though Step 1.0.2 already STOPs on the default branch when no
task ID is given, this guard catches the explicit-task-ID path as well — closing a
task while sitting on the default branch is never correct, regardless of how the
skill was invoked.

### Step 1.0.3: Identify Task to Close

**If the user specified a task ID** (e.g., "close T-012"):
- Use the provided task ID
- Confirm with the user using `AskUser`: "I'll close task T-012: [task title]. Correct?"

**If the user did NOT specify a task ID:**
1. Use the task resolved from the current feature branch/worktree in Step 1.0.2
2. If no current task can be resolved safely, **STOP** and ask the user to switch to the
   task branch/worktree or invoke `/optimus:done T-XXX`
3. Do NOT offer multiple tasks as choices

**BLOCKING**: Do NOT proceed until the user confirms which task to close.

### Step 1.0.3.1: Session State (done-specific)

`done` must not offer to resume, start fresh, redo previous stages, or restart the
stage from zero.

If `.optimus/sessions/session-T-XXX.json` exists:
- If it is corrupted or stale, delete it silently and proceed
- Otherwise, reuse/overwrite it for the current `done` execution and proceed
- Do NOT present options like `Resume`, `Start fresh`, or `Continue`

`done` either continues with the current close gates or stops with a clear blocking
message. It never offers to redo `plan`, `build`, or `review`.

**On marking DONE** (Phase 3): delete the session file and restore terminal title.

### Step 1.0.3.2: Set Terminal Title

**CRITICAL:** Set the terminal title so the user can identify this terminal at a glance.

**First, parse `TASK_TITLE` from optimus-tasks.md** — the title is interpolated
into the terminal title below, and parsing it lazily (after the title is set)
results in `optimus: DONE T-XXX — ` with an empty trailing dash:

```bash
# optimus-tasks.md columns by pipe index:
# | 1=<blank> | 2=ID | 3=Title | 4=Tipo | 5=Depends | 6=Priority | 7=Version | 8=Estimate | 9=TaskSpec | 10=<blank> |
# Use the same parser pattern as resume/SKILL.md Step 2.3 (Read Task Metadata).
TASK_TITLE=$(awk -F'|' -v id="$TASK_ID" '
  { gsub(/^[[:space:]]+|[[:space:]]+$/,"",$2) }
  $2 == id {
    title=$3
    gsub(/^[[:space:]]+|[[:space:]]+$/, "", title)
    print title
    exit
  }
' "$TASKS_FILE")

if [ -z "$TASK_TITLE" ]; then
  # Non-fatal: the terminal title is informational. Fall back to a stub so the
  # later interpolation does not produce a trailing-dash artifact.
  TASK_TITLE="(title unavailable)"
fi
```

Then execute the title-setter NOW. Set terminal title — see AGENTS.md Protocol: Terminal Identification. Use stage label `DONE`:

```bash
_optimus_set_title "optimus: DONE $TASK_ID — $TASK_TITLE"
```

**On stage completion or exit**, restore the title:

```bash
_optimus_set_title ""
```

### Step 1.1: Validate Task Status

**HARD BLOCK:** This step is mandatory. Do NOT skip it.

1. Read `optimus-tasks.md` and find the row for the confirmed task ID
2. Read the task's status from state.json — see AGENTS.md Protocol: State Management.
   - If status is `Validando Impl` → proceed (review has completed)
   - If status is `Pendente` → **STOP**: "Task T-XXX is in 'Pendente'. It must go through plan, build, and review first."
   - If status is `Validando Spec` → **STOP**: "Task T-XXX is in 'Validando Spec'. Run build and review first."
   - If status is `Em Andamento` → **STOP**: "Task T-XXX is in 'Em Andamento'. Run review first."
   - If status is `DONE` → **STOP**: "Task T-XXX is already done. Re-execution of done is not supported."
   - If status is `Cancelado` → **STOP**: "Task T-XXX was cancelled. Cannot close a cancelled task."
3. **Check dependencies (HARD BLOCK):** Read the Depends column for this task from optimus-tasks.md.
   - If Depends is `-` → proceed (no dependencies)
   - For each dependency ID listed, read its status from state.json (collecting all statuses into a `DEP_STATUSES` array as you go):
     - If ALL dependencies have status `DONE` → proceed
     - If ANY dependency is NOT `DONE`:
       - Invoke notification hooks (event=`task-blocked`) — see AGENTS.md Protocol: Notification Hooks.
       - **Check all-deps-cancelled** — see AGENTS.md Protocol: All-Dependencies-Cancelled Resolution.
       - If the dependency has status `Cancelado` → **STOP**: `"T-YYY was cancelled (Cancelado). Consider removing this dependency via /optimus:tasks."`
       - Otherwise → **STOP**: `"Task T-XXX depends on T-YYY (status: '<status>'). T-YYY must be DONE first."`
3.1. **Active version guard:** Check active version guard — see AGENTS.md Protocol: Active Version Guard.
4. **Expanded confirmation before status change:**
   - **If the user did NOT specify the task ID explicitly** (auto-detect):
     - Present to the user via `AskUser`:
       ```
       I'm about to close task T-XXX and mark it as DONE (from '<current>').

       **T-XXX: [title]**
       **Version:** [version from table]

       Confirm close?
       ```
     - **BLOCKING:** Do NOT proceed to the close checklist until the user confirms
   - **If the user specified the task ID explicitly** (e.g., "close T-012"):
     - Skip expanded confirmation (user already has context)

   **NOTE:** done does not support re-execution (status always changes to `DONE`), so the re-execution skip does not apply here.

### Step 1.2: Check optimus-tasks.md Divergence (warning)

Check optimus-tasks.md divergence — see AGENTS.md Protocol: Divergence Warning.

---

## Phase 2: Close Gates

Run gates sequentially. Each gate is a **HARD BLOCK** — if it fails, STOP immediately.

### Gate 1: No Uncommitted Changes

```bash
git status --porcelain
```

- **PASS:** Output is empty → proceed to Gate 2
- **FAIL → HARD BLOCK:**
  ```
  Uncommitted changes found:
    M src/handler.go
    ?? new_file.go

  Commit or discard these changes before running done.
  ```
  **STOP** — do NOT proceed.

### Gate 2: No Unpushed Commits

```bash
git rev-parse --abbrev-ref @{u} 2>/dev/null
```

- **If no upstream:** HARD BLOCK — "Branch has no upstream. Run `git push -u origin \"$(git branch --show-current)\"` first."
- **If upstream exists:**
  ```bash
  git log @{u}..HEAD --oneline
  ```
  - **PASS:** Output is empty → proceed to Gate 3
  - **FAIL → HARD BLOCK:** "N unpushed commits. Run `git push` first."

### Gate 3: PR Review Feedback

Before validating final PR state (Gate 4), check whether reviewers (CodeRabbit,
DeepSource, humans) flagged feedback that has not been addressed. The point is
to make the user aware **before** the PR is merged and the task is closed.

```bash
HEAD_BRANCH=$(git branch --show-current 2>/dev/null)
if [ -z "$HEAD_BRANCH" ]; then
  echo "ERROR: Cannot determine current branch. Checkout the task branch first."
  # STOP — HARD BLOCK
fi

# Fetch PR metadata ONCE — shared by Gate 3 (review feedback) and Gate 4 (final state).
PR_JSON=$(gh pr list --head "$HEAD_BRANCH" --json number,state,reviewDecision --jq '.[0]')
if [ $? -ne 0 ]; then
  echo "ERROR: GitHub CLI failed. Check network and run 'gh auth status'."
  # STOP — HARD BLOCK (cannot verify PR state)
fi

PR_NUM=$(printf '%s' "$PR_JSON" | jq -r '.number // empty' 2>/dev/null)
PR_STATE=$(printf '%s' "$PR_JSON" | jq -r '.state // empty' 2>/dev/null)
PR_DECISION=$(printf '%s' "$PR_JSON" | jq -r '.reviewDecision // empty' 2>/dev/null)
```

- **gh command failed (non-zero exit):** HARD BLOCK — cannot verify PR state
- **No PR exists** (PR_NUM empty): PASS → proceed (task went directly to default branch)

**`reviewDecision` values from GitHub:**
| Value | Meaning |
|---|---|
| `APPROVED` | At least one approving review; no requested changes outstanding |
| `CHANGES_REQUESTED` | At least one reviewer requested changes; not yet resolved |
| `REVIEW_REQUIRED` | Required reviewers have not reviewed yet |
| `null`/empty | No reviews yet, or reviews are advisory only |

**Decision logic:**

- **PR_DECISION is empty / null / `APPROVED`:** PASS → proceed to Gate 4
- **PR_DECISION is `CHANGES_REQUESTED`:** Ask via `AskUser`:
  ```
  PR #${PR_NUM} has unresolved review feedback (reviewDecision=CHANGES_REQUESTED).
  How would you like to proceed?
  ```
  Options:
  - **Run `/optimus:pr-check` now** (Recommended) — invoke the pr-check skill to
    fetch all comments and address them iteratively. After pr-check completes,
    re-run `/optimus:done` to re-evaluate this gate.
  - **Override (I have addressed all comments)** — proceed to Gate 4. Useful when
    the user has already resolved everything via the GitHub UI but reviewers
    haven't dismissed/re-approved. Logs a warning to `.optimus/logs/`.
  - **Cancel** — STOP, do not change task status.
- **PR_DECISION is `REVIEW_REQUIRED`:** soft warning + `AskUser`:
  ```
  PR #${PR_NUM} is awaiting required reviewers. Proceed anyway?
  ```
  Options:
  - **Wait — cancel `done`** — STOP. Re-run when reviewers respond.
  - **Proceed anyway** — continue to Gate 4 (typical when waiting on a long-tail
    reviewer and the team agrees to merge async).

If the user picks "Run `/optimus:pr-check` now", invoke the `optimus-pr-check`
skill via the `Skill` tool. After it completes, re-fetch `PR_JSON` and re-evaluate
Gate 3. Loop up to 3 times to avoid infinite back-and-forth; if still
`CHANGES_REQUESTED` after 3 iterations, fall through to the override/cancel
prompt.

### Gate 4: PR in Final State

Reuses `PR_STATE` from the metadata fetched in Gate 3.

- **PR state is MERGED:** PASS → proceed
- **PR state is CLOSED (not merged):** Ask via `AskUser`:
  ```
  PR #${PR_NUM} was closed without merging. How should this task be marked?
  ```
  Options:
  - **Mark as DONE** — task is complete despite PR closure (e.g., changes landed another way)
  - **Mark as Cancelado** — task was abandoned
  - **Cancel** — stop, do not change status
- **PR state is OPEN → HARD BLOCK:**
  ```
  PR #${PR_NUM} is still open. Merge or close the PR before running done.
  Lint, tests, and CI validation happen in the PR pipeline — not in done.
  ```
  **STOP** — do NOT proceed.

---

## Phase 3: Mark Task as Done

All gates passed. Mark the task:

1. Update status to `DONE` (or `Cancelado` if user chose that in Gate 3) in state.json — see AGENTS.md Protocol: State Management.
2. Invoke notification hooks (event=`status-change`) — see AGENTS.md Protocol: Notification Hooks.
3. If DONE: invoke notification hooks (event=`task-done`).
   If Cancelado: invoke notification hooks (event=`task-cancelled`).
4. Proceed to Phase 4 (cleanup).

---

## Phase 4: Cleanup (after marking DONE)

This phase runs ONLY after the task has been marked as `DONE` (or `Cancelado`).

### Step 4.1: Check for Task Worktree

**IMPORTANT:** Worktree must be removed BEFORE attempting branch deletion.

Resolve the worktree from the source-of-truth: read the task's branch from
state.json (set by Workspace Auto-Navigation in earlier stages), then match it
against `git worktree list --porcelain`. This avoids substring false positives
on short task IDs (e.g., `T-1` matching `T-10`, `T-100`).

```bash
# Resolve main worktree — see AGENTS.md Protocol: Resolve Main Worktree Path.
MAIN_WORKTREE="${MAIN_WORKTREE:-$(git worktree list --porcelain 2>/dev/null | awk '/^worktree / {print $2; exit}')}"
MAIN_WORKTREE="${MAIN_WORKTREE:?MAIN_WORKTREE not resolved — not in a git repository}"
TASK_BRANCH=$(jq -r --arg id "$TASK_ID" '.[$id].branch // ""' "${MAIN_WORKTREE}/.optimus/state.json" 2>/dev/null)

WORKTREE_PATH=""
if [ -n "$TASK_BRANCH" ]; then
  # Match by branch (exact, deterministic) — porcelain output has one
  # `worktree <path>` line followed by `branch refs/heads/<name>` per entry.
  WORKTREE_PATH=$(git worktree list --porcelain 2>/dev/null | awk -v br="refs/heads/$TASK_BRANCH" '
    /^worktree / { path=$2 }
    /^branch /   { if ($2 == br) { print path; exit } }
  ')
fi

if [ -z "$WORKTREE_PATH" ]; then
  # Fallback: anchored kebab-cased path-segment match — never `grep -iF "$TASK_ID"`,
  # which would match T-1 against T-10/T-100.
  TASK_KEBAB="-$(echo "$TASK_ID" | tr '[:upper:]' '[:lower:]')-"
  WORKTREE_PATH=$(git worktree list --porcelain 2>/dev/null \
    | awk -v anchor="$TASK_KEBAB" '/^worktree / { path=$2; if (index(tolower(path), anchor) > 0) { print path; exit } }')
fi
```

If a worktree is found (`WORKTREE_PATH` non-empty), ask via `AskUser`:
```
Task T-XXX is done. A worktree still exists at '<path>'. What should I do?
```
Options:
- **Remove worktree**: `git worktree remove <path>`
- **Keep**: Leave the worktree as is

**Edge case — running INSIDE the worktree:** If the agent's current working directory IS
the worktree being removed, `cd` to the main repository first:
1. Identify the main repository path from `git worktree list` (first entry)
2. `cd <main-repo-path>`
3. Then `git worktree remove <worktree-path>`

### Step 4.2: Check for Task Branch

Identify the task's branch (resolve `MAIN_WORKTREE` first so `state.json` is
read from the main worktree, not from a linked worktree's isolated copy):

```bash
# Resolve main worktree — see AGENTS.md Protocol: Resolve Main Worktree Path.
MAIN_WORKTREE="${MAIN_WORKTREE:-$(git worktree list --porcelain 2>/dev/null | awk '/^worktree / {print $2; exit}')}"
MAIN_WORKTREE="${MAIN_WORKTREE:?MAIN_WORKTREE not resolved — not in a git repository}"
TASK_BRANCH=$(jq -r --arg id "$TASK_ID" '.[$id].branch // ""' "${MAIN_WORKTREE}/.optimus/state.json" 2>/dev/null)
if [ -z "$TASK_BRANCH" ]; then
  TASK_BRANCH=$(git branch --list "*$(echo "$TASK_ID" | tr '[:upper:]' '[:lower:]')*" 2>/dev/null | head -1 | tr -d ' *')
fi
```

If the branch exists (locally and/or remotely), ask via `AskUser`:
```
Task T-XXX is done. The branch '<branch>' still exists. What should I do?
```
Options:
- **Delete local and remote**: switch to default branch, pull, then delete
- **Delete local only**: switch to default branch, delete local
- **Keep**: Leave the branch as is

**Final confirmation for destructive options:** If the user selects "Delete local and remote"
or "Delete local only", present a final confirmation via `AskUser`:
"This will permanently delete branch `<branch>`. Are you sure?" Options: Yes, delete / Cancel.

**Before deleting:** switch to the default branch first. Use the canonical
deterministic recipe — see AGENTS.md Protocol: Default Branch Resolution.

```bash
# Resolve DEFAULT_BRANCH deterministically — see AGENTS.md Protocol: Default Branch Resolution.
DEFAULT_BRANCH=""
if symref=$(git symbolic-ref --short refs/remotes/origin/HEAD 2>/dev/null); then
  DEFAULT_BRANCH="${symref#origin/}"
elif git show-ref --verify --quiet refs/heads/main; then
  DEFAULT_BRANCH="main"
elif git show-ref --verify --quiet refs/heads/master; then
  DEFAULT_BRANCH="master"
fi
if [ -z "$DEFAULT_BRANCH" ]; then
  echo "ERROR: Could not determine default branch (no origin/HEAD, no main, no master)." >&2
  echo "       Set it with: git remote set-head origin <branch>" >&2
  # STOP — do not proceed with branch deletion
fi
git checkout "$DEFAULT_BRANCH"
git pull

# Local delete first; -d (safe) preferred over -D
if ! git branch -d "$TASK_BRANCH" 2>/dev/null; then
  if ! LOCAL_DELETE_OUTPUT=$(git branch -D "$TASK_BRANCH" 2>&1); then
    echo "ERROR: Could not delete local branch $TASK_BRANCH: $LOCAL_DELETE_OUTPUT" >&2
    # AskUser:
    #   "Local branch delete failed. How should I proceed?"
    #   - **Continue cleanup anyway** — proceed (e.g., the user will clean up manually)
    #   - **Abort cleanup** — STOP without attempting remote deletion
  fi
fi

# Remote delete with explicit failure-cause classification.
# `DELETE_REMOTE` is "yes" only when the user picked "Delete local and remote".
if [ "$DELETE_REMOTE" = "yes" ]; then
  if ! PUSH_OUTPUT=$(git push origin --delete "$TASK_BRANCH" 2>&1); then
    PUSH_RC=$?
    # Classify the failure so the user gets actionable diagnostics.
    case "$PUSH_OUTPUT" in
      *"remote ref does not exist"*|*"deleted reference"*)
        echo "ℹ Remote branch already deleted upstream (rc=$PUSH_RC) — local cleanup complete." >&2
        REMOTE_DELETE_RESULT="already-deleted"
        ;;
      *"protected branch"*|*"protection"*)
        echo "✗ Remote branch is protected — cannot delete (rc=$PUSH_RC)." >&2
        echo "  Local branch deleted; remote branch will need manual cleanup or branch-protection adjustment." >&2
        REMOTE_DELETE_RESULT="protected"
        ;;
      *"could not read"*|*"unable to access"*|*"connection"*|*"timed out"*|*"timeout"*|*"Network"*)
        echo "✗ Network error pushing branch deletion (rc=$PUSH_RC):" >&2
        echo "  $PUSH_OUTPUT" >&2
        echo "  Local branch deleted; retry or run \`git push origin --delete $TASK_BRANCH\` manually after restoring connectivity." >&2
        REMOTE_DELETE_RESULT="network-error"
        ;;
      *)
        echo "✗ Remote branch delete failed (rc=$PUSH_RC): $PUSH_OUTPUT" >&2
        REMOTE_DELETE_RESULT="other-error"
        ;;
    esac

    # AskUser (integrate the classification message above into the body):
    #   "Remote branch deletion failed (<classification>). What should I do?"
    #   - **Ignore and continue** — leave the remote branch as is (logged with `pending-remote-delete`)
    #   - **Retry now** — re-run `git push origin --delete "$TASK_BRANCH"` once
    #   - **Abort cleanup** — STOP; user will resolve manually
    #
    # Notify the user via Hooks if available (event=`pending-remote-delete`).
    # Tag the task in state.json with `pending_remote_delete: true` so a future
    # operation (e.g., a follow-up `done`, or a maintenance script) can retry.
  else
    REMOTE_DELETE_RESULT="ok"
  fi
fi
```

**Partial-state contract on failure:** if remote deletion fails after local
deletion succeeds, the task is `DONE` and the local branch is gone, but the
remote branch may persist. The task is flagged with `pending_remote_delete`
in state.json so it can be retried later. The Cleanup Summary (Step 4.3) MUST
reflect this partial state — do NOT report "Deleted" for the remote when the
push failed.

### Step 4.3: Cleanup Summary

```markdown
## Cleanup Summary for T-XXX

| Resource | Status | Action Taken |
|----------|--------|-------------|
| Worktree `/path/to/wt` | Found | Removed / Kept |
| Branch `<tipo>/t-xxx-...` (local) | Found | Deleted / Kept |
| Branch `<tipo>/t-xxx-...` (remote) | Found | Deleted / Kept |
```

---

## Rules

- Gates are sequential hard blocks — stop at the first failure
- Do NOT change task status unless ALL gates pass
- After marking as done, update state.json (no commit needed — it's gitignored)
- Lint, tests, and CI are the responsibility of the PR pipeline — done does NOT run them
- To cancel a task without going through gates, use `/optimus:tasks cancel`
- **Next step suggestion:** After the cleanup summary, inform the user: "Task T-XXX is done.
  Run `/optimus:report` to see updated project status and what to work on next."

### Dry-Run Mode

Follow AGENTS.md Protocol: Dry-Run Mode. The canonical rules apply uniformly
to plan/build/review/done — see the inlined Protocol: Dry-Run Mode block below.

**Stage-4 (done) specifics:**
- The "no status change" rule means skip the DONE status update.
- The "no fix application" rule means skip Phase 4 (cleanup) entirely.
- All 3 gates (Phase 2) still run in full so the user sees what would have
  happened.

<!-- INLINE-PROTOCOLS:START -->
## Shared Protocols (from AGENTS.md)

The following protocols are referenced by this skill. They are
extracted from the Optimus AGENTS.md to make this plugin self-contained.

### File Location

Optimus splits its files into two trees:

**Operational tree (`.optimus/`) — 100% gitignored, per-user/per-machine:**

```
.optimus/
├── config.json          # gitignored — optional overrides (tasksDir, defaultScope)
├── state.json           # gitignored — operational state (status, branch per task)
├── stats.json           # gitignored — stage execution counters per task
├── sessions/            # gitignored — session state for crash recovery
└── reports/             # gitignored — exported reports
```

**Planning tree (`<tasksDir>/`) — versioned, shared with the team:**

```
<tasksDir>/              # default: docs/pre-dev/
├── optimus-tasks.md     # versioned — structural task data (NO status, NO branch)
├── tasks/               # versioned — Ring pre-dev task specs (task_001.md, ...)
└── subtasks/            # versioned — Ring pre-dev subtask specs (T-001/, ...)
```

**Configuration** (optional) is stored in `.optimus/config.json`:

```json
{
  "tasksDir": "docs/pre-dev",
  "defaultScope": "ativa"
}
```

- **`tasksDir`** (optional): Path to the Ring pre-dev artifacts root. Default:
  `docs/pre-dev`. The import and stage agents look for `optimus-tasks.md`, `tasks/`, and
  `subtasks/` inside this directory. Can point to a path inside the project repo
  (default case) OR to a path in a separate git repo (for teams that separate task
  tracking from code).
- **`defaultScope`** (optional): Default version scope used by `report` and `quick-report`
  when the user does not specify one in the invocation. Valid values: `ativa`, `upcoming`,
  `all`, or a specific version name (must exist in the Versions table). When set, skills
  skip the "Which version scope do you want to see?" prompt. See Protocol: Default Scope
  Resolution.

Since `config.json` is gitignored, it exists ONLY when the user overrides a default.
Projects using the defaults do not need a `config.json`.

**Tasks file** is always at `<tasksDir>/optimus:tasks.md` (derived from `tasksDir`).

**Operational state** is stored in `.optimus/state.json` (gitignored):

```json
{
  "T-001": { "status": "DONE", "branch": "feat/t-001-setup-auth", "updated_at": "2025-01-15T10:30:00Z" },
  "T-003": { "status": "Em Andamento", "branch": "feat/t-003-user-registration", "updated_at": "2025-01-16T14:00:00Z" }
}
```

- Each key is a task ID. A task with no entry is `Pendente` (implicit default).
- `status`: current pipeline stage (see Valid Status Values).
- `branch`: the derived branch name, stored for quick reference (always re-derivable).
- Stage agents read and write this file — never optimus-tasks.md — for status changes.
- If state.json is lost, status can be reconstructed: task with a worktree = in progress,
  without = Pendente. The agent asks the user to confirm before proceeding.

**Stage execution stats** are stored in `.optimus/stats.json` (gitignored):

```json
{
  "T-001": { "plan_runs": 2, "review_runs": 3, "last_plan": "2025-01-15T10:30:00Z", "last_review": "2025-01-16T14:00:00Z" },
  "T-002": { "plan_runs": 1, "review_runs": 0 }
}
```

- Each key is a task ID. Values track how many times `plan` and `review` executed on the task.
- A high `plan_runs` signals unclear or problematic specs. A high `review_runs` signals
  complex review cycles or specification gaps.
- The file is created on first use by `plan` or `review`. If missing, agents treat all
  counters as 0.
- `report` reads this file to display churn metrics.

Agents resolve paths:
1. **Read `.optimus/config.json`** for `tasksDir` if it exists. Fallback: `docs/pre-dev`.
2. **Tasks file:** `${tasksDir}/optimus:tasks.md` (derived, not configurable separately).
3. **If `<tasksDir>/optimus:tasks.md` not found:** **STOP** and suggest running `import` to create one.

Everything inside `.optimus/` is gitignored. The planning tree (`<tasksDir>/optimus:tasks.md`,
`<tasksDir>/tasks/`, `<tasksDir>/subtasks/`) is versioned (structural data shared with
the team) — but the repo that versions it depends on `tasksDir`: if `tasksDir` is inside
the project repo, it is committed alongside the code; if `tasksDir` is in a separate
repo, it is committed there.


### Valid Status Values (stored in state.json)

Status lives in `.optimus/state.json`, NOT in optimus-tasks.md. A task with no entry in
state.json is implicitly `Pendente`.

| Status | Set by | Meaning |
|--------|--------|---------|
| `Pendente` | Initial (implicit) | Not started — no entry in state.json |
| `Validando Spec` | plan | Spec being validated |
| `Em Andamento` | build | Implementation in progress |
| `Validando Impl` | review | Implementation being reviewed |
| `DONE` | done | Completed |
| `Cancelado` | tasks, done | Task abandoned, will not be implemented |

**Administrative status operations** (managed by tasks, not by stage agents):
- **Reopen:** `DONE` → `Pendente` (remove entry from state.json) or `Em Andamento` (if worktree exists) — when a bug is found after close. Also accepts `Cancelado` → `Pendente` — when a cancellation decision is reversed.
- **Advance:** move forward one stage — when work was done manually outside the pipeline
- **Demote:** move backward one stage — when rework is needed after review
- **Cancel:** any non-terminal → `Cancelado` — task will not be implemented

These operations require explicit user confirmation.


### Format Validation

Every stage agent (1-4) MUST validate the optimus-tasks.md format before operating:
1. **First line** is `<!-- optimus:tasks-v1 -->` (format marker)
2. A `## Versions` section exists with a table containing columns: Version, Status, Description
3. All Version Status values are valid (`Ativa`, `Próxima`, `Planejada`, `Backlog`, `Concluída`)
4. Exactly one version has Status `Ativa`
5. At most one version has Status `Próxima`
6. A markdown table exists with columns: ID, Title, Tipo, Depends, Priority, Version (Estimate and TaskSpec are optional — tables without them are still valid). **Status and Branch columns are NOT expected** — they live in state.json.
7. All task IDs follow the `T-NNN` pattern
8. All Tipo values are one of: `Feature`, `Fix`, `Refactor`, `Chore`, `Docs`, `Test`
9. All Depends values are either `-` or comma-separated valid task IDs that exist as rows in the tasks table (not just matching `T-NNN` pattern — the referenced task must actually exist)
10. All Priority values are one of: `Alta`, `Media`, `Baixa`
11. All Version values reference a version name that exists in the Versions table
12. No duplicate task IDs
13. No circular dependencies in the dependency graph (e.g., T-001 → T-002 → T-001)

If the format marker is missing or validation fails, the agent must **STOP** and suggest
running `/optimus:import` to fix the format. Do NOT attempt to interpret malformed data.

14. No unescaped pipe characters (`|`) in task titles (breaks markdown table parsing)
15. **Empty table handling:** If the tasks table exists but has zero data rows (only headers),
format validation PASSES. Stage agents (1-4) MUST check for this condition immediately after
format validation and before task identification. If zero data rows: **STOP** and inform the
user: "No tasks found in optimus-tasks.md. Use `/optimus:tasks` to create a task or `/optimus:import`
to import from Ring pre-dev." Do NOT proceed to task identification with an empty table.

**NOTE:** For circular dependency detection (item 13), trace the full dependency chain for
each task. If any task appears twice in the chain, a cycle exists. Report ALL tasks involved
in the cycle so the user can fix it with `/optimus:tasks`.


### Protocol: Resolve Tasks Git Scope

**Referenced by:** all stage agents (1-4), tasks, batch, resolve, import, resume, report, quick-report

Resolves `TASKS_DIR` (Ring pre-dev root) and `TASKS_FILE` (`<tasksDir>/optimus:tasks.md`), then
detects whether `tasksDir` lives in the same git repo as the project code or in a
**separate** git repo. Exposes a `tasks_git` helper function so skills can run git
commands on optimus-tasks.md uniformly regardless of scope.

```bash
# Step 0: Resolve main worktree — see AGENTS.md Protocol: Resolve Main Worktree Path.
# Required because .optimus/config.json is gitignored and lives only in the main
# worktree's filesystem; resolving it relative to PWD would miss it from a linked
# worktree.
MAIN_WORKTREE="$(git worktree list --porcelain 2>/dev/null | awk '/^worktree / {print $2; exit}')"
if [ -z "$MAIN_WORKTREE" ]; then
  echo "ERROR: Cannot determine main worktree — not in a git repository." >&2
  exit 1
fi
# Step 1: Resolve tasksDir from config.json (if present) or fall back to default.
CONFIG_FILE="${MAIN_WORKTREE}/.optimus/config.json"
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
TASKS_FILE="${TASKS_DIR}/optimus:tasks.md"

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


### Protocol: Active Version Guard

**Referenced by:** all stage agents (1-4)

After the task ID is confirmed and dependencies are validated, check if the task belongs
to the `Ativa` version. If not, present options before proceeding.

1. Read the task's **Version** column from `optimus-tasks.md`
2. Read the **Versions** table and find the version with Status `Ativa`
   - **If no version has Status `Ativa`** → **STOP**: "No active version found in the Versions table. Run `/optimus:tasks` to set a version as Ativa before proceeding."
3. **If the task's version matches the `Ativa` version** → proceed silently
4. **If the task's version does NOT match the `Ativa` version** → present via `AskUser`:
   ```
   Task T-XXX is in version '<task_version>' (<version_status>),
   but the active version is '<active_version>'.
   To execute this task, it must be moved to the active version first.
   ```
   Options:
   - **Move to active version and continue** — updates the Version column to the active version, commits, and proceeds
   - **Cancel** — stops execution

5. **If "Move to active version and continue":**
   - Update the task's Version column in `optimus-tasks.md` to the `Ativa` version name
   - Commit using `tasks_git` so the change lands in the correct repo (same-repo or
     separate-repo, as resolved by Protocol: Resolve Tasks Git Scope):
     ```bash
     tasks_git add "$TASKS_GIT_REL"
     COMMIT_MSG_FILE=$(mktemp -t optimus.XXXXXX) || { echo "ERROR: mktemp failed" >&2; exit 1; }
     chmod 600 "$COMMIT_MSG_FILE"
     printf '%s' "chore(tasks): move T-XXX to active version <active_version>" > "$COMMIT_MSG_FILE"
     tasks_git commit -F "$COMMIT_MSG_FILE"
     rm -f "$COMMIT_MSG_FILE"
     ```
   - Proceed with the stage

6. **If "Cancel":** **STOP** — do not proceed with the stage

Skills reference this as: "Check active version guard — see AGENTS.md Protocol: Active Version Guard."


### Protocol: All-Dependencies-Cancelled Resolution

**Referenced by:** plan, build, review, done, batch

When all dependencies of a task are status `Cancelado`, emit a multi-option resolution
message AFTER the per-dependency status check (i.e., after detecting that every dep is
`Cancelado`, before the per-dep error-and-exit). The check supplements the per-dep loop;
it does not replace it.

**Variable contract:** the caller's dep-check loop populates an array `DEP_STATUSES`
with one status string per dependency (the same status read from `state.json` for each
dep ID listed in the Depends column). If the existing skill code uses a different
variable name, adapt the recipe below to match — the contract is "an iterable of
dependency status strings".

**Bash recipe:**

```bash
# Assumes DEP_STATUSES is an array of dependency status strings,
# already populated by the caller's dep-check loop.
ALL_CANCELLED=true
for dep_status in "${DEP_STATUSES[@]}"; do
  if [ "$dep_status" != "Cancelado" ]; then
    ALL_CANCELLED=false
    break
  fi
done

if [ "$ALL_CANCELLED" = true ] && [ "${#DEP_STATUSES[@]}" -gt 0 ]; then
  echo "All dependencies of $TASK_ID are cancelled. To unblock:" >&2
  echo "  (a) remove all dependencies: /optimus:tasks edit $TASK_ID" >&2
  echo "  (b) replace with alternative task IDs: /optimus:tasks edit $TASK_ID" >&2
  echo "  (c) cancel $TASK_ID: /optimus:tasks cancel $TASK_ID" >&2
  exit 1
fi
# Per-dep message follows here (existing logic).
```

Skills reference this as: "Check all-deps-cancelled — see AGENTS.md Protocol: All-Dependencies-Cancelled Resolution."


### Protocol: Default Branch Refusal (HARD BLOCK)

**Referenced by:** build, review, done

**Why:** Workspace Auto-Navigation is the primary safeguard, but it can be bypassed
in edge cases (user cancels the AskUser prompt, silent failure, future skill that
forgets to invoke the protocol). A second, unconditional refusal at the start of any
mutating stage prevents accidental commits, worktree removals, or status writes on
the default branch.

```bash
DEFAULT_BRANCH=$(git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's@^refs/remotes/origin/@@')
if [ -z "$DEFAULT_BRANCH" ]; then
  if git show-ref --verify refs/remotes/origin/main >/dev/null 2>&1; then
    DEFAULT_BRANCH="main"
  elif git show-ref --verify refs/remotes/origin/master >/dev/null 2>&1; then
    DEFAULT_BRANCH="master"
  fi
fi
CURRENT=$(git branch --show-current 2>/dev/null)
if [ -n "$DEFAULT_BRANCH" ] && [ "$CURRENT" = "$DEFAULT_BRANCH" ]; then
  echo "ERROR: refusing to run /optimus-<stage> on default branch '$CURRENT'." >&2
  echo "       Switch to the task's feature branch (Workspace Auto-Navigation should have handled this)." >&2
  exit 1
fi
```

**Where to invoke:** immediately after Workspace Auto-Navigation completes, before
the skill performs any state.json write, git commit, git worktree mutation, or
status transition.

Skills reference this as: "Refuse to run on default branch (HARD BLOCK) — see AGENTS.md Protocol: Default Branch Refusal."


### Protocol: Default Branch Resolution

**Referenced by:** done (cleanup), Workspace Auto-Navigation, Default Branch Refusal,
Resolve Tasks Git Scope, Push Commits.

**Why:** Several skills need to resolve the project repo's default branch (the
branch to checkout before deleting a feature branch, the branch the workspace
auto-navigation refuses to mutate, etc.). Non-deterministic resolutions like
`git branch --list main master | head -1` return whichever entry git happens to
list first — which depends on collation and on whether both branches exist
locally. The recipe below is fully deterministic.

**Recipe:**

```bash
# Deterministic default-branch resolution: prefer remote symbolic-ref
# (origin/HEAD), then verify against `main` first, then `master`, then bail.
DEFAULT_BRANCH=""
if symref=$(git symbolic-ref --short refs/remotes/origin/HEAD 2>/dev/null); then
  DEFAULT_BRANCH="${symref#origin/}"
elif git show-ref --verify --quiet refs/heads/main; then
  DEFAULT_BRANCH="main"
elif git show-ref --verify --quiet refs/heads/master; then
  DEFAULT_BRANCH="master"
fi

if [ -z "$DEFAULT_BRANCH" ]; then
  echo "ERROR: Could not determine default branch (no origin/HEAD, no main, no master)" >&2
  exit 1
fi
```

**Resolution order (deterministic):**

1. `origin/HEAD` symbolic-ref — the canonical answer when `gh repo clone`/
   `git clone` has set it. Fastest and works even when neither `main` nor
   `master` exists locally.
2. Local `refs/heads/main` — second-best signal: if the user has `main`
   checked out at all, it is overwhelmingly the default.
3. Local `refs/heads/master` — fall-back for legacy repos.
4. None of the above → hard error. The user must run
   `git remote set-head origin <branch>` (or fetch from origin) before any
   skill that needs the default branch can proceed.

**Why prefer `main` before `master` in the fallback chain:** when
`origin/HEAD` is absent (e.g., shallow clone, fresh repo, broken remote),
both `main` and `master` may exist locally as orphans. Probing `main` first
biases toward the modern default rather than the historical one.

**`git branch --list main master | head -1` is forbidden:** it returns
whichever name sorts first alphabetically (`main` always wins), which only
*happens* to look correct — but it also returns `main` when only `master`
actually exists locally (because `head -1` on empty stdout is empty). Any
skill that needs the default branch MUST use the recipe above.

Skills reference this as: "Resolve default branch — see AGENTS.md Protocol: Default Branch Resolution."


### Protocol: Divergence Warning

**Referenced by:** all stage agents (1-4)

Since status and branch data live in state.json (gitignored), optimus-tasks.md rarely changes
on feature branches. This protocol detects the uncommon case where optimus-tasks.md WAS modified
(e.g., Active Version Guard moved a task). It uses `tasks_git` so it works in both
same-repo and separate-repo scopes.

**Prerequisite:** Protocol: Resolve Tasks Git Scope must have been executed so
`TASKS_FILE`, `TASKS_GIT_REL`, `TASKS_GIT_SCOPE`, `TASKS_DEFAULT_BRANCH`, and
`tasks_git` are defined.

```bash
# Requires Protocol: Resolve Main Worktree Path to have run first
# (or resolve inline; see that protocol).
MAIN_WORKTREE="$(git worktree list --porcelain 2>/dev/null | awk '/^worktree / {print $2; exit}')"
MAIN_WORKTREE="${MAIN_WORKTREE:?MAIN_WORKTREE not resolved — not in a git repository}"
if [ -z "$TASKS_DEFAULT_BRANCH" ]; then
  echo "WARNING: Cannot determine default branch for tasks repo. Skipping divergence check."
  # Skip — this is a warning, not a HARD BLOCK
else
  # Throttle fetch: only re-fetch if the cached timestamp is older than 5 minutes.
  # Each stage skill would otherwise pay ~2s network latency per invocation.
  # The cache lives in the PROJECT repo's .optimus/ (always present, gitignored).
  FETCH_MARKER="${MAIN_WORKTREE}/.optimus/.last-tasks-fetch"
  NOW_EPOCH=$(date +%s)
  SHOULD_FETCH=1
  if [ -f "$FETCH_MARKER" ]; then
    LAST_EPOCH=$(cat "$FETCH_MARKER" 2>/dev/null || echo 0)
    # Defense-in-depth: ensure marker contents are numeric before arithmetic.
    # A corrupted/manually-edited marker file would otherwise crash the
    # `$((NOW_EPOCH - LAST_EPOCH))` expression under `set -euo pipefail`.
    [[ "$LAST_EPOCH" =~ ^[0-9]+$ ]] || LAST_EPOCH=0
    if [ -n "$LAST_EPOCH" ] && [ "$((NOW_EPOCH - LAST_EPOCH))" -lt 300 ]; then
      SHOULD_FETCH=0
    fi
  fi
  if [ "$SHOULD_FETCH" = "1" ]; then
    if tasks_git fetch origin "$TASKS_DEFAULT_BRANCH" --quiet 2>/dev/null; then
      mkdir -p "${MAIN_WORKTREE}/.optimus"
      printf '%s' "$NOW_EPOCH" > "$FETCH_MARKER"
    else
      echo "WARNING: Could not fetch from origin. Divergence check may use stale data."
    fi
  fi
  tasks_git diff "origin/$TASKS_DEFAULT_BRANCH" -- "$TASKS_GIT_REL" 2>/dev/null | head -20
fi
```

- If diff output is non-empty → warn via `AskUser`:
  ```
  optimus-tasks.md has diverged between your branch and <default_branch>.
  This may cause merge conflicts when the PR is merged.
  ```
  Options:
  - **Sync now** — run `tasks_git merge origin/<default_branch>` to incorporate changes
  - **Continue without syncing** — I'll handle conflicts later
- If diff output is empty → proceed silently (files are in sync)
- **NOTE:** This is a warning, not a HARD BLOCK. The user may choose to continue.
- **NOTE:** In separate-repo scope, "diverged" means the tasks repo branches diverge —
  not the project code branches.

Skills reference this as: "Check optimus-tasks.md divergence — see AGENTS.md Protocol: Divergence Warning."


## Protocol: Dry-Run Mode

**Referenced by:** plan, build, review, done (all stage agents 1-4).

All stage agents support **dry-run mode**. When the user includes "dry-run" or
"preview" in their invocation (e.g., "dry-run spec T-003", "preview review T-012"),
the agent MUST:

1. **Run all analysis/validation phases normally** — agent dispatch, findings, etc.
2. **Do NOT change task status** — skip the status update step in state.json.
3. **Do NOT commit or push anything** — no git operations that modify state.
4. **Do NOT create workspaces** — skip branch/worktree creation (stage-1 only).
5. **Do NOT apply fixes** — skip batch-apply phases.
6. **Do NOT increment stage stats** — skip the Increment Stage Stats protocol.
7. **Do NOT write session files** — session state is for crash recovery of real
   executions, not previews.
8. **Skip convergence rounds 2+** — round 1 (primary review pass) is sufficient
   for preview; do NOT enter the convergence loop.
9. **Present results as informational** — phrase the summary as "what would happen"
   without implying any side effects occurred.

Stage agents may add stage-specific dry-run notes (e.g., which phase numbers
to skip), but MUST NOT relax any of the rules above. The point of dry-run is
to give the user a reliable preview with zero state mutation.


### Protocol: GitHub CLI Check (HARD BLOCK)

**Referenced by:** all stage agents (1-4), tasks, batch

```bash
gh auth status 2>/dev/null
```

If this command fails (exit code != 0), **STOP** immediately:
```
GitHub CLI (gh) is not authenticated. Run `gh auth login` to authenticate before proceeding.
```


### Protocol: Notification Hooks

**Referenced by:** all stage agents (1-4), tasks

After writing a status change to state.json, invoke notification hooks if present.

**IMPORTANT — Capture timing:** Read the current status from state.json and store it as
`OLD_STATUS` BEFORE writing the new status. The sequence is:
1. Read current status (with guard for missing/empty state.json):
   ```bash
   if [ -f "$STATE_FILE" ]; then
     OLD_STATUS=$(jq -r --arg id "$TASK_ID" '.[$id].status // "Pendente"' "$STATE_FILE" 2>/dev/null)
     [ -z "$OLD_STATUS" ] && OLD_STATUS="Pendente"
   else
     OLD_STATUS="Pendente"
   fi
   ```
2. Write new status to state.json
3. Invoke hooks with `OLD_STATUS` and new status

**IMPORTANT:** Always quote all arguments and sanitize user-derived values to prevent
shell injection. Hook scripts MUST NOT pass their arguments to `eval` or shell
interpretation — treat all arguments as untrusted data.

```bash
# Sanitize: allow only safe characters. Does NOT allow `.` or `/` (which would
# enable path-traversal if hook args flow into file paths).
_optimus_sanitize() { printf '%s' "$1" | tr -cd '[:alnum:][:space:]-_:'; }

# Resolve HOOKS_FILE with an explicit if-elif-else (instead of the fragile
# `test && echo || (test && echo)` pattern).
if [ -f ./tasks-hooks.sh ]; then
  HOOKS_FILE="./tasks-hooks.sh"
elif [ -f ./docs/tasks-hooks.sh ]; then
  HOOKS_FILE="./docs/tasks-hooks.sh"
else
  HOOKS_FILE=""
fi

if [ -n "$HOOKS_FILE" ] && [ -x "$HOOKS_FILE" ]; then
  "$HOOKS_FILE" "$(_optimus_sanitize "$event")" "$(_optimus_sanitize "$task_id")" "$(_optimus_sanitize "$old_status")" "$(_optimus_sanitize "$new_status")" 2>/dev/null &
fi
```

Events and their parameter signatures:

| Event | Parameters | Description |
|-------|-----------|-------------|
| `status-change` | `event task_id old_status new_status` | Any status transition |
| `task-done` | `event task_id old_status "DONE"` | Task marked as done |
| `task-cancelled` | `event task_id old_status "Cancelado"` | Task cancelled |
| `task-blocked` | `event task_id current_status reason` | Dependency check failed (4 args — includes reason) |

When a dependency check fails (provide defaults so hook payload is never malformed):
```bash
: "${dep_id:=unknown}"
: "${dep_status:=unknown}"
if [ -n "$HOOKS_FILE" ] && [ -x "$HOOKS_FILE" ]; then
  "$HOOKS_FILE" "task-blocked" "$(_optimus_sanitize "$task_id")" "$(_optimus_sanitize "$current_status")" "$(_optimus_sanitize "blocked by $dep_id ($dep_status)")" 2>/dev/null &
fi
```

Hooks run in background (`&`) and their failure does NOT block the pipeline.
If `tasks-hooks.sh` does not exist, hooks are silently skipped.

Skills reference this as: "Invoke notification hooks — see AGENTS.md Protocol: Notification Hooks."


### Protocol: Resolve Main Worktree Path

**Referenced by:** all skills that read or write `.optimus/` operational files (state.json, stats.json, sessions, reports, logs, and checkpoint markers).

**Why:** `.optimus/` is gitignored. Git does NOT propagate ignored files across linked worktrees (`git worktree add` creates a sibling working tree but does not share gitignored files). When a skill runs from a linked worktree (the common case for `/optimus:build`, `/optimus:review`, `/optimus:done` which default to the task's worktree), reads and writes against `.optimus/state.json` resolve to the worktree's isolated copy. Updates never reach the main worktree. When the linked worktree is later removed (e.g., by `/optimus:done` cleanup), the writes are lost — silent data loss.

**Recipe:**

```bash
MAIN_WORKTREE="$(git worktree list --porcelain 2>/dev/null | awk '/^worktree / {print $2; exit}')"
if [ -z "$MAIN_WORKTREE" ]; then
  echo "ERROR: Cannot determine main worktree — not in a git repository." >&2
  exit 1
fi
```

The first `worktree` line in `git worktree list --porcelain` is always the main worktree (where the bare `.git/` directory or the repo's HEAD lives), regardless of where the command is run from.

**Path resolution pattern:**

After resolving `MAIN_WORKTREE`, every `.optimus/` path MUST be prefixed:

```bash
# RIGHT (works from any worktree):
STATE_FILE="${MAIN_WORKTREE}/.optimus/state.json"
SESSION_FILE="${MAIN_WORKTREE}/.optimus/sessions/session-${TASK_ID}.json"
STATS_FILE="${MAIN_WORKTREE}/.optimus/stats.json"
mkdir -p "${MAIN_WORKTREE}/.optimus/sessions" \
         "${MAIN_WORKTREE}/.optimus/reports" \
         "${MAIN_WORKTREE}/.optimus/logs"

# WRONG (resolves against PWD, breaks in linked worktrees):
STATE_FILE=".optimus/state.json"
SESSION_FILE=".optimus/sessions/session-${TASK_ID}.json"
STATS_FILE=".optimus/stats.json"
mkdir -p .optimus/sessions .optimus/reports .optimus/logs
```

**What does NOT need this protocol:**

- `<tasksDir>/optimus:tasks.md` and `<tasksDir>/tasks/`, `<tasksDir>/subtasks/` — versioned content, propagated by git across worktrees automatically.
- `.optimus/config.json` — when **versioned** (legacy projects), it propagates via git; when **gitignored** (current default), it suffers the same isolation as state.json. **Treat `.optimus/config.json` as gitignored and resolve via `$MAIN_WORKTREE` for safety in current projects** — the cost is a single `git worktree list` call.
- `.gitignore` itself — versioned, propagated via git.

**Idempotency:** the resolution is read-only against git metadata; safe to call multiple times in the same skill execution. Cache `MAIN_WORKTREE` in a local variable rather than re-running `git worktree list` for each path.

Skills reference this as: "Resolve main worktree — see AGENTS.md Protocol: Resolve Main Worktree Path."


### Protocol: State Management

**Referenced by:** all stage agents (1-4), tasks, report, quick-report, import, batch

All status and branch data is stored in `.optimus/state.json` (gitignored).

**Prerequisites:**

```bash
if ! command -v jq >/dev/null 2>&1; then
  echo "ERROR: jq is required for state management but not installed." >&2
  exit 1
fi
```

**Reading state:**

```bash
# Requires Protocol: Resolve Main Worktree Path to have run first
# (or resolve inline; see that protocol).
MAIN_WORKTREE="$(git worktree list --porcelain 2>/dev/null | awk '/^worktree / {print $2; exit}')"
MAIN_WORKTREE="${MAIN_WORKTREE:?MAIN_WORKTREE not resolved — not in a git repository}"
STATE_FILE="${MAIN_WORKTREE}/.optimus/state.json"
if [ -f "$STATE_FILE" ]; then
  # Validate JSON integrity before reading
  if ! jq empty "$STATE_FILE" 2>/dev/null; then
    echo "WARNING: state.json is corrupted. Running reconciliation."
    rm -f "$STATE_FILE"
    # Fall through to missing-file handling below
  fi
fi
if [ -f "$STATE_FILE" ]; then
  TASK_STATUS=$(jq -r --arg id "$TASK_ID" '.[$id].status // "Pendente"' "$STATE_FILE")
  TASK_BRANCH=$(jq -r --arg id "$TASK_ID" '.[$id].branch // ""' "$STATE_FILE")
else
  TASK_STATUS="Pendente"
  TASK_BRANCH=""
fi
```

A task with no entry in state.json is implicitly `Pendente`.

**Writing state:**

```bash
# Requires Protocol: Resolve Main Worktree Path to have run first
# (or resolve inline; see that protocol).
MAIN_WORKTREE="$(git worktree list --porcelain 2>/dev/null | awk '/^worktree / {print $2; exit}')"
MAIN_WORKTREE="${MAIN_WORKTREE:?MAIN_WORKTREE not resolved — not in a git repository}"
# Initialize .optimus directory — see AGENTS.md Protocol: Initialize .optimus Directory.
STATE_FILE="${MAIN_WORKTREE}/.optimus/state.json"
if [ ! -f "$STATE_FILE" ]; then
  echo '{}' > "$STATE_FILE"
fi
if [ -z "$TASK_ID" ] || [ -z "$NEW_STATUS" ]; then
  echo "ERROR: Cannot write state — TASK_ID or NEW_STATUS is empty." >&2
  exit 1
fi
UPDATED_AT=$(date -u +%Y-%m-%dT%H:%M:%SZ)
if jq --arg id "$TASK_ID" --arg status "$NEW_STATUS" --arg branch "$BRANCH_NAME" --arg ts "$UPDATED_AT" \
  '.[$id] = {status: $status, branch: $branch, updated_at: $ts}' "$STATE_FILE" > "${STATE_FILE}.tmp"; then
  if jq empty "${STATE_FILE}.tmp" 2>/dev/null; then
    mv "${STATE_FILE}.tmp" "$STATE_FILE"
  else
    rm -f "${STATE_FILE}.tmp"
    echo "ERROR: jq produced invalid JSON — state.json unchanged" >&2
    exit 1
  fi
else
  rm -f "${STATE_FILE}.tmp"
  echo "ERROR: jq failed to update state.json" >&2
  exit 1
fi
```

**Removing entry (for Pendente reset):**

```bash
# Requires Protocol: Resolve Main Worktree Path to have run first
# (or resolve inline; see that protocol).
MAIN_WORKTREE="$(git worktree list --porcelain 2>/dev/null | awk '/^worktree / {print $2; exit}')"
MAIN_WORKTREE="${MAIN_WORKTREE:?MAIN_WORKTREE not resolved — not in a git repository}"
STATE_FILE="${MAIN_WORKTREE}/.optimus/state.json"
if [ ! -f "$STATE_FILE" ]; then
  echo "state.json does not exist — task is already implicitly Pendente."
else
  if jq --arg id "$TASK_ID" 'del(.[$id])' "$STATE_FILE" > "${STATE_FILE}.tmp"; then
    mv "${STATE_FILE}.tmp" "$STATE_FILE"
  else
    rm -f "${STATE_FILE}.tmp"
    echo "ERROR: jq failed to update state.json"
  fi
fi
```

**Listing all tasks with status (for report/quick-report):**

```bash
# Requires Protocol: Resolve Main Worktree Path to have run first
# (or resolve inline; see that protocol).
MAIN_WORKTREE="$(git worktree list --porcelain 2>/dev/null | awk '/^worktree / {print $2; exit}')"
MAIN_WORKTREE="${MAIN_WORKTREE:?MAIN_WORKTREE not resolved — not in a git repository}"
STATE_FILE="${MAIN_WORKTREE}/.optimus/state.json"
# TASKS_FILE is resolved via Protocol: Resolve Tasks Git Scope (<tasksDir>/optimus:tasks.md).
# Validate state.json if it exists
if [ -f "$STATE_FILE" ] && ! jq empty "$STATE_FILE" 2>/dev/null; then
  echo "WARNING: state.json is corrupted. Treating all tasks as Pendente."
  rm -f "$STATE_FILE"
fi
# Get all task IDs from optimus-tasks.md
TASK_IDS=$(grep -E '^\| T-[0-9]+ \|' "$TASKS_FILE" | awk -F'|' '{print $2}' | tr -d ' ')
# For each task, read status from state.json (default: Pendente)
for TASK_ID in $TASK_IDS; do
  if [ -f "$STATE_FILE" ]; then
    STATUS=$(jq -r --arg id "$TASK_ID" '.[$id].status // "Pendente"' "$STATE_FILE")
  else
    STATUS="Pendente"
  fi
  echo "$TASK_ID: $STATUS"
done
```

**Cancelado state.json shape contract:**
When a task transitions to status `Cancelado`, the `branch` field MUST remain present
in the state.json entry but MAY be set to empty string `""` (NOT removed) if the
underlying branch was deleted by the cancel flow. Readers MUST treat `"branch": ""`
as a valid Cancelado-state sentinel; they MUST NOT treat absence of the `branch`
field as a meaningful state difference. The State Management writer ALWAYS produces
the full `{status, branch, updated_at}` triple.

**state.json is NEVER committed.** It is gitignored. No `git add` or `git commit`
for state changes.

**Reconciliation (if state.json is lost or empty):**
1. List all worktrees: `git worktree list`
2. For each worktree matching a task ID pattern (e.g., `t-003` in the path),
   infer status as `Em Andamento` (most common in-progress status)
3. Tasks without worktrees are `Pendente`
4. Ask the user to confirm before proceeding

**Automatic mismatch detection:** Stage agents SHOULD check for inconsistencies on startup:
if state.json is missing or empty AND worktrees exist for known task IDs, warn the user
and offer to run reconciliation before proceeding. This prevents tasks from silently
appearing as `Pendente` when they actually have active worktrees.

Skills reference this as: "Read/write state.json — see AGENTS.md Protocol: State Management."


### Protocol: Terminal Identification

**Referenced by:** all stage agents (1-4), batch

After the task ID is identified and confirmed, set the terminal title to show the
current stage and task. This allows users running multiple agents in parallel terminals
to identify each terminal at a glance.

**Set title (after task ID is known):**

```bash
_optimus_set_title() {
  # iTerm2 AppleScript title updater. Empirical testing showed that Optimus
  # tasks always run in "divorced" iTerm2 sessions where the profile's
  # autoNameFormat is locked to a literal — OSC 0/1/2 and OSC 1337
  # SetUserVar are both ineffective in that state, so AppleScript's
  # `set name of s` is the only channel that actually mutates session.name.
  # The Execute tool runs bash without a controlling TTY, so /dev/tty fails
  # with ENODEV; we resolve the parent process's TTY via ps instead. Walk
  # up to 4 ancestors in case of nested shells. First run triggers a macOS
  # TCC prompt ("droid wants to control iTerm"); approving enables this
  # permanently. Silent no-op outside macOS/iTerm2 or when osascript is
  # unavailable — non-iTerm2 / non-macOS users get no title update.
  local title="$1"
  local pid="$PPID" tty=""
  for _ in 1 2 3 4; do
    [ -z "$pid" ] || [ "$pid" = "1" ] && break
    tty=$(ps -o tty= -p "$pid" 2>/dev/null | tr -d ' ')
    case "$tty" in
      ""|"?"|"??") pid=$(ps -o ppid= -p "$pid" 2>/dev/null | tr -d ' ') ;;
      *) break ;;
    esac
  done
  if { [ "$LC_TERMINAL" = "iTerm2" ] || [ "$TERM_PROGRAM" = "iTerm.app" ]; } \
     && command -v osascript >/dev/null 2>&1 && [ -n "$tty" ] \
     && [ "$tty" != "?" ] && [ "$tty" != "??" ]; then
    osascript \
      -e 'on run argv' \
      -e '  set targetTty to "/dev/" & item 1 of argv' \
      -e '  set newName to item 2 of argv' \
      -e '  tell application "iTerm2"' \
      -e '    repeat with w in windows' \
      -e '      repeat with t in tabs of w' \
      -e '        repeat with s in sessions of t' \
      -e '          if (tty of s as string) is targetTty then' \
      -e '            try' \
      -e '              set name of s to newName' \
      -e '            end try' \
      -e '          end if' \
      -e '        end repeat' \
      -e '      end repeat' \
      -e '    end repeat' \
      -e '  end tell' \
      -e 'end run' \
      -- "$tty" "$title" >/dev/null 2>&1 || true
  fi
}
_optimus_set_title "optimus: <STAGE> $TASK_ID — $TASK_TITLE"
```

Example output in terminal tab: `optimus: REVIEW T-003 — User Auth JWT`

**Why the parent-process TTY:** The Execute tool runs `bash -c` without a controlling
terminal, so `/dev/tty` returns `ENODEV` ("Device not configured"). The resolver above
asks `ps` for the parent's controlling TTY device path and matches it against iTerm2's
session list via AppleScript — that device is connected to the user's real iTerm2
session. If no ancestor has a TTY (Docker/CI) or osascript is unavailable, the
function silently no-ops.

**Restore title (at stage completion or exit):**

```bash
_optimus_set_title ""
```

**NOTE:** This helper is iTerm2-on-macOS only. Optimus tasks always run in
"divorced" iTerm2 sessions, where AppleScript's `set name of s` is the only
channel that reliably mutates `session.name`. Non-iTerm2 / non-macOS users
will not see a title update.

**Troubleshooting iTerm2 (if the title still doesn't update):**

1. **Window > Edit Tab Title** must be empty. A manually-set tab title is
   sticky on the tab label and overrides the session name visually, even
   when `session.name` is updated correctly underneath.
2. The first run on macOS triggers a TCC prompt ("`droid` wants to control
   `iTerm`"). Approve it to enable the helper. Denying makes the helper a
   silent no-op.
3. The helper requires the parent process to have a controlling TTY. Inside
   Docker/CI without a TTY, no ancestor will resolve and the helper will
   silently no-op.

Skills reference this as: "Set terminal title — see AGENTS.md Protocol: Terminal Identification."


### Protocol: optimus-tasks.md Validation (HARD BLOCK)

**Referenced by:** all stage agents (1-4), tasks, batch. Note: resolve performs inline format validation in its own Step 4.2.

Every stage agent MUST validate optimus-tasks.md before operating. The full validation rules are
defined in the "Format Validation" section above (items 1-15). This protocol is the
executable version:

1. **Resolve paths and git scope:** Execute Protocol: Resolve Tasks Git Scope (below) to
   resolve `TASKS_DIR`, `TASKS_FILE`, `TASKS_GIT_SCOPE`, and the `tasks_git` helper.
2. **Find optimus-tasks.md:** Check if `TASKS_FILE` exists. If not found, **STOP** and suggest `/optimus:import`.
3. **Validate format:** Execute all 15 validation checks from the "Format Validation" section. If the format marker is missing or any check fails, **STOP** and suggest `/optimus:import`.

**All subsequent references to `optimus-tasks.md` in the skill use the resolved `TASKS_FILE` path.
All references to Ring pre-dev artifacts use `TASKS_DIR` as the root** — never hardcoded paths.
**All git operations on optimus-tasks.md use the `tasks_git` helper** (which handles both same-repo
and separate-repo scopes).

Skills reference this as: "Find and validate optimus-tasks.md (HARD BLOCK) — see AGENTS.md Protocol: optimus-tasks.md Validation."


<!-- INLINE-PROTOCOLS:END -->
