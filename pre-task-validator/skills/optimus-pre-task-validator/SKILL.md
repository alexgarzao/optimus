---
name: optimus-pre-task-validator
description: >
  Validates a task specification against project docs BEFORE code generation begins.
  Catches gaps, contradictions, ambiguities, test coverage holes, and observability
  issues that would cause rework. Analysis only — does not generate code.
trigger: >
  - Before starting any task implementation
  - When user requests spec validation (e.g., "validate spec for T-006")
  - Before invoking optimus-task-executor for a task
skip_when: >
  - Task is already implemented (use optimus-post-task-validator instead)
  - No task spec exists yet (use pre-dev workflow to create it first)
  - Task is pure research with no implementation deliverables
prerequisite: >
  - Task spec exists (user provides ID or skill auto-detects next pending task)
  - Reference docs exist (PRD, TRD, API design, data model)
  - Coding standards / project rules file exists
NOT_skip_when: >
  - "Task spec looks complete" → Completeness is not correctness. Cross-doc contradictions are invisible without validation.
  - "We already reviewed the spec" → Human review misses field-level contradictions. Automated validation catches what eyes skip.
  - "Time pressure" → Validation prevents rework, saving more time than it costs.
  - "Simple task" → Simple tasks still need dependency and test coverage checks.
examples:
  - name: Validate a full-stack task
    invocation: "Validate spec for T-006"
    expected_flow: >
      1. User specified task ID — confirm with user
      2. Discover project structure and reference docs
      3. Load task spec and all reference docs
      4. Cross-reference across all docs
      5. Analyze test coverage gaps
      6. Analyze observability gaps
      7. Present summary table, then walk through findings one at a time
      8. Batch apply all approved corrections
  - name: Validate next task (auto-detect)
    invocation: "Validate the next task"
    expected_flow: >
      1. Discover tasks file, identify next pending task
      2. Suggest to user and confirm via AskUser
      3. Standard validation flow
  - name: Validate a backend-only task
    invocation: "Validate spec for T-010"
    expected_flow: >
      1. User specified task ID — confirm with user
      2. Load context, skip frontend-related checks
      3. Focus on API contracts, data model, integration tests
      4. Present and resolve findings
related:
  complementary:
    - optimus-task-executor
    - optimus-post-task-validator
  differentiation:
    - name: optimus-post-task-validator
      difference: >
        optimus-post-task-validator validates AFTER implementation (code correctness,
        test quality, code review). optimus-pre-task-validator validates BEFORE
        implementation (spec correctness, doc consistency, test design).
  sequence:
    before:
      - optimus-task-executor
verification:
  manual:
    - All contradictions between docs resolved
    - All test coverage gaps addressed or explicitly accepted
    - Task spec updated with corrections before implementation begins
---

# Pre-Task Validator

Validates a task specification against project docs BEFORE code generation begins.
Catches gaps, contradictions, and ambiguities that would cause rework.

---

## Phase 0: Discover and Load Context

### Step 0.0: Identify Task to Validate

Determine which task to validate:

**If the user specified a task ID** (e.g., "validate T-006"):
- Use the provided task ID
- Confirm with the user using `AskUser`: "I'll validate task T-006: [task title]. Correct?"

**If the user did NOT specify a task ID** (e.g., "validate the next task", or just invoked the skill):
1. **Find the tasks file:** Look for task specs in `docs/`, `docs/pre-dev/`, or equivalent (files named `tasks.md`, `tasks/*.md`, or similar)
2. **Identify the next pending task:** Scan the tasks file for the first task that:
   - Has status "pending", "todo", "not started", or no status marker
   - Has all dependencies (required tasks) marked as "completed" or "done"
   - Is not blocked by other tasks
3. **If multiple candidates exist**, pick the one with the lowest ID (or earliest in the file)
4. **Suggest to the user** using `AskUser`: "I identified the next task to validate: T-XXX — [task title]. Is this correct, or would you like to validate a different task?"
5. **If no tasks file is found or no pending tasks exist**, ask the user to provide a task ID

