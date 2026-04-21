---
name: optimus-verify-code
description: >
  Two-phase code verification. Phase 2 runs static analysis in parallel
  (lint, format, unit tests -- commands auto-detected from project stack).
  Phase 3 runs integration and E2E tests sequentially. Presents executive
  summary with MERGE_READY or NEEDS_FIX verdict. Supports Go, TypeScript,
  Python, and any project with a Makefile.
trigger: >
  - When user asks to verify, validate, or check the code before merge
  - Before creating a pull request
  - After completing implementation and wanting to confirm everything passes
skip_when: >
  - User only wants to run a single specific command
prerequisite: >
  - Project has a recognized stack (go.mod, package.json, pyproject.toml, Cargo.toml, or Makefile)
NOT_skip_when: >
  - "Tests passed last time" -- Code changed since then. Verify again.
  - "Only changed one file" -- One file can break lint, vet, and tests.
  - "CI will catch it" -- Catching locally is faster and cheaper.
examples:
  - name: Full verification before merge
    invocation: "/optimus-verify-code"
    expected_flow: >
      1. Run Phase 2 (6 commands in parallel)
      2. If all pass, run Phase 3 (integration then E2E)
      3. Present executive summary with verdict
  - name: Verification after fixing a bug
    invocation: "Verify the code"
    expected_flow: >
      1. Run both phases
      2. Present summary showing what passed/failed
related:
  complementary:
    - optimus-cycle-impl-stage-2
    - optimus-cycle-impl-review-stage-3
  differentiation:
    - name: optimus-deep-review
      difference: >
        optimus-deep-review dispatches specialist agents for deep analysis of
        code quality, business logic, and security. optimus-verify-code runs
        automated checks (lint, vet, tests) and reports pass/fail verdicts.
    - name: optimus-coderabbit-review
      difference: >
        optimus-coderabbit-review uses CodeRabbit CLI to generate findings and
        adds a TDD fix cycle. optimus-verify-code only runs automated checks
        without fixing anything.
verification:
  automated:
    - command: "test -f go.mod"
      description: Go project detected
      success_pattern: exit 0
  manual:
    - Executive summary presented with correct verdict
    - All command outputs captured and displayed
    - Duration measured for each command individually
---

# Verify Code

Two-phase code verification supporting multiple stacks.

---

## Phase 1: Detect Project Stack

Before running any checks, detect the project stack and determine available commands.

### Step 1.1: Identify Stack(s)

Check for ALL of these files — a project may have multiple stacks (e.g., Go backend + React frontend):

| File | Stack | Language |
|------|-------|----------|
| `go.mod` | Go | Go |
| `package.json` | Node.js | TypeScript/JavaScript |
| `pyproject.toml` or `setup.py` | Python | Python |
| `Cargo.toml` | Rust | Rust |
| `Makefile` (alone, no other matches) | Generic | Unknown — use Makefile targets only |

**Multi-stack detection:** If multiple stack files are found (e.g., `go.mod` AND `package.json`),
detect ALL stacks and build a **union** of their command matrices in Step 1.2. Run checks
for ALL detected stacks. The primary stack (for reporting purposes) is the first match in
the table above.

**Example:** A project with `go.mod` and `package.json` runs Go lint + vet + format + tests
AND Node.js lint + typecheck + format + tests.

### Step 1.1.1: Check for Custom Commands

Check if `.optimus/config.json` exists and contains a `commands` section:

```bash
cat .optimus/config.json 2>/dev/null | jq '.commands' 2>/dev/null
```

If found, use the configured commands instead of auto-detection. Missing keys fall back
to auto-detection. Empty string values (`""`) mean skip that check.

### Step 1.1.2: Determine Scope

Ask the user what to verify (or detect from invocation):

- **Full project** (default) — run all checks on the entire codebase
- **Changed files only** — scope checks to files changed since a base branch:
  ```bash
  DEFAULT_BRANCH=$(git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's@^refs/remotes/origin/@@')
  CHANGED_FILES=$(git diff --name-only "origin/$DEFAULT_BRANCH"...HEAD)
  ```
  If `CHANGED_FILES` is empty (no files changed), inform the user and exit early:
  ```
  No changes detected between your branch and <default_branch>. Nothing to verify.
  ```
  **STOP** — do not proceed to Phase 2.

  When scoped to changed files:
  - **Lint:** run lint only on changed files (if the linter supports file arguments)
  - **Vet/Typecheck:** run on full project (type checking needs full context)
  - **Format:** check only changed files
  - **Tests:** run tests for packages/modules containing changed files, not all tests

