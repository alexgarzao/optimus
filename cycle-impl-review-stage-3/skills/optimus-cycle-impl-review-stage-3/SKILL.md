---
name: optimus-cycle-impl-review-stage-3
description: >
  Stage 3 of the task lifecycle. Validates that a completed task was executed
  correctly: spec compliance, coding standards adherence, engineering best
  practices, test coverage, and production readiness. Uses parallel specialist
  agents for deep analysis, then presents findings interactively.
  Runs AFTER optimus-cycle-impl-stage-2 finishes and BEFORE the final commit.
trigger: >
  - After optimus-cycle-impl-stage-2 completes all phases and verification gates pass
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
  - "optimus-cycle-impl-stage-2 already ran verification gates" → Gates check pass/fail; this validates correctness.
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
      1. Check optimus-cycle-impl-stage-2-state.json or git diff for context
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
    - optimus-cycle-impl-stage-2
    - requesting-code-review
    - dev-validation
  differentiation:
    - name: requesting-code-review
      difference: >
        requesting-code-review dispatches reviewers during the dev-cycle.
        optimus-cycle-impl-review-stage-3 is a standalone validation that also checks
        spec compliance, test ID coverage, and cross-file consistency.
  sequence:
    after:
      - optimus-cycle-impl-stage-2
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

Runs AFTER optimus-cycle-impl-stage-2 finishes and BEFORE the final commit.

---

## Phase 0: Load Context

### Step 0.0: Find and Validate tasks.md

1. **Find tasks.md:** Look in `./tasks.md` (project root). If not found, look in `./docs/tasks.md`. If not found in either, **STOP** and suggest `/optimus-cycle-migrate`.
2. **Validate format (HARD BLOCK):**
   - **First line** must be `<!-- optimus:tasks-v1 -->` (format marker). If missing → **STOP**.
   - A markdown table exists with columns: ID, Title, Tipo, Status, Depends, Priority, Branch
   - All task IDs match `T-NNN` pattern
   - All Tipo values are valid (`Feature`, `Fix`, `Refactor`, `Chore`, `Docs`, `Test`)
   - All Status values are valid (`Pendente`, `Validando Spec`, `Em Andamento`, `Validando Impl`, `Revisando PR`, `**DONE**`)
   - All Depends values are `-` or comma-separated valid task IDs
   - No duplicate task IDs

If validation fails, **STOP** and suggest: "tasks.md is not in valid optimus format. Run `/optimus-cycle-migrate` to fix it."

3. **Verify workspace (HARD BLOCK):** This agent modifies code. It MUST NOT run on the default/main branch.
   ```bash
   DEFAULT_BRANCH=$(git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's@^refs/remotes/origin/@@')
   CURRENT_BRANCH=$(git branch --show-current)
   ```
   - If `CURRENT_BRANCH` equals `DEFAULT_BRANCH` (or is `main`/`master`) → **STOP**:
     ```
     Cannot run cycle-impl-review-stage-3 on the default branch (<branch>).
     Switch to the task's feature branch first.
     ```

4. **Branch-task cross-validation:** After confirming the task ID (Step 0.0.1), check that the current branch matches the **Branch** column in `tasks.md` for this task:
   - Read the Branch column for the confirmed task ID
   - If Branch is `-` or empty → warn: "tasks.md shows no branch for T-XXX, but you are on `<current>`. Continue anyway?" (via `AskUser`)
   - If Branch has a value AND it does not match `CURRENT_BRANCH` → warn: "tasks.md shows branch `<expected>` for T-XXX, but you are on `<current>`. Continue on current branch, or switch?" (via `AskUser`)
   - If Branch matches `CURRENT_BRANCH` → proceed silently

### Step 0.0.1: Identify Task to Validate

**If the user specified a task ID** (e.g., "validate T-012"):
- Use the provided task ID
- Confirm with the user using `AskUser`: "I'll validate task T-012: [task title]. Correct?"

**If the user did NOT specify a task ID** (e.g., "validate the last task", or just invoked the skill):
1. **Identify the task to validate:** Scan the table for tasks with status `Em Andamento` (cycle-impl-stage-2 completed) or `Validando Impl` (re-execution). If exactly one, suggest it. If multiple, ask user which one.
2. **If no tasks with `Em Andamento` or `Validando Impl`:** Check git branch name for task ID references, then ask the user.
3. **Suggest to the user** using `AskUser`: "I identified the task to validate: T-XXX — [task title]. Is this correct, or would you like to validate a different task?"
4. **If no task can be identified**, ask the user to provide a task ID

