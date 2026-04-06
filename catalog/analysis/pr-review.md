# PR Review

## Description

PR-aware code review orchestrator. Receives a pull request URL, fetches PR metadata (description, branch, changed files, linked issues), enriches the review context, and delegates to optimus-deep-review for parallel specialist agent review.

## Variables

None — receives PR URL as input or detects the current branch's PR automatically.

## Skill

See the full installable version at [`pr-review/skills/optimus-pr-review/SKILL.md`](../../pr-review/skills/optimus-pr-review/SKILL.md).

## Example

```
/optimus-pr-review https://github.com/org/repo/pull/42 — fetches PR context and runs deep review.
```
