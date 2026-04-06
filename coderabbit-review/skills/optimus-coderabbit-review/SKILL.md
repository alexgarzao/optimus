---
name: optimus-coderabbit-review
description: >
  CodeRabbit-driven code review with TDD fix cycle, secondary validation
  via parallel review agents for logic changes, and interactive finding-by-finding
  resolution. Runs CodeRabbit CLI to generate findings, then processes each
  with mandatory RED-GREEN-REFACTOR and full test execution.
trigger: >
  - When user requests code review using CodeRabbit
  - Before creating a pull request (when CodeRabbit is available)
  - When user wants TDD-driven fix cycle for code review findings
skip_when: >
  - CodeRabbit CLI is not installed or configured
  - No coderabbit config file exists (dot_coderabbit.yaml or .coderabbit.yaml)
  - User wants agent-only review without external tool (use optimus-deep-review instead)
prerequisite: >
  - CodeRabbit CLI installed and accessible
  - CodeRabbit config file exists (dot_coderabbit.yaml or .coderabbit.yaml)
  - Git repository with a base branch to compare against
NOT_skip_when: >
  - "CodeRabbit already ran in CI" → Local review catches issues before push, saving CI cycles.
  - "It's a small change" → Small changes still benefit from TDD-driven fixes.
  - "Tests already pass" → Passing tests don't guarantee CodeRabbit findings are addressed.
  - "We'll fix later" → TDD cycle ensures each fix is verified immediately.
examples:
  - name: Review against main branch
    invocation: "Run CodeRabbit review"
    expected_flow: >
      1. Execute CodeRabbit CLI against origin/main
      2. Parse and categorize findings by severity
      3. Present overview table
      4. Process each finding with TDD cycle
      5. Present final summary
  - name: Review against specific branch
    invocation: "CodeRabbit review against origin/develop"
    expected_flow: >
      1. Execute CodeRabbit CLI with custom base branch
      2. Standard flow
related:
  complementary:
    - optimus-deep-review
    - optimus-verify-code
  differentiation:
    - name: optimus-deep-review
      difference: >
        optimus-deep-review uses parallel specialist agents to generate findings.
        optimus-coderabbit-review uses CodeRabbit CLI as the source of findings
        and adds mandatory TDD cycle + secondary agent validation for logic changes.
    - name: optimus-post-task-validator
      difference: >
        optimus-post-task-validator validates a completed task against its spec.
        optimus-coderabbit-review is a generic review driven by CodeRabbit
        without task/spec context.
verification:
  automated:
    - command: "which coderabbit 2>/dev/null && echo 'available'"
      description: CodeRabbit CLI is installed
      success_pattern: available
  manual:
    - All findings presented to user
    - TDD cycle completed for each approved fix
    - All tests passing after fixes
    - Final summary presented
---

# CodeRabbit Review

CodeRabbit-driven code review with TDD fix cycle, secondary agent validation for logic changes, and interactive finding-by-finding resolution.

---

## Phase 0: Execute CodeRabbit

### Step 0.1: Discover Configuration

1. **Find config file:** Look for `dot_coderabbit.yaml`, `.coderabbit.yaml`, or equivalent
2. **Determine base branch:** Default to `origin/main`, or use user-specified branch
3. **Verify CLI:** Confirm `coderabbit` command is available

### Step 0.2: Run CodeRabbit

Execute the CodeRabbit CLI:

```bash
coderabbit review --prompt-only --base <base-branch> --plain --config <config-file>
```

Capture the full output for parsing.

### Step 0.3: Load Project Context

1. **Identify stack:** Check for `go.mod`, `package.json`, `Makefile`, `Cargo.toml`, etc.
2. **Identify test commands:** Look in `Makefile`, `package.json` scripts, or CI config for lint, unit test, integration test, and E2E test commands
3. **Identify coding standards:** Look for `PROJECT_RULES.md`, linter configs, or equivalent

Store discovered commands:
```
LINT_CMD=<discovered lint command>
TEST_UNIT_CMD=<discovered unit test command>
TEST_INTEGRATION_CMD=<discovered integration test command>
```

---

## Phase 1: Triage

### Step 1.1: Parse Findings

Parse the CodeRabbit output and categorize each finding by severity:

| Severity | Criteria |
|----------|----------|
| **CRITICAL** | Security vulnerability, data loss risk, auth bypass, broken business rule |
| **HIGH** | Missing validation, broken error handling, incorrect logic, missing tests for critical paths |
| **MEDIUM** | Code quality concern, pattern inconsistency, maintainability issue, missing edge case coverage |
| **LOW** | Polish, style, formatting, minor improvements |

### Step 1.2: Present Overview Table

```markdown
## CodeRabbit Review — X findings

| # | Severity | File | Line | Summary |
|---|----------|------|------|---------|
| 1 | CRITICAL | auth.go | 42 | ... |
| 2 | HIGH | handler.go | 88 | ... |

### Summary by Severity
- CRITICAL: X
- HIGH: X
- MEDIUM: X
- LOW: X
```

