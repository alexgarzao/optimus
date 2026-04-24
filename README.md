# Optimus

Skills marketplace for Droid (Factory) and Claude Code.

**Requires the Ring ecosystem** (droids + pre-dev workflow).

## Task Lifecycle

Skills are classified as **Administrative** (run anywhere) or **Execution** (require feature branch).

### Administrative Skills

| Skill | Description | Command |
|-------|-------------|---------|
| `import` | Import Ring pre-dev artifacts into optimus format. Creates tasks.md with TaskSpec column. Re-runnable — only imports what's new | `/optimus-import` |
| `report` | Task status dashboard. Shows progress, active/blocked/ready tasks, dependency graph, and parallelization opportunities. Read-only | `/optimus-report` |
| `tasks` | Administrative: Create, edit, remove, reorder, cancel, and reopen tasks. Manage versions and move tasks between versions. Runs on any branch | `/optimus-tasks` |
| `batch` | Pipeline orchestrator: chains stages 1-4 for one or more tasks with user checkpoints between stages | `/optimus-batch` |
| `resolve` | Administrative: Resolves merge conflicts in tasks.md caused by parallel task execution across feature branches | `/optimus-resolve` |
| `resume` | Administrative: Resume a task after closing the terminal. Locates/recreates the worktree for a given T-XXX, reports current status, and offers to invoke the next stage. Read-only on state.json except for a user-confirmed Reset-to-Pendente recovery. | `/optimus-resume` |
| `quick-report` | Compact daily status dashboard. Shows version progress, active tasks with current status, ready-to-start, and blocked tasks. Read-only | `/optimus-quick-report` |
| `help` | Lists all available Optimus skills with descriptions, usage commands, and when to use each one | `/optimus-help` |
| `sync` | Sync all Optimus plugins — install new, update existing, remove orphaned. Recommended after new releases | `/optimus-sync` |

### Execution Skills (stages 1-4)

Stage-1 creates the workspace (worktree). Stages 2-4 auto-navigate to the task's worktree.

```
Pendente → Validando Spec → Em Andamento → Validando Impl → DONE
           (plan)            (build)        (review)         (done)
```

| Skill | Stage | Description | Command |
|-------|-------|-------------|---------|
| `plan` | 1 | Validates task specifications against project docs before implementation. Catches gaps, contradictions, and test coverage holes. Creates workspace (branch/worktree) | `/optimus-plan` |
| `build` | 2 | End-to-end task implementation with verification gates, code review, and commit approval | `/optimus-build` |
| `review` | 3 | Validates completed task implementation against spec, coding standards, and best practices using parallel specialist agents | `/optimus-review` |
| `done` | 4 | Requires PR in final state (merged or closed) before marking task done. Cleans up worktree and branch interactively | `/optimus-done` |

## Review & Verification Skills

| Skill | Description | Command |
|-------|-------------|---------|
| `pr-check` | Standalone PR review orchestrator. Collects PR metadata and existing comments (Codacy, DeepSource, CodeRabbit, human), dispatches agents, applies fixes, resolves threads. Does not change task status | `/optimus-pr-check` |
| `deep-doc-review` | Deep review of project documentation. Finds errors, inconsistencies, gaps, and improvements with interactive one-by-one resolution | `/optimus-deep-doc-review` |
| `deep-review` | Parallel code review with consolidation, deduplication, and interactive finding-by-finding resolution. Auto-discovers installed Ring review droids. Flexible scope: entire project, git diff, or specific directory | `/optimus-deep-review` |
| `coderabbit-review` | CodeRabbit-driven code review with TDD fix cycle, secondary validation via review agents, and interactive finding resolution. Requires CodeRabbit CLI | `/optimus-coderabbit-review` |

## Install

```bash
droid plugin marketplace add https://github.com/alexgarzao/optimus
droid plugin install help@optimus
```

Then run `/optimus-sync` to install all plugins at once.

### Staying up to date

Run `/optimus-sync` (or `make sync-plugins`) to sync all plugins — installs new,
updates existing, removes orphaned. This is the recommended way to stay up to date.

## Quick Start

1. **Import tasks:** `/optimus-import` — creates `tasks.md` from Ring pre-dev artifacts
2. **Check status:** `/optimus-report` — see the dashboard with dependencies and parallelization
3. **Validate spec:** `/optimus-plan` — validates the first pending task and creates a workspace
4. **Implement:** `/optimus-build` — implements the task with TDD and verification gates
5. **Review:** `/optimus-review` — validates implementation with parallel specialist agents
6. **Close:** `/optimus-done` — verifies prerequisites and marks the task as done

Or use `/optimus-batch` to chain all stages with checkpoints between them.

**Note:** Execution and review skills require [Ring ecosystem](https://github.com/LerianStudio) droids to be installed.

## Command Aliases

Each plugin includes a short alias for quick access:

| Alias | Command | Alias | Command |
|-------|---------|-------|---------|
| `/sp` | `/optimus-plan` | `/dr` | `/optimus-deep-review` |
| `/bd` | `/optimus-build` | `/ddr` | `/optimus-deep-doc-review` |
| `/rv` | `/optimus-review` | `/cr` | `/optimus-coderabbit-review` |
| `/dn` | `/optimus-done` | `/prc` | `/optimus-pr-check` |
| `/bt` | `/optimus-batch` | `/im` | `/optimus-import` |
| `/qr` | `/optimus-quick-report` | `/rs` | `/optimus-resolve` |
| `/rp` | `/optimus-report` | `/t` | `/optimus-tasks` |
| `/rsm` | `/optimus-resume` | | |

## How it works

Each skill is an installable plugin with:
- `<plugin>/.factory-plugin/plugin.json` — plugin manifest
- `<plugin>/skills/optimus-<skill>/SKILL.md` — full instructions with frontmatter (trigger, prerequisite, etc.)

Future improvements are tracked in `docs/future-improvements.md`.

## Logs

Verification skills (`build`, `review`, `pr-check`, `coderabbit-review`, `deep-review`)
write the full output of `make test`, `make lint`, and similar commands to
`.optimus/logs/<timestamp>-<label>-<pid>.log` instead of streaming it through the
agent context. This cuts agent token usage by ~99% on the success path while
preserving the full log for manual inspection (`cat .optimus/logs/<file>.log`).

The directory is gitignored and auto-pruned during skill execution (logs older than
30 days OR beyond the 500 most-recent files are removed; pruning happens both during
admin/standalone skill init and at every stage agent phase transition). To clear all
logs manually:

```bash
rm .optimus/logs/*.log
```
