---
name: optimus-pr-review
description: >
  PR-aware code review orchestrator. Receives a pull request URL, fetches
  PR metadata (description, branch, changed files, linked issues), collects
  existing review comments (CodeRabbit, human reviewers, CI), dispatches
  parallel agents to evaluate both code and comments, and presents findings
  interactively with source attribution. Creates separate commits per finding and references them in PR replies.
trigger: >
  - When user provides a PR URL for review (e.g., "review this PR: https://github.com/org/repo/pull/123")
  - When user asks to review a pull request
skip_when: >
  - No PR URL provided and user wants a generic code review (use optimus-deep-review directly)
  - PR is already merged (nothing to review)
  - User wants to run automated checks only (use optimus-verify-code instead)
prerequisite: >
  - PR URL is provided or can be inferred (current branch has an open PR)
  - gh CLI is installed and authenticated
NOT_skip_when: >
  - "The PR is small" → Small PRs still benefit from structured review with PR context.
  - "I already looked at the diff" → Specialist agents catch issues human review misses.
  - "CI passed" → CI checks automated rules; agents review logic, security, and quality.
  - "CodeRabbit already reviewed" → Agents validate/contest CodeRabbit findings and catch what it misses.
examples:
  - name: Review a PR by URL
    invocation: "Review this PR: https://github.com/org/repo/pull/42"
    expected_flow: >
      1. Fetch PR metadata and existing comments
      2. Checkout PR branch
      3. Present PR summary (including comment sources)
      4. Dispatch all agents to review code AND evaluate existing comments
      5. Consolidate with source attribution
      6. Interactive finding-by-finding resolution
      7. Apply fixes with separate commits per finding
      8. PR readiness verdict
  - name: Review current branch PR
    invocation: "Review the PR for this branch"
    expected_flow: >
      1. Detect current branch, find associated open PR via gh CLI
      2. Fetch PR metadata and comments
      3. Standard flow
