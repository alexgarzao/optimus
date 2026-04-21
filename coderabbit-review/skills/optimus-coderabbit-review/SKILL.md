---
name: optimus-coderabbit-review
description: "CodeRabbit-driven code review with TDD fix cycle, secondary validation via parallel review agents for logic changes, and interactive finding-by-finding resolution. Runs CodeRabbit CLI to generate findings, then processes each with mandatory RED-GREEN-REFACTOR and full test execution."
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
  - "CodeRabbit already ran in CI" -- Local review catches issues before push, saving CI cycles.
  - "It's a small change" -- Small changes still benefit from TDD-driven fixes.
  - "Tests already pass" -- Passing tests don't guarantee CodeRabbit findings are addressed.
  - "We'll fix later" -- TDD cycle ensures each fix is verified immediately.
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
    - name: optimus-check
      difference: >
        optimus-check validates a completed task against its spec.
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

## Phase 1: Execute CodeRabbit

### Step 1.1: Discover Configuration

1. **Find config file:** Look for `.coderabbit.yaml` in the project root
2. **Determine base branch:** Default to `origin/main`, or use user-specified branch
3. **Verify CLI:** Confirm `coderabbit` command is available

### Step 1.2: Run CodeRabbit

Check if the CodeRabbit CLI is available:

```bash
which coderabbit 2>/dev/null || which coderabbit-cli 2>/dev/null
```

**If CodeRabbit CLI is available:** Execute the CLI:

```bash
coderabbit review --prompt-only --base <base-branch> --plain --config <config-file>
```

Capture the full output for parsing.

**If CodeRabbit CLI is NOT available:** Inform the user and offer a fallback:

```
CodeRabbit CLI is not installed. To install it:
  npm install -g coderabbit

Alternatively, I can run a code review using specialist agents instead (same as /optimus-deep-review).
```

Ask via `AskUser`:
- **Install CodeRabbit** — show installation instructions and retry
- **Fall back to agent review** — proceed with a deep-review style agent dispatch (skip Phase 2 parsing, go directly to Phase 3 interactive resolution with parallel agent findings)
- **Cancel** — stop the review

If the user chooses the fallback, dispatch the same agents used by `optimus-deep-review`
(code quality, business logic, security, test quality, cross-file consistency) and follow
the same interactive resolution flow from Phase 3 onward.

### Step 1.3: Load Project Context

1. **Identify stack:** Check for `go.mod`, `package.json`, `Makefile`, `Cargo.toml`, etc.
2. **Identify test commands:** Look in `Makefile`, `package.json` scripts, or CI config for lint, unit test, integration test, and E2E test commands
3. **Identify project rules and AI instructions (MANDATORY):** Execute project rules discovery — see AGENTS.md Protocol: Project Rules Discovery.

Store discovered commands:
```
LINT_CMD=<discovered lint command>
TEST_UNIT_CMD=<discovered unit test command>
TEST_INTEGRATION_CMD=<discovered integration test command>
```

---

## Phase 2: Triage

### Step 2.1: Parse Findings

Parse the CodeRabbit output. The output may contain three types of findings:

1. **Regular findings** — inline suggestions about code within the diff. Tag as `origin: inline`.
2. **Duplicate comments** — findings CodeRabbit already reported in previous reviews that remain unresolved. Look for a `<details>` block titled "Duplicate comments" in the output. Parse each entry and tag as `origin: duplicate`.
3. **Outside diff range comments** — suggestions about code OUTSIDE the reviewed diff. Look for a `<details>` block titled `⚠️ Outside diff range comments` in the output. Parse each entry (file path, line, suggestion) and tag as `origin: outside-diff`.

Categorize ALL findings (regardless of origin) by severity:

| Severity | Criteria |
|----------|----------|
| **CRITICAL** | Security vulnerability, data loss risk, auth bypass, broken business rule |
| **HIGH** | Missing validation, broken error handling, incorrect logic, missing tests for critical paths |
| **MEDIUM** | Code quality concern, pattern inconsistency, maintainability issue, missing edge case coverage |
| **LOW** | Polish, style, formatting, minor improvements |

### Step 2.2: Present Overview Table

```markdown
## CodeRabbit Review — X findings

| # | Severity | Origin | File | Line | Summary |
|---|----------|--------|------|------|---------|
| 1 | CRITICAL | inline | auth.go | 42 | ... |
| 2 | HIGH | DUPLICATE | handler.go | 88 | (reported in previous review) ... |
| 3 | MEDIUM | OUTSIDE PR DIFF | config.go | 15 | (outside this PR's changes) ... |

### Summary by Severity
- CRITICAL: X
- HIGH: X
- MEDIUM: X
- LOW: X

### Summary by Origin
- Inline (within diff): X
- Duplicate (from previous reviews): X
- Outside PR diff: X
```

---

## Phase 3: Interactive Finding-by-Finding Resolution (collect decisions only)

**BEFORE presenting the first finding:** Announce total findings count prominently: `"### Total findings to review: N"`

Process ONE finding at a time, in severity order (CRITICAL first, LOW last). Collect ALL decisions first — do NOT apply any fix during this phase.

For EACH finding, present with `"Finding X of N"` in the header, including the origin tag:
- Regular: `## Finding X of N — [SEVERITY] | CodeRabbit | Category`
- Duplicate: `## Finding X of N — [SEVERITY] | CodeRabbit — DUPLICATE | Category`
- Outside diff: `## Finding X of N — [SEVERITY] | CodeRabbit — OUTSIDE PR DIFF | Category`

### 1. Deep Research Before Presenting (MANDATORY)

**BEFORE presenting any finding to the user, you MUST research it deeply.** This research
is done SILENTLY — do not show the research process. Present only the conclusions.

**Research checklist (ALL items, every finding):**

1. **Project patterns:** Read the affected file(s) fully, understand the patterns used, check how similar cases are handled elsewhere in the codebase
2. **Architectural decisions:** Review project rules (AGENTS.md, PROJECT_RULES.md, etc.) and architecture docs. Understand WHY the project is structured this way
3. **Existing codebase:** Search for precedent — if the codebase already does the same thing in other places, that context changes the finding's weight
4. **Current task focus:** Is this finding within the scope of the changes being reviewed? Flag tangential findings as such
5. **User/consumer use cases:** Who consumes this code — end users, other services, internal modules? Trace impact to real user scenarios
6. **UX impact:** For user-facing changes, evaluate usability, accessibility, error messaging, and workflows
7. **API best practices:** REST conventions, error handling, idempotency, status codes, pagination, versioning, backward compatibility
8. **Engineering best practices:** SOLID principles, DRY, separation of concerns, error handling, resilience, observability, testability
9. **Language-specific best practices:** Use `WebSearch` to research idioms for the specific language (Go, TypeScript, etc.) — official style guides, linter rules, community patterns
10. **Correctness over convenience:** Always recommend the correct approach, regardless of effort

**After research, form your recommendation:** Option A MUST be the approach you believe is correct based on all the research above, backed by evidence.

### 2. Description

- What was found (problem identified)
- Relevant current code with context
- Severity classification (CRITICAL/HIGH/MEDIUM/LOW) with justification

### 3. Impact Analysis (four lenses)

Evaluate the finding through all four perspectives to help the user make an informed decision:

- **User (UX):** How does this affect the end user? Usability degradation, confusion, broken workflow, accessibility issue? Would the user notice? Would it block their work?
- **Task focus:** Does this finding relate to the changes being reviewed? Is it within scope, or a tangential concern that should be a separate effort?
- **Project focus:** Is this MVP-critical, or gold-plating? Does ignoring it now create rework later? Does it conflict with the project's priorities?
- **Engineering quality:** Does this hurt maintainability, testability, reliability, or codebase consistency? What is the technical debt cost of skipping it?

