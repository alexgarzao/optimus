---
name: optimus-cycle-pr-review-stage-4
description: >
  Unified PR review orchestrator. Fetches PR metadata, collects ALL review
  comments (Codacy, DeepSource, CodeRabbit, human reviewers), dispatches
  parallel agents to evaluate code and comments, presents findings interactively,
  applies fixes with TDD cycle and separate commits per finding, responds to
  every comment thread with commit reference or justification, and adds inline
  suppression tags for Codacy/DeepSource when a finding won't be fixed.
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
  - For Codacy/DeepSource findings: workflows codacy-issues.yml and deepsource-pr-issues.yml should exist in the repo (if not present, those sources are simply skipped)
NOT_skip_when: >
  - "The PR is small" → Small PRs still benefit from structured review with PR context.
  - "I already looked at the diff" → Specialist agents catch issues human review misses.
  - "CI passed" → CI checks automated rules; agents review logic, security, and quality.
  - "CodeRabbit already reviewed" → Agents validate/contest CodeRabbit findings and catch what it misses.
  - "Codacy/DeepSource already analyzed" → Agents validate/contest static analysis findings and catch what they miss.
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
    - optimus-verify-code
  differentiation:
    - name: optimus-deep-review
      difference: >
        optimus-deep-review is a generic code review that works with any scope
        (all files, git diff, directory). optimus-pr-review adds PR context
        (description, linked issues, existing comments from ALL sources) and
        evaluates feedback from multiple sources (Codacy, DeepSource, CodeRabbit,
        human reviewers, agents).
  sequence:
    after:
      - optimus-cycle-impl-review-stage-3
    before:
      - optimus-cycle-close-stage-5
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

## Phase -1: Verify GitHub CLI (HARD BLOCK)

```bash
gh auth status 2>/dev/null
```

If this command fails (exit code != 0), **STOP** immediately:
```
GitHub CLI (gh) is not authenticated. Run `gh auth login` to authenticate before proceeding.
```

---

## CRITICAL: Every Invocation Starts From Scratch

**HARD BLOCK:** Every time this skill is invoked, it MUST fetch ALL data fresh from the PR. There is NO state carried over from previous invocations.

- Do NOT assume issues from a previous run are still resolved
- Do NOT skip fetching comments because "I already saw this PR"
- Do NOT say "issues were already resolved" without fetching and verifying RIGHT NOW
- New comments, new commits, new CI results may exist since the last run
- Always run Phase 0 completely: fetch metadata, fetch ALL threads, fetch CI checks, fetch changed files
- The PR may have changed entirely since the last time you looked at it

If you find yourself saying "these were already addressed" without having run `gh api` commands in THIS session, you are violating this rule.

---

## Task Mode vs Standalone Mode

This skill operates in TWO modes:

### Task Mode (part of the stage pipeline)
When the user references a task (e.g., "review PR for T-012") or a `tasks.md` exists with a task in status `Validando Impl` or `Revisando PR`:

1. **Find tasks.md:** Look in `./tasks.md` (project root). If not found, look in `./docs/tasks.md`.
2. **Validate format:** First line must be `<!-- optimus:tasks-v1 -->`. If missing, **STOP** and suggest `/optimus-cycle-migrate`.
3. **Verify workspace (HARD BLOCK):** This agent modifies code. It MUST NOT run on the default/main branch.
   ```bash
   DEFAULT_BRANCH=$(git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's@^refs/remotes/origin/@@')
   CURRENT_BRANCH=$(git branch --show-current)
   ```
   - If `CURRENT_BRANCH` equals `DEFAULT_BRANCH` (or is `main`/`master`) → **STOP**:
     ```
     Cannot run cycle-pr-review-stage-4 on the default branch (<branch>).
     Switch to the task's feature branch first.
     ```
3.1. **Branch-task cross-validation:** After confirming the task ID, check that the current branch matches the **Branch** column in `tasks.md` for this task:
   - Read the Branch column for the confirmed task ID
   - If Branch is `-` or empty → warn: "tasks.md shows no branch for T-XXX, but you are on `<current>`. Continue anyway?" (via `AskUser`)
   - If Branch has a value AND it does not match `CURRENT_BRANCH` → warn: "tasks.md shows branch `<expected>` for T-XXX, but you are on `<current>`. Continue on current branch, or switch?" (via `AskUser`)
   - If Branch matches `CURRENT_BRANCH` → proceed silently
