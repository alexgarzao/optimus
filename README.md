# Optimus

Skills marketplace for Droid (Factory) and Claude Code.

## Task Lifecycle

Skills are classified as **Administrative** (run anywhere) or **Execution** (require feature branch).

### Administrative Skills

| Skill | Description | Command |
|-------|-------------|---------|
| `migrate` | Discovers existing task files in any format and converts them to the standard optimus tasks.md format. Runs once per project | `/optimus-migrate` |
| `report` | Task status dashboard. Shows progress, active/blocked/ready tasks, dependency graph, and parallelization opportunities. Read-only | `/optimus-report` |
| `tasks` | Create, edit, remove, reorder, and cancel tasks in tasks.md. Runs on any branch | `/optimus-tasks` |
| `batch` | Pipeline orchestrator: chains stages 1-5 for one or more tasks with user checkpoints between stages | `/optimus-batch` |
| `resolve` | Resolves merge conflicts in tasks.md caused by parallel task execution across feature branches | `/optimus-resolve` |
| `quick-report` | Compact daily status dashboard. Shows version progress, active tasks with criteria progress, ready-to-start, and blocked tasks. Read-only | `/optimus-quick-report` |
| `help` | Lists all available Optimus skills with descriptions, usage commands, and when to use each one | `/optimus-help` |

### Execution Skills (stages 1-5)

Stage-1 creates the workspace (worktree). Stages 2-5 auto-navigate to the task's worktree.

```
Pendente → Validando Spec → Em Andamento → Validando Impl → [Revisando PR] → **DONE**
           (plan)            (build)         (check)          (pr-check)      (done)
```

| Skill | Stage | Description | Command |
|-------|-------|-------------|---------|
| `plan` | 1 | Validates task specifications against project docs before implementation. Catches gaps, contradictions, and test coverage holes | `/optimus-plan` |
| `build` | 2 | End-to-end task implementation with verification gates, code review, and commit approval | `/optimus-build` |
| `check` | 3 | Validates completed task implementation against spec, coding standards, and best practices using parallel specialist agents | `/optimus-check` |
| `pr-check` | 4 | (Optional) Unified PR review orchestrator. Collects PR metadata and existing comments, dispatches agents, applies fixes, resolves threads | `/optimus-pr-check` |
| `done` | 5 | Verifies all prerequisites (commits pushed, PR ready, tests passing) and marks the task as done. Offers to merge the PR during cleanup | `/optimus-done` |

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