### 4. Proposed Solutions (2-3 options)

**Option A MUST be your researched recommendation** — always prefer correctness over convenience.

For each option:

```
**Option A: [name] (RECOMMENDED)**
[Concrete steps — what to do, which files to change, what code to write]
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

### 5. Wait for User Decision

Use `AskUser` tool. **BLOCKING**: Do NOT proceed to the next finding until the user decides.
**Every AskUser MUST include a "Tell me more" option** alongside the fix/skip options.

**IMMEDIATE RESPONSE RULE:** If the user selects "Tell me more" or responds with free text
(a question, disagreement, or request for clarification) instead of a decision:
**STOP IMMEDIATELY.** Do NOT continue to the next finding. Do NOT batch the response.
Research the user's concern RIGHT NOW using `WebSearch`, codebase analysis, or both.
Provide a thorough answer with evidence. Only AFTER the user is satisfied, re-present the
options and ask for their decision again. **NEVER defer to the end of the findings loop.**

The user may:
- Accept one of the proposed options (e.g., "A", "B")
- Select "Tell me more" for deeper analysis
- Resolve differently (user describes approach)
- Ignore this issue (proceed without fixing)

Record the decision internally. Do NOT apply any fix yet — all fixes are applied in Phase 4.

### Batch Processing

If there are 3+ findings of the same nature (e.g., "missing error handling in 5 handlers",
"inconsistent import path in 4 files"), group them and present as a single batch entry with
the list of affected files. Ask via `AskUser` if all can be applied at once. This avoids
repetitive one-by-one decisions for identical issues.

---

## Phase 4: Apply All Approved Fixes with TDD + Agent Validation

**IMPORTANT:** This phase runs ONCE, after ALL findings have been presented and ALL decisions collected in Phase 3. No fix is applied during Phase 3.

Apply ALL approved fixes in a single pass (skipped for ignored findings). Group fixes by file
to minimize I/O. The steps below apply to each fix within the batch — NOT sequentially
one-at-a-time with full test cycles between each. Run the full test suite ONCE after all
fixes are applied (Step 4.2 TDD covers individual fix verification, Step 4.3 handles failures).

For each approved fix:

### Step 4.1: Secondary Agent Validation (for logic changes only)

For fixes that alter execution flow, conditions, method calls, or observable behavior:

1. **Dispatch review agents in parallel** via `Task` tool. Use the agent selection priority below:

**Ring droids are REQUIRED.** If the core review droids are not installed, **STOP** and inform the user:
```
Required ring droids are not installed. Install them before running this skill:
  - ring-default-code-reviewer
  - ring-default-business-logic-reviewer
  - ring-default-security-reviewer
  - ring-default-ring-test-reviewer
