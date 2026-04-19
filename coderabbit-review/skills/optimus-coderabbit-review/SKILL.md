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
  - No coderabbit config file exists (.coderabbit.yaml)
  - User wants agent-only review without external tool (use optimus-deep-review instead)
prerequisite: >
  - CodeRabbit CLI installed and accessible
  - CodeRabbit config file exists (.coderabbit.yaml)
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

1. **Find config file:** Look for `.coderabbit.yaml` in the project root
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
3. **Identify project rules and AI instructions (MANDATORY):** Search for these files and read ALL that exist:
   - `AGENTS.md`, `CLAUDE.md`, `DROIDS.md`, `.cursorrules` (repo root)
   - `PROJECT_RULES.md` (repo root or `docs/`)
   - `.editorconfig`, `docs/coding-standards.md`, `docs/conventions.md`
   - `.github/CONTRIBUTING.md` or `CONTRIBUTING.md`
   - Linter configs: `.eslintrc*`, `biome.json`, `.golangci.yml`, `.prettierrc*`

   These are the **source of truth** for coding standards. Pass relevant sections to every agent dispatched.

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
- Severity classification (CRITICAL/HIGH/MEDIUM/LOW) with justification

### 2. Impact Analysis (four lenses)

Evaluate the finding through all four perspectives to help the user make an informed decision:

- **User (UX):** How does this affect the end user? Usability degradation, confusion, broken workflow, accessibility issue? Would the user notice? Would it block their work?
- **Task focus:** Does this finding relate to the changes being reviewed? Is it within scope, or a tangential concern that should be a separate effort?
- **Project focus:** Is this MVP-critical, or gold-plating? Does ignoring it now create rework later? Does it conflict with the project's priorities?
- **Engineering quality:** Does this hurt maintainability, testability, reliability, or codebase consistency? What is the technical debt cost of skipping it?

### 3. Proposed Solutions (2-3 options)

For each option, evaluate all four lenses:

```
**Option A: [name]**
[What to do — concrete steps, files to change]
- UX: [impact on the end user's experience]
- Task focus: [within scope / tangential]
- Project focus: [MVP-aligned / nice-to-have / out-of-scope]
- Engineering: [pros and cons — complexity, maintainability, test coverage, consistency]
- Effort: [trivial (< 5 min) / small (5-15 min) / moderate (15-60 min) / large (> 1h)]
```

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

1. **Dispatch review agents in parallel** via `Task` tool. Use the agent selection priority below:

**Agent selection priority:**

1. **Ring review droids (preferred when available):**
   - `ring-default-code-reviewer` → Code quality, architecture, patterns
   - `ring-default-business-logic-reviewer` → Domain correctness, edge cases
   - `ring-default-security-reviewer` → Vulnerabilities, OWASP, input validation
   - `ring-default-ring-test-reviewer` → Test coverage gaps, test quality
   - `ring-default-ring-nil-safety-reviewer` → Nil/null pointer risks, unsafe dereferences
   - `ring-default-ring-consequences-reviewer` → Ripple effects beyond changed files
   - `ring-default-ring-dead-code-reviewer` → Orphaned code from changes
2. **Other available specialist droids**
3. **Worker droid with domain instructions** — as fallback

| Domain | When to Dispatch | Preferred Ring Droid |
|--------|-----------------|---------------------|
| **Code Quality** | Always | `ring-default-code-reviewer` |
| **Business Logic** | Always | `ring-default-business-logic-reviewer` |
| **Security** | Always | `ring-default-security-reviewer` |
| **Test Quality** | Always | `ring-default-ring-test-reviewer` |
| **Nil/Null Safety** | Always (if droid available) | `ring-default-ring-nil-safety-reviewer` |
| **Ripple Effects** | Always (if droid available) | `ring-default-ring-consequences-reviewer` |
| **Dead Code** | Always (if droid available) | `ring-default-ring-dead-code-reviewer` |

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

