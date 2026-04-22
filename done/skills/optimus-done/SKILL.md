---
name: optimus-done
description: "Stage 5 of the task lifecycle. Verifies all prerequisites before marking a task as done: no uncommitted changes, no unpushed commits, PR ready to merge (if applicable), CI passing, tests and lint passing locally. During cleanup, offers to merge the PR (user chooses merge strategy via AskUser)."
trigger: >
  - After optimus-pr-check has completed for a task (optional), or after optimus-check
  - When user requests closing a task (e.g., "close T-012", "mark T-012 as done")
skip_when: >
  - Task has not been through at least check yet
  - Task is already done
prerequisite: >
  - Task exists in tasks.md with status "Validando Impl" or "Revisando PR" in state.json
  - At least check has completed (pr-check is optional)
NOT_skip_when: >
  - "Everything is already ready" -- Verify it. Do not assume.
  - "Tests passed in CI" -- Also run locally to confirm.
  - "It's a small task" -- All tasks need the same close verification.
examples:
  - name: Close a completed task
    invocation: "Close task T-012"
    expected_flow: >
      1. Confirm task ID with user
      2. Validate status is "Validando Impl" or "Revisando PR"
      3. Run close checklist (8 verifications: git state, lint, tests)
      4. If all pass, mark as DONE
      5. Write DONE status to state.json
  - name: Close with failures
    invocation: "Close task T-012"
    expected_flow: >
      1. Confirm task ID
      2. Validate status
      3. Run checklist -- uncommitted changes found
      4. Report what's missing, do NOT change status
  - name: Force close (skip checklist)
    invocation: "Force close T-012" or "force done T-012"
    expected_flow: >
      1. Confirm task ID
      2. Validate status
      3. Skip the 8-check checklist
      4. Warn user about risks
      5. Mark as DONE after explicit confirmation
related:
  complementary:
    - optimus-pr-check
    - optimus-check
  sequence:
    after:
      - optimus-check
      - optimus-pr-check
verification:
  manual:
    - All checklist items passed
    - Task status updated to DONE in state.json
---

# Task Closer

Stage 5 of the task lifecycle. Verifies all prerequisites before marking a task as done.

---

## Phase 1: Identify and Validate Task

### Step 1.0: Verify GitHub CLI (HARD BLOCK)

Verify GitHub CLI — see AGENTS.md Protocol: GitHub CLI Check.

### Step 1.0.1: Find and Validate tasks.md

**HARD BLOCK:** Find and validate tasks.md — see AGENTS.md Protocol: tasks.md Validation.

### Step 1.0.2: Resolve Workspace (HARD BLOCK)
Resolve workspace — see AGENTS.md Protocol: Workspace Auto-Navigation. Branch-task cross-validation is included in this protocol.

### Step 1.0.3: Identify Task to Close

**If the user specified a task ID** (e.g., "close T-012"):
- Use the provided task ID
- Confirm with the user using `AskUser`: "I'll close task T-012: [task title]. Correct?"

**If the user did NOT specify a task ID:**
1. Look for tasks with status `Validando Impl` or `Revisando PR`
2. If exactly one found, suggest it
3. If multiple found, ask the user which one to close
4. If none found, inform the user there are no tasks ready to close

**BLOCKING**: Do NOT proceed until the user confirms which task to close.

### Step 1.0.3.1: Check Session State

Execute session state protocol — see AGENTS.md Protocol: Session State. Use stage=`done`, status=`DONE`.

**On marking DONE** (Phase 3): delete the session file.

### Step 1.1: Validate Task Status

**HARD BLOCK:** This step is mandatory. Do NOT skip it.

1. Read `tasks.md` and find the row for the confirmed task ID
2. Read the task's status from state.json — see AGENTS.md Protocol: State Management.
   - If status is `Validando Impl` → proceed (check has completed, pr-check was skipped)
   - If status is `Revisando PR` → proceed (pr-check has completed)
   - If status is `Pendente` → **STOP**: "Task T-XXX is in 'Pendente'. It must go through plan, build, and check first."
   - If status is `Validando Spec` → **STOP**: "Task T-XXX is in 'Validando Spec'. Run build and check first."
   - If status is `Em Andamento` → **STOP**: "Task T-XXX is in 'Em Andamento'. Run check first."
   - If status is `DONE` → **STOP**: "Task T-XXX is already done. Re-execution of done is not supported."
   - If status is `Cancelado` → **STOP**: "Task T-XXX was cancelled. Cannot close a cancelled task."
