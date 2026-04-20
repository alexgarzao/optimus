---
name: optimus-cycle-impl-stage-2
description: >
  Stage 2 of the task lifecycle. Executes a validated task specification
  end-to-end: identifies the task, loads context, questions ambiguities upfront,
  then delegates execution to the dev-cycle skill (preferred) or uses a built-in
  fallback pipeline (implementation, review, verification, validation).
  Commits only after user approval.
trigger: >
  - After optimus-cycle-spec-stage-1 has PASSED for a task
  - When user requests full task execution with a task ID (e.g., "execute T-012")
  - When starting implementation of a validated task from a tasks file
skip_when: >
  - Already inside a dev-cycle execution (dev-cycle orchestrates its own gates)
  - Task is pure research or documentation (no code to verify)
  - No tasks file exists yet (use pre-dev workflow first)
prerequisite: >
  - Task exists in a tasks file (user provides ID or skill auto-detects next pending task)
  - Pre-task validation has passed
  - Reference docs exist (PRD, TRD, API design, data model)
  - Project rules file exists with coding standards
  - Project has lint, test, integration test, and E2E test commands configured
NOT_skip_when: >
  - "Task is simple" → Simple tasks still need the full dev-cycle gates.
  - "I already know the codebase" → Always explore before coding.
  - "Tests can come later" → dev-cycle enforces testing gates.
  - "Code review is optional" → dev-cycle Gate 4 is mandatory.
examples:
  - name: Execute a full-stack task
    invocation: "Execute task T-012"
    expected_flow: >
      1. User specified task ID — confirm with user
      2. Load context from reference docs
      3. Explore existing codebase patterns
      4. Ask all questions upfront
      5. Invoke dev-cycle to execute 6-gate pipeline
      6. Present summary and wait for commit approval
  - name: Execute next task (auto-detect)
    invocation: "Execute the next task"
    expected_flow: >
      1. Discover tasks file, identify next pending task
      2. Suggest to user and confirm via AskUser
      3. Standard execution flow via dev-cycle
  - name: Resume interrupted execution
    invocation: "Resume task T-012"
    expected_flow: >
      1. Invoke dev-cycle --resume
      2. dev-cycle resumes from last completed gate
related:
  complementary:
    - dev-cycle
    - dev-implementation
    - dev-testing
    - requesting-code-review
    - dev-validation
  differentiation:
    - name: dev-cycle
      difference: >
        dev-cycle is the 6-gate execution engine. optimus-cycle-impl-stage-2 is the
        preparation layer that handles task identification, context loading,
        upfront questioning, and codebase exploration BEFORE invoking dev-cycle.
        Use cycle-impl-stage-2 when you need the full workflow; use dev-cycle directly
        when context is already loaded and the task file path is known.
  sequence:
    after:
      - optimus-cycle-spec-stage-1
      - pre-dev-task-breakdown
      - pre-dev-subtask-creation
    before:
      - dev-feedback-loop
verification:
  automated:
    - command: "cat docs/dev-cycle/current-cycle.json 2>/dev/null | jq '.status'"
      description: dev-cycle state file tracks execution progress
      success_pattern: completed
  manual:
    - All 6 dev-cycle gates passed
    - Code review findings resolved or explicitly skipped
    - User approved final summary before commit
---

# Task Executor

Executes a validated task specification end-to-end: identifies the task, loads context, questions ambiguities upfront, then delegates execution to the dev-cycle skill for the 6-gate pipeline. Commits only after user approval.

---

## Phase 0: Load Context & Question Everything

### Step 0.0: Verify GitHub CLI (HARD BLOCK)

**HARD BLOCK:** Verify GitHub CLI — see AGENTS.md Protocol: GitHub CLI Check.

### Step 0.1: Find and Validate tasks.md

**HARD BLOCK:** Find and validate tasks.md — see AGENTS.md Protocol: tasks.md Validation.

### Step 0.2: Identify Task to Execute

**If the user specified a task ID** (e.g., "execute T-012"):
- Use the provided task ID
- Confirm with the user using `AskUser`: "I'll execute task T-012: [task title]. Correct?"

