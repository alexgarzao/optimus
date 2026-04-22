---
name: optimus-deep-review
description: "Parallel code review with consolidation, deduplication, and interactive finding-by-finding resolution. Supports initial (8 agents, critical gaps) and final (10 agents, full coverage including stack idiomaticity) review modes. Flexible scope: entire project, git diff, or specific directory."
trigger: >
  - When user requests code review (e.g., "review the code", "code review")
  - Before creating a pull request or merging a branch
  - After completing a feature and wanting quality validation
skip_when: >
  - Reviewing documentation only (use optimus-deep-doc-review instead)
  - Validating a specific task against its spec (use optimus-check instead)
  - Running automated checks only (use optimus-verify-code instead)
prerequisite: >
  - Project has source code to review
  - Code is accessible in the repository
NOT_skip_when: >
  - "Code already works" -- Working code can still have security issues, maintainability problems, and missing edge cases.
  - "It's a small change" -- Small changes can introduce regressions and security vulnerabilities.
  - "We'll review later" -- Later reviews accumulate debt and miss context.
  - "CI will catch it" -- CI catches syntax and test failures, not architectural or business logic issues.
examples:
  - name: Initial review during development
    invocation: "Review the code (initial)"
    expected_flow: >
      1. Ask scope (all files, git diff, directory)
      2. Dispatch 8 agents in parallel
      3. Consolidate and deduplicate findings
      4. Present overview table
      5. Walk through findings one by one
      6. Apply approved fixes
      7. Present summary
  - name: Final review before merge
    invocation: "Final code review before merge"
    expected_flow: >
      1. Ask scope
      2. Dispatch 10 agents in parallel (includes stack-specific agents)
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
    - optimus-build
    - optimus-pr-check
    - optimus-verify-code
  differentiation:
    - name: optimus-check
      difference: >
        optimus-check validates a completed task against its spec
        (acceptance criteria, test IDs, spec compliance). optimus-deep-review is
        a generic code review without task/spec context -- focused on code quality,
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

## Phase 1: Review Scope

Before starting, determine the review parameters.

### Step 1.1: Determine Review Type

Ask the user which type of review:

- **Initial** (recurring review during development): 8 agents, focused on correctness and critical gaps
- **Final** (review before merge/deployment): 10 agents, full coverage including stack idiomaticity

### Step 1.2: Determine Scope

Ask the user what to review:

- **All project files** — full codebase review
- **Changed files only** — use `git diff --name-only` to identify (optionally against a base branch)
- **Specific directory or feature** — user specifies the path

### Step 1.3: Load Context

1. **Identify stack:** Check for `go.mod`, `package.json`, `Makefile`, `Cargo.toml`, etc.
2. **Identify project rules and AI instructions (MANDATORY):** Execute project rules discovery — see AGENTS.md Protocol: Project Rules Discovery.
3. **Identify reference docs:** Look for PRD, TRD, API design, data model — these provide context but are not the primary validation target (unlike optimus-check)
4. **Read all files in scope:** Load the full content of every file that will be reviewed

---

## Phase 2: Parallel Agent Dispatch

Dispatch ALL applicable agents simultaneously via `Task` tool. Each agent receives file paths and can navigate the codebase autonomously.

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

### Initial Review (8 agents)

| # | Agent | Focus | Ring Droid |
|---|-------|-------|------------|
| 1 | **Code quality reviewer** | Architecture, design patterns, SOLID, DRY, maintainability, algorithmic flow, resilience, resource lifecycle, concurrency, performance, configuration, cognitive complexity, error handling, domain purity | `ring-default-code-reviewer` |
| 2 | **Business logic reviewer** | Domain correctness, business rules, edge cases, requirements compliance, spec traceability, data integrity, backward compatibility, API semantics | `ring-default-business-logic-reviewer` |
| 3 | **Security reviewer** | Vulnerabilities, authentication, input validation, OWASP, secrets, data privacy, error response leakage, rate limiting, auth propagation | `ring-default-security-reviewer` |
| 4 | **Test quality analyst** | Test coverage gaps (unit, integration, E2E), error scenario coverage, flaky patterns, test effectiveness, false positive risk, test coupling, spec traceability | `ring-default-ring-test-reviewer` |
| 5 | **Cross-file consistency** | Interfaces vs implementations, DTOs, imports, registered routes, shared constants, backward compatibility, configuration drift, migration paths, shared state, event contracts | `ring-default-ring-consequences-reviewer` |
| 6 | **Nil/Null safety reviewer** | Nil pointer risks, unsafe dereferences, missing guards, panic paths, resource cleanup nil checks, channel/map/slice safety | `ring-default-ring-nil-safety-reviewer` |
| 7 | **Dead code reviewer** | Orphaned code, unreachable branches, unused imports, commented-out code, zombie test infrastructure, stale feature flags, deprecated paths | `ring-default-ring-dead-code-reviewer` |
| 8 | **QA analyst** | Test strategy validation, scenario coverage, edge case identification, error path verification, testability assessment, operational readiness, AC coverage | `ring-dev-team-qa-analyst` |

