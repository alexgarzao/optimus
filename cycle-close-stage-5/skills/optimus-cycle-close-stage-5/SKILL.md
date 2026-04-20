---
name: optimus-cycle-close-stage-5
description: >
  Stage 5 of the task lifecycle. Verifies all prerequisites before marking
  a task as done: no uncommitted changes, no unpushed commits, PR ready to merge
  (if applicable), CI passing, tests and lint passing locally.
  During cleanup, offers to merge the PR (user chooses merge strategy via AskUser).
trigger: >
  - After optimus-cycle-pr-review-stage-4 has completed for a task (optional), or after optimus-cycle-impl-review-stage-3
  - When user requests closing a task (e.g., "close T-012", "mark T-012 as done")
skip_when: >
  - Task has not been through at least cycle-impl-review-stage-3 yet
  - Task is already done
prerequisite: >
  - Task exists in tasks.md with status "Validando Impl" or "Revisando PR"
  - At least cycle-impl-review-stage-3 has completed (cycle-pr-review-stage-4 is optional)
NOT_skip_when: >
  - "Everything is already ready" → Verify it. Do not assume.
  - "Tests passed in CI" → Also run locally to confirm.
  - "It's a small task" → All tasks need the same close verification.
examples:
  - name: Close a completed task
    invocation: "Close task T-012"
    expected_flow: >
      1. Confirm task ID with user
      2. Validate status is "Validando Impl" or "Revisando PR"
      3. Run close checklist (8 verifications: git state, lint, tests)
      4. If all pass, mark as DONE
      5. Commit status change
  - name: Close with failures
    invocation: "Close task T-012"
    expected_flow: >
      1. Confirm task ID
      2. Validate status
      3. Run checklist — uncommitted changes found
      4. Report what's missing, do NOT change status
related:
  complementary:
    - optimus-cycle-pr-review-stage-4
    - optimus-cycle-impl-review-stage-3
  sequence:
    after:
      - optimus-cycle-impl-review-stage-3
      - optimus-cycle-pr-review-stage-4
verification:
  manual:
    - All checklist items passed
    - Task status updated to DONE in tasks.md
    - Status change committed
---

# Task Closer

Stage 5 of the task lifecycle. Verifies all prerequisites before marking a task as done.

---

## Phase 0: Identify and Validate Task

### Step 0.0: Find and Validate tasks.md

1. **Find tasks.md:** Look in `./tasks.md` (project root). If not found, look in `./docs/tasks.md`. If not found in either, **STOP** and suggest `/optimus-cycle-migrate`.
2. **Validate format (HARD BLOCK):**
   - **First line** must be `<!-- optimus:tasks-v1 -->` (format marker). If missing → **STOP**.
   - A `## Versions` section exists with columns: Version, Status, Description
   - Exactly one version has Status `Ativa`
   - At most one version has Status `Próxima`
   - A markdown table exists with columns: ID, Title, Tipo, Status, Depends, Priority, Version, Branch
   - All Version values reference a version name in the Versions table
   - All task IDs match `T-NNN` pattern
   - All Tipo values are valid (`Feature`, `Fix`, `Refactor`, `Chore`, `Docs`, `Test`)
   - All Status values are valid (`Pendente`, `Validando Spec`, `Em Andamento`, `Validando Impl`, `Revisando PR`, `**DONE**`)
   - All Depends values are `-` or comma-separated valid task IDs
   - No duplicate task IDs

If validation fails, **STOP** and suggest: "tasks.md is not in valid optimus format. Run `/optimus-cycle-migrate` to fix it."

3. **Verify workspace (HARD BLOCK):** This agent runs verification checks. It MUST run on the task's feature branch, not the default/main branch.
   ```bash
   DEFAULT_BRANCH=$(git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's@^refs/remotes/origin/@@')
   CURRENT_BRANCH=$(git branch --show-current)
   ```
   - If `CURRENT_BRANCH` equals `DEFAULT_BRANCH` (or is `main`/`master`) → **STOP**:
     ```
     Cannot run cycle-close-stage-5 on the default branch (<branch>).
     Switch to the task's feature branch first.
     ```

