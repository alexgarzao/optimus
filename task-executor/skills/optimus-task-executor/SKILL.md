---
name: optimus-task-executor
description: >
  Executes a validated task specification end-to-end: identifies the task,
  loads context, questions ambiguities upfront, then delegates execution
  to the dev-cycle skill which handles the 6-gate pipeline (implementation,
  devops, SRE, testing, review, validation). Commits only after user approval.
trigger: >
  - After optimus-pre-task-validator has PASSED for a task
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
        dev-cycle is the 6-gate execution engine. optimus-task-executor is the
        preparation layer that handles task identification, context loading,
        upfront questioning, and codebase exploration BEFORE invoking dev-cycle.
        Use task-executor when you need the full workflow; use dev-cycle directly
        when context is already loaded and the task file path is known.
  sequence:
    after:
      - optimus-pre-task-validator
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

### Step 0.0: Identify Task to Execute

Determine which task to execute:

**If the user specified a task ID** (e.g., "execute T-012"):
- Use the provided task ID
- Confirm with the user using `AskUser`: "I'll execute task T-012: [task title]. Correct?"

**If the user did NOT specify a task ID** (e.g., "execute the next task", or just invoked the skill):
1. **Find the tasks file:** Look for task specs in `docs/`, `docs/pre-dev/`, or equivalent (files named `tasks.md`, `tasks/*.md`, or similar)
2. **Identify the next pending task:** Scan the tasks file for the first task that:
   - Has status "pending", "todo", "not started", or no status marker
   - Has all dependencies (required tasks) marked as "completed" or "done"
   - Is not blocked by other tasks
3. **If multiple candidates exist**, pick the one with the lowest ID (or earliest in the file)
4. **Suggest to the user** using `AskUser`: "I identified the next task to execute: T-XXX — [task title]. Is this correct, or would you like to execute a different task?"
5. **If no tasks file is found or no pending tasks exist**, ask the user to provide a task ID

**BLOCKING**: Do NOT proceed until the user confirms which task to execute.

### Step 0.1: Discover Project Structure

Before loading docs, discover the project's structure and tooling:

1. **Identify stack:** Check for `go.mod`, `package.json`, `Makefile`, `Cargo.toml`, etc.
2. **Identify test commands:** Look in `Makefile`, `package.json` scripts, or CI config for lint, test, integration test, and E2E test commands.
3. **Identify reference docs:** Look for `docs/pre-dev/`, `docs/`, or project-specific locations for tasks, PRD, TRD, API design, data model, and coding standards.

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

## Phase 1: Execute via dev-cycle

After context is loaded and all questions are answered, delegate execution to the `dev-cycle` skill.

### Step 1.1: Invoke dev-cycle

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

### Step 1.2: Provide Context to dev-cycle

When dev-cycle starts, provide:
- The tasks file path and confirmed task ID
- All reference docs discovered in Phase 0
- Codebase patterns found in Step 0.3
- Answers to all questions from Step 0.4
- Any user preferences or constraints mentioned during questioning

### Step 1.3: Monitor and Support

While dev-cycle executes:
- The dev-cycle manages its own state persistence, gate transitions, and agent dispatch
- If dev-cycle encounters a blocker or needs user input, it will handle it through its own flow
- Do NOT interfere with dev-cycle's gate execution — let it run its full pipeline

---

## Phase 2: Post-Execution

After dev-cycle completes all 6 gates (Gate 5 passes with user approval):

### Step 2.1: Test Gap Cross-Reference

Review any test gaps identified during dev-cycle execution:

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
