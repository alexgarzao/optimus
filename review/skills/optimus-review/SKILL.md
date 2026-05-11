---
name: optimus-review
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
  - Project has a Makefile with `lint` and `test` targets
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
  sequence:
    after:
      - optimus-build
verification:
  automated:
    - command: "git diff --name-only 2>/dev/null | wc -l"
      description: Changed files exist (uncommitted changes to validate)
      success_pattern: '[1-9]'
  manual:
    - All findings resolved (fixed or explicitly skipped by user)
    - Verification gate passed after fixes applied
    - Convergence loop run, skipped, or stopped (status recorded)
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

**Mark terminal session (iTerm2 badge + tab color).** Before running this block, **substitute `$TASK_ID`** with the confirmed task ID and **`$TASKS_FILE`** with the resolved optimus-tasks.md path. The block parses `TASK_TITLE` and calls `_optimus_mark_session` in the **SAME** Bash invocation — each Bash tool invocation is a fresh shell, so a `TASK_TITLE` parsed in a previous block would NOT survive here, and the badge would render empty. The function body is inlined for the same reason. See AGENTS.md Protocol: Terminal Identification. The canonical function body lives there.

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
  # Non-fatal: the badge text is informational. Fall back to a stub so the
  # badge does not render as a bare "REVIEW" with no task context.
  TASK_TITLE="(title unavailable)"
fi

_optimus_mark_session() {
  local stage="$1" task_id="$2" title="$3"
  [ "$LC_TERMINAL" = "iTerm2" ] || [ "$TERM_PROGRAM" = "iTerm.app" ] || return 0
  local pid="$PPID" target_tty=""
  for _ in 1 2 3 4; do
    [ -z "$pid" ] || [ "$pid" = "1" ] && break
    target_tty=$(ps -o tty= -p "$pid" 2>/dev/null | tr -d ' ')
    case "$target_tty" in
      ""|"?"|"??") pid=$(ps -o ppid= -p "$pid" 2>/dev/null | tr -d ' '); target_tty="" ;;
      *) break ;;
    esac
  done
  _optimus_emit() {
    if [ -n "$target_tty" ] && [ -w "/dev/$target_tty" ]; then
      printf '%s' "$1" > "/dev/$target_tty" 2>/dev/null || printf '%s' "$1"
    else
      printf '%s' "$1"
    fi
  }
  local badge_b64
  badge_b64=$(printf '%s %s\n%s' "$stage" "$task_id" "$title" | base64 | tr -d '\n')
  _optimus_emit "$(printf '\e]1337;SetBadgeFormat=%s\a' "$badge_b64")"
  local r g b
  case "$stage" in
    PLAN)   r=66;  g=135; b=245 ;;
    BUILD)  r=34;  g=197; b=94  ;;
    REVIEW) r=234; g=179; b=8   ;;
    DONE)   r=148; g=163; b=184 ;;
    *)      r=168; g=85;  b=247 ;;
  esac
  _optimus_emit "$(printf '\e]6;1;bg;red;brightness;%d\a\e]6;1;bg;green;brightness;%d\a\e]6;1;bg;blue;brightness;%d\a' "$r" "$g" "$b")"
}
_optimus_mark_session REVIEW "$TASK_ID" "$TASK_TITLE"
```

**On stage completion or exit**, restore the title (body inlined for the same reason as above):

```bash
_optimus_clear_session() {
  [ "$LC_TERMINAL" = "iTerm2" ] || [ "$TERM_PROGRAM" = "iTerm.app" ] || return 0
  local pid="$PPID" target_tty=""
  for _ in 1 2 3 4; do
    [ -z "$pid" ] || [ "$pid" = "1" ] && break
    target_tty=$(ps -o tty= -p "$pid" 2>/dev/null | tr -d ' ')
    case "$target_tty" in
      ""|"?"|"??") pid=$(ps -o ppid= -p "$pid" 2>/dev/null | tr -d ' '); target_tty="" ;;
      *) break ;;
    esac
  done
  _optimus_emit_clear() {
    if [ -n "$target_tty" ] && [ -w "/dev/$target_tty" ]; then
      printf '%s' "$1" > "/dev/$target_tty" 2>/dev/null || printf '%s' "$1"
    else
      printf '%s' "$1"
    fi
  }
  _optimus_emit_clear "$(printf '\e]1337;SetBadgeFormat=\a')"
  _optimus_emit_clear "$(printf '\e]6;1;bg;*;default\a')"
}
_optimus_clear_session
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

