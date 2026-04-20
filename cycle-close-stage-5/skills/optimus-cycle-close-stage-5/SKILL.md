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

### Step 0.0: Verify GitHub CLI (HARD BLOCK)

```bash
gh auth status 2>/dev/null
```

If this command fails (exit code != 0), **STOP** immediately:
```
GitHub CLI (gh) is not authenticated. Run `gh auth login` to authenticate before proceeding.
```

### Step 0.0.1: Find and Validate tasks.md

1. **Find tasks.md:** Look in `./tasks.md` (project root). If not found, look in `./docs/tasks.md`. If not found in either, **STOP** and suggest `/optimus-cycle-migrate`.
2. **Validate format (HARD BLOCK):**
   - **First line** must be `<!-- optimus:tasks-v1 -->` (format marker). If missing → **STOP**.
   - A `## Versions` section exists with columns: Version, Status, Description
   - Exactly one version has Status `Ativa`
   - At most one version has Status `Próxima`
   - A markdown table exists with columns: ID, Title, Tipo, Status, Depends, Priority, Version, Branch
   - All Priority values are valid (`Alta`, `Media`, `Baixa`)
   - All Version values reference a version name in the Versions table
   - All task IDs match `T-NNN` pattern
   - All Tipo values are valid (`Feature`, `Fix`, `Refactor`, `Chore`, `Docs`, `Test`)
   - All Status values are valid (`Pendente`, `Validando Spec`, `Em Andamento`, `Validando Impl`, `Revisando PR`, `**DONE**`, `Cancelado`)
   - All Depends values are `-` or comma-separated valid task IDs
   - No duplicate task IDs
   - All Version Status values are valid (`Ativa`, `Próxima`, `Planejada`, `Backlog`, `Concluída`)
   - No circular dependencies in the dependency graph
   - No unescaped pipe characters (`|`) in task titles

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

4. **Branch-task cross-validation:** After confirming the task ID (Step 0.0.2), check that the current branch matches the **Branch** column in `tasks.md` for this task:
   - Read the Branch column for the confirmed task ID
   - If Branch is `-` or empty → warn: "tasks.md shows no branch for T-XXX, but you are on `<current>`. Continue anyway?" (via `AskUser`)
   - If Branch has a value AND it does not match `CURRENT_BRANCH` → warn: "tasks.md shows branch `<expected>` for T-XXX, but you are on `<current>`. Continue on current branch, or switch?" (via `AskUser`)
   - If Branch matches `CURRENT_BRANCH` → proceed silently

### Step 0.0.2: Identify Task to Close

**If the user specified a task ID** (e.g., "close T-012"):
- Use the provided task ID
- Confirm with the user using `AskUser`: "I'll close task T-012: [task title]. Correct?"

**If the user did NOT specify a task ID:**
1. Look for tasks with status `Validando Impl` or `Revisando PR`
2. If exactly one found, suggest it
3. If multiple found, ask the user which one to close
4. If none found, inform the user there are no tasks ready to close

**BLOCKING**: Do NOT proceed until the user confirms which task to close.

### Step 0.0.2.1: Check Session State

After identifying the task, check for a previous session:

```bash
SESSION_FILE=".optimus/session-${TASK_ID}.json"
if [ -f "$SESSION_FILE" ]; then
  cat "$SESSION_FILE"
fi
```

- If the file exists AND the task's status in `tasks.md` matches the session's `status`:
  - Present via `AskUser`:
    ```
    Previous session found:
      Task: T-XXX — [title]
      Stage: cycle-close-stage-5
      Last active: <time since updated_at>
      Progress: <phase from session>
    Resume this session?
    ```
    Options: Resume / Start fresh / Ignore
  - If **Resume**: skip to the phase indicated in the session file
  - If **Start fresh**: delete the session file and proceed normally
  - If **Ignore**: proceed normally
- If the file is stale (>24h) or the task status has changed → delete and proceed normally
- If no file exists → proceed normally