```

**Droids to dispatch:**

| Domain | When to Dispatch | Ring Droid |
|--------|-----------------|------------|
| **Code Quality** | Always | `ring-default-code-reviewer` |
| **Business Logic** | Always | `ring-default-business-logic-reviewer` |
| **Security** | Always | `ring-default-security-reviewer` |
| **Test Quality** | Always | `ring-default-ring-test-reviewer` |
| **Nil/Null Safety** | Always | `ring-default-ring-nil-safety-reviewer` |
| **Ripple Effects** | Always | `ring-default-ring-consequences-reviewer` |
| **Dead Code** | Always | `ring-default-ring-dead-code-reviewer` |

2. **Skip agent validation** for purely cosmetic fixes (comments, rename, formatting, DRY without logic change)

3. **Handle conflicts between agents:** If two or more agents give contradictory feedback:
   - **Security conflicts:** Prioritize security > business-logic > code-quality
   - **Architectural conflicts:** Present both perspectives with tradeoffs (performance, maintainability, complexity, long-term impact) and recommend the option most aligned with project coding standards
   - **Implementation conflicts:** Prioritize code-quality > business-logic
   - In all cases: present both feedbacks to the user with priority recommendation and wait for decision before proceeding

### Step 4.2: TDD Cycle (mandatory)

For each approved fix:

1. **RED:** Write a failing test (if one doesn't already exist for the scenario)
2. **GREEN:** Implement the minimal fix
3. **REFACTOR:** Improve if necessary
4. **RUN UNIT TESTS:** Execute `make test` to verify no regressions

**For documentation fixes (docs, README, specs):** dispatch ring documentation droids
(`ring-tw-team-functional-writer`, `ring-tw-team-api-writer`). Documentation
droids do NOT follow TDD — they apply the fix directly.

### Step 4.3: Handle Test Failures

If tests fail after implementing the fix (maximum 3 attempts):

1. **Classify the failure:**
   - **Logic bug** → Return to RED phase, adjust test/fix
   - **Flaky/environmental test** → Before marking as skipped, re-execute the test at least 3 times in a clean environment to confirm flakiness. Maximum 1 test skipped per fix. Document explicit justification (error message, flakiness evidence) and tag with "pending-test-fix"
   - **Unavailable external dependency** → Pause and wait for restoration

2. **Do NOT proceed** to the next finding until all tests pass or the failure is classified and documented

### Step 4.4: Batching Independent Fixes

For PRs with many findings, independent fixes (in different modules/files) may be grouped in a single test cycle, as long as all tests pass before proceeding to the next group.

---

## Phase 5: Coverage Verification and Test Gap Analysis

After all findings have been processed through the TDD cycle:

### Step 5.1: Lint + Coverage Measurement

**Run lint ONCE** after all fixes are applied:
```bash
make lint
```
If lint fails, fix formatting issues and re-run.

**Measure unit test coverage:**

Use the project's Makefile or `.optimus.json` commands. If neither exists, fall
back to stack-specific commands:

```bash
# Preferred: Makefile target
make test-coverage 2>/dev/null

# Fallback: stack-specific
# Go:     go test -coverprofile=coverage-unit.out ./... && go tool cover -func=coverage-unit.out | tail -1
# Node:   npm test -- --coverage
# Python: pytest --cov=. --cov-report=term
```

**Threshold:** Unit tests: 85% minimum

If coverage measurement is available and below threshold, flag as a finding:
- **HIGH** severity for unit test coverage below 85%
- List untested business-logic functions as individual **HIGH** findings

If coverage measurement is NOT available (no Makefile target, no recognized stack), mark
as SKIP and note: "Coverage measurement not available — configure `make test-coverage`
or `.optimus.json`."

**NOTE:** Integration and E2E tests run only before push or when user invokes directly.

### Step 5.2: Test Scenario Gap Analysis

Dispatch an agent to identify missing test scenarios in the changed files.

**Dispatch a test gap analyzer** via `Task` tool. Use `ring-default-ring-test-reviewer` or `ring-dev-team-qa-analyst`.

The agent receives:
1. **Changed source files** — full content (non-test files only)
2. **Test files for changed source** — full content
3. **Coverage profile** — coverage command output (if available)

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

## Phase 6: Convergence Loop (MANDATORY — automatic re-validation with escalating scrutiny)

After Phase 5 completes, the reviewer MUST automatically re-validate using fresh sub-agents to eliminate session bias. This catches both new issues introduced by fixes AND issues missed in round 1.

**CRITICAL — Why Fresh Sub-Agents:**

The primary failure mode of convergence loops is **false convergence**: the orchestrator re-runs analysis in the same session, with the same mental model, and declares "zero new findings" — not because there are none, but because it can't see past its own prior reasoning.

The solution: **rounds 2+ are executed by a fresh sub-agent** dispatched via `Task` tool. The sub-agent has zero context from prior rounds, reads all files from scratch, and returns findings independently. The orchestrator then deduplicates against the cumulative ledger.

**Round structure:**

| Round | Who analyzes | How |
|-------|-------------|-----|
| **1** (initial) | Orchestrator (this agent) | CodeRabbit CLI + parallel agent dispatch — normal flow |
| **2** (mandatory) | **Fresh sub-agent** via `Task` | Sub-agent re-runs CodeRabbit CLI, reads all changed files from scratch, reviews independently, returns findings |
| **3-5** | **Fresh sub-agent** via `Task` | Same as round 2 — only triggered if round 2+ found new findings |

**Round 2 is MANDATORY.** The "zero new findings" stop condition can only trigger starting from round 3.

**Fresh sub-agent dispatch (rounds 2+):**

Dispatch a single sub-agent via `Task` tool (use any available ring review droid, e.g., `ring-default-code-reviewer`). The sub-agent receives:

1. **All changed files** — full content, re-read fresh from disk
2. **Project rules and coding standards** — re-read fresh
3. **The findings ledger** — for deduplication ONLY
4. **CodeRabbit CLI command** — the sub-agent re-runs CodeRabbit CLI itself to get fresh analysis

```
Goal: Independent code review (convergence round X of 5)

