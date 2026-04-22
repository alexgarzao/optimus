---
name: optimus-check
description: "Stage 3 of the task lifecycle. Validates that a completed task was implemented correctly: spec compliance, coding standards adherence, engineering best practices, test coverage, and production readiness. Uses parallel specialist agents for deep analysis, then presents findings interactively. Runs AFTER optimus-build finishes to validate code quality and spec compliance before the task can proceed to PR review or close."
trigger: >
  - After optimus-build completes all phases and verification gates pass
  - When user requests validation of a completed task (e.g., "validate T-012")
  - Before the final commit of a task execution
skip_when: >
  - Task is pure research or documentation (no code to validate)
  - Already inside a code review skill execution
prerequisite: >
  - Task execution is complete (user provides ID or skill auto-detects last executed task)
  - Changed files exist (committed or uncommitted -- both are supported)
  - Reference docs exist (task spec, coding standards)
  - Project has lint and test commands configured
NOT_skip_when: >
  - "Task was simple" -- Simple tasks still need spec compliance checks.
  - "Tests already pass" -- Passing tests do not guarantee spec compliance or code quality.
  - "optimus-build already ran verification gates" -- Gates check pass/fail; this validates correctness.
  - "Time pressure" -- Validation prevents rework, saving time overall.
examples:
  - name: Validate a full-stack task
    invocation: "Validate task T-012"
    expected_flow: >
      1. User specified task ID -- confirm with user
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
      1. Check session state files or git diff for context
      2. Identify the task that was just executed
      3. Suggest to user and confirm via AskUser
      4. Standard validation flow
  - name: Validate a frontend-only task
    invocation: "Validate task T-015"
    expected_flow: >
      1. User specified task ID -- confirm with user
      2. Load context, classify as frontend-only
      3. Dispatch 7 agents (skip backend specialist)
      4. Consolidate, present, resolve findings
      5. Apply fixes, verify
related:
  complementary:
    - optimus-plan
    - optimus-build
    - optimus-deep-doc-review
    - requesting-code-review  # external: ring ecosystem
    - dev-validation  # external: ring ecosystem
  differentiation:
    - name: requesting-code-review
      difference: >
        requesting-code-review dispatches reviewers during the dev-cycle.
        optimus-check is a standalone validation that also checks
        spec compliance, test ID coverage, and cross-file consistency.
  sequence:
    after:
      - optimus-build
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

Validates that a completed task was implemented correctly: spec compliance, coding standards
adherence, engineering best practices, test coverage, and production readiness. Uses parallel
specialist agents for deep analysis, then presents findings interactively.

Runs AFTER optimus-build finishes. Validates both committed and uncommitted
changes — it handles both cases (use `git diff` for uncommitted, `git diff base..HEAD`
for committed code).

---

## Phase 1: Load Context

### Step 1.0: Verify GitHub CLI (HARD BLOCK)
Verify GitHub CLI — see AGENTS.md Protocol: GitHub CLI Check.

### Step 1.0.1: Find and Validate tasks.md
**HARD BLOCK:** Find and validate tasks.md — see AGENTS.md Protocol: tasks.md Validation.

### Step 1.0.2: Verify Workspace (HARD BLOCK)
Resolve workspace — see AGENTS.md Protocol: Workspace Auto-Navigation.

### Step 1.0.3: Check tasks.md Divergence (warning)
Check tasks.md divergence — see AGENTS.md Protocol: Divergence Warning.

### Step 1.0.4: Branch-Task Cross-Validation
Branch-task cross-validation — included in AGENTS.md Protocol: Workspace Auto-Navigation.

### Step 1.0.5: Validate PR Title (if PR exists)
Validate PR title — see AGENTS.md Protocol: PR Title Validation.

### Step 1.0.6: Identify Task to Validate

**If the user specified a task ID** (e.g., "validate T-012"):
- Use the provided task ID
- Confirm with the user using `AskUser`: "I'll validate task T-012: [task title]. Correct?"

