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
- **Remove worktree**: `git worktree remove <path>` then prune empty parent dirs (see snippet below)
- **Keep**: Leave the worktree as is

**Removal snippet** — after the user picks "Remove worktree":

```bash
git worktree remove "$WORKTREE_PATH"
# Cleanup intermediate parent dirs (e.g., empty .worktrees/feat/ after removing leaf).
# Idempotent: rmdir refuses non-empty dirs silently.
parent="$(dirname "$WORKTREE_PATH")"
while [ "$parent" != "${MAIN_WORKTREE}/.worktrees" ] && [ "$parent" != "/" ]; do
  rmdir "$parent" 2>/dev/null || break
  parent="$(dirname "$parent")"
done
```

This walks up from the removed worktree leaf to `${MAIN_WORKTREE}/.worktrees/` removing
empty intermediate dirs (`feat/`, `fix/`, etc.) but stops at `.worktrees/` itself.

**Edge case — running INSIDE the worktree:** If the agent's current working directory IS
the worktree being removed, `cd` to the main repository first:
1. Identify the main repository path from `git worktree list` (first entry)
2. `cd <main-repo-path>`
3. Then run the **Removal snippet** above.

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

### File Location (summarized)

> **Summary inlined here. Full recipe at `AGENTS.md -> File Location`.**

**Summary:** Defines where Optimus operational files live: `${MAIN_WORKTREE}/.optimus/{state.json, stats.json, sessions/, reports/, logs/}` (gitignored, per-user) vs `<tasksDir>/optimus:tasks.md` + `<tasksDir>/{tasks,subtasks}/` (versioned, project-team-shared, propagated by git). Also: `${MAIN_WORKTREE}/.gitignore` (versioned), `${MAIN_WORKTREE}/.worktrees/` (gitignored linked-worktree dir). Critical contract: `.optimus/*` paths NEVER propagate across linked worktrees (gitignored = not shared by `git worktree add`); use `${MAIN_WORKTREE}/` prefix consistently. See full table in AGENTS.md.

Optimus splits its files into two trees:

### Valid Status Values (stored in state.json) (summarized)

> **Summary inlined here. Full recipe at `AGENTS.md -> Valid Status Values (stored in state.json)`.**

**Summary:** state.json status values: `Pendente` (implicit, no entry), `Validando Spec` (plan), `Em Andamento` (build), `Validando Impl` (review), `DONE` (done), `Cancelado` (tasks/done). Administrative ops (Reopen, Advance, Demote, Cancel) require explicit user confirmation. See full table + transitions in AGENTS.md.

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

### Format Validation (summarized)

> **Summary inlined here. Full recipe at `AGENTS.md -> Format Validation`.**

**Summary:** 15-rule validation for `<tasksDir>/optimus:tasks.md` enforced at Step 1.0.1 of every stage agent (1-4): format marker `<!-- optimus:tasks-v1 -->` present; `## Versions` table with valid columns; all Version Status values valid (`Ativa`/`Próxima`/`Planejada`/`Backlog`/`Concluída`); exactly one `Ativa`, at most one `Próxima`; tasks table columns correct (Status/Branch live in state.json, NOT here); IDs match `T-NNN`; Tipo ∈ {Feature, Fix, Refactor, Chore, Docs, Test}; Priority ∈ {Alta, Media, Baixa}; Depends resolves to existing task rows; Version cells reference existing version rows; no duplicate IDs; no circular dependencies; no unescaped pipes; empty-table guard. HARD BLOCK on any failure — STOP and suggest `/optimus:import`. See full 15-item enumeration in AGENTS.md.

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

### Protocol: Resolve Tasks Git Scope (summarized)

> **Summary inlined here. Full recipe at `AGENTS.md -> Protocol: Resolve Tasks Git Scope`.**

**Summary:** Resolves `TASKS_DIR` (from `.optimus/config.json` `tasksDir` key, default `docs/pre-dev`) and `TASKS_FILE` (`<tasksDir>/optimus:tasks.md`), then detects whether tasksDir lives inside the project repo (`same-repo`) or a separate git repo (`separate-repo`). Sets `TASKS_REPO_ROOT`, `TASKS_GIT_REL`, `TASKS_DEFAULT_BRANCH`, and exposes a `tasks_git()` helper that wraps `git -C "$TASKS_DIR"` in separate-repo mode. Hard guards: reject `tasksDir` starting with `-` (git-option injection), require `python3` for separate-repo path computation, validate `TASKS_DEFAULT_BRANCH` against `^[a-zA-Z0-9._/-]+$`. Skills MUST use `tasks_git` (never raw `git`) on `$TASKS_FILE`. See full recipe in AGENTS.md.

### Protocol: Active Version Guard (summarized)

> **Summary inlined here. Full recipe at `AGENTS.md -> Protocol: Active Version Guard`.**

**Summary:** After task ID/deps confirmed, check the task's Version against the Versions table. If no version is `Ativa` → STOP. If task version matches `Ativa` → proceed silently. Otherwise present `AskUser` with two options: "Move to active version and continue" (updates Version column, commits via `tasks_git`) or "Cancel" (STOP). HARD BLOCK forces explicit version transition before mutating optimus-tasks.md. See full commit recipe in AGENTS.md.

### Protocol: All-Dependencies-Cancelled Resolution (summarized)

> **Summary inlined here. Full recipe at `AGENTS.md -> Protocol: All-Dependencies-Cancelled Resolution`.**

