# Phase 6: Apply Fixes

Loaded by `SKILL.md` after all findings are resolved with the user. Batch-apply approved fixes via ring droids (or directly for simple changes). Re-run tests after each fix.

**IMPORTANT:** This phase starts ONLY after ALL findings have been presented and ALL decisions collected. No fix is applied during Phase 6.

### Step 7.1: Present Pre-Apply Summary

Before touching any code, show the user a summary of everything that will be changed:

```markdown
### Fixes to Apply (X of Y findings)

| # | Finding | Decision | Files Affected |
|---|---------|----------|---------------|
| F1 | [summary] | Option A: [name] | file1.tsx, file2.ts |
| F3 | [summary] | Option B: [name] | layout.tsx |

### Skipped (Z findings)
| # | Finding | Reason |
|---|---------|--------|
| F2 | [summary] | User: skip |
| F5 | [summary] | User: out of scope |
```

### Step 7.2: Apply All Fixes via Ring Droids
Apply fixes using ring droids with TDD cycle — see AGENTS.md "Common Patterns > Fix Implementation".

**Droid selection for this stage:** Use the stack-appropriate droid (Go→`ring:backend-engineer-golang`, TS→`ring:backend-engineer-typescript`, React→`ring:frontend-engineer`, tests→`ring:qa-analyst`). Documentation fixes use ring-tw-team droids without TDD.

**After each fix:** run unit tests to verify no regressions.

### Step 7.3: Final Verification (Lint)

**After ALL fixes are applied**, run lint one final time — wrapped in
`_optimus_quiet_run` (see AGENTS.md Protocol: Quiet Command Execution):

```bash
_optimus_quiet_run "make-lint" make lint   # Lint — runs ONCE after all fixes
```

If lint fails, fix formatting issues and re-run (the helper already printed
the last 50 lines of the log).

Unit tests run in Step 7.4 via `make test-coverage` (Protocol: Coverage Measurement) — no need to duplicate here.

**Handling test failures (max 3 attempts per fix):**
1. **Logic bug** — return to RED, adjust test/fix
2. **Flaky test** — re-execute at least 3 times in a clean environment to confirm flakiness.
   Maximum 1 test skipped per fix. Document explicit justification (error message,
   flakiness evidence) and tag with `pending-test-fix`
3. **External dependency** — pause and wait for restoration

If tests fail after 3 attempts to fix, revert the offending fix and ask the user.

**NOTE:** Integration tests do NOT run here — they run in Phase 10 (after re-run guard, before summary).

### Step 7.4: Coverage Verification

Measure coverage — see AGENTS.md Protocol: Coverage Measurement.

If coverage is below threshold, add findings to the results.

### Step 7.5: Test Scenario Gap Analysis

After coverage measurement, dispatch an agent to cross-reference the task spec's acceptance criteria with implemented tests and identify missing scenarios.

**Dispatch a test gap analyzer** via `Task` tool. Use `ring:test-reviewer` or `ring:qa-analyst`.

The agent receives file paths and can navigate the codebase autonomously.

```
Goal: Cross-reference task spec with implemented tests to find scenario gaps.

Context:
  - Project root: <absolute path to project worktree>
  - Doc brief (READ FIRST — contains AC list + test IDs in dedicated sections):
    .optimus/sessions/T-XXX/doc-brief.md
  - Full task spec (consult only for verbatim wording): <TASKS_DIR>/<TaskSpec>
  - Changed source files: [list of file paths] (READ each file)
  - Test files: [list of test file paths] (READ each file)
  - Coverage profile: [coverage command output if available]

IMPORTANT: You have access to Read, Grep, and Glob tools. USE THEM to:
  - Read files at the paths above
  - Search for existing test patterns in the project
  - Find related test files not listed above
  - Discover how similar functions are tested elsewhere in the codebase

Your job:
  1. For each acceptance criterion in the task spec, verify:
     - Is there a test that validates this criterion? (map AC → test)
     - Does the test cover both success AND failure paths?
  2. For each public function changed/added by this task, check:
     - Happy path tested?
     - Error paths tested (each error return)?
     - Edge cases (nil, empty, boundary values)?
     - Validation failures?
  3. For integration points (DB, external APIs, message queues):
     - Are failure, timeout, and retry scenarios tested?
     - Are rollback and constraint violation scenarios tested?
  4. Test effectiveness analysis:
     - Do tests verify BEHAVIOR or just mock internals? Flag false confidence tests
     - Could these tests pass while the feature is actually broken?
     - Are tests coupled to implementation details rather than behavior?
     - Do integration tests use real dependencies or just mocks?

Required output format:
  ## Acceptance Criteria Coverage
  | AC | Description | Test Exists | Scenarios Covered | Missing Scenarios |
  |-----|------------|-------------|-------------------|-------------------|

  ## Unit Test Gaps
  | # | File | Function | Existing Scenarios | Missing Scenarios | Priority |
  |---|------|----------|--------------------|-------------------|----------|

  ## Integration Test Gaps
  | # | File | Function | Existing Scenarios | Missing Scenarios | Priority |
  |---|------|----------|--------------------|-------------------|----------|

  ## Test Effectiveness Issues
  | # | File | Test | Issue | Risk | Priority |
  |---|------|------|-------|------|----------|
```

**Gap findings become part of Phase 6** (interactive resolution) — each HIGH gap is presented as a finding for user decision (fix now or defer).

---
