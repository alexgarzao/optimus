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

CodeRabbit-driven code review with TDD fix cycle, secondary agent validation
for logic changes, and interactive finding-by-finding resolution.

## Operating Mode

This skill is structured as an **executable index**: each phase lives in its own
file under `phases/`, loaded on demand. **Before executing a phase, you MUST
`Read` the phase file in full** — phase files carry HARD BLOCKs, TDD-cycle
guards, and bash blocks.

For deviations, ambiguous instructions, or any "skip this finding" request,
**you MUST `Read` `rules.md` BEFORE answering**.

## Phases

Run phases in order. Before each phase, **`Read` the phase file**, then execute its steps.

1. **Phase 1 — Execute CodeRabbit.** Read `phases/01-execute.md`. Discover CodeRabbit config, run the CLI against the base branch, parse JSON into a structured findings list.
2. **Phase 2 — Triage.** Read `phases/02-triage.md`. Categorize by severity, dedupe, present overview table.
3. **Phase 3 — Resolve Findings (Interactive).** Read `phases/03-resolve-findings.md`. Walk each finding via AskUser. **HARD BLOCK on Tell-me-more — deep research mandatory before presenting each finding.**
4. **Phase 4 — Apply Fixes (TDD + Agent Validation).** Read `phases/04-apply-fixes.md`. RED-GREEN-REFACTOR for each approved fix. Dispatch review agent for logic changes. Max 3 retries / max 1 skipped test per fix.
5. **Phase 5 — Verify, Converge, Push.** Read `phases/05-verify-and-converge.md`. Coverage verification, optional convergence loop (rounds 2-5), integration tests, optional push.
6. **Phase 6 — Final Summary.** Read `phases/06-final-summary.md`. Structured summary of fixes applied / skipped / convergence status / next-step recommendation.

## Rules Summary

The full ruleset lives in `rules.md` — **`Read` it before any deviation, dry-run, or skip request**. The non-negotiables:

- **One finding at a time, severity order** (CRITICAL > HIGH > MEDIUM > LOW).
- **Deep research before every finding** — Option A must be backed by evidence.
- **No auto-decisions** — the USER decides every finding, regardless of severity.
- **TDD is mandatory** for every approved fix — RED-GREEN-REFACTOR, no exceptions.
- **Max 3 retries per test failure, max 1 skipped test per fix** (with documented justification).
- **Tell-me-more = IMMEDIATE response** — never defer.
- **At any moment if instruction is ambiguous, conflicting, or the user requests deviation → Read `rules.md` before answering.**

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

### Protocol: Quiet Command Execution (summarized)

> **Summary inlined here. Full recipe at `AGENTS.md -> Protocol: Quiet Command Execution`.**

**Summary:** `_optimus_quiet_run <label> <command>` redirects stdout+stderr to `${MAIN_WORKTREE}/.optimus/logs/<ts>-<label>-<pid>.log`, emits a single `PASS`/`FAIL` line, and on failure dumps the last 50 lines (with `cat -v` to neutralize ANSI/OSC escape sequences). Uses `umask 0077` on the log file (output may contain credentials/stack traces). Exit code preserved so `if _optimus_quiet_run ...; then ... fi` works. Reserved exit codes: `2` = missing label/command; `3` = cannot create logs dir. Log retention (30-day age cap + 500-file count cap) is pruned at every Initialize Directory + Session State call. Use for verification commands only; never for output the agent must parse turn-by-turn. See full recipe in AGENTS.md.

### Protocol: Test Gap Analyzer Dispatch

**Summary:** Standardised prompt template for dispatching a test gap analyzer (`ring:test-reviewer` or `ring:qa-analyst`) via `Task` tool. Identifies missing test scenarios across changed files: happy path / error paths / edge cases / integration failures + test effectiveness checks. Returns three tables (Unit Test Gaps, Integration Test Gaps, Test Effectiveness Issues) plus a Summary. Used by skills that perform post-change reviews.

**Referenced by:** deep-review, coderabbit-review

The orchestrator MUST dispatch via `Task` tool with this exact prompt (substituting the listed file paths and the coverage profile placeholder):

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

Skills reference this as: "Dispatch a test gap analyzer — see AGENTS.md Protocol: Test Gap Analyzer Dispatch."


<!-- INLINE-PROTOCOLS:END -->