4. **Validate status:** The task MUST be in status `Validando Impl` (set by cycle-impl-review-stage-3) or `Revisando PR` (re-execution). If not, STOP and tell the user which agent to run first.
5. **Check dependencies (HARD BLOCK):** Read the Depends column for this task.
   - If Depends is `-` → proceed (no dependencies)
   - For each dependency ID listed, check its Status in the table:
     - If ALL dependencies have status `**DONE**` → proceed
     - If ANY dependency is NOT `**DONE**` → **STOP**:
       ```
       Task T-XXX depends on T-YYY (status: '<status>'). T-YYY must be **DONE** first.
       ```
6. **Expanded confirmation before status change:**
   - **If status will change** (current status is NOT `Revisando PR`) AND the user did NOT specify the task ID explicitly (auto-detect):
     - Read the task's H2 detail section (`## T-XXX: Title`) from `tasks.md`
     - Present to the user via `AskUser`:
       ```
       I'm about to change task T-XXX status from '<current>' to 'Revisando PR'.

       **T-XXX: [title]**
       **Version:** [version from table]
       **Objetivo:** [objective from detail section]
       **Critérios de Aceite:**
       - [ ] [criterion 1]
       - [ ] [criterion 2]
       ...

       Confirm status change?
       ```
     - **BLOCKING:** Do NOT change status until the user confirms
   - **If re-execution** (status is already `Revisando PR`) OR the user specified the task ID explicitly:
     - Skip expanded confirmation (user already has context)
7. **Update status:** Change the task status in `tasks.md` to `Revisando PR` (if not already).
8. Commit the status change immediately:
   ```bash
   git add tasks.md
   git commit -m "chore(tasks): set T-XXX status to Revisando PR"
   ```

   **Why commit immediately:** If the session is interrupted or the agent crashes before any review fixes are committed, the status update would be lost. Committing now ensures the status change is persisted regardless of the review outcome.
9. At the END of the review (after all findings resolved, threads replied), do NOT change status again — the user invokes cycle-close-stage-5 next.

### Standalone Mode (no task)
When no task is referenced and no `tasks.md` exists, or the user explicitly wants to review a PR without a task context:
- Skip all task status logic
- Proceed directly to Phase 0

### How to detect which mode:
1. If the user mentions a task ID (T-XXX) → Task Mode
2. Find `tasks.md` in `./tasks.md` or `./docs/tasks.md`. If found:
   a. If exactly ONE task is in `Validando Impl` or `Revisando PR` → Task Mode (confirm with user via `AskUser`)
   b. If MULTIPLE tasks are in `Validando Impl` or `Revisando PR` → Task Mode, but ask the user which task to review via `AskUser` (list all candidates with ID, title, version, and branch)
   c. If NO tasks are in `Validando Impl` or `Revisando PR` → Standalone Mode
3. If no `tasks.md` exists → Standalone Mode

---

## Phase 0: Fetch PR Context

### Step 0.1: Obtain PR URL

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
- **Create PR** — create a PR against the default branch with a Conventional Commits title derived from the task's Tipo and title (same logic as cycle-impl-review-stage-3 Phase 8)
- **Provide URL** — I have a PR URL to use
- **Cancel** — stop the review

If the user chooses **Create PR**:
1. Generate PR title from task Tipo + ID + title (e.g., `feat(T-003): add user registration API`)
2. Generate PR body from the task's detail section (Objetivo + Critérios de Aceite)
3. Push the branch if not yet pushed: `git push -u origin $(git branch --show-current)`
4. Create the PR:
   ```bash
   gh pr create --title "<title>" --body "<body>" --base <default_branch> --assignee @me
   ```
5. Use the newly created PR for the rest of the review

If the user chooses **Provide URL**, ask for the URL via `AskUser`.

### Step 0.2: Fetch PR Metadata

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

### Step 0.2.1: Validate PR Title (Conventional Commits)

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

**If in Task Mode:** cross-check the type against the task's **Tipo** column:
- Feature → `feat`, Fix → `fix`, Refactor → `refactor`, Chore → `chore`, Docs → `docs`, Test → `test`
- If the type does not match the Tipo mapping, flag as a finding

**Regex for validation:**
```
^(feat|fix|refactor|chore|docs|test|build|ci|style|perf)(\([a-zA-Z0-9_\-]+\))?!?: .+$
```