**If the user did NOT specify a task ID** (e.g., "execute the next task", or just invoked the skill):
1. **Identify the next task ready for implementation:** Scan the table for the first task that:
   - Has status `Validando Spec` (cycle-spec-stage-1 completed) or `Em Andamento` (re-execution)
   - Has all dependencies (Depends column) with status `**DONE**` (or Depends is `-`)
   - **Version priority:** prefer tasks from the `Ativa` version first. If none found, try `Próxima`. If none found, pick from any version and warn the user: "No eligible tasks in the active version (<name>). Suggesting T-XXX from version '<other>'."
2. **If multiple candidates exist in the same version priority**, pick the one with highest Priority (`Alta` > `Media` > `Baixa`), then lowest ID
3. **Suggest to the user** using `AskUser`: "I identified the next task to execute: T-XXX — [task title]. Is this correct, or would you like to execute a different task?"
4. **If no eligible tasks exist**, ask the user to provide a task ID

**BLOCKING**: Do NOT proceed until the user confirms which task to execute.

### Step 0.2.1: Check Session State

Execute session state protocol — see AGENTS.md Protocol: Session State. Use stage=`cycle-impl-stage-2`, status=`Em Andamento`.

**On stage completion** (after Phase 2 post-execution): delete the session file.

### Step 0.3: Validate and Update Task Status

**HARD BLOCK:** This step is mandatory. Do NOT skip it.

1. Read `tasks.md` and find the row for the confirmed task ID
2. Check the **Status** column:
   - If status is `Validando Spec` → proceed (cycle-spec-stage-1 has completed)
   - If status is `Em Andamento` → proceed (re-execution of this stage)
   - If status is `Pendente` → **STOP**: "Task T-XXX is in 'Pendente'. Run cycle-spec-stage-1 first."
   - If status is `Validando Impl`, `Revisando PR`, `**DONE**`, or `Cancelado` → **STOP**: "Task T-XXX is in '<status>'. It has already moved past this stage or was cancelled."
3. **Check dependencies (HARD BLOCK):** Read the Depends column for this task.
   - If Depends is `-` → proceed (no dependencies)
   - For each dependency ID listed, check its Status in the table:
     - If ALL dependencies have status `**DONE**` → proceed
     - If ANY dependency is NOT `**DONE**` → **STOP**:
       ```
       Task T-XXX depends on T-YYY (status: '<status>'). T-YYY must be **DONE** first.
       ```
4. **Expanded confirmation before status change:**
   - **If status will change** (current status is NOT `Em Andamento`) AND the user did NOT specify the task ID explicitly (auto-detect):
     - Read the task's H2 detail section (`## T-XXX: Title`) from `tasks.md`
     - Present to the user via `AskUser`:
       ```
       I'm about to change task T-XXX status from '<current>' to 'Em Andamento'.

       **T-XXX: [title]**
       **Version:** [version from table]
       **Objetivo:** [objective from detail section]
       **Critérios de Aceite:**
       - [ ] [criterion 1]
       - [ ] [criterion 2]
       ...

       Confirm status change?
       ```
     - **BLOCKING:** Do NOT change status until the user confirms
   - **If re-execution** (status is already `Em Andamento`) OR the user specified the task ID explicitly:
     - Skip expanded confirmation (user already has context)
5. Update the Status column to `Em Andamento` (if not already)
6. Commit the status change immediately:
   ```bash
   git add .optimus/tasks.md
   git commit -m "chore(tasks): set T-XXX status to Em Andamento"
   ```
7. Invoke notification hooks (event=`status-change`) — see AGENTS.md Protocol: Notification Hooks.

**Why commit immediately:** If the session is interrupted or the agent crashes before any code changes are committed, the status update would be lost. Committing now ensures the status change is persisted regardless of what happens during implementation.

### Step 0.3.1: Check tasks.md Divergence (warning)

Check tasks.md divergence — see AGENTS.md Protocol: Divergence Warning.

