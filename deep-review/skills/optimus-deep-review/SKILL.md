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

### Protocol: Resolve Main Worktree Path

**Referenced by:** all skills that read or write `.optimus/` operational files (state.json, stats.json, sessions, reports, logs, and checkpoint markers).

**Why:** `.optimus/` is gitignored. Git does NOT propagate ignored files across linked worktrees (`git worktree add` creates a sibling working tree but does not share gitignored files). When a skill runs from a linked worktree (the common case for `/optimus-build`, `/optimus-review`, `/optimus-done` which default to the task's worktree), reads and writes against `.optimus/state.json` resolve to the worktree's isolated copy. Updates never reach the main worktree. When the linked worktree is later removed (e.g., by `/optimus-done` cleanup), the writes are lost — silent data loss.

**Recipe:**

```bash
MAIN_WORKTREE="$(git worktree list --porcelain 2>/dev/null | awk '/^worktree / {print $2; exit}')"
if [ -z "$MAIN_WORKTREE" ]; then
  echo "ERROR: Cannot determine main worktree — not in a git repository." >&2
  exit 1
fi
```

The first `worktree` line in `git worktree list --porcelain` is always the main worktree (where the bare `.git/` directory or the repo's HEAD lives), regardless of where the command is run from.

**Path resolution pattern:**

After resolving `MAIN_WORKTREE`, every `.optimus/` path MUST be prefixed:

```bash
# RIGHT (works from any worktree):
STATE_FILE="${MAIN_WORKTREE}/.optimus/state.json"
SESSION_FILE="${MAIN_WORKTREE}/.optimus/sessions/session-${TASK_ID}.json"
STATS_FILE="${MAIN_WORKTREE}/.optimus/stats.json"
mkdir -p "${MAIN_WORKTREE}/.optimus/sessions" \
         "${MAIN_WORKTREE}/.optimus/reports" \
         "${MAIN_WORKTREE}/.optimus/logs"

# WRONG (resolves against PWD, breaks in linked worktrees):
STATE_FILE=".optimus/state.json"
SESSION_FILE=".optimus/sessions/session-${TASK_ID}.json"
STATS_FILE=".optimus/stats.json"
mkdir -p .optimus/sessions .optimus/reports .optimus/logs
```

**What does NOT need this protocol:**

- `<tasksDir>/optimus-tasks.md` and `<tasksDir>/tasks/`, `<tasksDir>/subtasks/` — versioned content, propagated by git across worktrees automatically.
- `.optimus/config.json` — when **versioned** (legacy projects), it propagates via git; when **gitignored** (current default), it suffers the same isolation as state.json. **Treat `.optimus/config.json` as gitignored and resolve via `$MAIN_WORKTREE` for safety in current projects** — the cost is a single `git worktree list` call.
- `.gitignore` itself — versioned, propagated via git.

**Idempotency:** the resolution is read-only against git metadata; safe to call multiple times in the same skill execution. Cache `MAIN_WORKTREE` in a local variable rather than re-running `git worktree list` for each path.

Skills reference this as: "Resolve main worktree — see AGENTS.md Protocol: Resolve Main Worktree Path."


### Finding Presentation (Unified Model)
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

   **AskUser template (MANDATORY — follow this exact structure for every finding):**
   ```
   1. [question] (X/N) SEVERITY — Finding title summary
   [topic] (X/N) F#-Category
   [option] Option A: recommended fix
   [option] Option B: alternative approach
   [option] Skip
   [option] Tell me more
   ```

9. **HARD BLOCK — IMMEDIATE RESPONSE RULE — If the user selects "Tell me more" OR responds
   with free text (a question, disagreement, or request for clarification):**
   **STOP IMMEDIATELY.** Do NOT continue to the next finding. Do NOT batch the response.
   Research the user's concern RIGHT NOW using `WebSearch`, codebase analysis, or both.
   Provide a thorough answer with evidence (links, code references, best practice citations).
   Only AFTER the user is satisfied, re-present the SAME finding's options and ask for
   their decision again. This may go back and forth multiple times — that is expected.
   **NEVER defer the response to the end of the findings loop.**

   **Anti-rationalization (excuses the agent MUST NOT use to skip immediate response):**
   - "I'll address all questions after presenting the remaining findings" — NO
   - "Let me continue with the next finding and come back to this" — NO
   - "I'll research this after the findings loop" — NO
   - "This is noted, moving to the next finding" — NO
10. After ALL N decisions collected: apply ALL approved fixes (see below)
11. Run verification (see Verification Timing below)
12. Present final summary


### Protocol: Convergence Loop (Full Roster Model — Opt-In, Gated)
Applies to: plan, review, pr-check, coderabbit-review, deep-review, deep-doc-review, build

Round 1 (the skill's primary agent dispatch) is MANDATORY and uses the per-skill
default ring roster. Convergence rounds 2+ are OPTIONAL and gated behind explicit
user prompts. Convergence detection (zero new findings) exits the loop silently
without offering further rounds.

- **Round 1:** Orchestrator dispatches the per-skill default roster of specialist
  ring droids in parallel (with full session context). This round is NOT counted
  as a "convergence round" — it is the skill's primary review pass.
- **Rounds 2-5 (each gated by user prompt):** The **same agent roster** as round 1
  is dispatched in parallel via `Task` tool, each with zero prior context. Each
  agent reads all files fresh from disk.
- **Sub-agents do NOT receive the findings ledger.** Dedup is performed entirely
  by the orchestrator after agents return, using **strict matching**: same file +
  same line range (±5 lines) + same category. "Description similarity" is NOT
  sufficient for dedup — the file, location, and category must all match.
- LOW severity findings are NOT a reason to skip presentation — ALL findings are
  presented to the user.

**Entry gate (before round 2 — MANDATORY):** After round 1 completes (decisions
collected, fixes applied), ask via `AskUser`:
```
1. [question] Round 1 produced N findings (X fixed, Y skipped). Run convergence
   round 2 (re-dispatches the same roster with clean context)?
[topic] Convergence-Entry
[option] Run round 2
[option] Skip convergence loop
```
- "Skip convergence loop" → exit with status `SKIPPED`.
- "Run round 2" → dispatch round 2.

**Per-round gate (before rounds 3, 4, 5 — MANDATORY):** After each round 2+
completes (findings presented, fixes applied), before dispatching the next round:
```
1. [question] Round N-1 produced M new findings. Run round N?
[topic] Convergence-RoundN
[option] Continue (run round N)
[option] Stop here
```
- "Stop here" → exit with status `USER_STOPPED`.
- "Continue" → dispatch round N.

**Convergence detection (after each dispatched round — DO NOT ASK):** If a
dispatched round returns ZERO new findings (using the strict matching rules
above), the orchestrator MUST:
1. Print: `Convergence reached at round N: zero new findings.`
2. Exit immediately with status `CONVERGED`.
3. NEVER offer to run another round — the user is informed, not asked.

**Hard limit:** Round 5 is the maximum. After round 5 completes (with new
findings present), exit with status `HARD_LIMIT` without asking.

**Dispatch failure (default):** If a `Task` dispatch fails entirely (transport error,
ring droid unavailable, etc.), do NOT count as zero findings (would falsely
mark `CONVERGED`). Ask via `AskUser`:
```
1. [question] Round N dispatch failed: <error>. Retry, or stop here?
[topic] Convergence-DispatchFail
[option] Retry round N
[option] Stop here
```
- "Retry round N" → re-dispatch.
- "Stop here" → exit with status `DISPATCH_FAILED_ABORTED`.

**Dispatch failure (build-specific carve-out):** `build` runs the convergence loop
deep inside Phase 2.3 of a potentially hours-long multi-subtask implementation. A
blocking prompt at this point is disruptive. `build` therefore MAY treat a single
failed slot as "zero new findings for that slot" and continue silently with a
printed warning. The user is informed via the Final Summary. If multiple slots
fail in the same round, `build` falls back to the default behavior (ask immediately).
This carve-out applies ONLY to `build`; all other skills use the default.

**Exit statuses (recorded for the Final Summary):**

| Status | Trigger |
|--------|---------|
| `CONVERGED` | A dispatched round returned zero new findings |
| `USER_STOPPED` | User chose "Stop here" at a per-round gate (before rounds 3, 4, or 5) |
| `SKIPPED` | User chose "Skip convergence loop" at the entry gate |
| `HARD_LIMIT` | Round 5 completed with new findings still present |
| `DISPATCH_FAILED_ABORTED` | Dispatch failure followed by user choosing to stop |

**Why full roster, not a single agent:** A single generalist agent structurally cannot
replicate the coverage of 8-10 domain specialists. The security-reviewer catches injection
risks a code-reviewer won't. The nil-safety-reviewer catches empty guards a QA analyst won't.
Dispatching a single agent in rounds 2+ creates false convergence — the agent declares
"zero new findings" because it lacks the domain depth, not because the code is clean.


### Protocol: Coverage Measurement

**Referenced by:** review, pr-check, coderabbit-review, deep-review, build

Measure test coverage using Makefile targets with stack-specific fallbacks.

**Run coverage quietly.** Coverage commands are the single biggest source of
verbose output (N packages × per-file coverage lines). Wrap them with
`_optimus_quiet_run` (see Protocol: Quiet Command Execution) so the full output
lands on disk and only a PASS/FAIL line reaches the agent. Then read only the
"total" summary line to extract the percentage.

**Unit coverage command resolution order:**
1. `make test-coverage` (if Makefile target exists), run via `_optimus_quiet_run`
2. Stack-specific fallback:
   - Go: `go test -coverprofile=coverage-unit.out ./...` (wrapped) then `go tool cover -func=coverage-unit.out`
   - Node: `npm test -- --coverage` (wrapped)
   - Python: `pytest --cov=. --cov-report=term` (wrapped)

If no unit coverage command is available, mark as **SKIP** — do not fail the verification.

**Integration coverage command resolution order:**
1. `make test-integration-coverage` (if Makefile target exists), run via `_optimus_quiet_run`
2. Stack-specific fallback:
   - Go: `go test -tags=integration -coverprofile=coverage-integration.out ./...` (wrapped) then `go tool cover -func=coverage-integration.out`
   - Node: `npm run test:integration -- --coverage` (wrapped)
   - Python: `pytest -m integration --cov=. --cov-report=term` (wrapped)

If no integration coverage command is available, mark as **SKIP** — do not fail the verification.

**Extracting the percentage (agent-visible output):** after the wrapped run, emit
only the total line. Examples:

```bash
# Go
_optimus_quiet_run "make-test-coverage" make test-coverage
if [ -f coverage-unit.out ]; then
  go tool cover -func=coverage-unit.out | awk '/^total:/ {print "Unit coverage: " $NF}'
fi

# Node (Istanbul JSON/text-summary)
_optimus_quiet_run "npm-test-coverage" npm test -- --coverage
if [ -f coverage/coverage-summary.json ]; then
  jq -r '.total.lines.pct | "Unit coverage: \(.)%"' coverage/coverage-summary.json
fi

# Python (pytest-cov)
_optimus_quiet_run "pytest-cov" pytest --cov=. --cov-report=term --cov-report=json:coverage.json
if [ -f coverage.json ]; then
  jq -r '.totals.percent_covered_display | "Unit coverage: \(.)%"' coverage.json
fi
```

The agent sees ~2 lines total (PASS verdict + "Unit coverage: 87.4%"). The full
per-file breakdown stays in `.optimus/logs/` and in the native coverage files.

**Thresholds:**

| Test Type | Threshold | Verdict if Below |
|-----------|-----------|-----------------|
| Unit tests | 85% | NEEDS_FIX / HIGH finding |
| Integration tests | 70% | NEEDS_FIX / HIGH finding |

**Coverage gap analysis:** When scanning for untested functions/methods (0% coverage),
read the coverage output file (not the agent turn stdout) — either the native
`coverage-*.out` / `coverage-summary.json` / `coverage.json` file, or the
`.optimus/logs/<timestamp>-*-coverage-*.log` file produced by `_optimus_quiet_run`
(the trailing `-<pid>` segment is part of every helper-produced log filename).
Flag business-logic functions with 0% as HIGH, infrastructure/generated code with
0% as SKIP.

Skills reference this as: "Measure coverage — see AGENTS.md Protocol: Coverage Measurement."


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

For non-ring entries (only present when `INCLUDE_NON_RING=true`), apply the same
description filter. Non-ring agents that pass the filter are returned in the `Non-Ring`
group regardless of stack/domain category — the caller decides whether to default-select
them in its UX.

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


### Protocol: Initialize .optimus Directory

**Referenced by:** import, tasks, report (export), quick-report, batch, pr-check, deep-review, coderabbit-review, all stage agents (1-4) for session files

Before creating ANY file inside `.optimus/`, ensure the directory structure exists
and that the entire `.optimus/` tree is gitignored (it is 100% operational/per-user).

```bash
# Requires Protocol: Resolve Main Worktree Path to have run first
# (or resolve inline; see that protocol).
MAIN_WORKTREE="$(git worktree list --porcelain 2>/dev/null | awk '/^worktree / {print $2; exit}')"
mkdir -p "${MAIN_WORKTREE}/.optimus/sessions" "${MAIN_WORKTREE}/.optimus/reports" "${MAIN_WORKTREE}/.optimus/logs"
if ! grep -q '^# optimus-operational-files' .gitignore 2>/dev/null; then
  printf '\n# optimus-operational-files\n.optimus/config.json\n.optimus/state.json\n.optimus/stats.json\n.optimus/sessions/\n.optimus/reports/\n.optimus/logs/\n' >> .gitignore
fi
# Linked worktrees managed by Optimus live at ${MAIN_WORKTREE}/.worktrees/
# (see Worktree Location Convention). Add the gitignore entry idempotently
# on a separate marker so existing projects whose `.gitignore` already
# carries the operational-files block still get the worktree exclusion.
# Refuse symlinked .gitignore (defense against link-following file-write).
if [ -L .gitignore ]; then
  echo "ERROR: .gitignore is a symlink — refusing to append (potential symlink attack)." >&2
  exit 1
fi
if ! grep -q '^# optimus-operational-worktrees' .gitignore 2>/dev/null; then
  printf '\n# optimus-operational-worktrees\n.worktrees/\n' >> .gitignore
fi
# Log retention (idempotent — fires once per init): age-based + count-cap prune.
# Also duplicated in Protocol: Session State so stage agents (which call Session
# State but not Initialize Directory) get pruning at every phase transition.
# Both prune sites are no-ops on clean directories; running both is harmless.
find "${MAIN_WORKTREE}/.optimus/logs" -type f -name '*.log' -mtime +30 -delete 2>/dev/null
if [ -d "${MAIN_WORKTREE}/.optimus/logs" ]; then
  ls -1t "${MAIN_WORKTREE}/.optimus/logs"/*.log 2>/dev/null | tail -n +501 \
    | while IFS= read -r _log_to_rm; do rm -f -- "$_log_to_rm"; done
fi
```

**Log retention** for `.optimus/logs/` runs at TWO sites for full coverage:
- **Protocol: Initialize .optimus Directory** (this protocol) — fires when
  admin/standalone skills (`import`, `tasks`, `report`, `quick-report`, `batch`,
  `pr-check`, `deep-review`, `coderabbit-review`) initialize `.optimus/`.
- **Protocol: Session State** — fires at every stage agent (`plan`, `build`,
  `review`, `done`) phase transition.

Both sites are idempotent (no-op on clean directories) and use the same prune
logic (30-day age cap + 500-file count cap). Running both per session is a
harmless cheap operation.

Everything inside `.optimus/` is gitignored. The planning tree is versioned
separately at `<tasksDir>/optimus-tasks.md` (and `<tasksDir>/tasks/`, `<tasksDir>/subtasks/`
for Ring specs) — see the File Location section above.

Skills reference this as: "Initialize .optimus directory — see AGENTS.md Protocol: Initialize .optimus Directory."


### Protocol: Per-Droid Quality Checklists

**Referenced by:** review, pr-check, deep-review, coderabbit-review, plan, build

Each droid type has specific dimensions it MUST verify beyond its core domain. Skills
that dispatch review droids MUST include the applicable checklists in agent prompts.

**Code Quality agent** (`ring-default-code-reviewer`) must additionally verify:
- Resilience: external calls have timeout, retry with backoff, circuit breaker where appropriate
- Resource lifecycle: all opened connections/handles are closed (defer, cleanup, graceful shutdown)
- Concurrency: shared state has proper synchronization, no goroutine leaks, no deadlock risk
- Performance: no N+1 queries, no unbounded queries, indexes exist for query patterns, no hot-path allocations
- Configuration: no hardcoded values that should be environment-configurable, safe defaults
- Cognitive complexity: functions with >3 nesting levels or >30 lines flagged for decomposition
- Error handling: errors wrapped with context, consistent with codebase error patterns
- Domain purity: no infrastructure concerns in domain layer, dependency direction correct
- Resource leaks: DB connections, HTTP clients, file handles, channels properly closed

**Business Logic agent** (`ring-default-business-logic-reviewer`) must additionally verify:
- Spec traceability: each code path maps to a spec requirement (flag orphan logic with no spec backing)
- Data integrity: transaction boundaries correct, partial writes impossible, rollback defined
- Backward compatibility: existing consumers/contracts not broken by this change
- API semantics: correct HTTP status codes, idempotent operations marked as such, pagination consistent
- Domain edge cases: what happens with zero, negative, maximum, duplicate, concurrent values?
- Business rule completeness: all business rules from spec have implementation AND test

**Security agent** (`ring-default-security-reviewer`) must additionally verify:
- Data privacy: PII not logged, sensitive fields masked in responses, LGPD/GDPR compliance
- Error responses: no internal details leaked (stack traces, DB schemas, internal paths, SQL)
- Rate limiting: high-throughput or public endpoints have rate limiting consideration
- Input validation: happens at the right layer (not just client-side), consistent with codebase
- Secrets: no hardcoded credentials, tokens, API keys in code or config files
- Auth propagation: authentication context properly propagated through the call chain

**Test Quality agent** (`ring-default-ring-test-reviewer`) must additionally verify:
- Test effectiveness: do tests verify BEHAVIOR or just mock internals? Flag tests where assertions only check mock.Called() without verifying output/state
- False positive risk: could these tests pass while the feature is actually broken?
- Test coupling: are tests coupled to implementation details (private fields, internal struct layout)?
- Spec traceability: for each acceptance criterion in the task spec, is there a test?
- Integration tests: do they use real dependencies (testcontainers/docker) or just mocks?
- Test isolation: can tests run in parallel without interference? Shared state between tests?
- Error scenario completeness: each error return path has a corresponding test?
- Boundary values: min, max, zero, empty, nil, negative tested where applicable?

**Nil/Null Safety agent** (`ring-default-ring-nil-safety-reviewer`) must additionally verify:
- Resource cleanup: nil checks before Close/Release calls
- Channel safety: sends to nil/closed channels
- Map safety: reads/writes to nil maps
- Slice safety: index bounds after filtering/transforming

**Ripple Effects agent** (`ring-default-ring-consequences-reviewer`) must additionally verify:
- Values duplicated between files that should be a shared constant
- Imports follow the project's layer architecture (no circular deps, no backwards imports)
- New code follows the same patterns as existing code in the same domain
- Backward compatibility: does this change break any existing consumer or API contract?
- Configuration drift: new defaults reasonable? existing config overrides still valid?
- Migration path: if breaking change, is migration strategy documented?
- Shared state: new global/package-level state that could cause issues across modules?
- Event/message contracts: changes to event payloads affect downstream consumers?

**Dead Code agent** (`ring-default-ring-dead-code-reviewer`) must additionally verify:
- Dead code: unused imports, unreachable branches, commented-out code
- Zombie test infrastructure: test helpers, fixtures, mocks no longer used by any test
- Feature flags: stale feature flag checks for flags that were already fully rolled out
- Deprecated paths: code paths behind deprecated API versions with no remaining consumers

**Spec Compliance / QA agent** (`ring-dev-team-qa-analyst`) must additionally verify:
- Testability assessment: is the code structured for testability? (dependency injection, interfaces)
- Operational readiness: can ops monitor, debug, and rollback this in production?
- Acceptance criteria coverage: each AC has both success AND failure test scenarios
- Cross-cutting scenarios: concurrent modifications, large datasets, special characters, timezone handling

**Frontend specialist** (`ring-dev-team-frontend-engineer`) must additionally verify:
- UX completeness: loading states, empty states, error states all handled
- Accessibility: keyboard navigation, screen reader support, ARIA labels, color contrast
- Responsive behavior: works across viewport sizes (mobile, tablet, desktop)
- i18n readiness: no hardcoded user-facing strings, date/number formatting locale-aware
- Performance: no unnecessary re-renders, large lists virtualized, images optimized

**Backend specialist** (`ring-dev-team-backend-engineer-golang` or TS equivalent) must additionally verify:
- Language idiomaticity: follows official style guide conventions
- Graceful shutdown: SIGTERM handling, in-flight request draining
- Connection pool sizing: appropriate for expected load
- Context propagation: request context passed through the full call chain
- Structured logging: logs include correlation IDs, operation names, durations

Skills reference this as: "Include per-droid quality checklists — see AGENTS.md Protocol: Per-Droid Quality Checklists."


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


### Protocol: Quiet Command Execution

**Referenced by:** build, review, pr-check, coderabbit-review, deep-review (for `make test`, `make lint`, `make test-integration`, coverage runs)

Long-running verification commands (`make test`, `make lint`, `make test-coverage`,
`make test-integration`, `make test-integration-coverage`) often emit thousands of
output lines. Capturing that output in the agent's context wastes tokens and slows
down every turn, even when the command passes cleanly.

This protocol defines `_optimus_quiet_run`, a bash helper that runs a command with
stdout/stderr redirected to a log file under `.optimus/logs/` and emits **a single
verdict line** based on the exit code. On failure it also prints the last 50 lines of
the log so the agent can diagnose without ingesting the full output. The exit code
is preserved, so downstream control flow (`if ...; then ... fi`) keeps working.

**Helper (auto-inlined — do NOT manually copy):**

This helper is automatically inlined into every consumer skill by
`scripts/inline-protocols.py` (see Shared Protocols block at the end of each
SKILL.md). You do NOT need to paste it into skills manually — editing this single
source of truth is enough.

```bash
_optimus_quiet_run() {
  # Usage: _optimus_quiet_run <label> <command> [args...]
  # Runs <command> with stdout+stderr redirected to
  # .optimus/logs/<timestamp>-<label>-<pid>.log. Prints a single PASS/FAIL line;
  # on FAIL also prints last 50 lines of the log (terminal escapes stripped).
  # Returns the command's exit code unchanged.
  local label="$1"; shift
  if [ -z "$label" ] || [ $# -eq 0 ]; then
    echo "ERROR: _optimus_quiet_run requires <label> and <command>" >&2
    return 2
  fi
  local safe
  safe=$(printf '%s' "$label" | tr -c '[:alnum:]-_' '-' | sed 's/--*/-/g;s/^-//;s/-$//')
  [ -z "$safe" ] && safe="run"
  local ts
  ts=$(date +%Y%m%d-%H%M%S)
  # PID suffix prevents same-second same-label collisions (parallel or fast sequential).
  local log=".optimus/logs/${ts}-${safe}-$$.log"
  if ! mkdir -p "$(dirname "$log")" 2>/dev/null; then
    echo "ERROR: _optimus_quiet_run cannot create $(dirname "$log") (permission denied, disk full, or read-only FS)" >&2
    return 3
  fi
  # umask 0077 ensures log file is owner-read/write only (logs may contain
  # sensitive test output: credentials in debug lines, internal stack traces).
  if ( umask 0077; "$@" > "$log" 2>&1 ); then
    echo "PASS: $label (log: $log)"
    return 0
  else
    local rc=$?
    echo "FAIL: $label (exit=$rc, log: $log)"
    echo "--- last 50 lines ---"
    # `cat -v` strips terminal escape sequences (non-printable bytes become ^X
    # notation), preventing a malicious test from hijacking the terminal title
    # or obscuring errors via ANSI/OSC sequences.
    tail -n 50 "$log" | cat -v
    return $rc
  fi
}
```

**Usage examples:**

```bash
_optimus_quiet_run "make-lint" make lint
_optimus_quiet_run "make-test" make test
_optimus_quiet_run "make-test-coverage" make test-coverage
_optimus_quiet_run "make-test-integration" make test-integration
```

**Contract:**

1. **Success path (exit 0):** one line `PASS: <label> (log: <path>)` — this is ALL the
   output the agent reads. The full log stays on disk for manual inspection.
2. **Failure path (exit != 0):** `FAIL: <label> (exit=N, log: <path>)` + a separator
   line + the last 50 lines of the log (with terminal escape sequences stripped via
   `cat -v`). The agent has enough context to diagnose or dispatch a fix droid
   without loading the full output.
3. **Exit code preserved:** the helper returns the same exit code as the wrapped
   command. Downstream `if _optimus_quiet_run ...; then ... fi` works the same as
   `if make test; then ... fi` would.
4. **Log retention:** logs accumulate under `.optimus/logs/` (gitignored). Both
   Protocol: Initialize .optimus Directory (admin/standalone skills) and
   Protocol: Session State (stage agents at phase transitions) automatically
   prune logs older than 30 days AND cap the directory at 500 most-recent
   files, whichever limit hits first. Users may `rm .optimus/logs/*.log` at any
   time to reclaim space manually.
5. **Reserved exit codes:** `2` = missing/empty label or missing command;
   `3` = cannot create `.optimus/logs/` (perm denied, disk full, read-only FS).
   Any other exit code comes from the wrapped command.

**Label naming convention:**
- `make-<target>` for Makefile targets: `make-lint`, `make-test`, `make-test-coverage`, `make-test-integration`, `make-test-integration-coverage`
- `<tool>` for direct tool invocations: `go-vet`, `goimports`, `gofmt`, `prettier`
- `<tool>-<action>` when a single tool has multiple modes: `npm-test-coverage`, `pytest-cov`

Keep labels short (≤30 chars) and filesystem-safe — the helper sanitizes aggressively,
but readable labels produce readable log filenames in `.optimus/logs/`.

**When the agent needs full output:** use `cat "${MAIN_WORKTREE}/.optimus/logs/<filename>.log"` or
point a sub-agent to the log path (`Read` tool). Never re-run the command just to
see the output — the log already has it.

**Output parsing (e.g., coverage %):** do NOT parse the stdout of
`_optimus_quiet_run`. Read the log file or, better, use a separate command that
prints only the metric (example in Protocol: Coverage Measurement).

**When NOT to use this helper:**
- Commands whose output must be parsed by the agent turn-by-turn (rare for
  verification, common for `git log`, `gh pr view`, etc.) — use normal Execute.
- Interactive commands that expect TTY input.
- Commands under 20 lines of output where the savings are negligible.

Skills reference this as: "Run quietly — see AGENTS.md Protocol: Quiet Command Execution."


<!-- INLINE-PROTOCOLS:END -->
