---
description: Stage 3 of the task lifecycle. Validates that a completed task was implemented correctly: spec compliance, coding standards adherence, engineering best practices, test coverage, and production readiness. Uses parallel specialist agents for deep analysis, then presents findings interactively. Runs AFTER optimus-build finishes to validate code quality and spec compliance before the task can proceed to PR review or close.
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

### Step 1.0.1: Resolve and Validate optimus-tasks.md
**HARD BLOCK:** Find and validate optimus-tasks.md — see AGENTS.md Protocol: optimus-tasks.md Validation.

### Step 1.0.2: Verify Workspace (HARD BLOCK)
Resolve workspace — see AGENTS.md Protocol: Workspace Auto-Navigation.

### Step 1.0.2.1: Refuse Default Branch (HARD BLOCK)
Refuse to run on default branch — see AGENTS.md Protocol: Default Branch Refusal.

Defense-in-depth: even if Workspace Auto-Navigation was bypassed, this guard prevents
review state mutations (status writes, etc.) on the default branch.

### Step 1.0.3: Check optimus-tasks.md Divergence (warning)
Check optimus-tasks.md divergence — see AGENTS.md Protocol: Divergence Warning.

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
Execute session state protocol — see AGENTS.md Protocol: Session State. Use stage=`review`, status=`Validando Impl`.

**On stage completion** (after Phase 9 Re-run Guard resolves to advance): delete the session file and restore terminal title.

### Step 1.0.7.1: Set Terminal Title

**CRITICAL:** Set the terminal title so the user can identify this terminal at a glance.

**First, parse `TASK_TITLE` from optimus-tasks.md** — the title is interpolated
into the terminal title below, and parsing it lazily (after the title is set)
results in `optimus: REVIEW T-XXX — ` with an empty trailing dash:

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

Then execute the title-setter NOW. Set terminal title — see AGENTS.md Protocol: Terminal Identification. Use stage label `REVIEW`:

```bash
_optimus_set_title "optimus: REVIEW $TASK_ID — $TASK_TITLE"
```

**On stage completion or exit**, restore the title:

```bash
_optimus_set_title ""
```

### Step 1.0.8: Validate and Update Task Status

**HARD BLOCK:** This step is mandatory. Do NOT skip it.

1. Read `optimus-tasks.md` and find the row for the confirmed task ID
2. Read the task's status from state.json — see AGENTS.md Protocol: State Management.
   - If status is `Em Andamento` → proceed (build has completed)
   - If status is `Validando Impl` → proceed (re-execution of this stage)
   - If status is `Pendente` → **STOP**: "Task T-XXX is in 'Pendente'. Run plan and build first."
   - If status is `Validando Spec` → **STOP**: "Task T-XXX is in 'Validando Spec'. Run build first."
   - If status is `DONE` → **STOP**: "Task T-XXX is in 'DONE'. It has already moved past this stage."
   - If status is `Cancelado` → **STOP**: "Task T-XXX was cancelled. Cannot validate a cancelled task."
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
5. Update status to `Validando Impl` in state.json (if not already) — see AGENTS.md Protocol: State Management.
6. Invoke notification hooks (event=`status-change`) — see AGENTS.md Protocol: Notification Hooks.

### Step 1.0.9: Increment Stage Stats

Increment stage stats — see AGENTS.md Protocol: Increment Stage Stats. Use counter=`review_runs`, timestamp=`last_review`.

### Step 1.1: Discover Project Structure

Before loading docs, discover the project's structure and tooling (reuse discoveries from optimus-build if available):

1. **Identify stack:** Check for `go.mod`, `package.json`, `Makefile`, `Cargo.toml`, etc.
2. **Verify Makefile targets (HARD BLOCK):** The project MUST have a `Makefile` with `lint` and `test` targets. If either is missing, **STOP**: "Project is missing required Makefile targets (`make lint`, `make test`). Add them before running check."
3. **Identify project rules and AI instructions (MANDATORY):** Execute project rules discovery — see AGENTS.md Protocol: Project Rules Discovery.

4. **Identify reference docs:** Look for task specs, API design, data model, and architecture docs.

### Step 1.2: Load Reference Documents

Resolve TaskSpec — see AGENTS.md Protocol: TaskSpec Resolution. Also load:
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

Run ALL applicable checks simultaneously via `_optimus_quiet_run` —
see AGENTS.md Protocol: Quiet Command Execution. The helper redirects each
command's output to `.optimus/logs/` and prints only a PASS/FAIL line (plus
last 50 lines on failure), so only the failing checks consume agent context.

Run `make lint` for lint checks. Optional static analysis tools (vet, imports, format, docs) are auto-detected from the project stack.

| # | Check | Command (wrapped in `_optimus_quiet_run`) | What it detects |
|---|-------|-------------------------------------------|-----------------|
| 1 | Lint | `_optimus_quiet_run "make-lint" make lint` (or `golangci-lint run` / `npm run lint`) | Linter rule violations |
| 2 | Vet | `_optimus_quiet_run "go-vet" go vet ./...` (Go projects) | Suspicious constructs |
| 3 | Import ordering | `_optimus_quiet_run "goimports" goimports -l .` (Go projects) | Unordered/missing imports |
| 4 | Format | `_optimus_quiet_run "gofmt" gofmt -l .` (Go) or `_optimus_quiet_run "prettier" npx prettier --check .` (JS/TS) | Formatting violations |
| 5 | Doc generation | `_optimus_quiet_run "generate-docs" make generate-docs` (if target exists) | Stale documentation |

For each check that **fails**, create a finding:
- Severity: **HIGH** for lint/vet, **MEDIUM** for format/imports/docs
- Source: `[Static Analysis: <check-name>]`
- Include the relevant error lines from the last 50 already printed by
  `_optimus_quiet_run` on failure (full log at `.optimus/logs/<timestamp>-<label>-<pid>.log`).

For checks that **pass**, note them for the Phase 5 overview — only the one-line
`PASS: ...` verdict is needed.

Skip checks whose commands don't exist in the project (e.g., skip `go vet` in a pure JS project).

### Step 2.2: Run Unit Tests with Coverage (Baseline)

Unit tests should pass before proceeding to agent dispatch. This establishes
the baseline — if unit tests are already failing, review findings may be unreliable.

Run unit tests with coverage in a single pass via `make test-coverage`, wrapped
in `_optimus_quiet_run`. The helper is defined in AGENTS.md Protocol: Quiet Command Execution.
The percentage extraction is covered by AGENTS.md Protocol: Coverage Measurement.
Fallback to `make test` only if the coverage target is unavailable:

```bash
_optimus_quiet_run "make-test-coverage" make test-coverage
# Fallback if coverage target missing:
# _optimus_quiet_run "make-test" make test
```

The agent sees only the PASS/FAIL verdict plus the extracted coverage percentage
(see Protocol: Coverage Measurement for the `awk '/^total:/'` line). The full
per-package coverage lives in `.optimus/logs/` and the native coverage file.

Measure coverage — see AGENTS.md Protocol: Coverage Measurement.

**If unit tests fail:**
1. `_optimus_quiet_run` already printed the last 50 lines and the log path —
   review them in place.
2. Ask the user via `AskUser`: "Unit tests are failing. Fix before continuing, or skip check?"
3. Do NOT proceed to Phase 3 until unit tests pass or user explicitly chooses to skip

**NOTE:** Integration tests are NOT run here. They run only in Phase 10
(after re-run guard, before summary) or when the user invokes them directly.
This avoids slow test suites blocking the review loop.

### Step 2.3: Analyze Coverage

Read the coverage output file (e.g., `coverage-unit.out`, `coverage.json`, or
`.optimus/logs/<timestamp>-*-coverage-*.log` — trailing `-<pid>` is part of every
helper-produced filename). See AGENTS.md Protocol: Coverage Measurement.
Identify:
- Overall coverage percentage (already emitted by the extraction command in Step 2.2)
- Packages/files with lowest coverage (bottom 20)
- Functions/methods with 0% coverage (untested)

Do NOT parse the stdout of `_optimus_quiet_run` for this — that stream contains only
the PASS/FAIL verdict and the extracted total line.

Create findings for coverage issues (aligned with AGENTS.md Protocol: Coverage Measurement):
- **HIGH**: Unit coverage below 85% threshold, or integration coverage below 70% threshold, or business logic functions with 0% coverage
- **MEDIUM**: Coverage above threshold but with notable untested functions
- Infrastructure/generated code with 0% → skip (not a finding)

### Step 2.4: Test Scenario Gap Analysis

Dispatch a test gap analyzer via `Task` tool. Use `ring-default-ring-test-reviewer` or `ring-dev-team-qa-analyst`.

The agent receives file paths and can navigate the codebase autonomously.

```
Goal: Cross-reference implemented tests with source code to find missing scenarios.

Context:
  - Project root: <absolute path to project worktree>
  - Task spec: <TASKS_DIR>/<TaskSpec> (READ this file for acceptance criteria)
  - Changed source files: [list of file paths] (READ each file)
  - Test files: [list of test file paths] (READ each file)
  - Coverage output: [coverage command output if available]

IMPORTANT: You have access to Read, Grep, and Glob tools. USE THEM to:
  - Read files at the paths above
  - Search for existing test patterns in the project
  - Find related test files not listed above
  - Discover how similar functions are tested elsewhere in the codebase

For each public function changed/added by this task:
  - Happy path tested?
  - Error paths tested (each error return)?
  - Edge cases (nil, empty, boundary values)?
  - Validation failures?
  - Integration points (DB failure, timeout, retry)?

Additionally verify test effectiveness:
  - Do tests verify BEHAVIOR or just mock internals? Flag tests where assertions only check mock.Called()
  - Could these tests pass while the feature is actually broken? (false positive risk)
  - Are tests coupled to implementation details (private fields, internal struct layout)?
  - For each acceptance criterion in the task spec, is there a corresponding test?
  - Do integration tests use real dependencies (testcontainers/docker) or just mocks?

Report: function, existing scenarios, missing scenarios, priority (HIGH/MEDIUM/LOW)
```

HIGH priority gaps become findings in Phase 4 consolidation.

### Step 2.5: Collect Results

Merge all static analysis findings and coverage gap findings into the findings list.
These are presented alongside agent review findings in Phase 5 (overview) and Phase 6 (interactive resolution).

---

## Phase 3: Parallel Agent Dispatch

Dispatch ALL applicable agents simultaneously via `Task` tool. Each agent receives file paths and can navigate the codebase autonomously to gather context.

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
  - Project root: <absolute path to project worktree>
  - Task spec: <TASKS_DIR>/<TaskSpec> (READ this file)
  - Subtasks dir: <TASKS_DIR>/subtasks/T-XXX/ (READ all .md files if dir exists)
  - Reference docs dir: <TASKS_DIR>/ (explore for PRD, TRD, API design, data model)
  - Project rules: AGENTS.md, PROJECT_RULES.md, docs/PROJECT_RULES.md (READ all that exist)
  - Changed files: [list of file paths] (READ each file)

IMPORTANT: You have access to Read, Grep, and Glob tools. USE THEM to:
  - Read files at the paths above
  - Search the codebase for patterns similar to the code under review
  - Find how the same problem was solved elsewhere in the project
  - Discover test patterns, error handling conventions, and architectural styles
  - Explore related files not listed above when needed for context

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

Cross-cutting analysis (MANDATORY for all agents):
  1. What would break in production under load with this code?
  2. What's MISSING that should be here? (not just what's wrong)
  3. Does this code trace back to a spec requirement? Flag orphan code without spec backing
  4. How would a new developer understand this code 6 months from now?
  5. Search the codebase for how similar problems were solved — flag inconsistencies with existing patterns
