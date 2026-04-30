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

Then execute the title-setter NOW. Mark terminal session — see AGENTS.md Protocol: Terminal Identification. Use stage label `DONE`:

```bash
_optimus_mark_session DONE "$TASK_ID" "$TASK_TITLE"
```

**On stage completion or exit**, restore the title:

```bash
_optimus_clear_session
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
# Cleanup empty parent dirs (legacy nested layout only — flat layout's parent
# is .worktrees/ directly, so the loop exits after one iteration).
# Idempotent: rmdir refuses non-empty dirs silently.
parent="$(dirname "$WORKTREE_PATH")"
while [ "$parent" != "${MAIN_WORKTREE}/.worktrees" ] && [ "$parent" != "/" ]; do
  rmdir "$parent" 2>/dev/null || break
  parent="$(dirname "$parent")"
done
```

This loop walks up from the removed worktree to `${MAIN_WORKTREE}/.worktrees/` and removes empty parent dirs. With the FLAT layout (`Protocol: Worktree Location`), a flat worktree's parent is `.worktrees/` directly so the loop exits after one iteration. Legacy nested worktrees (still supported for backwards-compat) trigger the loop to clean up their `feat/` / `fix/` parent dir as before.

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


### Protocol: GitHub CLI Check (HARD BLOCK)

**Referenced by:** all stage agents (1-4), tasks, batch

```bash
gh auth status 2>/dev/null
```

If this command fails (exit code != 0), **STOP** immediately:
```
GitHub CLI (gh) is not authenticated. Run `gh auth login` to authenticate before proceeding.
```


### Protocol: Terminal Identification

**Summary:** `_optimus_mark_session <stage> <task_id> <title>` marks the current iTerm2 session with two **focus-independent** signals: an iTerm2 Badge (OSC 1337 SetBadgeFormat) — large semi-transparent overlay text always visible (incl. Mission Control thumbnails and Dock previews) — and a Tab Color (OSC 6 SetColors) tinting the tab per stage (PLAN=blue, BUILD=green, REVIEW=yellow, DONE=gray, RESUME/BATCH=purple). Used by stage skills so users running multiple Optimus sessions can identify each at a glance, even with the window unfocused or backgrounded. Replaces the previous AppleScript title approach which only updated reliably when the iTerm2 tab had focus and required TCC permission. Helper writes to the parent shell's controlling TTY; silent no-op outside iTerm2/macOS. Companion `_optimus_clear_session` resets badge and tab color at stage completion. See full bash function in AGENTS.md.

**Referenced by:** all stage agents (1-4), batch

After the task ID is identified and confirmed, set the terminal title to show the
current stage and task. This allows users running multiple agents in parallel terminals
to identify each terminal at a glance.

**Mark session (after task ID is known):**

