# Task Executor

## Description

AI agent prompt that executes development tasks end-to-end. Orchestrates sequential phases (backend, frontend, tests), dispatches parallel agents, runs verification gates between phases, conducts interactive code review with the user, and only commits after explicit approval. Stack-agnostic: automatically discovers project commands (lint, test, etc.) before executing.

## Variables

- `{{task_id}}`: Task identifier to execute (e.g., "T-012")

## Skill

See the full installable version at [`cycle-impl-stage-2/skills/optimus-cycle-impl-stage-2/SKILL.md`](../../cycle-impl-stage-2/skills/optimus-cycle-impl-stage-2/SKILL.md).

## Example

```
Run with {{task_id}} = "T-012" to implement the task, going through all execution phases, verification, code review, and commit.
```