```

### Special Instructions per Agent

Include per-droid quality checklists — see AGENTS.md Protocol: Per-Droid Quality Checklists.

**Spec Compliance agent** (`ring-dev-team-qa-analyst`) must additionally (beyond the protocol):
1. List every acceptance criterion from the Ring source (via `TaskSpec` column) and mark PASS/FAIL/PARTIAL
2. List every test ID and verify a corresponding test exists
3. If the task has API endpoints, verify request/response format matches API contracts
4. If the task has DB changes, verify column types/constraints match the data model

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

For EACH finding, present with `"(X/N)"` progress prefix in the header:

### Deep Research Before Presenting (MANDATORY)
Execute deep research before presenting each finding — see AGENTS.md "Common Patterns > Deep Research Before Presenting". All 12 checklist items apply.

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

**AskUser `[topic]` format:** Format: `(X/N) F#-Category`.
Example: `[topic] (8/12) F8-DeadCode`.

Use `AskUser` tool. **BLOCKING**: Do NOT advance to the next finding until the user decides.
**Every AskUser MUST include these options:**
- One option per proposed solution (Option A, Option B, Option C, etc.)
- Skip — no action
- Tell me more — if selected, STOP and answer immediately (do NOT continue to next finding)

**AskUser template (MANDATORY — follow this exact structure for every finding):**
```
1. [question] (X/N) SEVERITY — Finding title summary
[topic] (X/N) F#-Category
[option] Option A: recommended fix
[option] Option B: alternative approach
[option] Skip
[option] Tell me more
```

**HARD BLOCK — IMMEDIATE RESPONSE RULE:** If the user selects "Tell me more" or responds
with free text: **STOP IMMEDIATELY.** Do NOT continue to the next finding. Research and
answer RIGHT NOW. Only after the user is satisfied, re-present the SAME finding's options.
**NEVER defer to the end of the findings loop.**

**Anti-rationalization (excuses the agent MUST NOT use):**
- "I'll address all questions after presenting the remaining findings" — NO
- "Let me continue with the next finding and come back to this" — NO
- "I'll research this after the findings loop" — NO
- "This is noted, moving to the next finding" — NO

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

**Dispatch a test gap analyzer** via `Task` tool. Use `ring-default-ring-test-reviewer` or `ring-dev-team-qa-analyst`.

The agent receives file paths and can navigate the codebase autonomously.

```
Goal: Cross-reference task spec with implemented tests to find scenario gaps.

Context:
  - Project root: <absolute path to project worktree>
  - Task spec: <TASKS_DIR>/<TaskSpec> (READ this file for acceptance criteria and test IDs)
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

## Phase 8: Convergence Loop (Optional — Gated)

Execute the opt-in convergence loop — see AGENTS.md "Common Patterns > Protocol: Convergence Loop (Full Roster Model — Opt-In, Gated)".

**Behavioral contract for THIS phase:**
- Round 1 already ran in Phase 3. THIS phase only handles rounds 2 through 5.
- Present the **entry gate** before round 2 (`Run round 2` / `Skip convergence loop`).
- Present the **per-round gate** before rounds 3, 4, 5 (`Continue` / `Stop here`).
- If a dispatched round produces ZERO new findings, declare convergence and exit
  silently — DO NOT ask the user whether to run another round.
- Record the final loop status (`CONVERGED` / `USER_STOPPED` / `SKIPPED` /
  `HARD_LIMIT` / `DISPATCH_FAILED_ABORTED`) for the Final Summary.

**Stage-specific scope for convergence rounds 2+:**
Dispatch the **same agent roster** from Phase 3 (all agents from the Agent Roster table).
Each agent receives file paths, task spec, reference docs, and project rules (re-read fresh
from disk). Do NOT include the findings ledger in agent prompts — the orchestrator handles
dedup using strict matching (same file + same line range ±5 + same category).

Include the cross-cutting analysis instructions (same 5 items from Phase 3 prompt).

**Failure handling:** If a fresh sub-agent dispatch fails (Task tool error, ring droid
unavailable), do NOT count as zero findings. Ask the user via `AskUser` whether to
retry the round or stop (status `DISPATCH_FAILED_ABORTED` if user stops).

When the loop exits (any status), proceed to Phase 9 (Re-run Guard).

---

## Phase 9: Re-run Guard

### Step 9.1: Evaluate Re-run or Advance

Execute re-run guard — see AGENTS.md Protocol: Re-run Guard.

- If the user chooses **Re-run with clean context**: go back to Step 1.1 (Discover Project
  Structure). Skip all prior setup steps (GitHub CLI check, optimus-tasks.md validation, workspace
  resolution, task identification, session state, status validation, divergence check).
  Increment stage stats before re-starting analysis. Apply the **Re-run reset semantics**: reset `convergence_status` to `null`; reset `phase` to the first re-executed phase; overwrite `started_at`; preserve `task_id`, `task_branch`, `created_at`. See AGENTS.md Protocol: Re-run Guard.
- If the user chooses **Advance** (or 0 findings): proceed to Phase 10 (integration tests).

---

## Phase 10: Integration Tests (before push)

**After the convergence loop exits**, run integration tests. These are slow and
expensive, so they run ONCE at the end — not during the fix/convergence cycle.

If Step 7.4 measured integration coverage via `make test-integration-coverage`,
integration tests already ran — skip this phase (no-op).
Otherwise (coverage target missing, marked SKIP in Step 7.4), run quietly — see
AGENTS.md Protocol: Quiet Command Execution:

```bash
_optimus_quiet_run "make-test-integration" make test-integration   # Optional fallback — SKIP if missing
```

| Test Type | Command | If target exists | If missing |
|-----------|---------|-----------------|------------|
| Integration | `_optimus_quiet_run "make-test-integration" make test-integration` | **HARD BLOCK** if fails | SKIP |

**If integration tests fail:**
1. `_optimus_quiet_run` already printed the last 50 lines plus the log path —
   review them in place.
2. Ask via `AskUser`: "Integration tests are failing. What should I do?"
   - Fix the issue (dispatch ring droid)
   - Skip and proceed to summary (user will handle later)

**If all pass (or targets don't exist):** proceed to the Validation Summary.

---

## Phase 11: Validation Summary

```markdown
## Post-Task Validation Summary: T-XXX

### Verdict: APPROVED / APPROVED WITH CAVEATS / NEEDS REWORK

### Convergence
- Rounds dispatched (round 1 + convergence rounds): X
- Status: CONVERGED | USER_STOPPED | SKIPPED | HARD_LIMIT | DISPATCH_FAILED_ABORTED

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
- Integration tests: PASS / SKIPPED (Phase 10)

### Test Coverage
- Unit tests: XX.X% (threshold: 85%) — PASS / FAIL
- Integration tests: XX.X% (threshold: 70%) — PASS / FAIL / SKIP
- Untested functions: X (Y business logic, Z infrastructure)
```

---

## Phase 12: Push Commits (optional)
Offer to push commits — see AGENTS.md Protocol: Push Commits.

---

## Phase 13: Offer PR Creation

After the validation summary is presented and the verdict is APPROVED or APPROVED WITH CAVEATS,
offer to create a PR for the task.

### Step 13.1: Check if PR Already Exists

```bash
gh pr list --head "$(git branch --show-current)" --json number,state,url --jq '.[]'
```

- **If PR already exists (any state):** skip PR creation — inform the user: "PR #X already exists: <url>"
- **If no PR exists:** proceed to Step 13.2

### Step 13.2: Generate PR Title (Conventional Commits)

Derive the PR title from the task's **Tipo** column and title:

1. Read the Tipo for the task and map to the conventional commit prefix:
   - Feature→`feat`, Fix→`fix`, Refactor→`refactor`, Chore→`chore`, Docs→`docs`, Test→`test`
2. Use the task ID as scope
3. Use the task title as description (lowercase, imperative)

**Format:** `<type>(T-XXX): <description>`

**Example:** Task T-003 "User registration API" with Tipo "Feature" → `feat(T-003): add user registration API`

### Step 13.3: Offer to Create

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
gh pr create --title "<title>" --body "<auto-generated body>" --base "$DEFAULT_BRANCH" --assignee @me
```

The `--assignee @me` flag assigns the PR to the authenticated GitHub user automatically.

The body should include:
- Task ID and title
- Objective (from Ring source via `TaskSpec` column)
- Link to the task section in optimus-tasks.md

### Step 13.4: Confirm

If created, show: "PR #N created: <url> (assigned to you)"

**NOTE:** PR creation is optional — the user may prefer to create it manually with additional
context. The agent NEVER creates a PR without explicit user approval.

---

## Rules

### Agent Dispatch
- ALWAYS dispatch agents for: Code Quality, Business Logic, Security, QA, Cross-File Consistency, Spec Compliance
- Dispatch Frontend/Backend specialists based on task scope (Step 1.4)
- Each agent receives file paths and can navigate the codebase autonomously via Read/Grep/Glob tools
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
- Within a dispatched round, present every finding regardless of severity. Whether to run another round is gated by user prompt.

### Dry-Run Mode

Follow AGENTS.md Protocol: Dry-Run Mode. The canonical rules apply uniformly
to plan/build/review/done — see the inlined Protocol: Dry-Run Mode block below.

**Stage-3 (review) specifics:**
- The "no status change" rule means skip the status update in Step 1.0.8.
- The "no stats" rule means skip Step 1.0.9 (Increment Stage Stats).
- The "no fix application" rule means skip Phase 7 (batch apply) entirely.
- The "skip convergence rounds 2+" rule means stop after Phase 6 round 1.
- Present a summary showing: total findings, severity breakdown, estimated
  fix effort.

### Communication
- Be specific: "line 42 of file.tsx uses X, but coding standards section Y requires Z"
- Be constructive: always provide a concrete fix, not just criticism
- Be honest about effort: don't say "trivial" for something that requires refactoring multiple files
- **Re-run guard:** After the convergence loop exits, execute the Re-run Guard protocol
  (Phase 9) instead of unconditionally suggesting the next stage. The next stage is only
  suggested when the analysis produces 0 findings. See AGENTS.md Protocol: Re-run Guard.

<!-- INLINE-PROTOCOLS:START -->
## Shared Protocols (from AGENTS.md)

The following protocols are referenced by this skill. They are
extracted from the Optimus AGENTS.md to make this plugin self-contained.

### File Location

Optimus splits its files into two trees:

**Operational tree (`.optimus/`) — 100% gitignored, per-user/per-machine:**

```
.optimus/
├── config.json          # gitignored — optional overrides (tasksDir, defaultScope)
├── state.json           # gitignored — operational state (status, branch per task)
├── stats.json           # gitignored — stage execution counters per task
├── sessions/            # gitignored — session state for crash recovery
└── reports/             # gitignored — exported reports
```

**Planning tree (`<tasksDir>/`) — versioned, shared with the team:**

```
<tasksDir>/              # default: docs/pre-dev/
├── optimus-tasks.md     # versioned — structural task data (NO status, NO branch)
├── tasks/               # versioned — Ring pre-dev task specs (task_001.md, ...)
└── subtasks/            # versioned — Ring pre-dev subtask specs (T-001/, ...)
```

**Configuration** (optional) is stored in `.optimus/config.json`:

```json
{
  "tasksDir": "docs/pre-dev",
  "defaultScope": "ativa"
}
```

- **`tasksDir`** (optional): Path to the Ring pre-dev artifacts root. Default:
  `docs/pre-dev`. The import and stage agents look for `optimus-tasks.md`, `tasks/`, and
  `subtasks/` inside this directory. Can point to a path inside the project repo
  (default case) OR to a path in a separate git repo (for teams that separate task
  tracking from code).
- **`defaultScope`** (optional): Default version scope used by `report` and `quick-report`
  when the user does not specify one in the invocation. Valid values: `ativa`, `upcoming`,
  `all`, or a specific version name (must exist in the Versions table). When set, skills
  skip the "Which version scope do you want to see?" prompt. See Protocol: Default Scope
  Resolution.

