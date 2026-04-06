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
    - optimus-task-executor
    - optimus-post-task-validator
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
| 6 | `make test-unit` | Unit test suite |

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
| 7 | `make test-integration` | Integration tests (DB, external services) |
| 8 | `make test-e2e` | End-to-end tests (full user flows) |

**Execution rules:**
- Run `make test-integration` first
- Regardless of result, run `make test-e2e` next
- Capture output, exit code, and duration for each

---

## Phase 3: Executive Summary

After both phases complete, present the summary using the `<json-render>` format for rich terminal UI.

### Summary Structure

```
============================================
  VERIFICATION SUMMARY
============================================

Phase 1 — Static Analysis + Unit Tests: PASS / FAIL
Phase 2 — Integration + E2E Tests:      PASS / FAIL
Total time: Xs

┌───┬──────────────────────┬────────┬──────────┐
│ # │ Command              │ Status │ Duration │
├───┼──────────────────────┼────────┼──────────┤
│ 1 │ make lint            │ PASS   │ 3.2s     │
│ 2 │ go vet ./...         │ PASS   │ 1.1s     │
│ 3 │ goimports -l .       │ FAIL   │ 0.4s     │
│ 4 │ gofmt -l .           │ PASS   │ 0.3s     │
│ 5 │ make generate-docs   │ PASS   │ 2.1s     │
│ 6 │ make test-unit       │ PASS   │ 8.5s     │
│ 7 │ make test-integration│ PASS   │ 22.3s    │
│ 8 │ make test-e2e        │ SKIP   │ -        │
└───┴──────────────────────┴────────┴──────────┘

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
| All 8 commands pass | **MERGE_READY** |
| Any command fails | **NEEDS_FIX** |
| Integration or E2E not available (no Makefile target) | **SKIP** that command, do not count as failure |

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
