# Phase 2: Present Summary + Parallel Agent Dispatch

Loaded by `SKILL.md` after Phase 1 fetches all data. Presents the PR summary to the user, then dispatches review agents in PARALLEL to evaluate code AND existing review comments.

### Phase 2: Present PR Summary

**HARD BLOCK:** If `gh pr checks` showed ANY failing checks, the summary MUST list every failing check name prominently. Do NOT present a summary without the CI Status section. If all checks pass, say so explicitly. If any fail, they MUST appear in bold with the word "FAILING".

```markdown
### PR Review: #<number> — <title>

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

### Phase 3: Parallel Agent Dispatch

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