Since `config.json` is gitignored, it exists ONLY when the user overrides a default.
Projects using the defaults do not need a `config.json`.

**Tasks file** is always at `<tasksDir>/optimus:tasks.md` (derived from `tasksDir`).

**Operational state** is stored in `.optimus/state.json` (gitignored):

```json
{
  "T-001": { "status": "DONE", "branch": "feat/t-001-setup-auth", "updated_at": "2025-01-15T10:30:00Z" },
  "T-003": { "status": "Em Andamento", "branch": "feat/t-003-user-registration", "updated_at": "2025-01-16T14:00:00Z" }
}
```

- Each key is a task ID. A task with no entry is `Pendente` (implicit default).
- `status`: current pipeline stage (see Valid Status Values).
- `branch`: the derived branch name, stored for quick reference (always re-derivable).
- Stage agents read and write this file — never optimus-tasks.md — for status changes.
- If state.json is lost, status can be reconstructed: task with a worktree = in progress,
  without = Pendente. The agent asks the user to confirm before proceeding.

**Stage execution stats** are stored in `.optimus/stats.json` (gitignored):

```json
{
  "T-001": { "plan_runs": 2, "review_runs": 3, "last_plan": "2025-01-15T10:30:00Z", "last_review": "2025-01-16T14:00:00Z" },
  "T-002": { "plan_runs": 1, "review_runs": 0 }
}
```

- Each key is a task ID. Values track how many times `plan` and `review` executed on the task.
- A high `plan_runs` signals unclear or problematic specs. A high `review_runs` signals
  complex review cycles or specification gaps.
- The file is created on first use by `plan` or `review`. If missing, agents treat all
  counters as 0.
- `report` reads this file to display churn metrics.

Agents resolve paths:
1. **Read `.optimus/config.json`** for `tasksDir` if it exists. Fallback: `docs/pre-dev`.
2. **Tasks file:** `${tasksDir}/optimus:tasks.md` (derived, not configurable separately).
3. **If `<tasksDir>/optimus:tasks.md` not found:** **STOP** and suggest running `import` to create one.

Everything inside `.optimus/` is gitignored. The planning tree (`<tasksDir>/optimus:tasks.md`,
`<tasksDir>/tasks/`, `<tasksDir>/subtasks/`) is versioned (structural data shared with
the team) — but the repo that versions it depends on `tasksDir`: if `tasksDir` is inside
the project repo, it is committed alongside the code; if `tasksDir` is in a separate
repo, it is committed there.


### Valid Status Values (stored in state.json)

Status lives in `.optimus/state.json`, NOT in optimus-tasks.md. A task with no entry in
state.json is implicitly `Pendente`.

| Status | Set by | Meaning |
|--------|--------|---------|
| `Pendente` | Initial (implicit) | Not started — no entry in state.json |
| `Validando Spec` | plan | Spec being validated |
| `Em Andamento` | build | Implementation in progress |
| `Validando Impl` | review | Implementation being reviewed |
| `DONE` | done | Completed |
| `Cancelado` | tasks, done | Task abandoned, will not be implemented |

**Administrative status operations** (managed by tasks, not by stage agents):
- **Reopen:** `DONE` → `Pendente` (remove entry from state.json) or `Em Andamento` (if worktree exists) — when a bug is found after close. Also accepts `Cancelado` → `Pendente` — when a cancellation decision is reversed.
- **Advance:** move forward one stage — when work was done manually outside the pipeline
- **Demote:** move backward one stage — when rework is needed after review
- **Cancel:** any non-terminal → `Cancelado` — task will not be implemented

These operations require explicit user confirmation.


### Task Spec Resolution

Every task SHOULD have a Ring pre-dev reference in the `TaskSpec` column. Tasks may be created with `TaskSpec=-` (deferred); the next `/optimus:plan` run will offer to generate or link a spec. Stage agents
(plan, build, review) resolve the full path as `<tasksDir>/<TaskSpec>` and read the
referenced file for objective, acceptance criteria, and implementation details.

The subtasks directory is derived automatically from the TaskSpec path:
- TaskSpec: `tasks/task_001.md` → Subtasks: `<tasksDir>/subtasks/T-001/`
- The `T-NNN` identifier is extracted from the task spec filename convention

Agents read objective and acceptance criteria directly from the Ring source files.
The optimus-tasks.md table only tracks structural data (dependencies, versions, priorities)
— it does NOT duplicate content from Ring.


### Format Validation

Every stage agent (1-4) MUST validate the optimus-tasks.md format before operating:
1. **First line** is `<!-- optimus:tasks-v1 -->` (format marker)
2. A `## Versions` section exists with a table containing columns: Version, Status, Description
3. All Version Status values are valid (`Ativa`, `Próxima`, `Planejada`, `Backlog`, `Concluída`)
4. Exactly one version has Status `Ativa`
5. At most one version has Status `Próxima`
6. A markdown table exists with columns: ID, Title, Tipo, Depends, Priority, Version (Estimate and TaskSpec are optional — tables without them are still valid). **Status and Branch columns are NOT expected** — they live in state.json.
7. All task IDs follow the `T-NNN` pattern
8. All Tipo values are one of: `Feature`, `Fix`, `Refactor`, `Chore`, `Docs`, `Test`
9. All Depends values are either `-` or comma-separated valid task IDs that exist as rows in the tasks table (not just matching `T-NNN` pattern — the referenced task must actually exist)
10. All Priority values are one of: `Alta`, `Media`, `Baixa`
11. All Version values reference a version name that exists in the Versions table
12. No duplicate task IDs
13. No circular dependencies in the dependency graph (e.g., T-001 → T-002 → T-001)

If the format marker is missing or validation fails, the agent must **STOP** and suggest
running `/optimus:import` to fix the format. Do NOT attempt to interpret malformed data.

14. No unescaped pipe characters (`|`) in task titles (breaks markdown table parsing)
15. **Empty table handling:** If the tasks table exists but has zero data rows (only headers),
format validation PASSES. Stage agents (1-4) MUST check for this condition immediately after
format validation and before task identification. If zero data rows: **STOP** and inform the
user: "No tasks found in optimus-tasks.md. Use `/optimus:tasks` to create a task or `/optimus:import`
to import from Ring pre-dev." Do NOT proceed to task identification with an empty table.

**NOTE:** For circular dependency detection (item 13), trace the full dependency chain for
each task. If any task appears twice in the chain, a cycle exists. Report ALL tasks involved
in the cycle so the user can fix it with `/optimus:tasks`.


### Protocol: Resolve Tasks Git Scope (summarized)

> **Summary inlined here. Full recipe at `AGENTS.md -> Protocol: Resolve Tasks Git Scope`.**

**Summary:** Resolves `TASKS_DIR` (from `.optimus/config.json` `tasksDir` key, default `docs/pre-dev`) and `TASKS_FILE` (`<tasksDir>/optimus:tasks.md`), then detects whether tasksDir lives inside the project repo (`same-repo`) or a separate git repo (`separate-repo`). Sets `TASKS_REPO_ROOT`, `TASKS_GIT_REL`, `TASKS_DEFAULT_BRANCH`, and exposes a `tasks_git()` helper that wraps `git -C "$TASKS_DIR"` in separate-repo mode. Hard guards: reject `tasksDir` starting with `-` (git-option injection), require `python3` for separate-repo path computation, validate `TASKS_DEFAULT_BRANCH` against `^[a-zA-Z0-9._/-]+$`. Skills MUST use `tasks_git` (never raw `git`) on `$TASKS_FILE`. See full recipe in AGENTS.md.

### Protocol: Resolve Main Worktree Path (summarized)

> **Summary inlined here. Full recipe at `AGENTS.md -> Protocol: Resolve Main Worktree Path`.**

