---
name: optimus-post-task-validator
description: >
  Validates that a completed task was executed correctly: spec compliance,
  coding standards adherence, engineering best practices, test coverage,
  and production readiness. Uses parallel specialist agents for deep analysis,
  then presents findings interactively. Runs AFTER optimus-task-executor finishes
  and BEFORE the final commit.
trigger: >
  - After optimus-task-executor completes all phases and verification gates pass
  - When user requests validation of a completed task (e.g., "validate T-012")
  - Before the final commit of a task execution
skip_when: >
  - Task is pure research or documentation (no code to validate)
  - Already inside a code review skill execution
  - Changes have already been committed (validation must happen before commit)
prerequisite: >
  - Task execution is complete (user provides ID or skill auto-detects last executed task)
  - Changed files are uncommitted (validation happens before commit)
  - Reference docs exist (task spec, coding standards)
  - Project has lint and test commands configured
NOT_skip_when: >
  - "Task was simple" → Simple tasks still need spec compliance checks.
  - "Tests already pass" → Passing tests do not guarantee spec compliance or code quality.
  - "optimus-task-executor already ran verification gates" → Gates check pass/fail; this validates correctness.
  - "Time pressure" → Validation prevents rework, saving time overall.
examples:
  - name: Validate a full-stack task
    invocation: "Validate task T-012"
    expected_flow: >
      1. User specified task ID — confirm with user
      2. Load task spec and reference docs
      3. Identify changed files
      4. Dispatch 8 parallel agents (code, business logic, security, QA, frontend, backend, cross-file, spec compliance)
      5. Consolidate and deduplicate findings
      6. Present overview table
      7. Interactive finding-by-finding resolution
      8. Batch apply approved fixes
      9. Run verification gate
      10. Present validation summary
  - name: Validate last executed task (auto-detect)
    invocation: "Validate the last task"
    expected_flow: >
      1. Check optimus-task-executor-state.json or git diff for context
      2. Identify the task that was just executed
      3. Suggest to user and confirm via AskUser
      4. Standard validation flow
  - name: Validate a frontend-only task
    invocation: "Validate task T-015"
    expected_flow: >
      1. User specified task ID — confirm with user
      2. Load context, classify as frontend-only
      3. Dispatch 7 agents (skip backend specialist)
      4. Consolidate, present, resolve findings
      5. Apply fixes, verify
related:
  complementary:
    - optimus-task-executor
    - requesting-code-review
    - dev-validation
  differentiation:
    - name: requesting-code-review
      difference: >
        requesting-code-review dispatches reviewers during the dev-cycle.
        optimus-post-task-validator is a standalone validation that also checks
        spec compliance, test ID coverage, and cross-file consistency.
  sequence:
    after:
      - optimus-task-executor
    before:
      - dev-feedback-loop
verification:
  automated:
    - command: "git diff --name-only 2>/dev/null | wc -l"
      description: Changed files exist (uncommitted changes to validate)
      success_pattern: '[1-9]'
  manual:
    - All findings resolved (fixed or explicitly skipped by user)
    - Verification gate passed after fixes applied
    - Validation summary presented to user
---

# Post-Task Validator

Validates that a completed task was executed correctly: spec compliance, coding standards adherence, engineering best practices, test coverage, and production readiness. Uses parallel specialist agents for deep analysis, then presents findings interactively.

Runs AFTER optimus-task-executor finishes and BEFORE the final commit.

---

## Phase 0: Load Context

### Step 0.0: Identify Task to Validate

Determine which task to validate:

**If the user specified a task ID** (e.g., "validate T-012"):
- Use the provided task ID
- Confirm with the user using `AskUser`: "I'll validate task T-012: [task title]. Correct?"

**If the user did NOT specify a task ID** (e.g., "validate the last task", or just invoked the skill):
1. **Check for execution state:** Look for `docs/dev-cycle/optimus-task-executor-state.json` — if it exists and has a recent task, use that task ID
2. **Check git diff:** If no state file, examine uncommitted changes to infer which task was just implemented (look for task ID references in changed files, commit messages, or branch name)
3. **Fall back to tasks file:** Scan the tasks file for the most recently completed task (status "in_progress" or last "completed")
4. **Suggest to the user** using `AskUser`: "I identified the task to validate: T-XXX — [task title]. Is this correct, or would you like to validate a different task?"
5. **If no task can be identified**, ask the user to provide a task ID

