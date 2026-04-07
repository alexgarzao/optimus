# PR Review

## Description

PR-aware code review orchestrator. Receives a pull request URL, fetches PR metadata, collects existing review comments from all sources (CodeRabbit, human reviewers, CI), dispatches parallel agents to evaluate both code and comments, and presents findings interactively with source attribution. Agents validate or contest existing feedback. Approved fixes are applied in batch at the end.

## Variables

None — receives PR URL as input or detects the current branch's PR automatically.

## Skill

See the full installable version at [`pr-review/skills/optimus-pr-review/SKILL.md`](../../pr-review/skills/optimus-pr-review/SKILL.md).

## Example

```
/optimus-pr-review https://github.com/org/repo/pull/42 — collects comments, evaluates with agents, resolves interactively.
```
