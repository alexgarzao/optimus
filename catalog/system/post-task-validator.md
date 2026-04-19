# Post-Task Validator

## Description

AI agent prompt that validates development tasks after execution. Checks spec compliance, coding standards adherence, engineering best practices, test coverage, and production readiness. Dispatches specialist agents in parallel and presents findings interactively with four-lens analysis (UX, task focus, project focus, engineering). Stack-agnostic.

## Variables

- `{{task_id}}`: Task identifier to validate (e.g., "T-012")

## Skill

See the full installable version at [`stage-3-review/skills/optimus-stage-3-review/SKILL.md`](../../stage-3-review/skills/optimus-stage-3-review/SKILL.md).

## Example

```
Run with {{task_id}} = "T-012" to validate the task after execution by task-executor, dispatching review agents in parallel and resolving findings interactively.
```
