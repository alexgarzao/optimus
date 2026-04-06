---
name: optimus-pr-review
description: >
  PR-aware code review orchestrator. Receives a pull request URL, fetches
  PR metadata (description, branch, changed files, linked issues), enriches
  the review context, and delegates to optimus-deep-review for the actual
  code review with parallel specialist agents.
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
  - optimus-deep-review skill is available
NOT_skip_when: >
  - "The PR is small" → Small PRs still benefit from structured review with PR context.
  - "I already looked at the diff" → Specialist agents catch issues human review misses.
  - "CI passed" → CI checks automated rules; agents review logic, security, and quality.
examples:
  - name: Review a PR by URL
    invocation: "Review this PR: https://github.com/org/repo/pull/42"
    expected_flow: >
      1. Fetch PR metadata (title, description, branch, changed files)
      2. Checkout PR branch
      3. Present PR summary to user
      4. Ask review type (initial/final)
      5. Delegate to optimus-deep-review with PR-scoped changed files and enriched context
  - name: Review current branch PR
    invocation: "Review the PR for this branch"
    expected_flow: >
      1. Detect current branch, find associated open PR via gh CLI
      2. Fetch PR metadata
      3. Standard flow
related:
  complementary:
    - optimus-deep-review
    - optimus-verify-code
  differentiation:
    - name: optimus-deep-review
      difference: >
        optimus-deep-review is a generic code review that works with any scope
        (all files, git diff, directory). optimus-pr-review adds a PR context
        layer (description, linked issues, PR metadata) and delegates to
        optimus-deep-review for the actual review.
    - name: optimus-coderabbit-review
      difference: >
        optimus-coderabbit-review uses CodeRabbit CLI as the source of findings
        with a TDD fix cycle. optimus-pr-review uses specialist agents (via
        optimus-deep-review) and enriches context with PR metadata.
  sequence:
    before:
      - optimus-verify-code
verification:
  automated:
    - command: "which gh 2>/dev/null && echo 'available'"
      description: gh CLI is installed
      success_pattern: available
  manual:
    - PR metadata fetched and presented correctly
    - Review delegated to optimus-deep-review with correct scope
    - PR context (description, linked issues) included in agent prompts
---

# PR Review

PR-aware code review orchestrator. Fetches PR metadata, enriches the review context, and delegates to optimus-deep-review for parallel specialist agent review.

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
- **Existing review comments** — to avoid re-flagging already-discussed issues

### Step 0.3: Fetch Changed Files

Get the list of files changed in the PR:

```bash
gh pr diff <PR_NUMBER_OR_URL> --name-only
```

Read the full content of each changed file for the review agents.

### Step 0.4: Checkout PR Branch

Ensure the working tree matches the PR state:

```bash
gh pr checkout <PR_NUMBER_OR_URL>
```

If already on the correct branch, skip this step. If checkout fails due to uncommitted changes, inform the user and ask them to stash or commit their changes first.

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

### Changed Files
- file1.go
- file2.go
- file3_test.go
```

---

## Phase 2: Determine Review Type

Ask the user which type of review to run. Use `AskUser` tool.

- **Initial** (5 agents) — correctness and critical gaps, suitable for in-progress PRs
- **Final** (7 agents) — full coverage including stack idiomaticity, suitable for PRs ready to merge

---

## Phase 3: Delegate to optimus-deep-review

Invoke the `optimus-deep-review` skill with the following enriched context:

### Context Enrichment

When optimus-deep-review dispatches its agents, each agent prompt MUST include the PR context in addition to the standard review instructions:

```
PR Context:
  - PR #<number>: <title>
  - Purpose: <PR description summary>
  - Linked issues: <list of linked issues with their titles if available>
  - Base branch: <base>
  - Existing review comments: <summary of already-discussed topics to avoid re-flagging>

Review scope: Only the files changed in this PR (listed below).
Review type: Initial / Final (as chosen by user).
```

### Scope Override

Pass the scope to optimus-deep-review as "changed files only" with the exact file list from `gh pr diff --name-only`.

### Execution

Invoke optimus-deep-review using the `Skill` tool. Since this skill replaces Phase 0 (scope/type selection), execution resumes at Phase 1 of optimus-deep-review with the scope and review type already determined:
- Phase 1: Parallel agent dispatch (with PR-enriched prompts)
- Phase 2: Consolidation and triage
- Phase 3: Overview table
- Phase 4: Interactive finding-by-finding resolution
- Phase 5: Final summary

### Additional Post-Review Step

After optimus-deep-review completes its summary, add a PR-specific section:

```markdown
### PR Readiness
- [ ] All CRITICAL/HIGH findings resolved
- [ ] Changes align with PR description and linked issues
- [ ] No unrelated changes included in the PR
- [ ] Test coverage adequate for the changes

**Verdict:** READY FOR MERGE / NEEDS CHANGES
```

---

## Rules

- Always fetch PR metadata before starting the review — the PR description provides essential context for agents
- Never review files outside the PR scope — only files changed in the PR are reviewed
- Include PR description and linked issues in every agent prompt — this helps agents evaluate whether the code matches the stated purpose
- If the PR has existing review comments, summarize them and instruct agents to skip already-discussed topics
- Do NOT merge the PR — only review and present findings
- Do NOT commit fixes to the PR branch without explicit user approval
- If `gh` CLI is not installed, inform the user and suggest installation (e.g., `brew install gh` on macOS). If installed but not authenticated, ask the user to run `gh auth login`
