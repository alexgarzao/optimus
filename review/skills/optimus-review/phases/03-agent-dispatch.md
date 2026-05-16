# Phase 3: Parallel Agent Dispatch

Loaded by `SKILL.md` after Phase 2 completes. Dispatch all review droids in parallel with the agent prompt template, severity classification, and special instructions per agent.

Dispatch ALL applicable agents simultaneously via `Task` tool. Each agent receives file paths and can navigate the codebase autonomously to gather context.

### Agent Roster

Dispatch specialist agents covering the validation domains below. Use the agent selection priority to pick the best available droid for each domain.

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
  - ring-dev-team-qa-analyst
```

**Droids to dispatch:**

| Validation Domain | When to Dispatch | Ring Droid |
|-------------------|------------------|------------|
| **Code Quality** — architecture, patterns, SOLID, DRY, maintainability | Always | `ring-default-code-reviewer` |
| **Business Logic** — domain correctness, edge cases, business rules | Always | `ring-default-business-logic-reviewer` |
| **Security** — vulnerabilities, OWASP, input validation, secrets | Always | `ring-default-security-reviewer` |
| **Test Quality** — coverage gaps, test quality, missing scenarios | Always | `ring-default-ring-test-reviewer` |
| **Nil/Null Safety** — nil pointer risks, unsafe dereferences | Always | `ring-default-ring-nil-safety-reviewer` |
| **Ripple Effects** — how changes propagate beyond changed files | Always | `ring-default-ring-consequences-reviewer` |
| **Dead Code** — orphaned code from changes | Always | `ring-default-ring-dead-code-reviewer` |
| **Frontend Patterns** — framework patterns, accessibility, performance | Frontend or full-stack tasks | `ring-dev-team-frontend-engineer` |
| **Backend Patterns** — language patterns, error handling, conventions | Backend or full-stack tasks | `ring-dev-team-backend-engineer-golang` |
| **Spec Compliance** — acceptance criteria, test IDs, API contracts | Always | `ring-dev-team-qa-analyst` |

### Agent Prompt Template

Each agent dispatch MUST include this information:

```
Goal: Post-task validation of T-XXX — [your validation domain]

Context:
  - Project root: <absolute path to project worktree>
  - Doc brief (READ FIRST — task-scoped excerpt of pre-dev docs, AGENTS.md protocols, project rules):
    .optimus/sessions/T-XXX/doc-brief.md
  - Full pre-dev docs (consult ONLY if Doc Brief is insufficient): <TASKS_DIR>/
  - Subtasks dir: <TASKS_DIR>/subtasks/T-XXX/ (READ all .md files if dir exists; SKIP if absent)
  - Changed files: [list of file paths] (READ each file)

IMPORTANT: You have access to Read, Grep, and Glob tools. USE THEM to:
  - Read files at the paths above
  - Search the codebase for patterns similar to the code under review
  - Find how the same problem was solved elsewhere in the project
  - Discover test patterns, error handling conventions, and architectural styles
  - Explore related files not listed above when needed for context

Your job:
  Validate the implementation against the spec, coding standards, and engineering
  best practices. Report issues ONLY — do NOT fix anything.

Required output format:
  For each issue found, provide:
  - Severity: CRITICAL / HIGH / MEDIUM / LOW
  - File: exact file path
  - Line: line number or range
  - Rule violated: exact reference (coding standards section, spec criterion, or named best practice)
  - Summary: one-line description
  - Detail: what is wrong, why it matters, what should be done

  If no issues found, state "PASS — no issues in [domain]"
  Always include a "What Was Done Well" section acknowledging good practices.

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

### Special Instructions per Agent

Include per-droid quality checklists — see AGENTS.md Protocol: Per-Droid Quality Checklists.

**Spec Compliance agent** (`ring-dev-team-qa-analyst`) must additionally (beyond the protocol):
1. List every acceptance criterion from the Ring source (via `TaskSpec` column) and mark PASS/FAIL/PARTIAL
2. List every test ID and verify a corresponding test exists
3. If the task has API endpoints, verify request/response format matches API contracts
4. If the task has DB changes, verify column types/constraints match the data model

---