3. **Check dependencies (HARD BLOCK):** Read the Depends column for this task from tasks.md.
   - If Depends is `-` → proceed (no dependencies)
   - For each dependency ID listed, read its status from state.json:
     - If ALL dependencies have status `DONE` → proceed
     - If ANY dependency is NOT `DONE`:
       - Invoke notification hooks (event=`task-blocked`) — see AGENTS.md Protocol: Notification Hooks.
       - If the dependency has status `Cancelado` → **STOP**: `"T-YYY was cancelled (Cancelado). Consider removing this dependency via /optimus-tasks."`
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

### Step 1.2: Check tasks.md Divergence (warning)

Check tasks.md divergence — see AGENTS.md Protocol: Divergence Warning.

### Step 1.3: Push Unpushed Commits (if any)

Previous stages may have code commits that were not pushed. Before running the close checklist, ensure the feature branch is in sync with remote.

**Step 1 — Check if upstream tracking exists:**

```bash
git rev-parse --abbrev-ref @{u} 2>/dev/null
```

- **If command fails (no upstream):** The branch was never pushed. Push with `-u` to create the upstream:
  ```bash
  git push -u origin "$(git branch --show-current)"
  ```
- **If command succeeds (upstream exists):** Check for unpushed commits:
  ```bash
  git log @{u}..HEAD --oneline
  ```
  If there are unpushed commits, push them: `git push`

**Why check upstream first:** `git log @{u}..HEAD` silently produces empty output when no upstream exists, making it appear there's nothing to push. But in reality ALL local commits are unpushed because the remote branch doesn't exist yet. Without this check, the close checklist would pass while the feature branch was never pushed — and branch deletion in cleanup would lose all work.

**Why push now:** The close checklist (Check 2) verifies "no unpushed commits". Without this step, Check 2 would fail if there are legitimate code commits that were never pushed.

---

## Phase 2: Close Checklist

Run ALL verifications. Do NOT stop at the first failure — run all of them and report the full picture.

### Group A: Git & PR State

#### Check 1: No Uncommitted Changes

```bash
git status --porcelain
```

- **PASS:** Output is empty
- **FAIL:** List the uncommitted files

#### Check 2: No Unpushed Commits

First verify upstream exists, then check for unpushed commits:

```bash
# Step 1: verify upstream exists
git rev-parse --abbrev-ref @{u} 2>/dev/null
# Step 2: if upstream exists, check for unpushed commits
git log @{u}..HEAD --oneline
```

- **PASS:** Upstream exists AND output of `git log` is empty (local is in sync with remote)
- **FAIL (no upstream):** "Branch has no upstream tracking. Run `git push -u origin \"$(git branch --show-current)\"` first."
- **FAIL (unpushed commits):** List the unpushed commits

#### Check 3: PR Ready to Merge (if applicable)

Check if a PR exists for the current branch or task branch:

```bash
PR_JSON=$(gh pr list --head "$(git branch --show-current)" --json number,state,title,reviewDecision --jq '.[0]' 2>/dev/null)
PR_NUMBER=$(echo "$PR_JSON" | jq -r '.number // empty')
PR_STATE=$(echo "$PR_JSON" | jq -r '.state // empty')
PR_TITLE=$(echo "$PR_JSON" | jq -r '.title // empty')
```

**Store `PR_NUMBER` for use in Check 4.**

- **If no PR exists** (`PR_NUMBER` is empty): PASS (task went directly to default branch)
- **If PR exists and state is MERGED:** PASS
- **If PR exists and state is CLOSED (not merged):** FAIL — "PR #$PR_NUMBER was closed without merging."
- **If PR exists and state is OPEN:**
  1. **Validate PR title:** See AGENTS.md Protocol: PR Title Validation. If invalid → FAIL.
  2. **If title is valid:** PASS.

**NOTE:** This check validates PR state and title only. CI status is checked separately in Check 4.

#### Check 4: CI Passing (if PR exists)

If `PR_NUMBER` was set in Check 3 (a PR exists):

```bash
gh pr checks "$PR_NUMBER"
```

- **PASS:** All checks show "pass"
- **FAIL:** List failing checks

If no PR was found in Check 3 (`PR_NUMBER` is empty), skip this check.

### Group B: Code Quality

#### Load Verification Commands

Before running checks 5-8, check for custom commands in `.optimus/config.json`:

```bash
CONFIG_FILE=".optimus/config.json"
if [ -f "$CONFIG_FILE" ]; then
  LINT_CMD=$(cat "$CONFIG_FILE" | jq -r '.commands.lint // empty')
  TEST_CMD=$(cat "$CONFIG_FILE" | jq -r '.commands.test // empty')
  TEST_INT_CMD=$(cat "$CONFIG_FILE" | jq -r '.commands["test-integration"] // empty')
  TEST_E2E_CMD=$(cat "$CONFIG_FILE" | jq -r '.commands["test-e2e"] // empty')
fi
```

- If .optimus/config.json exists, use its commands for checks 5-8 (empty string means skip)
- If .optimus/config.json does not exist or a key is missing, fall back to Makefile targets

#### Check 5: Lint Passes

Run `$LINT_CMD` (from .optimus/config.json) or `make lint` (fallback).

```bash
make lint
```

- **PASS:** Exit code 0
- **FAIL:** Show first 20 lines of error output
- **SKIP:** `make lint` target does not exist (warn user)

`make lint` should run ALL quality checks for the project (linter, vet, format, imports).
The Makefile is responsible for knowing which tools apply to the stack.

### Group C: Tests

#### Check 6: Unit Tests Pass

Run `$TEST_CMD` (from .optimus/config.json) or `make test` (fallback).

```bash
make test
```

- **PASS:** Exit code 0
- **FAIL:** Show first 20 lines of error output

#### Check 7: Integration Tests Pass (if Makefile target exists)

Run `$TEST_INT_CMD` (from .optimus/config.json) or `make test-integration` (fallback).

```bash
make test-integration
```

- **PASS:** Exit code 0
- **FAIL:** Show first 20 lines of error output
- **SKIP:** `make test-integration` target does not exist

#### Check 8: E2E Tests Pass (if Makefile target exists)

Run `$TEST_E2E_CMD` (from .optimus/config.json) or `make test-e2e` (fallback).

```bash
make test-e2e
```

- **PASS:** Exit code 0
- **FAIL:** Show first 20 lines of error output
- **SKIP:** `make test-e2e` target does not exist

---

## Phase 3: Present Results

### If ALL checks pass:

```markdown
## Task Close: T-XXX — [title]

### Checklist
| # | Group | Verification | Result |
|---|-------|-------------|--------|
| 1 | Git | No uncommitted changes | PASS |
| 2 | Git | No unpushed commits | PASS |
| 3 | Git | PR ready to merge (+ title) | PASS (PR #X) / PASS (no PR) |
| 4 | Git | CI passing | PASS / SKIP (no PR) |
| 5 | Quality | Lint (make lint) | PASS / SKIP |
| 6 | Tests | Unit tests | PASS |
| 7 | Tests | Integration tests | PASS / SKIP |
| 8 | Tests | E2E tests | PASS / SKIP |

**Verdict: READY TO CLOSE**

All prerequisites met. Marking task as DONE.
```

Then:
1. Update status to `DONE` in state.json — see AGENTS.md Protocol: State Management.
2. Invoke notification hooks (event=`status-change`) — see AGENTS.md Protocol: Notification Hooks.
3. Invoke notification hooks (event=`task-done`) — see AGENTS.md Protocol: Notification Hooks.
4. Proceed to Phase 4 (cleanup).

### If ANY check fails:

```markdown
## Task Close: T-XXX — [title]

### Checklist
| # | Group | Verification | Result | Details |
|---|-------|-------------|--------|---------|
| 1 | Git | No uncommitted changes | FAIL | 3 files modified |
| 2 | Git | No unpushed commits | PASS | |
| ... | ... | ... | ... | ... |

**Verdict: NOT READY**

### Action Required
- [ ] Commit and push the uncommitted changes
- [ ] ...

Task status remains unchanged. Fix the issues above and run done again.
```

Do NOT change the status.

**Warning when all quality checks are SKIP:** If checks 5-8 (lint, unit tests, integration
tests, E2E tests) ALL resulted in SKIP (no Makefile targets found, no test commands detected),
display a prominent warning:
```
WARNING: No quality verification was possible — no lint or test commands were found.
The close checklist passed based on git state only (commits, push, PR).
Consider running quality checks manually before closing, or configure a Makefile
with `lint`, `test`, `test-integration`, `test-e2e` targets.
```

**Offer to fix actionable failures** via `AskUser`:

```
X checks failed. I can attempt to fix some of these automatically. What should I do?
```