4. **Branch-task cross-validation:** After confirming the task ID (Step 0.0.1), check that the current branch matches the **Branch** column in `tasks.md` for this task:
   - Read the Branch column for the confirmed task ID
   - If Branch is `-` or empty → warn: "tasks.md shows no branch for T-XXX, but you are on `<current>`. Continue anyway?" (via `AskUser`)
   - If Branch has a value AND it does not match `CURRENT_BRANCH` → warn: "tasks.md shows branch `<expected>` for T-XXX, but you are on `<current>`. Continue on current branch, or switch?" (via `AskUser`)
   - If Branch matches `CURRENT_BRANCH` → proceed silently

### Step 0.0.1: Identify Task to Close

**If the user specified a task ID** (e.g., "close T-012"):
- Use the provided task ID
- Confirm with the user using `AskUser`: "I'll close task T-012: [task title]. Correct?"

**If the user did NOT specify a task ID:**
1. Look for tasks with status `Validando Impl` or `Revisando PR`
2. If exactly one found, suggest it
3. If multiple found, ask the user which one to close
4. If none found, inform the user there are no tasks ready to close

**BLOCKING**: Do NOT proceed until the user confirms which task to close.

### Step 0.1: Validate Task Status

**HARD BLOCK:** This step is mandatory. Do NOT skip it.

1. Read `tasks.md` and find the row for the confirmed task ID
2. Check the **Status** column:
   - If status is `Validando Impl` → proceed (cycle-impl-review-stage-3 has completed, cycle-pr-review-stage-4 was skipped)
   - If status is `Revisando PR` → proceed (cycle-pr-review-stage-4 has completed)
   - If status is `Pendente` → **STOP**: "Task T-XXX is in 'Pendente'. It must go through cycle-spec-stage-1, cycle-impl-stage-2, and cycle-impl-review-stage-3 first."
   - If status is `Validando Spec` → **STOP**: "Task T-XXX is in 'Validando Spec'. Run cycle-impl-stage-2 and cycle-impl-review-stage-3 first."
   - If status is `Em Andamento` → **STOP**: "Task T-XXX is in 'Em Andamento'. Run cycle-impl-review-stage-3 first."
   - If status is `**DONE**` → **STOP**: "Task T-XXX is already done. Re-execution of cycle-close-stage-5 is not supported."
3. **Check dependencies (HARD BLOCK):** Read the Depends column for this task.
   - If Depends is `-` → proceed (no dependencies)
   - For each dependency ID listed, check its Status in the table:
     - If ALL dependencies have status `**DONE**` → proceed
     - If ANY dependency is NOT `**DONE**` → **STOP**:
       ```
       Task T-XXX depends on T-YYY (status: '<status>'). T-YYY must be **DONE** first.
       ```
4. **Expanded confirmation before status change:**
   - **If the user did NOT specify the task ID explicitly** (auto-detect):
     - Read the task's H2 detail section (`## T-XXX: Title`) from `tasks.md`
     - Present to the user via `AskUser`:
       ```
       I'm about to close task T-XXX and mark it as **DONE** (from '<current>').

       **T-XXX: [title]**
       **Version:** [version from table]
       **Objetivo:** [objective from detail section]
       **Critérios de Aceite:**
       - [ ] [criterion 1]
       - [ ] [criterion 2]
       ...

       Confirm close?
       ```
     - **BLOCKING:** Do NOT proceed to the close checklist until the user confirms
   - **If the user specified the task ID explicitly** (e.g., "close T-012"):
     - Skip expanded confirmation (user already has context)

   **NOTE:** cycle-close-stage-5 does not support re-execution (status always changes to `**DONE**`), so the re-execution skip does not apply here.

### Step 0.2: Push Unpushed Commits (if any)

Previous stages (1-4) commit tasks.md status changes immediately but do not push. Before running the close checklist, ensure the feature branch is in sync with remote.

