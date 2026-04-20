---
name: optimus-deep-review
description: >
  Parallel code review with consolidation, deduplication, and interactive
  finding-by-finding resolution. Supports initial (5 agents, critical gaps)
  and final (7 agents, full coverage including stack idiomaticity) review modes.
  Flexible scope: entire project, git diff, or specific directory.
trigger: >
  - When user requests code review (e.g., "review the code", "code review")
  - Before creating a pull request or merging a branch
  - After completing a feature and wanting quality validation
skip_when: >
  - Reviewing documentation only (use optimus-deep-doc-review instead)
  - Validating a specific task against its spec (use optimus-cycle-impl-review-stage-3 instead)
  - Running automated checks only (use optimus-verify-code instead)
prerequisite: >
  - Project has source code to review
  - Code is accessible in the repository
NOT_skip_when: >
  - "Code already works" -- Working code can still have security issues, maintainability problems, and missing edge cases.
  - "It's a small change" -- Small changes can introduce regressions and security vulnerabilities.
  - "We'll review later" -- Later reviews accumulate debt and miss context.
  - "CI will catch it" -- CI catches syntax and test failures, not architectural or business logic issues.
examples:
  - name: Initial review during development
    invocation: "Review the code (initial)"
    expected_flow: >
      1. Ask scope (all files, git diff, directory)
      2. Dispatch 5 agents in parallel
      3. Consolidate and deduplicate findings
      4. Present overview table
      5. Walk through findings one by one
      6. Apply approved fixes
      7. Present summary
  - name: Final review before merge
    invocation: "Final code review before merge"
    expected_flow: >
      1. Ask scope
      2. Dispatch 7 agents in parallel (includes stack-specific agents)
      3. Consolidate, present, resolve findings
      4. Apply fixes, present summary
  - name: Review specific directory
    invocation: "Review the code in internal/handler/"
    expected_flow: >
      1. Scope already defined, ask review type
      2. Dispatch agents scoped to the directory
      3. Standard flow
related:
  complementary:
    - optimus-cycle-impl-stage-2
    - optimus-cycle-pr-review-stage-4
    - optimus-verify-code
  differentiation:
    - name: optimus-cycle-impl-review-stage-3
      difference: >
        optimus-cycle-impl-review-stage-3 validates a completed task against its spec
        (acceptance criteria, test IDs, spec compliance). optimus-deep-review is
        a generic code review without task/spec context -- focused on code quality,
        security, and best practices.
    - name: optimus-verify-code
      difference: >
        optimus-verify-code runs automated checks (lint, vet, tests) and reports
        pass/fail. optimus-deep-review dispatches specialist agents for deep
        analysis that automated tools cannot catch.
  sequence:
    before:
      - optimus-verify-code
verification:
  manual:
    - All findings presented to user
    - Approved corrections applied correctly
    - Final summary presented
---

# Deep Review

Parallel code review with specialist agents, consolidation, deduplication, and interactive finding-by-finding resolution.

---

## Phase 0: Review Scope

Before starting, determine the review parameters.

### Step 0.1: Determine Review Type

Ask the user which type of review:

- **Initial** (recurring review during development): 5 agents, focused on correctness and critical gaps
- **Final** (review before merge/deployment): 7 agents, full coverage including stack idiomaticity

### Step 0.2: Determine Scope

Ask the user what to review:

- **All project files** — full codebase review
- **Changed files only** — use `git diff --name-only` to identify (optionally against a base branch)
- **Specific directory or feature** — user specifies the path

### Step 0.3: Load Context

1. **Identify stack:** Check for `go.mod`, `package.json`, `Makefile`, `Cargo.toml`, etc.
2. **Identify project rules and AI instructions (MANDATORY):** Search for these files and read ALL that exist:
   - `AGENTS.md`, `CLAUDE.md`, `DROIDS.md`, `.cursorrules` (repo root)
   - `PROJECT_RULES.md` (repo root or `docs/`)
   - `.editorconfig`, `docs/coding-standards.md`, `docs/conventions.md`
   - `.github/CONTRIBUTING.md` or `CONTRIBUTING.md`
   - Linter configs: `.eslintrc*`, `biome.json`, `.golangci.yml`, `.prettierrc*`

   These are the **source of truth** for coding standards. Pass relevant sections to every agent dispatched.
3. **Identify reference docs:** Look for PRD, TRD, API design, data model — these provide context but are not the primary validation target (unlike optimus-cycle-impl-review-stage-3)
4. **Read all files in scope:** Load the full content of every file that will be reviewed