**If validation fails:** add a finding (severity: MEDIUM) to the findings list with:
- Current title
- What's wrong (missing type, wrong format, type/Tipo mismatch, etc.)
- Suggested corrected title
- Fix command: `gh pr edit <number> --title "<corrected title>"`

**If validation passes:** no action needed, proceed.

### Step 0.3: Collect ALL Existing PR Comments and Threads

**IMPORTANT:** Static analysis tools post comments in TWO different ways:
1. **Native app comments** — posted directly by the tool's GitHub App (e.g., `deepsource-io`, `codacy-production`). These create review threads that the REST API CANNOT reply to (returns 404). You MUST use GraphQL to reply and resolve these.
2. **Workflow comments** — posted by `github-actions[bot]` via CI workflows (e.g., `codacy-issues.yml`, `deepsource-pr-issues.yml`). These are standard review comments that the REST API CAN reply to.

You MUST collect BOTH types for each tool.

#### Step 0.3.1: Fetch ALL Review Threads via GraphQL (PRIMARY SOURCE)

This is the **single source of truth** for all review threads. It captures threads from ALL sources (native apps, workflows, humans, bots) in one query:

```bash
gh api graphql -f query='
  query {
    repository(owner: "<owner>", name: "<repo>") {
      pullRequest(number: <number>) {
        reviewThreads(first: 100) {
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

#### Step 0.3.2: Fetch General PR Comments

```bash
gh pr view <PR_NUMBER_OR_URL> --comments
```

These are non-inline comments (discussion, summaries). They don't have threads.

#### Step 0.3.3: Parse Comment Content

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

#### Step 0.3.4: Summary

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

### Step 0.4: Checkout PR Branch

```bash
gh pr checkout <PR_NUMBER_OR_URL>
```

If already on the correct branch, skip. If checkout fails due to uncommitted changes, inform the user.

### Step 0.5: Fetch CI Check Status (MANDATORY)

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

### Step 0.6: Investigate EVERY Failing Check (MANDATORY)

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
COMMIT_SHA=$(gh api repos/{owner}/{repo}/pulls/{number} --jq '.head.sha')

# Get ALL failing check runs with their details
gh api repos/{owner}/{repo}/commits/${COMMIT_SHA}/check-runs \
  --jq '.check_runs[] | select(.conclusion == "failure") | {name, conclusion, app_slug: .app.slug, details_url, output: {title: .output.title, summary: .output.summary, annotations_count: .output.annotations_count}}'
```

2. **For GitHub Actions failures, fetch logs:**
```bash
RUN_ID=$(echo "<details_url>" | grep -oP 'runs/\K[0-9]+')
gh run view $RUN_ID --log-failed 2>/dev/null | tail -100
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

These CI failure findings are included in Phase 3 consolidation alongside agent findings, assigned sequential IDs (F1, F2...), and presented to the user for resolution in Phase 5 like any other finding.

**IMPORTANT:** CI failures are NOT informational — they are actionable findings that block merge readiness. If you present a PR summary that says "everything is OK" while `gh pr checks` shows failing checks, you have violated this rule.

### Step 0.7: Fetch Changed Files

```bash
gh pr diff <PR_NUMBER_OR_URL> --name-only
```

Read the full content of each changed file for the review agents.

---

## Phase 1: Present PR Summary

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

## Phase 2: Parallel Agent Dispatch

### Step 2.1: Discover Project Context

1. **Identify stack:** Check for `go.mod`, `package.json`, `Makefile`, `Cargo.toml`, etc.
2. **Identify test commands:** Look in `Makefile`, `package.json` scripts, or CI config
3. **Identify project rules and AI instructions (MANDATORY):** Search for these files and read ALL that exist:
   - `AGENTS.md`, `CLAUDE.md`, `DROIDS.md`, `.cursorrules` (repo root)
   - `PROJECT_RULES.md` (repo root or `docs/`)
   - `.editorconfig`, `docs/coding-standards.md`, `docs/conventions.md`
   - `.github/CONTRIBUTING.md` or `CONTRIBUTING.md`
   - Linter configs: `.eslintrc*`, `biome.json`, `.golangci.yml`, `.prettierrc*`

   These are the **source of truth** for coding standards. Pass relevant sections to every agent dispatched.
4. **Identify reference docs:** Look for PRD, TRD, API design

Store discovered commands:
```
LINT_CMD=<discovered lint command>
TEST_UNIT_CMD=<discovered unit test command>
TEST_INTEGRATION_CMD=<discovered integration test command>
TEST_E2E_CMD=<discovered E2E test command>
```

### Step 2.2: Dispatch Agents

Dispatch ALL applicable agents simultaneously via `Task` tool. Each agent receives:
- The full content of every changed file
- The PR context (description, linked issues)
- ALL existing PR comments from ALL sources (Codacy, DeepSource, CodeRabbit, human)
- Coding standards and reference docs

**Agent prompt MUST include:**

```
PR Context:
  - PR #<number>: <title>
  - Purpose: <PR description summary>
  - Linked issues: <list>
  - Base branch: <base>

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
```

### Agents (always dispatch ALL)

| # | Agent | Focus | Ring Droid |
|---|-------|-------|------------|
| 1 | Code quality | Architecture, SOLID, DRY, maintainability | `ring-default-code-reviewer` |
| 2 | Business logic | Domain correctness, edge cases | `ring-default-business-logic-reviewer` |
| 3 | Security | Vulnerabilities, OWASP, input validation | `ring-default-security-reviewer` |
| 4 | Test quality | Coverage gaps, error scenarios, flaky patterns | `ring-default-ring-test-reviewer` |
| 5 | Nil/null safety | Nil pointer risks, unsafe dereferences | `ring-default-ring-nil-safety-reviewer` |
| 6 | Ripple effects | Cross-file impacts beyond changed files | `ring-default-ring-consequences-reviewer` |
| 7 | Dead code | Orphaned code from changes | `ring-default-ring-dead-code-reviewer` |

**Ring droids are REQUIRED.** If the core review droids are not installed, **STOP** and inform the user:
```
Required ring droids are not installed. Install them before running this skill:
  - ring-default-code-reviewer
  - ring-default-business-logic-reviewer
  - ring-default-security-reviewer
  - ring-default-ring-test-reviewer