- Resolve TaskSpec — see AGENTS.md Protocol: TaskSpec Resolution.
- Load the Doc Brief — see AGENTS.md Protocol: Doc Brief Cache.
  - If `.optimus/sessions/T-XXX/doc-brief.md` exists with matching `task_spec_hash`: load it. The brief contains the task-scoped excerpt of PRD, TRD, API, data-model, plus the relevant AGENTS.md protocols.
  - Otherwise: generate the brief now per the protocol, using the protocol set: `Per-Droid Quality Checklists`, `Deep Research Before Presenting`, `Convergence Loop`, `Re-run Guard`, `Coverage Measurement`, `Quiet Command Execution`, `Ring Droid Requirement Check`.

The Doc Brief is the primary context for downstream agent dispatches in Phase 3 and beyond; do NOT instruct agents to read PRD/TRD/API/data-model directly unless the Doc Brief is explicitly insufficient for a finding.

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
  - Doc brief (READ FIRST — task-scoped excerpt of pre-dev docs, AGENTS.md protocols, project rules):
    .optimus/sessions/T-XXX/doc-brief.md
  - Full pre-dev docs (consult ONLY if Doc Brief is insufficient): <TASKS_DIR>/
  - Subtasks dir: <TASKS_DIR>/subtasks/T-XXX/ (READ all .md files if dir exists; SKIP if absent)
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

Verification scope (MANDATORY):
  Static analysis (lint, vet, format) and tests (unit, integration, coverage)
  have already been run by the orchestrator. Results are in this prompt or in
  the log files referenced under .optimus/logs/.
  - Do NOT run verification commands yourself. Forbidden: `go test`, `npm test`,
    `npm run test`, `pytest`, `make test`, `make lint`, `make test-coverage`,
    `make test-integration`, `golangci-lint`, `go vet`, `goimports`, `gofmt`,
    `prettier`, `eslint`, `tsc`, or any equivalent.
  - If you need test/coverage details, Read the log files referenced in this
    prompt — do not regenerate them.
  - Use Read, Grep, and Glob to inspect source files. Reserve Bash for read-only
    git inspection (`git log`, `git blame`, `git diff`) when needed.

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

**If N==1, skip any confirmation prompt** — present the single finding directly with header `(1/1) ...`. The user already chose to review by invoking the skill.

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
Each agent receives the SAME compact context as round 1: the Doc Brief
(`.optimus/sessions/T-XXX/doc-brief.md`), changed file paths, and the round-1 findings
ledger. Do NOT instruct agents to "re-read fresh from disk" — that defeats the brief's
caching purpose. Agents may consult full pre-dev docs only if a finding requires verbatim
reference. The orchestrator handles dedup using strict matching (same file + same line
range ±5 + same category).

Include the same items from the Phase 3 prompt (both the Verification scope block and the Cross-cutting analysis 5 items).

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

### Task Spec Resolution

Every task SHOULD have a Ring pre-dev reference in the `TaskSpec` column. Tasks may be created with `TaskSpec=-` (deferred); the next `/optimus-plan` run will offer to generate or link a spec. Stage agents
(plan, build, review) resolve the full path as `<tasksDir>/<TaskSpec>` and read the
referenced file for objective, acceptance criteria, and implementation details.

The subtasks directory is derived automatically from the TaskSpec path:
- TaskSpec: `tasks/task_001.md` → Subtasks: `<tasksDir>/subtasks/T-001/`
- The `T-NNN` identifier is extracted from the task spec filename convention

