# Resolve

## Description

Resolves merge conflicts in tasks.md caused by parallel task execution. When multiple tasks run simultaneously on different feature branches, each commits status changes to tasks.md. When branches merge, conflicts arise. This skill detects, parses, and resolves those conflicts using the "most advanced status" rule.

## Variables

None — automatically detects conflict markers in tasks.md.

## Skill

See the full installable version at [`resolve/skills/optimus-resolve/SKILL.md`](../../resolve/skills/optimus-resolve/SKILL.md).

## Example

```
/optimus-resolve — resolves tasks.md merge conflicts using most-advanced-status rule.
```
