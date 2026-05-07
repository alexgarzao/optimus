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
  differentiation:
    - name: optimus-deep-review
      difference: >
        optimus-deep-review uses parallel specialist agents to generate findings.
        optimus-coderabbit-review uses CodeRabbit CLI as the source of findings
        and adds mandatory TDD cycle + secondary agent validation for logic changes.
    - name: optimus-review
      difference: >
        optimus-review validates a completed task against its spec.
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
    - Convergence loop run, skipped, or stopped (status recorded)
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
2. **Verify Makefile targets (HARD BLOCK):** The project MUST have a `Makefile` with `lint` and `test` targets. If either is missing, **STOP**: "Project is missing required Makefile targets (`make lint`, `make test`). Add them before running coderabbit-review."
3. **Identify project rules and AI instructions (MANDATORY):** Execute project rules discovery — see AGENTS.md Protocol: Project Rules Discovery.
4. **Initialize .optimus directory (HARD BLOCK):** Execute Protocol: Initialize .optimus Directory — see AGENTS.md Protocol: Initialize .optimus Directory. This guarantees `.optimus/logs/` exists AND is gitignored before any `_optimus_quiet_run` call creates log files.

---

## Phase 2: Triage

### Step 2.1: Parse Findings

**Parse CodeRabbit review body — see AGENTS.md Protocol: Parse CodeRabbit Review Body.**

The shared protocol is the single source of truth for the deterministic
parsing algorithm consumed by both `coderabbit-review` and `pr-check`. It
covers: per-section parse (regular inline / duplicate / outside-diff),
per-finding fix-block extraction (`Minimal fix` / `Suggested refactor`), AI
prompt capture, severity mapping, count-parity HARD BLOCK, aggregate
cross-validation, and origin tagging.

The three origin tags surfaced by the protocol:

1. **Regular findings** — inline suggestions about code within the diff. `origin: inline`.
2. **Duplicate comments** — findings CodeRabbit already reported in previous reviews that remain unresolved. `origin: duplicate`.
3. **Outside diff range comments** — suggestions about code OUTSIDE the reviewed diff. `origin: outside-diff`.

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

**If N==1, skip any confirmation prompt** — present the single finding directly with header `(1/1) ...`. The user already chose to review by invoking the skill.

Process ONE finding at a time, in severity order (CRITICAL first, LOW last). Collect ALL decisions first — do NOT apply any fix during this phase.

For EACH finding, present with `"(X/N)"` progress prefix in the header, including the origin tag:
- Regular: `## (X/N) — [SEVERITY] | CodeRabbit | Category`
- Duplicate: `## (X/N) — [SEVERITY] | CodeRabbit — DUPLICATE | Category`
- Outside diff: `## (X/N) — [SEVERITY] | CodeRabbit — OUTSIDE PR DIFF | Category`

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
11. **Production resilience:** Would this code survive production conditions? Consider: timeouts on external calls, retry with backoff, circuit breakers, graceful degradation, resource cleanup, graceful shutdown, and behavior under load
12. **Data integrity and privacy:** Are transaction boundaries correct? Could partial writes occur? Is PII properly handled (not logged, masked in responses)? LGPD/GDPR compliance?

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

**AskUser `[topic]` format:** Format: `(X/N) F#-Category`.
Example: `[topic] (8/12) F8-DeadCode`.

Use `AskUser` tool. **BLOCKING**: Do NOT proceed to the next finding until the user decides.
**Every AskUser MUST include these options:**
- One option per proposed solution (Option A, Option B, Option C, etc.)
- Skip — no action
- Tell me more — if selected, STOP and answer immediately (do NOT continue to next finding)

**AskUser template (MANDATORY — follow this exact structure for every finding):**
```
1. [question] (X/N) SEVERITY — Finding title summary
[topic] (X/N) F#-Category
[option] Option A: recommended fix
[option] Option B: alternative approach
[option] Skip
[option] Tell me more
```

**HARD BLOCK — IMMEDIATE RESPONSE RULE:** If the user selects "Tell me more" or responds
with free text: **STOP IMMEDIATELY.** Do NOT continue to the next finding. Research and
answer RIGHT NOW. Only after the user is satisfied, re-present the SAME finding's options.
**NEVER defer to the end of the findings loop.**

**Anti-rationalization (excuses the agent MUST NOT use):**
- "I'll address all questions after presenting the remaining findings" — NO
- "Let me continue with the next finding and come back to this" — NO
- "I'll research this after the findings loop" — NO
- "This is noted, moving to the next finding" — NO

The user may:
- Accept one of the proposed options (e.g., "A", "B")
- Select "Tell me more" for deeper analysis
- Resolve differently (user describes approach)
- Ignore this issue (proceed without fixing)