```

All agents MUST be dispatched in a SINGLE message with parallel Task calls.

---

## Phase 3: Consolidation

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

## Phase 4: Present Overview

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

## Phase 5: Finding Presentation and Resolution

Findings are presented ONE AT A TIME, decisions collected for ALL, then fixes applied ALL AT ONCE at the end.

**=== MANDATORY — Progress Tracking (NEVER SKIP) ===**

**BEFORE presenting the first finding, you MUST:**
1. Count the TOTAL number of findings (N) — sum of genuine findings, validated comments, contested comments, and new agent findings
2. Display the total prominently: `"### Total findings to review: N"`
3. This total MUST be visible to the user BEFORE any finding is presented

**For EVERY finding presented, you MUST:**
1. Include `"Finding X of N"` in the header — this is NOT optional
2. X starts at 1 and increments sequentially
3. N is the total announced above and NEVER changes mid-review
4. If you present a finding WITHOUT "Finding X of N" in the header, you are violating this rule — STOP and correct it

**The user MUST always know:**
- How many findings exist in total (N)
- Which finding they are currently reviewing (X)
- How many remain (N - X)

### Step 5.1: Present Findings One at a Time (collect decisions only)

Present ALL findings sequentially, one after another, collecting the user's decision for each. Do NOT apply any fix during this phase — only collect decisions.

For EACH finding:

#### Finding Header

`## Finding X of N — [SEVERITY] F# | [Source] | [Category]`

Example: `## Finding 1 of 12 — [HIGH] F1 | Codacy + Agent | Security`
Example: `## Finding 5 of 12 — [MEDIUM] F5 | DeepSource + Agent | Anti-pattern`
Example: `## Finding 8 of 12 — [MEDIUM] F8 | CodeRabbit — DUPLICATE + Agent | Error handling`
Example: `## Finding 10 of 12 — [LOW] F10 | CodeRabbit — OUTSIDE PR DIFF + Agent | Naming`
Example: `## Finding 12 of 12 — [LOW] F12 | CodeRabbit + Agent | Style`

#### Deep Research Before Presenting (MANDATORY)

**BEFORE presenting any finding to the user, you MUST research it deeply.** This research
is done SILENTLY — do not show the research process. Present only the conclusions.

**Research checklist (ALL items, every finding):**