---

## Phase 1: Parallel Agent Dispatch

Dispatch ALL applicable agents simultaneously via `Task` tool. Each agent receives the files in scope plus any reference docs found.

**Ring droids are REQUIRED.** If the core review droids are not installed, **STOP** and inform the user:
```
Required ring droids are not installed. Install them before running this skill:
  - ring-default-code-reviewer
  - ring-default-business-logic-reviewer
  - ring-default-security-reviewer
  - ring-default-ring-test-reviewer
```

### Initial Review (5 agents)

| # | Agent | Focus | Ring Droid |
|---|-------|-------|------------|
| 1 | **Code quality reviewer** | Architecture, design patterns, SOLID, DRY, maintainability, algorithmic flow | `ring-default-code-reviewer` |
| 2 | **Business logic reviewer** | Domain correctness, business rules, edge cases, requirements compliance | `ring-default-business-logic-reviewer` |
| 3 | **Security reviewer** | Vulnerabilities, authentication, input validation, OWASP, secrets | `ring-default-security-reviewer` |
| 4 | **Test quality analyst** | Test coverage gaps (unit, integration, E2E), error scenario coverage, flaky patterns | `ring-default-ring-test-reviewer` |
| 5 | **Cross-file consistency** | Interfaces vs implementations, DTOs, imports, registered routes, shared constants, dead code | `ring-default-ring-consequences-reviewer` |

### Final Review (7 agents — includes the 5 above plus)

| # | Agent | Focus | Ring Droid |
|---|-------|-------|------------|
| 6 | **Backend specialist** | Language idiomaticity, performance, concurrency, ecosystem patterns | `ring-dev-team-backend-engineer-golang` (Go) / `ring-dev-team-backend-engineer-typescript` (TS) |
| 7 | **Frontend specialist** | Framework patterns, hooks, components, accessibility, responsive design, performance | `ring-dev-team-frontend-engineer` |

### Agent Prompt Template

Each agent dispatch MUST include:

```
Goal: Code review — [validation domain]

Context:
  - Review type: Initial / Final
  - Scope: [files or directory being reviewed]
  - Coding standards: [paste relevant sections]
  - Reference docs: [paste relevant sections if available]
  - Files to review (full content follows):
    [paste full content of each file with filename header]

Your job:
  Review the code for issues in your domain. Report issues ONLY — do NOT fix anything.

Required output format:
  For each issue found, provide:
  - Severity: CRITICAL / HIGH / MEDIUM / LOW
  - File: exact file path
  - Line: line number or range
  - Description: what is wrong and why it matters
  - Recommendation: concrete fix suggestion

  If no issues found, state "PASS — no issues in [domain]"
  Include a "What Was Done Well" section acknowledging good practices.
```

---

## Phase 2: Consolidation and Triage

After ALL agents return:

1. **Merge** all findings into a single list
2. **Deduplicate** — if multiple agents flag the same issue (same file + same concern), keep one entry and note which agents agreed
3. **Filter false positives** — verify in the code that each reported issue actually exists
4. **Sort** by severity: CRITICAL > HIGH > MEDIUM > LOW
5. **Assign** sequential IDs (F1, F2, F3...)

### Severity Classification

| Severity | Criteria |
|----------|----------|
| **CRITICAL** | Security vulnerability, data loss risk, auth bypass, broken business rule |
| **HIGH** | Missing validation, coding standards violation, missing error handling, broken accessibility |
| **MEDIUM** | Code quality concern, pattern inconsistency, maintainability issue, missing edge case test |
| **LOW** | Polish, minor style, optional improvement |

---

## Phase 3: Present Overview

Present the full findings table for a bird's-eye view:

```markdown
## Deep Review — X findings across Y agents

| # | Severity | File | Description | Agent(s) |
|---|----------|------|-------------|----------|
| F1 | CRITICAL | auth.go | ... | Security |
| F2 | HIGH | handler.go | ... | Code, QA |
| F3 | MEDIUM | layout.tsx | ... | Frontend, Cross-file |

### Summary by Severity
- CRITICAL: X
- HIGH: X
- MEDIUM: X
- LOW: X
```

---

## Phase 4: Interactive Finding-by-Finding Resolution

Findings are presented ONE AT A TIME, decisions collected for ALL, then fixes applied ALL AT ONCE in Phase 4.5.