### Step 0.4: Verify Workspace

**HARD BLOCK:** Resolve workspace — see AGENTS.md Protocol: Workspace Auto-Navigation.

Branch-task cross-validation is part of the workspace protocol above.

### Step 0.5: Validate PR Title (if PR exists)

Validate PR title — see AGENTS.md Protocol: PR Title Validation.

### Step 0.6: Discover Project Structure

Before loading docs, discover the project's structure and tooling:

1. **Identify stack:** Check for `go.mod`, `package.json`, `Makefile`, `Cargo.toml`, etc.
2. **Identify test commands:** Look in `Makefile`, `package.json` scripts, or CI config for lint, test, integration test, and E2E test commands.
3. **Identify project rules and AI instructions (MANDATORY):** Execute project rules discovery — see AGENTS.md Protocol: Project Rules Discovery.

4. **Identify reference docs:** Look for `docs/pre-dev/`, `docs/`, or project-specific locations for tasks, PRD, TRD, API design, data model.

### Step 0.7: Load All Reference Documents

Read the discovered reference docs to build full context:
- Tasks file — the task being executed (find the task by ID)
- API contracts
- DB schema / data model
- Technical architecture (TRD)
- Business requirements (PRD)
- Coding standards / project rules
- Dependency relationships

### Step 0.8: Explore Existing Codebase

Before planning, understand what already exists:
- **Grep for existing patterns** in the relevant domain packages. Understand the handler/service/repository structure, error patterns, test patterns.
- **Check for migrations** and identify the latest migration number.
- **Check existing test files** for patterns (table-driven tests, testcontainers, Playwright fixtures, Vitest, etc.).

### Step 0.9: Identify and Ask ALL Questions Upfront

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

## Phase 1: Execute Implementation

After context is loaded and all questions are answered, execute the implementation.

### Step 1.0: Choose Execution Strategy

**Tipo-aware gate selection:** Not all task types need all gates. Before choosing the
execution strategy, check the task's **Tipo** column and adapt:

| Tipo | Skip Gates | Reason |
|------|-----------|--------|
| `Feature`, `Fix`, `Refactor` | None — run all gates | Code changes need full validation |
| `Chore` | Gate 1 (DevOps) may be the primary gate | Depends on task content |
| `Docs` | Gate 1 (DevOps), Gate 2 (SRE), Gate 3 (Testing) | No production code — skip TDD, coverage, observability |
| `Test` | Gate 1 (DevOps), Gate 2 (SRE) | Tests ARE the deliverable — skip DevOps and SRE but run Gate 3 for coverage |

When using the built-in fallback (Step 1.2), skip irrelevant steps based on the table above.
When using dev-cycle (Step 1.1), pass the Tipo so dev-cycle can adapt its gate execution.

Check if the `dev-cycle` skill is available in the current environment:

1. **If `dev-cycle` is available** → use it (preferred path, Step 1.1)
2. **If `dev-cycle` is NOT available** → use the built-in fallback (Step 1.2).
   **NOTE:** The built-in fallback covers Implementation (TDD), Code Review, Verification,
   and User Validation. It does NOT include DevOps (Docker/IaC), SRE (observability validation),
   or dedicated testing gates — those are only available via `dev-cycle`. This is acceptable
   for most tasks; install `dev-cycle` for full gate coverage.

### Step 1.1: Execute via dev-cycle (preferred)

Use the `Skill` tool to load and execute the dev-cycle:

```
Skill("dev-cycle")
```

Pass the tasks file path that contains the confirmed task. The dev-cycle handles:

| Gate | Purpose | Sub-Skill |
|------|---------|-----------|
| Gate 0 | Implementation (TDD) | dev-implementation |
| Gate 1 | DevOps (Docker, IaC) | dev-devops |
| Gate 2 | SRE (observability validation) | dev-sre |
| Gate 3 | Testing (unit tests, coverage ≥ 85%) | dev-testing |
| Gate 4 | Code Review (3+ parallel reviewers) | requesting-code-review |
| Gate 5 | Validation (user approval) | dev-validation |