**BLOCKING**: Do NOT proceed until the user confirms which task to validate.

### Step 0.1: Discover Project Structure

Before loading docs, discover the project's structure:

1. **Identify stack:** Check for `go.mod`, `package.json`, `Makefile`, `Cargo.toml`, etc.
2. **Identify test commands:** Look in `Makefile`, `package.json` scripts, or CI config for lint, test, integration test, and E2E test commands. These are needed for DoD validation.
3. **Identify reference docs:** Look for task specs, coding standards, API design, data model, architecture docs, business requirements, and dependency maps.
4. **Identify doc hierarchy:** Determine the source-of-truth ordering for conflicting docs (typically: coding standards > API design > data model > architecture > business requirements > task specs).

### Step 0.2: Load Documents

Read ALL discovered reference docs:
- Task spec (find the task being validated by ID)
- API contracts
- DB schema / data model
- Technical architecture
- Business requirements
- Coding standards (source of truth)
- Dependency relationships

### Step 0.3: Verify Existing Code

Check the codebase for:
- Are dependencies (required tasks) actually implemented?
- Do shared packages/interfaces referenced exist?
- Does the DB schema match the data model doc?
- Are there existing patterns to follow?

---

## Validation Dimensions

### 1. Spec Completeness
- Does the task have ALL required sections? (Scope, Success Criteria, Testing Strategy, Dependencies, Definition of Done)
- Are all fields/entities referenced actually defined in the data model?
- Are all endpoints referenced actually defined in the API contracts?
- Are all business rules explicitly stated (not implied)?

### 2. Cross-Doc Consistency
Check for contradictions BETWEEN docs using the discovered source-of-truth hierarchy:

- **Task spec vs API contracts**: HTTP methods, request/response formats, error codes, query params, field names
- **Task spec vs data model**: Column types, constraints (lengths, nullability, uniqueness), relationships
- **Task spec vs architecture**: Patterns, libraries, configuration values
- **Task spec vs business requirements**: Feature scope, user stories, acceptance criteria
- **API contracts vs data model**: Field names (API naming vs DB naming), types, nullable fields

### 3. Dependency Readiness
- Are ALL "Requires" tasks actually implemented and merged?
- Are DB tables/migrations that this task needs already created?
- Are shared packages/middleware this task depends on available?
- Are there circular dependencies with other tasks?

### 4. API Contract Completeness
For each endpoint in the task:
- Request format fully defined? (body, query params, path params, headers)
- Response format fully defined? (success + all error codes with HTTP status)
- Pagination format matches global convention?
- Authentication/authorization specified?
- Edge cases: empty body, missing fields, invalid types, boundary values

### 5. Test Coverage Gaps (MANDATORY)

This section is MANDATORY. You MUST analyze ALL three test types below and for EACH type either:
- List specific missing scenarios as gaps, OR
- Explicitly state "NONE — all code paths covered" with a brief justification listing the paths verified.

Skipping a test type or leaving it empty is NOT allowed.

#### 5a. Unit Test Gaps (REQUIRED)
For EACH function/method that the task will create or modify, verify:
- [ ] Happy path covered?
- [ ] Each validation rule has a corresponding test?
- [ ] Each error return path has a corresponding test?
- [ ] Boundary values tested (min, max, empty, nil, zero)?
- [ ] Each branch/condition in business logic has a test?

Enumerate every function and check each bullet. If ANY bullet is not covered, add it as a gap.

