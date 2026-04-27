---
name: optimus-deep-review
description: "Parallel code review with consolidation, deduplication, and interactive finding-by-finding resolution. Auto-discovers installed Ring review droids and dispatches all that are relevant to the project stack. Flexible scope: entire project, git diff, or specific directory."
trigger: >
  - When user requests code review (e.g., "review the code", "code review")
  - Before creating a pull request or merging a branch
  - After completing a feature and wanting quality validation
skip_when: >
  - Reviewing documentation only (use optimus-deep-doc-review instead)
  - Validating a specific task against its spec (use optimus-review instead)
  - Running automated checks only (use `make lint && make test` directly)
prerequisite: >
  - Project has source code to review
  - Code is accessible in the repository
NOT_skip_when: >
  - "Code already works" -- Working code can still have security issues, maintainability problems, and missing edge cases.
  - "It's a small change" -- Small changes can introduce regressions and security vulnerabilities.
  - "We'll review later" -- Later reviews accumulate debt and miss context.
  - "CI will catch it" -- CI catches syntax and test failures, not architectural or business logic issues.
examples:
  - name: Review changed files
    invocation: "Review the code"
    expected_flow: >
      1. Ask scope (all files, git diff, directory)
      2. Auto-discover installed Ring review droids
      3. Present droid list for confirmation
      4. Dispatch all confirmed droids in parallel
      5. Consolidate and deduplicate findings
      6. Walk through findings one by one
      7. Apply approved fixes, present summary
  - name: Review specific directory
    invocation: "Review the code in internal/handler/"
    expected_flow: >
      1. Scope already defined
      2. Auto-discover droids, filter by project stack
      3. Dispatch, consolidate, resolve, apply
related:
  complementary:
    - optimus-build
    - optimus-pr-check
  differentiation:
    - name: optimus-review
      difference: >
        optimus-review validates a completed task against its spec
        (acceptance criteria, test IDs, spec compliance). optimus-deep-review is
        a generic code review without task/spec context -- focused on code quality,
        security, and best practices.
verification:
  manual:
    - All findings presented to user
    - Approved corrections applied correctly
    - Convergence loop run, skipped, or stopped (status recorded)
    - Final summary presented
---

# Deep Review

Parallel code review with specialist agents, consolidation, deduplication, and interactive finding-by-finding resolution.

---

## Phase 1: Review Scope and Droid Discovery

### Step 1.1: Determine Scope

Ask the user what to review:

- **All project files** — full codebase review
- **Changed files only** — use `git diff --name-only` to identify (optionally against a base branch)
- **Specific directory or feature** — user specifies the path

### Step 1.2: Load Context

1. **Identify stack:** Check for `go.mod`, `package.json`, `Makefile`, `Cargo.toml`, etc.
2. **Verify Makefile targets (HARD BLOCK):** The project MUST have a `Makefile` with `lint` and `test` targets. If either is missing, **STOP**: "Project is missing required Makefile targets (`make lint`, `make test`). Add them before running deep-review."
3. **Identify project rules and AI instructions (MANDATORY):** Execute project rules discovery — see AGENTS.md Protocol: Project Rules Discovery.
4. **Identify reference docs:** Look for PRD, TRD, API design, data model — these provide context but are not the primary validation target (unlike optimus-review)
5. **Read all files in scope:** Load the full content of every file that will be reviewed
6. **Initialize .optimus directory (HARD BLOCK):** Execute Protocol: Initialize .optimus Directory — see AGENTS.md Protocol: Initialize .optimus Directory. This guarantees `.optimus/logs/` exists AND is gitignored before any `_optimus_quiet_run` call creates log files.

### Step 1.3: Auto-Discover Review Droids

**1. Discover installed review droids:**

Execute `Protocol: Discover Review Droids` — see AGENTS.md Protocol: Discover Review Droids. Default `INCLUDE_NON_RING=false`.

If the protocol returns `MIN_NOT_MET`, **STOP** and inform the user:

```
Required ring droids not installed. Install at minimum
`ring-default-code-reviewer` and `ring-default-security-reviewer`,
then re-run.
```

**2. Opt-in question for non-ring agents:**

