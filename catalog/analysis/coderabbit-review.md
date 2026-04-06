# CodeRabbit Review

## Description

Code review using CodeRabbit CLI as the source of findings. Each finding is resolved with a mandatory TDD cycle (RED-GREEN-REFACTOR) and secondary validation via parallel agents for logic changes. Interactive one-by-one resolution with user approval.

## Variables

None — automatically detects the CodeRabbit config and project test commands.

## Skill

See the full installable version at [`coderabbit-review/skills/optimus-coderabbit-review/SKILL.md`](../../coderabbit-review/skills/optimus-coderabbit-review/SKILL.md).

## Example

```
/optimus-coderabbit-review — runs CodeRabbit and processes findings with TDD.
```
