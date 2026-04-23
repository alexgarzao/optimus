---
name: optimus-pr-check
description: "Unified PR review orchestrator. Fetches PR metadata, collects ALL review comments (Codacy, DeepSource, CodeRabbit, human reviewers), dispatches parallel agents to evaluate code and comments, presents findings interactively, applies fixes with TDD cycle and separate commits per finding, responds to every comment thread with commit reference or justification, and adds inline suppression tags for Codacy/DeepSource when a finding won't be fixed."
trigger: >
  - When user provides a PR URL for review (e.g., "review this PR: https://github.com/org/repo/pull/123")
  - When user asks to review a pull request
skip_when: >
  - No PR URL provided and user wants a generic code review (use optimus-deep-review directly)
  - PR is already merged (nothing to review)
  - User wants to run automated checks only (use `make lint && make test` directly)
prerequisite: >
  - PR URL is provided or can be inferred (current branch has an open PR)
  - gh CLI is installed and authenticated
  - For Codacy/DeepSource findings: workflows codacy-issues.yml and deepsource-pr-issues.yml should exist in the repo (if not present, those sources are simply skipped)
NOT_skip_when: >
  - "The PR is small" -- Small PRs still benefit from structured review with PR context.
  - "I already looked at the diff" -- Specialist agents catch issues human review misses.
  - "CI passed" -- CI checks automated rules; agents review logic, security, and quality.
  - "CodeRabbit already reviewed" -- Agents validate/contest CodeRabbit findings and catch what it misses.
  - "Codacy/DeepSource already analyzed" -- Agents validate/contest static analysis findings and catch what they miss.
