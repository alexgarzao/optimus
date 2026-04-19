---
name: optimus-stage-4-close
description: >
  Stage 4 of the task lifecycle. Verifies all prerequisites before marking
  a task as done: no uncommitted changes, no unpushed commits, PR merged
  (if applicable), CI passing, tests and lint passing locally.
trigger: >
  - After optimus-stage-3-review has completed for a task
  - When user requests closing a task (e.g., "close T-012", "mark T-012 as done")
skip_when: >
  - Task has not been through stage-3-review yet
  - Task is already done
prerequisite: >
  - Task exists in tasks.md with status "Validando Impl"
  - stage-3-review has completed
NOT_skip_when: >
  - "Everything is already merged" → Verify it. Do not assume.
  - "Tests passed in CI" → Also run locally to confirm.
  - "It's a small task" → All tasks need the same close verification.
examples:
  - name: Close a completed task
    invocation: "Close task T-012"
    expected_flow: >
      1. Confirm task ID with user
      2. Validate status is "Validando Impl"
      3. Run close checklist (11 verifications: git state, code quality, tests + coverage)
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
    - optimus-stage-3-review
  sequence:
    after:
      - optimus-stage-3-review
verification:
  manual:
    - All checklist items passed
    - Task status updated to DONE in tasks.md
    - Status change committed
---

# Task Closer

Stage 4 of the task lifecycle. Verifies all prerequisites before marking a task as done.

---

## Phase 0: Identify and Validate Task

### Step 0.0: Identify Task to Close

**If the user specified a task ID** (e.g., "close T-012"):
- Use the provided task ID
- Confirm with the user using `AskUser`: "I'll close task T-012: [task title]. Correct?"

**If the user did NOT specify a task ID:**
1. Find `tasks.md` and look for tasks with status `Validando Impl`
2. If exactly one found, suggest it
3. If multiple found, ask the user which one to close
4. If none found, inform the user there are no tasks ready to close

**BLOCKING**: Do NOT proceed until the user confirms which task to close.

### Step 0.1: Validate Task Status

**HARD BLOCK:** This step is mandatory. Do NOT skip it.

1. Read `tasks.md` and find the row for the confirmed task ID
2. Check the **Status** column:
   - If status is `Validando Impl` → proceed (stage-3-review has completed)
   - If status is `Pendente` → **STOP**: "Task T-XXX is in 'Pendente'. It must go through stage-1-spec, stage-2-impl, and stage-3-review first."
   - If status is `Validando Spec` → **STOP**: "Task T-XXX is in 'Validando Spec'. Run stage-2-impl and stage-3-review first."
   - If status is `Em Andamento` → **STOP**: "Task T-XXX is in 'Em Andamento'. Run stage-3-review first."
   - If status is `**DONE**` → **STOP**: "Task T-XXX is already done."

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

```bash
git log @{u}..HEAD --oneline
```

- **PASS:** Output is empty (local is in sync with remote)
- **FAIL:** List the unpushed commits

#### Check 3: PR Merged (if applicable)

Check if a PR exists for the current branch or task branch:

```bash
gh pr list --head "$(git branch --show-current)" --json number,state,title --jq '.[]'
```

- **If no PR exists:** PASS (task went directly to default branch)
- **If PR exists and state is MERGED:** PASS
- **If PR exists and state is OPEN:** FAIL — "PR #X is still open. Merge it first."
- **If PR exists and state is CLOSED (not merged):** FAIL — "PR #X was closed without merging."

#### Check 4: CI Passing (if PR exists)

If a PR was found in Check 3:

```bash
gh pr checks <PR_NUMBER>
```

- **PASS:** All checks show "pass"
- **FAIL:** List failing checks

If no PR exists, skip this check.

### Group B: Code Quality (pass/fail only)

#### Check 5: Lint Passes

```bash
# Discover from project: make lint, golangci-lint run, npm run lint
make lint
```

- **PASS:** Exit code 0
- **FAIL:** Show first 20 lines of error output

#### Check 6: Vet Passes (Go projects)

```bash
go vet ./...
```

- **PASS:** Exit code 0
- **FAIL:** Show error output
- **SKIP:** Not a Go project

#### Check 7: Format Clean

```bash
# Go: gofmt -l . (fail if output is non-empty)
# JS/TS: npx prettier --check . (fail if exit code != 0)
gofmt -l .
```

- **PASS:** No files listed (all formatted)
- **FAIL:** List files that need formatting

#### Check 8: Import Ordering (Go projects)

```bash
goimports -l .
```

- **PASS:** No files listed
- **FAIL:** List files with import issues
- **SKIP:** goimports not installed or not a Go project

### Group C: Tests & Coverage

#### Check 9: Unit Tests Pass

```bash
# Discover: make test, go test ./..., npm test
go test -coverprofile=coverage.out ./...
```

- **PASS:** Exit code 0
- **FAIL:** Show first 20 lines of error output

#### Check 10: Integration Tests Pass (if available)

```bash
# Discover: make test-integration, go test -tags=integration
go test -tags=integration ./...
```

- **PASS:** Exit code 0
- **FAIL:** Show first 20 lines of error output
- **SKIP:** No integration test target/tag exists

#### Check 11: Coverage Above Threshold

From the coverage profile generated in Check 9:

```bash
go tool cover -func=coverage.out | tail -1
```

- **PASS:** Total coverage >= 85% (unit) and >= 70% (integration if available)
- **FAIL:** Show current percentage and threshold

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
| 3 | Git | PR merged | PASS (PR #X) / PASS (no PR) |
| 4 | Git | CI passing | PASS / SKIP (no PR) |
| 5 | Quality | Lint | PASS |
| 6 | Quality | Vet | PASS / SKIP |
| 7 | Quality | Format | PASS |
| 8 | Quality | Import ordering | PASS / SKIP |
| 9 | Tests | Unit tests | PASS |
| 10 | Tests | Integration tests | PASS / SKIP |
| 11 | Tests | Coverage >= threshold | PASS (87.2%) |

**Verdict: READY TO CLOSE**

All prerequisites met. Marking task as **DONE**.
```

Then:
1. Update the Status column in `tasks.md` from `Validando Impl` to `**DONE**`
2. Commit: `chore: mark T-XXX as done`
3. Push the commit

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

Task status remains **Validando Impl**. Fix the issues above and run stage-4-close again.
```

Do NOT change the status. Do NOT offer to fix the issues — just report them.

---

## Rules

- Run ALL 11 checks even if the first one fails — the user needs the full picture
- Do NOT change task status unless ALL checks pass (SKIP counts as pass)
- Do NOT fix issues found by the checklist — only report them
- Do NOT skip checks because "they probably pass"
- The agent NEVER decides to close a task without running the full checklist
- After marking as done, always commit and push the status change