### Final Review (10 agents — includes the 8 above plus)

| # | Agent | Focus | Ring Droid |
|---|-------|-------|------------|
| 9 | **Backend specialist** | Language idiomaticity, performance, concurrency, ecosystem patterns, graceful shutdown, connection pool sizing, context propagation, structured logging | `ring-dev-team-backend-engineer-golang` (Go) / `ring-dev-team-backend-engineer-typescript` (TS) |
| 10 | **Frontend specialist** | Framework patterns, hooks, components, accessibility, responsive design, performance, UX completeness (loading/empty/error states), i18n readiness | `ring-dev-team-frontend-engineer` |

### Agent Prompt Template

Each agent dispatch MUST include:

```
Goal: Code review — [validation domain]

Context:
  - Review type: Initial / Final
  - Project root: <absolute path to project worktree>
  - Scope: [files or directory being reviewed — list of file paths]
  - Project rules: AGENTS.md, PROJECT_RULES.md, docs/PROJECT_RULES.md (READ all that exist)
  - Reference docs: [list paths to any reference docs found] (READ if relevant to your domain)

IMPORTANT: You have access to Read, Grep, and Glob tools. USE THEM to:
  - Read files at the paths above
  - Search the codebase for patterns similar to the code under review
  - Find how the same problem was solved elsewhere in the project
  - Discover test patterns, error handling conventions, and architectural styles
  - Explore related files not listed above when needed for context

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

Cross-cutting analysis (MANDATORY for all agents):
  1. What would break in production under load with this code?
  2. What's MISSING that should be here? (not just what's wrong)
  3. Does this code trace back to a spec requirement? Flag orphan code without spec backing
  4. How would a new developer understand this code 6 months from now?
  5. Search the codebase for how similar problems were solved — flag inconsistencies with existing patterns
```

### Special Instructions per Agent

Include per-droid quality checklists — see AGENTS.md Protocol: Per-Droid Quality Checklists.

---

## Phase 3: Consolidation and Triage

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

## Phase 4: Present Overview

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

## Phase 5: Interactive Finding-by-Finding Resolution

Findings are presented ONE AT A TIME, decisions collected for ALL, then fixes applied ALL AT ONCE in Phase 6.

**=== MANDATORY — Progress Tracking (NEVER SKIP) ===**

**BEFORE presenting the first finding, you MUST:**
1. Count the TOTAL number of findings (N)
2. Display the total prominently: `"### Total findings to review: N"`

**For EVERY finding presented, you MUST:**
1. Include `"Finding X of N"` in the header
2. X starts at 1 and increments sequentially
3. N is the total announced above and NEVER changes mid-review

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
**Every AskUser MUST include a "Tell me more" option** alongside the fix/skip options.

**IMMEDIATE RESPONSE RULE:** If the user selects "Tell me more" or responds with free text
(a question, disagreement, or request for clarification) instead of a decision:
**STOP IMMEDIATELY.** Do NOT continue to the next finding. Do NOT batch the response.
Research the user's concern RIGHT NOW using `WebSearch`, codebase analysis, or both.
Provide a thorough answer with evidence. Only AFTER the user is satisfied, re-present the
options and ask for their decision again. **NEVER defer to the end of the findings loop.**

The user may:
- Approve an option (e.g., "A", "B")
- Select "Tell me more" for deeper analysis
- Discard the finding
- Defer to a future version
- Group with the next finding if related

### 5. After Decision

Record the decision internally. Do NOT apply any fix yet — all fixes are applied in Phase 6 after ALL decisions are collected.

- **Approved:** Record finding ID, chosen option. Move to next finding.
- **Discarded:** Record as discarded. Move to next finding.
- **Deferred:** Record destination (backlog, tasks). Move to next finding.

### Optimization for Simple Findings

For findings with a direct, unambiguous fix: present the problem + proposed fix + "Accept?" in a single block to speed up the flow.

**Same-nature grouping:** applied automatically per AGENTS.md "Finding Presentation" item 3.

---

## Phase 6: Batch Apply All Approved Fixes

**IMPORTANT:** This phase runs ONCE, after ALL findings have been presented and ALL decisions
collected in Phase 5. No fix is applied during Phase 5.

### Step 6.1: Present Pre-Apply Summary

```markdown
## Fixes to Apply (X of Y findings)

| # | Finding | Decision | Files Affected |
|---|---------|----------|---------------|

### Skipped (Z findings)
| # | Finding | Reason |
|---|---------|--------|

### Deferred (W findings)
| # | Finding | Destination |
|---|---------|-------------|
```

### Step 6.2: Apply Fixes

For each approved fix, apply the change. After each fix, confirm what changed in 1-2 sentences.