examples:
  - name: Review a PR by URL
    invocation: "Review this PR: https://github.com/org/repo/pull/42"
    expected_flow: >
      1. Fetch PR metadata and ALL existing comments (Codacy, DeepSource, CodeRabbit, human)
      2. Checkout PR branch
      3. Present PR summary with all comment sources and CI status
      4. Dispatch agents to review code AND evaluate ALL existing comments
      5. Consolidate with source attribution and deduplication
      6. Interactive finding-by-finding resolution
      7. Apply fixes with TDD cycle, separate commits per finding
      8. Coverage verification and convergence loop
      9. Push commits
      10. Respond to ALL comment threads (commit SHA or won't-fix with suppression)
      11. Final summary with verdict
  - name: Review current branch PR
    invocation: "Review the PR for this branch"
    expected_flow: >
      1. Detect current branch, find associated open PR via gh CLI
      2. Fetch PR metadata and comments
      3. Standard flow
related:
  complementary:
    - optimus-deep-review
  differentiation:
    - name: optimus-deep-review
      difference: >
        optimus-deep-review is a generic code review that works with any scope
        (all files, git diff, directory). optimus-pr-check adds PR context
        (description, linked issues, existing comments from ALL sources) and
        evaluates feedback from multiple sources (Codacy, DeepSource, CodeRabbit,
        human reviewers, agents).
  sequence:
    after:
      - optimus-check
    before:
      - optimus-done
  re_execution:
    allowed: true
verification:
  automated:
    - command: "which gh 2>/dev/null && echo 'available'"
      description: gh CLI is installed
      success_pattern: available
  manual:
    - PR metadata and comments from ALL sources fetched correctly
    - Source attribution present in all findings
    - All findings presented interactively with progress indicator
    - Approved fixes applied with TDD cycle and separate commits
    - Coverage verification passed thresholds
    - Convergence loop completed
    - ALL comment threads replied with commit SHA or won't-fix justification
    - Codacy/DeepSource suppression tags added for won't-fix findings
    - PR readiness verdict presented
---

# PR Review

Unified PR review orchestrator. Fetches PR metadata, collects ALL review comments (Codacy, DeepSource, CodeRabbit, human reviewers), dispatches agents to evaluate both code and comments, and presents findings with source attribution. Applies fixes with TDD cycle, responds to every comment with resolution, and adds inline suppression for Codacy/DeepSource won't-fix findings.

---

## Pre-Check: Verify GitHub CLI (HARD BLOCK)

**HARD BLOCK:** Verify GitHub CLI — see AGENTS.md Protocol: GitHub CLI Check.

---

## CRITICAL: Every Invocation Starts From Scratch

**HARD BLOCK:** Every time this skill is invoked, it MUST fetch ALL data fresh from the PR. There is NO state carried over from previous invocations.

- Do NOT assume issues from a previous run are still resolved
- Do NOT skip fetching comments because "I already saw this PR"
- Do NOT say "issues were already resolved" without fetching and verifying RIGHT NOW
- New comments, new commits, new CI results may exist since the last run
- Always run Phase 1 completely: fetch metadata, fetch ALL threads, fetch CI checks, fetch changed files
- The PR may have changed entirely since the last time you looked at it

If you find yourself saying "these were already addressed" without having run `gh api` commands in THIS session, you are violating this rule.

---

## Operating Mode

This skill is a **standalone PR review tool**. It does NOT change task status in
state.json and is NOT part of the pipeline stages. It works like deep-review — the
user invokes it when they want to review a PR, independently of the task lifecycle.

No task identification, status validation, or state.json writes are performed.

---

## Phase 1: Fetch PR Context

### Step 1.1: Obtain PR URL

If the user provided a PR URL, use it directly.

If no URL was provided, attempt to find the PR for the current branch:

```bash
gh pr view --json url,number,title --jq '.url' 2>/dev/null
```

If no PR is found, offer to create one via `AskUser`:

```
No PR exists for the current branch (<branch>). What should I do?
```
Options:
- **Create PR** — create a PR against the default branch with a Conventional Commits title derived from the task's Tipo and title (same logic as check Phase 13)
- **Provide URL** — I have a PR URL to use
- **Cancel** — stop the review

If the user chooses **Create PR**:
1. Generate PR title from task Tipo + ID + title (e.g., `feat(T-003): add user registration API`)
2. Generate PR body from Ring source (read via `TaskSpec` column in tasks.md)
3. Push the branch if not yet pushed: `git push -u origin "$(git branch --show-current)"`
4. Create the PR:
   ```bash
   gh pr create --title "<title>" --body "<body>" --base "$DEFAULT_BRANCH" --assignee @me
   ```
5. Use the newly created PR for the rest of the review

If the user chooses **Provide URL**, ask for the URL via `AskUser`.

### Step 1.2: Fetch PR Metadata

```bash
gh pr view <PR_NUMBER_OR_URL> --json title,body,state,headRefName,baseRefName,changedFiles,additions,deletions,labels,milestone,assignees,reviewRequests,comments,url,number
```

**Guard: Check PR state.** If the PR state is `MERGED` or `CLOSED`, inform the user and stop.

Extract and store:
- **Title and description** — the PR's purpose and context
- **Head branch and base branch** — for accurate diff
- **Changed files count** — scope indicator
- **Labels and milestone** — categorization context
- **Linked issues** — from PR description (look for "Fixes #", "Closes #", "Resolves #" patterns)

### Step 1.2.1: Validate PR Title (Conventional Commits)

The PR title MUST follow the **Conventional Commits 1.0.0** specification
(https://www.conventionalcommits.org/en/v1.0.0/).

**Expected format:** `<type>[optional scope]: <description>`

**Validation rules:**
1. Title starts with a valid type: `feat`, `fix`, `refactor`, `chore`, `docs`, `test`,
   `build`, `ci`, `style`, `perf`
2. Optional scope in parentheses after the type (e.g., `feat(auth):`)
3. Optional `!` before `:` for breaking changes
4. Colon followed by a single space before the description
5. Description is present and non-empty
6. Type is lowercase

**Regex for validation:**
```
^(feat|fix|refactor|chore|docs|test|build|ci|style|perf)(\([a-zA-Z0-9_\-]+\))?!?: .+$
```

PR title validation follows AGENTS.md Protocol: PR Title Validation, with the addition that invalid titles become MEDIUM severity findings.

**If validation fails:** add a finding (severity: MEDIUM) to the findings list with:
- Current title
- What's wrong (missing type, wrong format, type/Tipo mismatch, etc.)
- Suggested corrected title
- Fix command: `gh pr edit <number> --title "<corrected title>"`

**If validation passes:** no action needed, proceed.

### Step 1.3: Collect ALL Existing PR Comments and Threads

**IMPORTANT:** Static analysis tools post comments in TWO different ways:
1. **Native app comments** — posted directly by the tool's GitHub App (e.g., `deepsource-io`, `codacy-production`). These create review threads that the REST API CANNOT reply to (returns 404). You MUST use GraphQL to reply and resolve these.
2. **Workflow comments** — posted by `github-actions[bot]` via CI workflows (e.g., `codacy-issues.yml`, `deepsource-pr-issues.yml`). These are standard review comments that the REST API CAN reply to.

You MUST collect BOTH types for each tool.

#### Step 1.3.1: Fetch ALL Review Threads via GraphQL (PRIMARY SOURCE)

This is the **single source of truth** for all review threads. It captures threads from ALL sources (native apps, workflows, humans, bots) in one query.

**IMPORTANT — Pagination:** The query uses `first: 100` for threads and `first: 10` for comments. If the response's `pageInfo.hasNextPage` is `true`, you MUST fetch additional pages using cursor-based pagination (`after: "<endCursor>"`). PRs with 100+ review threads or threads with 10+ comments will silently lose data without pagination.

```bash
gh api graphql -f query='
  query($cursor: String) {
    repository(owner: "<owner>", name: "<repo>") {
      pullRequest(number: <number>) {
        reviewThreads(first: 100, after: $cursor) {
          pageInfo { hasNextPage endCursor }
          nodes {
            id
            isResolved
            isOutdated
            path
            line
            comments(first: 10) {
              nodes {
                databaseId
                author { login }
                body
                createdAt
              }
            }
          }
        }
      }
    }
  }
'
```

If `pageInfo.hasNextPage` is `true`, re-run with `-f cursor="<endCursor>"` until all pages are fetched. Merge all nodes into a single list.

For each thread, classify by the **first comment's author**:

| Author login | Source | Reply method |
|-------------|--------|-------------|
| `deepsource-io` | DeepSource (native app) | GraphQL only (`addPullRequestReviewThreadReply`) |
| `codacy-production` | Codacy (native app) | GraphQL only (`addPullRequestReviewThreadReply`) |
| `github-actions[bot]` with body starting `**Codacy**` | Codacy (workflow) | REST API (`in_reply_to`) |
| `github-actions[bot]` with body starting `**DeepSource**` | DeepSource (workflow) | REST API (`in_reply_to`) |
| `coderabbitai[bot]` | CodeRabbit | REST API (`in_reply_to`) |
| `copilot` or `github-advanced-security[bot]` | Copilot / GitHub Security | REST API (`in_reply_to`) |
| Any other | Human reviewer | REST API (`in_reply_to`) |

Store each thread as:
```
{
  thread_node_id: "<GraphQL node ID>",
  first_comment_database_id: <integer>,
  source: "deepsource" | "codacy" | "coderabbit" | "copilot" | "human",
  reply_method: "graphql" | "rest",
  is_resolved: true | false,
  is_outdated: true | false,
  path: "<file>",
  line: <number>,
  body: "<first comment body>"
}
```

#### Step 1.3.2: Fetch General PR Comments

```bash
gh pr view <PR_NUMBER_OR_URL> --comments
```

These are non-inline comments (discussion, summaries). They don't have threads.

#### Step 1.3.3: Parse Comment Content

**Codacy native comments** (author: `codacy-production`):
- Body contains HTML with issue details embedded
- Extract: severity, rule, message, file, line from the thread metadata (path/line) and body

**Codacy workflow comments** (author: `github-actions[bot]`, body starts with `**Codacy**`):
```
**Codacy** | <SEVERITY> | <annotation_level>

<message>
```
Extract: severity (HIGH/MEDIUM/LOW), annotation_level, message, file, line.

**DeepSource native comments** (author: `deepsource-io`):
- Body contains HTML with `<!-- DeepSource: id=... -->` marker
- Contains issue shortcode, title, description, severity in structured HTML
- Extract: shortcode, severity, category, title, explanation from body content

**DeepSource workflow comments** (author: `github-actions[bot]`, body starts with `**DeepSource**`):
```
**DeepSource** | `<shortcode>` | <SEVERITY> | <CATEGORY>
**Analyzer:** <analyzer_name>

**<title>**

<explanation>
```
Extract: shortcode, severity, category, analyzer, title, explanation, file, line.

**CodeRabbit comments** (author: `coderabbitai[bot]`):
- Inline review comments with suggestions
- **Duplicated Comments section:** CodeRabbit embeds a `<details>` block titled "Duplicate comments" in its review body listing findings it already reported in previous reviews but remain unresolved. Parse each entry as a separate finding and tag with `origin: duplicate` (see tagging rules below).
- **Outside diff range section:** CodeRabbit embeds a `<details>` block titled `⚠️ Outside diff range comments` in its review body with suggestions about code OUTSIDE the PR diff. Parse each entry (file path, line, suggestion) as a separate finding and tag with `origin: outside-diff` (see tagging rules below).

**CodeRabbit origin tagging rules:**
When presenting findings from CodeRabbit, ALWAYS include the origin tag in the finding header:
- `[CodeRabbit — DUPLICATE]` for findings from the "Duplicate comments" section. These are repeat findings from previous reviews that remain unaddressed.
- `[CodeRabbit — OUTSIDE PR DIFF]` for findings from the "Outside diff range" section. These affect code not changed in this PR.
- `[CodeRabbit]` for regular inline findings (no special tag needed).

This tagging helps the user understand whether the finding is about code they changed in this PR, code outside their changes, or a recurring issue from a previous review.

**Human reviewer comments:** All threads where the first comment author is not a known bot.

#### Step 1.3.4: Summary

Group all collected threads by source:
```
PR Threads:
  - Codacy: X threads (Y native app, Z workflow) — A unresolved
  - DeepSource: X threads (Y native app, Z workflow) — A unresolved
  - CodeRabbit: X threads — A unresolved
  - Human reviewers: X threads from [usernames] — A unresolved
  - Other bots: X threads — A unresolved
  Total: X threads, Y unresolved
```

### Step 1.4: Checkout PR Branch

```bash
gh pr checkout <PR_NUMBER_OR_URL>
```

If already on the correct branch, skip. If checkout fails due to uncommitted changes, inform the user.

### Step 1.5: Fetch CI Check Status (MANDATORY)

**HARD BLOCK:** You MUST run this command and report the results. Do NOT skip this step.

```bash
gh pr checks <PR_NUMBER_OR_URL>
```

This command lists ALL checks: GitHub Actions workflows (Backend, Frontend, Merge Gate), external services (Codacy, DeepSource), and any other integrations. **Every line with "fail" is a problem that MUST be investigated.**

Example output:
```
Codacy Static Code Analysis    fail    0       https://app.codacy.com/...
DeepSource: Go                 fail    2m23s   https://app.deepsource.com/...
DeepSource: JavaScript         fail    28s     https://app.deepsource.com/...
Merge Gate                     fail    5s      https://github.com/.../actions/runs/...
Backend                        pass    3m14s   https://github.com/.../actions/runs/...
Frontend                       pass    2m35s   https://github.com/.../actions/runs/...
```

In this example, there are **4 failing checks**. ALL 4 must become findings.

Count and classify:
```
CI Status:
  - Passing: X checks [list names]
  - FAILING: X checks [list ALL names — this includes Codacy, DeepSource, Merge Gate, and ANY other failing check]
  - Pending/Running: X checks
```

### Step 1.6: Investigate EVERY Failing Check (MANDATORY)

**HARD BLOCK:** If `gh pr checks` showed ANY failing check, you MUST create a finding for EACH one. This applies to ALL types of failing checks:
- GitHub Actions workflows (Backend, Frontend, Merge Gate, etc.)
- Codacy Static Code Analysis
- DeepSource analyzers (Go, JavaScript, Docker, Shell, etc.)
- Any other external check

**Do NOT rationalize away failing checks.** Common mistakes to avoid:
- "Codacy/DeepSource failures are already covered by the review threads" — NO. The failing CHECK is a separate problem from individual comments. The check failing means the PR cannot be merged.
- "Merge Gate failed because of Codacy/DeepSource" — YES, but it's still a failing check that must be reported as a finding with root cause.
- "These are external tools, not CI" — ALL checks shown by `gh pr checks` are CI checks regardless of their source.

**For each failing check:**

1. **Fetch details:**
```bash
COMMIT_SHA=$(gh api repos/{owner}/{repo}/pulls/{number} --jq '.head.sha' 2>/dev/null)
if [ -z "$COMMIT_SHA" ]; then
  echo "ERROR: Could not fetch commit SHA for PR. Check gh auth and network."
  # STOP — cannot analyze CI checks without commit SHA
fi

# Get ALL failing check runs with their details
gh api repos/{owner}/{repo}/commits/${COMMIT_SHA}/check-runs \
  --jq '.check_runs[] | select(.conclusion == "failure") | {name, conclusion, app_slug: .app.slug, details_url, output: {title: .output.title, summary: .output.summary, annotations_count: .output.annotations_count}}'
```

2. **For GitHub Actions failures, fetch logs:**
```bash
RUN_ID=$(echo "<details_url>" | sed -n 's|.*/runs/\([0-9]*\).*|\1|p')
if [ -n "$RUN_ID" ]; then
  gh run view "$RUN_ID" --log-failed 2>/dev/null | tail -100
fi
```

3. **For Codacy failures, check annotation count:**
```bash
gh api repos/{owner}/{repo}/commits/${COMMIT_SHA}/check-runs \
  --jq '.check_runs[] | select(.app.slug == "codacy-production") | {name, conclusion, annotations: .output.annotations_count}'
```

4. **For DeepSource failures, check each analyzer:**
```bash
gh api repos/{owner}/{repo}/commits/${COMMIT_SHA}/check-runs \
  --jq '.check_runs[] | select(.app.slug == "deepsource-io") | {name, conclusion, title: .output.title}'
```

5. **Create a finding for EACH failing check** with:
   - Severity: **HIGH** (any failing check blocks merge)
   - Source: `[CI: <check-name>]`
   - The error message / log output / annotation count
   - Root cause analysis (what is causing the failure)
   - Proposed fix (what needs to change to make it pass)

These CI failure findings are included in Phase 4 consolidation alongside agent findings, assigned sequential IDs (F1, F2...), and presented to the user for resolution in Phase 6 like any other finding.

**IMPORTANT:** CI failures are NOT informational — they are actionable findings that block merge readiness. If you present a PR summary that says "everything is OK" while `gh pr checks` shows failing checks, you have violated this rule.

### Step 1.7: Fetch Changed Files

```bash
gh pr diff <PR_NUMBER_OR_URL> --name-only
```

Read the full content of each changed file for the review agents.

---

## Phase 2: Present PR Summary

**HARD BLOCK:** If `gh pr checks` showed ANY failing checks, the summary MUST list every failing check name prominently. Do NOT present a summary without the CI Status section. If all checks pass, say so explicitly. If any fail, they MUST appear in bold with the word "FAILING".

```markdown
## PR Review: #<number> — <title>

**Branch:** <head> → <base>
**Changed files:** X files (+Y additions, -Z deletions)
**Labels:** [label1, label2]
**Linked issues:** #issue1, #issue2

### CI Status
- Passing: X checks
- **FAILING: X checks** ← [list failing check names with links]
- Codacy: <conclusion> (<N> annotations)
- DeepSource: <analyzer statuses>
- Pending: X checks

### Existing Review Comments
- **Codacy:** X issues (via workflow comments)
- **DeepSource:** X issues (via workflow comments)
- **CodeRabbit:** X comments (Y unresolved)
- **Human reviewers:** X comments from [usernames] (Y unresolved)

### PR Description
<PR body/description>

### Changed Files
- file1.go
- file2.go
```

---

## Phase 3: Parallel Agent Dispatch

### Step 3.1: Discover Project Context

1. **Identify stack:** Check for `go.mod`, `package.json`, `Makefile`, `Cargo.toml`, etc.
2. **Verify Makefile targets (HARD BLOCK):** The project MUST have a `Makefile` with `lint` and `test` targets. If either is missing, **STOP**: "Project is missing required Makefile targets (`make lint`, `make test`). Add them before running pr-check."
3. **Identify project rules and AI instructions (MANDATORY):** Execute project rules discovery — see AGENTS.md Protocol: Project Rules Discovery.
4. **Identify reference docs:** Look for PRD, TRD, API design

### Step 3.2: Baseline Unit Tests

Unit tests should pass before dispatching review agents. This establishes the baseline —
if tests are already failing, agent findings may be unreliable.

```bash
make test
```

**If unit tests fail:**
1. Present the failure output (first 30 lines)
2. Ask the user via `AskUser`: "Unit tests are failing. Fix before continuing, or skip?"
3. Do NOT proceed to agent dispatch until tests pass or user explicitly chooses to skip

**If unit tests pass:** proceed to Step 3.3.

### Step 3.3: Dispatch Agents

Dispatch ALL applicable agents simultaneously via `Task` tool. Each agent receives file paths and can navigate the codebase autonomously.

**Agent prompt MUST include:**

```
PR Context:
  - PR #<number>: <title>
  - Purpose: <PR description summary>
  - Linked issues: <list>
  - Base branch: <base>

  - Project root: <absolute path to project worktree>
  - Task spec: <TASKS_DIR>/<TaskSpec> (READ this file if task-linked PR)
  - Reference docs dir: <TASKS_DIR>/ (explore for PRD, TRD, API design, data model)
  - Project rules: AGENTS.md, PROJECT_RULES.md, docs/PROJECT_RULES.md (READ all that exist)
  - Changed files: [list of file paths] (READ each file)

IMPORTANT: You have access to Read, Grep, and Glob tools. USE THEM to:
  - Read files at the paths above
  - Search the codebase for patterns similar to the code under review
  - Find how the same problem was solved elsewhere in the project
  - Discover test patterns, error handling conventions, and architectural styles
  - Explore related files not listed above when needed for context

Existing PR Comments — evaluate ALL of these (validate or contest each one):

  Codacy Issues:
  [paste all Codacy findings with file, line, severity, message]

  DeepSource Issues:
  [paste all DeepSource findings with file, line, shortcode, severity, category, title, message]

  CodeRabbit Comments (inline):
  [paste all CodeRabbit inline review comments]

  CodeRabbit Duplicate Comments:
  [paste entries from "Duplicate comments" section — tag each as DUPLICATE]

  CodeRabbit Outside Diff Range Comments:
  [paste entries from "⚠️ Outside diff range comments" section — tag each as OUTSIDE-DIFF]

  Human Reviewer Comments:
  [paste all human reviewer comments]

Review scope: Only the files changed in this PR.

Your job:
  1. Review the CODE for issues in your domain
  2. EVALUATE each existing PR comment in your domain:
     - AGREE: The comment is valid and should be addressed
     - CONTEST: The comment is incorrect or unnecessary (explain why)
     - ALREADY FIXED: The comment was addressed in a subsequent commit
  3. Report NEW findings not covered by existing comments

For EACH finding (new or evaluated), provide:
  - Severity: CRITICAL / HIGH / MEDIUM / LOW
  - File and line
  - Problem description with code context
  - Flow analysis: trace execution path, identify affected consumers
  - Impact analysis (four lenses):
    - UX: How does this affect end users?
    - Task focus: Is this within PR scope?
    - Project focus: MVP-critical or gold-plating?
    - Engineering quality: Maintainability, testability, reliability impact
  - Recommendation with tradeoffs

Cross-cutting analysis (MANDATORY for all agents):
  1. What would break in production under load with this code?
  2. What's MISSING that should be here? (not just what's wrong)
  3. Does this code trace back to a spec requirement? Flag orphan code without spec backing
  4. How would a new developer understand this code 6 months from now?
  5. Search the codebase for how similar problems were solved — flag inconsistencies with existing patterns
```

### Agents (always dispatch ALL)

| # | Agent | Focus | Ring Droid |
|---|-------|-------|------------|
| 1 | Code quality | Architecture, SOLID, DRY, maintainability, resilience, resource lifecycle, concurrency, performance, configuration, cognitive complexity, error handling, domain purity | `ring-default-code-reviewer` |
| 2 | Business logic | Domain correctness, edge cases, spec traceability, data integrity, backward compatibility, API semantics | `ring-default-business-logic-reviewer` |
| 3 | Security | Vulnerabilities, OWASP, input validation, data privacy, error response leakage, rate limiting, auth propagation | `ring-default-security-reviewer` |
| 4 | Test quality | Coverage gaps, error scenarios, flaky patterns, test effectiveness, false positive risk, test coupling, spec traceability | `ring-default-ring-test-reviewer` |
| 5 | Nil/null safety | Nil pointer risks, unsafe dereferences, resource cleanup nil checks, channel/map/slice safety | `ring-default-ring-nil-safety-reviewer` |
| 6 | Ripple effects | Cross-file impacts, backward compatibility, configuration drift, migration paths, shared state, event contracts | `ring-default-ring-consequences-reviewer` |
| 7 | Dead code | Orphaned code, zombie test infrastructure, stale feature flags, deprecated paths | `ring-default-ring-dead-code-reviewer` |

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
```

All agents MUST be dispatched in a SINGLE message with parallel Task calls.

### Special Instructions per Agent

Include per-droid quality checklists — see AGENTS.md Protocol: Per-Droid Quality Checklists.

---

## Phase 4: Consolidation

After ALL agents return:

1. **Merge** all new findings into a single list
2. **Merge** all comment evaluations into a single list
3. **Deduplicate** — if multiple agents flag the same issue, keep one entry noting which agents agreed
4. **Cross-reference** — for existing comments, note agreement/disagreement between agents and the original source
5. **Classify false positives** — for Codacy/DeepSource findings that agents contest as misconfigured rules (e.g., ES5 rules in modern project, framework-specific rules for wrong framework), separate into "False Positive — Misconfigured Rule" category
6. **Sort** by severity: CRITICAL > HIGH > MEDIUM > LOW
7. **Assign** sequential IDs (F1, F2, F3...)

### Source Attribution

Each finding MUST include its source(s):

| Source Type | Label |
|-------------|-------|
| New finding from agent review | `[Agent: <agent-name>]` |
| CI check failure | `[CI: <check-name>]` |
| Codacy finding validated by agent | `[Codacy + Agent: <agent-name>]` |
| DeepSource finding validated by agent | `[DeepSource + Agent: <agent-name>]` |
| CodeRabbit comment validated by agent | `[CodeRabbit + Agent: <agent-name>]` |
| CodeRabbit duplicate comment | `[CodeRabbit — DUPLICATE + Agent: <agent-name>]` |
| CodeRabbit outside-diff comment | `[CodeRabbit — OUTSIDE PR DIFF + Agent: <agent-name>]` |
| Human review comment validated by agent | `[Reviewer: <username> + Agent: <agent-name>]` |
| Existing comment contested by agent | `[Contested: <source> vs Agent: <agent-name>]` |

---

## Phase 5: Present Overview

```markdown
## PR Review: #<number> — X findings

### CI Status
- Codacy: <conclusion> (<N> annotations)
- DeepSource: <analyzer statuses>
- Other checks: X passing, Y failing

### False Positives — Misconfigured Rules (Codacy/DeepSource)
| # | Source | Pattern/Title | Count | Reason |
|---|--------|--------------|-------|--------|

### Genuine Findings (validated by agents)
| # | Severity | File | Summary | Source | Agent(s) |
|---|----------|------|---------|--------|----------|

### Contested Comments
| # | Original Source | Summary | Contesting Agent | Reason |
|---|----------------|---------|-----------------|--------|

### Agent Verdicts
| Agent | Evaluated | Agree | Contest | New |
|-------|-----------|-------|---------|-----|

### Summary
- New findings: X | Validated comments: X | Contested: X | False positives: X
```

---

## Phase 6: Finding Presentation and Resolution

Findings are presented ONE AT A TIME, decisions collected for ALL, then fixes applied ALL AT ONCE at the end.

**=== MANDATORY — Progress Tracking (NEVER SKIP) ===**

**BEFORE presenting the first finding, you MUST:**
1. Count the TOTAL number of findings (N) — sum of genuine findings, validated comments, contested comments, and new agent findings
2. Display the total prominently: `"### Total findings to review: N"`
3. This total MUST be visible to the user BEFORE any finding is presented

**For EVERY finding presented, you MUST:**
1. Include `"(X/N)"` progress prefix in the header — this is NOT optional
2. X starts at 1 and increments sequentially
3. N is the total announced above and NEVER changes mid-review
4. If you present a finding WITHOUT "(X/N)" progress prefix in the header, you are violating this rule — STOP and correct it

**The user MUST always know:**
- How many findings exist in total (N)
- Which finding they are currently reviewing (X)
- How many remain (N - X)

### Step 6.1: Present Findings One at a Time (collect decisions only)

Present ALL findings sequentially, one after another, collecting the user's decision for each. Do NOT apply any fix during this phase — only collect decisions.

For EACH finding:

#### Finding Header

`## (X/N) F# — [SEVERITY] | [Source] | [Category]`

Example: `## (1/12) F1 — [HIGH] | Codacy + Agent | Security`
Example: `## (5/12) F5 — [MEDIUM] | DeepSource + Agent | Anti-pattern`
Example: `## (8/12) F8 — [MEDIUM] | CodeRabbit — DUPLICATE + Agent | Error handling`
Example: `## (10/12) F10 — [LOW] | CodeRabbit — OUTSIDE PR DIFF + Agent | Naming`
Example: `## (12/12) F12 — [LOW] | CodeRabbit + Agent | Style`

#### Deep Research Before Presenting (MANDATORY)

Execute deep research before presenting each finding — see AGENTS.md "Common Patterns > Deep Research Before Presenting". All 12 checklist items apply.

#### Deep Technical Analysis

**Problem description:**
- Clear description with code snippet
- For validated comments: show original comment and agent's validation
- For contested comments: show both the original and agent's contestation

**Impact analysis (four lenses):**
- **UX:** End-user impact — errors, data loss, broken workflows
- **Task focus:** Within PR scope or tangential?
- **Project focus:** MVP-critical or gold-plating?
- **Engineering quality:** Maintainability, testability, reliability, consistency

#### Proposed Solutions

Present 2-3 options using the format from AGENTS.md "Common Patterns > Finding Option Format".

#### Collect Decision

**AskUser `[topic]` format:** Format: `F#-Category`.
Example: `[topic] F8-DeadCode`.

Use `AskUser`. **BLOCKING** — do not advance until decided.
**Every AskUser MUST include these options:**
- One option per proposed solution (Option A, Option B, Option C, etc.)
- Skip — no action
- Tell me more — if selected, STOP and answer immediately (do NOT continue to next finding)

**IMMEDIATE RESPONSE RULE** — see AGENTS.md "Finding Presentation" item 9. If the user
selects "Tell me more" or responds with free text: STOP, research and answer RIGHT NOW.
**NEVER defer to the end of the findings loop.**

Record: finding ID, source(s), decision (fix/skip/defer), chosen option. Do NOT apply any fix yet.

**Same-nature grouping:** applied automatically per AGENTS.md "Finding Presentation" item 3.

---

## Phase 7: Recommend Rule Configuration (Codacy/DeepSource)

If false positives were identified, present configuration recommendations:

### For Codacy false positives:

```markdown
**Via .codacy.yml:**
  exclude_paths:
    - "<path>"

**Via Codacy UI:** app.codacy.com > Repository > Code Patterns > disable pattern
```

### For DeepSource false positives:

```markdown
**Via .deepsource.toml:**
  exclude_patterns = ["<path>"]

**Via inline suppression:** // skipcq: <issue-code>
**Via DeepSource Dashboard:** app.deepsource.com > suppress issue
```

Ask the user whether to apply config changes. If approved, edit the config files.

---

## Phase 8: Apply All Approved Fixes with TDD Cycle

**IMPORTANT:** This phase runs ONCE, after ALL findings have been presented and ALL decisions collected in Phase 6. No fix is applied during Phase 6.

### Step 8.1: Pre-Apply Summary

```markdown
## Fixes to Apply (X of Y findings)

| # | Finding | Source | Decision | Files |
|---|---------|--------|----------|-------|
| F1 | [summary] | [Codacy + Agent] | Fix (Option A) | file1.go |
| F3 | [summary] | [Agent: Security] | Fix (Option B) | auth.go |

### Skipped (Z findings)
| # | Finding | Source | Reason |
|---|---------|--------|--------|

### Deferred (W findings)
| # | Finding | Source | Destination |
|---|---------|--------|-------------|
```

### Step 8.2: Classify and Apply Each Fix

For each approved fix, classify its complexity and apply accordingly — see AGENTS.md
"Common Patterns > Fix Implementation (Complexity-Based Dispatch)".

**Complexity classification (per finding):**

| Complexity | Criteria | Action |
|------------|----------|--------|
| **Simple** | Review agent provided exact fix, single file, localized change, obvious resolution (typo, missing nil guard, import, rename, dead code removal) | Apply directly with Edit tool |
| **Complex** | Multiple files, new logic, architectural impact, new test scenarios, security-sensitive, uncertain resolution | Dispatch ring droid with TDD cycle |
| **Uncertain** | Cannot confidently classify | Treat as complex → dispatch ring droid |

**Simple fix flow:**
1. Apply the fix directly using Edit/MultiEdit tools
2. Run unit tests to verify no regression
3. If tests fail → revert the change and escalate to ring droid dispatch

**Complex fix flow:**
1. Dispatch the stack-appropriate ring droid via `Task` tool with TDD cycle (RED-GREEN-REFACTOR)
2. Documentation fixes use ring-tw-team droids without TDD

**Droid selection (complex fixes only):**
- Go → `ring-dev-team-backend-engineer-golang`
- TypeScript → `ring-dev-team-backend-engineer-typescript`
- React/Next.js → `ring-dev-team-frontend-engineer`
- Tests → `ring-dev-team-qa-analyst`
- Docs → `ring-tw-team-functional-writer`, `ring-tw-team-api-writer`

### Step 8.3: Handle Test Failures (max 3 attempts)

1. **Logic bug** → Return to RED, adjust test/fix
2. **Flaky test** → Re-execute at least 3 times in a clean environment to confirm
   flakiness. Maximum 1 test skipped per fix. Document explicit justification
   (error message, flakiness evidence) and tag with `pending-test-fix`
3. **External dependency** → Pause and wait for restoration

### Step 8.4: Commit Each Fix

After each successful TDD cycle:

1. Stage ONLY the files changed by this fix
2. Commit with descriptive message:
   ```bash
   COMMIT_MSG_FILE=$(mktemp)
   printf 'fix: <concise description>\n\nAddresses review finding F<N> [<source>]' > "$COMMIT_MSG_FILE"
   git commit -F "$COMMIT_MSG_FILE"
   rm -f "$COMMIT_MSG_FILE"
   ```
3. Record `{finding_id} → {commit_sha}` mapping

### Step 8.4.1: Final Lint Check

**After ALL fixes are committed**, run lint once using the resolved command from Step 3.1:
```bash
make lint
```
If lint fails, fix formatting issues, amend the last commit or create a `chore: fix lint` commit.

### Step 8.5: Suppress Won't-Fix Findings (Codacy/DeepSource)

For each **skipped/discarded** finding from Codacy or DeepSource, add inline suppression:

**Codacy findings:**
Codacy has NO inline suppression syntax of its own. It uses the underlying linter's mechanism. You MUST identify which linter Codacy is running (check the Codacy annotation or `.codacy.yml`) and use that linter's suppression:
- **Biome** (JS/TS): `// biome-ignore lint/<category>/<rule>: <reason>` on the line BEFORE the flagged code
- **ESLint** (JS/TS): `// eslint-disable-next-line <rule>` on the line BEFORE
- **golangci-lint** (Go): `//nolint:<linter>` on the same line
- **Pylint** (Python): `# pylint: disable=<rule>` on the same line

**IMPORTANT:** `codacy:ignore` does NOT exist. Never use it.

**DeepSource findings:**
Add `// skipcq: <shortcode>` comment on the line above the flagged code (e.g., `// skipcq: JS-C1003`).

Commit all suppressions together:
```bash
COMMIT_MSG_FILE=$(mktemp)
printf 'chore: suppress won'\''t-fix static analysis findings\n\nCodacy: X findings suppressed (via <linter> inline suppression)\nDeepSource: Y findings suppressed (skipcq)' > "$COMMIT_MSG_FILE"
git commit -F "$COMMIT_MSG_FILE"
rm -f "$COMMIT_MSG_FILE"
```

Record the suppression commit SHA for use in Phase 13.

---

## Phase 9: Coverage Verification and Test Gap Analysis

**IMPORTANT:** This phase runs ONLY ONCE, after ALL fixes from Phase 8 have been applied.

### Step 9.1: Coverage Measurement (Unit Tests)

Measure coverage — see AGENTS.md Protocol: Coverage Measurement.

**NOTE:** Integration test coverage is measured in Phase 11 (before push), not here.

### Step 9.2: Test Gap Analysis

Dispatch a test gap analyzer via `Task` tool. Use `ring-default-ring-test-reviewer` or `ring-dev-team-qa-analyst`.

The agent receives file paths and can navigate the codebase autonomously.

```
Goal: Cross-reference implemented tests with source code to find missing scenarios.

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

HIGH priority gaps are presented as findings for user decision.

---

## Phase 10: Convergence Loop (MANDATORY)

Execute the convergence loop — see AGENTS.md "Common Patterns > Convergence Loop".

**Stage-specific scope for convergence rounds 2+:**
Dispatch the **same agent roster** from Phase 3 (all 7 agents from Step 3.3). Each agent
receives file paths, PR context (description, linked issues, base branch), and project
rules (re-read fresh from disk). Do NOT include the findings ledger in agent prompts —
the orchestrator handles dedup using strict matching (same file + same line range ±5 +
same category).

Include existing PR comments from all sources (reuse data from Phase 1 — do NOT re-fetch
Codacy/DeepSource comments, they only update after push). Include the cross-cutting
analysis instructions (same 5 items from Step 3.3 prompt).

**Failure handling:** If the fresh sub-agent dispatch fails (Task tool error, ring droid
unavailable), treat it as equivalent to "zero new findings" for that round but warn the
user. Do NOT fail the entire review.

When the loop exits, proceed to Phase 11 (integration tests).

---

## Phase 11: Integration Tests (before push)

**Before pushing**, run integration tests. These are slow and expensive, so they
run ONCE here — not during the fix/convergence cycle.

```bash
make test-integration        # Optional target — SKIP if missing
```

| Test Type | Command | If target exists | If target missing |
|-----------|---------|-----------------|-------------------|
| Integration | `make test-integration` | **HARD BLOCK** if fails | SKIP |

**If integration tests fail:**
1. Present the failure output (first 30 lines)
2. Ask via `AskUser`: "Integration tests are failing. What should I do?"
   - Fix the issue (dispatch ring droid)
   - Skip and push anyway (user will handle in CI)

---

## Phase 12: Push Commits

**HARD BLOCK:** Ask the user before pushing:

```
Fixes have been committed locally. Ready to push?
- Push now
- Skip (I'll push manually)
```

If approved:
```bash
git push
```

This triggers Codacy/DeepSource reanalysis automatically.

---

## Phase 13: Respond to ALL PR Comments (MANDATORY)

**HARD BLOCK:** This phase is MANDATORY regardless of whether any fixes were applied. Every existing PR comment thread MUST receive a reply.

### Step 13.1: Response Rules (uniform for ALL sources)

**IMPORTANT:** Use the `{finding_id} → {commit_sha}` mapping from Phase 8.

**Case 1 — Fix applied (ANY source: Codacy, DeepSource, CodeRabbit, human):**
```
Fixed in <commit_sha>.

<brief description of what was done>
```

**Case 2 — Won't fix (ANY source: Codacy, DeepSource, CodeRabbit, human):**
```
Won't fix: <concrete reason why this doesn't apply>
```

**Case 2a — Won't fix + suppression (Codacy/DeepSource only):**
```
Won't fix: <reason>. Suppressed in <suppression_commit_sha>.
```

**Case 3 — Deferred:**
```
Deferred to <destination>: <brief reason>
```

**Case 4 — Contested:**
```
Contested: <agent's reasoning for why the comment is incorrect>
```

**Case 5 — Already fixed:**
```
Already addressed in a previous commit.
```

**Case 6 — Question/clarification (human reviewers):**
```
<direct answer referencing specific code/files>
```

### Step 13.2: Refresh Thread Map

Re-fetch the thread map from Step 1.3.1 to get the latest state (threads may have been resolved by pushes or other activity):

```bash
gh api graphql -f query='
  query {
    repository(owner: "<owner>", name: "<repo>") {
      pullRequest(number: <number>) {
        reviewThreads(first: 100) {
          nodes {
            id
            isResolved
            path
            line
            comments(first: 10) {
              nodes {
                databaseId
                author { login }
                body
              }
            }
          }
        }
      }
    }
  }
'
```

Update the thread map with fresh `isResolved` status. Skip threads already resolved.

### Step 13.3: Reply AND Resolve Each Thread (atomically)

**CRITICAL:** For EACH thread, reply and resolve in the SAME step. Never batch "all replies first, then all resolves". The pattern is: reply → resolve → confirm → next thread.

**Deduplication check (MANDATORY):** Before posting a reply to any thread, check if a reply
from the agent already exists in that thread (e.g., from a previous interrupted run). If a
reply with similar content already exists, skip posting and proceed directly to resolve.
This prevents duplicate replies when re-executing after a crash between reply and resolve.

**For each unresolved thread, use the correct reply method based on the source:**

#### Case A: Native app threads (DeepSource `deepsource-io`, Codacy `codacy-production`)

The REST API returns 404 for these threads. You MUST use GraphQL for both reply and resolve.

**1. Reply via GraphQL:**
```bash
gh api graphql -f query='
  mutation {
    addPullRequestReviewThreadReply(input: {
      pullRequestReviewThreadId: "<thread_node_id>",
      body: "<reply>"
    }) { comment { id } }
  }
'
```

**2. Resolve via GraphQL:**
```bash
gh api graphql -f query='
  mutation {
    resolveReviewThread(input: {threadId: "<thread_node_id>"}) {
      thread { isResolved }
    }
  }
'
```

**3. Confirm** `isResolved: true` in the response.

**Example — DeepSource native thread:**
```bash
# Thread from deepsource-io at backend/internal/handler/client.go:42
# thread_node_id = "PRRT_kwDORrzDks579CXg"

# Reply
gh api graphql -f query='
  mutation {
    addPullRequestReviewThreadReply(input: {
      pullRequestReviewThreadId: "PRRT_kwDORrzDks579CXg",
      body: "Fixed in abc1234. Replaced exported function returning unexported type."
    }) { comment { id } }
  }
'

# Resolve
gh api graphql -f query='
  mutation {
    resolveReviewThread(input: {threadId: "PRRT_kwDORrzDks579CXg"}) {
      thread { isResolved }
    }
  }
'
```

**Example — Codacy native thread:**
```bash
# Thread from codacy-production at frontend/src/app/page.tsx:15
# thread_node_id = "PRRT_kwDORrzDks57_ABC"

# Reply
gh api graphql -f query='
  mutation {
    addPullRequestReviewThreadReply(input: {
      pullRequestReviewThreadId: "PRRT_kwDORrzDks57_ABC",
      body: "Won'\''t fix: this is a convention in the project. Suppressed via biome-ignore."
    }) { comment { id } }
  }
'

# Resolve
gh api graphql -f query='
  mutation {
    resolveReviewThread(input: {threadId: "PRRT_kwDORrzDks57_ABC"}) {
      thread { isResolved }
    }
  }
'
```

#### Case B: Workflow and bot threads (`github-actions[bot]`, `coderabbitai[bot]`, humans)

Use REST API with `in_reply_to` for the reply, then GraphQL for resolve.

**1. Reply via REST:**
```bash
gh api repos/{owner}/{repo}/pulls/{number}/comments \
  --method POST -f body="<reply>" -F in_reply_to=<first_comment_database_id>
```

**2. Resolve via GraphQL:**
```bash
gh api graphql -f query='
  mutation {
    resolveReviewThread(input: {threadId: "<thread_node_id>"}) {
      thread { isResolved }
    }
  }
'
```

**3. Confirm** `isResolved: true` in the response.

**If REST returns 404** (can happen for some bot types), fall back to Case A (GraphQL for both reply and resolve).

#### Case C: General PR comments (non-inline)

```bash
gh pr comment <PR_NUMBER_OR_URL> --body "<reply>"
```

These don't have threads and cannot be resolved.

### Step 13.4: Verify Zero Unresolved Remain

After all threads are processed, re-run the query from Step 13.2 and confirm ALL threads have `isResolved: true`. If any remain unresolved, reply and resolve them now. Do NOT proceed until zero unresolved threads remain.

### Step 13.5: Hide Fully-Resolved Reviews

After all threads are resolved, minimize fully-resolved review sections:

```bash
gh api graphql -f query='
  mutation {
    minimizeComment(input: {subjectId: "<review_node_id>", classifier: RESOLVED}) {
      minimizedComment { isMinimized }
    }
  }
'
```

### Step 13.6: Reply Summary

**HARD BLOCK:** The Status column MUST show "Resolved" for every row. If any row shows "Replied" instead of "Resolved", go back and resolve it.

```markdown
### PR Comment Replies Posted
| # | Thread | Source | Reply | Commit | Status |
|---|--------|--------|-------|--------|--------|
| 1 | file.go:42 | Codacy | Fixed | abc1234 | Resolved |
| 2 | file.go:88 | DeepSource | Won't fix: convention. Suppressed | def5678 | Resolved |
| 3 | file.go:15 | CodeRabbit | Fixed | ghi9012 | Resolved |
| 4 | file.go:22 | @reviewer | Won't fix: out of scope | — | Resolved |
| 5 | general | @reviewer | [answer] | — | Resolved |
```

---

## Phase 14: Final Summary

```markdown
## PR Review Summary: #<number> — <title>

### Sources Analyzed
- CI checks: X failing (Y fixed, Z remaining)
- Codacy: X issues (Y fixed, Z suppressed)
- DeepSource: X issues (Y fixed, Z suppressed)
- CodeRabbit: X comments (Y validated, Z contested)
- Human reviewers: X comments (Y validated, Z contested)
- New agent findings: X

### Convergence
- Rounds: X of 5
- Status: CONVERGED / HARD LIMIT REACHED

### Fixed (X findings)
| # | Source | File(s) | Commit |
|---|--------|---------|--------|

### Won't Fix — Suppressed (X findings)
| # | Source | File(s) | Reason | Suppression Commit |
|---|--------|---------|--------|--------------------|

### Skipped (X findings)
| # | Source | File(s) | Reason |
|---|--------|---------|--------|

### Deferred (X findings)
| # | Source | File(s) | Destination |
|---|--------|---------|-------------|

### CI Status
- Codacy: <conclusion> (<N> annotations)
- DeepSource: <analyzer statuses>
- Other: X passing, Y failing

### Verification
- Lint: PASS
- Unit tests: PASS (X tests) — Coverage: XX.X% (threshold: 85%)
- Integration tests: PASS/SKIPPED — Coverage: XX.X% (threshold: 70%) / SKIP

### Configuration Changes
| # | Tool | Change | Method |
|---|------|--------|--------|

### PR Readiness
- [ ] All CRITICAL/HIGH findings resolved (including CI failures)
- [ ] All CI checks passing (verified after fixes pushed)
- [ ] Codacy/DeepSource findings resolved or suppressed
- [ ] Changes align with PR description and linked issues
- [ ] Test coverage adequate

**Verdict:** READY FOR MERGE / NEEDS CHANGES
```

---

## Completion Checklist (MANDATORY — verify before ending)

- [ ] Total findings count (N) was announced before the first finding
- [ ] All findings presented with "(X/N)" progress prefix in EVERY header
- [ ] All decisions collected (fix / skip / defer for every finding)
- [ ] All approved fixes committed with TDD cycle (applied after all decisions collected)
- [ ] Won't-fix Codacy/DeepSource findings suppressed inline
- [ ] Push completed or explicitly skipped
- [ ] ALL comment threads replied AND resolved atomically (reply → resolve → next, never batch separately)
- [ ] Verification query confirms zero `isResolved: false` threads remain
- [ ] Fully-resolved reviews hidden via `minimizeComment`
- [ ] Reply summary presented — every row MUST show "Resolved" status
- [ ] Final summary with verdict presented

**STOP CONDITION:** You may ONLY end the review session after ALL items are checked.

---

## Rules

- Fetch comments from ALL sources before starting: Codacy (`**Codacy**` prefix from `github-actions[bot]`), DeepSource (`**DeepSource**` prefix from `github-actions[bot]`), CodeRabbit (`coderabbitai[bot]`), and human reviewers
- Agents MUST evaluate ALL existing comments — validate, contest, or mark as already fixed
- Every finding must include source attribution
- Only review files changed in the PR
- ALWAYS announce total findings count (N) before presenting the first finding: `"### Total findings to review: N"`
- Present findings ONE AT A TIME in severity order, ALWAYS showing "(X/N)" progress prefix in EVERY finding header
- Collect ALL decisions first (Phase 6), then apply ALL approved fixes at once (Phase 8)
- Coverage verification and convergence loop run ONLY after all fixes are applied
- No changes without user approval
- BEFORE presenting each finding: deep research is MANDATORY — project patterns, architectural decisions, existing codebase, task focus, user/consumer use cases, UX impact, API best practices, engineering best practices, language-specific idioms. Option A must be the correct approach backed by research evidence, regardless of effort
- If the user selects "Tell me more" or responds with free text: STOP, research and answer thoroughly RIGHT NOW — do NOT defer to the fix phase or continue to the next finding. NEVER batch responses.
- Ring droids are required for complex fixes and for review dispatch — do not proceed without them
- Simple fixes (obvious resolution provided by review agents) are applied directly; complex or uncertain fixes use ring droids with TDD cycle (RED-GREEN-REFACTOR)
- Each fix gets a separate commit regardless of whether it was applied directly or via ring droid
- For won't-fix Codacy findings: use the underlying linter's suppression syntax (e.g., `biome-ignore` for Biome, `eslint-disable-next-line` for ESLint, `//nolint` for Go). `codacy:ignore` does NOT exist.
- For won't-fix DeepSource findings: add `// skipcq: <shortcode>` inline and commit
- Response to ALL comments is uniform: commit SHA for fixes, concrete reason for won't-fix
- Do NOT merge the PR — only review and apply fixes
- Push triggers Codacy/DeepSource reanalysis automatically
- The agent NEVER decides whether a finding should be fixed or skipped — the USER always decides
- ALL findings (CRITICAL, HIGH, MEDIUM, and LOW) MUST be presented to the user for decision
- The agent may recommend an option, but MUST wait for user approval via AskUser before proceeding
- Do NOT auto-skip, auto-dismiss, or auto-resolve any finding regardless of severity
### Dry-Run Mode
If the user requests a dry-run (e.g., "dry-run pr-check", "preview PR review"):
- Fetch ALL PR data normally (Phase 1)
- Dispatch ALL review agents (Phase 3) and consolidate (Phase 4)
- Present ALL findings in Phase 6 (interactive resolution)
- **Do NOT apply fixes** — skip Phase 8 (TDD cycle)
- **Do NOT push anything** — skip Phase 12
- **Do NOT respond to PR comments** — skip Phase 13
- **Do NOT run convergence loop** — one pass for preview
- Present results as informational with estimated fix effort

<!-- INLINE-PROTOCOLS:START -->
## Shared Protocols (from AGENTS.md)

The following protocols are referenced by this skill. They are
extracted from the Optimus AGENTS.md to make this plugin self-contained.

### Convergence Loop (Full Roster Model)
Applies to: plan, check, pr-check, coderabbit-review, deep-review, deep-doc-review

The convergence loop eliminates false convergence by dispatching the **same agent roster**
as round 1 in every subsequent round:
- **Round 1:** Orchestrator dispatches all specialist agents in parallel (with full session context)
- **Rounds 2-5:** The **same agent roster** as round 1 is dispatched in parallel via `Task`
  tool, each with zero prior context. Each agent reads all files fresh from disk.
- **Round 2 is MANDATORY** — the "zero new findings" stop condition only applies from round 3 onward
- **Sub-agents do NOT receive the findings ledger.** Dedup is performed entirely by the
  orchestrator after agents return, using **strict matching**: same file + same line range
  (±5 lines) + same category. "Description similarity" is NOT sufficient for dedup — the
  file, location, and category must all match.
- Stop only when: zero new findings (round 3+), round 5 reached, or user explicitly stops
- LOW severity findings are NOT a reason to stop — ALL findings are presented to the user

**Why full roster, not a single agent:** A single generalist agent structurally cannot
replicate the coverage of 8-10 domain specialists. The security-reviewer catches injection
risks a code-reviewer won't. The nil-safety-reviewer catches empty guards a QA analyst won't.
Dispatching a single agent in rounds 2+ creates false convergence — the agent declares
"zero new findings" because it lacks the domain depth, not because the code is clean.


### Deep Research Before Presenting (MANDATORY for cycle review skills)
Applies to: plan, check, pr-check, coderabbit-review

**BEFORE presenting any finding to the user, the agent MUST research it deeply.** This
research is done SILENTLY — do not show the research process. Present only the conclusions.

**Research checklist (ALL items, every finding):**

1. **Project patterns:** Read the affected file(s) fully. Check how similar cases are handled
   elsewhere in the codebase. Identify existing conventions the finding might violate or follow.
2. **Architectural decisions:** Review project rules (AGENTS.md, PROJECT_RULES.md, etc.) and
   architecture docs (TRD, ADRs). Understand WHY the project is structured this way before
   suggesting changes.
3. **Existing codebase:** Search for precedent. If the codebase already does the same thing
   in 10 other places without issue, that context changes the finding's weight.
4. **Current task focus:** Is this finding within the scope of the task being worked on?
   Tangential findings should be flagged as such (not dismissed, but contextualized).
5. **User/consumer use cases:** Who consumes this code — end users, other services, internal
   modules? How does the finding affect them? Trace the impact to real user scenarios.
6. **UX impact:** For user-facing changes, evaluate usability, accessibility, error messaging,
   and workflows. Would the user notice? Would it block their work?
7. **API best practices:** For API changes, check REST conventions, error handling patterns,
   idempotency, status codes, pagination, versioning, and backward compatibility.
8. **Engineering best practices:** SOLID principles, DRY, separation of concerns, error
   handling, resilience patterns, observability, testability.
9. **Language-specific best practices:** Use `WebSearch` to research idioms and conventions
   for the specific language (Go, TypeScript, Python, etc.). Check official style guides,
   common linter rules, and community-accepted patterns.
10. **Correctness over convenience:** Always recommend the correct approach, regardless of
    effort. The easy option may be presented as an alternative, but Option A must be what
    the agent believes is right based on all the research above.
11. **Production resilience:** Would this code survive production conditions? Consider:
    timeouts on external calls, retry with backoff, circuit breakers, graceful degradation,
    resource cleanup (connections, handles, goroutines), graceful shutdown, and behavior
    under load (N+1 queries, unbounded queries, connection pool exhaustion).
12. **Data integrity and privacy:** Are transaction boundaries correct? Could partial writes
    occur? Is PII properly handled (not logged, masked in responses)? LGPD/GDPR compliance?

**After research, form the recommendation:** Option A MUST be the approach the agent
believes is correct based on the research. It must be backed by evidence (project patterns,
best practice references, official documentation), not just a generic suggestion.


### Finding Option Format (MANDATORY for cycle review skills)

Every finding must present 2-3 options with this structure:

```
**Option A: [name] (RECOMMENDED)**
[Concrete steps — what to do, which files to change, what code to write]
- Why recommended: [reference to research — best practice, project pattern, official docs]
- Impact: [UX / Task focus / Project focus / Engineering quality]
- Effort: [low / medium / high / very high]
- Estimated time: [< 5 min / 5-15 min / 15-60 min / 1-4h / > 4h]

**Option B: [name]**
[Alternative approach]
- Impact: [UX / Task focus / Project focus / Engineering quality]
- Effort: [low / medium / high / very high]
- Estimated time: [< 5 min / 5-15 min / 15-60 min / 1-4h / > 4h]
```

**Effort scale:**
- **Low:** Localized change, single file, no tests needed
- **Medium:** Multiple files, straightforward, may need test updates
- **High:** Significant refactoring, new tests, multiple modules affected
- **Very high:** Architectural change, many files, extensive testing, risk of regressions


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
   **AskUser `[topic]` format:** Format: `F#-Category`.
   Example: `[topic] F8-DeadCode`.
9. **IMMEDIATE RESPONSE RULE — If the user selects "Tell me more" OR responds with free text
   (a question, disagreement, or request for clarification) instead of a decision:**
   **STOP IMMEDIATELY.** Do NOT continue to the next finding. Do NOT batch the response.
   Research the user's concern RIGHT NOW using `WebSearch`, codebase analysis, or both.
   Provide a thorough answer with evidence (links, code references, best practice citations).
   Only AFTER the user is satisfied, re-present the options and ask for their decision again.
   This may go back and forth multiple times — that is expected and correct behavior.
   **NEVER defer the response to the end of the findings loop.**
10. After ALL N decisions collected: apply ALL approved fixes (see below)
11. Run verification (see Verification Timing below)
12. Present final summary


### Fix Implementation (Complexity-Based Dispatch)

Fixes are classified by complexity. **Simple fixes** are applied directly by the
orchestrator. **Complex fixes** (or fixes whose complexity cannot be determined) are
delegated to specialist ring droids.

#### Complexity Classification

For each approved fix, assess complexity BEFORE applying:

**Simple fix (apply directly):**
- The review agent already provided the exact code change needed
- Single file, localized change (few lines)
- Obvious resolution: typo, missing error check, wrong variable name, missing nil guard,
  import fix, formatting, adding a log line, renaming, removing dead code
- No new logic, no architectural impact, no new test scenarios needed

**Complex fix (dispatch ring droid):**
- Multiple files affected
- Requires understanding broader codebase context or architectural decisions
- New functionality, significant refactoring, or new integration points
- Requires new test scenarios (not just updating existing ones)
- Security-sensitive changes (auth, crypto, input validation)
- Database schema, API contract, or config changes
- The orchestrator is unsure how to fix it

**When in doubt → dispatch ring droid.** If you cannot confidently classify a fix as
simple, treat it as complex.

#### Direct Fix (simple findings)

The orchestrator applies the fix directly using Edit/MultiEdit tools. After applying:
1. Run unit tests to verify no regression
2. If tests fail, revert and escalate to ring droid dispatch

#### Ring Droid Dispatch (complex findings)

**Code fixes** → dispatch ring backend/frontend/QA droids with **TDD cycle** (RED-GREEN-REFACTOR):
- `ring-dev-team-backend-engineer-golang` (Go), `ring-dev-team-backend-engineer-typescript` (TS),
  `ring-dev-team-frontend-engineer` (React/Next.js), `ring-dev-team-qa-analyst` (tests)

**Documentation fixes** → dispatch ring documentation droids **without TDD** (no tests for docs):
- `ring-tw-team-functional-writer` (guides), `ring-tw-team-api-writer` (API docs),
  `ring-tw-team-docs-reviewer` (quality fixes)

**Ring droids are REQUIRED for complex fixes** — there is no alternative dispatch mechanism. If the
required droids are not installed and a complex fix is needed, the skill MUST stop and
inform the user which droids need to be installed.


### Protocol: Coverage Measurement

**Referenced by:** check, pr-check, coderabbit-review, deep-review, build

Measure test coverage using Makefile targets with stack-specific fallbacks.

**Unit coverage command resolution order:**
1. `make test-coverage` (if Makefile target exists)
2. Stack-specific fallback:
   - Go: `go test -coverprofile=coverage-unit.out ./... && go tool cover -func=coverage-unit.out`
   - Node: `npm test -- --coverage`
   - Python: `pytest --cov=. --cov-report=term`

If no unit coverage command is available, mark as **SKIP** — do not fail the verification.

**Integration coverage command resolution order:**
1. `make test-integration-coverage` (if Makefile target exists)
2. Stack-specific fallback:
   - Go: `go test -tags=integration -coverprofile=coverage-integration.out ./... && go tool cover -func=coverage-integration.out`
   - Node: `npm run test:integration -- --coverage`
   - Python: `pytest -m integration --cov=. --cov-report=term`

If no integration coverage command is available, mark as **SKIP** — do not fail the verification.

**Thresholds:**

| Test Type | Threshold | Verdict if Below |
|-----------|-----------|-----------------|
| Unit tests | 85% | NEEDS_FIX / HIGH finding |
| Integration tests | 70% | NEEDS_FIX / HIGH finding |

**Coverage gap analysis:** Parse the coverage output to identify untested functions/methods
(0% coverage). Flag business-logic functions with 0% as HIGH, infrastructure/generated
code with 0% as SKIP.

Skills reference this as: "Measure coverage — see AGENTS.md Protocol: Coverage Measurement."


### Protocol: GitHub CLI Check (HARD BLOCK)

**Referenced by:** all stage agents (1-4), tasks, batch

```bash
gh auth status 2>/dev/null
```

If this command fails (exit code != 0), **STOP** immediately:
```
GitHub CLI (gh) is not authenticated. Run `gh auth login` to authenticate before proceeding.
```


### Protocol: PR Title Validation

**Referenced by:** stages 2-4

Check if a PR exists for the current branch:
```bash
gh pr view --json number,title --jq '{number, title}' 2>/dev/null
```

If a PR exists, validate its title follows **Conventional Commits 1.0.0**:
- Regex: `^(feat|fix|refactor|chore|docs|test|build|ci|style|perf)(\([a-zA-Z0-9_\-]+\))?!?: .+$`
- Cross-check the type against the task's **Tipo** column (Feature→`feat`, Fix→`fix`, Refactor→`refactor`, Chore→`chore`, Docs→`docs`, Test→`test`)
- **If title is invalid:** warn via `AskUser`: "PR #N title `<current>` does not follow Conventional Commits. Suggested: `<corrected>`. Fix now with `gh pr edit <number> --title \"<corrected>\"`?"
- **If title is valid:** proceed silently
- If no PR exists, skip.

Skills reference this as: "Validate PR title — see AGENTS.md Protocol: PR Title Validation."


### Protocol: Per-Droid Quality Checklists

**Referenced by:** check, pr-check, deep-review, coderabbit-review, plan, build

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


### Protocol: Ring Droid Requirement Check

**Referenced by:** check, pr-check, deep-doc-review, coderabbit-review, plan, build

Before dispatching ring droids, verify the required droids are available. If any required
droid is not installed, **STOP** and list missing droids.

**Core review droids** (required by check, pr-check, deep-review, coderabbit-review):
- `ring-default-code-reviewer`
- `ring-default-business-logic-reviewer`
- `ring-default-security-reviewer`
- `ring-default-ring-test-reviewer`

**Extended review droids** (required by check, pr-check, deep-review, coderabbit-review):
- `ring-default-ring-nil-safety-reviewer`
- `ring-default-ring-consequences-reviewer`
- `ring-default-ring-dead-code-reviewer`

**QA droids** (required by check, deep-review, build):
- `ring-dev-team-qa-analyst`

**Documentation droids** (required by deep-doc-review):
- `ring-tw-team-docs-reviewer`
- `ring-default-business-logic-reviewer`
- `ring-default-code-reviewer`

**Implementation droids** (required by build):
- `ring-dev-team-backend-engineer-golang` (Go)
- `ring-dev-team-backend-engineer-typescript` (TypeScript)
- `ring-dev-team-frontend-engineer` (React/Next.js)

**Spec validation droids** (required by plan):
- `ring-default-business-logic-reviewer`
- `ring-default-security-reviewer`
- `ring-dev-team-qa-analyst`
- `ring-default-code-reviewer`

Skills reference this as: "Verify ring droids — see AGENTS.md Protocol: Ring Droid Requirement Check."


<!-- INLINE-PROTOCOLS:END -->