**BLOCKING**: Do NOT proceed until the user confirms which task to validate.

### Step 0.1: Discover Project Structure

Before loading docs, discover the project's structure and tooling (reuse discoveries from optimus-task-executor if available):

1. **Identify stack:** Check for `go.mod`, `package.json`, `Makefile`, `Cargo.toml`, etc.
2. **Identify test commands:** Look in `Makefile`, `package.json` scripts, or CI config for lint, test, integration test, and E2E test commands.
3. **Identify reference docs:** Look for task specs, coding standards, API design, data model, and architecture docs.

Store discovered commands for use in verification gates:
```
LINT_CMD=<discovered lint command>
TEST_CMD=<discovered test command>
TEST_INTEGRATION_CMD=<discovered integration test command>
TEST_E2E_CMD=<discovered E2E test command>
```

### Step 0.2: Load Reference Documents

Read the discovered reference docs to understand what was expected:
- Task spec — the task being validated (find by ID): scope, acceptance criteria, testing strategy, DoD
- API contracts (if backend task)
- DB schema / data model (if backend task)
- Technical architecture
- Business requirements and user stories
- Coding standards (source of truth)
- Dependency relationships

### Step 0.3: Identify Changed Files

Identify all files created/modified by the task. Use the appropriate method:
- If changes are uncommitted: `git diff --name-only` and `git diff --name-only --cached`
- If committed: `git diff --name-only <base>..HEAD`

Read ALL changed files — the full content of every changed file is required for agent prompts.

### Step 0.4: Determine Task Scope

Classify the task based on the file extensions of changed files:
- **Backend-only** — only backend source files, migrations, backend tests changed
- **Frontend-only** — only frontend source files, styles, frontend tests, E2E tests changed
- **Full-stack** — both backend and frontend files changed

This determines which specialist agents to dispatch in Phase 1.

---

## Phase 1: Parallel Agent Dispatch

Dispatch ALL applicable agents simultaneously via `Task` tool. Each agent receives the full content of every changed file plus the task spec excerpt.

### Agent Roster

Dispatch specialist agents covering the validation domains below. Use the agent selection priority to pick the best available droid for each domain.

**Agent selection priority:**

1. **Ring review droids (preferred when available):**
   - `ring-default-code-reviewer` → Code Quality
   - `ring-default-business-logic-reviewer` → Business Logic
   - `ring-default-security-reviewer` → Security
   - `ring-default-ring-test-reviewer` → Test Quality
   - `ring-default-ring-nil-safety-reviewer` → Nil/Null Safety (always dispatch if available)
   - `ring-default-ring-consequences-reviewer` → Ripple Effects (always dispatch if available)
   - `ring-default-ring-dead-code-reviewer` → Dead Code (always dispatch if available)
   - `ring-dev-team-qa-analyst` → QA / Spec Compliance
   - `ring-dev-team-backend-engineer-golang` → Backend Patterns (Go projects)
   - `ring-dev-team-frontend-engineer` → Frontend Patterns (React/Next.js projects)
2. **Other available specialist droids:** If Ring droids are not available, use any other review droids
3. **Worker droid with domain instructions:** Fall back to `worker` with domain-specific instructions