Options:
- **Auto-fix what I can** — the agent will attempt to fix the following actionable failures:
  - Uncommitted changes (Check 1) → `git add -A && git commit -m "chore: commit pending changes for T-XXX"`
  - Unpushed commits (Check 2) → `git push` (or `git push -u origin "$(git branch --show-current)"`)
  - Lint failures (Check 5) → run auto-fix (`make lint-fix` or equivalent), commit, and re-check
  - PR title invalid (Check 3) → `gh pr edit <number> --title "<corrected>"`
- **Just report** — show the list and I'll fix manually

**Non-fixable failures** (CI failures, test failures) are always reported without auto-fix
— they require investigation, not automated patching.

After auto-fix, re-run ONLY the checks that previously failed. If all now pass, proceed
to mark as DONE. If any still fail, report the remaining failures.

---

## Phase 4: Cleanup (after marking DONE)

This phase runs ONLY after the task has been marked as `DONE`. It checks for leftover
resources and asks the user what to do. The agent NEVER cleans up automatically.

### Step 4.1: Check for Task Worktree

**IMPORTANT:** Worktree must be removed BEFORE attempting branch deletion. Git refuses to delete a branch that is checked out in a worktree.

```bash
git worktree list | grep -iF "T-XXX"
```

If a worktree is found, ask via `AskUser`:
```
Task T-XXX is done. A worktree still exists at '<path>'. What should I do?
```
Options:
- **Remove worktree**: `git worktree remove <path>`
- **Keep**: Leave the worktree as is

**Edge case — running INSIDE the worktree:** If the agent's current working directory IS the worktree being removed, `git worktree remove` will fail. Before removing:
1. Identify the main repository path from `git worktree list` (the entry WITHOUT `[branch]` suffix, or the first entry)
2. Change working directory to the main repository: `cd <main-repo-path>`
3. Then run `git worktree remove <worktree-path>`

This also applies to Step 4.3 — if the agent is inside a worktree, `git checkout` changes the worktree's branch, not the main repo's. Always `cd` to the main repo first.

### Step 4.2: Check for Open PR

**IMPORTANT:** PR must be merged BEFORE branch deletion. If the branch is deleted first, all code commits on it are lost.

```bash
TASK_BRANCH=$(jq -r --arg id "$TASK_ID" '.[$id].branch // ""' .optimus/state.json 2>/dev/null)
if [ -z "$TASK_BRANCH" ]; then
  TASK_BRANCH=$(git branch --list "*$(echo "$TASK_ID" | tr '[:upper:]' '[:lower:]')*" 2>/dev/null | head -1 | tr -d ' *')
fi
gh pr list --head "$TASK_BRANCH" --json number,state,title,url --jq '.[] | select(.state == "OPEN")'
```

If an open PR is found, ask via `AskUser`:
```
Task T-XXX is done. PR #N is still open. What should I do?
```
Options:
- **Merge (merge commit)**: `gh pr merge <number> --merge`
- **Merge (squash)**: `gh pr merge <number> --squash`
- **Merge (rebase)**: `gh pr merge <number> --rebase`
- **Keep open**: Leave the PR for manual merge
- **Close without merging**: `gh pr close <number>`

**After any merge option (merge/squash/rebase):** Verify if the branch was auto-deleted
by GitHub (squash and rebase merges often auto-delete the branch):
```bash
git fetch origin --prune
git branch -r --list "origin/$TASK_BRANCH"
```
If the branch was auto-deleted, proceed directly to Step 4.3 to clean up the branch entry
in state.json. Do not ask the user about branch deletion — it already happened.

**"Close without merging":** Since status lives in state.json (local, gitignored), closing
the PR without merging does NOT lose the DONE status. Simply close the PR:
```bash
gh pr close <number>
```

### Step 4.3: Check for Task Branch

Identify the task's branch from state.json (primary) or by searching git branches:

```bash
# Primary: read branch from state.json
TASK_BRANCH=$(jq -r '.["T-XXX"].branch // ""' .optimus/state.json 2>/dev/null)

# Fallback: search by task ID pattern
if [ -z "$TASK_BRANCH" ]; then
  TASK_BRANCH=$(git branch --list "*t-xxx*" 2>/dev/null | head -1 | tr -d ' *')
fi

# Check if branch exists locally
git branch --list "$TASK_BRANCH"

# Check if branch exists on remote
git branch -r --list "origin/$TASK_BRANCH"
```

**HARD BLOCK — Check for open PR before offering deletion:**

Before asking the user about branch deletion, verify no open (unmerged) PR exists for this branch:

```bash
gh pr list --head "$TASK_BRANCH" --json number,state --jq '.[] | select(.state == "OPEN")'
```