Let `M` be the count of non-ring agents that PASS the protocol's filter (i.e.,
would actually be added to the roster if the user opts in). Implementation
hint: dry-run `Protocol: Discover Review Droids` with `INCLUDE_NON_RING=true`
first, count the non-ring entries it returns AFTER applying the protocol's
exclusion list and description filter — that count is `M`. Do NOT use the raw
count of `*.md` files under `~/.factory/droids/`; many of those would be
excluded by the protocol.

If `M > 0`, ask the user via `AskUser`:

```
Include M non-ring agents (e.g., my-custom-reviewer, third-party-auditor)? [y/N]
```

(List up to 3 example IDs.) Default answer is **N** (preserves current ring-only behavior).

If the user picks **Y**, re-run the same protocol — see AGENTS.md Protocol: Discover Review Droids. Use
`INCLUDE_NON_RING=true` and merge the additional non-ring entries into the roster.

If `M = 0`, skip this question entirely.

**3. Present the selected droids to the user for confirmation:**

Render the roster as returned by `Protocol: Discover Review Droids`, grouped
by `Ring Core / Ring Stack / Ring Domain / Non-Ring`. Each entry must show
`id`, `focus` (one-line summary derived from the description), and `source`
(`ring` or `non-ring`). The exact set of agents and groups depends on what
the protocol returned for this project — do NOT hardcode a list here.

Example shape (illustrative only; actual contents come from the protocol):

```
Discovered N review droids for this project (stack: Go):

  Ring Core
    - <id> — <focus>
    - ...

  Ring Stack
    - <id> — <focus>

  Ring Domain
    - <id> — <focus>
    - ...

  Non-Ring                       (only when INCLUDE_NON_RING=true)
    - <id> — <focus>

Confirm roster? [y/N]
```

Options via `AskUser`:
- **Proceed with all** — dispatch all listed droids
- **Remove some** — user specifies which to exclude

**BLOCKING:** Do NOT dispatch until the user confirms.

---

## Phase 2: Parallel Agent Dispatch

Dispatch ALL confirmed droids from Step 1.3 simultaneously via `Task` tool. Each agent
receives file paths and can navigate the codebase autonomously.

**If zero droids were confirmed** (user removed all, or none were discovered), **STOP**:
"No review droids available. Install Ring review droids before running this skill."

### Agent Prompt Template

Each agent dispatch MUST include:

```
Goal: Code review — [validation domain]

Context:
  - Project root: <absolute path to project worktree>
  - Scope: [files or directory being reviewed — list of file paths]
  - Project rules: AGENTS.md, PROJECT_RULES.md, docs/PROJECT_RULES.md (READ all that exist)
  - Reference docs: [list paths to any reference docs found] (READ if relevant to your domain)

IMPORTANT: You have access to Read, Grep, and Glob tools. USE THEM to:
  - Read files at the paths above
  - Search the codebase for patterns similar to the code under review
  - Find how the same problem was solved elsewhere in the project
  - Discover test patterns, error handling conventions, and architectural styles
  - Explore related files not listed above when needed for context

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

Cross-cutting analysis (MANDATORY for all agents):
  1. What would break in production under load with this code?
  2. What's MISSING that should be here? (not just what's wrong)
  3. Does this code trace back to a spec requirement? Flag orphan code without spec backing
  4. How would a new developer understand this code 6 months from now?
  5. Search the codebase for how similar problems were solved — flag inconsistencies with existing patterns
```

### Special Instructions per Agent

Include per-droid quality checklists — see AGENTS.md Protocol: Per-Droid Quality Checklists.

---

## Phase 3: Consolidation and Triage

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

## Phase 4: Present Overview

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

## Phase 5: Interactive Finding-by-Finding Resolution

Findings are presented ONE AT A TIME, decisions collected for ALL, then fixes applied ALL AT ONCE in Phase 6.

**=== MANDATORY — Progress Tracking (NEVER SKIP) ===**

**BEFORE presenting the first finding, you MUST:**
1. Count the TOTAL number of findings (N)
2. Display the total prominently: `"### Total findings to review: N"`

**For EVERY finding presented, you MUST:**
1. Include `"(X/N)"` progress prefix in the header
2. X starts at 1 and increments sequentially
3. N is the total announced above and NEVER changes mid-review

Present findings ONE AT A TIME, in severity order (CRITICAL first, LOW last).