Agents read objective and acceptance criteria directly from the Ring source files.
The optimus-tasks.md table only tracks structural data (dependencies, versions, priorities)
— it does NOT duplicate content from Ring.


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


### Protocol: Coverage Measurement (summarized)

> **Summary inlined here. Full recipe at `AGENTS.md -> Protocol: Coverage Measurement`.**

**Summary:** Measure unit + integration test coverage via Makefile targets with stack-specific fallbacks (Go: `go test -coverprofile`; Node: `npm test -- --coverage`; Python: `pytest --cov=. --cov-report=term`). Run wrapped in `_optimus_quiet_run` (Protocol: Quiet Command Execution) to keep agent context clean — the agent sees only PASS/FAIL + extracted total percentage; full per-file breakdown stays in `.optimus/logs/` and native coverage files. Thresholds: unit 85%, integration 70% (NEEDS_FIX/HIGH finding below). When scanning untested functions, read coverage output FILE (not stdout) — flag business-logic functions at 0% as HIGH; infrastructure/generated code as SKIP. If no coverage command resolves, mark SKIP — do not fail verification. See full extraction recipes in AGENTS.md.

### Protocol: Notification Hooks (summarized)

> **Summary inlined here. Full recipe at `AGENTS.md -> Protocol: Notification Hooks`.**

**Summary:** Optional hook system: stages emit events (`status-change`, `task-blocked`, `task-done`, `task-cancelled`) by invoking `<repo>/tasks-hooks.sh <event> <task_id> <args...>` (or `<repo>/docs/tasks-hooks.sh`) if the file exists and is executable. Hook receives sanitized args (alphanumeric + space + `-_:` only — does NOT allow `.` or `/` to prevent path-traversal if hook authors interpolate args into file paths). Argument shape: 4 args for `status-change`/`task-done`/`task-cancelled` (`event task_id old_status new_status`); 4 args for `task-blocked` (`event task_id current_status reason`). Hooks run in background (`&`) — failures NEVER block the pipeline. Capture `OLD_STATUS` BEFORE writing the new status. See full event signatures + sanitization recipe in AGENTS.md.

### Protocol: Per-Droid Quality Checklists (summarized)

> **Summary inlined here. Full recipe at `AGENTS.md -> Protocol: Per-Droid Quality Checklists`.**

**Summary:** Per-droid quality dimensions that review/pr-check/deep-review/coderabbit-review/plan/build skills MUST include in their agent prompts beyond the core review domain. Examples: code-reviewer adds resilience/concurrency/cognitive-complexity/error-handling checks; security-reviewer adds PII/error-response-leakage/rate-limiting/secrets; test-reviewer adds effectiveness/false-positive-risk/spec-traceability; nil-safety adds channel/map/slice safety; consequences adds backward-compat/migration-path/event-contract; dead-code adds zombie test infrastructure and stale feature flags; qa-analyst adds testability/operational-readiness; frontend adds UX states/accessibility/i18n; backend adds graceful-shutdown/context-propagation/structured-logging. Skills reference this when building specialist droid prompts so agents review uniformly. See full per-droid lists in AGENTS.md.

### Protocol: Quiet Command Execution (summarized)

> **Summary inlined here. Full recipe at `AGENTS.md -> Protocol: Quiet Command Execution`.**

**Summary:** `_optimus_quiet_run <label> <command>` redirects stdout+stderr to `${MAIN_WORKTREE}/.optimus/logs/<ts>-<label>-<pid>.log`, emits a single `PASS`/`FAIL` line, and on failure dumps the last 50 lines (with `cat -v` to neutralize ANSI/OSC escape sequences). Uses `umask 0077` on the log file (output may contain credentials/stack traces). Exit code preserved so `if _optimus_quiet_run ...; then ... fi` works. Reserved exit codes: `2` = missing label/command; `3` = cannot create logs dir. Log retention (30-day age cap + 500-file count cap) is pruned at every Initialize Directory + Session State call. Use for verification commands only; never for output the agent must parse turn-by-turn. See full recipe in AGENTS.md.