Provide to dev-cycle:
- The tasks file path and confirmed task ID
- All reference docs discovered in Phase 0
- Codebase patterns found in Step 0.3
- Answers to all questions from Step 0.4
- Any user preferences or constraints mentioned during questioning

While dev-cycle executes:
- The dev-cycle manages its own state persistence, gate transitions, and agent dispatch
- If dev-cycle encounters a blocker or needs user input, it will handle it through its own flow
- Do NOT interfere with dev-cycle's gate execution — let it run its full pipeline

### Step 1.2: Built-in Fallback (when dev-cycle is unavailable)

When `dev-cycle` is not installed, execute implementation directly using the following
simplified pipeline. Each step dispatches specialist droids via `Task` tool.

#### Step 1.2.0: Detect Re-Execution (existing implementation)

**If this is a re-execution** (status was already `Em Andamento` when the skill started),
check if implementation files already exist from a previous run:

```bash
git diff --name-only $(git merge-base HEAD origin/$(git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's@^refs/remotes/origin/@@'))..HEAD
```

If changed files exist, ask via `AskUser`:
```
Previous implementation detected — N files were already changed on this branch.
How should I proceed?
```
Options:
- **Continue from current state** — review existing changes and build on them
- **Start fresh** — revert all changes and re-implement from scratch (`git reset --hard origin/<default>`)

If the user chooses "Continue from current state", pass the existing file list and their
content to the implementation droid with instructions: "These files already exist from a
previous run. Review, update, and complete them rather than creating from scratch."

#### Step 1.2.1: Implementation (TDD)

Dispatch a specialist droid to implement the task using TDD methodology:

**Droid selection (based on project stack):**
1. `ring-dev-team-backend-engineer-golang` — Go projects
2. `ring-dev-team-backend-engineer-typescript` — TypeScript projects
3. `ring-dev-team-frontend-engineer` — React/Next.js projects

**If no matching ring droid is available for the project stack, STOP:**
```
No ring implementation droid available for this stack. Install the appropriate droid:
  - Go: ring-dev-team-backend-engineer-golang
  - TypeScript: ring-dev-team-backend-engineer-typescript
  - React/Next.js: ring-dev-team-frontend-engineer
```

**The droid MUST:**
1. Follow TDD: write failing tests first, implement to pass, refactor
2. Follow project coding standards (from Step 0.1)
3. Implement EXACTLY what the task spec says — no more, no less
4. Run `make test` (or equivalent) to verify all tests pass

#### Step 1.2.2: Code Review

Dispatch parallel ring review droids via `Task` tool:

1. `ring-default-code-reviewer` — architecture, patterns, SOLID, DRY
2. `ring-default-business-logic-reviewer` — domain correctness, edge cases
3. `ring-default-security-reviewer` — vulnerabilities, OWASP, input validation

Present findings to the user ONE AT A TIME. For each finding:
- Show problem, impact, and 2-3 options
- Collect decision via `AskUser`
- Apply approved fixes via specialist droids

#### Step 1.2.3: Verification

Check for custom commands in `.optimus/config.json` first. If found, use configured
commands. If not found or key is missing, fall back to Makefile:

Run all available verification commands:

```bash
make lint                    # Lint — if target exists
make test                   # Unit tests — MANDATORY
make test-integration       # Integration tests — if target exists
make test-e2e               # E2E tests — if target exists
```

If any MANDATORY check fails, fix and retry (max 3 attempts). If optional checks fail,
warn the user but do not block.

#### Step 1.2.4: User Validation

Present a summary of what was implemented and ask for explicit approval via `AskUser`:
- Files created/modified
- Tests added
- Acceptance criteria coverage
- Verification results

---

## Phase 1.5: Update Acceptance Criteria Checkboxes

After Phase 1 completes (via dev-cycle or built-in fallback), update the acceptance criteria
checkboxes in tasks.md to reflect what was actually implemented.