**Summary:** Resolve `MAIN_WORKTREE` once via `git worktree list --porcelain | awk '/^worktree / {print $2; exit}'` with `${MAIN_WORKTREE:?…}` defensive guard. Use `${MAIN_WORKTREE}/.optimus/...` for ALL `.optimus/` paths (gitignored, so doesn't propagate across linked worktrees). See full recipe in AGENTS.md.

### Deep Research Before Presenting (MANDATORY for cycle review skills)
Applies to: plan, review, pr-check, coderabbit-review

**BEFORE presenting any finding to the user, the agent MUST research it deeply.** This
research is done SILENTLY — do not show the research process. Present only the conclusions.

**Research checklist (ALL items, every finding):**

1. **Project patterns:** Read the affected file(s) fully. Check how similar cases are handled
   elsewhere in the codebase. Identify existing conventions the finding might violate or follow.
2. **Architectural decisions:** Review project rules (AGENTS.md, PROJECT_RULES.md, etc.) and
   architecture docs (TRD, ADRs). Understand WHY the project is structured this way before
   suggesting changes.
3. **Existing codebase:** Search for precedent. If the codebase already does the same thing
   in 10 other places without issue, that context changes the finding's weight.
4. **Current task focus:** Is this finding within the scope of the task being worked on?
   Tangential findings should be flagged as such (not dismissed, but contextualized).
5. **User/consumer use cases:** Who consumes this code — end users, other services, internal
   modules? How does the finding affect them? Trace the impact to real user scenarios.
6. **UX impact:** For user-facing changes, evaluate usability, accessibility, error messaging,
   and workflows. Would the user notice? Would it block their work?
7. **API best practices:** For API changes, check REST conventions, error handling patterns,
   idempotency, status codes, pagination, versioning, and backward compatibility.
8. **Engineering best practices:** SOLID principles, DRY, separation of concerns, error
   handling, resilience patterns, observability, testability.
9. **Language-specific best practices:** Use `WebSearch` to research idioms and conventions
   for the specific language (Go, TypeScript, Python, etc.). Check official style guides,
   common linter rules, and community-accepted patterns.
10. **Correctness over convenience:** Always recommend the correct approach, regardless of
    effort. The easy option may be presented as an alternative, but Option A must be what
    the agent believes is right based on all the research above.
11. **Production resilience:** Would this code survive production conditions? Consider:
    timeouts on external calls, retry with backoff, circuit breakers, graceful degradation,
    resource cleanup (connections, handles, goroutines), graceful shutdown, and behavior
    under load (N+1 queries, unbounded queries, connection pool exhaustion).
12. **Data integrity and privacy:** Are transaction boundaries correct? Could partial writes
    occur? Is PII properly handled (not logged, masked in responses)? LGPD/GDPR compliance?

**After research, form the recommendation:** Option A MUST be the approach the agent
believes is correct based on the research. It must be backed by evidence (project patterns,
best practice references, official documentation), not just a generic suggestion.


### Finding Option Format (MANDATORY for cycle review skills)

Every finding must present 2-3 options with this structure:

```
**Option A: [name] (RECOMMENDED)**
[Concrete steps — what to do, which files to change, what code to write]
- Why recommended: [reference to research — best practice, project pattern, official docs]
- Impact: [UX / Task focus / Project focus / Engineering quality]
- Effort: [low / medium / high / very high]
- Estimated time: [< 5 min / 5-15 min / 15-60 min / 1-4h / > 4h]

**Option B: [name]**
[Alternative approach]
- Impact: [UX / Task focus / Project focus / Engineering quality]
- Effort: [low / medium / high / very high]
- Estimated time: [< 5 min / 5-15 min / 15-60 min / 1-4h / > 4h]
```

**Effort scale:**
- **Low:** Localized change, single file, no tests needed
- **Medium:** Multiple files, straightforward, may need test updates
- **High:** Significant refactoring, new tests, multiple modules affected
- **Very high:** Architectural change, many files, extensive testing, risk of regressions


### Finding Presentation (Unified Model)
All cycle review skills follow this pattern:
1. Collect findings from agents/tools
2. Consolidate and deduplicate
3. **Group same-nature findings** — after deduplication, identify findings that share the
   same root cause or fix pattern (e.g., "missing error handling" in 5 handlers, "inconsistent
   import path" in 4 files). If 2+ findings are of the same nature, merge them into a **single
   grouped entry** listing all affected files/locations. Each group counts as ONE item in the
   `"(X/N)"` sequence. The user makes ONE decision for the entire group.
4. Announce total findings count: `"### Total findings to review: N"` (where N reflects
   grouped entries — a group of 5 same-nature findings counts as 1)
5. Present overview table with severity counts
6. **Deep research BEFORE presenting each finding** (see research checklist below)
7. Walk through findings ONE AT A TIME with `"(X/N)"` progress prefix in the header, ordered by severity
   (CRITICAL first, then HIGH, MEDIUM, LOW). **ALL findings MUST be presented regardless of
   severity** — the agent NEVER skips, filters, or auto-resolves any finding. The decision to
   fix or skip is ALWAYS the user's. For grouped entries, list all affected files/locations
   within the single presentation.
8. For each finding: present research-backed analysis + options, collect decision via AskUser.
   **Every AskUser for a finding decision MUST include these options:**
   - One option per proposed solution (Option A, Option B, Option C, etc.)
   - Skip — no action
   - Tell me more — if selected, STOP and answer immediately (do NOT continue to next finding)

   **AskUser template (MANDATORY — follow this exact structure for every finding):**
   ```
   1. [question] (X/N) SEVERITY — Finding title summary
   [topic] (X/N) F#-Category
   [option] Option A: recommended fix
   [option] Option B: alternative approach
   [option] Skip
   [option] Tell me more
   ```

   **Scope of the structured AskUser template:**

   The `[topic]/[option]` structured template applies ONLY to **AskUser calls that present
   findings/decisions inside cycle review skills** (plan, build, review, pr-check,
   deep-review, deep-doc-review, coderabbit-review). Each finding presentation must use
   the template so the user gets consistent UX and the test suite can verify the contract.

   Other AskUser calls — status confirmations, scope choosers, file-presence prompts,
   admin operations like task creation/cancellation, resume reset confirmations, etc. —
   MAY use prose. Authors should still aim for clarity and explicit option labels, but
   the structured template is not required outside finding loops.

   This scope is enforced by `TestStructuredAskUserScope` in `scripts/test_skill_consistency.py`.

9. **HARD BLOCK — IMMEDIATE RESPONSE RULE — If the user selects "Tell me more" OR responds
   with free text (a question, disagreement, or request for clarification):**
   **STOP IMMEDIATELY.** Do NOT continue to the next finding. Do NOT batch the response.
   Research the user's concern RIGHT NOW using `WebSearch`, codebase analysis, or both.
   Provide a thorough answer with evidence (links, code references, best practice citations).
   Only AFTER the user is satisfied, re-present the SAME finding's options and ask for
   their decision again. This may go back and forth multiple times — that is expected.
   **NEVER defer the response to the end of the findings loop.**

   **Anti-rationalization (excuses the agent MUST NOT use to skip immediate response):**
   - "I'll address all questions after presenting the remaining findings" — NO
   - "Let me continue with the next finding and come back to this" — NO
   - "I'll research this after the findings loop" — NO
   - "This is noted, moving to the next finding" — NO
10. After ALL N decisions collected: apply ALL approved fixes (see below)
11. Run verification (see Verification Timing below)
12. Present final summary


### Fix Implementation (Complexity-Based Dispatch)

Fixes are classified by complexity. **Simple fixes** are applied directly by the
orchestrator. **Complex fixes** (or fixes whose complexity cannot be determined) are
delegated to specialist ring droids.

#### Complexity Classification

For each approved fix, assess complexity BEFORE applying:

**Simple fix (apply directly):**
- The review agent already provided the exact code change needed
- Single file, localized change (few lines)
- Obvious resolution: typo, missing error check, wrong variable name, missing nil guard,
  import fix, formatting, adding a log line, renaming, removing dead code
- No new logic, no architectural impact, no new test scenarios needed

**Complex fix (dispatch ring droid):**
- Multiple files affected
- Requires understanding broader codebase context or architectural decisions
- New functionality, significant refactoring, or new integration points
- Requires new test scenarios (not just updating existing ones)
- Security-sensitive changes (auth, crypto, input validation)
- Database schema, API contract, or config changes
- The orchestrator is unsure how to fix it

**When in doubt → dispatch ring droid.** If you cannot confidently classify a fix as
simple, treat it as complex.

#### Direct Fix (simple findings)

The orchestrator applies the fix directly using Edit/MultiEdit tools. After applying:
1. Run unit tests to verify no regression
2. If tests fail, revert and escalate to ring droid dispatch

#### Ring Droid Dispatch (complex findings)

**Code fixes** → dispatch ring backend/frontend/QA droids with **TDD cycle** (RED-GREEN-REFACTOR):
- `ring-dev-team-backend-engineer-golang` (Go), `ring-dev-team-backend-engineer-typescript` (TS),
  `ring-dev-team-frontend-engineer` (React/Next.js), `ring-dev-team-qa-analyst` (tests)

**Documentation fixes** → dispatch ring documentation droids **without TDD** (no tests for docs):
- `ring-tw-team-functional-writer` (guides), `ring-tw-team-api-writer` (API docs),
  `ring-tw-team-docs-reviewer` (quality fixes)

**Ring droids are REQUIRED for complex fixes** — there is no alternative dispatch mechanism. If the
required droids are not installed and a complex fix is needed, the skill MUST stop and
inform the user which droids need to be installed.


### Protocol: Active Version Guard

**Referenced by:** all stage agents (1-4)

After the task ID is confirmed and dependencies are validated, check if the task belongs
to the `Ativa` version. If not, present options before proceeding.

1. Read the task's **Version** column from `optimus-tasks.md`
2. Read the **Versions** table and find the version with Status `Ativa`
   - **If no version has Status `Ativa`** → **STOP**: "No active version found in the Versions table. Run `/optimus:tasks` to set a version as Ativa before proceeding."
3. **If the task's version matches the `Ativa` version** → proceed silently
4. **If the task's version does NOT match the `Ativa` version** → present via `AskUser`:
   ```
   Task T-XXX is in version '<task_version>' (<version_status>),
   but the active version is '<active_version>'.
   To execute this task, it must be moved to the active version first.
   ```
   Options:
   - **Move to active version and continue** — updates the Version column to the active version, commits, and proceeds
   - **Cancel** — stops execution

5. **If "Move to active version and continue":**
   - Update the task's Version column in `optimus-tasks.md` to the `Ativa` version name
   - Commit using `tasks_git` so the change lands in the correct repo (same-repo or
     separate-repo, as resolved by Protocol: Resolve Tasks Git Scope):
     ```bash
     tasks_git add "$TASKS_GIT_REL"
     COMMIT_MSG_FILE=$(mktemp -t optimus.XXXXXX) || { echo "ERROR: mktemp failed" >&2; exit 1; }
     chmod 600 "$COMMIT_MSG_FILE"
     printf '%s' "chore(tasks): move T-XXX to active version <active_version>" > "$COMMIT_MSG_FILE"
     tasks_git commit -F "$COMMIT_MSG_FILE"
     rm -f "$COMMIT_MSG_FILE"
     ```
   - Proceed with the stage

6. **If "Cancel":** **STOP** — do not proceed with the stage

Skills reference this as: "Check active version guard — see AGENTS.md Protocol: Active Version Guard."


### Protocol: All-Dependencies-Cancelled Resolution

**Referenced by:** plan, build, review, done, batch

When all dependencies of a task are status `Cancelado`, emit a multi-option resolution
message AFTER the per-dependency status check (i.e., after detecting that every dep is
`Cancelado`, before the per-dep error-and-exit). The check supplements the per-dep loop;
it does not replace it.

**Variable contract:** the caller's dep-check loop populates an array `DEP_STATUSES`
with one status string per dependency (the same status read from `state.json` for each
dep ID listed in the Depends column). If the existing skill code uses a different
variable name, adapt the recipe below to match — the contract is "an iterable of
dependency status strings".

**Bash recipe:**

```bash
# Assumes DEP_STATUSES is an array of dependency status strings,
# already populated by the caller's dep-check loop.
ALL_CANCELLED=true
for dep_status in "${DEP_STATUSES[@]}"; do
  if [ "$dep_status" != "Cancelado" ]; then
    ALL_CANCELLED=false
    break
  fi
done

if [ "$ALL_CANCELLED" = true ] && [ "${#DEP_STATUSES[@]}" -gt 0 ]; then
  echo "All dependencies of $TASK_ID are cancelled. To unblock:" >&2
  echo "  (a) remove all dependencies: /optimus:tasks edit $TASK_ID" >&2
  echo "  (b) replace with alternative task IDs: /optimus:tasks edit $TASK_ID" >&2
  echo "  (c) cancel $TASK_ID: /optimus:tasks cancel $TASK_ID" >&2
  exit 1
fi
# Per-dep message follows here (existing logic).
```

Skills reference this as: "Check all-deps-cancelled — see AGENTS.md Protocol: All-Dependencies-Cancelled Resolution."


### Protocol: Convergence Loop (Full Roster Model — Opt-In, Gated) (summarized)

> **Summary inlined here. Full recipe at `AGENTS.md -> Protocol: Convergence Loop (Full Roster Model — Opt-In, Gated)`.**

**Summary:** Multi-round review pattern for plan, build, review, pr-check, coderabbit-review, deep-review, deep-doc-review. Round 1 is mandatory (the skill's primary dispatch). Rounds 2-5 are gated behind explicit `AskUser` prompts (entry gate before round 2, per-round gate before 3/4/5). Each gated round dispatches the SAME droid roster as round 1 in parallel via `Task` tool with zero prior context — agents read files fresh from disk. Convergence detection (zero new findings, strict `same file + ±5 lines + same category` matching) exits silently with status `CONVERGED` — never asks for another round. Hard limit at round 5. Exit statuses: `CONVERGED`, `USER_STOPPED`, `SKIPPED`, `HARD_LIMIT`, `DISPATCH_FAILED_ABORTED` (build has a single-slot carve-out). See full recipe in AGENTS.md.

### Protocol: Coverage Measurement

**Referenced by:** review, pr-check, coderabbit-review, deep-review, build

Measure test coverage using Makefile targets with stack-specific fallbacks.

**Run coverage quietly.** Coverage commands are the single biggest source of
verbose output (N packages × per-file coverage lines). Wrap them with
`_optimus_quiet_run` (see Protocol: Quiet Command Execution) so the full output
lands on disk and only a PASS/FAIL line reaches the agent. Then read only the
"total" summary line to extract the percentage.

**Unit coverage command resolution order:**
1. `make test-coverage` (if Makefile target exists), run via `_optimus_quiet_run`
2. Stack-specific fallback:
   - Go: `go test -coverprofile=coverage-unit.out ./...` (wrapped) then `go tool cover -func=coverage-unit.out`
   - Node: `npm test -- --coverage` (wrapped)
   - Python: `pytest --cov=. --cov-report=term` (wrapped)

If no unit coverage command is available, mark as **SKIP** — do not fail the verification.

**Integration coverage command resolution order:**
1. `make test-integration-coverage` (if Makefile target exists), run via `_optimus_quiet_run`
2. Stack-specific fallback:
   - Go: `go test -tags=integration -coverprofile=coverage-integration.out ./...` (wrapped) then `go tool cover -func=coverage-integration.out`
   - Node: `npm run test:integration -- --coverage` (wrapped)
   - Python: `pytest -m integration --cov=. --cov-report=term` (wrapped)

If no integration coverage command is available, mark as **SKIP** — do not fail the verification.

**Extracting the percentage (agent-visible output):** after the wrapped run, emit
only the total line. Examples:

```bash
# Go
_optimus_quiet_run "make-test-coverage" make test-coverage
if [ -f coverage-unit.out ]; then
  go tool cover -func=coverage-unit.out | awk '/^total:/ {print "Unit coverage: " $NF}'
fi

# Node (Istanbul JSON/text-summary)
_optimus_quiet_run "npm-test-coverage" npm test -- --coverage
if [ -f coverage/coverage-summary.json ]; then
  jq -r '.total.lines.pct | "Unit coverage: \(.)%"' coverage/coverage-summary.json
fi

# Python (pytest-cov)
_optimus_quiet_run "pytest-cov" pytest --cov=. --cov-report=term --cov-report=json:coverage.json
if [ -f coverage.json ]; then
  jq -r '.totals.percent_covered_display | "Unit coverage: \(.)%"' coverage.json
fi
```

The agent sees ~2 lines total (PASS verdict + "Unit coverage: 87.4%"). The full
per-file breakdown stays in `.optimus/logs/` and in the native coverage files.

**Thresholds:**

| Test Type | Threshold | Verdict if Below |
|-----------|-----------|-----------------|
| Unit tests | 85% | NEEDS_FIX / HIGH finding |
| Integration tests | 70% | NEEDS_FIX / HIGH finding |

**Coverage gap analysis:** When scanning for untested functions/methods (0% coverage),
read the coverage output file (not the agent turn stdout) — either the native
`coverage-*.out` / `coverage-summary.json` / `coverage.json` file, or the
`.optimus/logs/<timestamp>-*-coverage-*.log` file produced by `_optimus_quiet_run`
(the trailing `-<pid>` segment is part of every helper-produced log filename).
Flag business-logic functions with 0% as HIGH, infrastructure/generated code with
0% as SKIP.

Skills reference this as: "Measure coverage — see AGENTS.md Protocol: Coverage Measurement."


### Protocol: Default Branch Refusal (HARD BLOCK)

**Referenced by:** build, review, done

**Why:** Workspace Auto-Navigation is the primary safeguard, but it can be bypassed
in edge cases (user cancels the AskUser prompt, silent failure, future skill that
forgets to invoke the protocol). A second, unconditional refusal at the start of any
mutating stage prevents accidental commits, worktree removals, or status writes on
the default branch.

```bash
DEFAULT_BRANCH=$(git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's@^refs/remotes/origin/@@')
if [ -z "$DEFAULT_BRANCH" ]; then
  if git show-ref --verify refs/remotes/origin/main >/dev/null 2>&1; then
    DEFAULT_BRANCH="main"
  elif git show-ref --verify refs/remotes/origin/master >/dev/null 2>&1; then
    DEFAULT_BRANCH="master"
  fi
fi
CURRENT=$(git branch --show-current 2>/dev/null)
if [ -n "$DEFAULT_BRANCH" ] && [ "$CURRENT" = "$DEFAULT_BRANCH" ]; then
  echo "ERROR: refusing to run /optimus-<stage> on default branch '$CURRENT'." >&2
  echo "       Switch to the task's feature branch (Workspace Auto-Navigation should have handled this)." >&2
  exit 1
fi
```

**Where to invoke:** immediately after Workspace Auto-Navigation completes, before
the skill performs any state.json write, git commit, git worktree mutation, or
status transition.

Skills reference this as: "Refuse to run on default branch (HARD BLOCK) — see AGENTS.md Protocol: Default Branch Refusal."


### Protocol: Divergence Warning

**Referenced by:** all stage agents (1-4)

Since status and branch data live in state.json (gitignored), optimus-tasks.md rarely changes
on feature branches. This protocol detects the uncommon case where optimus-tasks.md WAS modified
(e.g., Active Version Guard moved a task). It uses `tasks_git` so it works in both
same-repo and separate-repo scopes.

**Prerequisite:** Protocol: Resolve Tasks Git Scope must have been executed so
`TASKS_FILE`, `TASKS_GIT_REL`, `TASKS_GIT_SCOPE`, `TASKS_DEFAULT_BRANCH`, and
`tasks_git` are defined.

```bash
# Requires Protocol: Resolve Main Worktree Path to have run first
# (or resolve inline; see that protocol).
MAIN_WORKTREE="$(git worktree list --porcelain 2>/dev/null | awk '/^worktree / {print $2; exit}')"
MAIN_WORKTREE="${MAIN_WORKTREE:?MAIN_WORKTREE not resolved — not in a git repository}"
if [ -z "$TASKS_DEFAULT_BRANCH" ]; then
  echo "WARNING: Cannot determine default branch for tasks repo. Skipping divergence check."
  # Skip — this is a warning, not a HARD BLOCK
else
  # Throttle fetch: only re-fetch if the cached timestamp is older than 5 minutes.
  # Each stage skill would otherwise pay ~2s network latency per invocation.
  # The cache lives in the PROJECT repo's .optimus/ (always present, gitignored).
  FETCH_MARKER="${MAIN_WORKTREE}/.optimus/.last-tasks-fetch"
  NOW_EPOCH=$(date +%s)
  SHOULD_FETCH=1
  if [ -f "$FETCH_MARKER" ]; then
    LAST_EPOCH=$(cat "$FETCH_MARKER" 2>/dev/null || echo 0)
    # Defense-in-depth: ensure marker contents are numeric before arithmetic.
    # A corrupted/manually-edited marker file would otherwise crash the
    # `$((NOW_EPOCH - LAST_EPOCH))` expression under `set -euo pipefail`.
    [[ "$LAST_EPOCH" =~ ^[0-9]+$ ]] || LAST_EPOCH=0
    if [ -n "$LAST_EPOCH" ] && [ "$((NOW_EPOCH - LAST_EPOCH))" -lt 300 ]; then
      SHOULD_FETCH=0
    fi
  fi
  if [ "$SHOULD_FETCH" = "1" ]; then
    if tasks_git fetch origin "$TASKS_DEFAULT_BRANCH" --quiet 2>/dev/null; then
      mkdir -p "${MAIN_WORKTREE}/.optimus"
      printf '%s' "$NOW_EPOCH" > "$FETCH_MARKER"
    else
      echo "WARNING: Could not fetch from origin. Divergence check may use stale data."
    fi
  fi
  tasks_git diff "origin/$TASKS_DEFAULT_BRANCH" -- "$TASKS_GIT_REL" 2>/dev/null | head -20
fi
```

- If diff output is non-empty → warn via `AskUser`:
  ```
  optimus-tasks.md has diverged between your branch and <default_branch>.
  This may cause merge conflicts when the PR is merged.
  ```
  Options:
  - **Sync now** — run `tasks_git merge origin/<default_branch>` to incorporate changes
  - **Continue without syncing** — I'll handle conflicts later
- If diff output is empty → proceed silently (files are in sync)
- **NOTE:** This is a warning, not a HARD BLOCK. The user may choose to continue.
- **NOTE:** In separate-repo scope, "diverged" means the tasks repo branches diverge —
  not the project code branches.

Skills reference this as: "Check optimus-tasks.md divergence — see AGENTS.md Protocol: Divergence Warning."


## Protocol: Dry-Run Mode

**Referenced by:** plan, build, review, done (all stage agents 1-4).

All stage agents support **dry-run mode**. When the user includes "dry-run" or
"preview" in their invocation (e.g., "dry-run spec T-003", "preview review T-012"),
the agent MUST:

1. **Run all analysis/validation phases normally** — agent dispatch, findings, etc.
2. **Do NOT change task status** — skip the status update step in state.json.
3. **Do NOT commit or push anything** — no git operations that modify state.
4. **Do NOT create workspaces** — skip branch/worktree creation (stage-1 only).
5. **Do NOT apply fixes** — skip batch-apply phases.
6. **Do NOT increment stage stats** — skip the Increment Stage Stats protocol.
7. **Do NOT write session files** — session state is for crash recovery of real
   executions, not previews.
8. **Skip convergence rounds 2+** — round 1 (primary review pass) is sufficient
   for preview; do NOT enter the convergence loop.
9. **Present results as informational** — phrase the summary as "what would happen"
   without implying any side effects occurred.

Stage agents may add stage-specific dry-run notes (e.g., which phase numbers
to skip), but MUST NOT relax any of the rules above. The point of dry-run is
to give the user a reliable preview with zero state mutation.


### Protocol: GitHub CLI Check (HARD BLOCK)

**Referenced by:** all stage agents (1-4), tasks, batch

```bash
gh auth status 2>/dev/null
```

If this command fails (exit code != 0), **STOP** immediately:
```
GitHub CLI (gh) is not authenticated. Run `gh auth login` to authenticate before proceeding.
```


### Protocol: Increment Stage Stats

**Referenced by:** plan, review

After the status change in state.json (and BEFORE any analysis work begins), increment
the execution counter for the current stage in `.optimus/stats.json`. This tracks how many
times each stage ran on each task — useful for spotting spec churn and review cycles.

**NOTE:** Only increment when NOT in dry-run mode.

1. Read `.optimus/stats.json`. If the file does not exist, start with an empty object `{}`.
   If the file exists but is corrupted, reset it:
   ```bash
   # Requires Protocol: Resolve Main Worktree Path to have run first
   # (or resolve inline; see that protocol).
   MAIN_WORKTREE="$(git worktree list --porcelain 2>/dev/null | awk '/^worktree / {print $2; exit}')"
   MAIN_WORKTREE="${MAIN_WORKTREE:?MAIN_WORKTREE not resolved — not in a git repository}"
   STATS_FILE="${MAIN_WORKTREE}/.optimus/stats.json"
   if [ -f "$STATS_FILE" ] && ! jq empty "$STATS_FILE" 2>/dev/null; then
     echo "WARNING: stats.json is corrupted. Resetting counters."
     echo '{}' > "$STATS_FILE"
   fi
   ```
2. If the task ID key does not exist, initialize it:
   ```json
   { "plan_runs": 0, "review_runs": 0 }
   ```
3. Increment the appropriate counter (`plan_runs` for plan, `review_runs` for review).
4. Set the timestamp field (`last_plan` or `last_review`) to the current UTC ISO 8601 time.
5. Write the updated JSON back to `.optimus/stats.json` (pretty-printed, sorted keys).

**NOTE:** stats.json is gitignored — no commit needed.

Skills reference this as: "Increment stage stats — see AGENTS.md Protocol: Increment Stage Stats."


### Protocol: Notification Hooks

**Referenced by:** all stage agents (1-4), tasks

After writing a status change to state.json, invoke notification hooks if present.

**IMPORTANT — Capture timing:** Read the current status from state.json and store it as
`OLD_STATUS` BEFORE writing the new status. The sequence is:
1. Read current status (with guard for missing/empty state.json):
   ```bash
   if [ -f "$STATE_FILE" ]; then
     OLD_STATUS=$(jq -r --arg id "$TASK_ID" '.[$id].status // "Pendente"' "$STATE_FILE" 2>/dev/null)
     [ -z "$OLD_STATUS" ] && OLD_STATUS="Pendente"
   else
     OLD_STATUS="Pendente"
   fi
   ```
2. Write new status to state.json
3. Invoke hooks with `OLD_STATUS` and new status

**IMPORTANT:** Always quote all arguments and sanitize user-derived values to prevent
shell injection. Hook scripts MUST NOT pass their arguments to `eval` or shell
interpretation — treat all arguments as untrusted data.

```bash
# Sanitize: allow only safe characters. Does NOT allow `.` or `/` (which would
# enable path-traversal if hook args flow into file paths).
_optimus_sanitize() { printf '%s' "$1" | tr -cd '[:alnum:][:space:]-_:'; }

# Resolve HOOKS_FILE with an explicit if-elif-else (instead of the fragile
# `test && echo || (test && echo)` pattern).
if [ -f ./tasks-hooks.sh ]; then
  HOOKS_FILE="./tasks-hooks.sh"
elif [ -f ./docs/tasks-hooks.sh ]; then
  HOOKS_FILE="./docs/tasks-hooks.sh"
else
  HOOKS_FILE=""
fi

if [ -n "$HOOKS_FILE" ] && [ -x "$HOOKS_FILE" ]; then
  "$HOOKS_FILE" "$(_optimus_sanitize "$event")" "$(_optimus_sanitize "$task_id")" "$(_optimus_sanitize "$old_status")" "$(_optimus_sanitize "$new_status")" 2>/dev/null &
fi
```

Events and their parameter signatures:

| Event | Parameters | Description |
|-------|-----------|-------------|
| `status-change` | `event task_id old_status new_status` | Any status transition |
| `task-done` | `event task_id old_status "DONE"` | Task marked as done |
| `task-cancelled` | `event task_id old_status "Cancelado"` | Task cancelled |
| `task-blocked` | `event task_id current_status reason` | Dependency check failed (4 args — includes reason) |

When a dependency check fails (provide defaults so hook payload is never malformed):
```bash
: "${dep_id:=unknown}"
: "${dep_status:=unknown}"
if [ -n "$HOOKS_FILE" ] && [ -x "$HOOKS_FILE" ]; then
  "$HOOKS_FILE" "task-blocked" "$(_optimus_sanitize "$task_id")" "$(_optimus_sanitize "$current_status")" "$(_optimus_sanitize "blocked by $dep_id ($dep_status)")" 2>/dev/null &
fi
```

Hooks run in background (`&`) and their failure does NOT block the pipeline.
If `tasks-hooks.sh` does not exist, hooks are silently skipped.

Skills reference this as: "Invoke notification hooks — see AGENTS.md Protocol: Notification Hooks."


### Protocol: PR Title Validation

**Referenced by:** stages 2-4

Check if a PR exists for the current branch:
```bash
gh pr view --json number,title --jq '{number, title}' 2>/dev/null
```

If a PR exists, validate its title follows **Conventional Commits 1.0.0**:
- Regex: `^(feat|fix|refactor|chore|docs|test|build|ci|style|perf)(\([a-zA-Z0-9_\-]+\))?!?: .+$`
- Cross-check the type against the task's **Tipo** column (Feature→`feat`, Fix→`fix`, Refactor→`refactor`, Chore→`chore`, Docs→`docs`, Test→`test`)
- **If title is invalid:** warn via `AskUser`: "PR #N title `<current>` does not follow Conventional Commits. Suggested: `<corrected>`. Fix now with `gh pr edit <number> --title \"<corrected>\"`?"
- **If title is valid:** proceed silently
- If no PR exists, skip.

Skills reference this as: "Validate PR title — see AGENTS.md Protocol: PR Title Validation."


### Protocol: Per-Droid Quality Checklists

**Referenced by:** review, pr-check, deep-review, coderabbit-review, plan, build

Each droid type has specific dimensions it MUST verify beyond its core domain. Skills
that dispatch review droids MUST include the applicable checklists in agent prompts.

**Code Quality agent** (`ring-default-code-reviewer`) must additionally verify:
- Resilience: external calls have timeout, retry with backoff, circuit breaker where appropriate
- Resource lifecycle: all opened connections/handles are closed (defer, cleanup, graceful shutdown)
- Concurrency: shared state has proper synchronization, no goroutine leaks, no deadlock risk
- Performance: no N+1 queries, no unbounded queries, indexes exist for query patterns, no hot-path allocations
- Configuration: no hardcoded values that should be environment-configurable, safe defaults
- Cognitive complexity: functions with >3 nesting levels or >30 lines flagged for decomposition
- Error handling: errors wrapped with context, consistent with codebase error patterns
- Domain purity: no infrastructure concerns in domain layer, dependency direction correct
- Resource leaks: DB connections, HTTP clients, file handles, channels properly closed

**Business Logic agent** (`ring-default-business-logic-reviewer`) must additionally verify:
- Spec traceability: each code path maps to a spec requirement (flag orphan logic with no spec backing)
- Data integrity: transaction boundaries correct, partial writes impossible, rollback defined
- Backward compatibility: existing consumers/contracts not broken by this change
- API semantics: correct HTTP status codes, idempotent operations marked as such, pagination consistent
- Domain edge cases: what happens with zero, negative, maximum, duplicate, concurrent values?
- Business rule completeness: all business rules from spec have implementation AND test

**Security agent** (`ring-default-security-reviewer`) must additionally verify:
- Data privacy: PII not logged, sensitive fields masked in responses, LGPD/GDPR compliance
- Error responses: no internal details leaked (stack traces, DB schemas, internal paths, SQL)
- Rate limiting: high-throughput or public endpoints have rate limiting consideration
- Input validation: happens at the right layer (not just client-side), consistent with codebase
- Secrets: no hardcoded credentials, tokens, API keys in code or config files
- Auth propagation: authentication context properly propagated through the call chain

**Test Quality agent** (`ring-default-ring-test-reviewer`) must additionally verify:
- Test effectiveness: do tests verify BEHAVIOR or just mock internals? Flag tests where assertions only check mock.Called() without verifying output/state
- False positive risk: could these tests pass while the feature is actually broken?
- Test coupling: are tests coupled to implementation details (private fields, internal struct layout)?
- Spec traceability: for each acceptance criterion in the task spec, is there a test?
- Integration tests: do they use real dependencies (testcontainers/docker) or just mocks?
- Test isolation: can tests run in parallel without interference? Shared state between tests?
- Error scenario completeness: each error return path has a corresponding test?
- Boundary values: min, max, zero, empty, nil, negative tested where applicable?

**Nil/Null Safety agent** (`ring-default-ring-nil-safety-reviewer`) must additionally verify:
- Resource cleanup: nil checks before Close/Release calls
- Channel safety: sends to nil/closed channels
- Map safety: reads/writes to nil maps
- Slice safety: index bounds after filtering/transforming

**Ripple Effects agent** (`ring-default-ring-consequences-reviewer`) must additionally verify:
- Values duplicated between files that should be a shared constant
- Imports follow the project's layer architecture (no circular deps, no backwards imports)
- New code follows the same patterns as existing code in the same domain
- Backward compatibility: does this change break any existing consumer or API contract?
- Configuration drift: new defaults reasonable? existing config overrides still valid?
- Migration path: if breaking change, is migration strategy documented?
- Shared state: new global/package-level state that could cause issues across modules?
- Event/message contracts: changes to event payloads affect downstream consumers?

**Dead Code agent** (`ring-default-ring-dead-code-reviewer`) must additionally verify:
- Dead code: unused imports, unreachable branches, commented-out code
- Zombie test infrastructure: test helpers, fixtures, mocks no longer used by any test
- Feature flags: stale feature flag checks for flags that were already fully rolled out
- Deprecated paths: code paths behind deprecated API versions with no remaining consumers

**Spec Compliance / QA agent** (`ring-dev-team-qa-analyst`) must additionally verify:
- Testability assessment: is the code structured for testability? (dependency injection, interfaces)
- Operational readiness: can ops monitor, debug, and rollback this in production?
- Acceptance criteria coverage: each AC has both success AND failure test scenarios
- Cross-cutting scenarios: concurrent modifications, large datasets, special characters, timezone handling

**Frontend specialist** (`ring-dev-team-frontend-engineer`) must additionally verify:
- UX completeness: loading states, empty states, error states all handled
- Accessibility: keyboard navigation, screen reader support, ARIA labels, color contrast
- Responsive behavior: works across viewport sizes (mobile, tablet, desktop)
- i18n readiness: no hardcoded user-facing strings, date/number formatting locale-aware
- Performance: no unnecessary re-renders, large lists virtualized, images optimized

**Backend specialist** (`ring-dev-team-backend-engineer-golang` or `ring-dev-team-backend-engineer-typescript`) must additionally verify:
- Language idiomaticity: follows official style guide conventions
- Graceful shutdown: SIGTERM handling, in-flight request draining
- Connection pool sizing: appropriate for expected load
- Context propagation: request context passed through the full call chain
- Structured logging: logs include correlation IDs, operation names, durations

Skills reference this as: "Include per-droid quality checklists — see AGENTS.md Protocol: Per-Droid Quality Checklists."


### Protocol: Project Rules Discovery

**Referenced by:** stages 1-4, deep-review, coderabbit-review

Every skill that reviews, validates, or generates code MUST search for project rules
and AI instruction files before starting. Search for these files in order and read ALL
that exist:

```
AGENTS.md                    # Primary agent instructions
CLAUDE.md                    # Claude-specific rules
DROIDS.md                    # Droid-specific rules
.cursorrules                 # Cursor-specific rules
PROJECT_RULES.md             # Coding standards (root or docs/)
docs/PROJECT_RULES.md
.editorconfig                # Editor formatting rules
docs/coding-standards.md     # Explicit coding conventions
docs/conventions.md
.github/CONTRIBUTING.md      # Contribution guidelines
CONTRIBUTING.md
.eslintrc*                   # Linter configs (implicit rules)
biome.json
.golangci.yml
.prettierrc*
```

If NONE exist, warn the user. If any are found, they become the source of truth
for coding standards and must be passed to every dispatched sub-agent.

Skills reference this as: "Discover project rules — see AGENTS.md Protocol: Project Rules Discovery."


### Protocol: Push Commits (optional)

**Referenced by:** plan, build, review, coderabbit-review. Note: done handles pushing inline in its own cleanup phase. pr-check and deep-review have their own push phases.

After stage work is complete, offer to push all local commits:

**Step 1 — Check if upstream tracking exists:**

```bash
git rev-parse --abbrev-ref @{u} 2>/dev/null
```

- **If command fails (no upstream):** The branch was never pushed. All local commits are unpushed.
  Ask via `AskUser`:
  ```
  Branch has no upstream (never pushed). Push now?
  ```
  Options:
  - **Push now** — `git push -u origin "$(git branch --show-current)"`
  - **Skip** — I'll push manually later

- **If command succeeds (upstream exists):** Check for unpushed commits:
  ```bash
  git log @{u}..HEAD --oneline 2>/dev/null
  ```
  If there are unpushed commits, ask via `AskUser`:
  ```
  There are N unpushed commits on this branch. Push now?
  ```
  Options:
  - **Push now** — `git push`
  - **Skip** — I'll push manually later

**Why check upstream first:** `git log @{u}..HEAD` silently produces empty output when no
upstream exists, making it appear there's nothing to push. Without this check, the push step
would be silently skipped even though ALL local commits are unpushed.

**Step 2 — Check tasks repo in separate-repo mode:**

If `$TASKS_GIT_SCOPE = "separate-repo"`, the tasks repo is independent from the project
repo. Commits made via `tasks_git commit` (e.g., Active Version Guard) land in the tasks
repo and must be pushed separately. Skipping this makes team members pull project main
without seeing version/task changes.

```bash
if [ "$TASKS_GIT_SCOPE" = "separate-repo" ]; then
  # Check if tasks-repo current branch has upstream
  if ! tasks_git rev-parse --abbrev-ref @{u} >/dev/null 2>&1; then
    TASKS_BRANCH=$(tasks_git branch --show-current 2>/dev/null)
    # AskUser: "Tasks repo branch '$TASKS_BRANCH' has no upstream. Push now?"
    # Options: Push now — `tasks_git push -u origin "$TASKS_BRANCH"` / Skip
  else
    TASKS_UNPUSHED=$(tasks_git log @{u}..HEAD --oneline 2>/dev/null)
    if [ -n "$TASKS_UNPUSHED" ]; then
      TASKS_UNPUSHED_COUNT=$(printf '%s\n' "$TASKS_UNPUSHED" | wc -l | tr -d ' ')
      # AskUser: "Tasks repo has $TASKS_UNPUSHED_COUNT unpushed commits. Push now?"
      # Options: Push now — `tasks_git push` / Skip
    fi
  fi
fi
```

**After a successful push**, check if the current repo is the Optimus plugin repository
and update installed plugins to pick up the changes just pushed:

```bash
if jq -e '.name == "optimus"' .factory-plugin/marketplace.json >/dev/null 2>&1; then
  echo "Optimus repo detected — updating installed plugins..."
  for skill in $(droid plugin list 2>/dev/null | grep optimus | awk '{print $1}'); do
    droid plugin update "$skill" 2>/dev/null
  done
fi
```

This ensures that agents running in the Optimus repo itself always use the latest
skill versions after pushing changes.

Skills reference this as: "Offer to push commits — see AGENTS.md Protocol: Push Commits."


### Protocol: Quiet Command Execution (summarized)

> **Summary inlined here. Full recipe at `AGENTS.md -> Protocol: Quiet Command Execution`.**

**Summary:** `_optimus_quiet_run <label> <command>` redirects stdout+stderr to `${MAIN_WORKTREE}/.optimus/logs/<ts>-<label>-<pid>.log`, emits a single `PASS`/`FAIL` line, and on failure dumps the last 50 lines (with `cat -v` to neutralize ANSI/OSC escape sequences). Uses `umask 0077` on the log file (output may contain credentials/stack traces). Exit code preserved so `if _optimus_quiet_run ...; then ... fi` works. Reserved exit codes: `2` = missing label/command; `3` = cannot create logs dir. Log retention (30-day age cap + 500-file count cap) is pruned at every Initialize Directory + Session State call. Use for verification commands only; never for output the agent must parse turn-by-turn. See full recipe in AGENTS.md.

### Protocol: Re-run Guard

**Referenced by:** plan, review

After the convergence loop exits and the final report/summary is presented, evaluate
whether to suggest advancement or offer a re-run. This protocol replaces the static
"Next step suggestion" in plan and review.

**Logic:**

1. Count `total_findings` produced during this execution (all findings from round 1 AND
   any convergence rounds that were dispatched — note: with opt-in gating, the user may
   have skipped them all, in which case only round 1 contributes — from all agents and
   static analysis, regardless of whether they were fixed or skipped by the user). If
   findings were grouped (per Finding Presentation item 3), count grouped entries, not
   individual occurrences.
2. **If `total_findings == 0`:** The analysis is clean. Suggest the next stage:
   - plan: "Spec validation clean — 0 findings. Next step: run `/optimus:build` to implement this task."
   - review: "Implementation review clean — 0 findings. Next step: run `/optimus:done` to close this task."
3. **If `total_findings > 0`:** Ask via `AskUser`:
   ```
   Validation found N findings (X fixed, Y skipped).
   Re-running dispatches ALL review agents again with clean context (no memory of
   previous findings — findings you previously skipped will reappear for review).
   This will consume similar tokens to the initial run. Workspace and status are preserved.
   ```
   Options:
   - **Re-run with clean context** — re-analyze from scratch
   - **Advance to next stage** — proceed despite findings

4. **If "Re-run with clean context":**
   - Increment stage stats (new execution)
   - **Skip:** GitHub CLI check, optimus-tasks.md validation, task identification, session state
     check, status validation/change, workspace creation, divergence check
   - **Re-execute:** project structure discovery, document loading, static analysis,
     coverage profiling, agent dispatch (ALL agents), finding presentation, fix application,
     convergence loop entry gate (and any rounds the user opts into)
   - **Session file:** After re-run starts, the session protocol (Protocol: Session State)
     resumes normal operation — update the session file at each phase transition as usual.
     This ensures crash recovery during a re-run resumes from the correct phase.
   - After the re-run completes, apply this protocol again (evaluate findings count)
   - There is no limit on re-runs — the user controls when to stop

   **Re-run reset semantics (MANDATORY):** When the user chooses "Re-run with clean
   context", the orchestrator MUST:

   1. Reset `convergence_status` to `null` in the session file (was set to `"CONVERGED"`
      or another terminal state at the previous run's end).
   2. Reset `phase` to the entry of the re-executed flow (typically the first phase
      that performs work, NOT the load-only phases).
   3. Overwrite `started_at` with the new run's timestamp; preserve `created_at`.
   4. Preserve `task_id`, `task_branch`, and any other identity fields.
   5. After reset, normal `Protocol: Session State` updates resume.

   WITHOUT this reset, a previous run's `convergence_status: "CONVERGED"` would
   short-circuit the re-run's loop, producing a phantom "no findings" result.

5. **If "Advance to next stage":** Proceed to push commits and present the next step suggestion.

**NOTE:** "0 findings" means the analysis produced zero findings — not that all findings
were resolved. If the user skipped findings in a previous run, they will reappear on
re-run (clean context has no memory of previous decisions). This is by design.

**NOTE:** Re-run analyzes the current codebase state, including any fixes applied and
committed during the previous run. It does NOT revert commits. This validates that
applied fixes are correct and checks for any issues introduced by the fixes.

Skills reference this as: "Execute re-run guard — see AGENTS.md Protocol: Re-run Guard."


### Protocol: Ring Droid Requirement Check

**Referenced by:** review, deep-doc-review, coderabbit-review, plan, build

Before dispatching ring droids, verify the required droids are available. If any required
droid is not installed, **STOP** and list missing droids.

**Core review droids** (required by review, pr-check, deep-review, coderabbit-review):
- `ring-default-code-reviewer`
- `ring-default-business-logic-reviewer`
- `ring-default-security-reviewer`
- `ring-default-ring-test-reviewer`

**Extended review droids** (required by review, pr-check, deep-review, coderabbit-review):
- `ring-default-ring-nil-safety-reviewer`
- `ring-default-ring-consequences-reviewer`
- `ring-default-ring-dead-code-reviewer`

**QA droids** (required by review, deep-review, build):
- `ring-dev-team-qa-analyst`

**Documentation droids** (required by deep-doc-review):
- `ring-tw-team-docs-reviewer`
- `ring-default-business-logic-reviewer`
- `ring-default-code-reviewer`

**Implementation droids** (required by build):
- `ring-dev-team-backend-engineer-golang` (Go)
- `ring-dev-team-backend-engineer-typescript` (TypeScript)
- `ring-dev-team-frontend-engineer` (React/Next.js)

**Spec validation droids** (required by plan):
- `ring-default-business-logic-reviewer`
- `ring-default-security-reviewer`
- `ring-dev-team-qa-analyst`
- `ring-default-code-reviewer`

Skills reference this as: "Verify ring droids — see AGENTS.md Protocol: Ring Droid Requirement Check."


### Protocol: Session State (summarized)

> **Summary inlined here. Full recipe at `AGENTS.md -> Protocol: Session State`.**

**Summary:** Session lifecycle state at `${MAIN_WORKTREE}/.optimus/sessions/session-${TASK_ID}.json` tracks `task_id`, `branch`, `phase`, `convergence_status`, `started_at`. Update at every phase transition. Initialize `.optimus/` directory + auto-prune `.optimus/logs/` (30-day, 500-file cap) on transition. See full recipe in AGENTS.md.

### Protocol: State Management (summarized)

> **Summary inlined here. Full recipe at `AGENTS.md -> Protocol: State Management`.**

**Summary:** Read/write/delete entries in `${MAIN_WORKTREE}/.optimus/state.json` with `jq`. Schema: `{task_id: {status, branch, updated_at}}`. Status values: `Pendente | Validando Spec | Em Andamento | Validando Impl | DONE | Cancelado`. All writes use `jq --arg id "$TASK_ID" --arg status "$NEW_STATUS" '.[$id] = {...}'` (injection-safe), with a tmp-file + `jq empty` validation step before `mv` to guarantee atomicity. Cancelado entries keep `branch: ""` (empty string, NOT absent — readers must treat both as Cancelado-state). Corrupted state.json is removed and treated as empty (reconciliation via worktree scan). state.json is gitignored; never committed. See full recipe in AGENTS.md for jq templates and reconciliation steps.

### Protocol: TaskSpec Resolution

**Referenced by:** plan, build, review

Resolve the full path to a task's Ring pre-dev spec and its subtasks directory:

1. Read the task's `TaskSpec` column from `optimus-tasks.md`
2. If `TaskSpec` is `-` → **STOP**: "Task T-XXX has no Ring pre-dev spec. Run `/optimus:plan T-XXX` to generate one (it will offer to invoke `ring:pre-dev-feature` interactively)."
3. Resolve full path: `TASK_SPEC_PATH = <TASKS_DIR>/<TaskSpec>`
4. **Path traversal validation (HARD BLOCK):** `TaskSpec` must resolve to a file **inside `TASKS_DIR`**.
   This prevents a malicious TaskSpec value like `../../../etc/passwd` from escaping the
   Ring pre-dev tree. Also rejects symlinks to prevent symlink-bypass TOCTOU attacks:
   ```bash
   TASKS_DIR_ABS=$(cd "$TASKS_DIR" 2>/dev/null && pwd) || { echo "ERROR: tasksDir does not exist." >&2; exit 1; }
   RESOLVED_PATH=$(cd "$TASKS_DIR_ABS" && realpath -m "$TASK_SPEC" 2>/dev/null \
     || python3 -c "import os,sys; print(os.path.realpath(os.path.join(sys.argv[1], sys.argv[2])))" "$TASKS_DIR_ABS" "$TASK_SPEC" 2>/dev/null)
   if [ -z "$RESOLVED_PATH" ]; then
     echo "ERROR: Cannot resolve TaskSpec path — realpath and python3 both unavailable." >&2
     exit 1
   fi
   case "$RESOLVED_PATH" in
     "$TASKS_DIR_ABS"/*) ;; # OK — within tasksDir
     *) echo "ERROR: TaskSpec path traversal detected — resolved path is outside tasksDir." >&2; exit 1 ;;
   esac
   # Reject symlinks: if TASK_SPEC itself or any intermediate component is a
   # symlink, a TOCTOU attacker could swap the target between validation and
   # read. realpath -m resolves symlinks transparently; this post-check ensures
   # no symlink is present in the final path.
   if [ -L "$RESOLVED_PATH" ]; then
     echo "ERROR: TaskSpec resolves to a symlink — refusing to read." >&2
     exit 1
   fi
   ```

   **Validate `TASKS_DIR` itself:** `TASKS_DIR` must be inside a valid git repository
   (same repo as project, OR a separate repo — both are allowed). Resolution of
   `TASKS_GIT_SCOPE` (Protocol: Resolve Tasks Git Scope) already enforces this by
   running `git -C "$TASKS_DIR" rev-parse --show-toplevel`. If that call fails,
   `TASKS_DIR` is not a git repository and skills STOP.

   **NOTE:** `TASKS_DIR` is NO LONGER required to be inside `PROJECT_ROOT`. Teams using
   separate-repo scope (e.g., `tasksDir: ../tasks-repo/project-alfa`) are supported.
   The security guarantee is that the **TaskSpec value** cannot escape `TASKS_DIR`.

5. Read the task spec file at `TASK_SPEC_PATH`
6. Derive subtasks directory: if TaskSpec is `tasks/task_001.md`, subtasks are at `<TASKS_DIR>/subtasks/T-001/`
7. If subtasks directory exists, read all `.md` files inside it

Skills reference this as: "Resolve TaskSpec — see AGENTS.md Protocol: TaskSpec Resolution."


### Protocol: Terminal Identification

**Referenced by:** all stage agents (1-4), batch

After the task ID is identified and confirmed, set the terminal title to show the
current stage and task. This allows users running multiple agents in parallel terminals
to identify each terminal at a glance.

**Set title (after task ID is known):**

```bash
_optimus_set_title() {
  # iTerm2 AppleScript title updater. Empirical testing showed that Optimus
  # tasks always run in "divorced" iTerm2 sessions where the profile's
  # autoNameFormat is locked to a literal — OSC 0/1/2 and OSC 1337
  # SetUserVar are both ineffective in that state, so AppleScript's
  # `set name of s` is the only channel that actually mutates session.name.
  # The Execute tool runs bash without a controlling TTY, so /dev/tty fails
  # with ENODEV; we resolve the parent process's TTY via ps instead. Walk
  # up to 4 ancestors in case of nested shells. First run triggers a macOS
  # TCC prompt ("droid wants to control iTerm"); approving enables this
  # permanently. Silent no-op outside macOS/iTerm2 or when osascript is
  # unavailable — non-iTerm2 / non-macOS users get no title update.
  local title="$1"
  local pid="$PPID" tty=""
  for _ in 1 2 3 4; do
    [ -z "$pid" ] || [ "$pid" = "1" ] && break
    tty=$(ps -o tty= -p "$pid" 2>/dev/null | tr -d ' ')
    case "$tty" in
      ""|"?"|"??") pid=$(ps -o ppid= -p "$pid" 2>/dev/null | tr -d ' ') ;;
      *) break ;;
    esac
  done
  if { [ "$LC_TERMINAL" = "iTerm2" ] || [ "$TERM_PROGRAM" = "iTerm.app" ]; } \
     && command -v osascript >/dev/null 2>&1 && [ -n "$tty" ] \
     && [ "$tty" != "?" ] && [ "$tty" != "??" ]; then
    osascript \
      -e 'on run argv' \
      -e '  set targetTty to "/dev/" & item 1 of argv' \
      -e '  set newName to item 2 of argv' \
      -e '  tell application "iTerm2"' \
      -e '    repeat with w in windows' \
      -e '      repeat with t in tabs of w' \
      -e '        repeat with s in sessions of t' \
      -e '          if (tty of s as string) is targetTty then' \
      -e '            try' \
      -e '              set name of s to newName' \
      -e '            end try' \
      -e '          end if' \
      -e '        end repeat' \
      -e '      end repeat' \
      -e '    end repeat' \
      -e '  end tell' \
      -e 'end run' \
      -- "$tty" "$title" >/dev/null 2>&1 || true
  fi
}
_optimus_set_title "optimus: <STAGE> $TASK_ID — $TASK_TITLE"
```

Example output in terminal tab: `optimus: REVIEW T-003 — User Auth JWT`

**Why the parent-process TTY:** The Execute tool runs `bash -c` without a controlling
terminal, so `/dev/tty` returns `ENODEV` ("Device not configured"). The resolver above
asks `ps` for the parent's controlling TTY device path and matches it against iTerm2's
session list via AppleScript — that device is connected to the user's real iTerm2
session. If no ancestor has a TTY (Docker/CI) or osascript is unavailable, the
function silently no-ops.

**Restore title (at stage completion or exit):**

```bash
_optimus_set_title ""
```

**NOTE:** This helper is iTerm2-on-macOS only. Optimus tasks always run in
"divorced" iTerm2 sessions, where AppleScript's `set name of s` is the only
channel that reliably mutates `session.name`. Non-iTerm2 / non-macOS users
will not see a title update.

**Troubleshooting iTerm2 (if the title still doesn't update):**

1. **Window > Edit Tab Title** must be empty. A manually-set tab title is
   sticky on the tab label and overrides the session name visually, even
   when `session.name` is updated correctly underneath.
2. The first run on macOS triggers a TCC prompt ("`droid` wants to control
   `iTerm`"). Approve it to enable the helper. Denying makes the helper a
   silent no-op.
3. The helper requires the parent process to have a controlling TTY. Inside
   Docker/CI without a TTY, no ancestor will resolve and the helper will
   silently no-op.

Skills reference this as: "Set terminal title — see AGENTS.md Protocol: Terminal Identification."


### Protocol: Workspace Auto-Navigation (HARD BLOCK)

**Referenced by:** stages 2-4

Execution stages (2-4) resolve the correct workspace automatically. The agent MUST
be in the task's worktree before proceeding with any work.

```bash
DEFAULT_BRANCH=$(git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's@^refs/remotes/origin/@@')
if [ -z "$DEFAULT_BRANCH" ]; then
  # Use show-ref for deterministic fallback (unlike `git branch --list` which can
  # return either arbitrarily when both branches exist).
  if git show-ref --verify refs/remotes/origin/main >/dev/null 2>&1; then
    DEFAULT_BRANCH="main"
  elif git show-ref --verify refs/remotes/origin/master >/dev/null 2>&1; then
    DEFAULT_BRANCH="master"
  fi
fi
if [ -z "$DEFAULT_BRANCH" ]; then
  echo "ERROR: Cannot determine default branch. Set it with: git remote set-head origin <branch>" >&2
  exit 1
fi
CURRENT_BRANCH=$(git branch --show-current 2>/dev/null)
if [ -z "$CURRENT_BRANCH" ]; then
  echo "ERROR: Cannot determine current branch (detached HEAD state). Checkout a branch first." >&2
  exit 1
fi
```

**Resolution order:**

1. **Already on a feature branch?**
   - Derive the expected branch name from the task's Tipo + ID + Title (see Protocol:
     Branch Name Derivation). Also read the `branch` field from state.json if available.
   - Cross-validate: check that `CURRENT_BRANCH` matches the expected/derived branch.
   - If matches → proceed silently.
   - If does not match → warn via `AskUser`: "Expected branch `<expected>` for T-XXX,
     but you are on `<current>`. Continue on current branch, or switch?"

2. **On the default branch (auto-navigate)?**
   - Read state.json and list tasks with status compatible with the current stage
     (use the Transition Table to determine which statuses are valid).
     Tasks with no entry in state.json are `Pendente`.
   - **If 0 eligible tasks** → **STOP**: "No tasks in `<expected-status>` found."
   - **If 1 eligible task** → suggest via `AskUser`: "Found task T-XXX — [title] in
     worktree `<path>`. Continue with this task?"
   - **If N eligible tasks** → list all with worktree paths via `AskUser`:
     ```
     Multiple tasks available:
       T-001 — User auth (Em Andamento) → <repo>/.worktrees/feat/t-001-user-auth/
       T-002 — Login page (Em Andamento) → <repo>/.worktrees/feat/t-002-login-page/
     Which task should I continue?
     ```
   - After task is identified, locate the worktree. Prefer the source-of-truth
     (state.json `branch` field) and match the porcelain output by exact
     branch ref. Fall back to a kebab-anchored path match — never an
     unanchored substring grep on the bare task ID, which produces false
     positives for short IDs (e.g., `T-1` matching `T-10`, `T-100`):
     ```bash
     # Source-of-truth: branch from state.json (set by stage 1).
     TASK_BRANCH=$(jq -r --arg id "$TASK_ID" '.[$id].branch // ""' \
       "${MAIN_WORKTREE}/.optimus/state.json" 2>/dev/null)
     WORKTREE_PATH=""
     if [ -n "$TASK_BRANCH" ]; then
       WORKTREE_PATH=$(git worktree list --porcelain 2>/dev/null | awk -v br="refs/heads/$TASK_BRANCH" '
         /^worktree / { path=$2 }
         /^branch /   { if ($2 == br) { print path; exit } }
       ')
     fi
     if [ -z "$WORKTREE_PATH" ]; then
       # Fallback: anchored kebab-cased path-segment match (avoids T-1 vs T-10 substring collision).
       TASK_KEBAB="-$(echo "$TASK_ID" | tr '[:upper:]' '[:lower:]')-"
       WORKTREE_PATH=$(git worktree list --porcelain 2>/dev/null \
         | awk -v anchor="$TASK_KEBAB" '/^worktree / { path=$2; if (index(tolower(path), anchor) > 0) { print path; exit } }')
     fi
     ```
   - **If `WORKTREE_PATH` is non-empty** → change working directory to it.
   - **If worktree NOT found** → derive the branch name (Protocol: Branch Name Derivation)
     and verify it exists:
     ```bash
     if ! git rev-parse --verify "<branch-name>" >/dev/null 2>&1; then
       # Branch doesn't exist — ask user for recovery
       # AskUser: "No worktree or branch found for T-XXX.
       #   This may indicate stage-1 crashed before creating it.
       #   Options: Create branch from HEAD / Re-run /optimus:plan"
     fi
     ```
     If the branch exists, create the worktree automatically. Canonical path
     follows Protocol: Worktree Location:
     ```bash
     # Resolve main worktree first — see Protocol: Resolve Main Worktree Path.
     # Reuse cached MAIN_WORKTREE if caller already resolved.
     if [ -z "${MAIN_WORKTREE:-}" ]; then
       MAIN_WORKTREE="$(git worktree list --porcelain 2>/dev/null | awk '/^worktree / {print $2; exit}')"
     fi
     MAIN_WORKTREE="${MAIN_WORKTREE:?MAIN_WORKTREE not resolved — not in a git repository}"

     # Path-traversal guard (defense in depth): branch name comes from state.json
     # in some flows.
     case "<branch-name>" in
       *..*|/*) echo "ERROR: refusing unsafe branch name." >&2; exit 1 ;;
     esac
     WORKTREE_DIR="${MAIN_WORKTREE}/.worktrees/<branch-name>"

     if ! git worktree add "$WORKTREE_DIR" "<branch-name>"; then
       echo "ERROR: 'git worktree add $WORKTREE_DIR' failed (branch already checked out, dir collision, or filesystem error)." >&2
       exit 1
     fi
     ```
     Then change working directory to the new worktree.

**Stage-specific overrides:**

- **Stage 4 (`/optimus:done`)** applies a STRICTER form of resolution: it does NOT
  present a multi-task chooser and does NOT auto-navigate across tasks. If invoked
  without an explicit `T-XXX` argument, `done` closes ONLY the task corresponding to
  the current feature branch/worktree. If the user is on the default branch with no
  task argument, `done` STOPS with an error rather than choosing a task. See
  `done/skills/optimus:done/SKILL.md` (anchor `step-resolve-current-workspace`) for
  the full strict-mode rule.

**Defense-in-depth — refusal on default branch:** even after this protocol runs,
mutating stages MUST reject execution if the current branch is still the default
branch. See **Protocol: Default Branch Refusal** below.

Skills reference this as: "Resolve workspace (HARD BLOCK) — see AGENTS.md Protocol: Workspace Auto-Navigation."


### Protocol: optimus-tasks.md Validation (HARD BLOCK)

**Referenced by:** all stage agents (1-4), tasks, batch. Note: resolve performs inline format validation in its own Step 4.2.

Every stage agent MUST validate optimus-tasks.md before operating. The full validation rules are
defined in the "Format Validation" section above (items 1-15). This protocol is the
executable version:

1. **Resolve paths and git scope:** Execute Protocol: Resolve Tasks Git Scope (below) to
   resolve `TASKS_DIR`, `TASKS_FILE`, `TASKS_GIT_SCOPE`, and the `tasks_git` helper.
2. **Find optimus-tasks.md:** Check if `TASKS_FILE` exists. If not found, **STOP** and suggest `/optimus:import`.
3. **Validate format:** Execute all 15 validation checks from the "Format Validation" section. If the format marker is missing or any check fails, **STOP** and suggest `/optimus:import`.

**All subsequent references to `optimus-tasks.md` in the skill use the resolved `TASKS_FILE` path.
All references to Ring pre-dev artifacts use `TASKS_DIR` as the root** — never hardcoded paths.
**All git operations on optimus-tasks.md use the `tasks_git` helper** (which handles both same-repo
and separate-repo scopes).

Skills reference this as: "Find and validate optimus-tasks.md (HARD BLOCK) — see AGENTS.md Protocol: optimus-tasks.md Validation."


<!-- INLINE-PROTOCOLS:END -->