### Protocol: Re-run Guard (summarized)

> **Summary inlined here. Full recipe at `AGENTS.md -> Protocol: Re-run Guard`.**

**Summary:** Replaces the static "next step" suggestion in plan and review. Counts `total_findings` from this execution (grouped entries count as 1). If 0 → suggest next stage (build for plan, done for review). If >0 → `AskUser` offering "Re-run with clean context" (re-dispatches ALL agents with no memory of prior decisions — skipped findings will reappear) or "Advance to next stage". Re-run reset semantics (MANDATORY): reset `convergence_status` to `null`, `phase` to entry, overwrite `started_at`; preserve identity fields. Skip GitHub CLI/tasks validation/workspace/divergence checks; re-execute discovery + dispatch. No re-run limit. See full reset checklist in AGENTS.md.

### Protocol: State Management (summarized)

> **Summary inlined here. Full recipe at `AGENTS.md -> Protocol: State Management`.**

**Summary:** Read/write/delete entries in `${MAIN_WORKTREE}/.optimus/state.json` with `jq`. Schema: `{task_id: {status, branch, updated_at}}`. Status values: `Pendente | Validando Spec | Em Andamento | Validando Impl | DONE | Cancelado`. All writes use `jq --arg id "$TASK_ID" --arg status "$NEW_STATUS" '.[$id] = {...}'` (injection-safe), with a tmp-file + `jq empty` validation step before `mv` to guarantee atomicity. Cancelado entries keep `branch: ""` (empty string, NOT absent — readers must treat both as Cancelado-state). Corrupted state.json is removed and treated as empty (reconciliation via worktree scan). state.json is gitignored; never committed. See full recipe in AGENTS.md for jq templates and reconciliation steps.

### Protocol: TaskSpec Resolution (summarized)

> **Summary inlined here. Full recipe at `AGENTS.md -> Protocol: TaskSpec Resolution`.**

**Summary:** Resolves the full path to a task's Ring pre-dev spec file by combining `<TASKS_DIR>` with the task's `TaskSpec` column from `optimus-tasks.md`. If `TaskSpec` is `-`, STOPs with a hint to run `/optimus-plan T-XXX`. HARD BLOCK on path traversal: resolves via `realpath -m` (or python3 `os.path.realpath` fallback) and rejects any result outside `$TASKS_DIR_ABS`. Also rejects symlinks (TOCTOU defence: realpath dereferences transparently, so a post-`-L` check guarantees no symlink in the final path). `TASKS_DIR` itself must be a valid git repo (enforced upstream by Resolve Tasks Git Scope) but is no longer required to live under `PROJECT_ROOT` — separate-repo scope is supported. Subtasks live at `<TASKS_DIR>/subtasks/T-NNN/`. See full recipe in AGENTS.md.

### Protocol: Terminal Identification (summarized)

> **Summary inlined here. Full recipe at `AGENTS.md -> Protocol: Terminal Identification`.**

**Summary:** `_optimus_mark_session <stage> <task_id> <title>` marks the current iTerm2 session with two **focus-independent** signals: an iTerm2 Badge (OSC 1337 SetBadgeFormat) — large semi-transparent overlay text always visible (incl. Mission Control thumbnails and Dock previews) — and a Tab Color (OSC 6 SetColors) tinting the tab per stage (PLAN=blue, BUILD=green, REVIEW=yellow, DONE=gray, RESUME/BATCH=purple). Used by stage skills so users running multiple Optimus sessions can identify each at a glance, even with the window unfocused or backgrounded. Replaces the previous AppleScript title approach which only updated reliably when the iTerm2 tab had focus and required TCC permission. Helper writes to the parent shell's controlling TTY; silent no-op outside iTerm2/macOS. Companion `_optimus_clear_session` resets badge and tab color at stage completion. See full bash function in AGENTS.md.

<!-- INLINE-PROTOCOLS:END -->