If the user says "verify changes", "verify diff", or "verify changed files", use diff mode.
If the user says "verify" or "verify all", use full project mode.

### Step 1.2: Build Command Matrix

Based on the detected stack(s), determine which commands to run:

| # | Check | Go | Node.js | Python | Generic (Makefile) |
|---|-------|----|---------|--------|--------------------|
| 1 | Lint | `make lint` or `golangci-lint run ./...` | `npm run lint` or `npx eslint .` | `make lint` or `ruff check .` | `make lint` |
| 2 | Vet/Typecheck | `go vet ./...` | `npx tsc --noEmit` | `mypy .` (if installed) | SKIP |
| 3 | Import/Format check | `goimports -l .` + `gofmt -l .` | `npx prettier --check .` | `ruff format --check .` | SKIP |
| 4 | Doc generation | `make generate-docs` | `make generate-docs` | `make generate-docs` | `make generate-docs` |
| 5 | Unit tests | `go test -coverprofile=coverage-unit.out ./...` | `npm test -- --coverage` | `pytest --cov=. --cov-report=term` | `make test` |

**IMPORTANT:** If a `Makefile` exists, prefer `make` targets over direct commands — the
Makefile is the project's source of truth for how to run checks. Check for target existence
with `make -n <target> 2>/dev/null`.

For each command: if the tool is not installed or the Makefile target does not exist, mark
as SKIP (not FAIL). Only report what is available.

---

## Phase 2: Static Analysis + Unit Tests (parallel)

Run ALL detected commands simultaneously. Capture stdout, stderr, exit code, and duration for each.

**Execution rules:**
- Run all commands in parallel (do not wait for one to finish before starting another)
- Capture output of each independently
- Format check commands fail if they produce any output (listed files need fixing)
- If `make generate-docs` modifies files, report which files changed — this means docs were stale
- Commands that are SKIP (tool not installed, target not found) do not count as failures

**Phase 2 verdict:**
- ALL commands pass (SKIP counts as pass) → proceed to Phase 3
- ANY fails → still proceed to Phase 3, but final verdict will be NEEDS_FIX

---

## Phase 3: Integration + E2E Tests (sequential)

Run sequentially, continue even if one fails:

| # | Check | Go | Node.js | Python | Generic |
|---|-------|----|---------|--------|---------|
| 6 | Integration tests | `make test-integration` or `go test -tags=integration ./...` | `npm run test:integration` | `pytest tests/integration/` | `make test-integration` |
| 7 | E2E tests | `make test-e2e` | `npm run test:e2e` or `npx playwright test` | `pytest tests/e2e/` | `make test-e2e` |

**Integration test command:**
Run integration tests with coverage profiling. The exact command depends on the project:
- **Go:** If `make test-integration` exists: use it. Otherwise: `go test -tags=integration -coverprofile=coverage-integration.out ./...`
- **Node.js:** `npm run test:integration` (if script exists)
- **Python:** `pytest tests/integration/ --cov=. --cov-report=term` (if directory exists)
- **Generic:** `make test-integration` (if target exists)

**Execution rules:**
- Run integration tests first
- Regardless of result, run `make test-e2e` next
- Capture output, exit code, and duration for each

### E2E Tests — User Decision

Before running E2E tests, check if they are available (`make test-e2e` target exists). If available, run them. If NOT available, ask the user using `AskUser`:

"E2E tests are not configured for this project. Would you like to skip E2E verification, or should they be implemented?"

Options:
- Skip E2E for now
- E2E tests should be implemented (flag as NEEDS_FIX)

---

## Phase 4: Coverage Analysis

After Phase 3 completes, analyze test coverage from the generated profiles.

### Step 1: Extract Coverage Percentages

**Go:**
```bash
go tool cover -func=coverage-unit.out | tail -1
go tool cover -func=coverage-integration.out | tail -1 2>/dev/null
```

**Node.js:** Parse the coverage summary from `npm test -- --coverage` output (look for
"All files" line with Stmts/Branch/Funcs/Lines percentages).

