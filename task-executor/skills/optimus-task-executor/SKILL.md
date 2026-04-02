---
name: optimus-task-executor
description: >
  Executes a validated task specification end-to-end: plans phases, questions
  ambiguities upfront, dispatches parallel agents, runs verification gates
  between phases, conducts interactive code review, and commits only after
  user approval.
trigger: >
  - After optimus-pre-task-validator has PASSED for a task
  - When user requests full task execution with a task ID (e.g., "execute T-012")
  - When starting implementation of a validated task from a tasks file
skip_when: >
  - Already inside a dev-cycle execution (dev-cycle orchestrates its own gates)
  - Task is pure research or documentation (no code to verify)
  - No tasks file exists yet (use pre-dev workflow first)
prerequisite: >
  - Task exists in a tasks file with a valid ID
  - Pre-task validation has passed
  - Reference docs exist (PRD, TRD, API design, data model)
  - Project rules file exists with coding standards
  - Project has lint, test, integration test, and E2E test commands configured
NOT_skip_when: >
  - "Task is simple" → Simple tasks still need verification gates.
  - "I already know the codebase" → Always explore before coding.
  - "Tests can come later" → Every phase must pass gates.
  - "Code review is optional" → Review is mandatory before commit.
examples:
  - name: Execute a full-stack task
    invocation: "Execute task T-012"
    expected_flow: >
      1. Load context from reference docs
      2. Explore existing codebase patterns
      3. Ask all questions upfront
      4. Plan phases and present to user
      5. Execute each phase with verification gates
      6. Run interactive code review
      7. Present summary and wait for commit approval
  - name: Execute a frontend-only task
    invocation: "Execute task T-015 (frontend only)"
    expected_flow: >
      1. Load context, skip backend reference docs
      2. Explore frontend patterns
      3. Plan frontend-only phases (types, components, pages, tests, E2E)
      4. Execute with verification gates (skip integration tests)
      5. Code review and commit
  - name: Resume interrupted execution
    invocation: "Resume task T-012"
    expected_flow: >
      1. Load state from optimus-task-executor-state.json
      2. Identify last completed phase
      3. Resume from next phase
related:
  complementary:
    - dev-implementation
    - dev-testing
    - requesting-code-review
    - dev-validation
  differentiation:
    - name: dev-cycle
      difference: >
        dev-cycle is a 6-gate orchestrator (implementation, devops, SRE, testing,
        review, validation) designed for Ring's gate system. optimus-task-executor is a
        standalone skill with its own phased execution, verification gates, and
        interactive code review — suited for projects that don't use the Ring
        gate system.
  sequence:
    after:
      - pre-dev-task-breakdown
      - pre-dev-subtask-creation
    before:
      - dev-feedback-loop
verification:
  automated:
    - command: "cat docs/dev-cycle/optimus-task-executor-state.json 2>/dev/null | jq '.status'"
      description: State file tracks execution progress
      success_pattern: completed
  manual:
    - All verification gates passed for every phase
    - Code review findings resolved or explicitly skipped
    - User approved final summary before commit
---

# Task Executor

Executes a validated task specification end-to-end: plans phases, questions ambiguities upfront, dispatches parallel agents, runs verification gates between phases, and commits only after user approval.

---

## Phase 0: Load Context & Question Everything

### Step 0.1: Discover Project Structure

Before loading docs, discover the project's structure and tooling:

1. **Identify stack:** Check for `go.mod`, `package.json`, `Makefile`, `Cargo.toml`, etc.
2. **Identify test commands:** Look in `Makefile`, `package.json` scripts, or CI config for lint, test, integration test, and E2E test commands.
3. **Identify reference docs:** Look for `docs/pre-dev/`, `docs/`, or project-specific locations for tasks, PRD, TRD, API design, data model, and coding standards.

Store discovered commands for use in verification gates:
```
LINT_CMD=<discovered lint command>
TEST_CMD=<discovered test command>
TEST_INTEGRATION_CMD=<discovered integration test command>
TEST_E2E_CMD=<discovered E2E test command>
```

If any command is not found, ask the user before proceeding.

### Step 0.2: Load All Reference Documents

Read the discovered reference docs to build full context:
- Tasks file — the task being executed (find the task by ID)
- API contracts
- DB schema / data model
- Technical architecture (TRD)
- Business requirements (PRD)
- Coding standards / project rules
- Dependency relationships

### Step 0.3: Explore Existing Codebase

Before planning, understand what already exists:
- **Grep for existing patterns** in the relevant domain packages. Understand the handler/service/repository structure, error patterns, test patterns.
- **Check for migrations** and identify the latest migration number.
- **Check existing test files** for patterns (table-driven tests, testcontainers, Playwright fixtures, Vitest, etc.).

### Step 0.4: Identify and Ask ALL Questions Upfront

Before writing a single line of code, analyze the task spec for:

1. **Ambiguities:** Anything a developer would need to ask to proceed
2. **Design decisions:** UI layout choices, component structure, state management approach
3. **Missing details:** Error messages, edge cases, exact file paths for new code
4. **Conflicts with existing code:** Patterns in the codebase that differ from what the task implies

Use the `AskUser` tool to ask ALL questions at once (max 4 per call, multiple calls if needed). Group questions by topic.

**Rules:**
- Never assume — if the task spec doesn't say it explicitly, ask
- Never start coding before all questions are answered
- Questions must be specific and actionable (not "how should I do X?" but "should X use pattern A or pattern B?")
- Include your recommendation with each question so the user can just approve

---

## Phase 1: Plan Execution

### Step 1.1: Break Task into Phases

Decompose the task into sequential phases. Each phase is a logical unit of work that can be verified independently. Typical phases for a full-stack task:

1. **Backend Domain** — models, errors, enums, validation logic
2. **Backend Repository** — database queries, SQL, migrations
3. **Backend Service** — business logic, orchestration
4. **Backend Handler** — HTTP handlers, request/response mapping, routing
5. **Backend Unit Tests** — all unit tests for the above
6. **Backend Integration Tests** — integration tests for repository + service
7. **Frontend Types & API** — types, API client functions
8. **Frontend Components** — UI components, forms, modals, tables
9. **Frontend Pages** — page-level composition, routing, data fetching
10. **Frontend Unit Tests** — frontend unit tests
11. **E2E Tests** — end-to-end tests for full user flows

Not all tasks need all phases. Skip phases that don't apply to the task scope.

### Step 1.2: Identify Parallelizable Work

Within each phase, identify independent units that can be dispatched to parallel agents:

**Parallelizable (no dependencies between them):**
- Unit tests for different functions (handler tests vs service tests vs model tests)
- Component tests for different components
- Multiple E2E test files covering different flows
- Independent components
- Backend model + frontend types (if API contract is stable)

**NOT parallelizable (sequential dependencies):**
- Migration must exist before repository
- Repository must exist before service
- Service must exist before handler
- Handler must exist before E2E tests
- API client must exist before components that use it

### Step 1.3: Present Plan to User

Before executing, present the plan as a numbered phase list with:
- What each phase delivers
- Which phases will use parallel agents (and which specialized droid)
- Estimated complexity (trivial / moderate / complex)
- Verification gate after each phase

Wait for user approval of the plan before proceeding.

---

## Phase 2-N: Execute Each Phase

### Execution Rules

For each phase:

1. **Update todo list** — mark the current phase as `in_progress`
2. **Dispatch parallel agents when applicable** — use the most appropriate specialized droids available in the environment. If no specialized droid exists for a task, execute directly.
3. **Write code following existing patterns** — match the codebase's style, not theoretical best practices
4. **Do NOT commit anything** — all changes stay uncommitted until the very end

### State Persistence

After each phase completes, save state to `docs/dev-cycle/optimus-task-executor-state.json`:
```json
{
  "task_id": "T-XXX",
  "status": "in_progress",
  "current_phase": 3,
  "phases": [
    {"name": "Backend Domain", "status": "completed", "gate": "PASS"},
    {"name": "Backend Repository", "status": "completed", "gate": "PASS"},
    {"name": "Backend Service", "status": "in_progress", "gate": null}
  ],
  "questions_answered": true,
  "plan_approved": true,
  "commands": {
    "lint": "make lint",
    "test": "make test",
    "test_integration": "make test-integration",
    "test_e2e": "make test-e2e"
  }
}
```

This enables resuming interrupted executions.

### Parallel Agent Dispatch

When dispatching agents via the `Task` tool, the prompt MUST include:

```
Goal: [what to build/test]
Context:
  - Task ID: T-XXX
  - Relevant files: [exact paths]
  - Existing patterns to follow: [file:line references]
  - API contract: [request/response format if applicable]
Constraints:
  - Follow project coding standards
  - Match existing code style in [package/directory]
  - Do NOT create new dependencies without approval
  - Do NOT modify files outside the scope listed
Expected output:
  - Files to create/modify: [list]
  - Tests to include: [list]
  - Summary of what was done
```

### Verification Gate (BLOCKING)

After EACH phase completes, run the verification gate using the discovered commands. ALL applicable commands must pass before advancing to the next phase.

**Gate rules:**
- If ANY command fails, STOP. Do not advance to the next phase.
- Diagnose the failure, fix it, and re-run the gate.
- If the fix requires changes to a previous phase's code, make the fix and re-run the gate for the current phase.
- Maximum 3 fix attempts per gate. If still failing after 3 attempts, present the failure to the user with diagnosis and ask for guidance.

**Gate optimization (intermediate phases only):**
- After a backend-only phase (no frontend changes), skip E2E tests
- After a frontend-only phase (no backend changes), skip integration tests
- Always run lint and unit tests (fast, catches regressions)