**BLOCKING**: Do NOT proceed until the user confirms which task to validate.

### Step 0.0.2: Validate and Update Task Status

**HARD BLOCK:** This step is mandatory. Do NOT skip it.

1. Read `tasks.md` and find the row for the confirmed task ID
2. Check the **Status** column:
   - If status is `Em Andamento` → proceed (cycle-impl-stage-2 has completed)
   - If status is `Validando Impl` → proceed (re-execution of this stage)
   - If status is `Pendente` → **STOP**: "Task T-XXX is in 'Pendente'. Run cycle-spec-stage-1 and cycle-impl-stage-2 first."
   - If status is `Validando Spec` → **STOP**: "Task T-XXX is in 'Validando Spec'. Run cycle-impl-stage-2 first."
   - If status is `Revisando PR` or `**DONE**` → **STOP**: "Task T-XXX is in '<status>'. It has already moved past this stage."
3. **Check dependencies (HARD BLOCK):** Read the Depends column for this task.
   - If Depends is `-` → proceed (no dependencies)
   - For each dependency ID listed, check its Status in the table:
     - If ALL dependencies have status `**DONE**` → proceed
     - If ANY dependency is NOT `**DONE**` → **STOP**:
       ```
       Task T-XXX depends on T-YYY (status: '<status>'). T-YYY must be **DONE** first.
       ```
4. **Expanded confirmation before status change:**
   - **If status will change** (current status is NOT `Validando Impl`) AND the user did NOT specify the task ID explicitly (auto-detect):
     - Read the task's H2 detail section (`## T-XXX: Title`) from `tasks.md`
     - Present to the user via `AskUser`:
       ```
       I'm about to change task T-XXX status from '<current>' to 'Validando Impl'.

       **T-XXX: [title]**
       **Objetivo:** [objective from detail section]
       **Critérios de Aceite:**
       - [ ] [criterion 1]
       - [ ] [criterion 2]
       ...

       Confirm status change?
       ```
     - **BLOCKING:** Do NOT change status until the user confirms
   - **If re-execution** (status is already `Validando Impl`) OR the user specified the task ID explicitly:
     - Skip expanded confirmation (user already has context)
5. Update the Status column to `Validando Impl` (if not already)
6. Commit the status change immediately:
   ```bash
   git add tasks.md
   git commit -m "chore(tasks): set T-XXX status to Validando Impl"
   ```

**Why commit immediately:** If the session is interrupted or the agent crashes before any review fixes are committed, the status update would be lost. Committing now ensures the status change is persisted regardless of the review outcome.

### Step 0.1: Discover Project Structure

Before loading docs, discover the project's structure and tooling (reuse discoveries from optimus-cycle-impl-stage-2 if available):

1. **Identify stack:** Check for `go.mod`, `package.json`, `Makefile`, `Cargo.toml`, etc.
2. **Identify test commands:** Look in `Makefile`, `package.json` scripts, or CI config for lint, test, integration test, and E2E test commands.
3. **Identify project rules and AI instructions (MANDATORY):** Search for these files in order and read ALL that exist:
   - `AGENTS.md` (repo root) — primary agent instructions
   - `CLAUDE.md` (repo root) — Claude-specific rules
   - `DROIDS.md` (repo root) — Droid-specific rules
   - `.cursorrules` (repo root) — Cursor-specific rules
   - `PROJECT_RULES.md` (repo root or `docs/`) — project coding standards
   - `docs/PROJECT_RULES.md`
   - `.editorconfig` — editor formatting rules
   - `docs/coding-standards.md` or `docs/conventions.md`
   - `.github/CONTRIBUTING.md` or `CONTRIBUTING.md`
   - Linter configs: `.eslintrc*`, `biome.json`, `.golangci.yml`, `.prettierrc*`

   **If NONE of these files exist**, warn the user: "No project rules or AI instructions found. Validation will use generic best practices only. Consider creating an AGENTS.md or PROJECT_RULES.md."

   **If any are found**, they become the **source of truth** for coding standards. Every finding must reference a rule from these files when applicable. Pass relevant sections to every agent dispatched.

