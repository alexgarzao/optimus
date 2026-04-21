# PR Review

## Description

PR-aware code review orchestrator. Receives a pull request URL, fetches PR metadata, collects existing review comments from all sources (Codacy, DeepSource, CodeRabbit, human reviewers, CI), dispatches parallel agents to evaluate both code and comments, and presents findings interactively with source attribution. Agents validate or contest existing feedback. Approved fixes are applied with TDD cycle and separate commits per finding, and PR comment replies reference the exact commit SHA. Also works standalone without a task context.

## Variables

None — receives PR URL as input or detects the current branch's PR automatically.

## Skill

See the full installable version at [`pr-check/skills/optimus-pr-check/SKILL.md`](../../pr-check/skills/optimus-pr-check/SKILL.md).

## Example

```
/optimus-pr-check — collects comments from all sources, evaluates with agents, resolves interactively.
```
