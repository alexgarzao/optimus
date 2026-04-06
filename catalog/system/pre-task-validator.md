# Pre-Task Validator

## Description

AI agent prompt that validates task specifications BEFORE implementation begins. Cross-references the spec with reference docs (API, data model, TRD, PRD), detects contradictions, test coverage gaps, observability issues, and ambiguities. Presents findings interactively with resolution options. Analysis only — does not generate code. Stack-agnostic.

## Variables

- `{{task_id}}`: Task identifier to validate (e.g., "T-006")

## Skill

See the full installable version at [`pre-task-validator/skills/optimus-pre-task-validator/SKILL.md`](../../pre-task-validator/skills/optimus-pre-task-validator/SKILL.md).

## Example

```
Run with {{task_id}} = "T-006" to validate the task specification before starting implementation, cross-referencing with api-design, data-model, trd, and prd.
```
