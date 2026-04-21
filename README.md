# Optimus

Skills marketplace for Droid (Factory) and Claude Code.

## Task Lifecycle

Skills are classified as **Administrative** (run anywhere) or **Execution** (require feature branch).

### Administrative Skills

| Skill | Description | Command |
|-------|-------------|---------|
| `cycle-migrate` | Discovers existing task files in any format and converts them to the standard optimus tasks.md format. Runs once per project | `/optimus-cycle-migrate` |
| `cycle-report` | Task status dashboard. Shows progress, active/blocked/ready tasks, dependency graph, and parallelization opportunities. Read-only | `/optimus-cycle-report` |
| `cycle-crud` | Create, edit, remove, reorder, and cancel tasks in tasks.md. Runs on any branch | `/optimus-cycle-crud` |
| `cycle-batch` | Pipeline orchestrator: chains stages 1-5 for one or more tasks with user checkpoints between stages | `/optimus-cycle-batch` |
| `cycle-conflict-resolve` | Resolves merge conflicts in tasks.md caused by parallel task execution across feature branches | `/optimus-cycle-conflict-resolve` |
| `help` | Lists all available Optimus skills with descriptions, usage commands, and when to use each one | `/optimus-help` |

### Execution Skills (stages 1-5)

Stage-1 creates the workspace (worktree). Stages 2-5 auto-navigate to the task's worktree.

```
Pendente → Validando Spec → Em Andamento → Validando Impl → [Revisando PR] → **DONE**
           (stage-1)          (stage-2)       (stage-3)        (stage-4)       (stage-5)
```

| Skill | Stage | Description | Command |
|-------|-------|-------------|---------|
| `cycle-spec-stage-1` | 1 | Validates task specifications against project docs before implementation. Catches gaps, contradictions, and test coverage holes | `/optimus-cycle-spec-stage-1` |
| `cycle-impl-stage-2` | 2 | End-to-end task implementation with verification gates, code review, and commit approval | `/optimus-cycle-impl-stage-2` |
| `cycle-impl-review-stage-3` | 3 | Validates completed task implementation against spec, coding standards, and best practices using parallel specialist agents | `/optimus-cycle-impl-review-stage-3` |
| `cycle-pr-review-stage-4` | 4 | (Optional) Unified PR review orchestrator. Collects PR metadata and existing comments, dispatches agents, applies fixes, resolves threads | `/optimus-cycle-pr-review-stage-4` |
| `cycle-close-stage-5` | 5 | Verifies all prerequisites (commits pushed, PR ready, tests passing) and marks the task as done. Offers to merge the PR during cleanup | `/optimus-cycle-close-stage-5` |

## Review & Verification Skills

| Skill | Description | Command |
|-------|-------------|---------|
| `deep-doc-review` | Deep review of project documentation. Finds errors, inconsistencies, gaps, and improvements with interactive one-by-one resolution | `/optimus-deep-doc-review` |
| `deep-review` | Parallel code review with consolidation, deduplication, and interactive finding-by-finding resolution. Supports initial (5 agents) and final (7 agents) review modes | `/optimus-deep-review` |
| `coderabbit-review` | CodeRabbit-driven code review with TDD fix cycle, secondary validation via review agents, and interactive finding resolution | `/optimus-coderabbit-review` |
| `verify` | Two-phase code verification (Go, TypeScript, Python, generic): parallel static analysis + sequential test execution with executive summary | `/optimus-verify-code` |

## Install

```bash
droid plugin marketplace add https://github.com/alexgarzao/optimus
droid plugin install <plugin-name>@optimus
```

## Catalog

Skill reference cards organized by category:

- `catalog/system/` — Orchestration and task execution skills
- `catalog/analysis/` — Analysis and review skills
- `catalog/coding/` — Coding skill cards
- `catalog/writing/` — Writing skill cards

## How it works

Each skill is an installable plugin with:
- `<plugin>/.factory-plugin/plugin.json` — plugin manifest
- `<plugin>/skills/optimus-<skill>/SKILL.md` — full instructions with frontmatter (trigger, prerequisite, etc.)