1. **Project patterns:** Read the affected file(s) fully, understand the patterns used, check how similar cases are handled elsewhere in the codebase
2. **Architectural decisions:** Review project rules (AGENTS.md, PROJECT_RULES.md, etc.) and architecture docs. Understand WHY the project is structured this way
3. **Existing codebase:** Search for precedent — if the codebase already does the same thing in other places, that context changes the finding's weight
4. **Current task focus:** Is this finding within the scope of the PR/task? Flag tangential findings as such
5. **User/consumer use cases:** Who consumes this code — end users, other services, internal modules? Trace impact to real user scenarios
6. **UX impact:** For user-facing changes, evaluate usability, accessibility, error messaging, and workflows
7. **API best practices:** REST conventions, error handling, idempotency, status codes, pagination, versioning, backward compatibility
8. **Engineering best practices:** SOLID principles, DRY, separation of concerns, error handling, resilience, observability, testability
9. **Language-specific best practices:** Use `WebSearch` to research idioms for the specific language (Go, TypeScript, etc.) — official style guides, linter rules, community patterns
10. **Correctness over convenience:** Always recommend the correct approach, regardless of effort

**After research, form your recommendation:** Option A MUST be the approach you believe is correct based on all the research above, backed by evidence (project patterns, best practice references, official docs).

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

**Option A MUST be your researched recommendation** — the approach you believe is correct based on best practices research, project context, and engineering principles. State clearly why this is the recommended option. Always prefer correctness over convenience.

For each option:
```
**Option A: [name] (RECOMMENDED)**
[Concrete steps — what to do, which files to change]
- Why recommended: [reference to research — best practice, project pattern, official docs]
- Impact: UX / Task focus / Project focus / Engineering quality
- Effort: low / medium / high / very high
- Estimated time: < 5 min / 5-15 min / 15-60 min / 1-4h / > 4h

**Option B: [name]**
[Alternative approach]
- Impact: UX / Task focus / Project focus / Engineering quality
- Effort: low / medium / high / very high
- Estimated time: < 5 min / 5-15 min / 15-60 min / 1-4h / > 4h
```

#### Collect Decision

Use `AskUser`. **BLOCKING** — do not advance until decided.

**CRITICAL — If the user responds with a question or disagreement instead of a decision:**
- STOP immediately — do NOT continue to the next finding
- Research the user's question/concern RIGHT NOW using `WebSearch`, codebase analysis, or both
- Provide a thorough answer with evidence (links, code references, best practice citations)
- Only AFTER the user is satisfied, ask for their decision again
- This may go back and forth multiple times — that is expected and correct behavior

Record: finding ID, source(s), decision (fix/skip/defer), chosen option. Do NOT apply any fix yet.

---

## Phase 5.5: Recommend Rule Configuration (Codacy/DeepSource)

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

## Phase 6: Apply All Approved Fixes with TDD Cycle

**IMPORTANT:** This phase runs ONCE, after ALL findings have been presented and ALL decisions collected in Phase 5. No fix is applied during Phase 5.

### Step 6.1: Pre-Apply Summary

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

### Step 6.2: TDD Cycle for Each Fix

For each approved fix, dispatch a specialist droid via `Task` tool:

1. **RED:** Write a failing test that exposes the problem
2. **GREEN:** Implement the minimal fix to make the test pass
3. **REFACTOR:** Improve without changing behavior
4. **RUN UNIT TESTS:** Execute `make test` to verify no regressions

**For documentation fixes (docs, README, specs):** dispatch ring documentation droids
(`ring-tw-team-functional-writer`, `ring-tw-team-api-writer`). Documentation
droids do NOT follow TDD — they apply the fix directly.

**Droid selection priority (code fixes):**
1. `ring-dev-team-backend-engineer-golang` — Go fixes
2. `ring-dev-team-backend-engineer-typescript` — TypeScript backend
3. `ring-dev-team-frontend-engineer` — React/Next.js frontend
4. `ring-dev-team-qa-analyst` — test fixes
5. `ring-dev-team-qa-analyst` — test fixes

### Step 6.3: Handle Test Failures (max 3 attempts)

1. **Logic bug** → Return to RED, adjust test/fix
2. **Flaky test** → Re-execute 3 times, document, tag with "pending-test-fix"
3. **External dependency** → Pause and wait

### Step 6.4: Commit Each Fix

After each successful TDD cycle:

1. Stage ONLY the files changed by this fix
2. Commit with descriptive message:
   ```bash
   git commit -m "fix: <concise description>

   Addresses review finding F<N> [<source>]"
   ```
3. Record `{finding_id} → {commit_sha}` mapping

### Step 6.4.1: Final Lint Check