For EACH finding, present:

### 1. Finding Header

`## (X/N) [SEVERITY] F# | [Category]`
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

**AskUser `[topic]` format:** Format: `(X/N) F#-Category`.
Example: `[topic] (8/12) F8-DeadCode`.

Use `AskUser` tool. **BLOCKING**: Do NOT advance to the next finding until the user decides.
**Every AskUser MUST include these options:**
- One option per proposed solution (Option A, Option B, Option C, etc.)
- Skip — no action
- Tell me more — if selected, STOP and answer immediately (do NOT continue to next finding)

**AskUser template (MANDATORY — follow this exact structure for every finding):**
```
1. [question] (X/N) SEVERITY — Finding title summary
[topic] (X/N) F#-Category
[option] Option A: recommended fix
[option] Option B: alternative approach
[option] Skip
[option] Tell me more
```

**HARD BLOCK — IMMEDIATE RESPONSE RULE:** If the user selects "Tell me more" or responds
with free text: **STOP IMMEDIATELY.** Do NOT continue to the next finding. Research and
answer RIGHT NOW. Only after the user is satisfied, re-present the SAME finding's options.
**NEVER defer to the end of the findings loop.**

**Anti-rationalization (excuses the agent MUST NOT use):**
- "I'll address all questions after presenting the remaining findings" — NO
- "Let me continue with the next finding and come back to this" — NO
- "I'll research this after the findings loop" — NO
- "This is noted, moving to the next finding" — NO

The user may:
- Approve an option (e.g., "A", "B")
- Select "Tell me more" for deeper analysis
- Discard the finding
- Defer to a future version
- Group with the next finding if related

### 5. After Decision

Record the decision internally. Do NOT apply any fix yet — all fixes are applied in Phase 6 after ALL decisions are collected.

- **Approved:** Record finding ID, chosen option. Move to next finding.
- **Discarded:** Record as discarded. Move to next finding.
- **Deferred:** Record destination (backlog, tasks). Move to next finding.

### Optimization for Simple Findings

For findings with a direct, unambiguous fix: present the problem + proposed fix + "Accept?" in a single block to speed up the flow.

**Same-nature grouping:** applied automatically per AGENTS.md "Finding Presentation" item 3.

---

## Phase 6: Batch Apply All Approved Fixes

**IMPORTANT:** This phase runs ONCE, after ALL findings have been presented and ALL decisions
collected in Phase 5. No fix is applied during Phase 5.

### Step 6.1: Present Pre-Apply Summary

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

### Step 6.2: Apply Fixes

For each approved fix, apply the change. After each fix, confirm what changed in 1-2 sentences.

For fixes that alter execution flow, conditions, or observable behavior, run unit
tests after the fix to verify no regressions — quietly, via
`_optimus_quiet_run "make-test" make test` (see AGENTS.md Protocol: Quiet Command
Execution).

### Step 6.2.1: Handle Test Failures

If tests fail after applying a fix (maximum 3 attempts per fix):

1. **Logic bug** — adjust the fix, re-run tests
2. **Flaky test** — re-execute at least 3 times in a clean environment to confirm flakiness.
   Maximum 1 test skipped per fix. Document explicit justification (error message,
   flakiness evidence) and tag with `pending-test-fix`
3. **External dependency** — pause and wait for restoration

If tests fail after 3 attempts to fix, revert the offending fix and ask the user.

### Step 6.3: Final Lint Check

After ALL fixes are applied, run lint once (if available), wrapped in
`_optimus_quiet_run` — see AGENTS.md Protocol: Quiet Command Execution:
```bash
_optimus_quiet_run "make-lint" make lint
```
If lint fails, fix formatting issues.

### Step 6.4: Coverage Measurement

Measure coverage — see AGENTS.md Protocol: Coverage Measurement.
If coverage is below threshold, add findings to the results.

### Step 6.5: Test Scenario Gap Analysis

Dispatch a test gap analyzer via `Task` tool. Use `ring-default-ring-test-reviewer` or `ring-dev-team-qa-analyst`.

The agent receives file paths and can navigate the codebase autonomously.

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

---

## Phase 7: Convergence Loop (Optional — Gated)