```bash
_optimus_mark_session() {
  # iTerm2 Badge + Tab Color marker. Both signals are focus-independent:
  # the Badge (OSC 1337 SetBadgeFormat) renders a large semi-transparent
  # overlay visible in Mission Control and Dock previews even when the
  # window is unfocused. Tab Color (OSC 6) tints the tab itself, visible
  # in the tab bar regardless of which tab is active. Replaces the
  # previous AppleScript title approach, which only worked reliably with
  # focus and required TCC permission. The Execute tool runs bash without
  # a controlling TTY, so we resolve the parent process's TTY via ps and
  # write escape sequences directly to it; iTerm2 interprets OSC 1337
  # and OSC 6 immediately. Silent no-op outside iTerm2/macOS or when the
  # parent TTY cannot be resolved (Docker/CI).
  # $1 = stage label (PLAN|BUILD|REVIEW|DONE|RESUME|BATCH)
  # $2 = task id     (e.g. T-003)
  # $3 = task title  (e.g. "User Auth JWT")
  local stage="$1" task_id="$2" title="$3"
  [ "$LC_TERMINAL" = "iTerm2" ] || [ "$TERM_PROGRAM" = "iTerm.app" ] || return 0

  local pid="$PPID" target_tty=""
  for _ in 1 2 3 4; do
    [ -z "$pid" ] || [ "$pid" = "1" ] && break
    target_tty=$(ps -o tty= -p "$pid" 2>/dev/null | tr -d ' ')
    case "$target_tty" in
      ""|"?"|"??") pid=$(ps -o ppid= -p "$pid" 2>/dev/null | tr -d ' '); target_tty="" ;;
      *) break ;;
    esac
  done

  _optimus_emit() {
    if [ -n "$target_tty" ] && [ -w "/dev/$target_tty" ]; then
      printf '%s' "$1" > "/dev/$target_tty" 2>/dev/null || printf '%s' "$1"
    else
      printf '%s' "$1"
    fi
  }

  local badge_b64
  badge_b64=$(printf '%s %s\n%s' "$stage" "$task_id" "$title" | base64 | tr -d '\n')
  _optimus_emit "$(printf '\e]1337;SetBadgeFormat=%s\a' "$badge_b64")"

  local r g b
  case "$stage" in
    PLAN)   r=66;  g=135; b=245 ;;  # blue
    BUILD)  r=34;  g=197; b=94  ;;  # green
    REVIEW) r=234; g=179; b=8   ;;  # yellow
    DONE)   r=148; g=163; b=184 ;;  # gray
    *)      r=168; g=85;  b=247 ;;  # purple (RESUME/BATCH)
  esac
  _optimus_emit "$(printf '\e]6;1;bg;red;brightness;%d\a\e]6;1;bg;green;brightness;%d\a\e]6;1;bg;blue;brightness;%d\a' "$r" "$g" "$b")"
}
_optimus_mark_session "<STAGE>" "$TASK_ID" "$TASK_TITLE"
```

Example: stage `PLAN`, task `T-003`, title `User Auth JWT` produces a blue tab and an overlay badge reading "PLAN T-003 / User Auth JWT".

**Why escape sequences over AppleScript:** Badge and tab color render immediately on receipt, regardless of focus, in iTerm2 sessions including "divorced" ones. The Execute tool runs `bash -c` without a controlling TTY, so we resolve the parent shell's TTY via `ps` and write the escape sequences there. No TCC prompt, no AppleScript permission dance.

**Restore at stage completion or exit:**

```bash
_optimus_clear_session() {
  [ "$LC_TERMINAL" = "iTerm2" ] || [ "$TERM_PROGRAM" = "iTerm.app" ] || return 0
  local pid="$PPID" target_tty=""
  for _ in 1 2 3 4; do
    [ -z "$pid" ] || [ "$pid" = "1" ] && break
    target_tty=$(ps -o tty= -p "$pid" 2>/dev/null | tr -d ' ')
    case "$target_tty" in
      ""|"?"|"??") pid=$(ps -o ppid= -p "$pid" 2>/dev/null | tr -d ' '); target_tty="" ;;
      *) break ;;
    esac
  done
  _optimus_emit_clear() {
    if [ -n "$target_tty" ] && [ -w "/dev/$target_tty" ]; then
      printf '%s' "$1" > "/dev/$target_tty" 2>/dev/null || printf '%s' "$1"
    else
      printf '%s' "$1"
    fi
  }
  _optimus_emit_clear "$(printf '\e]1337;SetBadgeFormat=\a')"
  _optimus_emit_clear "$(printf '\e]6;1;bg;*;default\a')"
}
_optimus_clear_session
```

**NOTE:** This helper is iTerm2-on-macOS only. Outside iTerm2 (Terminal.app, Ghostty, Warp, Alacritty) or outside macOS, both functions are silent no-ops — users on other terminals see no visual marker.

**Troubleshooting iTerm2:**

1. **Badge invisible despite call succeeding** — Open iTerm2 Preferences > Profiles > [your profile] > Badge. Badge font/color is configured per-profile; if the badge font color matches the background, increase contrast. Default semi-transparent rendering should always be visible.
2. **Tab color appears wrong or doesn't change** — Some iTerm2 themes lock tab background colors. Check Preferences > Appearance > Tabs > "Tab style". `Compact` or `Minimal` styles render tab colors most reliably.
3. **No badge or color in some sessions** — The helper requires the parent process to have a controlling TTY. Inside Docker/CI without a TTY, the function silently no-ops; this is expected.

Skills reference this as: "Mark terminal session — see AGENTS.md Protocol: Terminal Identification."


<!-- INLINE-PROTOCOLS:END -->