#### 5b. Integration Test Gaps (REQUIRED)
For EACH database operation that the task will create or modify, verify:
- [ ] CRUD cycle covered?
- [ ] Constraint violations tested (unique, FK, not null)?
- [ ] Data isolation tested (user A cannot see user B's data)?
- [ ] Pagination with real DB (first page, last page, beyond last page)?
- [ ] Sort/filter with real DB (each filter param, combined filters)?
- [ ] Edge cases: empty result set, single result, exact page boundary?

#### 5c. E2E Test Gaps (REQUIRED)
For EACH user-facing flow the task introduces, verify:
- [ ] Happy path covered (full flow from start to completion)?
- [ ] Each form field validation has a test?
- [ ] Error states covered (server error, network timeout, 4xx responses)?
- [ ] Navigation flows covered (create -> list -> detail -> edit -> delete)?
- [ ] Empty state (zero records) has a test?
- [ ] URL state persistence (query params survive refresh)?

#### 5d. Cross-Cutting Scenarios (REQUIRED)
For EACH of the following, verify if it applies to the task:
- [ ] Concurrent modifications (optimistic locking needed?)
- [ ] Large datasets (pagination boundary: last page, beyond last page)
- [ ] Special characters in text fields (unicode, injection via parameterized queries, XSS via framework escaping)
- [ ] Input truncation (fields exceeding length limits)
- [ ] Timezone handling (if dates are involved)

### 6. Definition of Done (DoD) Validation
Verify the task has a Definition of Done section with ALL required items:

**Required items (every task MUST have):**
- [ ] Code reviewed (specify reviewers as applicable)
- [ ] Tests passing with coverage threshold
- [ ] All verification commands passing (lint, unit tests, integration tests, E2E tests)
- [ ] Documentation updated (if applicable)

**Validate DoD quality:**
- Are coverage thresholds specified and realistic?
- Does the DoD explicitly list the project's verification commands?
- Are reviewer roles appropriate for the task type?
- Does the DoD include ALL deliverables?
- Are there measurable criteria (not vague like "works correctly")?
- Does the DoD match the task's Testing Strategy?
- Compare with DoD from completed tasks to ensure consistency

### 7. Observability Gaps

Analyze whether the task has adequate logging and metrics coverage. Check existing codebase patterns and verify:

#### 7a. Logging Gaps (REQUIRED)
For EACH new component the task creates:
- [ ] Success operations logged? (with entity IDs, operation name)
- [ ] Error paths logged? (with error message, context IDs)
- [ ] Security-relevant events logged? (auth failures, rate limits, suspicious input)
- [ ] Async/background operations logged? (start/end with duration, items processed)
- [ ] Sensitive data excluded from logs? (no passwords, tokens, PII)

Cross-cutting:
- [ ] Slow query logging exists?
- [ ] Server lifecycle logging exists?
- [ ] External service calls logged?

#### 7b. Metrics Gaps (REQUIRED)
Check if the task should emit structured fields that enable metrics:
- [ ] Operation counters?
- [ ] Duration tracking for batch/external operations?
- [ ] Error counters by type?
- [ ] Business KPIs relevant to the feature?

### 8. Implementability Check
- Can a developer implement each item WITHOUT asking questions?
- Are UI wireframes/designs referenced or described enough?
- Are external API contracts documented?
- Are feature flags or gradual rollout needed?
- Are there performance requirements with measurable thresholds?

---

## Execution

### Step 1: Cross-Reference
For EACH item in the task spec, verify it exists and is consistent in the reference docs.
Flag any item that:
- Exists in the task spec but NOT in API contracts or data model
- Has different values between docs (field type, HTTP method, error code)
- References something that doesn't exist yet (table, endpoint, component)

### Step 2: Analyze Test Gaps (MANDATORY — do NOT skip)
For EACH test type (unit, integration, E2E):
1. List every function/method/flow the task will create or modify
2. For each one, check every bullet from Dimension 5
3. For each uncovered bullet, add a row to the Test Coverage Gaps table
4. If all bullets are covered, write "NONE — verified: [list functions/flows checked]"

You MUST produce output for all 4 sub-sections (5a, 5b, 5c, 5d).

### Step 2.1: Cross-Reference Test Gaps with Future Tasks (MANDATORY)
For EACH test gap identified in Step 2:
1. **Search future tasks:** Scan the tasks file for any task that explicitly covers the missing test scenario (look for test-related acceptance criteria, testing strategy sections, or test IDs that match the gap)
2. **Classify each gap:**
   - **NOT PLANNED** — no future task covers this test. Flag as a gap in the current task.
   - **PLANNED IN T-XXX** — a future task explicitly includes this test. Note which task and what it covers.
3. **For gaps planned in future tasks**, evaluate and present to the user:
   - **Which future task** covers it (task ID and title)
   - **Opinion on timing:** Should the test be created now or is it reasonable to defer? Consider:
     - Does the current task introduce the code path that needs testing? If yes, recommend testing now.
     - Is the future task a dedicated testing task? If yes, deferring may be acceptable.
     - Does the gap create a risk window (untested code in production between tasks)?
   - **Ask the user** via `AskUser`: "Test gap [description] is planned for T-XXX. I recommend [now/deferring] because [reason]. Do you want to add this test to the current task?"

Add a column to the Test Coverage Gaps table:

```
| # | Type | Scenario Missing | Priority | Future Task | Recommendation |
|---|------|------------------|----------|-------------|----------------|
| 1 | Unit | Error path for X  | HIGH     | NOT PLANNED | Add to current task |
| 2 | Integration | Pagination edge case | MEDIUM | T-015 | Defer — dedicated test task |
| 3 | E2E | Empty state flow | HIGH | T-018 | Anticipate — current task creates this flow |
```

### Step 3: Analyze Observability Gaps (MANDATORY — do NOT skip)
For EACH new component:
1. Check existing logging patterns in the codebase
2. Verify new components follow them
3. Flag missing logs and missing structured fields for metrics

### Step 3.1: Dispatch Validation Agents (when available)

If specialist review droids are available in the environment, dispatch them in parallel to enrich the validation with expert analysis. Each agent receives the task spec, reference docs, and the gaps/findings identified so far.

**Agent selection priority:**

1. **Ring review droids (preferred when available):**
   - `ring-default-business-logic-reviewer` — validate business rules completeness, edge cases, and domain correctness in the task spec
   - `ring-default-security-reviewer` — identify security gaps in the spec (missing auth, input validation, data exposure risks)
   - `ring-dev-team-qa-analyst` — validate testing strategy completeness, identify untested scenarios
   - `ring-default-code-reviewer` — assess architectural feasibility, identify patterns that may conflict with the codebase
2. **Other available review droids:** If Ring droids are not available, use any other review droids
3. **Worker droid with validation instructions:** Fall back to `worker` with domain-specific instructions
4. **Skip:** If no droids are available, proceed with the findings from Steps 1-3 (the skill still works without agents)

**Agent prompt MUST include:**
```
Goal: Pre-implementation validation of task T-XXX — [your domain]

Context:
  - Task spec: [full task content]
  - Reference docs: [relevant sections]
  - Gaps already identified: [list from Steps 1-3]

Your job:
  Validate the task spec from your domain perspective BEFORE implementation.
  Identify risks, gaps, contradictions, or missing requirements.
  Report findings ONLY — do NOT generate code.

Required output:
  For each finding: severity, category, description, recommendation
  If no issues: "PASS — [domain] validation clean"
```

Merge agent findings with the findings from Steps 1-3. Deduplicate and sort by severity before presenting.

### Step 4: Phase 1 — Present Summary, then Walk Through Each Finding

1. **Present the summary report** (tables from Output Format) for bird's-eye view
2. **Then present findings ONE AT A TIME** in priority order: contradictions > missing specs > test gaps > observability > DoD > ambiguities
3. **For EACH finding**, present:
   - **Problem:** Clear description, referencing exact doc locations
   - **Why it matters:** Impact through UX and engineering best practices lenses
   - **Options:** 2-3 concrete resolution options with pros/cons/effort
   - **Recommendation:** Preferred option with justification
4. Use `AskUser` tool. **BLOCKING**: Do NOT advance to the next finding until the user decides
5. **Track all decisions** internally

### Step 5: Phase 2 — Apply ALL Approved Corrections

After the user has responded to ALL findings:
1. Present a pre-apply summary listing every change grouped by file
2. Apply ALL approved changes to the docs in a single pass
3. Present a final summary of what was changed vs skipped/rejected

**Do NOT commit automatically.** Present the changes and wait for the user to decide whether to commit.

---

## Output Format

```markdown
# Pre-Task Validation Report: T-XXX

## Status: PASS | FAIL | PASS WITH WARNINGS

## 1. Contradictions Found
| # | Doc A | Doc B | Field/Topic | Doc A Says | Doc B Says | Recommendation |
|---|-------|-------|-------------|------------|------------|----------------|

## 2. Missing Specifications
| # | What's Missing | Where Expected | Impact | Recommendation |
|---|----------------|----------------|--------|----------------|

## 3. Dependency Issues
| # | Dependency | Status | Blocker? | Resolution |
|---|------------|--------|----------|------------|

## 4. Test Coverage Gaps (MANDATORY — all 4 sub-sections required)

### 4a. Unit Test Gaps
Functions/methods verified: [list each function checked]
| # | Function/Method | Scenario Missing | Priority |
|---|----------------|------------------|----------|
(or: NONE — all paths covered. Justification: ...)

### 4b. Integration Test Gaps
Repository methods verified: [list each method checked]
| # | Repository Method | Scenario Missing | Priority |
|---|------------------|------------------|----------|
(or: NONE — all paths covered. Justification: ...)

### 4c. E2E Test Gaps
User flows verified: [list each flow checked]
| # | User Flow | Scenario Missing | Priority |
|---|-----------|------------------|----------|
(or: NONE — all paths covered. Justification: ...)

### 4d. Cross-Cutting Gaps
| # | Scenario | Applies? | Covered? | Gap Description |
|---|----------|----------|----------|-----------------|

## 5. Observability Gaps (MANDATORY)

### 5a. Logging Gaps
Components verified: [list each component checked]
| # | Component | Gap Description | Priority |
|---|-----------|-----------------|----------|
(or: NONE — all components have adequate logging. Justification: ...)

### 5b. Metrics Gaps
| # | Metric Missing | Where Expected | Priority |
|---|---------------|----------------|----------|
(or: NONE — all operations emit structured fields. Justification: ...)

## 6. Definition of Done Issues
| # | Issue | Current DoD Says | Expected | Recommendation |
|---|-------|-----------------|----------|----------------|

## 7. Ambiguities (developer would need to ask)
| # | Question | Context | Suggested Answer |
|---|----------|---------|-----------------|

## 8. Recommendations
- [ ] Fix before starting: ...
- [ ] Clarify with stakeholder: ...
- [ ] Add to backlog: ...
```

---

## Rules
- Do NOT generate code — this is analysis only
- Do NOT assume — if something is ambiguous, flag it
- ALWAYS check both happy path AND error paths
- Prioritize findings: contradictions > missing specs > test gaps > observability gaps > DoD issues > ambiguities
- Reference exact file locations when citing docs
- Test Coverage Gaps (Dimension 5) is MANDATORY and MUST enumerate gaps for ALL three test types plus cross-cutting scenarios
- Observability Gaps (Dimension 7) is MANDATORY. Check existing codebase logging patterns and verify new components follow them
- ALWAYS use the two-phase flow: Phase 1 presents summary then walks through each finding one at a time. Phase 2 applies all approved corrections at once
- Do NOT commit automatically — present changes and wait for user approval
- Every finding must reference a specific doc section or standard — "I would do it differently" is not a valid finding