## Phase 4: Coverage Verification and Test Gap Analysis

After all findings have been processed through the TDD cycle:

### Step 4.1: Coverage Measurement

Measure test coverage for the changed files:

**Unit test coverage:**
```bash
go test -coverprofile=coverage-unit.out ./...
go tool cover -func=coverage-unit.out | tail -1
```

**Integration test coverage (if applicable):**
```bash
go test -tags=integration -coverprofile=coverage-integration.out ./...
go tool cover -func=coverage-integration.out | tail -1
```

**Untested functions:**
```bash
go tool cover -func=coverage-unit.out | grep "0.0%"
```

**Thresholds:**
- Unit tests: 85% minimum
- Integration tests: 70% minimum

If coverage is below threshold, flag as a finding:
- **HIGH** severity for unit test coverage below 85%
- **MEDIUM** severity for integration test coverage below 70%
- List untested business-logic functions as individual **HIGH** findings

**E2E tests:** If not configured, ask the user using `AskUser`:
"E2E tests are not configured. Should they be implemented, or skip for now?"

### Step 4.2: Test Scenario Gap Analysis

Dispatch an agent to identify missing test scenarios in the changed files.

**Dispatch a test gap analyzer** via `Task` tool. Use `ring-default-ring-test-reviewer`, `ring-dev-team-qa-analyst`, or `worker` (in that priority order).

The agent receives:
1. **Changed source files** — full content (non-test files only)
2. **Test files for changed source** — full content
3. **Coverage profile** — `go tool cover -func` output

```
Goal: Identify missing test scenarios in files changed during this review.

Context:
  - Source files changed: [full content]
  - Test files: [full content]
  - Coverage profile: [go tool cover -func output]

Your job:
  For each public function changed/added:
  1. Unit tests: check for happy path, error paths, edge cases, validation failures
  2. Integration tests: check for DB failure, timeout, retry, rollback scenarios
  3. Report what EXISTS and what is MISSING

Required output format:
  ## Unit Test Gaps
  | # | File | Function | Existing Scenarios | Missing Scenarios | Priority |
  |---|------|----------|--------------------|-------------------|----------|

  ## Integration Test Gaps
  | # | File | Function | Existing Scenarios | Missing Scenarios | Priority |
  |---|------|----------|--------------------|-------------------|----------|

  ## Summary
  - Functions analyzed: X
  - Fully covered: X | Partial: X | No tests: X
  - Missing scenarios: X HIGH, Y MEDIUM, Z LOW
```

**HIGH priority gaps** are presented as findings for user decision (fix now or defer).

---

## Phase 5: Convergence Loop (MANDATORY — automatic re-validation with escalating scrutiny)

After Phase 4 completes, the reviewer MUST automatically re-run CodeRabbit and agent validation on the updated code. This catches new issues introduced by the fixes just applied.

**CRITICAL — Escalating Scrutiny Per Round:**

The primary failure mode of convergence loops is that re-running the same analysis with the same depth produces the same results (minus already-seen findings), leading to false convergence. To prevent this, EACH round MUST escalate its level of scrutiny:

| Round | Scrutiny Level | Focus |
|-------|---------------|-------|
| **1** (initial) | Standard analysis | Normal CodeRabbit + agent validation |
| **2** | Skeptical re-read | For each domain, ask: "What did I accept as correct in round 1 that I should question?" Re-read code with the assumption that something was missed. Check function-by-function, branch-by-branch instead of scanning |
| **3** | Adversarial analysis | Actively try to break the code: invent edge cases, look for implicit assumptions, check what happens when inputs are nil/empty/zero, when concurrent requests hit the same path, when external services fail |
| **4** | Cross-cutting deep dive | Focus on interactions BETWEEN domains: does the test coverage actually exercise the security-sensitive paths? Do the fixes from previous rounds introduce new consistency issues? |
| **5** | Final sweep | Review ALL previously skipped/deferred findings with fresh eyes — should any be reconsidered? Check the cumulative changes for internal consistency |