**MANDATORY: Final gate (before presenting summary to user) MUST run ALL commands — no exceptions, no skipping. E2E tests are NON-NEGOTIABLE in the final gate.**

---

## Phase R: Code Review (after all execution phases pass)

After all implementation phases pass verification, dispatch review agents and present findings interactively.

### Step R.1: Dispatch Review Agents in Parallel

Dispatch available review agents simultaneously via `Task` tool, scoped ONLY to files changed by this task. Use whatever review droids are available in the environment. At minimum, cover:

- **Code quality** — architecture, patterns, maintainability
- **Business logic** — domain correctness, edge cases
- **Security** — vulnerabilities, input validation
- **Test quality** — coverage gaps, test anti-patterns

Each agent prompt MUST include the full content of every changed file plus the task spec excerpt. Request structured output: severity (Critical/High/Medium/Low), file, line, finding summary, and suggested fix.

### Step R.2: Consolidate and Deduplicate

After all agents return:

1. Merge all findings into a single list
2. Deduplicate — if multiple agents flag the same issue (same file + same concern), keep one entry and note which agents agreed
3. Sort by severity: Critical > High > Medium > Low
4. Assign a sequential ID to each finding (F1, F2, F3...)

### Step R.3: Present Overview Table

Show a summary table so the user sees the full picture before diving in:

```markdown
## Code Review: X findings across Y agents

| # | Severity | File | Summary (1 line) | Agents |
|---|----------|------|-------------------|--------|
| F1 | HIGH | file.tsx | ... | QA, Code |
| F2 | MEDIUM | file.ts | ... | Frontend |

Security verdict: PASS / FAIL
```

### Step R.4: Interactive Finding-by-Finding Resolution

Process ONE finding at a time, starting from highest severity. For EACH finding, present:

#### Problem Description
- What is wrong and where (file, line, code snippet)
- Why it matters — what breaks, what risk it creates, what spec requirement it violates
- Impact on the end user if applicable

#### Proposed Solutions (2-3 options)

Each solution must consider:
- **UX impact** — how does this affect the end user?
- **Project focus** — does this align with MVP scope, or is it gold-plating?
- **Engineering quality** — maintainability, testability, consistency with codebase patterns
- **Effort** — trivial / small / moderate

Include a recommendation when one option is clearly better, with brief justification.

#### Ask User for Decision

Use `AskUser` tool. **BLOCKING**: Do NOT proceed to the next finding until the user decides.

### Step R.5: Apply Approved Fixes

For each finding the user chose to fix (not skipped):

1. Implement the chosen solution
2. Run lint + unit tests after each fix (or batch independent fixes in the same file)
3. If tests fail, diagnose and fix (max 3 attempts), then re-run
4. If fix fails 3 times, present the failure to user and ask for guidance

### Step R.6: Post-Review Verification Gate

After ALL findings are resolved (fixed or skipped), run the full verification gate. E2E tests MUST pass before proceeding.

### Step R.7: Review Summary

Present a final review summary with fixed findings, skipped findings, and verification results.

---

## Phase Final: User Validation & Commit

### Step F.1: Run Full Verification Gate (MANDATORY — NO EXCEPTIONS)

Run ALL discovered commands. Every single one MUST pass. Do NOT proceed to Step F.2 until all pass.

### Step F.2: Present Summary to User

Present a structured summary including: files created, files modified, tests added, verification gate results, and notes/decisions made.

### Step F.3: Wait for User Approval

Do NOT commit until the user explicitly says to commit. The user may want to:
- Review the code manually
- Run additional tests
- Request changes
- Test on a real device (for frontend tasks)

### Step F.4: Commit

Only after explicit user approval:

1. Run `git status` and `git diff --stat` to review
2. Run `git diff` to check for sensitive data (secrets, keys, tokens)
3. If clean, stage all relevant files and commit with a descriptive message
4. Run `git status` to confirm the commit succeeded

---

## Rules

### Code Quality
- Follow project coding standards strictly
- Match existing patterns in the codebase (grep before writing)
- Never introduce new dependencies without asking the user first
- Never create README/documentation files unless the task spec explicitly requires it
- Comments only when the code is non-obvious

### Scope Discipline
- Implement EXACTLY what the task spec says — no more, no less
- Do not refactor existing code unless the task requires it
- Do not fix unrelated bugs found during implementation (flag them to the user)
- Do not add "nice to have" improvements

### Error Handling
- If a phase fails verification gate 3 times, STOP and ask the user
- If a parallel agent returns incorrect or incomplete work, fix it yourself rather than re-dispatching
- If you discover a gap in the task spec during implementation, ask the user before proceeding

### Testing
- Every new function/method MUST have a corresponding test
- Tests must be deterministic (no random values, no current timestamps)
- Follow existing test patterns in the codebase
- E2E tests must use explicit waits (selectors, URLs, visibility), not timeouts

### Communication
- Update the todo list at EVERY phase transition
- Report verification gate results after each phase
- Never go silent for more than one phase without reporting status
