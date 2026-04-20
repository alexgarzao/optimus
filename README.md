# Optimus

Skills marketplace for Droid (Factory) and Claude Code.

## Task Lifecycle

Skills are classified as **Administrative** (run anywhere) or **Execution** (require feature branch).

### Administrative Skills

| Skill | Description | Command |
|-------|-------------|---------|
| `cycle-migrate` | Discovers and converts existing task files to optimus format | `/optimus-cycle-migrate` |
| `cycle-report` | Task status dashboard with dependency graph and parallelization | `/optimus-cycle-report` |
| `cycle-crud` | Create, edit, remove, and reorder tasks in tasks.md | `/optimus-cycle-crud` |
| `help` | Lists all available skills with descriptions and situational guidance | `/optimus-help` |

### Execution Skills (stages 1-5)

Stage-1 creates the workspace (branch/worktree). Stages 2-5 verify it exists.

```
Pendente → Validando Spec → Em Andamento → Validando Impl → [Revisando PR] → DONE
           (stage-1)          (stage-2)       (stage-3)        (stage-4)       (stage-5)
```

| Skill | Stage | Description | Command |
|-------|-------|-------------|---------|
| `cycle-spec-stage-1` | 1 | Validates specs + creates workspace (branch/worktree) | `/optimus-cycle-spec-stage-1` |
| `cycle-impl-stage-2` | 2 | End-to-end task implementation with verification gates | `/optimus-cycle-impl-stage-2` |
| `cycle-impl-review-stage-3` | 3 | Post-implementation validation with parallel specialist agents | `/optimus-cycle-impl-review-stage-3` |
| `cycle-pr-review-stage-4` | 4 | PR review orchestrator (optional, also works standalone) | `/optimus-cycle-pr-review-stage-4` |
| `cycle-close-stage-5` | 5 | Verifies prerequisites and marks task as done | `/optimus-cycle-close-stage-5` |

## Review & Verification Skills

| Skill | Description | Command |
|-------|-------------|---------|
| `deep-doc-review` | Deep doc review with cross-referencing and interactive resolution | `/optimus-deep-doc-review` |
| `deep-review` | Parallel code review with specialist agents and interactive resolution | `/optimus-deep-review` |
| `coderabbit-review` | Code review with CodeRabbit CLI + TDD cycle + agent validation | `/optimus-coderabbit-review` |
| `verify` | Two-phase code verification (Go, TypeScript, Python, generic) | `/optimus-verify-code` |

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