**=== MANDATORY — Progress Tracking (NEVER SKIP) ===**

**BEFORE presenting the first finding, you MUST:**
1. Count the TOTAL number of findings (N)
2. Display the total prominently: `"### Total findings to review: N"`

**For EVERY finding presented, you MUST:**
1. Include `"Finding X of N"` in the header
2. X starts at 1 and increments sequentially
3. N is the total announced above and NEVER changes mid-review

Present findings ONE AT A TIME, in severity order (CRITICAL first, LOW last).

For EACH finding, present:

### 1. Finding Header

`## [SEVERITY] F# | [Category]`
- Source agent(s)
- File and line number

### 2. Problem Description

- Clear description of the issue with code snippet if applicable
- Why it matters — what breaks, what risk it creates
- Reference to coding standard or best practice violated

### 3. Proposed Solutions

One or more approaches, each with:
- What changes
- Tradeoffs (complexity, performance, breaking changes)
- If it's a straightforward fix with no tradeoffs, state explicitly: "Direct fix, no tradeoffs."

Include a recommendation when one option is clearly better.

### 4. Wait for User Decision

Use `AskUser` tool. **BLOCKING**: Do NOT advance to the next finding until the user decides.
**Every AskUser MUST include a "Tell me more" option** alongside the fix/skip options.

**IMMEDIATE RESPONSE RULE:** If the user selects "Tell me more" or responds with free text
(a question, disagreement, or request for clarification) instead of a decision:
**STOP IMMEDIATELY.** Do NOT continue to the next finding. Do NOT batch the response.
Research the user's concern RIGHT NOW using `WebSearch`, codebase analysis, or both.
Provide a thorough answer with evidence. Only AFTER the user is satisfied, re-present the
options and ask for their decision again. **NEVER defer to the end of the findings loop.**

The user may:
- Approve an option (e.g., "A", "B")
- Select "Tell me more" for deeper analysis
- Discard the finding
- Defer to a future version
- Group with the next finding if related

### 5. After Decision

Record the decision internally. Do NOT apply any fix yet — all fixes are applied in Phase 4.5 after ALL decisions are collected.

- **Approved:** Record finding ID, chosen option. Move to next finding.
- **Discarded:** Record as discarded. Move to next finding.
- **Deferred:** Record destination (backlog, tasks). Move to next finding.

### Optimization for Simple Findings

For findings with a direct, unambiguous fix: present the problem + proposed fix + "Accept?" in a single block to speed up the flow.

### Batch Processing

If there are 3+ findings of the same nature (e.g., "inconsistent import path in 5 files"), group them and present as a batch with the list of affected files. Ask if all can be applied at once.

---

## Phase 4.5: Batch Apply All Approved Fixes

**IMPORTANT:** This phase runs ONCE, after ALL findings have been presented and ALL decisions
collected in Phase 4. No fix is applied during Phase 4.

### Step 4.5.1: Present Pre-Apply Summary

```markdown
## Fixes to Apply (X of Y findings)

| # | Finding | Decision | Files Affected |
|---|---------|----------|---------------|

### Skipped (Z findings)
| # | Finding | Reason |
|---|---------|--------|

### Deferred (W findings)
| # | Finding | Destination |
|---|---------|-------------|
```

### Step 4.5.2: Apply Fixes

For each approved fix, apply the change. After each fix, confirm what changed in 1-2 sentences.

For fixes that alter execution flow, conditions, or observable behavior, run unit tests
after the fix to verify no regressions.

### Step 4.5.3: Final Lint Check

After ALL fixes are applied, run lint once (if available):
```bash
make lint
```
If lint fails, fix formatting issues.

---

## Phase 4.6: Convergence Loop (MANDATORY)

After Phase 4.5, automatically re-validate using fresh sub-agents to eliminate session bias.

**CRITICAL — Why Fresh Sub-Agents:**

The primary failure mode of convergence loops is **false convergence**: the orchestrator
re-runs analysis in the same session, with the same mental model, and declares "zero new
findings" — not because there are none, but because it can't see past its own prior reasoning.

The solution: **rounds 2+ are executed by a fresh sub-agent** dispatched via `Task` tool.
The sub-agent has zero context from prior rounds, reads all files from scratch, and returns
findings independently. The orchestrator then deduplicates against the cumulative ledger.

**Round structure:**

