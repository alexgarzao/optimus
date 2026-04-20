---
name: optimus-cycle-spec-stage-1
description: >
  Stage 1 of the task lifecycle. Validates a task specification against project
  docs BEFORE code generation begins. Catches gaps, contradictions, ambiguities,
  test coverage holes, and observability issues. Analysis only — does not generate code.
trigger: >
  - Before starting any task implementation
  - When user requests spec validation (e.g., "validate spec for T-006")
  - Before invoking optimus-cycle-impl-stage-2 for a task
skip_when: >
  - Task is already implemented (use optimus-cycle-impl-review-stage-3 instead)
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
    - optimus-cycle-impl-stage-2
    - optimus-cycle-impl-review-stage-3
  differentiation:
    - name: optimus-cycle-impl-review-stage-3
      difference: >
        optimus-cycle-impl-review-stage-3 validates AFTER implementation (code correctness,
        test quality, code review). optimus-cycle-spec-stage-1 validates BEFORE
        implementation (spec correctness, doc consistency, test design).
  sequence:
    before:
      - optimus-cycle-impl-stage-2
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

### Step 0.0.1: Identify Task to Validate

**If the user specified a task ID** (e.g., "validate T-006"):
- Use the provided task ID
- Confirm with the user using `AskUser`: "I'll validate task T-006: [task title]. Correct?"

**If the user did NOT specify a task ID** (e.g., "validate the next task", or just invoked the skill):
1. **Identify the next eligible task:** Scan the table for the first task that:
   - Has status `Pendente` or `Validando Spec` (re-execution)
   - Has all dependencies (Depends column) with status `**DONE**` (or Depends is `-`)
2. **If multiple candidates exist**, pick the one with highest Priority (`Alta` > `Media` > `Baixa`), then lowest ID
3. **Suggest to the user** using `AskUser`: "I identified the next task to validate: T-XXX — [task title]. Is this correct, or would you like to validate a different task?"
4. **If no eligible tasks exist**, ask the user to provide a task ID

**BLOCKING**: Do NOT proceed until the user confirms which task to validate.

### Step 0.0.2: Validate Task Status (DO NOT modify yet)

**HARD BLOCK:** This step is mandatory. Do NOT skip it.

1. Read `tasks.md` and find the row for the confirmed task ID
2. Check the **Status** column:
   - If status is `Pendente` → proceed
   - If status is `Validando Spec` → proceed (re-execution of this stage)
   - If status is anything else → **STOP** and tell the user:
     ```
     Task T-XXX is in '<current_status>'. To run cycle-spec-stage-1,
     it must be in 'Pendente' or 'Validando Spec'. This task has already moved past this stage.
     ```
3. **Check dependencies (HARD BLOCK):** Read the Depends column for this task.
   - If Depends is `-` → proceed (no dependencies)
   - For each dependency ID listed, check its Status in the table:
     - If ALL dependencies have status `**DONE**` → proceed
     - If ANY dependency is NOT `**DONE**` → **STOP**:
       ```
       Task T-XXX depends on T-YYY (status: '<status>'). T-YYY must be **DONE** first.
       ```
4. **Expanded confirmation before status change:**
   - **If status will change** (current status is NOT `Validando Spec`) AND the user did NOT specify the task ID explicitly (auto-detect):
     - Read the task's H2 detail section (`## T-XXX: Title`) from `tasks.md`
     - Present to the user via `AskUser`:
       ```
       I'm about to change task T-XXX status from '<current>' to 'Validando Spec'.

       **T-XXX: [title]**
       **Objetivo:** [objective from detail section]
       **Critérios de Aceite:**
       - [ ] [criterion 1]
       - [ ] [criterion 2]
       ...

       Confirm status change?
       ```
     - **BLOCKING:** Do NOT change status until the user confirms
   - **If re-execution** (status is already `Validando Spec`) OR the user specified the task ID explicitly:
     - Skip expanded confirmation (user already has context)

**IMPORTANT:** Do NOT modify tasks.md yet. Status and Branch updates happen in Step 0.0.4 AFTER the workspace is created. This ensures the modifications happen in the correct working directory (worktree or feature branch).

**Anti-pulo:** This agent accepts tasks in `Pendente` or `Validando Spec` (re-execution) status. If a task is in any other status (`Em Andamento`, `Validando Impl`, `Revisando PR`, `**DONE**`), refuse to proceed — the task has already passed this stage.