**If the user did NOT specify a task ID** (e.g., "validate the last task", or just invoked the skill):
1. **Identify the task to validate:** Scan the table for tasks with status `Em Andamento` (build completed) or `Validando Impl` (re-execution). If exactly one, suggest it. If multiple, ask user which one.
2. **If no tasks with `Em Andamento` or `Validando Impl`:** Check git branch name for task ID references, then ask the user.
3. **Suggest to the user** using `AskUser`: "I identified the task to validate: T-XXX — [task title]. Is this correct, or would you like to validate a different task?"
4. **If no task can be identified**, ask the user to provide a task ID

**BLOCKING**: Do NOT proceed until the user confirms which task to validate.

### Step 1.0.7: Check Session State
Execute session state protocol — see AGENTS.md Protocol: Session State. Use stage=`check`, status=`Validando Impl`.

**On stage completion** (after Phase 10 validation summary): delete the session file.

### Step 1.0.8: Validate and Update Task Status

**HARD BLOCK:** This step is mandatory. Do NOT skip it.

1. Read `tasks.md` and find the row for the confirmed task ID
2. Check the **Status** column:
   - If status is `Em Andamento` → proceed (build has completed)
   - If status is `Validando Impl` → proceed (re-execution of this stage)
   - If status is `Pendente` → **STOP**: "Task T-XXX is in 'Pendente'. Run plan and build first."
   - If status is `Validando Spec` → **STOP**: "Task T-XXX is in 'Validando Spec'. Run build first."
   - If status is `Revisando PR` or `DONE` → **STOP**: "Task T-XXX is in '<status>'. It has already moved past this stage."
   - If status is `Cancelado` → **STOP**: "Task T-XXX was cancelled. Cannot validate a cancelled task."
3. **Check dependencies (HARD BLOCK):** Read the Depends column for this task.
   - If Depends is `-` → proceed (no dependencies)
   - For each dependency ID listed, check its Status in the table:
     - If ALL dependencies have status `DONE` → proceed
     - If ANY dependency is NOT `DONE`:
       - Invoke notification hooks (event=`task-blocked`) — see AGENTS.md Protocol: Notification Hooks.
       - If the dependency has status `Cancelado` → **STOP**: `"T-YYY was cancelled (Cancelado). Consider removing this dependency via /optimus-tasks."`
       - Otherwise → **STOP**: `"Task T-XXX depends on T-YYY (status: '<status>'). T-YYY must be DONE first."`
3.1. **Active version guard:** Check active version guard — see AGENTS.md Protocol: Active Version Guard.
4. **Expanded confirmation before status change:**
   - **If status will change** (current status is NOT `Validando Impl`) AND the user did NOT specify the task ID explicitly (auto-detect):
     - Present to the user via `AskUser`:
       ```
       I'm about to change task T-XXX status from '<current>' to 'Validando Impl'.

       **T-XXX: [title]**
       **Version:** [version from table]

       Confirm status change?
       ```
     - **BLOCKING:** Do NOT change status until the user confirms
   - **If re-execution** (status is already `Validando Impl`) OR the user specified the task ID explicitly:
     - Skip expanded confirmation (user already has context)
5. Update the Status column to `Validando Impl` (if not already)
6. Commit the status change immediately:
   ```bash
   git add "$TASKS_FILE"
   git commit -m "chore(tasks): set T-XXX status to Validando Impl"
   ```
   Where `TASKS_FILE` is the resolved path from the tasks.md Validation protocol.
7. Invoke notification hooks (event=`status-change`) — see AGENTS.md Protocol: Notification Hooks.

**Why commit immediately:** If the session is interrupted or the agent crashes before any review fixes are committed, the status update would be lost. Committing now ensures the status change is persisted regardless of the review outcome.

### Step 1.1: Discover Project Structure

Before loading docs, discover the project's structure and tooling (reuse discoveries from optimus-build if available):

1. **Identify stack:** Check for `go.mod`, `package.json`, `Makefile`, `Cargo.toml`, etc.
2. **Identify test commands:** Look in `Makefile`, `package.json` scripts, or CI config for lint, test, integration test, and E2E test commands.
3. **Identify project rules and AI instructions (MANDATORY):** Execute project rules discovery — see AGENTS.md Protocol: Project Rules Discovery.

