---
name: optimus-deep-review
description: >
  Parallel code review with consolidation, deduplication, and interactive
  finding-by-finding resolution. Supports initial (5 agents, critical gaps)
  and final (7 agents, full coverage including stack idiomaticity) review modes.
  Flexible scope: entire project, git diff, or specific directory.
trigger: >
  - When user requests code review (e.g., "review the code", "code review")
  - Before creating a pull request or merging a branch
  - After completing a feature and wanting quality validation
skip_when: >
  - Reviewing documentation only (use optimus-deep-doc-review instead)
  - Validating a specific task against its spec (use optimus-post-task-validator instead)
  - Running automated checks only (use optimus-verify-code instead)
prerequisite: >
  - Project has source code to review
  - Code is accessible in the repository
NOT_skip_when: >
  - "Code already works" → Working code can still have security issues, maintainability problems, and missing edge cases.
  - "It's a small change" → Small changes can introduce regressions and security vulnerabilities.
  - "We'll review later" → Later reviews accumulate debt and miss context.
  - "CI will catch it" → CI catches syntax and test failures, not architectural or business logic issues.
examples:
  - name: Initial review during development
    invocation: "Review the code (initial)"
    expected_flow: >
      1. Ask scope (all files, git diff, directory)
      2. Dispatch 5 agents in parallel
      3. Consolidate and deduplicate findings
      4. Present overview table
      5. Walk through findings one by one
      6. Apply approved fixes
      7. Present summary
  - name: Final review before merge
    invocation: "Final code review before merge"
    expected_flow: >
      1. Ask scope
      2. Dispatch 7 agents in parallel (includes stack-specific agents)
      3. Consolidate, present, resolve findings
      4. Apply fixes, present summary
  - name: Review specific directory
    invocation: "Review the code in internal/handler/"
    expected_flow: >
      1. Scope already defined, ask review type
      2. Dispatch agents scoped to the directory
      3. Standard flow
related:
  complementary:
    - optimus-task-executor
    - optimus-verify-code
  differentiation:
    - name: optimus-post-task-validator
      difference: >
        optimus-post-task-validator validates a completed task against its spec
        (acceptance criteria, test IDs, spec compliance). optimus-deep-review is
        a generic code review without task/spec context — focused on code quality,
        security, and best practices.
    - name: optimus-verify-code
      difference: >
        optimus-verify-code runs automated checks (lint, vet, tests) and reports
        pass/fail. optimus-deep-review dispatches specialist agents for deep
        analysis that automated tools cannot catch.
  sequence:
    before:
      - optimus-verify-code
verification:
  manual:
    - All findings presented to user
    - Approved corrections applied correctly
    - Final summary presented
---

# Deep Review

Parallel code review with specialist agents, consolidation, deduplication, and interactive finding-by-finding resolution.

---

## Phase 0: Review Scope

Before starting, determine the review parameters.

### Step 0.1: Determine Review Type

Ask the user which type of review:

- **Initial** (recurring review during development): 5 agents, focused on correctness and critical gaps
- **Final** (review before merge/deployment): 7 agents, full coverage including stack idiomaticity

### Step 0.2: Determine Scope

Ask the user what to review:

- **All project files** — full codebase review
- **Changed files only** — use `git diff --name-only` to identify (optionally against a base branch)
- **Specific directory or feature** — user specifies the path

### Step 0.3: Load Context

1. **Identify stack:** Check for `go.mod`, `package.json`, `Makefile`, `Cargo.toml`, etc.
2. **Identify coding standards:** Look for `PROJECT_RULES.md`, `.editorconfig`, linter configs, or equivalent
3. **Identify reference docs:** Look for PRD, TRD, API design, data model — these provide context but are not the primary validation target (unlike optimus-post-task-validator)
4. **Read all files in scope:** Load the full content of every file that will be reviewed

---

## Phase 1: Parallel Agent Dispatch

Dispatch ALL applicable agents simultaneously via `Task` tool. Each agent receives the files in scope plus any reference docs found.

### Initial Review (5 agents)

| # | Agent | Focus |
|---|-------|-------|
| 1 | **Code quality reviewer** | Architecture, design patterns, SOLID, DRY, maintainability, algorithmic flow |
| 2 | **Business logic reviewer** | Domain correctness, business rules, edge cases, requirements compliance |
| 3 | **Security reviewer** | Vulnerabilities, authentication, input validation, OWASP, secrets |
| 4 | **Test quality analyst** | Test coverage gaps (unit, integration, E2E), error scenario coverage, flaky patterns |
| 5 | **Cross-file consistency** (worker) | Interfaces vs implementations, DTOs, imports, registered routes, shared constants, dead code |

### Final Review (7 agents — includes the 5 above plus)

| # | Agent | Focus |
|---|-------|-------|
| 6 | **Backend specialist** | Language idiomaticity, performance, concurrency, ecosystem patterns |
| 7 | **Frontend specialist** | Framework patterns, hooks, components, accessibility, responsive design, performance |

Use whatever specialist droids are available in the environment. If a specialized droid does not exist for a domain, use a `worker` agent with domain-specific instructions.

### Agent Prompt Template