| Validation Domain | When to Dispatch | Preferred Ring Droid |
|-------------------|------------------|---------------------|
| **Code Quality** — architecture, patterns, SOLID, DRY, maintainability | Always | `ring-default-code-reviewer` |
| **Business Logic** — domain correctness, edge cases, business rules | Always | `ring-default-business-logic-reviewer` |
| **Security** — vulnerabilities, OWASP, input validation, secrets | Always | `ring-default-security-reviewer` |
| **Test Quality** — coverage gaps, test quality, missing scenarios | Always | `ring-default-ring-test-reviewer` |
| **Nil/Null Safety** — nil pointer risks, unsafe dereferences | Always (if droid available) | `ring-default-ring-nil-safety-reviewer` |
| **Ripple Effects** — how changes propagate beyond changed files | Always (if droid available) | `ring-default-ring-consequences-reviewer` |
| **Dead Code** — orphaned code from changes | Always (if droid available) | `ring-default-ring-dead-code-reviewer` |
| **Frontend Patterns** — framework patterns, accessibility, performance | Frontend or full-stack tasks | `ring-dev-team-frontend-engineer` |
| **Backend Patterns** — language patterns, error handling, conventions | Backend or full-stack tasks | `ring-dev-team-backend-engineer-golang` |
| **Cross-File Consistency** — duplication, shared constants, imports | Always | `worker` with cross-file instructions |
| **Spec Compliance** — acceptance criteria, test IDs, API contracts | Always | `ring-dev-team-qa-analyst` |

### Agent Prompt Template

Each agent dispatch MUST include this information:

```
Goal: Post-task validation of T-XXX — [your validation domain]

Context:
  - Task ID: T-XXX
  - Task spec excerpt: [paste the full task section from the tasks file]
  - Coding standards: [paste relevant sections for this agent's domain]
  - Changed files (full content follows):
    [paste full content of each changed file with filename header]

Your job:
  Validate the implementation against the spec, coding standards, and engineering
  best practices. Report issues ONLY — do NOT fix anything.

Required output format:
  For each issue found, provide:
  - Severity: CRITICAL / HIGH / MEDIUM / LOW
  - File: exact file path
  - Line: line number or range
  - Rule violated: exact reference (coding standards section, spec criterion, or named best practice)
  - Summary: one-line description
  - Detail: what is wrong, why it matters, what should be done

  If no issues found, state "PASS — no issues in [domain]"
  Always include a "What Was Done Well" section acknowledging good practices.
```

### Special Instructions per Agent

**Spec Compliance agent** must additionally:
1. List every acceptance criterion from the task spec and mark PASS/FAIL/PARTIAL
2. List every test ID and verify a corresponding test exists
3. If the task has API endpoints, verify request/response format matches API contracts
4. If the task has DB changes, verify column types/constraints match the data model

**Cross-File Consistency agent** must additionally:
1. Check for values duplicated between files that should be a shared constant
2. Verify imports follow the project's layer architecture (no circular deps, no backwards imports)
3. Check that new code follows the same patterns as existing code in the same domain
4. Look for dead code (unused imports, unreachable branches, commented-out code)

---

## Phase 2: Consolidate and Deduplicate

After ALL agents return:

1. **Merge** all findings into a single list
2. **Deduplicate** — if multiple agents flag the same issue (same file + same concern), keep one entry and note which agents agreed
3. **Enrich** — for each finding, add:
   - Which validation phase it belongs to (Spec Compliance, Coding Standards, Security, Test Coverage, etc.)
   - Cross-references to the exact rule/spec it violates
4. **Sort** by severity: CRITICAL > HIGH > MEDIUM > LOW
5. **Assign** sequential IDs (F1, F2, F3...)

### Severity Classification

| Severity | Criteria | Examples |
|----------|----------|---------|
| **CRITICAL** | Spec violation, security vulnerability, data loss risk, auth bypass | Missing acceptance criterion, injection vulnerability, hardcoded secret, broken business rule |
| **HIGH** | Missing test from spec, coding standards violation, broken accessibility, missing validation | Test ID not implemented, standards violation, no error handling, missing ARIA labels |
| **MEDIUM** | Code quality concern, pattern inconsistency, maintainability issue, missing edge case test | Duplication between files, inconsistent naming, missing boundary test, no loading state |
| **LOW** | Polish, minor style issue, optional improvement | Redundant style rule, verbose comment, slightly suboptimal approach |

---

## Phase 3: Present Overview Table

Show the user the full picture before diving into individual findings:

```markdown
## Post-Task Validation: T-XXX — X findings across Y agents

| # | Severity | Category | File | Summary | Agents |
|---|----------|----------|------|---------|--------|
| F1 | CRITICAL | Security | auth.go | ... | Security |
| F2 | HIGH | Spec Compliance | page.tsx | ... | Spec, Frontend |
| F3 | MEDIUM | Code Quality | layout.tsx | ... | Code, Cross-file |

### Agent Verdicts
| Agent | Verdict | Issues |
|-------|---------|--------|
| Code Quality | PASS/FAIL | 0C 2H 3M 1L |
| Business Logic | PASS/FAIL | ... |
| Security | PASS/FAIL | ... |
| QA Analyst | PASS/FAIL | ... |
| Frontend/Backend | PASS/FAIL | ... |
| Cross-File | PASS/FAIL | ... |
| Spec Compliance | PASS/FAIL | ... |

Spec compliance: X/Y acceptance criteria verified
Test coverage: X/Y test IDs implemented
Security verdict: PASS / FAIL
```

---

## Phase 4: Interactive Finding-by-Finding Resolution (collect decisions only)

Process ONE finding at a time, starting from highest severity. Present ALL findings sequentially, collecting the user's decision for each. Do NOT apply any fix during this phase — only collect decisions.

For EACH finding, present:

### Problem Description
- What is wrong (file, line, code snippet if relevant)
- Which rule/spec it violates (exact reference to coding standards section, task spec line, or named best practice)
- Which agent(s) flagged it
- Why it matters — what breaks, what risk it creates, what the user would experience

### Impact Analysis (four lenses)

Evaluate the finding through all four perspectives:

- **User (UX):** How does this affect the end user? Usability degradation, confusion, broken workflow, accessibility issue? Would the user notice? Would it block their work?
- **Task focus:** Does this finding relate to what the task was supposed to deliver? Is it within the task's scope, or is it a tangential concern that should be a separate task?
- **Project focus:** Is this MVP-critical, or gold-plating? Does ignoring it now create rework later? Does it conflict with the project's priorities?
- **Engineering quality:** Does this hurt maintainability, testability, reliability, or codebase consistency? What is the technical debt cost of skipping it?

### Proposed Solutions (2-3 options)

For each option, evaluate all four lenses:

```
**Option A: [name]**
[What to do — concrete steps, files to change]
- UX: [impact on the end user's experience]
- Task focus: [within task scope / tangential]
- Project focus: [MVP-aligned / nice-to-have / out-of-scope]
- Engineering: [pros and cons — complexity, maintainability, test coverage, consistency]
- Effort: [trivial (< 5 min) / small (5-15 min) / moderate (15-60 min) / large (> 1h)]

**Option B: [name]**
[What to do]
- UX: [impact]
- Task focus: [alignment]
- Project focus: [alignment]
- Engineering: [pros/cons]
- Effort: [estimate]
```

Include a recommendation when one option is clearly better, with brief justification.

### Ask for Decision

Use `AskUser` tool. **BLOCKING**: Do NOT advance to the next finding until the user decides.

Internally record every decision: finding ID, chosen option (or "skip"), and rationale if provided.

---

## Phase 5: Batch Apply All Approved Fixes

**IMPORTANT:** This phase starts ONLY after ALL findings have been presented and ALL decisions collected. No fix is applied during Phase 4.

### Step 5.1: Present Pre-Apply Summary

Before touching any code, show the user a summary of everything that will be changed:

```markdown
## Fixes to Apply (X of Y findings)

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

### Step 5.2: Apply All Fixes

Apply ALL approved fixes in a single pass:

1. Group fixes by file to minimize file I/O
2. Apply all changes
3. Run lint — if format issues, fix and re-run
4. Run unit tests — if failures, diagnose and fix (max 3 attempts per failure)
5. If a fix causes test failures after 3 attempts, revert that specific fix, present the failure to the user, and ask for guidance

### Step 5.3: Verification Gate

After all fixes applied, run the full gate using discovered commands:
- Always run lint and unit tests with coverage profiling
- If backend files were changed: also run integration tests with coverage profiling
- If frontend files were changed: also run E2E tests (if available)

### Step 5.4: Coverage Verification

After the verification gate passes, measure test coverage:

**Unit test coverage:**
```bash
go test -coverprofile=coverage-unit.out ./...
go tool cover -func=coverage-unit.out | tail -1
```

**Integration test coverage (if applicable):**
```bash
go test -tags=integration -coverprofile=coverage-integration.out ./...
go tool cover -func=coverage-integration.out | tail -1
```

**Coverage gap analysis:**
```bash
# Untested functions (0% coverage) — potential gaps
go tool cover -func=coverage-unit.out | grep "0.0%"
```

**Thresholds:**
- Unit tests: 85% minimum
- Integration tests: 70% minimum

If coverage is below threshold, add findings to the results:
- **HIGH** severity for unit test coverage below 85%
- **MEDIUM** severity for integration test coverage below 70%
- List untested business-logic functions as individual **HIGH** findings

**E2E tests:**
If E2E tests are not configured, ask the user using `AskUser`:
"E2E tests are not configured for this project. Should E2E tests be implemented for this task?"
- If yes: flag as a finding (MEDIUM severity) in the validation summary
- If no: mark as SKIP in the summary

### Step 5.5: Test Scenario Gap Analysis

After coverage measurement, dispatch an agent to cross-reference the task spec's acceptance criteria with implemented tests and identify missing scenarios.

**Dispatch a test gap analyzer** via `Task` tool. Use `ring-default-ring-test-reviewer`, `ring-dev-team-qa-analyst`, or `worker` (in that priority order).

The agent receives:
1. **Task spec** — acceptance criteria, testing strategy, test IDs
2. **Source files changed by this task** — full content
3. **Test files for changed source** — full content
4. **Coverage profile** — `go tool cover -func` output

```
Goal: Cross-reference task spec with implemented tests to find scenario gaps.

Context:
  - Task spec: [paste task section with acceptance criteria and test IDs]
  - Source files: [full content]
  - Test files: [full content]
  - Coverage profile: [go tool cover -func output]

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
```

**Gap findings become part of Phase 4** (interactive resolution) — each HIGH gap is presented as a finding for user decision (fix now or defer).

---

## Phase 6: Convergence Loop (MANDATORY — automatic re-validation)

After Phase 5 completes (whether fixes were applied or all findings were skipped), the validator MUST automatically re-run validation on the updated code. This catches new issues exposed by the fixes just applied.

**Loop rules:**
- **Maximum rounds:** 5 (the initial run counts as round 1)
- **Progress indicator:** Show `"=== Re-validation round X of 5 ==="` at the start of each re-run
- **Scope:** Re-execute Phase 1 (dispatch agents) and Phase 2 (consolidate). Do NOT re-load context (Phase 0) — use the same task and docs, but re-read any files that were modified by fixes. Agents receive the UPDATED file contents
- **Finding deduplication:** Maintain a ledger of ALL findings from ALL previous rounds (by ID and description). Only present findings that are NEW — not already seen, resolved, or skipped in a prior round. If a finding was skipped/discarded by the user in a prior round, do NOT re-present it
- **If new findings exist:** Present them using Phase 3 (overview) and Phase 4 (interactive resolution), apply via Phase 5 (batch apply), then loop again
- **Stop conditions (any one triggers exit):**
  1. Zero new findings in the current round
  2. Only LOW severity findings remain (ask user: "Only LOW findings remain. Stop validation?")
  3. Round 5 completed (hard limit)
  4. User explicitly requests to stop (via AskUser response)

**Round summary (show after each round):**

```markdown
### Round X of 5 — Summary
- New findings this round: N (C critical, H high, M medium, L low)
- Cumulative: X total findings across Y rounds
- Fixed: A | Skipped: B | Deferred: C
- Status: CONVERGED / CONTINUING / HARD LIMIT REACHED
```

**When the loop exits**, proceed to the Validation Summary with the cumulative results from ALL rounds.

---

## Phase 7: Validation Summary

```markdown
## Post-Task Validation Summary: T-XXX

### Verdict: APPROVED / APPROVED WITH CAVEATS / NEEDS REWORK