**Python:** Parse the coverage summary from `pytest --cov` output (look for "TOTAL" line).

### Step 2: Identify Coverage Gaps

For each coverage profile, identify packages/files with low coverage:

**Go:**
```bash
go tool cover -func=coverage-unit.out | grep -v "total:" | awk '{print $NF, $1}' | sort -n | head -20
```

**Node.js/Python:** Parse per-file coverage from the coverage report output.

Flag files/packages below thresholds:
- **CRITICAL:** 0% coverage (completely untested code)
- **HIGH:** < 50% coverage
- **MEDIUM:** < 70% coverage
- **LOW:** < 85% coverage

### Step 3: Identify Untested Functions

Extract functions with 0% coverage — these are potential test gaps:

```bash
go tool cover -func=coverage-unit.out | grep "0.0%"
```

For each untested function, classify:
- **Business logic** (handlers, services, domain) → HIGH priority gap
- **Infrastructure** (config, bootstrap, wiring) → MEDIUM priority gap
- **Generated code** (mocks, protobuf) → can be excluded

### Step 4: Coverage Summary

Include in the executive summary:

```
Coverage Analysis:
  Unit tests:        XX.X% (threshold: 85%)     PASS / FAIL
  Integration tests: XX.X% (threshold: 70%)     PASS / FAIL
  
  Packages below threshold: X
  Untested functions: X (Y business logic, Z infrastructure)
  
  Top 5 lowest-coverage packages:
    1. internal/handler/boleto   — 42.3%
    2. internal/service/payment  — 58.7%
    3. ...
```

### Coverage Thresholds

| Test Type | Threshold | Verdict if Below |
|-----------|-----------|-----------------|
| Unit tests | 85% | NEEDS_FIX |
| Integration tests | 70% | NEEDS_FIX |

If coverage profiles cannot be generated (command fails), report as SKIP with note — do not fail the entire verification.

---

## Phase 5: Test Scenario Gap Analysis

After coverage measurement, dispatch an agent to systematically identify missing test scenarios. Coverage % tells you HOW MUCH is tested; this phase tells you WHAT is NOT tested.

### Step 1: Collect Inputs

Gather the following for the agent:
1. **Source files:** Read all non-test source files in `internal/` (or equivalent) — handlers, services, repositories, domain models
2. **Test files:** Read all `*_test.go` files corresponding to the source files
3. **Coverage profile:** The output of `go tool cover -func=coverage-unit.out` (full output, not just total)
4. **Integration test files:** Read all integration test files (tagged or in separate directories)

### Step 2: Dispatch Test Gap Analyzer

Dispatch a single agent via `Task` tool to analyze gaps:

```
Goal: Systematically identify missing test scenarios in unit and integration tests.

Context:
  - Source files: [full content of each source file]
  - Test files: [full content of each test file]
  - Coverage profile: [go tool cover -func output]

Your job:
  For each public function/method in the source code, analyze:
  1. What test scenarios EXIST (from the test files)
  2. What test scenarios are MISSING — specifically:
     - Happy path (basic success case)
     - Error paths (each error return)
     - Edge cases (nil inputs, empty collections, boundary values)
     - Validation failures (invalid inputs)
     - Concurrent access (if the function uses shared state, goroutines, channels)
     - Integration points (if the function calls external services, DB)

  For integration tests specifically, check:
     - Database operations: are rollback, constraint violation, and timeout scenarios tested?
     - External API calls: are failure, timeout, and retry scenarios tested?
     - Message queue: are publish failure and consume failure scenarios tested?

Required output format:
  ## Unit Test Gaps
  | # | File | Function | Existing Scenarios | Missing Scenarios | Priority |
  |---|------|----------|--------------------|-------------------|----------|
  | 1 | internal/handler/boleto.go | CancelBoleto | happy path, invalid ID | auth failure, already cancelled, timeout | HIGH |

  ## Integration Test Gaps
  | # | File | Function | Existing Scenarios | Missing Scenarios | Priority |
  |---|------|----------|--------------------|-------------------|----------|
  | 1 | internal/repository/boleto.go | UpdateStatus | happy path | DB timeout, concurrent update, constraint violation | HIGH |

  ## Summary
  - Total public functions analyzed: X
  - Functions with complete test coverage: X
  - Functions with partial coverage: X (missing Y scenarios total)
  - Functions with no tests: X
  - Priority: X HIGH, Y MEDIUM, Z LOW gaps
```