**Step 1 — Check if upstream tracking exists:**

```bash
git rev-parse --abbrev-ref @{u} 2>/dev/null
```

- **If command fails (no upstream):** The branch was never pushed. Push with `-u` to create the upstream:
  ```bash
  git push -u origin $(git branch --show-current)
  ```
- **If command succeeds (upstream exists):** Check for unpushed commits:
  ```bash
  git log @{u}..HEAD --oneline
  ```
  If there are unpushed commits, push them: `git push`

**Why check upstream first:** `git log @{u}..HEAD` silently produces empty output when no upstream exists, making it appear there's nothing to push. But in reality ALL local commits are unpushed because the remote branch doesn't exist yet. Without this check, the close checklist would pass while the feature branch was never pushed — and branch deletion in cleanup would lose all work.

**Why push now:** The close checklist (Check 2) verifies "no unpushed commits". Stages 2-4 commit status changes eagerly to prevent data loss on session interruption, but they don't push. Without this step, Check 2 would always fail with false positives from those legitimate status commits.

---

## Phase 1: Close Checklist

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
- **FAIL (no upstream):** "Branch has no upstream tracking. Run `git push -u origin $(git branch --show-current)` first."
- **FAIL (unpushed commits):** List the unpushed commits

#### Check 3: PR Ready to Merge (if applicable)

Check if a PR exists for the current branch or task branch:

```bash
gh pr list --head "$(git branch --show-current)" --json number,state,title,reviewDecision --jq '.[]'
```