**After ALL fixes are committed**, run lint once:
```bash
make lint
```
If lint fails, fix formatting issues, amend the last commit or create a `chore: fix lint` commit.

### Step 6.5: Suppress Won't-Fix Findings (Codacy/DeepSource)

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
git commit -m "chore: suppress won't-fix static analysis findings

Codacy: X findings suppressed (via <linter> inline suppression)
DeepSource: Y findings suppressed (skipcq)"
```

Record the suppression commit SHA for use in Phase 8.

---

## Phase 6.6: Coverage Verification and Test Gap Analysis

**IMPORTANT:** This phase runs ONLY ONCE, after ALL fixes from Phase 6 have been applied.

### Step 6.6.1: Coverage Measurement (Unit Tests)

```bash
go test -coverprofile=coverage-unit.out ./...
go tool cover -func=coverage-unit.out | tail -1
```

**Threshold:** Unit tests: 85% minimum

**NOTE:** Integration test coverage is measured in Phase 7.1 (before push), not here.

### Step 6.6.2: Test Gap Analysis

Dispatch a test gap analyzer via `Task` tool. Use `ring-default-ring-test-reviewer` or `ring-dev-team-qa-analyst`.

HIGH priority gaps are presented as findings for user decision.

---

## Phase 6.7: Convergence Loop (MANDATORY)

After Phase 6.6, automatically re-validate using fresh sub-agents to eliminate session bias.

**CRITICAL — Why Fresh Sub-Agents:**

The primary failure mode of convergence loops is **false convergence**: the orchestrator re-runs analysis in the same session, with the same mental model, and declares "zero new findings" — not because there are none, but because it can't see past its own prior reasoning.

The solution: **rounds 2+ are executed by a fresh sub-agent** dispatched via `Task` tool. The sub-agent has zero context from prior rounds, reads all files from scratch, and returns findings independently. The orchestrator then deduplicates against the cumulative ledger.

**Round structure:**

| Round | Who analyzes | How |
|-------|-------------|-----|
| **1** (initial) | Orchestrator (this agent) | Phase 2 (parallel agent dispatch) + Phase 3 (consolidate) — normal flow |
| **2** (mandatory) | **Fresh sub-agent** via `Task` | Sub-agent reads all changed files from scratch, reviews independently, returns findings |
| **3-5** | **Fresh sub-agent** via `Task` | Same as round 2 — only triggered if round 2+ found new findings |

**Round 2 is MANDATORY.** The "zero new findings" stop condition can only trigger starting from round 3.

**Fresh sub-agent dispatch (rounds 2+):**

Dispatch a single sub-agent via `Task` tool (use any available ring review droid, e.g., `ring-default-code-reviewer`). The sub-agent receives:

1. **All changed files** — full content, re-read fresh from disk
2. **PR context** — description, linked issues, base branch
3. **Project rules and coding standards** — re-read fresh
4. **The findings ledger** — for deduplication ONLY
5. **Existing PR comments** — from Codacy, DeepSource, CodeRabbit, humans (do NOT re-fetch; use the data from Phase 0)

```
Goal: Independent PR review of #<number> (convergence round X of 5)

You are a FRESH reviewer with NO prior context. Review this PR from scratch.

Context:
  - PR: #<number> — <title>
  - Changed files: [full content — re-read from disk]
  - Project rules: [full content — re-read from files]
  - Existing PR comments: [from all sources]

Analysis scope: code quality, business logic, security, test quality,
spec compliance, cross-file consistency.

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
2. **Genuinely new findings** → add to ledger, present to user
3. **Duplicates** → discard silently

**Loop rules:**
- Max 5 rounds (initial = round 1)
- **Round 2 is MANDATORY** — always dispatch a fresh sub-agent regardless of round 1 results
- Show `"=== Re-validation round X of 5 (fresh sub-agent) ==="` at start
- Do NOT re-fetch Codacy/DeepSource comments (they only update after push)
- Maintain deduplication ledger across all rounds
- **Stop conditions (any one triggers exit):**
  1. Zero new findings — **only valid from round 3 onward** (round 2 is mandatory)
  2. Round 5 completed (hard limit)
  3. User explicitly requests to stop
- **LOW severity findings are NOT a reason to stop** — ALL findings regardless of severity MUST be presented to the user for decision.

**Round summary (show after each round):**

