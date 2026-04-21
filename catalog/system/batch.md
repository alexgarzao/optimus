# Batch

## Description

Pipeline orchestrator that chains stages 1-5 for one or more tasks sequentially. Handles dependency ordering, worktree context switching, and user checkpoints between stages. Supports re-evaluation of eligibility after each task completes.

## Variables

None — automatically detects eligible tasks from tasks.md.

## Skill

See the full installable version at [`batch/skills/optimus-batch/SKILL.md`](../../batch/skills/optimus-batch/SKILL.md).

## Example

```
/optimus-batch — chains all stages for one or more tasks with checkpoints.
```