---

## Phase 2: Interactive Finding-by-Finding Resolution

Process ONE finding at a time, in severity order (CRITICAL first, LOW last).

For EACH finding, present:

### 1. Description

- What was found (problem identified)
- Relevant current code with context
- Impact/risk if not fixed

### 2. Severity

- Classification (CRITICAL/HIGH/MEDIUM/LOW) with justification

### 3. Proposed Solutions (2-3 options)

For each option:
- **Option A:** [description] — Tradeoffs: [pros and cons]
- **Option B:** [description] — Tradeoffs: [pros and cons]
- **Option C** (if applicable): [description] — Tradeoffs: [pros and cons]

For straightforward fixes with no ambiguity, state: "Direct fix, no tradeoffs."

### 4. Wait for User Decision

Use `AskUser` tool. **BLOCKING**: Do NOT proceed to the next finding until the user decides.

The user may:
- Accept one of the proposed options (e.g., "A", "B")
- Resolve differently (user describes approach)
- Ignore this issue (proceed without fixing)

---

## Phase 3: Fix with TDD + Agent Validation

For each approved fix (skipped for ignored findings):

### Step 3.1: Secondary Agent Validation (for logic changes only)

For fixes that alter execution flow, conditions, method calls, or observable behavior:

1. **Dispatch review agents in parallel** via `Task` tool. Use whatever review agents are available in the environment covering:
   - Code quality
   - Business logic correctness
   - Security
   - Test quality
   - Nil/null safety

2. **Skip agent validation** for purely cosmetic fixes (comments, rename, formatting, DRY without logic change)

3. **Handle conflicts between agents:** If two or more agents give contradictory feedback:
   - **Security conflicts:** Prioritize security > business-logic > code-quality
   - **Architectural conflicts:** Present both perspectives with tradeoffs (performance, maintainability, complexity, long-term impact) and recommend the option most aligned with project coding standards
   - **Implementation conflicts:** Prioritize code-quality > business-logic
   - In all cases: present both feedbacks to the user with priority recommendation and wait for decision before proceeding

### Step 3.2: TDD Cycle (mandatory)

For each approved fix:

1. **RED:** Write a failing test (if one doesn't already exist for the scenario)
2. **GREEN:** Implement the minimal fix
3. **REFACTOR:** Improve if necessary
4. **RUN ALL TESTS:** Execute unit + integration tests using discovered commands

### Step 3.3: Handle Test Failures

If tests fail after implementing the fix (maximum 3 attempts):

1. **Classify the failure:**
   - **Logic bug** → Return to RED phase, adjust test/fix
   - **Flaky/environmental test** → Before marking as skipped, re-execute the test at least 3 times in a clean environment to confirm flakiness. Maximum 1 test skipped per fix. Document explicit justification (error message, flakiness evidence) and tag with "pending-test-fix"
   - **Unavailable external dependency** → Pause and wait for restoration

2. **Do NOT proceed** to the next finding until all tests pass or the failure is classified and documented

### Step 3.4: Batching Independent Fixes

For PRs with many findings, independent fixes (in different modules/files) may be grouped in a single test cycle, as long as all tests pass before proceeding to the next group.

---

## Phase 4: Test Requirements

For each fix, ensure:

- **Unit tests:** Valid AND invalid scenarios covered
- **Integration tests:** When the fix involves API/DB interactions
- If opting not to implement a test, justify explicitly

---

## Phase 5: Final Summary

After processing all findings:

```markdown
## CodeRabbit Review — Summary

### Fixed (X findings)
| # | Severity | File | Fix Applied | Tests Added |
|---|----------|------|-------------|-------------|

### Ignored (X findings)
| # | Severity | File | Reason |
|---|----------|------|--------|

### Pending (X findings)
| # | Severity | File | Blocker |
|---|----------|------|---------|

### Test Results
- Unit tests: PASS (X tests)
- Integration tests: PASS / SKIPPED
- Skipped tests: X (with justification)

### Statistics
- Total findings: X
- Fixed: X
- Ignored: X
- Pending: X
- Files modified: [list]
```

**Do NOT commit automatically.** Present the summary and ask the user if they want to commit.

---

## Rules

- All findings are investigated, one at a time, in severity order (CRITICAL > HIGH > MEDIUM > LOW)
- No changes without prior user approval — the user ALWAYS decides the approach
- Ignored findings are recorded but not fixed
- Use review agents (Step 3.1) for logic changes; use codebase exploration for context investigation
- Prioritize correctness over convenience
- If a fix involves logic changes (flow, conditions, behavior), mention explicitly
- Follow project coding standards (PROJECT_RULES.md or equivalent)
- After each fix, update the todo list to maintain progress visibility
- TDD cycle is mandatory for every approved fix — no exceptions
- Do NOT proceed to the next finding until all tests pass or the failure is classified
- Maximum 3 retry attempts per test failure
- Maximum 1 skipped test per fix, with documented justification