Execute the opt-in convergence loop — see AGENTS.md "Common Patterns > Protocol: Convergence Loop (Full Roster Model — Opt-In, Gated)".

**Behavioral contract for THIS phase:**
- Round 1 already ran in Phase 2. THIS phase only handles rounds 2 through 5.
- Present the **entry gate** before round 2 (`Run round 2` / `Skip convergence loop`).
- Present the **per-round gate** before rounds 3, 4, 5 (`Continue` / `Stop here`).
- If a dispatched round produces ZERO new findings, declare convergence and exit
  silently — DO NOT ask the user whether to run another round.
- Record the final loop status (`CONVERGED` / `USER_STOPPED` / `SKIPPED` /
  `HARD_LIMIT` / `DISPATCH_FAILED_ABORTED`) for the Final Summary.

**Stage-specific scope for convergence rounds 2+:**
Dispatch the **same droids confirmed in Step 1.3**. Each agent receives file paths and
project rules (re-read fresh from disk). Do NOT include the findings ledger in agent
prompts — the orchestrator handles dedup using strict matching (same file + same line
range ±5 + same category).

Include the scope from Phase 1, plus the cross-cutting analysis instructions (same 5
items from Phase 2 prompt).

**Failure handling:** If a dispatched agent slot fails (Task tool error, ring droid
unavailable), do NOT count as zero findings. Ask the user via `AskUser` whether to
retry the round or stop (status `DISPATCH_FAILED_ABORTED` if user stops).

When the loop exits (any status), proceed to Phase 8 (Final Summary).

---

## Phase 8: Final Summary

After the convergence loop exits and all findings are processed:

```markdown
## Deep Review — Summary

### Convergence
- Rounds dispatched (round 1 + convergence rounds): X
- Status: CONVERGED | USER_STOPPED | SKIPPED | HARD_LIMIT | DISPATCH_FAILED_ABORTED

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
- Do NOT fix anything during agent dispatch or consolidation — fixes happen only in Phase 6 after user approval
- The agent NEVER decides whether a finding should be fixed or skipped — the USER always decides
- ALL findings (CRITICAL, HIGH, MEDIUM, and LOW) MUST be presented to the user for decision
- The agent may recommend an option, but MUST wait for user approval via AskUser before proceeding
- Do NOT auto-skip, auto-dismiss, or auto-resolve any finding regardless of severity

<!-- INLINE-PROTOCOLS:START -->
## Shared Protocols (from AGENTS.md)

The following protocols are referenced by this skill. They are
extracted from the Optimus AGENTS.md to make this plugin self-contained.

### Protocol: Resolve Main Worktree Path (summarized)

> **Summary inlined here. Full recipe at `AGENTS.md -> Protocol: Resolve Main Worktree Path`.**

**Summary:** Resolve `MAIN_WORKTREE` once via `git worktree list --porcelain | awk '/^worktree / {print $2; exit}'` with `${MAIN_WORKTREE:?…}` defensive guard. Use `${MAIN_WORKTREE}/.optimus/...` for ALL `.optimus/` paths (gitignored, so doesn't propagate across linked worktrees). See full recipe in AGENTS.md.

### Finding Presentation (Unified Model) (summarized)

> **Summary inlined here. Full recipe at `AGENTS.md -> Finding Presentation (Unified Model)`.**

**Summary:** Common pattern for cycle review skills (plan, build, review, pr-check, deep-review, deep-doc-review, coderabbit-review): collect findings, dedup, group same-nature, present ONE-AT-A-TIME via AskUser with strict `[topic]/[option]` template, collect ALL decisions before applying ANY fixes. Mandatory: `(X/N)` progress prefix per finding; ALL findings presented (no auto-skip by severity); HARD BLOCK on "Tell me more" or free-text response — STOP and answer immediately, never defer to end of loop. Anti-rationalization defenses listed inline ("I'll address questions at end" — NO). Scope of structured template: finding-decision AskUsers in cycle review skills only; admin AskUsers MAY use prose. See full pattern + anti-rationalization examples in AGENTS.md.

All cycle review skills follow this pattern:
1. Collect findings from agents/tools
2. Consolidate and deduplicate
3. **Group same-nature findings** — after deduplication, identify findings that share the
   same root cause or fix pattern (e.g., "missing error handling" in 5 handlers, "inconsistent
   import path" in 4 files). If 2+ findings are of the same nature, merge them into a **single
   grouped entry** listing all affected files/locations. Each group counts as ONE item in the
   `"(X/N)"` sequence. The user makes ONE decision for the entire group.
4. Announce total findings count: `"### Total findings to review: N"` (where N reflects
   grouped entries — a group of 5 same-nature findings counts as 1)
5. Present overview table with severity counts
6. **Deep research BEFORE presenting each finding** (see research checklist below)
7. Walk through findings ONE AT A TIME with `"(X/N)"` progress prefix in the header, ordered by severity
   (CRITICAL first, then HIGH, MEDIUM, LOW). **ALL findings MUST be presented regardless of
   severity** — the agent NEVER skips, filters, or auto-resolves any finding. The decision to
   fix or skip is ALWAYS the user's. For grouped entries, list all affected files/locations
   within the single presentation.
8. For each finding: present research-backed analysis + options, collect decision via AskUser.
   **Every AskUser for a finding decision MUST include these options:**
   - One option per proposed solution (Option A, Option B, Option C, etc.)
   - Skip — no action
   - Tell me more — if selected, STOP and answer immediately (do NOT continue to next finding)

### Protocol: Convergence Loop (Full Roster Model — Opt-In, Gated) (summarized)

> **Summary inlined here. Full recipe at `AGENTS.md -> Protocol: Convergence Loop (Full Roster Model — Opt-In, Gated)`.**

**Summary:** Multi-round review pattern for plan, build, review, pr-check, coderabbit-review, deep-review, deep-doc-review. Round 1 is mandatory (the skill's primary dispatch). Rounds 2-5 are gated behind explicit `AskUser` prompts (entry gate before round 2, per-round gate before 3/4/5). Each gated round dispatches the SAME droid roster as round 1 in parallel via `Task` tool with zero prior context — agents read files fresh from disk. Convergence detection (zero new findings, strict `same file + ±5 lines + same category` matching) exits silently with status `CONVERGED` — never asks for another round. Hard limit at round 5. Exit statuses: `CONVERGED`, `USER_STOPPED`, `SKIPPED`, `HARD_LIMIT`, `DISPATCH_FAILED_ABORTED` (build has a single-slot carve-out). See full recipe in AGENTS.md.

### Protocol: Coverage Measurement (summarized)

> **Summary inlined here. Full recipe at `AGENTS.md -> Protocol: Coverage Measurement`.**

**Summary:** Measure unit + integration test coverage via Makefile targets with stack-specific fallbacks (Go: `go test -coverprofile`; Node: `npm test -- --coverage`; Python: `pytest --cov=. --cov-report=term`). Run wrapped in `_optimus_quiet_run` (Protocol: Quiet Command Execution) to keep agent context clean — the agent sees only PASS/FAIL + extracted total percentage; full per-file breakdown stays in `.optimus/logs/` and native coverage files. Thresholds: unit 85%, integration 70% (NEEDS_FIX/HIGH finding below). When scanning untested functions, read coverage output FILE (not stdout) — flag business-logic functions at 0% as HIGH; infrastructure/generated code as SKIP. If no coverage command resolves, mark SKIP — do not fail verification. See full extraction recipes in AGENTS.md.

### Protocol: Discover Review Droids

**Referenced by:** deep-review, pr-check

**Why:** Both review skills need a roster of installed review droids. Hardcoding the
list traps users on a fixed slate; rolling each skill's own discovery duplicates the
exclusion list and the description-based relevance filter. This protocol is the single
source of truth: callers invoke it, get back a categorized roster (or `MIN_NOT_MET`),
and render their own confirmation UX.

**Inputs:**

- `INCLUDE_NON_RING` (env var or caller flag, default `false`). When `false`, only
  `ring-*.md` agents are considered. When `true`, every `*.md` agent under
  `~/.factory/droids/` is considered, subject to the exclusion list and relevance
  filter below.

**Discovery glob:**

```bash
if [ "${INCLUDE_NON_RING:-false}" = "true" ]; then
  ls ~/.factory/droids/*.md 2>/dev/null
else
  ls ~/.factory/droids/ring-*.md 2>/dev/null
fi
```

For each candidate, read the `description` field from the YAML frontmatter — relevance
classification depends on it.

**Permanent exclusion list** (never dispatch for code review, regardless of
`INCLUDE_NON_RING`):

Droids whose purpose is implementation, design, operations, or non-code domains:

- `ring-default-codebase-explorer` — exploration, not review
- `ring-default-write-plan` — planning, not review
- `ring-default-review-slicer` — internal classification, not code review
- `ring-dev-team-devops-engineer` — DevOps implementation
- `ring-dev-team-frontend-designer` — UX design
- `ring-dev-team-helm-engineer` — Helm charts
- `ring-dev-team-sre` — observability validation
- `ring-dev-team-ui-engineer` — UI implementation
- `ring-dev-team-frontend-bff-engineer-*` — BFF implementation
- `ring-dev-team-prompt-quality-reviewer` — reviews AI prompts, not code
- All `ring-finance-*`, `ring-finops-*`, `ring-ops-*`, `ring-pm-*`, `ring-pmm-*`, `ring-pmo-*`, `ring-tw-*` — non-code domains

**Description-based relevance filter:**

| Classification | Selection rule | Examples |
|----------------|---------------|----------|
| **Core reviewer** | Description matches `code review|security|testing|safety|reviewer|audit` | `code-reviewer`, `business-logic-reviewer`, `security-reviewer`, `test-reviewer`, `nil-safety-reviewer`, `consequences-reviewer`, `dead-code-reviewer` |
| **QA analyst** | Description matches `test strategy|acceptance criteria` | `qa-analyst`, `qa-analyst-frontend` |
| **Stack specialist** | Description mentions a specific language/framework — include only if the project uses that stack | `backend-engineer-golang` (if `go.mod` exists), `backend-engineer-typescript` (if `package.json`), `frontend-engineer` (if frontend files in scope) |
| **Domain specialist** | Description mentions a specific technology — include only if the project uses it | `lib-commons-reviewer` (if `go.mod` imports `lib-commons`), `multi-tenant-reviewer` (if project uses multi-tenancy), `performance-reviewer` (always relevant) |
| **Non-reviewer (EXCLUDE)** | Description indicates implementation, design, ops, finance, planning, or infrastructure — NOT code review | See exclusion list above |

**Deny-list filter (applied AFTER inclusion regex, BEFORE final selection):**

If the description matches `architecture|design|planning|process|workflow|strategy`,
EXCLUDE the agent regardless of inclusion-regex match. These words indicate the
agent is meta-level (not code review) and should not be dispatched to review code.
This guards against future agents whose descriptions accidentally match the
inclusion regex's broader words (e.g., `architecture-reviewer`,
`design-reviewer`, `process-reviewer`) — they would otherwise be dispatched
against actual code, which is not their job.

The combined logic: `(matches inclusion regex) AND NOT (matches deny regex) → include`.

**Positive allow-list** (overrides deny-list for known good agents that may have
"design" or another deny term in their descriptions accidentally): listed in the
protocol's roster JSON (empty by default; add specific droid IDs as needed).
Allow-list entries are matched by full droid ID (not regex) so a single
accidental wording match cannot reopen the deny-list for an entire family of
droids.

For non-ring entries (only present when `INCLUDE_NON_RING=true`), apply the same
description filter AND the deny-list. Non-ring agents that pass both filters are
returned in the `Non-Ring` group regardless of stack/domain category — the caller
decides whether to default-select them in its UX.

**Output format:**

The protocol returns a grouped roster. Each entry carries `id`, `focus` (one-line
summary derived from the description), and `source` (`ring` or `non-ring`):

```
Ring Core
  - ring-default-code-reviewer — Code quality, SOLID, DRY, maintainability
  - ring-default-security-reviewer — Vulnerabilities, OWASP, input validation
  - ...

Ring Stack
  - ring-dev-team-backend-engineer-golang — Go idiomaticity (project has go.mod)

Ring Domain
  - ring-dev-team-performance-reviewer — Performance hotspots
  - ring-dev-team-lib-commons-reviewer — lib-commons usage (project imports it)

Non-Ring                       (only when INCLUDE_NON_RING=true)
  - my-custom-reviewer — User-installed reviewer
```

The caller renders this for user confirmation per its own UX (e.g., AskUser table
with default-selected ring entries and default-deselected non-ring entries).

**Minimum-roster contract:**

The protocol MUST yield at least both:

- `ring-default-code-reviewer` AND
- `ring-default-security-reviewer`

If either is missing from the discovered roster, the protocol returns `MIN_NOT_MET`
instead of a roster. The caller is responsible for STOP semantics — typically a
message instructing the user to install the missing droids and re-run.

Skills reference this as: "Execute Protocol: Discover Review Droids — see AGENTS.md Protocol: Discover Review Droids."


### Protocol: Initialize .optimus Directory (summarized)

> **Summary inlined here. Full recipe at `AGENTS.md -> Protocol: Initialize .optimus Directory`.**

**Summary:** Create `${MAIN_WORKTREE}/.optimus/{sessions,reports,logs}/` with `mkdir -p`. Add `# optimus-operational-files` and `# optimus-operational-worktrees` markers to `${MAIN_WORKTREE}/.gitignore` idempotently (grep-anchor before append). Refuse symlinked `.gitignore`. Auto-prune `.optimus/logs/` (30 days, 500 files). See full recipe in AGENTS.md.

### Protocol: Per-Droid Quality Checklists (summarized)

> **Summary inlined here. Full recipe at `AGENTS.md -> Protocol: Per-Droid Quality Checklists`.**

**Summary:** Per-droid quality dimensions that review/pr-check/deep-review/coderabbit-review/plan/build skills MUST include in their agent prompts beyond the core review domain. Examples: code-reviewer adds resilience/concurrency/cognitive-complexity/error-handling checks; security-reviewer adds PII/error-response-leakage/rate-limiting/secrets; test-reviewer adds effectiveness/false-positive-risk/spec-traceability; nil-safety adds channel/map/slice safety; consequences adds backward-compat/migration-path/event-contract; dead-code adds zombie test infrastructure and stale feature flags; qa-analyst adds testability/operational-readiness; frontend adds UX states/accessibility/i18n; backend adds graceful-shutdown/context-propagation/structured-logging. Skills reference this when building specialist droid prompts so agents review uniformly. See full per-droid lists in AGENTS.md.

### Protocol: Project Rules Discovery

**Referenced by:** stages 1-4, deep-review, coderabbit-review

Every skill that reviews, validates, or generates code MUST search for project rules
and AI instruction files before starting. Search for these files in order and read ALL
that exist:

```
AGENTS.md                    # Primary agent instructions
CLAUDE.md                    # Claude-specific rules
DROIDS.md                    # Droid-specific rules
.cursorrules                 # Cursor-specific rules
PROJECT_RULES.md             # Coding standards (root or docs/)
docs/PROJECT_RULES.md
.editorconfig                # Editor formatting rules
docs/coding-standards.md     # Explicit coding conventions
docs/conventions.md
.github/CONTRIBUTING.md      # Contribution guidelines
CONTRIBUTING.md
.eslintrc*                   # Linter configs (implicit rules)
biome.json
.golangci.yml
.prettierrc*
```

If NONE exist, warn the user. If any are found, they become the source of truth
for coding standards and must be passed to every dispatched sub-agent.

Skills reference this as: "Discover project rules — see AGENTS.md Protocol: Project Rules Discovery."


### Protocol: Quiet Command Execution (summarized)

> **Summary inlined here. Full recipe at `AGENTS.md -> Protocol: Quiet Command Execution`.**

**Summary:** `_optimus_quiet_run <label> <command>` redirects stdout+stderr to `${MAIN_WORKTREE}/.optimus/logs/<ts>-<label>-<pid>.log`, emits a single `PASS`/`FAIL` line, and on failure dumps the last 50 lines (with `cat -v` to neutralize ANSI/OSC escape sequences). Uses `umask 0077` on the log file (output may contain credentials/stack traces). Exit code preserved so `if _optimus_quiet_run ...; then ... fi` works. Reserved exit codes: `2` = missing label/command; `3` = cannot create logs dir. Log retention (30-day age cap + 500-file count cap) is pruned at every Initialize Directory + Session State call. Use for verification commands only; never for output the agent must parse turn-by-turn. See full recipe in AGENTS.md.

<!-- INLINE-PROTOCOLS:END -->