For fixes that alter execution flow, conditions, or observable behavior, run unit tests
after the fix to verify no regressions.

Check `.optimus/config.json` for custom commands before running any verification:

```bash
CONFIG_FILE=".optimus/config.json"
if [ -f "$CONFIG_FILE" ]; then
  LINT_CMD=$(jq -r '.commands.lint // empty' "$CONFIG_FILE")
  TEST_CMD=$(jq -r '.commands.test // empty' "$CONFIG_FILE")
fi
```

Use configured commands if present (empty string means skip that check). Fall back to
`make lint` / `make test` if `.optimus/config.json` is missing or the key is absent.

### Step 6.2.1: Handle Test Failures

If tests fail after applying a fix (maximum 3 attempts per fix):

1. **Logic bug** — adjust the fix, re-run tests
2. **Flaky test** — re-execute at least 3 times in a clean environment to confirm flakiness.
   Maximum 1 test skipped per fix. Document explicit justification (error message,
   flakiness evidence) and tag with `pending-test-fix`
3. **External dependency** — pause and wait for restoration

If tests fail after 3 attempts to fix, revert the offending fix and ask the user.

### Step 6.3: Final Lint Check

After ALL fixes are applied, run lint once (if available):
```bash
$LINT_CMD   # from .optimus/config.json, or fallback:
make lint
```
If lint fails, fix formatting issues.

### Step 6.4: Coverage Measurement

Measure coverage — see AGENTS.md Protocol: Coverage Measurement.
If coverage is below threshold, add findings to the results.

### Step 6.5: Test Scenario Gap Analysis

Dispatch a test gap analyzer via `Task` tool. Use `ring-default-ring-test-reviewer` or `ring-dev-team-qa-analyst`.

The agent receives file paths and can navigate the codebase autonomously.

```
Goal: Identify missing test scenarios in files changed during this review.

Context:
  - Project root: <absolute path to project worktree>
  - Changed source files: [list of file paths] (READ each file)
  - Test files: [list of test file paths] (READ each file)
  - Coverage profile: [coverage command output if available]

IMPORTANT: You have access to Read, Grep, and Glob tools. USE THEM to:
  - Read files at the paths above
  - Search for existing test patterns in the project
  - Find related test files not listed above
  - Discover how similar functions are tested elsewhere in the codebase

Your job:
  For each public function changed/added:
  1. Unit tests: check for happy path, error paths, edge cases, validation failures
  2. Integration tests: check for DB failure, timeout, retry, rollback scenarios
  3. Report what EXISTS and what is MISSING
  4. Test effectiveness: do tests verify BEHAVIOR or just mock internals? Flag false confidence tests
  5. Could these tests pass while the feature is actually broken?

Required output format:
  ## Unit Test Gaps
  | # | File | Function | Existing Scenarios | Missing Scenarios | Priority |
  |---|------|----------|--------------------|-------------------|----------|

  ## Integration Test Gaps
  | # | File | Function | Existing Scenarios | Missing Scenarios | Priority |
  |---|------|----------|--------------------|-------------------|----------|

  ## Test Effectiveness Issues
  | # | File | Test | Issue | Risk | Priority |
  |---|------|------|-------|------|----------|

  ## Summary
  - Functions analyzed: X
  - Fully covered: X | Partial: X | No tests: X
  - Missing scenarios: X HIGH, Y MEDIUM, Z LOW
  - Effectiveness issues: X
```

**HIGH priority gaps** are presented as findings for user decision (fix now or defer).

---

## Phase 7: Convergence Loop (MANDATORY)

Execute the convergence loop — see AGENTS.md "Common Patterns > Convergence Loop".

**Stage-specific scope for convergence rounds 2+:**
Dispatch the **same agent roster** from Phase 2 (all 8 or 10 agents depending on review type).
Each agent receives file paths and project rules (re-read fresh from disk). Do NOT include
the findings ledger in agent prompts — the orchestrator handles dedup using strict matching
(same file + same line range ±5 + same category).

Include the review type (Initial/Final) and scope from Phase 1, plus the cross-cutting
analysis instructions (same 5 items from Phase 2 prompt).

**Failure handling:** If any agent dispatch fails, treat that agent's slot as "zero findings"
for that round but warn the user. Do NOT fail the entire review.

When the loop exits, proceed to Phase 8 (Final Summary).

---

## Phase 8: Final Summary

After the convergence loop exits and all findings are processed:

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
- Ring droids are required — do not proceed without them
- Do NOT fix anything during agent dispatch or consolidation — fixes happen only in Phase 6 after user approval
- The agent NEVER decides whether a finding should be fixed or skipped — the USER always decides
- ALL findings (CRITICAL, HIGH, MEDIUM, and LOW) MUST be presented to the user for decision
- The agent may recommend an option, but MUST wait for user approval via AskUser before proceeding
- Do NOT auto-skip, auto-dismiss, or auto-resolve any finding regardless of severity
