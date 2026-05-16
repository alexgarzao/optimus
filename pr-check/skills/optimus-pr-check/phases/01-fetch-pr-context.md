# Phase 1: Fetch PR Context

Loaded by `SKILL.md` first. Fetch PR metadata, all review comments (Codacy/DeepSource/CodeRabbit/human), CI status, and changed files. EVERY invocation starts from scratch — no state carried over.

### Phase 1: Fetch PR Context

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
                pullRequestReview { id author { login } }
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
  body: "<first comment body>",
  review_node_id: "<PullRequestReview node ID, or null if thread is not part of a review>",
  review_author: "<login, e.g. coderabbitai[bot]>"
}
```

`review_node_id` and `review_author` come from the first comment's `pullRequestReview { id author { login } }` selection in the GraphQL query above. They are consumed by Step 13.5 to group threads by their parent review and decide which review summaries (e.g. CodeRabbit's `#pullrequestreview-<id>` entries) are fully resolved and therefore eligible to be hidden via `minimizeComment`.

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