**Summary:** When every dependency in a task's `Depends:` column has status `Cancelado`, emit a multi-option resolution message AFTER the per-dep status check loop populates the `DEP_STATUSES` array. Recipe: iterate `DEP_STATUSES`, set `ALL_CANCELLED=true` if every entry equals `Cancelado`; when `ALL_CANCELLED=true` AND the array is non-empty, print three options to stderr — (a) remove all dependencies, (b) replace with alternative task IDs, (c) cancel the task itself — each with the corresponding `/optimus:tasks` invocation, then `exit 1`. If the array is empty or any dep is non-Cancelado, fall through to per-dep error. Variable contract: `DEP_STATUSES` is the canonical name; adapt if existing skill code uses another. See full recipe in AGENTS.md.

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


### Protocol: Divergence Warning (summarized)

> **Summary inlined here. Full recipe at `AGENTS.md -> Protocol: Divergence Warning`.**

**Summary:** Detects when `optimus-tasks.md` has diverged between the current branch and the tasks repo's default branch. Uses `tasks_git` so it works in both same-repo and separate-repo scopes. Throttles `tasks_git fetch` via a 5-minute cache marker at `${MAIN_WORKTREE}/.optimus/.last-tasks-fetch` (defense-in-depth: validates marker contents are numeric before arithmetic to survive corrupted marker files under `set -euo pipefail`). Compares against `origin/$TASKS_DEFAULT_BRANCH` via `tasks_git diff` limited to `$TASKS_GIT_REL`. On non-empty diff, warns via `AskUser` with options to **Sync now** (merge `origin/<default>`) or **Continue without syncing**. NOT a HARD BLOCK — divergence is a soft warning. Skipped silently when `TASKS_DEFAULT_BRANCH` is unresolved. See full recipe in AGENTS.md.

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


### Protocol: Notification Hooks (summarized)

> **Summary inlined here. Full recipe at `AGENTS.md -> Protocol: Notification Hooks`.**

**Summary:** Optional hook system: stages emit events (`status-change`, `task-blocked`, `task-done`, `task-cancelled`) by invoking `<repo>/tasks-hooks.sh <event> <task_id> <args...>` (or `<repo>/docs/tasks-hooks.sh`) if the file exists and is executable. Hook receives sanitized args (alphanumeric + space + `-_:` only — does NOT allow `.` or `/` to prevent path-traversal if hook authors interpolate args into file paths). Argument shape: 4 args for `status-change`/`task-done`/`task-cancelled` (`event task_id old_status new_status`); 4 args for `task-blocked` (`event task_id current_status reason`). Hooks run in background (`&`) — failures NEVER block the pipeline. Capture `OLD_STATUS` BEFORE writing the new status. See full event signatures + sanitization recipe in AGENTS.md.

### Protocol: Resolve Main Worktree Path (summarized)

> **Summary inlined here. Full recipe at `AGENTS.md -> Protocol: Resolve Main Worktree Path`.**

**Summary:** Resolve `MAIN_WORKTREE` once via `git worktree list --porcelain | awk '/^worktree / {print $2; exit}'` with `${MAIN_WORKTREE:?…}` defensive guard. Use `${MAIN_WORKTREE}/.optimus/...` for ALL `.optimus/` paths (gitignored, so doesn't propagate across linked worktrees). See full recipe in AGENTS.md.

### Protocol: State Management (summarized)

> **Summary inlined here. Full recipe at `AGENTS.md -> Protocol: State Management`.**

**Summary:** Read/write/delete entries in `${MAIN_WORKTREE}/.optimus/state.json` with `jq`. Schema: `{task_id: {status, branch, updated_at}}`. Status values: `Pendente | Validando Spec | Em Andamento | Validando Impl | DONE | Cancelado`. All writes use `jq --arg id "$TASK_ID" --arg status "$NEW_STATUS" '.[$id] = {...}'` (injection-safe), with a tmp-file + `jq empty` validation step before `mv` to guarantee atomicity. Cancelado entries keep `branch: ""` (empty string, NOT absent — readers must treat both as Cancelado-state). Corrupted state.json is removed and treated as empty (reconciliation via worktree scan). state.json is gitignored; never committed. See full recipe in AGENTS.md for jq templates and reconciliation steps.

### Protocol: Terminal Identification (summarized)

> **Summary inlined here. Full recipe at `AGENTS.md -> Protocol: Terminal Identification`.**

**Summary:** `_optimus_set_title <text>` updates the terminal title for iTerm2-on-macOS via AppleScript (`osascript ... set name of s to newName`) — the only channel that reliably mutates `session.name` in "divorced" iTerm2 sessions where OSC 0/1/2 and SetUserVar are ineffective. Used by stage skills to surface task context (e.g., `optimus: PLAN T-007 — User auth`) so users running multiple Optimus sessions can identify them at a glance. The function is auto-inlined into 6 SKILLs by `inline-protocols.py` (do NOT manually paste the body in SKILL.md — F12f rule). Title is informational; failure to set it is non-fatal (silent no-op outside iTerm2/macOS, in Docker/CI without TTY, or when osascript denied). See full bash function in AGENTS.md.

### Protocol: optimus-tasks.md Validation (HARD BLOCK) (summarized)

> **Summary inlined here. Full recipe at `AGENTS.md -> Protocol: optimus-tasks.md Validation (HARD BLOCK)`.**

**Summary:** At Step 1.0.1 of every stage agent: (1) resolve paths via Protocol: Resolve Tasks Git Scope; (2) check `TASKS_FILE` exists, else STOP and suggest `/optimus:import`; (3) run all 15 Format Validation rules, else STOP and suggest `/optimus:import`. HARD BLOCK on any failure. All subsequent skill steps use the resolved `TASKS_FILE` and `tasks_git` helper. See full enumeration in AGENTS.md.

<!-- INLINE-PROTOCOLS:END -->