**If an open PR still exists:** the branch CANNOT be deleted — deleting it would orphan the PR and lose all commits. Inform the user:
```
Branch '<branch>' cannot be deleted because PR #N is still open.
Merge or close the PR first (Step 4.2), then re-run cleanup.
```
Skip branch deletion and proceed to Step 4.4.

**If no open PR exists** (merged, closed, or never created), ask via `AskUser`:
```
Task T-XXX is done. The branch '<branch>' still exists (local and/or remote). What should I do?
```
Options:
- **Delete local and remote**: switch to default branch first, then delete
- **Delete local only**: switch to default branch first, then delete local
- **Keep**: Leave the branch as is

**IMPORTANT:** You cannot delete a branch you are currently on. Before deleting, switch to the default branch and sync with remote (the merge in Step 4.2 may have changed `tasks.md` on the remote):
```bash
DEFAULT_BRANCH=$(git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's@^refs/remotes/origin/@@')
git checkout "$DEFAULT_BRANCH"
git pull
git branch -d <branch> 2>/dev/null || git branch -D <branch>
# If also deleting remote:
git push origin --delete <branch>
```

**Why `git pull` after checkout:** If the PR was merged (especially squash merge), the remote `main` has changes not yet in local `main`. Pulling ensures local is in sync before any further operations.

**After branch deletion:** Remove the `branch` field from the task's entry in state.json
(or remove the entry entirely if status is DONE).

### Step 4.4: Cleanup Summary

```markdown
## Cleanup Summary for T-XXX

| Resource | Status | Action Taken |
|----------|--------|-------------|
| Worktree `/path/to/wt` | Not found | - |
| PR #42 | Open | Merged / Kept / Closed |
| Branch `<tipo>/t-xxx-...` (local) | Found | Deleted / Kept |
| Branch `<tipo>/t-xxx-...` (remote) | Found | Deleted / Kept |
```

---

## Rules

- Run ALL 8 checks even if the first one fails — the user needs the full picture
- Do NOT change task status unless ALL checks pass (SKIP counts as pass)
- Do NOT skip checks because "they probably pass"
- The agent NEVER decides to close a task without running the full checklist
- After marking as done, update state.json (no commit needed — it's gitignored)
- **Next step suggestion:** After the cleanup summary, inform the user: "Task T-XXX is done.
  Run `/optimus-report` to see updated project status and what to work on next."

### Force-Close Mode
If the user requests a force close (e.g., "force close T-012", "force done T-012"):
- **Skip most of the close checklist** (Phase 2) — skip checks 2-8
- **ALWAYS run Check 1 (uncommitted changes)** even in force-close mode. If uncommitted
  changes exist, warn via `AskUser`:
  ```
  WARNING: There are uncommitted changes on this branch. Force-closing and deleting
  the branch would lose this work.
  ```
  Options:
  - **Commit and continue** — `git add -A && git commit -m "chore: commit pending changes for T-XXX"`, then proceed
  - **Continue without committing** — I accept the risk
  - **Cancel force-close** — let me handle this first
- **Require explicit confirmation** via `AskUser`:
  ```
  WARNING: Force-closing T-XXX will skip checks 2-8:
  - No lint, test, or CI validation
  - No check for unpushed commits
  - No PR state verification
  Note: Check 1 (uncommitted changes) still runs to prevent data loss.

  This is intended for tasks completed outside the pipeline (manual implementation,
  external tools, or when you've already verified everything yourself).

  Type the task ID to confirm: T-XXX
  ```
  The user must type the exact task ID (not just "yes") to prevent accidental force-closes.
- **IMPORTANT — Worktree edge case:** If force-close is executed while inside the task's
  worktree, the agent must `cd` to the main repository before attempting any worktree or
  branch deletion during cleanup (same edge case handling as Steps 4.1 and 4.3).
- **If confirmed:** mark as `DONE` in state.json, then run cleanup (Phase 4) normally
- **NOTE:** Force-close still validates task status (Step 1.1) and dependencies — it only
  skips the quality/git checks in Phase 2

### Dry-Run Mode
If the user requests a dry-run (e.g., "dry-run close T-012", "preview close"):
- Run ALL 8 checks normally (Phase 2)
- Present the full checklist results (Phase 3)
- **Do NOT change task status** — skip marking as DONE
- **Do NOT commit or push anything**
- **Do NOT run cleanup** — skip Phase 4 entirely
- Present the verdict (READY TO CLOSE / NOT READY) as information only
- This allows the user to see what would happen before committing to a close