You are a FRESH reviewer with NO prior context. Review from scratch.

Steps:
  1. Re-run CodeRabbit CLI: coderabbit review --prompt-only --base <base-branch> --plain
  2. Parse CodeRabbit output for findings
  3. Review all changed files for: code quality, business logic, security,
     test quality, spec compliance
  4. Return all findings

Context:
  - Changed files: [full content — re-read from disk]
  - Project rules: [full content — re-read from files]

Previously identified findings (for DEDUP ONLY):
  [list of findings with IDs and descriptions]

CRITICAL: Analyze INDEPENDENTLY. Do NOT skip areas because previous rounds
"already covered" them. The orchestrator will dedup.

Required output:
  For each finding: severity, file, line, category, description, recommendation
  If no issues: "PASS — all domains clean"
```

**Orchestrator deduplication after sub-agent returns:**

1. Compare each sub-agent finding against the cumulative ledger (match by file + topic + description similarity)
2. **Genuinely new findings** → add to ledger, present to user via Phase 3
3. **Duplicates** → discard silently

**Loop rules:**
- **Maximum rounds:** 5 (the initial run counts as round 1)
- **Round 2 is MANDATORY** — always dispatch a fresh sub-agent regardless of round 1 results
- **Progress indicator:** Show `"=== Re-validation round X of 5 (fresh sub-agent) ==="` at the start of each re-run
- **Scope:** Sub-agent re-runs CodeRabbit CLI, reviews files, and returns findings. Do NOT re-load project context (Phase 1) in the orchestrator
- **If new findings exist:** Present them using Phase 3 (interactive resolution), fix via Phase 4 (TDD cycle), verify via Phase 5 (coverage), then loop again
- **Stop conditions (any one triggers exit):**
  1. Zero new findings — **only valid from round 3 onward** (round 2 is mandatory)
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

**When the loop exits**, proceed to the Final Summary with the cumulative results from ALL rounds.

---

## Phase 7: Final Summary

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
- Untested functions: X (Y business logic, Z infrastructure)

### Test Results
- Unit tests: PASS (X tests)
- Lint: PASS
- Integration tests: not run (run before push or invoke directly)
- E2E tests: not run (run before push or invoke directly)
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
- BEFORE presenting each finding: deep research is MANDATORY — project patterns, architectural decisions, existing codebase, task focus, user/consumer use cases, UX impact, API best practices, engineering best practices, language-specific idioms. Option A must be the correct approach backed by research evidence, regardless of effort
- No changes without prior user approval — the user ALWAYS decides the approach
- Ignored findings are recorded but not fixed
- Use review agents (Step 4.1) for logic changes; use codebase exploration for context investigation
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
