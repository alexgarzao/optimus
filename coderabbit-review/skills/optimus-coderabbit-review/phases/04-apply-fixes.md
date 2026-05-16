# Phase 4: Apply All Approved Fixes with TDD + Agent Validation

Loaded after Phase 3. Apply each approved fix following RED-GREEN-REFACTOR. Dispatch review agent for logic changes. Max 3 retries per test failure, max 1 skipped test per fix.

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
  - ring:code-reviewer
  - ring:business-logic-reviewer
  - ring:security-reviewer
  - ring:test-reviewer
  - ring:nil-safety-reviewer
  - ring:consequences-reviewer
  - ring:dead-code-reviewer
```

**Droids to dispatch:**

| Domain | When to Dispatch | Ring Droid |
|--------|-----------------|------------|
| **Code Quality** — architecture, SOLID, DRY, resilience, resource lifecycle, concurrency, performance, configuration, cognitive complexity, error handling, domain purity | Always | `ring:code-reviewer` |
| **Business Logic** — domain correctness, edge cases, spec traceability, data integrity, backward compatibility, API semantics | Always | `ring:business-logic-reviewer` |
| **Security** — vulnerabilities, OWASP, input validation, data privacy, error response leakage, rate limiting, auth propagation | Always | `ring:security-reviewer` |
| **Test Quality** — coverage gaps, error scenarios, flaky patterns, test effectiveness, false positive risk, test coupling, spec traceability | Always | `ring:test-reviewer` |
| **Nil/Null Safety** — nil pointer risks, unsafe dereferences, resource cleanup nil checks, channel/map/slice safety | Always | `ring:nil-safety-reviewer` |
| **Ripple Effects** — cross-file impacts, backward compatibility, configuration drift, migration paths, shared state, event contracts | Always | `ring:consequences-reviewer` |
| **Dead Code** — orphaned code, zombie test infrastructure, stale feature flags, deprecated paths | Always | `ring:dead-code-reviewer` |

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

Verification scope (MANDATORY):
  Static analysis (lint, vet, format) and tests (unit, integration, coverage)
  have already been run by the orchestrator. Results are in this prompt or in
  the log files referenced under .optimus/logs/.
  - Do NOT run verification commands yourself. Forbidden: `go test`, `npm test`,
    `npm run test`, `pytest`, `make test`, `make lint`, `make test-coverage`,
    `make test-integration`, `golangci-lint`, `go vet`, `goimports`, `gofmt`,
    `prettier`, `eslint`, `tsc`, or any equivalent.
  - If you need test/coverage details, Read the log files referenced in this
    prompt — do not regenerate them.
  - Use Read, Grep, and Glob to inspect source files. Reserve Bash for read-only
    git inspection (`git log`, `git blame`, `git diff`) when needed.

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
(`ring:functional-writer`, `ring:api-writer`). Documentation
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
