# Phase 2 (Close Gates): Four Sequential Hard Blocks

Loaded by `SKILL.md` after Phase 1 completes. Each gate is a **HARD BLOCK** — if
it fails, STOP immediately. Run gates sequentially.

## Gate 1: No Uncommitted Changes

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

## Gate 2: No Unpushed Commits

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

## Gate 3: PR Review Feedback

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
  - **Run `/optimus-pr-check` now** (Recommended) — invoke the pr-check skill to
    fetch all comments and address them iteratively. After pr-check completes,
    re-run `/optimus-done` to re-evaluate this gate.
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

If the user picks "Run `/optimus-pr-check` now", invoke the `optimus-pr-check`
skill via the `Skill` tool. After it completes, re-fetch `PR_JSON` and re-evaluate
Gate 3. Loop up to 3 times to avoid infinite back-and-forth; if still
`CHANGES_REQUESTED` after 3 iterations, fall through to the override/cancel
prompt.

## Gate 4: PR in Final State

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