Record the decision internally. Do NOT apply any fix yet — all fixes are applied in Phase 4.

**Same-nature grouping:** applied automatically per AGENTS.md "Finding Presentation" item 3.

---

## Phase 4: Apply All Approved Fixes with TDD + Agent Validation

**IMPORTANT:** This phase runs ONCE, after ALL findings have been presented and ALL decisions collected in Phase 3. No fix is applied during Phase 3.

**Relationship to pr-check:** `pr-check` allows direct application of CodeRabbit's
`[Minimal fix]` or `[Suggested refactor]` blocks (path: `CodeRabbit-as-is`) for
nitpick-level findings without requiring TDD. `coderabbit-review` always uses TDD
for ALL findings — by design, this skill is for the case where the user wants to
deeply understand and re-implement each suggestion, not just merge cosmetic patches.

If you want as-is application of CodeRabbit's exact suggestions, use `pr-check`
instead. If you want TDD-driven re-implementation with full author understanding,
use `coderabbit-review`.

Apply ALL approved fixes in a single pass (skipped for ignored findings). Group fixes by file
to minimize I/O. The steps below apply to each fix within the batch — NOT sequentially
one-at-a-time with full test cycles between each. Run the full test suite ONCE after all
fixes are applied (Step 4.2 TDD covers individual fix verification, Step 4.3 handles failures).

For each approved fix:

### Step 4.1: Secondary Agent Validation (for logic changes only)

For fixes that alter execution flow, conditions, method calls, or observable behavior:

1. **Dispatch review agents in parallel** via `Task` tool. Use the agent selection priority below:

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
```

**Droids to dispatch:**

| Domain | When to Dispatch | Ring Droid |
|--------|-----------------|------------|
| **Code Quality** — architecture, SOLID, DRY, resilience, resource lifecycle, concurrency, performance, configuration, cognitive complexity, error handling, domain purity | Always | `ring-default-code-reviewer` |
| **Business Logic** — domain correctness, edge cases, spec traceability, data integrity, backward compatibility, API semantics | Always | `ring-default-business-logic-reviewer` |
| **Security** — vulnerabilities, OWASP, input validation, data privacy, error response leakage, rate limiting, auth propagation | Always | `ring-default-security-reviewer` |
| **Test Quality** — coverage gaps, error scenarios, flaky patterns, test effectiveness, false positive risk, test coupling, spec traceability | Always | `ring-default-ring-test-reviewer` |
| **Nil/Null Safety** — nil pointer risks, unsafe dereferences, resource cleanup nil checks, channel/map/slice safety | Always | `ring-default-ring-nil-safety-reviewer` |
| **Ripple Effects** — cross-file impacts, backward compatibility, configuration drift, migration paths, shared state, event contracts | Always | `ring-default-ring-consequences-reviewer` |
| **Dead Code** — orphaned code, zombie test infrastructure, stale feature flags, deprecated paths | Always | `ring-default-ring-dead-code-reviewer` |

**Agent prompt context MUST include:**
```
  - Project root: <absolute path to project worktree>
  - Project rules: AGENTS.md, PROJECT_RULES.md, docs/PROJECT_RULES.md (READ all that exist)
  - Changed files: [list of file paths] (READ each file)

IMPORTANT: You have access to Read, Grep, and Glob tools. USE THEM to:
  - Read files at the paths above
  - Search the codebase for patterns similar to the code under review
  - Find how the same problem was solved elsewhere in the project
  - Discover test patterns, error handling conventions, and architectural styles
  - Explore related files not listed above when needed for context

Cross-cutting analysis (MANDATORY for all agents):
  1. What would break in production under load with this code?
  2. What's MISSING that should be here? (not just what's wrong)
  3. Does this code trace back to a spec requirement? Flag orphan code without spec backing
  4. How would a new developer understand this code 6 months from now?
  5. Search the codebase for how similar problems were solved — flag inconsistencies with existing patterns