Each agent dispatch MUST include:

```
Goal: Code review — [validation domain]

Context:
  - Review type: Initial / Final
  - Scope: [files or directory being reviewed]
  - Coding standards: [paste relevant sections]
  - Reference docs: [paste relevant sections if available]
  - Files to review (full content follows):
    [paste full content of each file with filename header]

Your job:
  Review the code for issues in your domain. Report issues ONLY — do NOT fix anything.

Required output format:
  For each issue found, provide:
  - Severity: CRITICAL / HIGH / MEDIUM / LOW
  - File: exact file path
  - Line: line number or range
  - Description: what is wrong and why it matters
  - Recommendation: concrete fix suggestion

  If no issues found, state "PASS — no issues in [domain]"
  Include a "What Was Done Well" section acknowledging good practices.
```

---

## Phase 2: Consolidation and Triage

After ALL agents return:

1. **Merge** all findings into a single list
2. **Deduplicate** — if multiple agents flag the same issue (same file + same concern), keep one entry and note which agents agreed
3. **Filter false positives** — verify in the code that each reported issue actually exists
4. **Sort** by severity: CRITICAL > HIGH > MEDIUM > LOW
5. **Assign** sequential IDs (F1, F2, F3...)

### Severity Classification

| Severity | Criteria |
|----------|----------|
| **CRITICAL** | Security vulnerability, data loss risk, auth bypass, broken business rule |
| **HIGH** | Missing validation, coding standards violation, missing error handling, broken accessibility |
| **MEDIUM** | Code quality concern, pattern inconsistency, maintainability issue, missing edge case test |
| **LOW** | Polish, minor style, optional improvement |

---

## Phase 3: Present Overview

Present the full findings table for a bird's-eye view:

```markdown
## Deep Review — X findings across Y agents

| # | Severity | File | Description | Agent(s) |
|---|----------|------|-------------|----------|
| F1 | CRITICAL | auth.go | ... | Security |
| F2 | HIGH | handler.go | ... | Code, QA |
| F3 | MEDIUM | layout.tsx | ... | Frontend, Cross-file |

### Summary by Severity
- CRITICAL: X
- HIGH: X
- MEDIUM: X
- LOW: X
```

---

## Phase 4: Interactive Finding-by-Finding Resolution

Present findings ONE AT A TIME, in severity order (CRITICAL first, LOW last).

For EACH finding, present:

### 1. Finding Header

`## [SEVERITY] F# | [Category]`
- Source agent(s)
- File and line number

### 2. Problem Description

- Clear description of the issue with code snippet if applicable
- Why it matters — what breaks, what risk it creates
- Reference to coding standard or best practice violated

### 3. Proposed Solutions

One or more approaches, each with:
- What changes
- Tradeoffs (complexity, performance, breaking changes)
- If it's a straightforward fix with no tradeoffs, state explicitly: "Direct fix, no tradeoffs."

Include a recommendation when one option is clearly better.

### 4. Wait for User Decision

Use `AskUser` tool. **BLOCKING**: Do NOT advance to the next finding until the user decides.

The user may:
- Approve an option (e.g., "A", "B")
- Request more context
- Discard the finding
- Defer to a future version
- Group with the next finding if related

### 5. After Decision

- **Approved:** Implement the fix immediately, confirm what changed in 1-2 sentences, move to next
- **Discarded:** Record as discarded, move to next
- **Deferred:** Add note in the appropriate location (backlog, tasks), move to next

### Optimization for Simple Findings

For findings with a direct, unambiguous fix: present the problem + proposed fix + "Accept?" in a single block to speed up the flow.

### Batch Processing

If there are 3+ findings of the same nature (e.g., "inconsistent import path in 5 files"), group them and present as a batch with the list of affected files. Ask if all can be applied at once.

---

## Phase 5: Final Summary

After processing all findings:

```markdown
## Deep Review — Summary

### Fixed (X findings)
| # | Severity | File(s) | Fix Applied |
|---|----------|---------|-------------|

### Discarded (X findings)
| # | Severity | File(s) | Reason |
|---|----------|---------|--------|

### Deferred (X findings)
| # | Severity | File(s) | Destination |
|---|----------|---------|-------------|

### Statistics
- Total findings: X
- Fixed: X
- Discarded: X
- Deferred: X
- Files modified: [list]
```

**Do NOT commit automatically.** Present the summary and wait for the user to decide whether to commit.

---

## Rules

- Every finding must reference a specific standard, best practice, or measurable risk — "I would do it differently" is NOT a valid finding
- One finding at a time, severity order (CRITICAL > HIGH > MEDIUM > LOW)
- No changes without explicit user approval
- Prioritize correctness over convenience
- If a fix involves logic changes (flow, conditions, behavior), mention explicitly
- Follow coding standards found in the project (PROJECT_RULES.md or equivalent)
- After each fix, update the todo list to maintain progress visibility
- If the codebase already does the same thing elsewhere without issue, it is NOT a finding
- Use whatever specialist droids are available in the environment; fall back to `worker` with domain instructions
- Do NOT fix anything during agent dispatch or consolidation — fixes happen only in Phase 4 after user approval
