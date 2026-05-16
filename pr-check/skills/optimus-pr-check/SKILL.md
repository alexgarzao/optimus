---
name: optimus-pr-check
description: "Standalone PR review orchestrator. Fetches PR metadata, collects ALL review comments (Codacy, DeepSource, CodeRabbit, human reviewers), dispatches parallel agents to evaluate code and comments, presents findings interactively, applies fixes with TDD cycle and separate commits per finding, responds to every comment thread with commit reference or justification, and adds inline suppression tags for Codacy/DeepSource when a finding won't be fixed."
trigger: >
  - When user provides a PR URL for review (e.g., "review this PR: https://github.com/org/repo/pull/123")
  - When user asks to review a pull request
skip_when: >
  - No PR URL provided and user wants a generic code review (use optimus-deep-review directly)
  - PR is already merged (nothing to review)
  - User wants to run automated checks only (use `make lint && make test` directly)
prerequisite: >
  - PR URL is provided or can be inferred (current branch has an open PR)
  - gh CLI is installed and authenticated
  - For Codacy/DeepSource findings: workflows codacy-issues.yml and deepsource-pr-issues.yml should exist in the repo (if not present, those sources are simply skipped)
NOT_skip_when: >
  - "The PR is small" -- Small PRs still benefit from structured review with PR context.
  - "I already looked at the diff" -- Specialist agents catch issues human review misses.
  - "CI passed" -- CI checks automated rules; agents review logic, security, and quality.
  - "CodeRabbit already reviewed" -- Agents validate/contest CodeRabbit findings and catch what it misses.
  - "Codacy/DeepSource already analyzed" -- Agents validate/contest static analysis findings and catch what they miss.