```

**Special Instructions per Agent:**

Include per-droid quality checklists — see AGENTS.md Protocol: Per-Droid Quality Checklists.

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
4. **RUN UNIT TESTS:** Execute `_optimus_quiet_run "make-test" make test` to verify
   no regressions — see AGENTS.md Protocol: Quiet Command Execution.

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

**Run lint ONCE** after all fixes are applied, using the resolved command from
Step 1.3, wrapped in `_optimus_quiet_run` — see AGENTS.md Protocol: Quiet
Command Execution:
```bash
_optimus_quiet_run "make-lint" make lint
```
If lint fails, fix formatting issues and re-run.

**Measure unit test coverage:**

Measure coverage — see AGENTS.md Protocol: Coverage Measurement.

If coverage is below threshold, flag as findings.

**NOTE:** Integration tests run only before push or when user invokes directly.

### Step 5.2: Test Scenario Gap Analysis

Dispatch an agent to identify missing test scenarios in the changed files.

**Dispatch a test gap analyzer** via `Task` tool. Use `ring-default-ring-test-reviewer` or `ring-dev-team-qa-analyst`.

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

## Phase 6: Convergence Loop (Optional — Gated)

Execute the opt-in convergence loop — see AGENTS.md "Common Patterns > Protocol: Convergence Loop (Full Roster Model — Opt-In, Gated)".

**Behavioral contract for THIS phase:**
- "Round 1" maps to the aggregate of Phase 4 Step 4.1 per-fix Secondary Agent Validation
  dispatches (this skill is fix-driven; the agent roster is dispatched per fix, not as
  a single primary review pass). THIS phase (rounds 2 through 5) re-dispatches the same
  roster ONCE over the full diff to catch issues missed during the per-fix passes.
- Present the **entry gate** before round 2 (`Run round 2` / `Skip convergence loop`).
- Present the **per-round gate** before rounds 3, 4, 5 (`Continue` / `Stop here`).
- If a dispatched round produces ZERO new findings, declare convergence and exit
  silently — DO NOT ask the user whether to run another round.
- Record the final loop status (`CONVERGED` / `USER_STOPPED` / `SKIPPED` /
  `HARD_LIMIT` / `DISPATCH_FAILED_ABORTED`) for the Final Summary.

**Stage-specific scope for convergence rounds 2+:**
Dispatch the **same agent roster** used in Phase 4 Step 4.1 (all 7 review droids). Each
agent receives file paths and project rules (re-read fresh from disk). Do NOT include the
findings ledger in agent prompts — the orchestrator handles dedup using strict matching
(same file + same line range ±5 + same category).

Additionally, one agent in the roster should re-run CodeRabbit CLI
(`coderabbit review --prompt-only --base <base-branch> --plain`) to get fresh static
analysis. The other agents review the code from their specialist domains.

**Failure handling:** If a dispatched agent slot fails (Task tool error, ring droid
unavailable), do NOT count as zero findings. Ask the user via `AskUser` whether to
retry the round or stop (status `DISPATCH_FAILED_ABORTED` if user stops).

When the loop exits (any status), proceed to Phase 7 (integration tests).

---

## Phase 7: Integration Tests (before push)

**After the convergence loop exits**, run integration tests. These are slow and
expensive, so they run ONCE here — not during the fix/convergence cycle. Run
quietly — see AGENTS.md Protocol: Quiet Command Execution:

```bash
_optimus_quiet_run "make-test-integration" make test-integration   # Optional target — SKIP if missing
```

| Test Type | Command | If target exists | If missing |
|-----------|---------|-----------------|------------|
| Integration | `_optimus_quiet_run "make-test-integration" make test-integration` | **HARD BLOCK** if fails | SKIP |

**If integration tests fail:**
1. `_optimus_quiet_run` already printed the last 50 lines plus the log path —
   review them in place.
2. Ask via `AskUser`: "Integration tests are failing. What should I do?"
   - Fix the issue (dispatch ring droid)
   - Skip and proceed to summary (user will handle later)

**If all pass (or targets don't exist):** proceed to Phase 8 (Push) or Phase 9 (Final Summary).

---

## Phase 8: Push Commits (optional)

Offer to push commits — see AGENTS.md Protocol: Push Commits.

---

## Phase 9: Final Summary

After all phases complete:

```markdown
## CodeRabbit Review — Summary

### Convergence
- Rounds dispatched (round 1 + convergence rounds): X
- Status: CONVERGED | USER_STOPPED | SKIPPED | HARD_LIMIT | DISPATCH_FAILED_ABORTED

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
- Integration tests: XX.X% (threshold: 70%) — PASS / FAIL / SKIP
- Untested functions: X (Y business logic, Z infrastructure)

### Test Results
- Unit tests: PASS (X tests)
- Lint: PASS
- Integration tests: not run (run before push or invoke directly)
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

<!-- INLINE-PROTOCOLS:START -->
## Shared Protocols (from AGENTS.md)

The following protocols are referenced by this skill. They are
extracted from the Optimus AGENTS.md to make this plugin self-contained.

### Protocol: Coverage Measurement (summarized)

> **Summary inlined here. Full recipe at `AGENTS.md -> Protocol: Coverage Measurement`.**