Use the appropriate ring droid:
1. `ring-default-ring-test-reviewer` (preferred)
2. `ring-dev-team-qa-analyst`

### Step 3: Present Gap Summary

Include in the executive summary after the coverage section:

```
TEST SCENARIO GAPS:
─────────────────────────────────────
  Functions analyzed: 45
  Fully covered: 28
  Partially covered: 12 (34 missing scenarios)
  No tests: 5

  HIGH priority gaps: 8
  MEDIUM priority gaps: 15
  LOW priority gaps: 11

  Top gaps:
    1. [HIGH] CancelBoleto — missing: auth failure, already cancelled
    2. [HIGH] UpdateStatus — missing: DB timeout, concurrent update
    3. ...
```

**Verdict impact:** Test gaps do NOT change the MERGE_READY/NEEDS_FIX verdict (which is based on pass/fail and coverage %). Gaps are reported as recommendations for the user to prioritize.

---

## Phase 6: Executive Summary

After all phases complete, present the summary using the `<json-render>` format for rich terminal UI.

### Summary Structure

```
============================================
  VERIFICATION SUMMARY
============================================

Phase 2 — Static Analysis + Unit Tests: PASS / FAIL
Phase 3 — Integration + E2E Tests:      PASS / FAIL
Coverage — Unit / Integration:           PASS / FAIL
Total time: Xs

┌───┬──────────────────────────────┬────────┬──────────┐
│ # │ Command                      │ Status │ Duration │
├───┼──────────────────────────────┼────────┼──────────┤
│ 1 │ make lint                    │ PASS   │ 3.2s     │
│ 2 │ go vet ./...                 │ PASS   │ 1.1s     │
│ 3 │ goimports -l .               │ FAIL   │ 0.4s     │
│ 4 │ gofmt -l .                   │ PASS   │ 0.3s     │
│ 5 │ make generate-docs           │ PASS   │ 2.1s     │
│ 6 │ Unit tests + coverage        │ PASS   │ 8.5s     │
│ 7 │ Integration tests + coverage │ PASS   │ 22.3s    │
│ 8 │ E2E tests                    │ SKIP   │ -        │
└───┴──────────────────────────────┴────────┴──────────┘

COVERAGE:
─────────────────────────────────────
  Unit tests:        87.2% (threshold: 85%) ✓
  Integration tests: 72.1% (threshold: 70%) ✓
  
  Untested functions: 12 (8 business logic, 4 infrastructure)
  Packages below threshold: 2
    - internal/handler/boleto   42.3%
    - internal/service/payment  58.7%

TEST SCENARIO GAPS:
─────────────────────────────────────
  Functions analyzed: 45
  Fully covered: 28 | Partial: 12 | No tests: 5
  Missing scenarios: 8 HIGH, 15 MEDIUM, 11 LOW

ERRORS (first 10 lines per failure):
─────────────────────────────────────
#3 goimports -l .
  internal/handler/user.go
  internal/service/auth.go

VERDICT: NEEDS_FIX
```

### Verdict Rules

| Condition | Verdict |
|-----------|---------|
| All commands pass AND coverage above thresholds | **MERGE_READY** |
| Any command fails OR coverage below thresholds | **NEEDS_FIX** |
| Integration or E2E not available (no Makefile target) | **SKIP** that command, do not count as failure |
| Coverage profile cannot be generated | **SKIP** coverage check, do not count as failure |

### Error Display

For each failed command:
- Show the first 10 lines of stderr (or stdout if stderr is empty)
- If `goimports -l` or `gofmt -l` failed, the output IS the list of files to fix
- If `make generate-docs` changed files, list which files were modified

---

## Rules

- Do NOT fix anything — this skill only reports
- Do NOT use `-short` flag in any test command — all tests must run completely
- Do NOT skip commands that are slow — run everything
- If a Makefile target does not exist, SKIP it and note in the summary (do not fail)
- If a stack-specific tool is not installed (e.g., `goimports`, `prettier`, `ruff`), report as SKIP with note
- Always show the full summary even if everything passes
- Duration must be measured for each command individually
- Auto-detect the stack from project files — do NOT assume Go
