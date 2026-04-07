# Optimus

Skills marketplace for Droid (Factory) and Claude Code.

## Skills

| Skill | Description | Command |
|-------|-------------|---------|
| `pre-task-validator` | Validates task specs against project docs before implementation | `/optimus-pre-task-validator` |
| `task-executor` | End-to-end task execution with verification gates | `/optimus-task-executor` |
| `post-task-validator` | Post-execution validation with parallel specialist agents | `/optimus-post-task-validator` |
| `deep-doc-review` | Deep doc review with cross-referencing and interactive resolution | `/optimus-deep-doc-review` |
| `deep-review` | Parallel code review with specialist agents and interactive resolution | `/optimus-deep-review` |
| `pr-review` | PR-aware review with comment collection, agent evaluation, and source attribution | `/optimus-pr-review` |
| `coderabbit-review` | Code review with CodeRabbit CLI + TDD cycle + agent validation | `/optimus-coderabbit-review` |
| `verify` | Two-phase code verification for Go (static analysis + tests) | `/optimus-verify-code` |

## Install

```bash
droid plugin marketplace add https://github.com/alexgarzao/optimus
droid plugin install <plugin-name>@optimus
```

## Catalog

Skill reference cards organized by category:

- `catalog/system/` — Orchestration and task execution skills
- `catalog/analysis/` — Analysis and review skills

## How it works

Each skill is an installable plugin with:
- `<plugin>/.factory-plugin/plugin.json` — plugin manifest
- `<plugin>/skills/optimus-<skill>/SKILL.md` — full instructions with frontmatter (trigger, prerequisite, etc.)