4. **Identify reference docs:** Look for task specs, API design, data model, and architecture docs.

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

## Phase 0.5: Static Analysis and Coverage Profiling

**MANDATORY.** Before dispatching review agents, run automated checks to collect concrete data. These results feed into agent prompts and become findings if they fail.

### Step 0.5.1: Run Static Analysis (parallel)

Run ALL applicable checks simultaneously. Capture stdout, stderr, exit code for each.

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

For checks that **pass**, note them for the Phase 3 overview.

Skip checks whose commands don't exist in the project (e.g., skip `go vet` in a pure JS project).

### Step 0.5.2: Run Tests (HARD BLOCK)

**HARD BLOCK:** ALL tests must pass before proceeding to agent dispatch. If any test fails, STOP and present the failures to the user. Do NOT continue to Phase 1 with failing tests.

The project's `Makefile` defines the standard test targets:

```bash
# Preferred: runs all test types (unit + integration + e2e, skipping non-existent)
make test-all

# If test-all does not exist, run each individually:
make test                    # Unit tests (MANDATORY — every project must have these)
make test-integration        # Integration tests (SKIP if target does not exist)
make test-e2e                # E2E tests (SKIP if target does not exist)
```

**Results:**

| Test Type | Makefile Target | If target exists | If target missing |
|-----------|----------------|-----------------|-------------------|
| Unit | `make test` | **HARD BLOCK** if fails | **HARD BLOCK** — unit tests are mandatory |
| Integration | `make test-integration` | **HARD BLOCK** if fails | SKIP (not all projects have integration tests) |
| E2E | `make test-e2e` | **HARD BLOCK** if fails | SKIP (not all projects have E2E tests) |

**If any test fails:**
1. Present the failure output (first 30 lines)
2. Ask the user via `AskUser`: "Tests are failing. Fix before continuing, or skip cycle-impl-review-stage-3?"
3. Do NOT proceed to Phase 1 until tests pass or user explicitly chooses to skip

**If all tests pass (or non-existent targets are skipped):** collect coverage data for analysis:

```bash
# Re-run unit tests with coverage profiling (if not already captured)
go test -coverprofile=coverage-unit.out ./...
# or: npm test -- --coverage
```

### Step 0.5.3: Analyze Coverage

```bash
# Overall coverage
go tool cover -func=coverage-unit.out | tail -1

# Packages with low coverage (sorted)
go tool cover -func=coverage-unit.out | grep -v "total:" | awk '{print $NF, $1}' | sort -n | head -20

# Untested functions (0% coverage)
go tool cover -func=coverage-unit.out | grep "0.0%"
```

Create findings for coverage issues:
- **HIGH**: Business logic functions with 0% coverage
- **MEDIUM**: Packages below 70% coverage
- **LOW**: Packages below 85% coverage
- Infrastructure/generated code with 0% → skip (not a finding)

### Step 0.5.4: Test Scenario Gap Analysis

Dispatch a test gap analyzer via `Task` tool (use `ring-default-ring-test-reviewer` or `worker`).

The agent receives: source files, test files, and `go tool cover -func` output.

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

HIGH priority gaps become findings in Phase 2 consolidation.

### Step 0.5.5: Collect Results

Merge all static analysis findings and coverage gap findings into the findings list.
These are presented alongside agent review findings in Phase 3 (overview) and Phase 4 (interactive resolution).

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

**BEFORE presenting the first finding:** Announce total findings count prominently: `"### Total findings to review: N"`

Process ONE finding at a time, starting from highest severity. Present ALL findings sequentially, collecting the user's decision for each. Do NOT apply any fix during this phase — only collect decisions.

For EACH finding, present with `"Finding X of N"` in the header:

### Deep Research Before Presenting (MANDATORY)

**BEFORE presenting any finding to the user, you MUST research it deeply.** This research
is done SILENTLY — do not show the research process. Present only the conclusions.

**Research checklist (ALL items, every finding):**

