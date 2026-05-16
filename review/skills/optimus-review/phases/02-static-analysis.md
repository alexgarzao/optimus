# Phase 2: Static Analysis and Coverage Profiling

Loaded by `SKILL.md` after Phase 1 completes. MANDATORY automated checks (lint, vet, format, unit tests, coverage, test gap analysis) before dispatching review agents.

**MANDATORY.** Before dispatching review agents, run automated checks to collect concrete data. These results feed into agent prompts and become findings if they fail.

### Step 2.1: Run Static Analysis (parallel)

Run ALL applicable checks simultaneously via `_optimus_quiet_run` —
see AGENTS.md Protocol: Quiet Command Execution. The helper redirects each
command's output to `.optimus/logs/` and prints only a PASS/FAIL line (plus
last 50 lines on failure), so only the failing checks consume agent context.

Run `make lint` for lint checks. Optional static analysis tools (vet, imports, format, docs) are auto-detected from the project stack.

| # | Check | Command (wrapped in `_optimus_quiet_run`) | What it detects |
|---|-------|-------------------------------------------|-----------------|
| 1 | Lint | `_optimus_quiet_run "make-lint" make lint` (or `golangci-lint run` / `npm run lint`) | Linter rule violations |
| 2 | Vet | `_optimus_quiet_run "go-vet" go vet ./...` (Go projects) | Suspicious constructs |
| 3 | Import ordering | `_optimus_quiet_run "goimports" goimports -l .` (Go projects) | Unordered/missing imports |
| 4 | Format | `_optimus_quiet_run "gofmt" gofmt -l .` (Go) or `_optimus_quiet_run "prettier" npx prettier --check .` (JS/TS) | Formatting violations |
| 5 | Doc generation | `_optimus_quiet_run "generate-docs" make generate-docs` (if target exists) | Stale documentation |

For each check that **fails**, create a finding:
- Severity: **HIGH** for lint/vet, **MEDIUM** for format/imports/docs
- Source: `[Static Analysis: <check-name>]`
- Include the relevant error lines from the last 50 already printed by
  `_optimus_quiet_run` on failure (full log at `.optimus/logs/<timestamp>-<label>-<pid>.log`).

For checks that **pass**, note them for the Phase 5 overview — only the one-line
`PASS: ...` verdict is needed.

Skip checks whose commands don't exist in the project (e.g., skip `go vet` in a pure JS project).

### Step 2.2: Run Unit Tests with Coverage (Baseline)

Unit tests should pass before proceeding to agent dispatch. This establishes
the baseline — if unit tests are already failing, review findings may be unreliable.

Run unit tests with coverage in a single pass via `make test-coverage`, wrapped
in `_optimus_quiet_run`. The helper is defined in AGENTS.md Protocol: Quiet Command Execution.
The percentage extraction is covered by AGENTS.md Protocol: Coverage Measurement.
Fallback to `make test` only if the coverage target is unavailable:

```bash
_optimus_quiet_run "make-test-coverage" make test-coverage
# Fallback if coverage target missing:
# _optimus_quiet_run "make-test" make test
```

The agent sees only the PASS/FAIL verdict plus the extracted coverage percentage
(see Protocol: Coverage Measurement for the `awk '/^total:/'` line). The full
per-package coverage lives in `.optimus/logs/` and the native coverage file.

Measure coverage — see AGENTS.md Protocol: Coverage Measurement.

**If unit tests fail:**
1. `_optimus_quiet_run` already printed the last 50 lines and the log path —
   review them in place.
2. Ask the user via `AskUser`: "Unit tests are failing. Fix before continuing, or skip check?"
3. Do NOT proceed to Phase 3 until unit tests pass or user explicitly chooses to skip

**NOTE:** Integration tests are NOT run here. They run only in Phase 10
(after re-run guard, before summary) or when the user invokes them directly.
This avoids slow test suites blocking the review loop.

### Step 2.3: Analyze Coverage

Read the coverage output file (e.g., `coverage-unit.out`, `coverage.json`, or
`.optimus/logs/<timestamp>-*-coverage-*.log` — trailing `-<pid>` is part of every
helper-produced filename). See AGENTS.md Protocol: Coverage Measurement.
Identify:
- Overall coverage percentage (already emitted by the extraction command in Step 2.2)
- Packages/files with lowest coverage (bottom 20)
- Functions/methods with 0% coverage (untested)

Do NOT parse the stdout of `_optimus_quiet_run` for this — that stream contains only
the PASS/FAIL verdict and the extracted total line.

Create findings for coverage issues (aligned with AGENTS.md Protocol: Coverage Measurement):
- **HIGH**: Unit coverage below 85% threshold, or integration coverage below 70% threshold, or business logic functions with 0% coverage
- **MEDIUM**: Coverage above threshold but with notable untested functions
- Infrastructure/generated code with 0% → skip (not a finding)

### Step 2.4: Test Scenario Gap Analysis

Dispatch a test gap analyzer via `Task` tool. Use `ring-default-ring-test-reviewer` or `ring-dev-team-qa-analyst`.

The agent receives file paths and can navigate the codebase autonomously.

```
Goal: Cross-reference implemented tests with source code to find missing scenarios.

Context:
  - Project root: <absolute path to project worktree>
  - Task spec: <TASKS_DIR>/<TaskSpec> (READ this file for acceptance criteria)
  - Changed source files: [list of file paths] (READ each file)
  - Test files: [list of test file paths] (READ each file)
  - Coverage output: [coverage command output if available]

IMPORTANT: You have access to Read, Grep, and Glob tools. USE THEM to:
  - Read files at the paths above
  - Search for existing test patterns in the project
  - Find related test files not listed above
  - Discover how similar functions are tested elsewhere in the codebase

For each public function changed/added by this task:
  - Happy path tested?
  - Error paths tested (each error return)?
  - Edge cases (nil, empty, boundary values)?
  - Validation failures?
  - Integration points (DB failure, timeout, retry)?

Additionally verify test effectiveness:
  - Do tests verify BEHAVIOR or just mock internals? Flag tests where assertions only check mock.Called()
  - Could these tests pass while the feature is actually broken? (false positive risk)
  - Are tests coupled to implementation details (private fields, internal struct layout)?
  - For each acceptance criterion in the task spec, is there a corresponding test?
  - Do integration tests use real dependencies (testcontainers/docker) or just mocks?

Report: function, existing scenarios, missing scenarios, priority (HIGH/MEDIUM/LOW)
```

HIGH priority gaps become findings in Phase 4 consolidation.

### Step 2.5: Collect Results

Merge all static analysis findings and coverage gap findings into the findings list.
These are presented alongside agent review findings in Phase 5 (overview) and Phase 6 (interactive resolution).

---
