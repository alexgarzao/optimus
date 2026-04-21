# Done

## Description

Stage 5 of the task lifecycle. Verifies all prerequisites (no uncommitted changes, no unpushed commits, PR ready, CI passing, lint and tests passing) before marking a task as DONE. Offers to merge the PR during cleanup. Supports force-close for tasks completed outside the pipeline.

## Variables

- `{{task_id}}`: Task identifier to close (e.g., "T-012")

## Skill

See the full installable version at [`done/skills/optimus-done/SKILL.md`](../../done/skills/optimus-done/SKILL.md).

## Example

```
/optimus-done — runs the 8-check close checklist and marks the task as DONE.
```