4. **Identify reference docs:** Look for task specs, API design, data model, and architecture docs.

Store discovered commands for use in verification gates:
```
LINT_CMD=<discovered lint command>
TEST_CMD=<discovered test command>
TEST_INTEGRATION_CMD=<discovered integration test command>
TEST_E2E_CMD=<discovered E2E test command>
```

### Step 1.2: Load Reference Documents

Read the task's `TaskSpec` column from tasks.md and resolve the full path as
`<TASKS_DIR>/<TaskSpec>`. Load the Ring pre-dev task spec and derive subtask files. Also load:
- Task spec: scope, acceptance criteria, testing strategy, DoD
- API contracts (if backend task)
- DB schema / data model (if backend task)
- Technical architecture
- Business requirements and user stories
- Coding standards (source of truth)
- Dependency relationships

### Step 1.3: Identify Changed Files

Identify all files created/modified by the task. Use the appropriate method:
- If changes are uncommitted: `git diff --name-only` and `git diff --name-only --cached`
- If committed: `git diff --name-only <base>..HEAD`

Read ALL changed files — the full content of every changed file is required for agent prompts.

### Step 1.4: Determine Task Scope

Classify the task based on the file extensions of changed files:
- **Backend-only** — only backend source files, migrations, backend tests changed
- **Frontend-only** — only frontend source files, styles, frontend tests, E2E tests changed
- **Full-stack** — both backend and frontend files changed

This determines which specialist agents to dispatch in Phase 3.

---

## Phase 2: Static Analysis and Coverage Profiling

**MANDATORY.** Before dispatching review agents, run automated checks to collect concrete data. These results feed into agent prompts and become findings if they fail.

### Step 2.1: Run Static Analysis (parallel)

Run ALL applicable checks simultaneously. Capture stdout, stderr, exit code for each.

Check `.optimus/config.json` for custom commands first. If `commands.lint` exists, use it. If a command key is present but empty (`""`), skip that check entirely. If missing, fall back to auto-detection below.

| # | Check | Command (discover from project) | What it detects |
|---|-------|---------------------------------|-----------------|
| 1 | Lint | `make lint` or `golangci-lint run` or `npm run lint` | Linter rule violations |
| 2 | Vet | `go vet ./...` (Go projects) | Suspicious constructs |
| 3 | Import ordering | `goimports -l .` (Go projects) | Unordered/missing imports |
| 4 | Format | `gofmt -l .` (Go) or `npx prettier --check .` (JS/TS) | Formatting violations |
| 5 | Doc generation | `make generate-docs` (if target exists) | Stale documentation |

For each check that **fails**, create a finding:
- Severity: **HIGH** for lint/vet, **MEDIUM** for format/imports/docs
- Source: `[Static Analysis: <check-name>]`
- Include the first 20 lines of error output

For checks that **pass**, note them for the Phase 5 overview.

Skip checks whose commands don't exist in the project (e.g., skip `go vet` in a pure JS project).

### Step 2.2: Run Unit Tests (Baseline)

Unit tests should pass before proceeding to agent dispatch. This establishes
the baseline — if unit tests are already failing, review findings may be unreliable.

Check `.optimus/config.json` for custom `commands.test` first. Fall back to `make test` if not configured.

```bash
make test                    # Unit tests — MANDATORY
```

**If unit tests fail:**
1. Present the failure output (first 30 lines)
2. Ask the user via `AskUser`: "Unit tests are failing. Fix before continuing, or skip check?"
3. Do NOT proceed to Phase 3 until unit tests pass or user explicitly chooses to skip

**If unit tests pass:** collect coverage data for analysis using the project's Makefile
or `.optimus/config.json` commands:

```bash
# Preferred: Makefile target
make test-coverage 2>/dev/null

# Fallback: stack-specific
# Go:     go test -coverprofile=coverage-unit.out ./... && go tool cover -func=coverage-unit.out
# Node:   npm test -- --coverage
# Python: pytest --cov=. --cov-report=term
```

