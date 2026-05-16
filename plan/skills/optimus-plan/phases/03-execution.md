# Phase 3 (Execution): Cross-Reference, Test/Observability Analysis, Agent Dispatch

Loaded by `SKILL.md` after Phase 2 context is built. Implements the original
Phase 2: cross-referencing, test-gap analysis, observability analysis, and
parallel ring-droid dispatch.

### Step 2.1: Cross-Reference

For EACH item in the task spec, verify it exists and is consistent in the reference docs.
Flag any item that:
- Exists in the task spec but NOT in API contracts or data model
- Has different values between docs (field type, HTTP method, error code)
- References something that doesn't exist yet (table, endpoint, component)

> Use the 8 validation dimensions from `templates/validation-dimensions.md` as
> the checklist for what to cross-reference.

### Step 2.2: Analyze Test Gaps (MANDATORY — do NOT skip)

For EACH test type (unit, integration, E2E):
1. List every function/method/flow the task will create or modify
2. For each one, check every bullet from Dimension 5 in `templates/validation-dimensions.md`
3. For each uncovered bullet, add a row to the Test Coverage Gaps table
4. If all bullets are covered, write "NONE — verified: [list functions/flows checked]"

You MUST produce output for all 4 sub-sections (5a, 5b, 5c, 5d).

### Step 2.2.1: Cross-Reference Test Gaps with Future Tasks (MANDATORY)

For EACH test gap identified in Step 2.2:
1. **Search future tasks:** Scan the tasks file for any task that explicitly covers the missing test scenario (look for test-related acceptance criteria, testing strategy sections, or test IDs that match the gap)
2. **Classify each gap:**
   - **NOT PLANNED** — no future task covers this test. Flag as a gap in the current task.
   - **PLANNED IN T-XXX** — a future task explicitly includes this test. Note which task and what it covers.
3. **For gaps planned in future tasks**, evaluate and present to the user:
   - **Which future task** covers it (task ID and title)
   - **Opinion on timing:** Should the test be created now or is it reasonable to defer? Consider:
     - Does the current task introduce the code path that needs testing? If yes, recommend testing now.
     - Is the future task a dedicated testing task? If yes, deferring may be acceptable.
     - Does the gap create a risk window (untested code in production between tasks)?
   - **Ask the user** via `AskUser`: "Test gap [description] is planned for T-XXX. I recommend [now/deferring] because [reason]. Do you want to add this test to the current task?"

Add a column to the Test Coverage Gaps table:

```
| # | Type | Scenario Missing | Priority | Future Task | Recommendation |
|---|------|------------------|----------|-------------|----------------|
| 1 | Unit | Error path for X  | HIGH     | NOT PLANNED | Add to current task |
| 2 | Integration | Pagination edge case | MEDIUM | T-015 | Defer — dedicated test task |
| 3 | E2E | Empty state flow | HIGH | T-018 | Anticipate — current task creates this flow |
```

### Step 2.3: Analyze Observability Gaps (MANDATORY — do NOT skip)

For EACH new component:
1. Check existing logging patterns in the codebase
2. Verify new components follow them
3. Flag missing logs and missing structured fields for metrics

### Step 2.4: Dispatch Validation Agents (MANDATORY)

**HARD BLOCK:** Dispatch specialist ring droids in parallel to validate the task spec. Each agent receives file paths and can navigate the codebase autonomously.

**Ring droids are REQUIRED** — verify ring droids — see AGENTS.md Protocol: Ring Droid Requirement Check. **If any of the droids below are not available, STOP and inform the user:**
```
Required ring droids are not installed. Install them before running this skill:
  - ring:business-logic-reviewer
  - ring:security-reviewer
  - ring:qa-analyst
  - ring:code-reviewer
```

**Droids to dispatch:**

1. `ring:business-logic-reviewer` — validate business rules completeness, edge cases, and domain correctness in the task spec
2. `ring:security-reviewer` — identify security gaps in the spec (missing auth, input validation, data exposure risks)
3. `ring:qa-analyst` — validate testing strategy completeness, identify untested scenarios
4. `ring:code-reviewer` — assess architectural feasibility, identify patterns that may conflict with the codebase

**Agent prompt MUST include:**
```
Goal: Pre-implementation validation of task T-XXX — [your domain]

Context:
  - Project root: <absolute path to project worktree>
  - Task spec excerpt (already extracted in Doc Brief; full file at <TASKS_DIR>/<TaskSpec>)
  - Doc brief (READ FIRST — task-scoped excerpt of pre-dev docs, AGENTS.md protocols, project rules):
    .optimus/sessions/T-XXX/doc-brief.md
  - Subtasks dir: <TASKS_DIR>/subtasks/T-XXX/ (READ all .md files if dir exists; SKIP if absent)
  - Full pre-dev docs (only consult if Doc Brief is insufficient): <TASKS_DIR>/
  - Gaps already identified: [list from Steps 2.1-2.3]

IMPORTANT: You have access to Read, Grep, and Glob tools. USE THEM to:
  - Read files at the paths above
  - Search the codebase for patterns similar to what the spec describes
  - Find how similar features were implemented in the project
  - Discover existing test patterns, error handling conventions, and architectural styles
  - Explore related files not listed above when needed for context

Your job:
  Validate the task spec from your domain perspective BEFORE implementation.
  Identify risks, gaps, contradictions, or missing requirements.
  Report findings ONLY — do NOT generate code.

Required output:
  For each finding: severity, category, description, recommendation
  If no issues: "PASS — [domain] validation clean"

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
  1. What would break in production under load if this spec is implemented as-is?
  2. What's MISSING from the spec that should be there? (not just what's wrong)
  3. Does this spec trace back to business requirements? Flag orphan requirements
  4. How would a new developer understand and implement this spec 6 months from now?
  5. Search the codebase for how similar features were built — flag inconsistencies with existing patterns
```

**Special Instructions per Agent:**

Include per-droid quality checklists — see AGENTS.md Protocol: Per-Droid Quality Checklists.
Adapt checklist items to spec validation context (e.g., "verify X exists in spec" instead of
"verify X is implemented in code").

**QA agent** (`ring:qa-analyst`) must additionally (beyond the protocol):
- Spec quality: are ACs measurable and testable? (not vague like "works correctly")
- Does each AC specify both success AND failure behavior?
- Rollback/recovery strategy defined for failure cases
- Can a developer implement each item WITHOUT asking questions?

Merge agent findings with the findings from Steps 2.1-2.3. Deduplicate and sort by severity before presenting.
