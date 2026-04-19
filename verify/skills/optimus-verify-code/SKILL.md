---
name: optimus-verify-code
description: >
  Two-phase code verification for Go projects. Phase 1 runs static analysis
  in parallel (lint, vet, imports, format, docs, unit tests). Phase 2 runs
  integration and E2E tests sequentially. Presents executive summary with
  MERGE_READY or NEEDS_FIX verdict.
trigger: >
  - When user asks to verify, validate, or check the code before merge
  - Before creating a pull request
  - After completing implementation and wanting to confirm everything passes
skip_when: >
  - Project is not Go (no go.mod found)
  - User only wants to run a single specific command
prerequisite: >
  - go.mod exists in the project
  - Makefile exists with lint, test-unit, test-integration, test-e2e targets
NOT_skip_when: >
  - "Tests passed last time" → Code changed since then. Verify again.
  - "Only changed one file" → One file can break lint, vet, and tests.
  - "CI will catch it" → Catching locally is faster and cheaper.
examples:
  - name: Full verification before merge
    invocation: "/optimus-verify-code"
    expected_flow: >
      1. Run Phase 1 (6 commands in parallel)
      2. If all pass, run Phase 2 (integration then E2E)
      3. Present executive summary with verdict
  - name: Verification after fixing a bug
    invocation: "Verify the code"
    expected_flow: >
      1. Run both phases
      2. Present summary showing what passed/failed
related:
  complementary:
    - optimus-stage-2-impl
    - optimus-stage-3-review
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

Two-phase code verification for Go projects.

---

## Phase 1: Static Analysis + Unit Tests (parallel)

Run ALL 6 commands simultaneously. Capture stdout, stderr, exit code, and duration for each.

| # | Command | What it checks |
|---|---------|---------------|
| 1 | `make lint` | Linter rules (golangci-lint or equivalent) |
| 2 | `go vet ./...` | Suspicious constructs the compiler doesn't catch |
| 3 | `goimports -l .` | Import ordering and missing/extra imports |
| 4 | `gofmt -l .` | Code formatting compliance |
| 5 | `make generate-docs` | Documentation generation (fails if docs are stale) |
| 6 | `go test -coverprofile=coverage-unit.out ./...` | Unit tests with coverage profiling |

**Execution rules:**
- Run all 6 in parallel (do not wait for one to finish before starting another)
- Capture output of each independently
- `goimports -l .` and `gofmt -l .` fail if they produce any output (listed files need fixing)
- If `make generate-docs` modifies files, report which files changed — this means docs were stale

**Phase 1 verdict:**
- ALL 6 pass → proceed to Phase 2
- ANY fails → still proceed to Phase 2, but final verdict will be NEEDS_FIX

---

## Phase 2: Integration + E2E Tests (sequential)

Run sequentially, continue even if one fails:

| # | Command | What it checks |
|---|---------|---------------|
| 7 | Integration tests with coverage (see below) | Integration tests (DB, external services) |
| 8 | `make test-e2e` | End-to-end tests (full user flows) |

**Integration test command:**
Run integration tests with coverage profiling. The exact command depends on the project:
- If `make test-integration` exists and supports coverage: `make test-integration COVER_FLAGS="-coverprofile=coverage-integration.out"`
- Otherwise: `go test -tags=integration -coverprofile=coverage-integration.out ./...`
- Check the Makefile to determine the correct approach

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

## Phase 2.5: Coverage Analysis

After Phase 2 completes, analyze test coverage from the generated profiles.

### Step 1: Extract Coverage Percentages

```bash
# Unit test coverage
go tool cover -func=coverage-unit.out | tail -1

# Integration test coverage (if profile exists)
go tool cover -func=coverage-integration.out | tail -1 2>/dev/null
```

### Step 2: Identify Coverage Gaps

For each coverage profile, identify packages/files with low coverage:

```bash
# List all packages with their coverage, sorted by lowest first
go tool cover -func=coverage-unit.out | grep -v "total:" | awk '{print $NF, $1}' | sort -n | head -20
```

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

## Phase 3: Test Scenario Gap Analysis

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

Use the best available droid:
1. `ring-default-ring-test-reviewer` (preferred)
2. `ring-dev-team-qa-analyst`
3. `worker` with the instructions above

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

## Phase 4: Executive Summary

After all phases complete, present the summary using the `<json-render>` format for rich terminal UI.

### Summary Structure

```
============================================
  VERIFICATION SUMMARY
============================================

Phase 1 — Static Analysis + Unit Tests: PASS / FAIL
Phase 2 — Integration + E2E Tests:      PASS / FAIL
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
- If `goimports` or `gofmt` are not installed, report as SKIP with note
- Always show the full summary even if everything passes
- Duration must be measured for each command individually