If no coverage command is available, mark as SKIP.

**NOTE:** Integration and E2E tests are NOT run here. They run only in Phase 9
(after convergence loop, before summary) or when the user invokes them directly.
This avoids slow test suites blocking the review loop.

### Step 2.3: Analyze Coverage

Parse the coverage output (format varies by stack) to identify:
- Overall coverage percentage
- Packages/files with lowest coverage (bottom 20)
- Functions/methods with 0% coverage (untested)

Create findings for coverage issues:
- **HIGH**: Business logic functions with 0% coverage
- **MEDIUM**: Packages below 70% coverage
- **LOW**: Packages below 85% coverage
- Infrastructure/generated code with 0% → skip (not a finding)

### Step 2.4: Test Scenario Gap Analysis

Dispatch a test gap analyzer via `Task` tool. Use `ring-default-ring-test-reviewer` or `ring-dev-team-qa-analyst`.

The agent receives: source files, test files, and coverage output (if available).

```
Goal: Cross-reference implemented tests with source code to find missing scenarios.

For each public function changed/added by this task:
  - Happy path tested?
  - Error paths tested (each error return)?
  - Edge cases (nil, empty, boundary values)?
  - Validation failures?
  - Integration points (DB failure, timeout, retry)?

Report: function, existing scenarios, missing scenarios, priority (HIGH/MEDIUM/LOW)
```

HIGH priority gaps become findings in Phase 4 consolidation.

### Step 2.5: Collect Results

Merge all static analysis findings and coverage gap findings into the findings list.
These are presented alongside agent review findings in Phase 5 (overview) and Phase 6 (interactive resolution).

---

## Phase 3: Parallel Agent Dispatch

Dispatch ALL applicable agents simultaneously via `Task` tool. Each agent receives the full content of every changed file plus the task spec excerpt.

### Agent Roster

Dispatch specialist agents covering the validation domains below. Use the agent selection priority to pick the best available droid for each domain.

**Ring droids are REQUIRED** — verify ring droids — see AGENTS.md Protocol: Ring Droid Requirement Check. If the core review droids are not installed, **STOP** and inform the user:
```
Required ring droids are not installed. Install them before running this skill:
  - ring-default-code-reviewer
  - ring-default-business-logic-reviewer
  - ring-default-security-reviewer
  - ring-default-ring-test-reviewer
  - ring-default-ring-nil-safety-reviewer
  - ring-default-ring-consequences-reviewer
  - ring-default-ring-dead-code-reviewer
  - ring-dev-team-qa-analyst
```

**Droids to dispatch:**

| Validation Domain | When to Dispatch | Ring Droid |
|-------------------|------------------|------------|
| **Code Quality** — architecture, patterns, SOLID, DRY, maintainability | Always | `ring-default-code-reviewer` |
| **Business Logic** — domain correctness, edge cases, business rules | Always | `ring-default-business-logic-reviewer` |
| **Security** — vulnerabilities, OWASP, input validation, secrets | Always | `ring-default-security-reviewer` |
| **Test Quality** — coverage gaps, test quality, missing scenarios | Always | `ring-default-ring-test-reviewer` |
| **Nil/Null Safety** — nil pointer risks, unsafe dereferences | Always | `ring-default-ring-nil-safety-reviewer` |
| **Ripple Effects** — how changes propagate beyond changed files | Always | `ring-default-ring-consequences-reviewer` |
| **Dead Code** — orphaned code from changes | Always | `ring-default-ring-dead-code-reviewer` |
| **Frontend Patterns** — framework patterns, accessibility, performance | Frontend or full-stack tasks | `ring-dev-team-frontend-engineer` |
| **Backend Patterns** — language patterns, error handling, conventions | Backend or full-stack tasks | `ring-dev-team-backend-engineer-golang` |
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
1. List every acceptance criterion from the Ring source (via `TaskSpec` column) and mark PASS/FAIL/PARTIAL
2. List every test ID and verify a corresponding test exists
4. If the task has API endpoints, verify request/response format matches API contracts
5. If the task has DB changes, verify column types/constraints match the data model

