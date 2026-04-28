---
name: optimus-pr-check
description: "Standalone PR review orchestrator. Fetches PR metadata, collects ALL review comments (Codacy, DeepSource, CodeRabbit, human reviewers), dispatches parallel agents to evaluate code and comments, presents findings interactively, applies fixes with TDD cycle and separate commits per finding, responds to every comment thread with commit reference or justification, and adds inline suppression tags for Codacy/DeepSource when a finding won't be fixed."
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
      8. Coverage verification and (optional) convergence loop
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
      - optimus-review
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
    - Convergence loop run, skipped, or stopped (status recorded)
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

### Step 1.0: Resolve Paths and Git Scope

Execute AGENTS.md Protocol: Resolve Tasks Git Scope. This obtains `TASKS_DIR`,
`TASKS_FILE`, `TASKS_GIT_SCOPE`, `TASKS_GIT_REL`, and the `tasks_git` helper. The
TaskSpec lookups later in this skill (e.g., Step 1.1 PR-creation, Phase 4 attribution)
depend on `TASKS_DIR` being resolved.

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
- **Create PR** — create a PR against the default branch with a Conventional Commits title derived from the task's Tipo and title (same logic as review Phase 13)
- **Provide URL** — I have a PR URL to use
- **Cancel** — stop the review

If the user chooses **Create PR**:
1. Generate PR title from task Tipo + ID + title (e.g., `feat(T-003): add user registration API`)
2. Generate PR body from Ring source (read via `TaskSpec` column in optimus-tasks.md)
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

### Step 1.2.2: Cross-Check PR Branch Against Current Branch