| Round | Who analyzes | How |
|-------|-------------|-----|
| **1** (initial) | Orchestrator (this agent) | Phase 1 (parallel agent dispatch) + Phase 2 (consolidate) — normal flow |
| **2** (mandatory) | **Fresh sub-agent** via `Task` | Sub-agent reads all files from scratch, reviews independently, returns findings |
| **3-5** | **Fresh sub-agent** via `Task` | Same as round 2 — only triggered if round 2+ found new findings |

**Round 2 is MANDATORY.** The "zero new findings" stop condition can only trigger starting from round 3.

**Fresh sub-agent dispatch (rounds 2+):**

Dispatch a single sub-agent via `Task` tool (use `ring-default-code-reviewer` or any
available ring review droid). The sub-agent receives:

1. **All files in scope** — full content, re-read fresh from disk
2. **Project rules and coding standards** — re-read fresh
3. **The findings ledger** — for deduplication ONLY

```
Goal: Independent code review (convergence round X of 5)

You are a FRESH reviewer with NO prior context. Review from scratch.

Context:
  - Review type: Initial / Final
  - Files to review: [full content — re-read from disk]
  - Project rules: [full content — re-read from files]

Previously identified findings (for DEDUP ONLY):
  [list of findings with IDs and descriptions]

CRITICAL: Analyze INDEPENDENTLY. Do NOT skip areas because previous rounds
"already covered" them. The orchestrator will dedup.

Required output:
  For each finding: severity, file, line, category, description, recommendation
  If no issues: "PASS — all domains clean"
```

**Orchestrator deduplication after sub-agent returns:**

1. Compare each sub-agent finding against the cumulative ledger (match by file + topic + description similarity)
2. **Genuinely new findings** → add to ledger, present to user via Phase 4 (interactive resolution)
3. **Duplicates** → discard silently

**Loop rules:**
- Max 5 rounds (initial = round 1)
- **Round 2 is MANDATORY** — always dispatch a fresh sub-agent regardless of round 1 results
- Show `"=== Re-validation round X of 5 (fresh sub-agent) ==="` at start
- **If new findings exist:** Present them using Phase 4, fix via Phase 4.5, then loop again
- **Stop conditions (any one triggers exit):**
  1. Zero new findings — **only valid from round 3 onward** (round 2 is mandatory)
  2. Round 5 completed (hard limit)
  3. User explicitly requests to stop
- **LOW severity findings are NOT a reason to stop** — ALL findings are presented to the user

**Round summary (show after each round):**

```markdown
### Round X of 5 (fresh sub-agent) — Summary
- New findings this round: N (C critical, H high, M medium, L low)
- Cumulative: X total findings across Y rounds
- Fixed: A | Skipped: B | Deferred: C
- Status: CONVERGED / CONTINUING / HARD LIMIT REACHED
```

---

## Phase 5: Final Summary

After the convergence loop exits and all findings are processed:

```markdown
## Deep Review — Summary

### Fixed (X findings)
| # | Severity | File(s) | Fix Applied |
|---|----------|---------|-------------|

### Discarded (X findings)
| # | Severity | File(s) | Reason |
|---|----------|---------|--------|

### Deferred (X findings)
| # | Severity | File(s) | Destination |
|---|----------|---------|-------------|

### Statistics
- Total findings: X
- Fixed: X
- Discarded: X
- Deferred: X
- Files modified: [list]
```

**Do NOT commit automatically.** Present the summary and wait for the user to decide whether to commit.

---

## Rules

- Every finding must reference a specific standard, best practice, or measurable risk — "I would do it differently" is NOT a valid finding
- One finding at a time, severity order (CRITICAL > HIGH > MEDIUM > LOW)
- No changes without explicit user approval
- Prioritize correctness over convenience
- If a fix involves logic changes (flow, conditions, behavior), mention explicitly
- Follow coding standards found in the project (PROJECT_RULES.md or equivalent)
- After each fix, update the todo list to maintain progress visibility
- If the codebase already does the same thing elsewhere without issue, it is NOT a finding
- Ring droids are required — do not proceed without them
- Do NOT fix anything during agent dispatch or consolidation — fixes happen only in Phase 4 after user approval
- The agent NEVER decides whether a finding should be fixed or skipped — the USER always decides
- ALL findings (CRITICAL, HIGH, MEDIUM, and LOW) MUST be presented to the user for decision
- The agent may recommend an option, but MUST wait for user approval via AskUser before proceeding
- Do NOT auto-skip, auto-dismiss, or auto-resolve any finding regardless of severity