```markdown
### Round X of 5 (fresh sub-agent) — Summary
- New findings this round: N (C critical, H high, M medium, L low)
- Cumulative: X total findings across Y rounds
- Fixed: A | Skipped: B | Deferred: C
- Status: CONVERGED / CONTINUING / HARD LIMIT REACHED
```

---

## Phase 7: Integration and E2E Tests (before push)

**Before pushing**, run integration and E2E tests. These are slow and expensive, so they
run ONCE here — not during the fix/convergence cycle.

```bash
make test-integration        # Integration tests — if target exists
make test-e2e                # E2E tests — if target exists
```

| Test Type | Makefile Target | If target exists | If target missing |
|-----------|----------------|-----------------|-------------------|
| Integration | `make test-integration` | **HARD BLOCK** if fails | SKIP |
| E2E | `make test-e2e` | **HARD BLOCK** if fails | SKIP |

**If any test fails:**
1. Present the failure output (first 30 lines)
2. Ask via `AskUser`: "Integration/E2E tests are failing. What should I do?"
   - Fix the issue (dispatch ring droid)
   - Skip and push anyway (user will handle in CI)

---

## Phase 7.1: Push Commits

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

## Phase 8: Respond to ALL PR Comments (MANDATORY)

**HARD BLOCK:** This phase is MANDATORY regardless of whether any fixes were applied. Every existing PR comment thread MUST receive a reply.

### Step 8.1: Response Rules (uniform for ALL sources)

**IMPORTANT:** Use the `{finding_id} → {commit_sha}` mapping from Phase 6.

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

### Step 8.2: Refresh Thread Map

Re-fetch the thread map from Step 0.3.1 to get the latest state (threads may have been resolved by pushes or other activity):

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

### Step 8.3: Reply AND Resolve Each Thread (atomically)

**CRITICAL:** For EACH thread, reply and resolve in the SAME step. Never batch "all replies first, then all resolves". The pattern is: reply → resolve → confirm → next thread.

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

### Step 8.4: Verify Zero Unresolved Remain

After all threads are processed, re-run the query from Step 8.2 and confirm ALL threads have `isResolved: true`. If any remain unresolved, reply and resolve them now. Do NOT proceed until zero unresolved threads remain.

### Step 8.5: Hide Fully-Resolved Reviews

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

### Step 8.6: Reply Summary

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

## Phase 9: Final Summary

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
- Integration tests: PASS/SKIPPED — Coverage: XX.X% (threshold: 70%)
- E2E tests: PASS/SKIPPED

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
- [ ] All findings presented with "Finding X of N" in EVERY header
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
- Present findings ONE AT A TIME in severity order, ALWAYS showing "Finding X of N" in EVERY finding header
- Collect ALL decisions first (Phase 5), then apply ALL approved fixes at once (Phase 6)
- Coverage verification and convergence loop run ONLY after all fixes are applied
- No changes without user approval
- BEFORE presenting each finding: deep research is MANDATORY — project patterns, architectural decisions, existing codebase, task focus, user/consumer use cases, UX impact, API best practices, engineering best practices, language-specific idioms. Option A must be the correct approach backed by research evidence, regardless of effort
- If the user responds with a question or disagreement: STOP, research and answer thoroughly RIGHT NOW — do NOT defer to the fix phase or continue to the next finding
- Ring droids are required — do not proceed without them
- Fixes use TDD cycle (RED-GREEN-REFACTOR) with separate commits per finding
- For won't-fix Codacy findings: use the underlying linter's suppression syntax (e.g., `biome-ignore` for Biome, `eslint-disable-next-line` for ESLint, `//nolint` for Go). `codacy:ignore` does NOT exist.
- For won't-fix DeepSource findings: add `// skipcq: <shortcode>` inline and commit
- Response to ALL comments is uniform: commit SHA for fixes, concrete reason for won't-fix
- Do NOT merge the PR — only review and apply fixes
- Push triggers Codacy/DeepSource reanalysis automatically
- The agent NEVER decides whether a finding should be fixed or skipped — the USER always decides
- ALL findings (CRITICAL, HIGH, MEDIUM, and LOW) MUST be presented to the user for decision
- The agent may recommend an option, but MUST wait for user approval via AskUser before proceeding
- Do NOT auto-skip, auto-dismiss, or auto-resolve any finding regardless of severity
- **Next step suggestion (Task Mode only):** After the final summary, inform the user:
  "PR review complete. Next step: run `/optimus-cycle-close-stage-5` to close this task."