**Re-run CodeRabbit and re-dispatch agents with escalated prompts:**

```
This is re-validation round X of 5. In previous rounds, the following findings
were already identified and resolved:
[list of previous findings with resolutions]

Your job NOW is to look DEEPER — not repeat what was already found.
Specifically:
- Question assumptions: what did round 1 accept that might be wrong?
- Check interactions: do the fixes from previous rounds create new issues?
- Look for subtle issues: off-by-one errors, race conditions, missing error
  propagation, implicit type coercions, nil dereferences in rare paths
- Examine what was NOT flagged: absence of validation, missing constraints,
  undocumented behavior, untested error paths

Do NOT report findings that match any previously identified finding.
Only report genuinely NEW issues.
```

**Loop rules:**
- **Maximum rounds:** 5 (the initial run counts as round 1)
- **Progress indicator:** Show `"=== Re-validation round X of 5 (scrutiny: <level>) ==="` at the start of each re-run
- **Scope:** Re-run CodeRabbit CLI, re-dispatch agents with escalated prompts, re-measure coverage. Do NOT re-load project context (Phase 0)
- **Finding deduplication:** Maintain a ledger of ALL findings from ALL previous rounds (by ID and description). Only present findings that are NEW — not already seen, resolved, or skipped in a prior round. If a finding was skipped/discarded by the user in a prior round, do NOT re-present it
- **If new findings exist:** Present them using Phase 2 (interactive resolution), fix via Phase 3 (TDD cycle), verify via Phase 4 (coverage), then loop again
- **Stop conditions (any one triggers exit):**
  1. Zero new findings in the current round (after escalated scrutiny — this is genuine convergence)
  2. Round 5 completed (hard limit)
  3. User explicitly requests to stop (via AskUser response)
  
  **IMPORTANT:** LOW severity findings are NOT a reason to stop. ALL findings regardless of severity MUST be presented to the user for decision. The agent NEVER decides that LOW findings can be skipped.

**Round summary (show after each round):**

```markdown
### Round X of 5 (scrutiny: <level>) — Summary
- New findings this round: N (C critical, H high, M medium, L low)
- Cumulative: X total findings across Y rounds
- Fixed: A | Skipped: B | Deferred: C
- Status: CONVERGED / CONTINUING / HARD LIMIT REACHED
```

**When the loop exits**, proceed to the Final Summary with the cumulative results from ALL rounds.

---

## Phase 6: Final Summary

After the convergence loop exits:

```markdown
## CodeRabbit Review — Summary

### Convergence
- Rounds executed: X of 5
- Status: CONVERGED / HARD LIMIT REACHED

### Fixed (X findings)
| # | Severity | File | Fix Applied | Tests Added | Round |
|---|----------|------|-------------|-------------|-------|

### Ignored (X findings)
| # | Severity | File | Reason | Round |
|---|----------|------|--------|-------|

### Pending (X findings)
| # | Severity | File | Blocker | Round |
|---|----------|------|---------|-------|

### Test Coverage
- Unit tests: XX.X% (threshold: 85%) — PASS / FAIL
- Integration tests: XX.X% (threshold: 70%) — PASS / FAIL
- Untested functions: X (Y business logic, Z infrastructure)
- E2E tests: Configured / Not configured

### Test Results
- Unit tests: PASS (X tests)
- Integration tests: PASS / SKIPPED
- E2E tests: PASS / SKIPPED
- Skipped tests: X (with justification)

### Statistics
- Total findings: X (across Y rounds)
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
- The agent NEVER decides whether a finding should be fixed or skipped — the USER always decides
- ALL findings (CRITICAL, HIGH, MEDIUM, and LOW) MUST be presented to the user for decision
- The agent may recommend an option, but MUST wait for user approval via AskUser before proceeding
- Do NOT auto-skip, auto-dismiss, or auto-resolve any finding regardless of severity
