# Import

## Description

Import Ring pre-dev artifacts into optimus format. Reads task specs and subtasks from Ring's pre-dev output, creates tracking overlays (tasks.md + T-NNN.md). Re-runnable — only imports what's new. Never copies content from Ring — only references it.

## Variables

None — automatically discovers Ring pre-dev artifacts in `docs/pre-dev/tasks/` and `docs/pre-dev/subtasks/`.

## Skill

See the full installable version at [`import/skills/optimus-import/SKILL.md`](../../import/skills/optimus-import/SKILL.md).

## Example

```
/optimus-import — reads Ring pre-dev output and creates optimus tracking overlays.
```
