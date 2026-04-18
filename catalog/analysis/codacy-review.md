# Codacy Review

## Description

Fetches Codacy PR issues via API, categorizes them into false positives (misconfigured rules), genuine findings, and informational issues. Evaluates genuine findings against actual code context, presents results interactively, recommends rule configuration changes, and optionally runs Codacy CLI for local analysis.

## Variables

None — detects PR from current branch automatically. Requires Codacy API token (prompts if not set via `CODACY_API_TOKEN` env var).

## Skill

See the full installable version at [`codacy-review/skills/optimus-codacy-review/SKILL.md`](../../codacy-review/skills/optimus-codacy-review/SKILL.md).

## Example

```
/optimus-codacy-review — fetches Codacy issues for current PR, classifies, reviews genuine findings interactively.
```