### Step 0.0.3: Create Workspace (if on default branch)

Check if currently on the default/main branch:

```bash
DEFAULT_BRANCH=$(git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's@^refs/remotes/origin/@@')
CURRENT_BRANCH=$(git branch --show-current)
```

**If already on a feature branch** (not default/main/master): proceed to Step 0.0.4 (re-execution or workspace already exists).

**If on default branch:** Create a workspace for the task. Ask the user via `AskUser`:

"Task T-XXX needs a workspace. How should I create it?"

Options:
- **(a) Git worktree (recommended)** — creates a worktree in a sibling directory, keeps the current branch untouched
- **(b) New branch** — creates and checks out a new branch in the current repository

**Branch naming:** Generate a descriptive name from the task ID and title:
- Pattern: `feat/<task-id>-<keywords>` where keywords are 2-4 lowercase words from the title
- Examples: `feat/t-016-boleto-cancellation`, `feat/t-003-user-auth-jwt`
- Strip articles, prepositions, and generic words (implement, add, create, update)

**If worktree (recommended):**
```bash
git worktree add ../<repo>-<task-id>-<keywords> -b feat/<task-id>-<keywords>
```
Then change working directory to the new worktree path for all subsequent steps.

**If new branch:**
```bash
git checkout -b feat/<task-id>-<keywords>
```

**BLOCKING**: Do NOT proceed until the workspace is created.

### Step 0.0.4: Update tasks.md (Status + Branch)

**IMPORTANT:** This step runs AFTER the workspace is created, so modifications happen in the feature branch's working directory — not on the default branch.

1. Update the **Status** column to `Validando Spec` (if not already)
2. Update the **Branch** column with the branch name created in Step 0.0.3 (if a new workspace was created)
3. Commit these changes immediately:
   ```bash
   git add tasks.md
   git commit -m "chore(tasks): start T-XXX — set status to Validando Spec"
   ```

**Why commit immediately:** Stage-1 is analysis-only — it may not produce any other file changes. If no findings are fixed (all skipped), Step 6 would not commit, leaving tasks.md changes uncommitted and at risk of being lost. Committing now ensures the status change is persisted regardless of the analysis outcome.

### Step 0.1: Discover Project Structure

Before loading docs, discover the project's structure:

1. **Identify stack:** Check for `go.mod`, `package.json`, `Makefile`, `Cargo.toml`, etc.
2. **Identify test commands:** Look in `Makefile`, `package.json` scripts, or CI config for lint, test, integration test, and E2E test commands. These are needed for DoD validation.
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

   **If any are found**, they become the **source of truth** for coding standards. Every finding must reference a rule from these files when applicable.

4. **Identify reference docs:** Look for task specs, API design, data model, architecture docs, business requirements, and dependency maps.
5. **Identify doc hierarchy:** Determine the source-of-truth ordering for conflicting docs (typically: project rules/AI instructions > API design > data model > architecture > business requirements > task specs).

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

### Step 3.1: Dispatch Validation Agents (MANDATORY)

**HARD BLOCK:** Dispatch specialist agents in parallel to validate the task spec. Each agent receives the task spec, reference docs, and the gaps/findings identified so far. The `worker` droid is always available as fallback, so this step is never skipped.

**Agent selection priority:**

1. **Ring review droids (preferred):**
   - `ring-default-business-logic-reviewer` — validate business rules completeness, edge cases, and domain correctness in the task spec
   - `ring-default-security-reviewer` — identify security gaps in the spec (missing auth, input validation, data exposure risks)
   - `ring-dev-team-qa-analyst` — validate testing strategy completeness, identify untested scenarios
   - `ring-default-code-reviewer` — assess architectural feasibility, identify patterns that may conflict with the codebase
2. **Other available review droids:** If Ring droids are not available, use any other review droids
3. **Worker droid with domain instructions (fallback):** Fall back to `worker` with domain-specific instructions — always available

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

1. **Announce total findings count:** Display `"### Total findings to review: N"` prominently before presenting the first finding
2. **Present the summary report** (tables from Output Format) for bird's-eye view
3. **Then present findings ONE AT A TIME** in priority order: contradictions > missing specs > test gaps > observability > DoD > ambiguities

**For EACH finding**, present with `"Finding X of N"` in the header:

#### Deep Research Before Presenting (MANDATORY)

**BEFORE presenting any finding to the user, you MUST research it deeply.** This research
is done SILENTLY — do not show the research process. Present only the conclusions.

**Research checklist (ALL items, every finding):**

1. **Project patterns:** Read related files fully, understand existing conventions
2. **Architectural decisions:** Review project rules (AGENTS.md, PROJECT_RULES.md, etc.) and architecture docs. Understand WHY the project is structured this way
3. **Existing codebase:** Search for precedent — if the codebase already handles similar cases, that context changes the finding's weight
4. **Current task focus:** Is this finding within the scope of the task spec being validated? Flag tangential findings as such
5. **User/consumer use cases:** Who will use this feature — end users, other services, internal modules? Trace impact to real user scenarios
6. **UX impact:** For user-facing features, evaluate usability, accessibility, error messaging, and workflows
7. **API best practices:** REST conventions, error handling, idempotency, status codes, pagination, versioning, backward compatibility
8. **Engineering best practices:** SOLID principles, DRY, separation of concerns, error handling, resilience, observability, testability
9. **Language-specific best practices:** Use `WebSearch` to research idioms for the specific language (Go, TypeScript, etc.) — official style guides, linter rules, community patterns
10. **Correctness over convenience:** Always recommend the correct approach, regardless of effort

**After research, form your recommendation:** Option A MUST be the approach you believe is correct based on all the research above, backed by evidence.

#### Present the Finding

- **Problem:** Clear description, referencing exact doc locations
- **Why it matters:** Impact analysis through four lenses:
  - **UX:** How does this affect the end user?
  - **Task focus:** Within task scope or tangential?
  - **Project focus:** MVP-critical or gold-plating?
  - **Engineering quality:** Maintainability, testability, reliability impact

#### Proposed Solutions (2-3 options)

**Option A MUST be your researched recommendation** — always prefer correctness over convenience.

```
**Option A: [name] (RECOMMENDED)**
[Concrete steps — what to change in the spec/docs]
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

#### Collect Decision

4. Use `AskUser` tool. **BLOCKING**: Do NOT advance to the next finding until the user decides
5. **CRITICAL — If the user responds with a question or disagreement instead of a decision:**
   - STOP immediately — do NOT continue to the next finding
   - Research the user's question/concern RIGHT NOW using `WebSearch`, codebase analysis, or both
   - Provide a thorough answer with evidence (links, code references, best practice citations)
   - Only AFTER the user is satisfied, ask for their decision again
   - This may go back and forth multiple times — that is expected and correct behavior
6. **Track all decisions** internally. Do NOT apply any fix yet — all fixes are applied in Step 5.

### Step 5: Phase 2 — Apply ALL Approved Corrections

After the user has responded to ALL findings:
1. Present a pre-apply summary listing every change grouped by file
2. Apply ALL approved changes to the docs in a single pass
3. Present a final summary of what was changed vs skipped/rejected

### Step 6: Commit Changes (if any modifications were made)

If any corrections were applied in Step 5:
1. Run `git status` and `git diff` to review all changes
2. Check for sensitive data (secrets, keys, tokens) — if found, STOP and warn the user
3. Present the summary of changes and ask the user for commit approval via `AskUser`
4. If approved, stage all modified files and commit using the task's Tipo for the conventional commit prefix (Feature→`feat`, Fix→`fix`, Refactor→`refactor`, Chore→`chore`, Docs→`docs`, Test→`test`). Example: `feat(T-003): fix spec — [brief summary of corrections]`
5. Run `git status` to confirm the commit succeeded

If no corrections were applied (all findings skipped), skip this step.

### Step 7: Convergence Loop (MANDATORY — fresh sub-agent re-validation)

After Step 6 completes (whether changes were committed or all findings were skipped), the validator MUST automatically re-validate. This catches both new gaps exposed by corrections AND issues missed in round 1 due to session bias.

**CRITICAL — Why Fresh Sub-Agents:**

The primary failure mode of convergence loops is **false convergence**: the orchestrator re-runs analysis in the same session, with the same mental model, and declares "zero new findings" — not because there are none, but because it can't see past its own prior reasoning. Escalating scrutiny via prose ("be more skeptical") does not reliably change LLM analysis depth.

The solution: **rounds 2+ are executed by a fresh sub-agent** dispatched via `Task` tool. The sub-agent has zero context from prior rounds, reads all files from scratch, and returns findings independently. The orchestrator then deduplicates against the cumulative ledger.

**Round structure:**

| Round | Who analyzes | How |
|-------|-------------|-----|
| **1** (initial) | Orchestrator (this agent) | Steps 1-3 + Step 3.1 (agent dispatch) — normal flow with full session context |
| **2** (mandatory) | **Fresh sub-agent** via `Task` | Sub-agent reads all files from scratch, analyzes independently, returns findings |
| **3-5** | **Fresh sub-agent** via `Task` | Same as round 2 — only triggered if round 2+ found new findings |

**Round 2 is MANDATORY.** The "zero new findings" stop condition can only trigger starting from round 3. This guarantees at least one fresh-eyes pass after the initial analysis.

**Fresh sub-agent dispatch (rounds 2+):**

Dispatch a single sub-agent via `Task` tool (use `worker` or any available review droid). The sub-agent receives:

1. **All relevant files** — task spec, reference docs, tasks.md, project rules (re-read fresh, not from cache)
2. **The findings ledger** — list of ALL findings from previous rounds with their resolutions (fixed/skipped/deferred), used ONLY for deduplication
3. **Analysis instructions** — the full validation dimensions (Steps 1-3) from this skill

```
Goal: Independent re-validation of task T-XXX spec (convergence round X of 5)