1. **Project patterns:** Read the affected file(s) fully, understand the patterns used, check how similar cases are handled elsewhere in the codebase
2. **Architectural decisions:** Review project rules (AGENTS.md, PROJECT_RULES.md, etc.) and architecture docs. Understand WHY the project is structured this way
3. **Existing codebase:** Search for precedent — if the codebase already does the same thing in other places, that context changes the finding's weight
4. **Current task focus:** Is this finding within the scope of the task being validated? Flag tangential findings as such
5. **User/consumer use cases:** Who consumes this code — end users, other services, internal modules? Trace impact to real user scenarios
6. **UX impact:** For user-facing changes, evaluate usability, accessibility, error messaging, and workflows
7. **API best practices:** REST conventions, error handling, idempotency, status codes, pagination, versioning, backward compatibility
8. **Engineering best practices:** SOLID principles, DRY, separation of concerns, error handling, resilience, observability, testability
9. **Language-specific best practices:** Use `WebSearch` to research idioms for the specific language (Go, TypeScript, etc.) — official style guides, linter rules, community patterns
10. **Correctness over convenience:** Always recommend the correct approach, regardless of effort

**After research, form your recommendation:** Option A MUST be the approach you believe is correct based on all the research above, backed by evidence (project patterns, best practice references, official docs).

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

**Option A MUST be your researched recommendation** — the approach you believe is correct based on the deep research above. Always prefer correctness over convenience.

For each option:

```
**Option A: [name] (RECOMMENDED)**
[Concrete steps — what to do, which files to change, what code to write]
- Why recommended: [reference to research — best practice, project pattern, official docs]
- Impact: UX / Task focus / Project focus / Engineering quality
- Effort: low / medium / high / very high
- Estimated time: < 5 min / 5-15 min / 15-60 min / 1-4h / > 4h

**Option B: [name]**
[Alternative approach]
- Impact: UX / Task focus / Project focus / Engineering quality
- Effort: low / medium / high / very high
- Estimated time: < 5 min / 5-15 min / 15-60 min / 1-4h / > 4h
```

### Ask for Decision

Use `AskUser` tool. **BLOCKING**: Do NOT advance to the next finding until the user decides.

**CRITICAL — If the user responds with a question or disagreement instead of a decision:**
- STOP immediately — do NOT continue to the next finding
- Research the user's question/concern RIGHT NOW using `WebSearch`, codebase analysis, or both
- Provide a thorough answer with evidence (links, code references, best practice citations)
- Only AFTER the user is satisfied, ask for their decision again
- This may go back and forth multiple times — that is expected and correct behavior

Internally record every decision: finding ID, chosen option (or "skip"), and rationale if provided. Do NOT apply any fix yet — all fixes are applied in Phase 5.

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

### Step 5.3: Verification Gate (HARD BLOCK)

**HARD BLOCK:** After all fixes applied, ALL tests must pass again. Run:

```bash
make lint                    # Lint — MANDATORY
make test-all                # Runs unit + integration + e2e (skips non-existent targets)
```

If `make test-all` target does not exist, fall back to running each individually:

```bash
make test                    # Unit tests — MANDATORY
make test-integration        # Integration — if target exists
make test-e2e                # E2E — if target exists
```

If ANY test or lint fails after fixes:
1. Diagnose the failure (max 3 attempts to fix per failure)
2. If unfixable after 3 attempts, revert that specific fix and ask the user
3. Do NOT proceed to Phase 6 (convergence) with failing tests

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
If `make test-e2e` target does not exist, mark as SKIP in the summary. Do NOT ask the user whether to implement E2E — that's a project-level decision, not a per-task decision.

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

## Phase 6: Convergence Loop (MANDATORY — automatic re-validation with escalating scrutiny)

After Phase 5 completes (whether fixes were applied or all findings were skipped), the validator MUST automatically re-validate. This catches both new issues exposed by fixes AND issues missed in round 1 due to session bias.

**CRITICAL — Why Fresh Sub-Agents:**

The primary failure mode of convergence loops is **false convergence**: the orchestrator re-runs analysis in the same session, with the same mental model, and declares "zero new findings" — not because there are none, but because it can't see past its own prior reasoning. Escalating scrutiny via prose ("be more skeptical") does not reliably change LLM analysis depth.

The solution: **rounds 2+ are executed by a fresh sub-agent** dispatched via `Task` tool. The sub-agent has zero context from prior rounds, reads all files from scratch, and returns findings independently. The orchestrator then deduplicates against the cumulative ledger.

**Round structure:**

