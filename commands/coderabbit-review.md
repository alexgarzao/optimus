---
description: CodeRabbit-driven code review with TDD fix cycle, secondary validation via parallel review agents for logic changes, and interactive finding-by-finding resolution. Runs CodeRabbit CLI to generate findings, then processes each with mandatory RED-GREEN-REFACTOR and full test execution.
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

Alternatively, I can run a code review using specialist agents instead (same as /optimus:deep-review).
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

### Protocol: Resolve Main Worktree Path (summarized)

> **Summary inlined here. Full recipe at `AGENTS.md -> Protocol: Resolve Main Worktree Path`.**

**Summary:** Resolve `MAIN_WORKTREE` once via `git worktree list --porcelain | awk '/^worktree / {print $2; exit}'` with `${MAIN_WORKTREE:?…}` defensive guard. Use `${MAIN_WORKTREE}/.optimus/...` for ALL `.optimus/` paths (gitignored, so doesn't propagate across linked worktrees). See full recipe in AGENTS.md.

### Finding Presentation (Unified Model)
All cycle review skills follow this pattern:
1. Collect findings from agents/tools
2. Consolidate and deduplicate
3. **Group same-nature findings** — after deduplication, identify findings that share the
   same root cause or fix pattern (e.g., "missing error handling" in 5 handlers, "inconsistent
   import path" in 4 files). If 2+ findings are of the same nature, merge them into a **single
   grouped entry** listing all affected files/locations. Each group counts as ONE item in the
   `"(X/N)"` sequence. The user makes ONE decision for the entire group.
4. Announce total findings count: `"### Total findings to review: N"` (where N reflects
   grouped entries — a group of 5 same-nature findings counts as 1)
5. Present overview table with severity counts
6. **Deep research BEFORE presenting each finding** (see research checklist below)
7. Walk through findings ONE AT A TIME with `"(X/N)"` progress prefix in the header, ordered by severity
   (CRITICAL first, then HIGH, MEDIUM, LOW). **ALL findings MUST be presented regardless of
   severity** — the agent NEVER skips, filters, or auto-resolves any finding. The decision to
   fix or skip is ALWAYS the user's. For grouped entries, list all affected files/locations
   within the single presentation.
8. For each finding: present research-backed analysis + options, collect decision via AskUser.
   **Every AskUser for a finding decision MUST include these options:**
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

   **Scope of the structured AskUser template:**

   The `[topic]/[option]` structured template applies ONLY to **AskUser calls that present
   findings/decisions inside cycle review skills** (plan, build, review, pr-check,
   deep-review, deep-doc-review, coderabbit-review). Each finding presentation must use
   the template so the user gets consistent UX and the test suite can verify the contract.

   Other AskUser calls — status confirmations, scope choosers, file-presence prompts,
   admin operations like task creation/cancellation, resume reset confirmations, etc. —
   MAY use prose. Authors should still aim for clarity and explicit option labels, but
   the structured template is not required outside finding loops.

   This scope is enforced by `TestStructuredAskUserScope` in `scripts/test_skill_consistency.py`.

9. **HARD BLOCK — IMMEDIATE RESPONSE RULE — If the user selects "Tell me more" OR responds
   with free text (a question, disagreement, or request for clarification):**
   **STOP IMMEDIATELY.** Do NOT continue to the next finding. Do NOT batch the response.
   Research the user's concern RIGHT NOW using `WebSearch`, codebase analysis, or both.
   Provide a thorough answer with evidence (links, code references, best practice citations).
   Only AFTER the user is satisfied, re-present the SAME finding's options and ask for
   their decision again. This may go back and forth multiple times — that is expected.
   **NEVER defer the response to the end of the findings loop.**

   **Anti-rationalization (excuses the agent MUST NOT use to skip immediate response):**
   - "I'll address all questions after presenting the remaining findings" — NO
   - "Let me continue with the next finding and come back to this" — NO
   - "I'll research this after the findings loop" — NO
   - "This is noted, moving to the next finding" — NO
10. After ALL N decisions collected: apply ALL approved fixes (see below)
11. Run verification (see Verification Timing below)
12. Present final summary


### Protocol: Convergence Loop (Full Roster Model — Opt-In, Gated) (summarized)

> **Summary inlined here. Full recipe at `AGENTS.md -> Protocol: Convergence Loop (Full Roster Model — Opt-In, Gated)`.**

**Summary:** Multi-round review pattern for plan, build, review, pr-check, coderabbit-review, deep-review, deep-doc-review. Round 1 is mandatory (the skill's primary dispatch). Rounds 2-5 are gated behind explicit `AskUser` prompts (entry gate before round 2, per-round gate before 3/4/5). Each gated round dispatches the SAME droid roster as round 1 in parallel via `Task` tool with zero prior context — agents read files fresh from disk. Convergence detection (zero new findings, strict `same file + ±5 lines + same category` matching) exits silently with status `CONVERGED` — never asks for another round. Hard limit at round 5. Exit statuses: `CONVERGED`, `USER_STOPPED`, `SKIPPED`, `HARD_LIMIT`, `DISPATCH_FAILED_ABORTED` (build has a single-slot carve-out). See full recipe in AGENTS.md.

### Protocol: Coverage Measurement

**Referenced by:** review, pr-check, coderabbit-review, deep-review, build

Measure test coverage using Makefile targets with stack-specific fallbacks.

**Run coverage quietly.** Coverage commands are the single biggest source of
verbose output (N packages × per-file coverage lines). Wrap them with
`_optimus_quiet_run` (see Protocol: Quiet Command Execution) so the full output
lands on disk and only a PASS/FAIL line reaches the agent. Then read only the
"total" summary line to extract the percentage.

**Unit coverage command resolution order:**
1. `make test-coverage` (if Makefile target exists), run via `_optimus_quiet_run`
2. Stack-specific fallback:
   - Go: `go test -coverprofile=coverage-unit.out ./...` (wrapped) then `go tool cover -func=coverage-unit.out`
   - Node: `npm test -- --coverage` (wrapped)
   - Python: `pytest --cov=. --cov-report=term` (wrapped)

If no unit coverage command is available, mark as **SKIP** — do not fail the verification.

**Integration coverage command resolution order:**
1. `make test-integration-coverage` (if Makefile target exists), run via `_optimus_quiet_run`
2. Stack-specific fallback:
   - Go: `go test -tags=integration -coverprofile=coverage-integration.out ./...` (wrapped) then `go tool cover -func=coverage-integration.out`
   - Node: `npm run test:integration -- --coverage` (wrapped)
   - Python: `pytest -m integration --cov=. --cov-report=term` (wrapped)

If no integration coverage command is available, mark as **SKIP** — do not fail the verification.

**Extracting the percentage (agent-visible output):** after the wrapped run, emit
only the total line. Examples:

```bash
# Go
_optimus_quiet_run "make-test-coverage" make test-coverage
if [ -f coverage-unit.out ]; then
  go tool cover -func=coverage-unit.out | awk '/^total:/ {print "Unit coverage: " $NF}'
fi

# Node (Istanbul JSON/text-summary)
_optimus_quiet_run "npm-test-coverage" npm test -- --coverage
if [ -f coverage/coverage-summary.json ]; then
  jq -r '.total.lines.pct | "Unit coverage: \(.)%"' coverage/coverage-summary.json
fi

# Python (pytest-cov)
_optimus_quiet_run "pytest-cov" pytest --cov=. --cov-report=term --cov-report=json:coverage.json
if [ -f coverage.json ]; then
  jq -r '.totals.percent_covered_display | "Unit coverage: \(.)%"' coverage.json
fi
```

The agent sees ~2 lines total (PASS verdict + "Unit coverage: 87.4%"). The full
per-file breakdown stays in `.optimus/logs/` and in the native coverage files.

**Thresholds:**

| Test Type | Threshold | Verdict if Below |
|-----------|-----------|-----------------|
| Unit tests | 85% | NEEDS_FIX / HIGH finding |
| Integration tests | 70% | NEEDS_FIX / HIGH finding |

**Coverage gap analysis:** When scanning for untested functions/methods (0% coverage),
read the coverage output file (not the agent turn stdout) — either the native
`coverage-*.out` / `coverage-summary.json` / `coverage.json` file, or the
`.optimus/logs/<timestamp>-*-coverage-*.log` file produced by `_optimus_quiet_run`
(the trailing `-<pid>` segment is part of every helper-produced log filename).
Flag business-logic functions with 0% as HIGH, infrastructure/generated code with
0% as SKIP.

Skills reference this as: "Measure coverage — see AGENTS.md Protocol: Coverage Measurement."


### Protocol: Initialize .optimus Directory (summarized)

> **Summary inlined here. Full recipe at `AGENTS.md -> Protocol: Initialize .optimus Directory`.**

**Summary:** Create `${MAIN_WORKTREE}/.optimus/{sessions,reports,logs}/` with `mkdir -p`. Add `# optimus-operational-files` and `# optimus-operational-worktrees` markers to `${MAIN_WORKTREE}/.gitignore` idempotently (grep-anchor before append). Refuse symlinked `.gitignore`. Auto-prune `.optimus/logs/` (30 days, 500 files). See full recipe in AGENTS.md.

### Protocol: Parse CodeRabbit Review Body

**Referenced by:** pr-check, coderabbit-review

Deterministic algorithm for extracting actionable findings from a CodeRabbit
review-body GraphQL response. Both pr-check and coderabbit-review consume the
same source format; this protocol is the single source of truth so the two
skills cannot drift in their parsing rules. Drift is exactly how CodeRabbit
findings get silently dropped — see the historical "duplicate comments missed"
incident that motivated the count-parity guard below.

**Source data — GraphQL fields fetched:**

The CodeRabbit review body is obtained via the GitHub GraphQL API:

```graphql
pullRequest(number: $pr) {
  reviews(first: 100) {
    nodes {
      author { login }      # filter to coderabbitai[bot]
      body                  # markdown body containing the <details> blocks below
      submittedAt
    }
    pageInfo { hasNextPage endCursor }
  }
}
```

Take the **latest** review whose author is `coderabbitai[bot]`. Pagination via
`pageInfo` is mandatory when `hasNextPage` is true.

**Parsing algorithm — top-level sections:**

The latest CodeRabbit review body contains zero or more of these top-level
`<details>` blocks (each parsed via the per-section algorithm below):

| Top-level summary regex | Origin tag | Description |
|------------------------|------------|-------------|
| `♻️ Duplicate comments \((\d+)\)` | `duplicate` | Findings repeated from previous reviews, still unresolved |
| `⚠️ Outside diff range comments \((\d+)\)` | `outside-diff` | Findings about code outside the PR diff |
| `🤖 Prompt for all review comments with AI agents` | `aggregate` (cross-validation only, NOT a per-finding source) | Aggregate flat-list block used to cross-check the per-finding parse |

Inline (in-diff) findings come from the per-thread GraphQL fetch (review
threads), not from the review body — they are tagged `origin: inline` by the
caller. The review body parser handles only the duplicate/outside-diff
sections plus the aggregate cross-validation block.

**Per-section algorithm (applied to each top-level `<details>` block):**

1. **Locate the outer `<details>`** by matching the summary regex (case-sensitive).
   Capture `N_TOTAL`. If no match: section absent (N=0) — skip.

2. **Extract the outer blockquote body**, tracking nesting: every inner
   `<details>` opens a level; every matching `</details>` closes one. Stop
   when the outer level closes.

3. **Iterate inner per-file `<details>` blocks**:
   `<summary>(.+?) \((\d+)\)</summary>` — capture `FILE_PATH` and `K_COUNT`.

4. **Within each per-file blockquote, split by `---` separators at the top
   level** (depth == 0). Walk line-by-line, increment depth on `<details>`,
   decrement on `</details>`; a line `^\s*---\s*$` is a separator only when
   depth == 0.

5. **Each slice = ONE finding.** Parse:
   - First non-empty line: `` `(\d+(?:-\d+)?)`: _(⚠️ Potential issue|🛠️ Refactor suggestion|🧹 Nitpick|...)_ \| _(🔴|🟠|🟡|🔵) (Critical|Major|Minor|Trivial)_ `` — capture `LINE_RANGE`, `TYPE_LABEL`, `SEVERITY_EMOJI`, `SEVERITY_LABEL`.
   - Next bold line `**...**` is the `TITLE`.
   - Body until first nested `<details>` or end-of-slice is the `DESCRIPTION`.

6. **Per-finding fix-block extraction.** Within each finding's slice:
   - `FIX_LABEL` + `FIX_DIFF` — match `<details><summary>(🐛 Minimal fix|🐛 Suggested refactor)</summary>` (the two labels are mutually exclusive within one finding; if neither is present, leave both empty). **Critical:** match BOTH labels — matching only `🐛 Minimal fix` silently drops findings labeled `Suggested refactor` even when the diff is supplied.
   - `AI_PROMPT` — match `<details><summary>🤖 Prompt for AI Agents</summary>` and capture body. **Disambiguation:** this is the per-finding prompt block, NOT the aggregate `🤖 Prompt for all review comments with AI agents` block. Both can coexist; extract independently.

7. **Severity mapping:**

   | Emoji | Label | Severity |
   |-------|-------|----------|
   | 🔴 | Critical | CRITICAL |
   | 🟠 | Major | HIGH |
   | 🟡 | Minor | MEDIUM |
   | 🔵 | Trivial | LOW |

**Count parity validation (HARD BLOCK on mismatch):**

After parsing each section:
- Sum per-file extracted findings → must equal `N_TOTAL`.
- Per-file extracted count → must equal `K_COUNT` for every file.

**On mismatch: STOP immediately.** Print: parsed N, expected M, file
breakdown, missing/extra IDs. **Do NOT offer an opt-out** — a silent
partial-set continuation is exactly the failure mode this gate prevents. The
user must investigate the parser or CodeRabbit output before the skill can
proceed.

**Cross-validation via aggregate prompt block:**

CodeRabbit emits a `<details><summary>🤖 Prompt for all review comments with AI agents</summary>` block listing findings as a flat bullet list grouped by section. Parse it independently and take the **UNION** with the per-section parse, matched by `(file, line_range)`:
- In both → merge (per-section block is primary; aggregate description is fallback).
- Only in one → keep, log which source surfaced it.
- **Never take the intersection** — single-source absence is a parsing bug, not ground truth.

**Outdated-thread partitioning:**

Inline review threads with `isOutdated: true` are partitioned out of the
active findings set. The original finding text is preserved in the duplicate
comments section of the review body (CodeRabbit re-emits unresolved findings
across reviews), so the duplicate-section parse remains the source of record
for content. Outdated threads are typically auto-resolved by the consuming
skill's hygiene step — see pr-check Step 13.0.

**Origin tagging rules** (when presenting findings to the user, ALWAYS include
the origin tag in the finding header):

| Source | Tag |
|--------|-----|
| Per-thread inline review comment (in-diff) | `[CodeRabbit]` |
| Duplicate-comments section | `[CodeRabbit — DUPLICATE]` |
| Outside-diff-range section | `[CodeRabbit — OUTSIDE PR DIFF]` |
| Non-CodeRabbit (Codacy/DeepSource/CI/human) | their own origin tag — NOT this protocol |

**Distinguishing CodeRabbit from CI bot, duplicate, human:**

This protocol handles CodeRabbit only. The caller separately identifies:
- **CI bots** (`github-actions[bot]`, `codacy-production[bot]`, `deepsource-io[bot]`, etc.) — handled by their own per-bot parsers.
- **Duplicate findings** (CodeRabbit's own duplicate section) — origin-tagged here, not de-duplicated against earlier reviews.
- **Human reviewers** — every author whose login is not in the known-bot list.

**Caller-specific application** (NOT part of this protocol):
- pr-check applies CodeRabbit-as-is (`[Minimal fix]` / `[Suggested refactor]` direct application path) for nitpick-level findings — see pr-check Step 1.3.3 surrounding prose.
- coderabbit-review always applies findings via TDD — see coderabbit-review Phase 4. The relationship between the two skills is documented in coderabbit-review/SKILL.md ("Relationship to pr-check").

Skills reference this as: "Parse CodeRabbit review body — see AGENTS.md Protocol: Parse CodeRabbit Review Body."


### Protocol: Per-Droid Quality Checklists

**Referenced by:** review, pr-check, deep-review, coderabbit-review, plan, build

Each droid type has specific dimensions it MUST verify beyond its core domain. Skills
that dispatch review droids MUST include the applicable checklists in agent prompts.

**Code Quality agent** (`ring-default-code-reviewer`) must additionally verify:
- Resilience: external calls have timeout, retry with backoff, circuit breaker where appropriate
- Resource lifecycle: all opened connections/handles are closed (defer, cleanup, graceful shutdown)
- Concurrency: shared state has proper synchronization, no goroutine leaks, no deadlock risk
- Performance: no N+1 queries, no unbounded queries, indexes exist for query patterns, no hot-path allocations
- Configuration: no hardcoded values that should be environment-configurable, safe defaults
- Cognitive complexity: functions with >3 nesting levels or >30 lines flagged for decomposition
- Error handling: errors wrapped with context, consistent with codebase error patterns
- Domain purity: no infrastructure concerns in domain layer, dependency direction correct
- Resource leaks: DB connections, HTTP clients, file handles, channels properly closed

**Business Logic agent** (`ring-default-business-logic-reviewer`) must additionally verify:
- Spec traceability: each code path maps to a spec requirement (flag orphan logic with no spec backing)
- Data integrity: transaction boundaries correct, partial writes impossible, rollback defined
- Backward compatibility: existing consumers/contracts not broken by this change
- API semantics: correct HTTP status codes, idempotent operations marked as such, pagination consistent
- Domain edge cases: what happens with zero, negative, maximum, duplicate, concurrent values?
- Business rule completeness: all business rules from spec have implementation AND test

**Security agent** (`ring-default-security-reviewer`) must additionally verify:
- Data privacy: PII not logged, sensitive fields masked in responses, LGPD/GDPR compliance
- Error responses: no internal details leaked (stack traces, DB schemas, internal paths, SQL)
- Rate limiting: high-throughput or public endpoints have rate limiting consideration
- Input validation: happens at the right layer (not just client-side), consistent with codebase
- Secrets: no hardcoded credentials, tokens, API keys in code or config files
- Auth propagation: authentication context properly propagated through the call chain

**Test Quality agent** (`ring-default-ring-test-reviewer`) must additionally verify:
- Test effectiveness: do tests verify BEHAVIOR or just mock internals? Flag tests where assertions only check mock.Called() without verifying output/state
- False positive risk: could these tests pass while the feature is actually broken?
- Test coupling: are tests coupled to implementation details (private fields, internal struct layout)?
- Spec traceability: for each acceptance criterion in the task spec, is there a test?
- Integration tests: do they use real dependencies (testcontainers/docker) or just mocks?
- Test isolation: can tests run in parallel without interference? Shared state between tests?
- Error scenario completeness: each error return path has a corresponding test?
- Boundary values: min, max, zero, empty, nil, negative tested where applicable?

**Nil/Null Safety agent** (`ring-default-ring-nil-safety-reviewer`) must additionally verify:
- Resource cleanup: nil checks before Close/Release calls
- Channel safety: sends to nil/closed channels
- Map safety: reads/writes to nil maps
- Slice safety: index bounds after filtering/transforming

**Ripple Effects agent** (`ring-default-ring-consequences-reviewer`) must additionally verify:
- Values duplicated between files that should be a shared constant
- Imports follow the project's layer architecture (no circular deps, no backwards imports)
- New code follows the same patterns as existing code in the same domain
- Backward compatibility: does this change break any existing consumer or API contract?
- Configuration drift: new defaults reasonable? existing config overrides still valid?
- Migration path: if breaking change, is migration strategy documented?
- Shared state: new global/package-level state that could cause issues across modules?
- Event/message contracts: changes to event payloads affect downstream consumers?

**Dead Code agent** (`ring-default-ring-dead-code-reviewer`) must additionally verify:
- Dead code: unused imports, unreachable branches, commented-out code
- Zombie test infrastructure: test helpers, fixtures, mocks no longer used by any test
- Feature flags: stale feature flag checks for flags that were already fully rolled out
- Deprecated paths: code paths behind deprecated API versions with no remaining consumers

**Spec Compliance / QA agent** (`ring-dev-team-qa-analyst`) must additionally verify:
- Testability assessment: is the code structured for testability? (dependency injection, interfaces)
- Operational readiness: can ops monitor, debug, and rollback this in production?
- Acceptance criteria coverage: each AC has both success AND failure test scenarios
- Cross-cutting scenarios: concurrent modifications, large datasets, special characters, timezone handling

**Frontend specialist** (`ring-dev-team-frontend-engineer`) must additionally verify:
- UX completeness: loading states, empty states, error states all handled
- Accessibility: keyboard navigation, screen reader support, ARIA labels, color contrast
- Responsive behavior: works across viewport sizes (mobile, tablet, desktop)
- i18n readiness: no hardcoded user-facing strings, date/number formatting locale-aware
- Performance: no unnecessary re-renders, large lists virtualized, images optimized

**Backend specialist** (`ring-dev-team-backend-engineer-golang` or `ring-dev-team-backend-engineer-typescript`) must additionally verify:
- Language idiomaticity: follows official style guide conventions
- Graceful shutdown: SIGTERM handling, in-flight request draining
- Connection pool sizing: appropriate for expected load
- Context propagation: request context passed through the full call chain
- Structured logging: logs include correlation IDs, operation names, durations

Skills reference this as: "Include per-droid quality checklists — see AGENTS.md Protocol: Per-Droid Quality Checklists."


### Protocol: Project Rules Discovery

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


### Protocol: Push Commits (optional)

**Referenced by:** plan, build, review, coderabbit-review. Note: done handles pushing inline in its own cleanup phase. pr-check and deep-review have their own push phases.

After stage work is complete, offer to push all local commits:

**Step 1 — Check if upstream tracking exists:**

```bash
git rev-parse --abbrev-ref @{u} 2>/dev/null
```

- **If command fails (no upstream):** The branch was never pushed. All local commits are unpushed.
  Ask via `AskUser`:
  ```
  Branch has no upstream (never pushed). Push now?
  ```
  Options:
  - **Push now** — `git push -u origin "$(git branch --show-current)"`
  - **Skip** — I'll push manually later

- **If command succeeds (upstream exists):** Check for unpushed commits:
  ```bash
  git log @{u}..HEAD --oneline 2>/dev/null
  ```
  If there are unpushed commits, ask via `AskUser`:
  ```
  There are N unpushed commits on this branch. Push now?
  ```
  Options:
  - **Push now** — `git push`
  - **Skip** — I'll push manually later

**Why check upstream first:** `git log @{u}..HEAD` silently produces empty output when no
upstream exists, making it appear there's nothing to push. Without this check, the push step
would be silently skipped even though ALL local commits are unpushed.

**Step 2 — Check tasks repo in separate-repo mode:**

If `$TASKS_GIT_SCOPE = "separate-repo"`, the tasks repo is independent from the project
repo. Commits made via `tasks_git commit` (e.g., Active Version Guard) land in the tasks
repo and must be pushed separately. Skipping this makes team members pull project main
without seeing version/task changes.

```bash
if [ "$TASKS_GIT_SCOPE" = "separate-repo" ]; then
  # Check if tasks-repo current branch has upstream
  if ! tasks_git rev-parse --abbrev-ref @{u} >/dev/null 2>&1; then
    TASKS_BRANCH=$(tasks_git branch --show-current 2>/dev/null)
    # AskUser: "Tasks repo branch '$TASKS_BRANCH' has no upstream. Push now?"
    # Options: Push now — `tasks_git push -u origin "$TASKS_BRANCH"` / Skip
  else
    TASKS_UNPUSHED=$(tasks_git log @{u}..HEAD --oneline 2>/dev/null)
    if [ -n "$TASKS_UNPUSHED" ]; then
      TASKS_UNPUSHED_COUNT=$(printf '%s\n' "$TASKS_UNPUSHED" | wc -l | tr -d ' ')
      # AskUser: "Tasks repo has $TASKS_UNPUSHED_COUNT unpushed commits. Push now?"
      # Options: Push now — `tasks_git push` / Skip
    fi
  fi
fi
```

**After a successful push**, check if the current repo is the Optimus plugin repository
and update installed plugins to pick up the changes just pushed:

```bash
if jq -e '.name == "optimus"' .factory-plugin/marketplace.json >/dev/null 2>&1; then
  echo "Optimus repo detected — updating installed plugins..."
  for skill in $(droid plugin list 2>/dev/null | grep optimus | awk '{print $1}'); do
    droid plugin update "$skill" 2>/dev/null
  done
fi
```

This ensures that agents running in the Optimus repo itself always use the latest
skill versions after pushing changes.

Skills reference this as: "Offer to push commits — see AGENTS.md Protocol: Push Commits."


### Protocol: Quiet Command Execution (summarized)

> **Summary inlined here. Full recipe at `AGENTS.md -> Protocol: Quiet Command Execution`.**

**Summary:** `_optimus_quiet_run <label> <command>` redirects stdout+stderr to `${MAIN_WORKTREE}/.optimus/logs/<ts>-<label>-<pid>.log`, emits a single `PASS`/`FAIL` line, and on failure dumps the last 50 lines (with `cat -v` to neutralize ANSI/OSC escape sequences). Uses `umask 0077` on the log file (output may contain credentials/stack traces). Exit code preserved so `if _optimus_quiet_run ...; then ... fi` works. Reserved exit codes: `2` = missing label/command; `3` = cannot create logs dir. Log retention (30-day age cap + 500-file count cap) is pruned at every Initialize Directory + Session State call. Use for verification commands only; never for output the agent must parse turn-by-turn. See full recipe in AGENTS.md.

### Protocol: Ring Droid Requirement Check

**Referenced by:** review, deep-doc-review, coderabbit-review, plan, build

Before dispatching ring droids, verify the required droids are available. If any required
droid is not installed, **STOP** and list missing droids.

**Core review droids** (required by review, pr-check, deep-review, coderabbit-review):
- `ring-default-code-reviewer`
- `ring-default-business-logic-reviewer`
- `ring-default-security-reviewer`
- `ring-default-ring-test-reviewer`

**Extended review droids** (required by review, pr-check, deep-review, coderabbit-review):
- `ring-default-ring-nil-safety-reviewer`
- `ring-default-ring-consequences-reviewer`
- `ring-default-ring-dead-code-reviewer`

**QA droids** (required by review, deep-review, build):
- `ring-dev-team-qa-analyst`

**Documentation droids** (required by deep-doc-review):
- `ring-tw-team-docs-reviewer`
- `ring-default-business-logic-reviewer`
- `ring-default-code-reviewer`

**Implementation droids** (required by build):
- `ring-dev-team-backend-engineer-golang` (Go)
- `ring-dev-team-backend-engineer-typescript` (TypeScript)
- `ring-dev-team-frontend-engineer` (React/Next.js)

**Spec validation droids** (required by plan):
- `ring-default-business-logic-reviewer`
- `ring-default-security-reviewer`
- `ring-dev-team-qa-analyst`
- `ring-default-code-reviewer`

Skills reference this as: "Verify ring droids — see AGENTS.md Protocol: Ring Droid Requirement Check."


<!-- INLINE-PROTOCOLS:END -->