**Ripple Effects agent** (`ring-default-ring-consequences-reviewer`) must additionally:
1. Check for values duplicated between files that should be a shared constant
2. Verify imports follow the project's layer architecture (no circular deps, no backwards imports)
3. Check that new code follows the same patterns as existing code in the same domain

**Dead Code agent** (`ring-default-ring-dead-code-reviewer`) must additionally:
1. Look for dead code (unused imports, unreachable branches, commented-out code)

---

## Phase 4: Consolidate and Deduplicate

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

## Phase 5: Present Overview Table

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

## Phase 6: Interactive Finding-by-Finding Resolution (collect decisions only)

**BEFORE presenting the first finding:** Announce total findings count prominently: `"### Total findings to review: N"`

Process ONE finding at a time, starting from highest severity. Present ALL findings sequentially, collecting the user's decision for each. Do NOT apply any fix during this phase — only collect decisions.

For EACH finding, present with `"Finding X of N"` in the header:

### Deep Research Before Presenting (MANDATORY)
Execute deep research before presenting each finding — see AGENTS.md "Common Patterns > Deep Research Before Presenting". All 10 checklist items apply.

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

Present 2-3 options using the format from AGENTS.md "Common Patterns > Finding Option Format".

### Ask for Decision

Use `AskUser` tool. **BLOCKING**: Do NOT advance to the next finding until the user decides.
**Every AskUser MUST include a "Tell me more" option** alongside the fix/skip options.

**IMMEDIATE RESPONSE RULE** — see AGENTS.md "Finding Presentation" item 8. If the user
selects "Tell me more" or responds with free text: STOP, research and answer RIGHT NOW.
**NEVER defer to the end of the findings loop.**

Internally record every decision: finding ID, chosen option (or "skip"), and rationale if provided. Do NOT apply any fix yet — all fixes are applied in Phase 7.

**Same-nature grouping:** applied automatically per AGENTS.md "Finding Presentation" item 3.

---

## Phase 7: Batch Apply All Approved Fixes

**IMPORTANT:** This phase starts ONLY after ALL findings have been presented and ALL decisions collected. No fix is applied during Phase 6.

### Step 7.1: Present Pre-Apply Summary

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

### Step 7.2: Apply All Fixes via Ring Droids
Apply fixes using ring droids with TDD cycle — see AGENTS.md "Common Patterns > Fix Implementation".

**Droid selection for this stage:** Use the stack-appropriate droid (Go→`ring-dev-team-backend-engineer-golang`, TS→`ring-dev-team-backend-engineer-typescript`, React→`ring-dev-team-frontend-engineer`, tests→`ring-dev-team-qa-analyst`). Documentation fixes use ring-tw-team droids without TDD.

**After each fix:** run unit tests to verify no regressions.

### Step 7.3: Final Verification (Lint + Unit Tests)

**After ALL fixes are applied**, run lint and unit tests one final time:

```bash
make lint                    # Lint — runs ONCE after all fixes
make test                    # Unit tests — final regression check
```

If lint fails, fix formatting issues and re-run. If unit tests fail after 3 attempts
to fix, revert the offending fix and ask the user.

**NOTE:** Integration and E2E tests do NOT run here — they run in Phase 9 (after convergence loop, before summary).

### Step 7.4: Coverage Verification

Measure coverage — see AGENTS.md Protocol: Coverage Measurement.

If coverage is below threshold, add findings to the results.

**E2E tests:**
If `make test-e2e` target does not exist, mark as SKIP in the summary. Do NOT ask the user whether to implement E2E — that's a project-level decision, not a per-task decision.

### Step 7.5: Test Scenario Gap Analysis

After coverage measurement, dispatch an agent to cross-reference the task spec's acceptance criteria with implemented tests and identify missing scenarios.

**Dispatch a test gap analyzer** via `Task` tool. Use `ring-default-ring-test-reviewer` or `ring-dev-team-qa-analyst`.