related:
  complementary:
    - optimus-deep-review
    - optimus-verify-code
  differentiation:
    - name: optimus-deep-review
      difference: >
        optimus-deep-review is a generic code review that works with any scope
        (all files, git diff, directory). optimus-pr-review adds PR context
        (description, linked issues, existing comments) and evaluates feedback
        from multiple sources (CodeRabbit, human reviewers, agents).
    - name: optimus-coderabbit-review
      difference: >
        optimus-coderabbit-review runs CodeRabbit CLI locally as the source of
        findings with a TDD fix cycle. optimus-pr-review collects comments
        already posted on the PR (including CodeRabbit's) and has agents
        validate/contest them.
  sequence:
    before:
      - optimus-verify-code
verification:
  automated:
    - command: "which gh 2>/dev/null && echo 'available'"
      description: gh CLI is installed
      success_pattern: available
  manual:
    - PR metadata and comments fetched correctly
    - Source attribution present in all findings
    - All findings presented interactively
    - Approved fixes applied with separate commits per finding
    - PR readiness verdict presented
    - PR comment threads replied with resolution status
---

# PR Review

PR-aware code review orchestrator. Fetches PR metadata, collects existing review comments, dispatches agents to evaluate both code and comments, and presents findings with source attribution.

---

## Phase 0: Fetch PR Context

### Step 0.1: Obtain PR URL

If the user provided a PR URL, use it directly.

If no URL was provided, attempt to find the PR for the current branch:

```bash
gh pr view --json url,number,title --jq '.url' 2>/dev/null
```

If no PR is found, ask the user for the URL using `AskUser`.

### Step 0.2: Fetch PR Metadata

Use `gh pr view` to extract all relevant metadata:

```bash
gh pr view <PR_NUMBER_OR_URL> --json title,body,state,headRefName,baseRefName,changedFiles,additions,deletions,labels,milestone,assignees,reviewRequests,comments,url,number
```

Alternatively, if using a GitHub URL, use `FetchUrl` to get the PR page content.

**Guard: Check PR state.** If the PR state is `MERGED` or `CLOSED`, inform the user and stop. Only open PRs should be reviewed.

If the command fails (invalid URL, PR not found, or permission denied), inform the user of the error and ask for a corrected URL using `AskUser`.

Extract and store:
- **Title and description** — the PR's purpose and context
- **Head branch and base branch** — for accurate diff
- **Changed files count** — scope indicator
- **Labels and milestone** — categorization context
- **Linked issues** — from PR description (look for "Fixes #", "Closes #", "Resolves #" patterns)

### Step 0.3: Collect Existing PR Comments

Collect ALL comments from ALL sources on the PR:

**General PR comments:**
```bash
gh pr view <PR_NUMBER_OR_URL> --comments
```

**Review comments (inline code comments and review summaries):**
```bash
gh api repos/{owner}/{repo}/pulls/{number}/reviews
gh api repos/{owner}/{repo}/pulls/{number}/comments
```

For each comment, extract and categorize:
- **Source:** Identify the author — CodeRabbit (bot), human reviewer (by username), CI/CD bot, or other automated tool
- **Type:** General comment, inline code comment, review summary, or approval/request-changes
- **File and line** (for inline comments) — map to the changed files
- **Content** — the actual feedback
- **Status:** Resolved/unresolved (if the platform tracks it)

**Duplicated comments sections:**
Some review tools (e.g., CodeRabbit) group repeated or similar comments under sections titled "Duplicated Comments", "Duplicate Comments", or similar headings within their review summaries. These sections contain valid feedback that was flagged on multiple files or locations. You MUST:
1. Parse these sections and extract each individual comment
2. Treat them as regular review comments — do NOT skip them because they are labeled as "duplicated"
3. Map each duplicated comment to the affected files/lines listed in the section

Group comments by source:
```
PR Comments:
  - CodeRabbit: X comments (Y inline, Z summary, W from duplicated sections)
  - Human reviewers: X comments from [usernames]
  - CI/CD: X comments
  - Unresolved threads: X
```

### Step 0.4: Checkout PR Branch

Ensure the working tree matches the PR state:

```bash
gh pr checkout <PR_NUMBER_OR_URL>
```

If already on the correct branch, skip this step. If checkout fails due to uncommitted changes, inform the user and ask them to stash or commit their changes first.

### Step 0.5: Fetch Changed Files

Get the list of files changed in the PR:

```bash
gh pr diff <PR_NUMBER_OR_URL> --name-only
```

Read the full content of each changed file for the review agents.

---

## Phase 1: Present PR Summary

Present a summary of the PR to the user before starting the review:

```markdown
## PR Review: #<number> — <title>

**Branch:** <head> → <base>
**Changed files:** X files (+Y additions, -Z deletions)
**Labels:** [label1, label2]
**Linked issues:** #issue1, #issue2

### PR Description
<PR body/description>

### Existing Review Comments
- **CodeRabbit:** X comments (Y unresolved)
- **Human reviewers:** X comments from [usernames] (Y unresolved)
- **CI/CD:** X comments

### Changed Files
- file1.go
- file2.go
- file3_test.go
```

---

## Phase 2: Parallel Agent Dispatch

### Step 3.1: Discover Project Context

1. **Identify stack:** Check for `go.mod`, `package.json`, `Makefile`, `Cargo.toml`, etc.
2. **Identify test commands:** Look in `Makefile`, `package.json` scripts, or CI config for lint, unit test, integration test, and E2E test commands
3. **Identify coding standards:** Look for `PROJECT_RULES.md`, linter configs, or equivalent
4. **Identify reference docs:** Look for PRD, TRD, API design, data model

Store discovered commands for use in the verification gate (Phase 6):
```
LINT_CMD=<discovered lint command>
TEST_UNIT_CMD=<discovered unit test command>
TEST_INTEGRATION_CMD=<discovered integration test command>
TEST_E2E_CMD=<discovered E2E test command>
```

### Step 3.2: Dispatch Agents

Dispatch ALL applicable agents simultaneously via `Task` tool. Each agent receives:
- The full content of every changed file
- The PR context (description, linked issues)
- ALL existing PR comments (so agents can validate/contest them)
- Coding standards and reference docs

**Agent prompt MUST include:**

```
PR Context:
  - PR #<number>: <title>
  - Purpose: <PR description summary>
  - Linked issues: <list>
  - Base branch: <base>

Existing PR Comments (evaluate these — validate or contest each one):
  [paste all comments grouped by source, including comments from "Duplicated Comments" sections]

Review scope: Only the files changed in this PR.

Your job:
  1. Review the CODE for issues in your domain
  2. EVALUATE each existing PR comment in your domain:
     - AGREE: The comment is valid and should be addressed
     - CONTEST: The comment is incorrect or unnecessary (explain why)
     - ALREADY FIXED: The comment was addressed in a subsequent commit
  3. Report NEW findings not covered by existing comments

Required output format:
  ## New Findings
  For each: severity, file, line, description, recommendation

  ## Comment Evaluation
  For each existing comment in your domain:
  - Comment source and summary
  - Your verdict: AGREE / CONTEST / ALREADY FIXED
  - Justification
```

### Agents (always dispatch ALL)

| # | Agent | Focus |
|---|-------|-------|
| 1 | **Code quality reviewer** | Architecture, design patterns, SOLID, DRY, maintainability |
| 2 | **Business logic reviewer** | Domain correctness, business rules, edge cases |
| 3 | **Security reviewer** | Vulnerabilities, authentication, input validation, OWASP |
| 4 | **Test quality analyst** | Test coverage gaps, error scenarios, flaky patterns |
| 5 | **Cross-file consistency** (worker) | Interfaces vs implementations, imports, shared constants, dead code |
| 6 | **Backend specialist** | Language idiomaticity, performance, concurrency, ecosystem patterns |
| 7 | **Frontend specialist** | Framework patterns, hooks, components, accessibility, performance |

Use whatever specialist droids are available in the environment. If a specialized droid does not exist for a domain, use a `worker` agent with domain-specific instructions. All agents MUST be dispatched in a SINGLE message with parallel Task calls.

---

## Phase 3: Consolidation

After ALL agents return:

1. **Merge** all new findings into a single list
2. **Merge** all comment evaluations into a single list
3. **Deduplicate** — if multiple agents flag the same issue, keep one entry and note which agents agreed
4. **Cross-reference** — for existing comments, note agreement/disagreement between agents and between agents and the original commenter
5. **Sort** by severity: CRITICAL > HIGH > MEDIUM > LOW
6. **Assign** sequential IDs (F1, F2, F3...)

### Source Attribution

Each finding MUST include its source(s):

| Source Type | Label |
|-------------|-------|
| New finding from agent review | `[Agent: <agent-name>]` |
| Existing CodeRabbit comment validated by agent | `[CodeRabbit + Agent: <agent-name>]` |
| Existing human review comment validated by agent | `[Reviewer: <username> + Agent: <agent-name>]` |
| Existing comment contested by agent | `[Contested: <source> vs Agent: <agent-name>]` |

---

## Phase 4: Present Overview

```markdown
## PR Review: #<number> — X findings

### New Findings (from agents)
| # | Severity | File | Summary | Agent(s) |
|---|----------|------|---------|----------|

### Validated Existing Comments
| # | Severity | File | Original Source | Summary | Validating Agent(s) |
|---|----------|------|----------------|---------|---------------------|

### Contested Comments
| # | Original Source | Comment Summary | Contesting Agent | Reason |
|---|----------------|----------------|-----------------|--------|

### Summary
- New findings: X (C critical, H high, M medium, L low)
- Validated comments: X
- Contested comments: X
- Already fixed: X
```

---

## Phase 5: Interactive Finding-by-Finding Resolution (collect decisions only)

Process ONE finding at a time, in severity order (CRITICAL first, LOW last). Include both new findings and validated existing comments. Present contested comments for user decision.

For EACH finding, present:

### 1. Finding Header

`## [SEVERITY] F# | [Category]`
- Source(s): which agent(s) and/or external reviewer(s) flagged this
- Agreement: which sources agree/disagree

### 2. Deep Technical Analysis

For each finding, provide a thorough analysis that goes beyond "what is wrong" — explain the full context so the user can make an informed decision:

**Problem description:**
- Clear description of the issue with code snippet
- For validated existing comments: show the original comment and the agent's validation
- For contested comments: show both the original comment and the agent's contestation

**Flow analysis:**
- Trace the execution flow through the affected code — what calls what, what data flows where
- Identify which consumers are affected (other services, frontend clients, end users, automated systems)
- Map the impact chain: if this is not fixed, what downstream behavior changes?

**Why it matters (user experience focus):**
- **For human users:** How does this affect the end-user experience? (errors they see, data they lose, actions they can't perform)
- **For system consumers (APIs):** How does this affect other services or integrations? (contract violations, unexpected responses, silent failures)
- Quantify the impact when possible: "affects X% of requests", "fails silently for Y scenario"

**Engineering analysis (when recommending implementation):**
- **API best practices:** Does the current implementation follow REST/gRPC conventions? Is the contract clear and consistent? Are error responses informative? Is idempotency handled?
- **Software engineering principles:** SOLID, DRY, separation of concerns, fail-fast, defensive programming — which principles are violated and why they matter here
- **Resilience and reliability:** Error handling, retry semantics, timeout behavior, graceful degradation
- **Observability:** Can the issue be detected in production? Are there logs/metrics/traces that would surface this problem?

**When contesting (recommending NOT to implement):**
- Explain why the current code is correct or acceptable
- Reference specific patterns in the codebase that validate the approach
- Identify the cost of implementing vs the risk of not implementing
- If the concern is valid but low-priority, suggest where to track it

### 3. Proposed Solutions

One or more approaches, each with:
- What changes (specific files, functions, patterns)
- How the flow changes after the fix — trace the new execution path
- Tradeoffs (complexity, performance, breaking changes, migration effort)
- Impact on API consumers (breaking vs non-breaking, backward compatibility)
- If it's a straightforward fix with no tradeoffs, state: "Direct fix, no tradeoffs."

Include a recommendation when one option is clearly better, with clear justification rooted in user experience and engineering quality.

### 4. Wait for User Decision

Use `AskUser` tool. **BLOCKING**: Do NOT advance to the next finding until the user decides.

The user may:
- Approve an option (e.g., "A", "B")
- Request more context
- Discard the finding
- Defer to a future version
- Group with the next finding if related

### 5. Record Decision

Internally record every decision: finding ID, source(s), chosen option (or "skip"/"defer"), and rationale if provided. Do NOT apply any fix yet — fixes are applied with separate commits in Phase 6.

---

## Phase 6: Apply Fixes with Separate Commits

**IMPORTANT:** This phase starts ONLY after ALL findings have been presented and ALL decisions collected. No fix is applied during Phase 5.

### Step 7.1: Present Pre-Apply Summary

Before touching any code, show the user a summary of everything that will be changed:

```markdown
## Fixes to Apply (X of Y findings)

| # | Finding | Source | Decision | Files Affected |
|---|---------|--------|----------|---------------|
| F1 | [summary] | [Agent + CodeRabbit] | Option A | file1.go |
| F3 | [summary] | [Agent: Security] | Option B | auth.go |

### Skipped (Z findings)
| # | Finding | Source | Reason |
|---|---------|--------|--------|
| F2 | [summary] | [Reviewer: john] | User: out of scope |

### Deferred (W findings)
| # | Finding | Source | Destination |
|---|---------|--------|-------------|
| F5 | [summary] | [Agent: QA] | Backlog |
```

### Step 7.2: Apply and Commit Each Fix Individually

Create **one commit per finding** whenever possible. This makes it easy to trace which commit addresses which review comment.

**Grouping rules:**
- **Independent fixes** (touching different logical concerns) → one commit each
- **Related fixes** (e.g., F1 and F3 both fix the same validation logic in the same function) → group into a single commit, referencing all finding IDs
- When in doubt, prefer separate commits — smaller commits are easier to review and revert

**For each approved fix (or group of related fixes), dispatch a specialist droid:**

Use the `Task` tool to dispatch the appropriate droid for each fix. Do NOT apply fixes directly — always delegate to a specialist.

**Droid selection priority:**
1. **Ring specialist droids (preferred):**
   - `ring-dev-team-backend-engineer-golang` — for Go source fixes
   - `ring-dev-team-backend-engineer-typescript` — for TypeScript backend fixes
   - `ring-dev-team-frontend-engineer` — for React/Next.js frontend fixes
   - `ring-dev-team-qa-analyst` — for test-related fixes
2. **Other available specialist droids**
3. **`worker` with domain instructions** — as fallback

**Droid prompt for each fix:**

```
Goal: Apply fix for review finding F<N>.

Finding:
  - ID: F<N>
  - Severity: <severity>
  - File(s): <affected files>
  - Problem: <finding description>
  - Chosen solution: <user's chosen option from Phase 5>

Context:
  - Full content of affected file(s): [paste]
  - Coding standards: [paste relevant sections]
  - Existing patterns in the codebase to follow: [file:line references]

Constraints:
  - Apply ONLY the fix described above — do not refactor or improve other code
  - Follow existing code style and patterns
  - Run lint after applying the fix and resolve any formatting issues
  - If the fix requires updating tests, update them

Expected output:
  - List of files modified
  - Summary of changes made
```

**After the droid completes each fix:**

1. Verify the droid applied changes correctly
2. Run lint — if format issues remain, fix them
3. Stage ONLY the files changed by this fix: `git add <affected_files>`
4. Commit with a descriptive message that references the finding ID(s):
   ```bash
   git commit -m "fix: <concise description of what was fixed>

   Addresses review finding(s): <F1, F2, ...>"
   ```
5. Record the commit SHA for this fix: `git rev-parse HEAD`
6. Store the mapping: `{finding_id} → {commit_sha}` for use in Phase 8

**If a fix causes lint failures that cannot be auto-resolved**, stop, present the issue to the user, and ask for guidance before continuing to the next fix.

### Step 7.3: Verification Gate

After ALL individual commits are created, run the full test suite:
- Always run lint and unit tests with coverage profiling
- If backend files were changed: also run integration tests with coverage profiling
- If frontend files were changed: also run E2E tests (if available)

**Coverage measurement:**
```bash
# Unit tests
go test -coverprofile=coverage-unit.out ./...
go tool cover -func=coverage-unit.out | tail -1

# Integration tests (if applicable)
go test -tags=integration -coverprofile=coverage-integration.out ./...
go tool cover -func=coverage-integration.out | tail -1
```

**Coverage thresholds:**
- Unit tests: 85% minimum
- Integration tests: 70% minimum

If coverage is below threshold, flag as a finding and ask the user whether to address it before proceeding or defer.

**E2E tests:** If not configured, ask the user using `AskUser`:
"E2E tests are not configured. Should they be implemented, or skip for now?"

### Step 7.4: Test Scenario Gap Analysis

After coverage measurement, dispatch an agent to identify missing test scenarios in the files changed by the PR.

**Dispatch a test gap analyzer** via `Task` tool. Use `ring-default-ring-test-reviewer`, `ring-dev-team-qa-analyst`, or `worker` (in that priority order).

The agent receives:
1. **PR changed source files** — full content (non-test files only)
2. **Test files for changed source** — full content
3. **Coverage profile** — `go tool cover -func` output
4. **PR context** — description, linked issues

```
Goal: Identify missing test scenarios in files changed by PR #<number>.

Context:
  - PR: #<number> — <title>
  - Source files changed: [full content]
  - Test files: [full content]
  - Coverage profile: [go tool cover -func output]

Your job:
  For each public function changed/added in this PR:
  1. Unit tests: check for happy path, error paths, edge cases, validation failures
  2. Integration tests: check for DB failure, timeout, retry, rollback scenarios
  3. Report what EXISTS and what is MISSING

Required output format:
  ## Unit Test Gaps
  | # | File | Function | Existing Scenarios | Missing Scenarios | Priority |
  |---|------|----------|--------------------|-------------------|----------|

  ## Integration Test Gaps
  | # | File | Function | Existing Scenarios | Missing Scenarios | Priority |
  |---|------|----------|--------------------|-------------------|----------|

  ## Summary
  - Functions analyzed: X
  - Fully covered: X | Partial: X | No tests: X
  - Missing scenarios: X HIGH, Y MEDIUM, Z LOW
```

HIGH priority gaps are presented as findings in the summary. The user decides whether to address them before merge or defer.

If tests fail:
1. Identify which commit introduced the failure (use `git bisect` or reason from the test output)
2. Attempt to fix (max 3 attempts)
3. If fixed, amend the offending commit or create a follow-up fix commit
4. If not fixable after 3 attempts, revert that specific commit, present the failure to the user, and ask for guidance

All commands MUST pass and coverage MUST meet thresholds before proceeding to Phase 7.

---

## Phase 7: Final Summary

```markdown
## PR Review Summary: #<number> — <title>

### Sources Analyzed
- CodeRabbit comments: X evaluated (Y validated, Z contested)
- Human reviewer comments: X evaluated (Y validated, Z contested)
- New agent findings: X
- Already fixed: X

### Fixed (X findings)
| # | Source | File(s) | Commit | Fix Applied |
|---|--------|---------|--------|-------------|

### Skipped (X findings)
| # | Source | File(s) | Reason |
|---|--------|---------|--------|

### Deferred (X findings)
| # | Source | File(s) | Destination |
|---|--------|---------|-------------|

### Verification
- Lint: PASS
- Unit tests: PASS (X tests)
- Integration tests: PASS / SKIPPED
- E2E tests: PASS / SKIPPED

### Test Coverage
- Unit tests: XX.X% (threshold: 85%) — PASS / FAIL
- Integration tests: XX.X% (threshold: 70%) — PASS / FAIL
- E2E tests: Configured / Not configured

### PR Readiness
- [ ] All CRITICAL/HIGH findings resolved
- [ ] Changes align with PR description and linked issues
- [ ] No unrelated changes included in the PR
- [ ] Test coverage adequate for the changes

**Verdict:** READY FOR MERGE / NEEDS CHANGES
```

Commits were already created individually in Phase 6. Ask the user if they want to push.

---

## Phase 8: Respond to PR Comments (MANDATORY — runs AFTER commits)

This phase runs AFTER the user pushes or explicitly skips the push in Phase 7. It is MANDATORY regardless of whether any fixes were applied. Even if every finding was skipped and no commit was made, every comment thread MUST receive a reply and be resolved.

**IMPORTANT:** Use the `{finding_id} → {commit_sha}` mapping recorded in Phase 6 to reference the exact commit that addresses each comment. This gives reviewers a direct link to the fix.

**Scope:** ALL existing PR comment threads — not just findings/suggestions, but also questions, clarification requests, and discussion threads. Every unanswered comment on the PR must be addressed.

### Step 9.1: Identify ALL Comment Threads to Respond

Scan ALL existing PR comments collected in Step 0.3. For each thread, determine the response:

**For findings/suggestions evaluated by agents:**

| Decision | Action |
|----------|--------|
| **Fixed** | Reply with the commit SHA, then resolve the thread |
| **Skipped/Discarded** | Reply explaining why it won't be fixed, then resolve the thread |
| **Deferred** | Reply explaining it was deferred and where it was tracked, then resolve the thread |
| **Contested** | Reply explaining why the comment was contested, then resolve the thread |
| **Already fixed** | Reply noting it was already addressed, then resolve the thread |

**For questions and clarification requests:**

| Type | Action |
|------|--------|
| **Question about implementation** | Answer the question based on the code context and review analysis, then resolve the thread |
| **Clarification request** | Provide the clarification based on the codebase and task context, then resolve the thread |
| **Discussion/opinion** | Provide a clear response with the decision taken, then resolve the thread |

**IMPORTANT:** Every thread MUST be resolved after posting the reply, regardless of the type or decision. No comment thread should remain open and unanswered after this phase completes.

### Step 9.2: Post Replies and Resolve Threads

For each comment thread, post the reply AND resolve the conversation on GitHub:

**For inline review comments (most common):**
```bash
# Post the reply
gh api repos/{owner}/{repo}/pulls/{number}/comments \
  --method POST \
  -f body="<reply>" \
  -F in_reply_to=<comment_id>
```

**For general PR comments:**
```bash
gh pr comment <PR_NUMBER_OR_URL> --body "<reply>"
```

**Resolve the conversation thread** (for review comment threads):
```bash
gh api graphql -f query='
  mutation {
    resolveReviewThread(input: {threadId: "<thread_node_id>"}) {
      thread { isResolved }
    }
  }
'
```

To get the thread node ID, query the PR's review threads:
```bash
gh api graphql -f query='
  query {
    repository(owner: "<owner>", name: "<repo>") {
      pullRequest(number: <number>) {
        reviewThreads(first: 100) {
          nodes {
            id
            isResolved
            comments(first: 1) {
              nodes { body databaseId }
            }
          }
        }
      }
    }
  }
'
```

Match each thread by its first comment's `databaseId` to the `comment_id` collected in Step 0.3, then resolve using the thread's `id`.

**Resolve ALL replied threads** — not just "Fixed" ones. Skipped, deferred, contested, and already-fixed threads must also be resolved after posting the reply.

### Step 9.3: Reply Templates

**Fixed:**
```
Fixed in <commit_sha> (use the specific SHA from the finding→commit mapping recorded in Phase 6).
```

**Skipped/Discarded:**
```
Won't fix: <user's reason or rationale>.
```

**Deferred:**
```
Deferred to <destination> (e.g., backlog, future PR): <brief reason>.
```

**Contested:**
```
Contested: <agent's reasoning for why the comment is incorrect or unnecessary>.
```

**Already fixed:**
```
Already addressed in a previous commit.
```

**Question/Clarification (answer based on code context):**
```
<direct answer to the question, referencing specific code/files when applicable>.
```

### Step 8.4: Hide Fully-Resolved Review Sections

After all replies are posted and threads resolved, check each PR review section (e.g., CodeRabbit's "Changes requested" reviews, human reviewer summaries) to determine if ALL its comment threads have been resolved.

**Step 1: Query all PR reviews with their threads:**
```bash
gh api graphql -f query='
  query {
    repository(owner: "<owner>", name: "<repo>") {
      pullRequest(number: <number>) {
        reviews(first: 100) {
          nodes {
            id
            body
            author { login }
            state
          }
        }
        reviewThreads(first: 100) {
          nodes {
            id
            isResolved
            comments(first: 1) {
              nodes {
                pullRequestReview { id }
              }
            }
          }
        }
      }
    }
  }
'
```

**Step 2: For each review, check if ALL its threads are resolved:**
- Group `reviewThreads` by `comments.nodes[0].pullRequestReview.id`
- For a given review, if every associated thread has `isResolved: true`, the review is fully resolved

**Step 3: Hide fully-resolved reviews using `minimizeComment`:**
```bash
gh api graphql -f query='
  mutation {
    minimizeComment(input: {subjectId: "<review_node_id>", classifier: RESOLVED}) {
      minimizedComment {
        isMinimized
        minimizedReason
      }
    }
  }
'
```

**Rules:**
- Only hide reviews where ALL threads are resolved — if even one thread remains unresolved, leave the review visible
- This applies to any review source (CodeRabbit, human reviewers, other bots)
- Reviews with no associated threads (e.g., approvals with no inline comments) should NOT be hidden

### Step 8.5: Present Reply Summary

After posting all replies and hiding resolved reviews, present a summary:

```markdown
### PR Comment Replies Posted
| # | Thread | Source | Reply | Commit | Status |
|---|--------|--------|-------|--------|--------|
| 1 | file.go:42 | CodeRabbit | Fixed | abc1234 | Resolved |
| 2 | file.go:88 | @reviewer | Won't fix: out of scope | — | Closed |
| 3 | general | CodeRabbit | Deferred to backlog | — | Closed |
| 4 | file.go:15 | @reviewer | [answer to question] | — | Resolved |

### Fully-Resolved Reviews Hidden
| # | Review Author | Review State | Threads | Action |
|---|---------------|-------------|---------|--------|
| 1 | coderabbitai | CHANGES_REQUESTED | 5/5 resolved | Hidden (RESOLVED) |
```

---

## Rules

- Always fetch PR metadata AND existing comments before starting the review
- Agents MUST evaluate existing comments — validate, contest, or mark as already fixed
- Every finding must include source attribution (agent, CodeRabbit, human reviewer)
- Never review files outside the PR scope — only files changed in the PR
- Include PR description, linked issues, and existing comments in every agent prompt
- One finding at a time, severity order (CRITICAL > HIGH > MEDIUM > LOW)
- No changes without prior user approval — the user ALWAYS decides the approach
- Fixes are collected during Phase 5 and applied with separate commits in Phase 6
- Do NOT merge the PR — only review and present findings
- Do NOT commit fixes without explicit user approval
- ALWAYS reply to every existing PR comment thread — findings, questions, clarifications, discussions — with the resolution or answer, then resolve the thread. This applies even if no fixes were applied and no commit was made
- If `gh` CLI is not installed, inform the user and suggest installation (e.g., `brew install gh` on macOS). If installed but not authenticated, ask the user to run `gh auth login`