You are a FRESH reviewer with NO prior context. Analyze this task spec
from scratch as if you've never seen it before.

Context:
  - Task spec: [full task content — re-read from file]
  - Reference docs: [full content — re-read from files]
  - Project rules: [full content — re-read from files]

Analysis scope (execute ALL of these):
  1. Cross-reference task spec against all reference docs (fields, types, endpoints, error codes)
  2. Analyze test coverage gaps (unit, integration, E2E, cross-cutting) — enumerate every function/flow
  3. Analyze observability gaps (logging, metrics) — check against codebase patterns
  4. Validate Definition of Done completeness
  5. Check for ambiguities a developer would need to ask about

Previously identified findings (for DEDUP ONLY — do NOT let this bias your analysis):
  [list of findings with IDs and descriptions]

CRITICAL: Analyze INDEPENDENTLY. The previous findings list is ONLY for avoiding
duplicate reports. Do NOT skip areas just because previous rounds "already covered" them.
If you find the same issue, report it — the orchestrator will dedup.

Required output:
  For each finding: severity (CRITICAL/HIGH/MEDIUM/LOW), category, description,
  doc references, recommendation
  If no issues found: "PASS — all validation dimensions clean"
```

**Orchestrator deduplication after sub-agent returns:**

1. Compare each sub-agent finding against the cumulative ledger (match by file + topic + description similarity)
2. **Genuinely new findings** → add to ledger, present to user via Step 4
3. **Duplicates of already-resolved findings** → discard silently
4. **Duplicates of user-skipped findings** → discard silently (user already decided)

**Loop rules:**
- **Maximum rounds:** 5 (the initial run counts as round 1)
- **Round 2 is MANDATORY** — always dispatch a fresh sub-agent regardless of round 1 results
- **Progress indicator:** Show `"=== Re-validation round X of 5 (fresh sub-agent) ==="` at the start of each re-run
- **If new findings exist:** Present them using Step 4 (one at a time, collect decisions), apply via Step 5, commit via Step 6, then loop again (next round also uses fresh sub-agent)
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

**When the loop exits**, proceed to the Output Format section with the cumulative results from ALL rounds.

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
- If corrections were applied, ask the user for commit approval — do NOT commit without explicit approval
- Every finding must reference a specific doc section or standard — "I would do it differently" is not a valid finding
- BEFORE presenting each finding: deep research is MANDATORY — project patterns, architectural decisions, existing codebase, task focus, user/consumer use cases, UX impact, API best practices, engineering best practices, language-specific idioms. Option A must be the correct approach backed by research evidence, regardless of effort
- The agent NEVER decides whether a finding should be fixed or skipped — the USER always decides
- ALL findings (CRITICAL, HIGH, MEDIUM, and LOW) MUST be presented to the user for decision
- The agent may recommend an option, but MUST wait for user approval via AskUser before proceeding
- Do NOT auto-skip, auto-dismiss, or auto-resolve any finding regardless of severity