The agent receives:
1. **Task spec** — acceptance criteria, testing strategy, test IDs
2. **Source files changed by this task** — full content
3. **Test files for changed source** — full content
4. **Coverage profile** — coverage command output (if available)

```
Goal: Cross-reference task spec with implemented tests to find scenario gaps.

Context:
  - Task spec: [paste task section with acceptance criteria and test IDs]
  - Source files: [full content]
  - Test files: [full content]
  - Coverage profile: [coverage command output]

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

**Gap findings become part of Phase 6** (interactive resolution) — each HIGH gap is presented as a finding for user decision (fix now or defer).

---

## Phase 8: Convergence Loop (MANDATORY)

Execute the convergence loop — see AGENTS.md "Common Patterns > Convergence Loop".

**Stage-specific scope for fresh sub-agent dispatch (rounds 2+):**
Use any available ring review droid (e.g., `ring-default-code-reviewer`). The sub-agent receives:
1. All changed files (re-read fresh from disk)
2. Task spec (re-read from tasks.md)
3. Project rules (re-read fresh)
4. The findings ledger (for dedup only)
5. Analysis instructions: code quality, business logic, security, test quality, spec compliance, cross-file consistency

When the loop exits, proceed to Phase 9 (integration/E2E tests).

---

## Phase 9: Integration and E2E Tests (before push)

**After the convergence loop exits**, run integration and E2E tests. These are slow and
expensive, so they run ONCE at the end — not during the fix/convergence cycle.

```bash
make test-integration        # Integration tests — if target exists
make test-e2e                # E2E tests — if target exists
```

| Test Type | Makefile Target | If target exists | If target missing |
|-----------|----------------|-----------------|-------------------|
| Integration | `make test-integration` | **HARD BLOCK** if fails | SKIP |
| E2E | `make test-e2e` | **HARD BLOCK** if fails | SKIP |

**If any test fails:**
1. Present the failure output (first 30 lines)
2. Ask via `AskUser`: "Integration/E2E tests are failing. What should I do?"
   - Fix the issue (dispatch ring droid)
   - Skip and proceed to summary (user will handle later)

**If all pass (or targets don't exist):** proceed to the Validation Summary.

---

## Phase 10: Validation Summary

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
- Integration tests: PASS / SKIPPED (Phase 9)
- E2E tests: PASS / SKIPPED (Phase 9)

### Test Coverage
- Unit tests: XX.X% (threshold: 85%) — PASS / FAIL
- Untested functions: X (Y business logic, Z infrastructure)
```

---

## Phase 11: Push Commits (optional)
Offer to push commits — see AGENTS.md Protocol: Push Commits.

---

## Phase 12: Offer PR Creation

After the validation summary is presented and the verdict is APPROVED or APPROVED WITH CAVEATS,
offer to create a PR for the task.

### Step 12.1: Check if PR Already Exists

```bash
gh pr list --head "$(git branch --show-current)" --json number,state,url --jq '.[]'
```

- **If PR already exists (any state):** skip PR creation — inform the user: "PR #X already exists: <url>"
- **If no PR exists:** proceed to Step 12.2

### Step 12.2: Generate PR Title (Conventional Commits)

Derive the PR title from the task's **Tipo** column and title:

1. Read the Tipo for the task and map to the conventional commit prefix:
   - Feature→`feat`, Fix→`fix`, Refactor→`refactor`, Chore→`chore`, Docs→`docs`, Test→`test`
2. Use the task ID as scope
3. Use the task title as description (lowercase, imperative)

**Format:** `<type>(T-XXX): <description>`

**Example:** Task T-003 "User registration API" with Tipo "Feature" → `feat(T-003): add user registration API`

### Step 12.3: Offer to Create

Ask via `AskUser`:
```
Validation complete. Would you like to create a PR?
  Title: <generated title>
  Base: <default branch>
  Head: <current branch>
```
Options:
- **Create PR with this title**
- **Create PR with a different title** (user provides)
- **Skip** — I'll create it manually