### Agent Results
| Agent | Verdict | Issues Found | Fixed | Skipped |
|-------|---------|-------------|-------|---------|
| Code Quality | PASS | 3 | 2 | 1 |
| Business Logic | PASS | 1 | 1 | 0 |
| Security | PASS | 0 | 0 | 0 |
| QA Analyst | PASS | 4 | 3 | 1 |

### Spec Compliance: X/Y acceptance criteria PASS
| Criterion | Status | Notes |
|-----------|--------|-------|
| AC-1 | PASS | |
| AC-2 | PASS | |

### Test Coverage: X/Y test IDs implemented
| Test ID | Status | File |
|---------|--------|------|
| U1 | PASS | ... |
| E1 | PASS | ... |

### Fixed (X findings)
| # | Finding | Agent(s) | Solution Applied |
|---|---------|----------|-----------------|
| F1 | ... | Security | Option A: ... |

### Skipped (X findings)
| # | Finding | Agent(s) | Reason |
|---|---------|----------|--------|
| F5 | ... | QA | User decision: out of scope |

### Verification
- Lint: PASS
- Unit tests: PASS (X tests)
- Integration tests: PASS / SKIPPED
- E2E tests: PASS / SKIPPED

### Test Coverage
- Unit tests: XX.X% (threshold: 85%) — PASS / FAIL
- Integration tests: XX.X% (threshold: 70%) — PASS / FAIL
- Untested functions: X (Y business logic, Z infrastructure)
- E2E tests: Configured / Not configured (user decision: implement / skip)
```

---

## Rules

### Agent Dispatch
- ALWAYS dispatch agents for: Code Quality, Business Logic, Security, QA, Cross-File Consistency, Spec Compliance
- Dispatch Frontend/Backend specialists based on task scope (Step 0.4)
- Each agent receives the FULL content of ALL changed files — never partial content
- Agents run in PARALLEL — do not wait for one before dispatching another
- Use whatever review droids are available; fall back to `worker` with domain instructions

### Scope
- Validate ONLY the files changed by this task — do not audit the entire codebase
- Do not suggest refactoring of pre-existing code unless the task introduced a regression
- Flag pre-existing issues as "pre-existing, not from this task" and do not count them as findings

### Objectivity
- Every finding must reference a specific rule (coding standards section, task spec line, or named best practice)
- "I would do it differently" is NOT a valid finding — it must violate a documented standard or create a measurable risk
- Subjective style preferences are LOW severity at most

### Prioritization
- Security vulnerabilities and spec violations are always CRITICAL/HIGH regardless of effort to fix
- Code style issues that don't affect correctness are LOW
- Missing tests for happy paths are HIGH; missing tests for extreme edge cases are MEDIUM

### Test Gap Cross-Reference
When agents identify a missing test (from QA analyst, spec compliance, or any other agent):
1. **Search future tasks** in the tasks file to check if the test is planned for a later task
2. **If planned in a future task (T-XXX):**
   - Include in the finding: "This test is planned in T-XXX: [task title]"
   - Provide your opinion on timing: should it be created now or deferred? Consider whether the current task introduced the code path being tested, and whether deferring creates a risk window (untested code in production between tasks)
   - During interactive resolution (Phase 4), ask via `AskUser`: "Test for [scenario] is planned for T-XXX. I recommend [creating now / deferring] because [reason]. Do you want to anticipate this test?"
3. **If NOT planned in any future task:**
   - Flag as a standard finding — recommend adding the test now
4. Do NOT silently downgrade test gap severity because a future task covers it — the user decides whether to anticipate or defer

### No False Positives
- If you're unsure whether something is a violation, check the existing codebase for precedent
- If the codebase already does the same thing elsewhere without issue, it's not a finding
- If the spec is ambiguous and the implementation is reasonable, flag as LOW (not HIGH)

### Communication
- Be specific: "line 42 of file.tsx uses X, but coding standards section Y requires Z"
- Be constructive: always provide a concrete fix, not just criticism
- Be honest about effort: don't say "trivial" for something that requires refactoring multiple files