**IMPORTANT:** This step runs AFTER implementation and verification complete but BEFORE
presenting the final summary. This ensures that when stage-3 (impl-review) runs, the
checkboxes in tasks.md already reflect what was implemented, preventing false findings
about mismatched checkbox state.

### Step 1.5.0: Reset Checkboxes on Re-Execution

**If this is a re-execution** (status was already `Em Andamento` when the skill started):
1. Read the task's detail section
2. **If the user chose "Start fresh" in Step 1.2.0:** Reset ALL checkboxes to unchecked
   (`- [ ]`) before re-evaluating. This prevents stale `[x]` marks from a previous
   partial run from persisting.
3. **If the user chose "Continue from current state" in Step 1.2.0:** Do NOT reset
   checkboxes. The existing `[x]` marks reflect work already completed in the previous
   run. Only evaluate and mark the remaining `[ ]` criteria.

### Step 1.5.1: Evaluate and Mark Checkboxes

1. Read the task's detail section and list all acceptance criteria (`- [ ] ...`)
2. For each criterion, verify whether the implementation satisfies it:
   - Check if the code/tests/config for that criterion exist and work
   - If satisfied → mark as `- [x]`
   - If NOT satisfied → leave as `- [ ]` and warn the user
3. Commit the updated checkboxes:
   ```bash
   git add .optimus/tasks.md
   git commit -m "chore(tasks): update acceptance criteria for T-XXX"
   ```

---

## Phase 2: Post-Execution

After implementation completes (via dev-cycle or built-in fallback):

### Step 2.1: Test Gap Cross-Reference

Review any test gaps identified during implementation:

1. **Search future tasks** in the tasks file to check if the test is planned for a later task
2. **If planned in a future task (T-XXX):**
   - Inform the user: "Test for [scenario] is planned in T-XXX: [task title]"
   - Provide your opinion on timing: should it be created now or deferred?
   - Ask via `AskUser`: "Do you want to anticipate this test in the current task, or keep it for T-XXX?"
3. **If NOT planned in any future task:**
   - Flag as a gap and recommend adding the test to the current task
4. Do NOT silently skip test gaps because they might be covered later — always verify and ask

### Step 2.2: Present Final Summary

Present a structured summary including:
- Task ID and title
- Files created and modified
- Tests added
- dev-cycle gate results (all 6 gates)
- Decisions made during questioning and review phases

### Step 2.3: Commit

Only after explicit user approval:

1. Run `git status` and `git diff --stat` to review
2. Run `git diff` to check for sensitive data (secrets, keys, tokens)
3. If clean, stage all relevant files and commit with a descriptive message
4. Run `git status` to confirm the commit succeeded

### Step 2.4: Push Commits (optional)

Offer to push commits — see AGENTS.md Protocol: Push Commits.

---

## Rules

### Scope Discipline
- Implement EXACTLY what the task spec says — no more, no less
- Do not refactor existing code unless the task requires it
- Do not fix unrelated bugs found during implementation (flag them to the user)
- Do not add "nice to have" improvements

### Error Handling
- If dev-cycle reports a blocker, present it to the user with context from Phase 0
- If you discover a gap in the task spec during Phase 0, ask the user before invoking dev-cycle

### Communication
- Update the todo list at Phase 0 completion and after dev-cycle finishes
- Report dev-cycle gate results as they complete
- Never go silent — if dev-cycle is running, inform the user of progress
- **Next step suggestion:** After the final commit, inform the user: "Implementation
  complete. Next step: run `/optimus-cycle-impl-review-stage-3` to validate this task."

### Dry-Run Mode
If the user requests a dry-run (e.g., "dry-run impl T-003", "preview implementation"):
- Run ALL discovery and context-loading phases (Phase 0) normally
- Present the implementation plan and all questions (Step 0.9)
- **Do NOT change task status** — skip Step 0.3 (status update)
- **Do NOT execute implementation** — skip Phase 1 entirely
- **Do NOT update checkboxes** — skip Phase 1.5
- **Do NOT commit or push anything** — skip Phase 2 commits
- Present a summary of: what would be implemented, estimated effort, identified risks