If the user chooses to create:
```bash
gh pr create --title "<title>" --body "<auto-generated body>" --base <default_branch> --assignee @me
```

The `--assignee @me` flag assigns the PR to the authenticated GitHub user automatically.

The body should include:
- Task ID and title
- Objective (from Ring source via `TaskSpec` column)
- Link to the task section in tasks.md

### Step 12.4: Confirm

If created, show: "PR #N created: <url> (assigned to you)"

**NOTE:** PR creation is optional — the user may prefer to create it manually with additional
context. The agent NEVER creates a PR without explicit user approval.

---

## Rules

### Agent Dispatch
- ALWAYS dispatch agents for: Code Quality, Business Logic, Security, QA, Cross-File Consistency, Spec Compliance
- Dispatch Frontend/Backend specialists based on task scope (Step 1.4)
- Each agent receives the FULL content of ALL changed files — never partial content
- Agents run in PARALLEL — do not wait for one before dispatching another
- Ring droids are required — do not proceed without them

### Scope
- Validate ONLY the files changed by this task — do not audit the entire codebase
- Do not suggest refactoring of pre-existing code unless the task introduced a regression
- Flag pre-existing issues as "pre-existing, not from this task" and do not count them as findings

### Objectivity
- Every finding must reference a specific rule (coding standards section, task spec line, or named best practice)
- "I would do it differently" is NOT a valid finding — it must violate a documented standard or create a measurable risk
- Subjective style preferences are LOW severity at most
- BEFORE presenting each finding: deep research is MANDATORY — project patterns, architectural decisions, existing codebase, task focus, user/consumer use cases, UX impact, API best practices, engineering best practices, language-specific idioms. Option A must be the correct approach backed by research evidence, regardless of effort

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
   - During interactive resolution (Phase 6), ask via `AskUser`: "Test for [scenario] is planned for T-XXX. I recommend [creating now / deferring] because [reason]. Do you want to anticipate this test?"
3. **If NOT planned in any future task:**
   - Flag as a standard finding — recommend adding the test now
4. Do NOT silently downgrade test gap severity because a future task covers it — the user decides whether to anticipate or defer

### No False Positives
- If you're unsure whether something is a violation, check the existing codebase for precedent
- If the codebase already does the same thing elsewhere without issue, it's not a finding
- If the spec is ambiguous and the implementation is reasonable, flag as LOW (not HIGH)

### User Authority Over Decisions
- The agent NEVER decides whether a finding should be fixed or skipped — the USER always decides
- ALL findings (CRITICAL, HIGH, MEDIUM, and LOW) MUST be presented to the user for decision
- The agent may recommend an option, but MUST wait for user approval via AskUser before proceeding
- Do NOT auto-skip, auto-dismiss, or auto-resolve any finding regardless of severity
- Do NOT group LOW findings and decide they "don't need attention" — present them individually
- If the convergence loop finds only LOW findings, still present each one to the user — do NOT stop the loop without user confirmation

### Dry-Run Mode
If the user requests a dry-run (e.g., "dry-run review T-012", "preview review"):
- Run ALL analysis phases (Phase 2, Phase 3, Phase 4, Phase 5) normally
- Present ALL findings in Phase 6 (interactive resolution)
- **Do NOT apply any fixes** — skip Phase 7 (batch apply) entirely
- **Do NOT change task status** — skip the status update in Step 1.0.8
- **Do NOT run the convergence loop** — one pass is sufficient for estimation
- Present a summary showing: total findings, severity breakdown, estimated fix effort
- This allows the user to see what would happen before committing to a full review

### Communication
- Be specific: "line 42 of file.tsx uses X, but coding standards section Y requires Z"
- Be constructive: always provide a concrete fix, not just criticism
- Be honest about effort: don't say "trivial" for something that requires refactoring multiple files
- **Next step suggestion:** After the validation summary (Phase 10) and optional PR creation (Phase 12),
  inform the user: "Implementation review complete. Next step: run `/optimus-pr-check`
  for PR review (optional), or `/optimus-done` to close this task."