**Why:** When the user invokes `/optimus-pr-check <num>` with an explicit PR number,
the PR may belong to a different branch than the one the user is currently on. The
review still works (pr-check operates on the PR's diff, not the current worktree),
but the user may have meant a different PR. A silent mismatch is a recipe for
confusion — fixes get committed to the right branch (because Step 1.4 checks out
the PR), but the user's mental model can be misaligned.

This guard surfaces the mismatch BEFORE proceeding, but only when the PR was given
explicitly. If pr-check inferred the PR from the current branch (Step 1.1), the
branches always match by construction — skip this check.

**Procedure:**

1. If the user did NOT pass an explicit PR number/URL (Step 1.1 inferred it from the
   current branch), SKIP this check.
2. Otherwise, compare `headRefName` (from Step 1.2) with the current branch:
   ```bash
   CURRENT=$(git branch --show-current 2>/dev/null)
   ```
3. If `CURRENT` is non-empty and differs from `headRefName`, present an `AskUser`
   warning:
   ```
   PR #<num> is for branch '<headRefName>' but you are on branch '<CURRENT>'.
   Continue reviewing PR #<num>?
   ```
   Options:
   - **Continue** — proceed with PR #<num> (Step 1.4 will check out the PR's branch)
   - **Switch and continue** — explicitly checkout the PR's branch first, then proceed
   - **Cancel** — stop the review

**BLOCKING:** Do NOT proceed past this step until the user responds.

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

**Partition by `isOutdated`:** Split threads into TWO lists, do NOT discard.

- **`active_threads`** — threads where `isOutdated` is `false`. These reference current
  code and are evaluated by agents in Phase 3 + replied/resolved per verdict in
  Phase 13.
- **`outdated_threads`** — threads where `isOutdated` is `true`. These reference code
  modified in subsequent commits, so agents have nothing to evaluate. **However, they
  are still OPEN on the PR and must be auto-resolved hygienically** (otherwise
  CodeRabbit and other approval gates withhold approval as long as ANY thread —
  active or outdated — remains unresolved). Phase 13 runs a dedicated cleanup step
  (Step 13.0) that posts a brief auto-reply ("outdated — code changed in subsequent
  commits") and resolves each one via GraphQL.

Both lists use the same storage shape (see below). Outdated threads are NOT included
in `findings_total` (Step 1.8) and are NOT dispatched to agents — they are pure
hygiene targets.

Log both counts for the summary: `"Active: N threads, Outdated: M threads (auto-resolved in Phase 13)"`.

For EACH thread (both `active_threads` and `outdated_threads` use the same storage shape; outdated threads still need source classification to choose the right reply API in Step 13.0), classify by the **first comment's author**:

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

#### Step 1.3.1.5: Fetch ALL PR Review Bodies (MANDATORY)

**HARD BLOCK:** CodeRabbit embeds its "Duplicate comments" and "⚠️ Outside diff range comments" sections inside **review bodies** — NOT in review threads (Step 1.3.1) or general comments (Step 1.3.2). A review body is the top-level markdown of a submitted review (`PullRequestReview` in the API), separate from inline review comments.

If you skip this step, both sections are silently lost, and findings CodeRabbit already reported in prior reviews will never be surfaced to the user.

```bash
gh api repos/<owner>/<repo>/pulls/<number>/reviews \
  --jq '[.[] | {id, state, submitted_at, user: .user.login, body}]' \
  > /tmp/pr-reviews.json
```

**Processing rules:**

1. Filter to `user == "coderabbitai[bot]"` with non-empty body.
2. Sort by `submitted_at` descending.
3. For the MOST RECENT review with `state` in `("CHANGES_REQUESTED", "COMMENTED")` and body containing either `♻️ Duplicate comments` OR `⚠️ Outside diff range comments`, apply the parsing algorithm in Step 1.3.3.
4. Store the extracted findings indexed by source review ID (for traceability in Phase 4 attribution).

**Why only the most recent review:** Earlier reviews are superseded — their duplicates either got resolved (don't reappear in latest) or are still unresolved (reappear in latest's "Duplicate comments" section). The latest review is CodeRabbit's current view of all unresolved findings.

**Do NOT** rely on `gh pr view --comments` (Step 1.3.2) to surface these sections. That command includes review bodies in its output but concatenates them unstructured with issue comments, making reliable per-review parsing impossible.

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

**Parse CodeRabbit review body — see AGENTS.md Protocol: Parse CodeRabbit Review Body.**

The shared protocol covers: GraphQL fetch, per-section deterministic algorithm
(duplicate / outside-diff sections), per-finding fix-block extraction (Minimal
fix / Suggested refactor), AI prompt capture, severity mapping, count parity
HARD BLOCK, aggregate cross-validation, outdated-thread partitioning, and
origin tagging rules (`[CodeRabbit]` / `[CodeRabbit — DUPLICATE]` /
`[CodeRabbit — OUTSIDE PR DIFF]`).

**pr-check-specific application:** the parsed findings feed into Step 1.3.4
(by-source summary) and downstream the CodeRabbit-as-is path that allows
direct application of `[Minimal fix]` / `[Suggested refactor]` blocks for
nitpick-level findings without TDD. This as-is path is intentional for
pr-check — coderabbit-review takes the TDD path for the same sources. See
the relationship note in coderabbit-review/SKILL.md Phase 4.

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
  - Outdated (auto-resolved in Step 13.0): X threads
  Total: X threads, Y unresolved (Z outdated → auto-resolved in Phase 13)
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

**Do NOT rationalize away failing checks.** Anti-rationalization (excuses the agent MUST NOT use):
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

### Step 1.8: Findings count gate + mode selection (HARD BLOCK)

Compute the total findings count from the data already collected in Phase 1:

```
findings_total =
    (unresolved threads in active_threads, from Step 1.3.1; outdated_threads are excluded — they go through Step 13.0 hygiene, not the verdict path)
  + (CodeRabbit duplicate findings, from Step 1.3.1.5)
  + (CodeRabbit outside-diff findings, from Step 1.3.1.5)
  + (failing CI checks, from Step 1.5)
```

Present the count to the user and let them choose what to do via `AskUser`. The
options shown depend on whether any findings were collected. Store the user's
choice as `REVIEW_MODE` for downstream phases; valid values are
`findings` | `diff` | `none`.

**If `findings_total == 0`:**

Render this exact framing in the AskUser preamble:

```
No findings to evaluate on this PR.

pr-check collected:
  - 0 review threads (Codacy / DeepSource / CodeRabbit / human)
  - 0 CodeRabbit duplicate / outside-diff findings
  - 0 failing CI checks

Choose how to proceed:
```

AskUser options (no default):
- `Review entire PR diff` — fresh review of the changed files (Job 1 + Job 3
  prompt; runs Phases 2-13 with `REVIEW_MODE=diff`). Use this when you want
  agent-driven code review on the PR even though no bots/humans commented yet.
- `Do nothing` — exit immediately without dispatching agents (`REVIEW_MODE=none`).

If the user selects `Do nothing`, **STOP** — skip Phases 2-13 and render the
Phase 14 summary with `findings_total: 0` and `mode: none`.

**If `findings_total > 0`:**

Render this exact framing in the AskUser preamble (substitute the actual breakdown):

```
Found N findings on this PR:
  - X review threads (Codacy: a, DeepSource: b, CodeRabbit: c, human: d)
  - Y CodeRabbit duplicate / outside-diff findings
  - Z failing CI checks

NEW (this release): pr-check now defaults to evaluating existing findings
only. If you previously relied on automatic fresh review of the diff, choose
"Review entire PR diff instead".

Choose how to proceed:
```

AskUser options (default = first):
- `Review N findings (recommended)` — current pr-check behaviour: agents evaluate
  each finding (`REVIEW_MODE=findings`). This is the default because it preserves
  pr-check's PR-aware value (reply + resolve threads in Phase 13).
- `Review entire PR diff instead` — ignore the existing findings and do a fresh
  agent review of the changed files (`REVIEW_MODE=diff`). Phase 13 reply/resolve
  is SKIPPED; the existing findings remain unaddressed (a warning is rendered
  in the Phase 14 final summary so the user can come back to them).
- `Do nothing` — exit immediately (`REVIEW_MODE=none`). The N findings remain
  unaddressed; user can re-run pr-check later.

If the user selects `Do nothing`, **STOP** — skip Phases 2-13 and render the
Phase 14 summary with the captured `findings_total` and `mode: none`.

**Mode propagation:** Phase 3 dispatches agents with a prompt selected by
`REVIEW_MODE` (see Step 3.3 below). Phase 13 (reply + resolve threads) runs
ONLY when `REVIEW_MODE=findings`; otherwise it is skipped (the agents never
produced AGREE/CONTEST verdicts to act on).

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
5. **Initialize .optimus directory (HARD BLOCK):** Execute Protocol: Initialize .optimus Directory — see AGENTS.md Protocol: Initialize .optimus Directory. This guarantees `.optimus/logs/` exists AND is gitignored before any `_optimus_quiet_run` call creates log files. Skipping this step in a fresh project will produce ungitignored logs that can be accidentally committed.

### Step 3.2: Baseline Unit Tests

Unit tests should pass before dispatching review agents. This establishes the baseline —
if tests are already failing, agent findings may be unreliable.

Run quietly — see AGENTS.md Protocol: Quiet Command Execution:

```bash
_optimus_quiet_run "make-test" make test
```

**If unit tests fail:**
1. `_optimus_quiet_run` already printed the last 50 lines plus the log path —
   review them in place.
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

[Render the header below based on `REVIEW_MODE` captured in Step 1.8. The data tables (Codacy / DeepSource / CodeRabbit / Human) that follow are IDENTICAL in both modes — only the framing changes. This avoids self-contradiction with the diff-mode appended block that says "DO NOT classify them".]

  When `REVIEW_MODE=findings`, render this header:

    Existing PR Comments — evaluate ALL of these (validate or contest each one):

  When `REVIEW_MODE=diff`, render this header instead:

    Existing PR Comments (informational context only — DO NOT classify):

  Then render the SAME data tables under whichever header was selected:

  Codacy Issues:
  [paste all Codacy findings with file, line, severity, message]

  DeepSource Issues:
  [paste all DeepSource findings with file, line, shortcode, severity, category, title, message]

  CodeRabbit Comments (inline):
  [paste all CodeRabbit inline review comments. For each comment, when the per-finding parse from Step 1.3.3 captured `FIX_LABEL`, `FIX_DIFF`, or `AI_PROMPT`, include those alongside the comment body so the agent has CodeRabbit's full framing — not just the prose description.]

  CodeRabbit Duplicate Comments (pre-parsed from review body — see Step 1.3.1.5 and 1.3.3):
  [render as a markdown table with EVERY finding from the <details> parse PLUS the "Prompt for all" parse UNION, one row each. Do NOT rely on the agent to reparse HTML.]

  | ID | File | Lines | Severity | Title | Description | Fix label | Fix diff | AI prompt (if any) | Source review ID |
  |----|------|-------|----------|-------|-------------|-----------|----------|--------------------|------------------|
  | D1 | scripts/enforce_signed_commit.py | 146-169 | CRITICAL | env /usr/bin/command git commit bypass | Inside the env branch, ... | Minimal fix | ```diff ... ``` | "Update the env-branch handling so the wrapped command no longer bypasses the signed-commit check..." | 4167400017 |
  | D2 | scripts/enforce_signed_commit.py | 11-12 | CRITICAL | Treat background & as separator | tokenize_command() emits &, but split_segments() ... | Suggested refactor | ```diff -SHELL_SEPARATORS = {"&&"...} +SHELL_SEPARATORS = {"&&"...,"&"} ``` | (none) | 4167400017 |

  Column semantics: `Fix label` is `Minimal fix` or `Suggested refactor` (or empty); `Fix diff` is the captured `<details>` body (or empty); `AI prompt (if any)` is the per-finding `🤖 Prompt for AI Agents` content (or `(none)`). All three may be empty for a single finding — CodeRabbit does not always supply them.

  **HARD BLOCK:** The count of rows in this table MUST equal the (N) in the review's "♻️ Duplicate comments (N)" summary. If the orchestrator could not produce a matching count, the run was aborted at Step 1.3.3 (count validation). If you see a mismatch here, STOP and report it.

  CodeRabbit Outside Diff Range Comments (pre-parsed from review body — see Step 1.3.1.5 and 1.3.3):
  [render as a markdown table using the same column schema as above; rows tagged OUTSIDE-DIFF]

  | ID | File | Lines | Severity | Title | Description | Fix label | Fix diff | AI prompt (if any) | Source review ID |
  |----|------|-------|----------|-------|-------------|-----------|----------|--------------------|------------------|
  | O1 | ... | ... | ... | ... | ... | ... | ... | ... | ... |

  Human Reviewer Comments:
  [paste all human reviewer comments]
```

**The Review Scope and Job sections are CONDITIONAL on `REVIEW_MODE` (captured
in Step 1.8).** Append exactly ONE of the two scope+job blocks below to the
prompt above, based on the user's choice. Both modes share the common header
just rendered (PR Context, project context, file list, existing comments).

**Append this block when `REVIEW_MODE=findings` (default for `findings_total > 0`):**

```
Review scope: existing PR comments and CI failure findings ONLY. Do NOT
review the changed code from scratch — fresh review is the job of
/optimus-deep-review (or REVIEW_MODE=diff in this same skill).

Your job:
  EVALUATE each existing PR comment in your domain:
    - AGREE: The comment is valid and should be addressed
    - CONTEST: The comment is incorrect or unnecessary (explain why)
    - ALREADY FIXED: The comment was addressed in a subsequent commit
  Plus: investigate CI failures assigned to your domain (Step 1.6).

For EACH evaluated comment, provide:
  - Severity: CRITICAL / HIGH / MEDIUM / LOW (echo from the original comment)
  - File and line (echo from the original comment)
  - Verdict: AGREE / CONTEST / ALREADY FIXED with justification
  - Impact analysis (four lenses):
    - UX: How does this affect end users?
    - Task focus: Is this within PR scope?
    - Project focus: MVP-critical or gold-plating?
    - Engineering quality: Maintainability, testability, reliability impact
  - Recommendation with tradeoffs

Cross-cutting analysis — apply ONLY to existing comments (use these questions to
decide AGREE / CONTEST / ALREADY FIXED, NOT to surface new findings):
  1. What would break in production under load with this code?
  2. What's MISSING that should be here? (not just what's wrong)
  3. Does this code trace back to a spec requirement? Flag orphan code without spec backing
  4. How would a new developer understand this code 6 months from now?
  5. Search the codebase for how similar problems were solved — flag inconsistencies with existing patterns
```

**Append this block when `REVIEW_MODE=diff` (user explicitly chose fresh review
in Step 1.8):**

```
Review scope: ALL files changed in this PR (fresh review of the diff).
The existing PR comments listed in the prompt above are INFORMATIONAL context
ONLY — DO NOT classify them as AGREE/CONTEST/ALREADY FIXED. The user
explicitly chose to set existing comments aside and request a fresh agent
review of the diff. (Phase 13 reply/resolve is SKIPPED this run; if the user
wants the existing comments addressed, they re-run pr-check with
REVIEW_MODE=findings.)

Your job:
  1. Review the CODE in your domain for issues across the changed files
  2. Report NEW findings discovered in the diff

For EACH new finding, provide:
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

Cross-cutting analysis (MANDATORY for all agents in diff mode):
  1. What would break in production under load with this code?
  2. What's MISSING that should be here? (not just what's wrong)
  3. Does this code trace back to a spec requirement? Flag orphan code without spec backing
  4. How would a new developer understand this code 6 months from now?
  5. Search the codebase for how similar problems were solved — flag inconsistencies with existing patterns
```

### Step 3.3 (continued): Discover and confirm roster

Execute `Protocol: Discover Review Droids` — see AGENTS.md Protocol: Discover Review Droids.

Default invocation: `INCLUDE_NON_RING=false` (privilege ring).

If the user invokes pr-check with the `--include-non-ring` flag (or the
slash-command alias surface accepts it), pass `INCLUDE_NON_RING=true`.

If the protocol returns `MIN_NOT_MET`, **STOP** with:

```
Required ring droids not installed. Install at minimum
`ring-default-code-reviewer` and `ring-default-security-reviewer`,
then re-run.
```

Present the discovered roster to the user via `AskUser` for confirmation before
dispatch (mirrors deep-review's existing UX). Default-selected: all ring entries.
Default-deselected: non-ring entries (only present if `INCLUDE_NON_RING=true`).

### Step 3.3.1: Pre-route by finding severity (findings mode only)

**Skip this step entirely when `REVIEW_MODE=diff`** — there are no existing
comments being evaluated, so severity-based routing of comments-with-FIX_DIFF
does not apply. All discovered ring agents are dispatched together for the
fresh diff review.

When `REVIEW_MODE=findings`, pre-route each comment based on its severity and
whether it ships with a `FIX_DIFF` (the per-finding fields `FIX_LABEL`,
`FIX_DIFF`, and `SEVERITY_LABEL` were captured at Step 1.3.3 — but ONLY for
the Duplicate / Outside-diff blocks parsed there. **Inline CodeRabbit threads
from Step 1.3.1 do NOT carry `FIX_LABEL` / `FIX_DIFF` / `SEVERITY_LABEL`** —
they intentionally route to the "WITHOUT FIX_DIFF: full dispatch" branch
below).

For each comment that has a non-empty `FIX_DIFF`, classify dispatch:

| Severity (CodeRabbit `SEVERITY_LABEL` / Codacy / DeepSource) | Dispatch |
|---|---|
| Critical (🔴) | ALL discovered ring agents |
| High / Major (🟠) | ALL discovered ring agents |
| Medium / Minor (🟡) | Single agent matching the finding's category (security finding → `ring-default-security-reviewer`; logic finding → `ring-default-business-logic-reviewer`; default → `ring-default-code-reviewer`) |
| Low / Trivial / Nitpick (🔵 / 🧹) | NO agent dispatch — present `FIX_DIFF` directly to user in Phase 6 with `Apply CodeRabbit as-is / Skip / Tell me more` (the option set already added in PR #15) |
| Unknown / missing severity | ALL discovered ring agents (safe fallback — never silently drop) |

> Note: Medium-tier category routing matches the FIRST roster entry whose focus
> aligns with the finding's category. Ring entries are preferred when both ring
> and non-ring agents match the same category.

For comments WITHOUT `FIX_DIFF`: full dispatch regardless of severity (current
behavior — agents have no diff to validate, the prose comment alone needs
interpretation).

Record the dispatch decision per finding in the audit trail so Phase 4 consolidation
can attribute correctly ("validated by N agents", "fast-tracked: nitpick with diff").

All confirmed agents MUST be dispatched in a SINGLE message with parallel Task calls.

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

**Mode gate:** Steps 2 and 4 are SKIPPED when `REVIEW_MODE=diff` (no
AGREE/CONTEST verdicts produced; nothing to merge or cross-reference).

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

[Mode gate: the "Contested Comments" and "Agent Verdicts" tables below are
rendered ONLY when `REVIEW_MODE=findings`. In `diff` mode, render only "False
Positives", "Genuine Findings", and "Summary" sections — replace the "Agent
Verdicts" line with a single line: "Agents performed fresh diff review
(REVIEW_MODE=diff). No verdicts on existing comments."]

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

**CodeRabbit's original suggestion (CodeRabbit-sourced findings only):**

Render this block ONLY when the finding's source is CodeRabbit AND at least one of `FIX_LABEL`, `FIX_DIFF`, or `AI_PROMPT` is non-empty. Render only the sub-fields that are populated; omit absent sub-fields silently. If all three are empty, omit the entire block.

- *Fix style:* `<FIX_LABEL>` *(e.g., `Minimal fix` or `Suggested refactor`)*
- *Suggested change:*
  ```diff
  <FIX_DIFF>
  ```
- *CodeRabbit-curated AI agent prompt:*
  > <AI_PROMPT>

Rationale: this gives the user full visibility into what CodeRabbit proposed before they pick from `Proposed Solutions`. The agent-validated options below remain the primary recommendation; the CodeRabbit block is supplementary context.

**Impact analysis (four lenses):**
- **UX:** End-user impact — errors, data loss, broken workflows
- **Task focus:** Within PR scope or tangential?
- **Project focus:** MVP-critical or gold-plating?
- **Engineering quality:** Maintainability, testability, reliability, consistency

#### Proposed Solutions

Present 2-3 options using the format from AGENTS.md "Common Patterns > Finding Option Format".

#### Collect Decision

**AskUser `[topic]` format:** Format: `(X/N) F#-Category`.
Example: `[topic] (8/12) F8-DeadCode`.

Use `AskUser`. **BLOCKING** — do not advance until decided.
**Every AskUser MUST include these options:**
- One option per proposed solution (Option A, Option B, Option C, etc.)
- **Apply CodeRabbit's suggested fix as-is** — *only* when the finding is CodeRabbit-sourced AND `FIX_DIFF` is non-empty. Selecting this option causes Phase 8 (Step 8.2) to apply `FIX_DIFF` verbatim, bypassing the agent-recommended options. Omit this option entirely when `FIX_DIFF` is empty (no CodeRabbit fix to apply) or when the finding is not CodeRabbit-sourced.
- Skip — no action
- Tell me more — if selected, STOP and answer immediately (do NOT continue to next finding)

**AskUser template (MANDATORY — follow this exact structure for every finding):**
```
1. [question] (X/N) SEVERITY — Finding title summary
[topic] (X/N) F#-Category
[option] Option A: recommended fix
[option] Option B: alternative approach
[option] Apply CodeRabbit's suggested fix as-is   ← include ONLY for CodeRabbit findings with non-empty FIX_DIFF
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
| **CodeRabbit-as-is** | User selected `Apply CodeRabbit's suggested fix as-is` in Phase 6, AND the finding has a non-empty `FIX_DIFF` | Apply `FIX_DIFF` verbatim with Edit tool, then run unit tests |
| **Simple** | Review agent provided exact fix, single file, localized change, obvious resolution (typo, missing nil guard, import, rename, dead code removal) | Apply directly with Edit tool |
| **Complex** | Multiple files, new logic, architectural impact, new test scenarios, security-sensitive, uncertain resolution | Dispatch ring droid with TDD cycle |
| **Uncertain** | Cannot confidently classify | Treat as complex → dispatch ring droid |

**CodeRabbit-as-is fix flow:**
1. Apply `FIX_DIFF` verbatim using Edit/MultiEdit. Treat the diff as authoritative — do NOT re-derive from agent recommendation.
2. Run unit tests to verify no regression.
3. If tests fail → revert the diff and escalate to ring droid dispatch (Complex flow), informing the user that CodeRabbit's diff did not pass tests as-applied. Record the failure in the per-finding audit trail.

**Relationship to coderabbit-review (intentional divergence):** This as-is path
is unique to `pr-check` and intentionally absent from `coderabbit-review`.
`coderabbit-review` always applies CodeRabbit findings via TDD (RED-GREEN-REFACTOR)
because that skill is for the case where the user wants to deeply understand
and re-implement each suggestion. `pr-check` accepts the trade-off of merging
CodeRabbit's exact patches (even nitpicks) because the goal here is unblocking
PR review, not author understanding. If you want as-is application, stay on
`pr-check`; if you want TDD-driven re-implementation, switch to
`coderabbit-review`. See coderabbit-review/SKILL.md Phase 4 for the mirror note.

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

**After ALL fixes are committed**, run lint once using the resolved command from
Step 3.1, wrapped in `_optimus_quiet_run` — see AGENTS.md Protocol: Quiet
Command Execution:
```bash
_optimus_quiet_run "make-lint" make lint
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

## Phase 10: Convergence Loop (Optional — Gated)

Execute the opt-in convergence loop — see AGENTS.md "Common Patterns > Protocol: Convergence Loop (Full Roster Model — Opt-In, Gated)".

**Behavioral contract for THIS phase:**
- Round 1 already ran in Phase 3. THIS phase only handles rounds 2 through 5.
- Present the **entry gate** before round 2 (`Run round 2` / `Skip convergence loop`).
- Present the **per-round gate** before rounds 3, 4, 5 (`Continue` / `Stop here`).
- If a dispatched round produces ZERO new findings, declare convergence and exit
  silently — DO NOT ask the user whether to run another round.
- Record the final loop status (`CONVERGED` / `USER_STOPPED` / `SKIPPED` /
  `HARD_LIMIT` / `DISPATCH_FAILED_ABORTED`) for the Final Summary in Phase 14.

**Stage-specific scope for convergence rounds 2+:**
Dispatch the **same agent roster** from Phase 3 (the roster confirmed in Step 3.3). Each agent
receives file paths, PR context (description, linked issues, base branch), and project
rules (re-read fresh from disk). Do NOT include the findings ledger in agent prompts —
the orchestrator handles dedup using strict matching (same file + same line range ±5 +
same category).

Include existing PR comments from all sources (reuse data from Phase 1 — do NOT re-fetch
Codacy/DeepSource comments, they only update after push). Include the cross-cutting
analysis instructions (same 5 items from Step 3.3 prompt).

**Failure handling:** If a fresh sub-agent dispatch fails (Task tool error, ring droid
unavailable), do NOT count as zero findings. Ask the user via `AskUser` whether to
retry the round or stop (status `DISPATCH_FAILED_ABORTED` if user stops).

When the loop exits (any status), proceed to Phase 11 (integration tests).

---

## Phase 11: Integration Tests (before push)

**Before pushing**, run integration tests. These are slow and expensive, so they
run ONCE here — not during the fix/convergence cycle. Run quietly —
see AGENTS.md Protocol: Quiet Command Execution:

```bash
_optimus_quiet_run "make-test-integration" make test-integration   # Optional target — SKIP if missing
```

| Test Type | Command | If target exists | If target missing |
|-----------|---------|-----------------|-------------------|
| Integration | `_optimus_quiet_run "make-test-integration" make test-integration` | **HARD BLOCK** if fails | SKIP |

**If integration tests fail:**
1. `_optimus_quiet_run` already printed the last 50 lines plus the log path —
   review them in place.
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

## Phase 13: Respond to ALL PR Comments

This phase has TWO sub-flows with independent mode gates:

| Sub-flow | Runs when | Purpose |
|---|---|---|
| **Step 13.0 — Outdated thread cleanup** | `REVIEW_MODE` ∈ {`findings`, `diff`} | Auto-reply + resolve every thread in `outdated_threads` (collected at Step 1.3.1). Pure hygiene — independent of agent verdicts. Required for CodeRabbit / approval-gate compliance, which withhold approval while ANY thread (including outdated ones) is unresolved. |
| **Steps 13.1-13.6 — Verdict-driven replies** | `REVIEW_MODE = findings` only | Reply per agent verdict (AGREE / CONTEST / ALREADY-FIXED) on `active_threads`, then resolve. Skipped in diff mode because agents performed a fresh review and never produced verdicts on existing comments. |

**Mode behavior at a glance:**
- `findings` → Step 13.0 runs THEN Steps 13.1-13.6 run.
- `diff` → Step 13.0 runs (outdated cleanup); Steps 13.1-13.6 are SKIPPED. Phase 14 renders a warning that existing active comments remain unaddressed.
- `none` → user already exited at Step 1.8; Phase 13 is unreachable.

**HARD BLOCK (when running):** Every thread in scope MUST receive a reply AND be resolved. Phase 14 verifies zero unresolved threads remain.

<a id="step-cleanup-outdated-threads"></a>
### Step 13.0: Auto-resolve outdated threads (runs in `findings` and `diff` modes)

For EACH thread in `outdated_threads` collected at Step 1.3.1 where `is_resolved` is `false` (skip already-resolved ones):

1. **Reply** with this exact body (use the source's reply method from the thread's `reply_method` field; see Cases A and B below for the API choice):

   ```
   Outdated — this thread references code that was modified in subsequent commits and is no longer relevant to the current diff. Auto-resolved by /optimus-pr-check.
   ```

2. **Resolve** via GraphQL `resolveReviewThread` mutation (always GraphQL for resolve, regardless of source).

3. **Confirm** `isResolved: true` in the response.

4. **Deduplication note:** if the same finding re-surfaces in CodeRabbit's `♻️ Duplicate comments` section (Step 1.3.1.5), that re-surfaced finding is a SEPARATE entity in `active_threads` and goes through the normal verdict flow in Steps 13.1-13.6. The outdated thread auto-reply does NOT conflict — they're different surfaces of the related finding (one stale, one re-asserted).

5. **Idempotency:** before posting, check whether the agent already replied with the "Outdated — this thread references code that was modified..." string in this thread. If yes, skip the reply and proceed directly to resolve (handles re-runs after a crash between reply and resolve).

After processing all outdated threads, log: `"Auto-resolved M outdated threads in Step 13.0."`

**HARD BLOCK (Steps 13.1-13.6, findings mode only):** When REVIEW_MODE=findings, every active PR comment thread MUST receive a verdict-driven reply via the steps below — regardless of whether any fixes were applied. Step 13.0 above runs independently of this gate.

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

After all threads are processed (BOTH the active threads from Steps 13.1-13.3 AND the outdated threads from Step 13.0), re-run the query from Step 13.2 and confirm ALL threads — including outdated ones — have `isResolved: true`. If any remain unresolved, reply and resolve them now. Do NOT proceed until zero unresolved threads remain.

**Why this includes outdated threads:** CodeRabbit and other approval gates inspect EVERY review thread on the PR, not just the ones agents acted on. Leaving outdated threads with `isResolved: false` blocks PR approval even though the underlying code was already fixed in subsequent commits. Step 13.0's auto-resolve hygiene is the entire reason this gate now passes.

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

**HARD BLOCK:** The Status column MUST show "Resolved" for every row (including outdated-cleanup rows). If any row shows "Replied" instead of "Resolved", go back and resolve it.

Render TWO tables. The "Active threads" table is omitted entirely in `diff` mode (no verdicts produced); the "Outdated threads" table is rendered in both `findings` and `diff` modes.

```markdown
### PR Comment Replies Posted

#### Active threads (verdict-driven — `findings` mode only)
| # | Thread | Source | Reply | Commit | Status |
|---|--------|--------|-------|--------|--------|
| 1 | file.go:42 | Codacy | Fixed | abc1234 | Resolved |
| 2 | file.go:88 | DeepSource | Won't fix: convention. Suppressed | def5678 | Resolved |
| 3 | file.go:15 | CodeRabbit | Fixed | ghi9012 | Resolved |
| 4 | file.go:22 | @reviewer | Won't fix: out of scope | — | Resolved |
| 5 | general | @reviewer | [answer] | — | Resolved |

#### Outdated threads (Step 13.0 hygiene — runs in `findings` and `diff` modes)
| # | Thread | Source | Reply | Status |
|---|--------|--------|-------|--------|
| 1 | file.go:120 | CodeRabbit | Outdated — code changed in subsequent commits | Resolved |
| 2 | file.go:88 | Codacy | Outdated — code changed in subsequent commits | Resolved |
```

---

## Phase 14: Final Summary

**Always render the `REVIEW_MODE` selected in Step 1.8** (`findings` | `diff` | `none`)
and a warning if findings remain unaddressed. Pick the template by mode:

**Template — when `REVIEW_MODE=none` (user chose Do nothing in Step 1.8):**

```markdown
## PR Review Summary: #<number> — <title>

**Mode:** none (user opted out)
**findings_total:** <N>
[render the next line ONLY if M > 0:]
**Outdated threads observed (NOT cleaned, blocking CodeRabbit approval):** M — re-run pr-check with mode=findings or mode=diff to auto-resolve them via Step 13.0. None mode respects user opt-out from all PR mutation, so these were left untouched.
**Status:** Exited without dispatching agents. <N> findings remain
unaddressed. Re-run `/optimus-pr-check` later to handle them.
```

**Template — when `REVIEW_MODE=diff` (user chose fresh diff review):**

```markdown
## PR Review Summary: #<number> — <title>

**Mode:** diff (fresh review of changed files; existing comments NOT evaluated)
**findings_total (existing, unaddressed):** <N>
**New agent findings (this run):** <M>
**Outdated threads auto-resolved (Step 13.0): M** — pure hygiene; required for CodeRabbit / approval-gate compliance

[render the next paragraph ONLY if findings_total > 0:]
⚠️ **<N> existing PR comments / CI failures were NOT addressed in this run.**
Phase 13 verdict-driven replies (Steps 13.1-13.6) were skipped because diff
mode does not produce AGREE/CONTEST verdicts on existing threads. (Step 13.0
outdated thread cleanup ran normally — see count below.) To address them,
re-run pr-check with `REVIEW_MODE=findings` (the default when findings_total > 0).

[then render the standard tables for Fixed / Skipped / Deferred / CI Status /
Verification / Configuration Changes — same schema as findings mode, but
populated only with the new findings discovered in this run]
```

**Template — when `REVIEW_MODE=findings` (default path with findings_total > 0):**

Render the standard summary below.

```markdown
## PR Review Summary: #<number> — <title>

### Sources Analyzed
- CI checks: X failing (Y fixed, Z remaining)
- Codacy: X issues (Y fixed, Z suppressed)
- DeepSource: X issues (Y fixed, Z suppressed)
- CodeRabbit: X comments (Y validated, Z contested)
- Human reviewers: X comments (Y validated, Z contested)
- New agent findings: X
- **Outdated threads auto-resolved (Step 13.0): M** — pure hygiene; required for CodeRabbit / approval-gate compliance
  [render this aside ONLY when M is non-trivially large, e.g. M >= 10:]
  (NOTE: on the first pr-check run after this skill was upgraded, M may be unexpectedly large because previously-discarded outdated threads from prior runs accumulate on the PR. Subsequent runs will see steady-state values.)

### Convergence
- Rounds dispatched (round 1 + convergence rounds): X
- Status: CONVERGED | USER_STOPPED | SKIPPED | HARD_LIMIT | DISPATCH_FAILED_ABORTED

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
- Coverage verification runs ONLY after all fixes are applied; the convergence loop is opt-in (gated)
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
- **Do NOT enter the convergence loop (rounds 2+)** — round 1 (primary review pass) is sufficient for preview
- Present results as informational with estimated fix effort

<!-- INLINE-PROTOCOLS:START -->
## Shared Protocols (from AGENTS.md)

The following protocols are referenced by this skill. They are
extracted from the Optimus AGENTS.md to make this plugin self-contained.

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


<!-- INLINE-PROTOCOLS:END -->
