# Optimus

Skills marketplace for Droid (Factory) and Claude Code.

## Task Lifecycle (stages 1-4)

Tasks flow through 4 stages. Each stage is a separate skill that validates the task status before proceeding.

```
Pendente → Validando Spec → Em Andamento → Validando Impl → DONE
           (stage-1-spec)   (stage-2-impl)  (stage-3-review)  (stage-4-close)
```

| Skill | Stage | Description | Command |
|-------|-------|-------------|---------|
| `stage-1-spec` | 1 | Validates task specs against project docs before implementation | `/optimus-stage-1-spec` |
| `stage-2-impl` | 2 | End-to-end task implementation with verification gates | `/optimus-stage-2-impl` |
| `stage-3-review` | 3 | Post-implementation validation with parallel specialist agents | `/optimus-stage-3-review` |
| `stage-4-close` | 4 | Verifies prerequisites and marks task as done | `/optimus-stage-4-close` |

## Review & Verification Skills

| Skill | Description | Command |
|-------|-------------|---------|
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