**On stage progress:** Update the session file at key phase transitions:
```bash
mkdir -p .optimus
grep -q '.optimus/' .gitignore 2>/dev/null || echo '.optimus/' >> .gitignore
cat > ".optimus/session-${TASK_ID}.json" << EOF
{"task_id":"${TASK_ID}","stage":"cycle-close-stage-5","status":"**DONE**","branch":"$(git branch --show-current)","started_at":"$(date -u +%Y-%m-%dT%H:%M:%SZ)","updated_at":"$(date -u +%Y-%m-%dT%H:%M:%SZ)","phase":"<current-phase>","notes":"<progress>"}
EOF
```

**On marking DONE** (Phase 2, after marking task as `**DONE**`): Delete the session file:
```bash
rm -f ".optimus/session-${TASK_ID}.json"
```

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
   - If status is `Cancelado` → **STOP**: "Task T-XXX was cancelled. Cannot close a cancelled task."
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

### Step 0.2: Check tasks.md Divergence (warning)

Compare `tasks.md` on the current branch with the default branch to detect concurrent edits that could cause merge conflicts when the PR is merged:

```bash
DEFAULT_BRANCH=$(git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's@^refs/remotes/origin/@@')
git fetch origin "$DEFAULT_BRANCH" --quiet 2>/dev/null
git diff "origin/$DEFAULT_BRANCH" -- tasks.md 2>/dev/null | head -20
```

- If diff output is non-empty → the file has diverged. Warn via `AskUser`:
  ```
  tasks.md has diverged between your branch and <default_branch>.
  This may cause merge conflicts when the PR is merged.
  ```
  Options:
  - **Sync now** — run `git merge origin/<default_branch>` to incorporate changes
  - **Continue without syncing** — I'll handle conflicts later
- If diff output is empty → proceed silently (files are in sync)
- **NOTE:** This is a warning, not a HARD BLOCK. The user may choose to continue.