| Round | Who analyzes | How |
|-------|-------------|-----|
| **1** (initial) | Orchestrator (this agent) | Phase 0.5 (static analysis) + Phase 1 (parallel agent dispatch) + Phase 2 (consolidate) — normal flow with full session context |
| **2** (mandatory) | **Fresh sub-agent** via `Task` | Sub-agent reads all changed files from scratch, dispatches its own review agents, returns findings |
| **3-5** | **Fresh sub-agent** via `Task` | Same as round 2 — only triggered if round 2+ found new findings |

**Round 2 is MANDATORY.** The "zero new findings" stop condition can only trigger starting from round 3. This guarantees at least one fresh-eyes pass after the initial analysis.

**Fresh sub-agent dispatch (rounds 2+):**

Dispatch a single sub-agent via `Task` tool (use `worker` or any available review droid). The sub-agent receives:

1. **All changed files** — full content, re-read fresh from disk (not from orchestrator's cache)
2. **Task spec** — the full task section from tasks.md
3. **Project rules and coding standards** — re-read fresh
4. **The findings ledger** — list of ALL findings from previous rounds with their resolutions (fixed/skipped/deferred), used ONLY for deduplication
5. **Analysis instructions** — the full validation domains from this skill

```
Goal: Independent post-task validation of T-XXX (convergence round X of 5)

You are a FRESH reviewer with NO prior context. Review this implementation
from scratch as if you've never seen it before.

Context:
  - Task spec: [full task content — re-read from file]
  - Changed files: [full content of each file — re-read from disk]
  - Project rules: [full content — re-read from files]
  - Test coverage data: [re-run coverage commands and include output]

Analysis scope (execute ALL of these):
  1. Code quality — architecture, patterns, SOLID, DRY, maintainability
  2. Business logic — domain correctness, edge cases, business rules
  3. Security — vulnerabilities, OWASP, input validation, secrets
  4. Test quality — coverage gaps, missing error scenarios, flaky patterns
  5. Spec compliance — verify each acceptance criterion is implemented
  6. Cross-file consistency — duplication, shared constants, imports

Previously identified findings (for DEDUP ONLY — do NOT let this bias your analysis):
  [list of findings with IDs and descriptions]

CRITICAL: Analyze INDEPENDENTLY. The previous findings list is ONLY for avoiding
duplicate reports. Do NOT skip areas just because previous rounds "already covered" them.
If you find the same issue, report it — the orchestrator will dedup.

Required output:
  For each finding: severity (CRITICAL/HIGH/MEDIUM/LOW), file, line, category,
  rule violated, description, recommendation
  If no issues found: "PASS — all validation domains clean"
```

**Orchestrator deduplication after sub-agent returns:**

1. Compare each sub-agent finding against the cumulative ledger (match by file + topic + description similarity)
2. **Genuinely new findings** → add to ledger, present to user via Phase 3-4
3. **Duplicates of already-resolved findings** → discard silently
4. **Duplicates of user-skipped findings** → discard silently (user already decided)

**Loop rules:**
- **Maximum rounds:** 5 (the initial run counts as round 1)
- **Round 2 is MANDATORY** — always dispatch a fresh sub-agent regardless of round 1 results
- **Progress indicator:** Show `"=== Re-validation round X of 5 (fresh sub-agent) ==="` at the start of each re-run
- **If new findings exist:** Present them using Phase 3 (overview) and Phase 4 (interactive resolution), apply via Phase 5 (batch apply), then loop again (next round also uses fresh sub-agent)
- **Stop conditions (any one triggers exit):**
  1. Zero new findings in the current round — **only valid from round 3 onward** (round 2 is mandatory)
  2. Round 5 completed (hard limit)
  3. User explicitly requests to stop (via AskUser response)
  
  **IMPORTANT:** LOW severity findings are NOT a reason to stop. ALL findings regardless of severity MUST be presented to the user for decision. The agent NEVER decides that LOW findings can be skipped.

**Round summary (show after each round):**

```markdown
### Round X of 5 (fresh sub-agent) — Summary
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
   - During interactive resolution (Phase 4), ask via `AskUser`: "Test for [scenario] is planned for T-XXX. I recommend [creating now / deferring] because [reason]. Do you want to anticipate this test?"
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

### Communication
- Be specific: "line 42 of file.tsx uses X, but coding standards section Y requires Z"
- Be constructive: always provide a concrete fix, not just criticism
- Be honest about effort: don't say "trivial" for something that requires refactoring multiple files