**Summary:** Measure unit + integration test coverage via Makefile targets with stack-specific fallbacks (Go: `go test -coverprofile`; Node: `npm test -- --coverage`; Python: `pytest --cov=. --cov-report=term`). Run wrapped in `_optimus_quiet_run` (Protocol: Quiet Command Execution) to keep agent context clean — the agent sees only PASS/FAIL + extracted total percentage; full per-file breakdown stays in `.optimus/logs/` and native coverage files. Thresholds: unit 85%, integration 70% (NEEDS_FIX/HIGH finding below). When scanning untested functions, read coverage output FILE (not stdout) — flag business-logic functions at 0% as HIGH; infrastructure/generated code as SKIP. If no coverage command resolves, mark SKIP — do not fail verification. See full extraction recipes in AGENTS.md.

### Protocol: Initialize .optimus Directory (summarized)

> **Summary inlined here. Full recipe at `AGENTS.md -> Protocol: Initialize .optimus Directory`.**

**Summary:** Create `${MAIN_WORKTREE}/.optimus/{sessions,reports,logs}/` with `mkdir -p`. Add `# optimus-operational-files` and `# optimus-operational-worktrees` markers to `${MAIN_WORKTREE}/.gitignore` idempotently (grep-anchor before append). Refuse symlinked `.gitignore`. Auto-prune `.optimus/logs/` (30 days, 500 files). See full recipe in AGENTS.md.

### Protocol: Per-Droid Quality Checklists (summarized)

> **Summary inlined here. Full recipe at `AGENTS.md -> Protocol: Per-Droid Quality Checklists`.**

**Summary:** Per-droid quality dimensions that review/pr-check/deep-review/coderabbit-review/plan/build skills MUST include in their agent prompts beyond the core review domain. Examples: code-reviewer adds resilience/concurrency/cognitive-complexity/error-handling checks; security-reviewer adds PII/error-response-leakage/rate-limiting/secrets; test-reviewer adds effectiveness/false-positive-risk/spec-traceability; nil-safety adds channel/map/slice safety; consequences adds backward-compat/migration-path/event-contract; dead-code adds zombie test infrastructure and stale feature flags; qa-analyst adds testability/operational-readiness; frontend adds UX states/accessibility/i18n; backend adds graceful-shutdown/context-propagation/structured-logging. Skills reference this when building specialist droid prompts so agents review uniformly. See full per-droid lists in AGENTS.md.

### Protocol: Project Rules Discovery

**Summary:** Every reviewing/validating/generating skill MUST scan for project conventions before starting. Search the canonical list (AGENTS.md, CLAUDE.md, DROIDS.md, .cursorrules, PROJECT_RULES.md, .editorconfig, coding-standards.md, CONTRIBUTING.md, linter configs like .eslintrc/biome.json/.golangci.yml/.prettierrc) and read ALL that exist. If none exist, warn the user. Discovered files become the authoritative source of truth and MUST be passed to every dispatched sub-agent. See full file list in AGENTS.md.

**Referenced by:** stages 1-4, deep-review, coderabbit-review

Every skill that reviews, validates, or generates code MUST search for project rules
and AI instruction files before starting. Search for these files in order and read ALL
that exist:

```
AGENTS.md                    # Primary agent instructions
CLAUDE.md                    # Claude-specific rules
DROIDS.md                    # Droid-specific rules
.cursorrules                 # Cursor-specific rules
PROJECT_RULES.md             # Coding standards (root or docs/)
docs/PROJECT_RULES.md
.editorconfig                # Editor formatting rules
docs/coding-standards.md     # Explicit coding conventions
docs/conventions.md
.github/CONTRIBUTING.md      # Contribution guidelines
CONTRIBUTING.md
.eslintrc*                   # Linter configs (implicit rules)
biome.json
.golangci.yml
.prettierrc*
```

If NONE exist, warn the user. If any are found, they become the source of truth
for coding standards and must be passed to every dispatched sub-agent.

Skills reference this as: "Discover project rules — see AGENTS.md Protocol: Project Rules Discovery."


### Protocol: Quiet Command Execution (summarized)

> **Summary inlined here. Full recipe at `AGENTS.md -> Protocol: Quiet Command Execution`.**

**Summary:** `_optimus_quiet_run <label> <command>` redirects stdout+stderr to `${MAIN_WORKTREE}/.optimus/logs/<ts>-<label>-<pid>.log`, emits a single `PASS`/`FAIL` line, and on failure dumps the last 50 lines (with `cat -v` to neutralize ANSI/OSC escape sequences). Uses `umask 0077` on the log file (output may contain credentials/stack traces). Exit code preserved so `if _optimus_quiet_run ...; then ... fi` works. Reserved exit codes: `2` = missing label/command; `3` = cannot create logs dir. Log retention (30-day age cap + 500-file count cap) is pruned at every Initialize Directory + Session State call. Use for verification commands only; never for output the agent must parse turn-by-turn. See full recipe in AGENTS.md.

<!-- INLINE-PROTOCOLS:END -->