### Step 0.3: Push Unpushed Commits (if any)

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
  1. **Validate PR title (Conventional Commits):** The PR title MUST follow the **Conventional Commits 1.0.0** specification (https://www.conventionalcommits.org/en/v1.0.0/).
     - Expected format: `<type>[optional scope]: <description>`
     - Regex: `^(feat|fix|refactor|chore|docs|test|build|ci|style|perf)(\([a-zA-Z0-9_\-]+\))?!?: .+$`
     - Cross-check the type against the task's **Tipo** column (Feature→`feat`, Fix→`fix`, etc.)
     - **If title is invalid:** FAIL — "PR #$PR_NUMBER title does not follow Conventional Commits: `$PR_TITLE`. Expected: `<corrected title>`. Fix with: `gh pr edit $PR_NUMBER --title \"<corrected title>\"`"
  2. **If title is valid:** PASS — "PR #$PR_NUMBER title is valid. CI status checked in Check 4."

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

- If config.json exists, use its commands for checks 5-8 (empty string means skip)
- If config.json does not exist or a key is missing, fall back to Makefile targets

#### Check 5: Lint Passes

Run `$LINT_CMD` (from config.json) or `make lint` (fallback).

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

Run `$TEST_CMD` (from config.json) or `make test` (fallback).

```bash
make test
```

- **PASS:** Exit code 0
- **FAIL:** Show first 20 lines of error output

#### Check 7: Integration Tests Pass (if Makefile target exists)

Run `$TEST_INT_CMD` (from config.json) or `make test-integration` (fallback).

```bash
make test-integration
```

- **PASS:** Exit code 0
- **FAIL:** Show first 20 lines of error output
- **SKIP:** `make test-integration` target does not exist

#### Check 8: E2E Tests Pass (if Makefile target exists)

Run `$TEST_E2E_CMD` (from config.json) or `make test-e2e` (fallback).

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
3. **Invoke notification hooks (if present):**
   ```bash
   HOOKS_FILE=$(test -f ./tasks-hooks.sh && echo ./tasks-hooks.sh || (test -f ./docs/tasks-hooks.sh && echo ./docs/tasks-hooks.sh))
   if [ -n "$HOOKS_FILE" ] && [ -x "$HOOKS_FILE" ]; then
     "$HOOKS_FILE" task-done T-XXX "<previous status>" "**DONE**" 2>/dev/null &
   fi
   ```
4. Push the commit
5. Proceed to Phase 3 (cleanup).

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
  - Unpushed commits (Check 2) → `git push` (or `git push -u origin $(git branch --show-current)`)
  - Lint failures (Check 5) → run auto-fix (`make lint-fix` or equivalent), commit, and re-check
  - PR title invalid (Check 3) → `gh pr edit <number> --title "<corrected>"`
- **Just report** — show the list and I'll fix manually

**Non-fixable failures** (CI failures, test failures) are always reported without auto-fix
— they require investigation, not automated patching.

After auto-fix, re-run ONLY the checks that previously failed. If all now pass, proceed
to mark as DONE. If any still fail, report the remaining failures.

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

**CRITICAL — Safety check for "Close without merging":** If the user chooses to close
the PR without merging, the DONE status change (committed on the feature branch) will
NOT be present on the default branch. Before closing, the agent MUST:
1. Switch to the default branch: `git checkout <default_branch> && git pull`
2. Cherry-pick ONLY the tasks.md DONE status commit from the feature branch:
   ```bash
   git cherry-pick <done-commit-sha> --no-commit
   git checkout -- . ':!tasks.md'   # keep only tasks.md changes
   git add tasks.md
   git commit -m "chore(tasks): mark T-XXX as done"
   git push
   ```
3. **If the cherry-pick fails** (conflict because tasks.md diverged significantly):
   - Do NOT abort silently. Inform the user:
     ```
     Cherry-pick of DONE status failed due to merge conflict in tasks.md.
     tasks.md has diverged too much between this branch and <default_branch>.
     ```
   - Offer resolution via `AskUser`:
     - **Resolve manually** — open tasks.md, show the conflict markers, let user fix
     - **Apply status directly** — instead of cherry-pick, read the current tasks.md on
       the default branch, find the row for T-XXX, update its Status to `**DONE**`, commit
       and push. This bypasses the cherry-pick entirely.
     - **Skip** — close the PR without preserving status. User will update tasks.md manually.
   - **BLOCKING:** Do NOT proceed until the conflict is resolved or the user chooses to skip.
4. Then close the PR: `gh pr close <number>`
5. Switch back to continue with branch cleanup

This ensures the DONE status is preserved on the default branch even when the PR is
not merged. Without this, deleting the branch would lose the status change entirely.

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
- Do NOT skip checks because "they probably pass"
- The agent NEVER decides to close a task without running the full checklist
- After marking as done, always commit and push the status change
- **Next step suggestion:** After the cleanup summary, inform the user: "Task T-XXX is done.
  Run `/optimus-cycle-report` to see updated project status and what to work on next."

### Force-Close Mode
If the user requests a force close (e.g., "force close T-012", "force done T-012"):
- **Skip most of the close checklist** (Phase 1) — skip checks 2-8
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
  WARNING: Force-closing T-XXX will skip ALL verification checks:
  - No lint, test, or CI validation
  - No check for uncommitted/unpushed changes
  - No PR state verification

  This is intended for tasks completed outside the pipeline (manual implementation,
  external tools, or when you've already verified everything yourself).

  Type the task ID to confirm: T-XXX
  ```
  The user must type the exact task ID (not just "yes") to prevent accidental force-closes.
- **If confirmed:** mark as `**DONE**`, commit, push, then run cleanup (Phase 3) normally
- **Commit message:** `chore(tasks): force-close T-XXX as done (checklist skipped)`
- **NOTE:** Force-close still validates task status (Step 0.1) and dependencies — it only
  skips the quality/git checks in Phase 1

### Dry-Run Mode
If the user requests a dry-run (e.g., "dry-run close T-012", "preview close"):
- Run ALL 8 checks normally (Phase 1)
- Present the full checklist results (Phase 2)
- **Do NOT change task status** — skip marking as DONE
- **Do NOT commit or push anything**
- **Do NOT run cleanup** — skip Phase 3 entirely
- Present the verdict (READY TO CLOSE / NOT READY) as information only
- This allows the user to see what would happen before committing to a close