examples:
  - name: Review a PR by URL
    invocation: "Review this PR: https://github.com/org/repo/pull/42"
    expected_flow: >
      1. Fetch PR metadata and ALL existing comments (Codacy, DeepSource, CodeRabbit, human)
      2. Checkout PR branch
      3. Present PR summary with all comment sources and CI status
      4. Dispatch agents to review code AND evaluate ALL existing comments
      5. Consolidate with source attribution and deduplication
      6. Interactive finding-by-finding resolution
      7. Apply fixes with TDD cycle, separate commits per finding
      8. Coverage verification and (optional) convergence loop
      9. Push commits
      10. Respond to ALL comment threads (commit SHA or won't-fix with suppression)
      11. Final summary with verdict
  - name: Review current branch PR
    invocation: "Review the PR for this branch"
    expected_flow: >
      1. Detect current branch, find associated open PR via gh CLI
      2. Fetch PR metadata and comments
      3. Standard flow
related:
  complementary:
    - optimus-deep-review
  differentiation:
    - name: optimus-deep-review
      difference: >
        optimus-deep-review is a generic code review that works with any scope
        (all files, git diff, directory). optimus-pr-check adds PR context
        (description, linked issues, existing comments from ALL sources) and
        evaluates feedback from multiple sources (Codacy, DeepSource, CodeRabbit,
        human reviewers, agents).
  sequence:
    after:
      - optimus-review
    before:
      - optimus-done
  re_execution:
    allowed: true
verification:
  automated:
    - command: "which gh 2>/dev/null && echo 'available'"
      description: gh CLI is installed
      success_pattern: available
  manual:
    - PR metadata and comments from ALL sources fetched correctly
    - Source attribution present in all findings
    - All findings presented interactively with progress indicator
    - Approved fixes applied with TDD cycle and separate commits
    - Coverage verification passed thresholds
    - Convergence loop run, skipped, or stopped (status recorded)
    - ALL comment threads replied with commit SHA or won't-fix justification
    - Codacy/DeepSource suppression tags added for won't-fix findings
    - PR readiness verdict presented
---

# PR Review

Unified PR review orchestrator. Fetches PR metadata, collects ALL review
comments (Codacy, DeepSource, CodeRabbit, human reviewers), dispatches agents
to evaluate both code and comments, and presents findings with source
attribution. Applies fixes with TDD cycle, responds to every comment with
resolution, and adds inline suppression for Codacy/DeepSource won't-fix
findings.

## Pre-Check: Verify GitHub CLI (HARD BLOCK)

**HARD BLOCK:** Verify GitHub CLI — see AGENTS.md Protocol: GitHub CLI Check.

## CRITICAL: Every Invocation Starts From Scratch

**HARD BLOCK:** Every time this skill is invoked, it MUST fetch ALL data fresh from the PR. There is NO state carried over from previous invocations.

- Do NOT assume issues from a previous run are still resolved
- Do NOT skip fetching comments because "I already saw this PR"
- Do NOT say "issues were already resolved" without fetching and verifying RIGHT NOW
- New comments, new commits, new CI results may exist since the last run
- Always run Phase 1 completely: fetch metadata, fetch ALL threads, fetch CI checks, fetch changed files
- The PR may have changed entirely since the last time you looked at it

If you find yourself saying "these were already addressed" without having run `gh api` commands in THIS session, you are violating this rule. The full ruleset (including this one) lives in `rules.md` — **`Read` it before any deviation**.

## Operating Mode

This skill is a **standalone PR review tool**. It does NOT change task status in
state.json and is NOT part of the pipeline stages. It works like deep-review — the
user invokes it when they want to review a PR, independently of the task lifecycle.

No task identification, status validation, or state.json writes are performed.

This skill is structured as an **executable index**: each phase lives in its own
file under `phases/`, loaded on demand. **Before executing a phase, you MUST
`Read` the phase file in full** — phase files contain the binding instructions,
HARD BLOCKs, agent roster, fetch recipes, and bash blocks for that step.

For deviations, ambiguous instructions, dry-run mode, or any "skip this finding"
request, **you MUST `Read` `rules.md` BEFORE answering**.

## Phases

Run phases in order. Before each phase, **`Read` the phase file**, then execute its steps.

1. **Phase 1 — Fetch PR Context.** Read `phases/01-fetch-pr-context.md`. Fetch PR metadata, ALL review comments (Codacy/DeepSource/CodeRabbit/human), CI status, changed files. **HARD BLOCK: every invocation starts from scratch — see Rules.**
2. **Phase 2 — Present Summary + Parallel Agent Dispatch.** Read `phases/02-summary-and-dispatch.md`. Present PR summary, dispatch review agents in PARALLEL to evaluate code AND existing comments.
3. **Phase 3 — Consolidate, Present, Resolve Findings.** Read `phases/03-consolidate-and-present.md`. Consolidate with source attribution, dedupe, overview table, walk findings via AskUser. **HARD BLOCK on Tell-me-more.**
4. **Phase 4 — Rule Configuration + Apply Fixes.** Read `phases/04-rules-and-fixes.md`. Recommend Codacy/DeepSource rule config; apply approved fixes with TDD (RED-GREEN-REFACTOR), one commit per fix.
5. **Phase 5 — Verify, Converge, Push.** Read `phases/05-verify-and-converge.md`. Coverage verification, convergence loop (opt-in), integration tests, push (triggers Codacy/DeepSource reanalysis).
6. **Phase 6 — Respond + Final Summary.** Read `phases/06-respond-and-summarize.md`. Reply to every Codacy/DeepSource/CodeRabbit/human comment thread (commit SHA or won't-fix reason); inline suppression tags for Codacy/DeepSource; final readiness verdict.

## Rules Summary

The full ruleset lives in `rules.md` — **`Read` it before any deviation, dry-run, or skip request**. The non-negotiables:

- **Every invocation fetches fresh** — no state from prior runs.
- **All comment sources** — Codacy, DeepSource, CodeRabbit, humans.
- **Every finding has source attribution.**
- **Findings presented one at a time, severity order, `(X/N)` progress prefix.**
- **No auto-decisions** — the USER decides every finding.
- **Tell-me-more = IMMEDIATE response** — never defer.
- **One commit per fix.** Suppression syntax matches the underlying linter (biome-ignore, eslint-disable, //nolint, // skipcq).
- **Do NOT merge the PR** — only review and apply fixes.
- **At any moment if instruction is ambiguous, conflicting, or the user requests deviation → Read `rules.md` before answering.**

<!-- INLINE-PROTOCOLS:START -->
## Shared Protocols (from AGENTS.md)

The following protocols are referenced by this skill. They are
extracted from the Optimus AGENTS.md to make this plugin self-contained.

### Finding Option Format (MANDATORY for cycle review skills)

Every finding must present 2-3 options with this structure:

```
**Option A: [name] (RECOMMENDED)**
[Concrete steps — what to do, which files to change, what code to write]
- Why recommended: [reference to research — best practice, project pattern, official docs]
- Impact: [UX / Task focus / Project focus / Engineering quality]
- Effort: [low / medium / high / very high]
- Estimated time: [< 5 min / 5-15 min / 15-60 min / 1-4h / > 4h]

**Option B: [name]**
[Alternative approach]
- Impact: [UX / Task focus / Project focus / Engineering quality]
- Effort: [low / medium / high / very high]
- Estimated time: [< 5 min / 5-15 min / 15-60 min / 1-4h / > 4h]
```

**Effort scale:**
- **Low:** Localized change, single file, no tests needed
- **Medium:** Multiple files, straightforward, may need test updates
- **High:** Significant refactoring, new tests, multiple modules affected
- **Very high:** Architectural change, many files, extensive testing, risk of regressions


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