- **If no PR exists:** PASS (task went directly to default branch)
- **If PR exists and state is MERGED:** PASS
- **If PR exists and state is CLOSED (not merged):** FAIL — "PR #X was closed without merging."
- **If PR exists and state is OPEN:**
  1. **Validate PR title (Conventional Commits):** The PR title MUST follow the **Conventional Commits 1.0.0** specification (https://www.conventionalcommits.org/en/v1.0.0/).
     - Expected format: `<type>[optional scope]: <description>`
     - Regex: `^(feat|fix|refactor|chore|docs|test|build|ci|style|perf)(\([a-zA-Z0-9_\-]+\))?!?: .+$`
     - Cross-check the type against the task's **Tipo** column (Feature→`feat`, Fix→`fix`, etc.)
     - **If title is invalid:** FAIL — "PR #X title does not follow Conventional Commits: `<current title>`. Expected: `<corrected title>`. Fix with: `gh pr edit <number> --title \"<corrected title>\"`"
  2. **If title is valid:** PASS — "PR #X title is valid. CI status checked in Check 4."

**NOTE:** This check validates PR state and title only. CI status is checked separately in Check 4.

#### Check 4: CI Passing (if PR exists)

If a PR was found in Check 3:

```bash
gh pr checks <PR_NUMBER>
```

- **PASS:** All checks show "pass"
- **FAIL:** List failing checks

If no PR exists, skip this check.

### Group B: Code Quality

#### Check 5: Lint Passes

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

```bash
make test
```

- **PASS:** Exit code 0
- **FAIL:** Show first 20 lines of error output

#### Check 7: Integration Tests Pass (if Makefile target exists)

```bash
make test-integration
```

- **PASS:** Exit code 0
- **FAIL:** Show first 20 lines of error output
- **SKIP:** `make test-integration` target does not exist

#### Check 8: E2E Tests Pass (if Makefile target exists)

```bash
make test-e2e
```

- **PASS:** Exit code 0
- **FAIL:** Show first 20 lines of error output
- **SKIP:** `make test-e2e` target does not exist

---

## Phase 2: Present Results

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

All prerequisites met. Marking task as **DONE**.
```

Then:
1. Update the Status column in `tasks.md` to `**DONE**` (from either `Validando Impl` or `Revisando PR`)
2. Commit: `chore(tasks): mark T-XXX as done`
3. Push the commit
4. Proceed to Phase 3 (cleanup).

**Why `chore(tasks):` and not the Tipo prefix:** Marking a task as DONE is an administrative
status change in `tasks.md`, not a code change. The Tipo prefix (`feat`, `fix`, etc.) applies
to PR titles and code commits, not to task management operations. All status change commits
across stages 1-5 use `chore(tasks):` for consistency.

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

Task status remains unchanged. Fix the issues above and run cycle-close-stage-5 again.
```

Do NOT change the status. Do NOT offer to fix the issues — just report them.

---

## Phase 3: Cleanup (after marking DONE)

This phase runs ONLY after the task has been marked as `**DONE**`. It checks for leftover
resources and asks the user what to do. The agent NEVER cleans up automatically.

### Step 3.1: Check for Task Worktree

**IMPORTANT:** Worktree must be removed BEFORE attempting branch deletion. Git refuses to delete a branch that is checked out in a worktree.

```bash
git worktree list | grep -i "T-XXX"
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

This also applies to Step 3.3 — if the agent is inside a worktree, `git checkout` changes the worktree's branch, not the main repo's. Always `cd` to the main repo first.

### Step 3.2: Check for Open PR

**IMPORTANT:** PR must be merged BEFORE branch deletion. If the branch is deleted first, all commits on it (including the DONE status change) are lost.

```bash
TASK_BRANCH=$(grep "T-XXX" tasks.md | ... extract Branch column ...)
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

### Step 3.3: Check for Task Branch

Identify the task's branch from the **Branch column** in `tasks.md` (primary source). If the column is `-` or empty, fall back to convention:

```bash
# Primary: read Branch column from tasks.md for this task ID
TASK_BRANCH=$(grep "T-XXX" tasks.md | ... extract Branch column ...)

# Fallback: search by convention (any Tipo prefix)
git branch --list "feat/*T-XXX*" "feat/*t-xxx*" "fix/*T-XXX*" "fix/*t-xxx*" "refactor/*T-XXX*" "refactor/*t-xxx*" "chore/*T-XXX*" "chore/*t-xxx*" "docs/*T-XXX*" "docs/*t-xxx*" "test/*T-XXX*" "test/*t-xxx*"

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
Merge or close the PR first (Step 3.2), then re-run cleanup.
```
Skip branch deletion and proceed to Step 3.4.

**If no open PR exists** (merged, closed, or never created), ask via `AskUser`:
```
Task T-XXX is done. The branch '<branch>' still exists (local and/or remote). What should I do?
```
Options:
- **Delete local and remote**: switch to default branch first, then delete
- **Delete local only**: switch to default branch first, then delete local
- **Keep**: Leave the branch as is

**IMPORTANT:** You cannot delete a branch you are currently on. Before deleting, switch to the default branch and sync with remote (the merge in Step 3.2 may have changed `tasks.md` on the remote):
```bash
DEFAULT_BRANCH=$(git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's@^refs/remotes/origin/@@')
git checkout "$DEFAULT_BRANCH"
git pull
git branch -d <branch>
# If also deleting remote:
git push origin --delete <branch>
```

**Why `git pull` after checkout:** If the PR was merged (especially squash merge), the remote `main` has a different version of `tasks.md` than the local `main`. Without pulling, the Branch column cleanup would operate on a stale version and could conflict or lose the DONE status change.

**After branch deletion:** Update the Branch column in `tasks.md` to `-` (the branch no longer exists, keeping the old name would be misleading). Commit and push (this is an administrative commit directly on the default branch — acceptable because the feature branch no longer exists):
```bash
git add tasks.md
git commit -m "chore(tasks): clear branch for T-XXX after cleanup"
git push
```

### Step 3.4: Cleanup Summary

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
- Do NOT fix issues found by the checklist — only report them
- Do NOT skip checks because "they probably pass"
- The agent NEVER decides to close a task without running the full checklist
- After marking as done, always commit and push the status change
- **Next step suggestion:** After the cleanup summary, inform the user: "Task T-XXX is done.
  Run `/optimus-cycle-report` to see updated project status and what to work on next."
