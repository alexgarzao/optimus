# Optimus

Skills marketplace for Droid (Factory) and Claude Code.

**Requires the Ring ecosystem** (droids + pre-dev workflow).

## Task Lifecycle

Skills are classified as **Administrative** (run anywhere) or **Execution** (require feature branch).

### Administrative Skills

| Skill | Description | Command |
|-------|-------------|---------|
| `import` | Import Ring pre-dev artifacts into optimus format. Creates optimus-tasks.md with TaskSpec column. Re-runnable — only imports what's new | `/optimus-import` |
| `report` | Task status dashboard. Shows progress, active/blocked/ready tasks, dependency graph, and parallelization opportunities. Mostly read-only — only writes `.optimus/config.json` defaultScope when user opts in | `/optimus-report` |
| `tasks` | Administrative: Create, edit, remove, reorder, cancel, and reopen tasks. Manage versions and move tasks between versions. Runs on any branch | `/optimus-tasks` |
| `batch` | Pipeline orchestrator: chains stages 1-4 for one or more tasks with user checkpoints between stages | `/optimus-batch` |
| `resolve` | Administrative: Resolves merge conflicts in optimus-tasks.md caused by parallel task execution across feature branches | `/optimus-resolve` |
| `resume` | Administrative: Resume a task after closing the terminal. Locates/recreates the worktree for a given T-XXX, reports current status, and offers to invoke the next stage. Read-only on state.json except for a user-confirmed Reset-to-Pendente recovery. | `/optimus-resume` |
| `quick-report` | Compact daily status dashboard. Shows version progress, active tasks with current status, ready-to-start, and blocked tasks. Mostly read-only — only writes `.optimus/config.json` defaultScope when user opts in | `/optimus-quick-report` |
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

### Droid (Factory)

```bash
droid plugin marketplace add https://github.com/alexgarzao/optimus
droid plugin install help@optimus
```

Then run `/optimus-sync` to install all plugins at once.

### Claude Code

```bash
claude plugin marketplace add https://github.com/alexgarzao/optimus
claude plugin install optimus@optimus
```

Reopen Claude Code (so the new plugin is discovered). All commands are exposed
under the `optimus:` namespace — e.g., `/optimus:plan`, `/optimus:build`,
`/optimus:done`. Aliases keep their short form but are also namespaced:
`/optimus:sp`, `/optimus:bd`, `/optimus:rv`, etc. (see Command Aliases below).

**Note:** On Claude Code there is a single `optimus` plugin instead of 17
separate plugins; running `/optimus-sync` (or `claude plugin update optimus@optimus`)
keeps it up to date as new commands are added.

### Staying up to date

Run `/optimus-sync` (or `make sync-plugins`) to sync all plugins — installs new,
updates existing, removes orphaned. Works for both Droid and Claude Code simultaneously.

## Quick Start

1. **Import tasks:** `/optimus-import` — creates `optimus-tasks.md` from Ring pre-dev artifacts
2. **Check status:** `/optimus-report` — see the dashboard with dependencies and parallelization
3. **Validate spec:** `/optimus-plan` — validates the first pending task and creates a workspace
4. **Implement:** `/optimus-build` — implements the task with TDD and verification gates
5. **Review:** `/optimus-review` — validates implementation with parallel specialist agents
6. **Close:** `/optimus-done` — verifies prerequisites and marks the task as done

Or use `/optimus-batch` to chain all stages with checkpoints between them.

**Note:** Execution and review skills require [Ring ecosystem](https://github.com/LerianStudio) droids to be installed.

## Command Aliases

Each skill includes a short alias for quick access. Droid and Claude Code use
different invocation forms — Droid keeps the bare alias; Claude Code namespaces
it under `optimus:`.

| Alias (Droid) | Claude Code | Command | Alias (Droid) | Claude Code | Command |
|---|---|---|---|---|---|
| `/sp` | `/optimus:sp` | `/optimus-plan` (Droid) / `/optimus:plan` (Claude) | `/dr` | `/optimus:dr` | `/optimus:deep-review` |
| `/bd` | `/optimus:bd` | `/optimus:build` | `/ddr` | `/optimus:ddr` | `/optimus:deep-doc-review` |
| `/rv` | `/optimus:rv` | `/optimus:review` | `/cr` | `/optimus:cr` | `/optimus:coderabbit-review` |
| `/dn` | `/optimus:dn` | `/optimus:done` | `/prc` | `/optimus:prc` | `/optimus:pr-check` |
| `/bt` | `/optimus:bt` | `/optimus:batch` | `/im` | `/optimus:im` | `/optimus:import` |
| `/qr` | `/optimus:qr` | `/optimus:quick-report` | `/rs` | `/optimus:rs` | `/optimus:resolve` |
| `/rp` | `/optimus:rp` | `/optimus:report` | `/t` | `/optimus:t` | `/optimus:tasks` |
| `/rsm` | `/optimus:rsm` | `/optimus:resume` | `/hp` | `/optimus:hp` | `/optimus:help` |
| `/sy` | `/optimus:sy` | `/optimus:sync` | | | |

## How it works

The repo packages the same SKILLs for two platforms, each with its own
marketplace manifest at the repo root:

- `.factory-plugin/marketplace.json` — Droid marketplace (lists 17 plugins)
- `.claude-plugin/marketplace.json` — Claude Code marketplace (lists the
  single `optimus` plugin sourced from `.`)

Per platform:

- **Droid:** 17 individual plugins, one per directory:
  - `.factory-plugin/marketplace.json` at the repo root — enumerates the 17 plugins
  - `<plugin>/.factory-plugin/plugin.json` — per-plugin manifest
  - `<plugin>/skills/optimus-<skill>/SKILL.md` — full instructions with frontmatter
  - `<plugin>/commands/<alias>.md` — optional short alias (redirects to `/optimus-<plugin>`)
- **Claude Code:** ONE plugin (`optimus`) sourced from the repo root:
  - `.claude-plugin/marketplace.json` at the repo root — enumerates the single `optimus` plugin
  - `.claude-plugin/plugin.json` at the repo root — `optimus` plugin manifest
  - Top-level `commands/<plugin>.md` and `commands/<alias>.md` are auto-discovered
    by Claude Code and exposed as `/optimus:<command>` / `/optimus:<alias>`.

The `commands/` directory at the repo root is **generated** by
`scripts/sync-claude-commands.py` from the per-skill `SKILL.md` (and the
optional `<plugin>/commands/<alias>.md`) — run the script after editing a
SKILL or an alias to keep the Claude side in sync. Tests in
`scripts/test_skill_consistency.py` (class `TestClaudeCommandsSync`) enforce
that the script was run before commit.

Future improvements are tracked in `docs/future-improvements.md`.

## Worktree layout

Optimus creates linked git worktrees under `<repo>/.worktrees/<branch-name>/` (gitignored). For project setup, configure your editor to exclude `.worktrees/` from search and indexing:

- **VS Code** (`.vscode/settings.json`):
  ```json
  {
    "search.exclude": { "**/.worktrees": true },
    "files.watcherExclude": { "**/.worktrees/**": true }
  }
  ```
- **IntelliJ:** mark `.worktrees/` as Excluded in Project Structure.

For the full convention (rationale, backwards compatibility, branch-name handling), see [AGENTS.md Protocol: Worktree Location](AGENTS.md#protocol-worktree-location).

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
