# Migrate

## Description

Task format migrator. Discovers existing task files in any format (index-only, inline tasks, individual files, subtask folders) and converts them to the standard optimus tasks.md format. Presents the current state, proposes the conversion, and only applies after user approval. Never deletes original files.

## Variables

None — automatically discovers task files in the project.

## Skill

See the full installable version at [`migrate/skills/optimus-migrate/SKILL.md`](../../migrate/skills/optimus-migrate/SKILL.md).

## Example

```
/optimus-migrate — discovers and converts existing task files to optimus format.
```
