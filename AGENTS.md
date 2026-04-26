# Optimus — Agent Instructions

This repository contains installable skill plugins for Droid (Factory) and Claude Code.
Every change to this repo is made by AI agents. This file is the primary context source
for any agent operating here.

## Repository Structure

```
optimus/
├── .factory-plugin/marketplace.json   # Plugin marketplace manifest
├── AGENTS.md                          # THIS FILE — read first
├── README.md                          # Public-facing docs
├── import/                    # Admin: Import external task artifacts (re-runnable)
├── report/                    # Admin: Task status dashboard (read-only)
├── tasks/                      # Admin: Create, edit, remove, reorder tasks
├── batch/                     # Admin: Pipeline orchestrator (stages 1-4)
├── resolve/          # Admin: Resolve optimus-tasks.md merge conflicts
├── plan/              # Execution Stage 1: Spec validation + workspace creation
├── build/              # Execution Stage 2: Task implementation
├── review/      # Execution Stage 3: Implementation review
├── pr-check/         # Standalone PR review tool (does not change task status)
├── done/             # Execution Stage 4: Close task (verify & mark done)
├── deep-review/                       # Parallel code review (no PR context)
├── deep-doc-review/                   # Documentation review
├── coderabbit-review/                 # CodeRabbit CLI + TDD cycle
├── help/                              # Skill discovery and help
├── sync/                              # Plugin sync (install, update, remove)
├── quick-report/                      # Compact daily status dashboard
├── scripts/                           # Build tools (inline-protocols.py, tests)
├── Makefile                           # test, lint, check-inline, sync-plugins targets
└── docs/                              # Project documentation
    └── future-improvements.md         # Tracked improvements not yet prioritized
```

Each plugin follows the same layout:
```
<plugin>/
├── .factory-plugin/plugin.json        # Plugin manifest (name, description)
└── skills/optimus-<skill>/SKILL.md    # Full skill instructions with YAML frontmatter
```

## How Skills Work

A SKILL.md file is the complete instruction set for an agent. It contains:
- **YAML frontmatter**: name, description, trigger conditions, skip conditions, prerequisites, examples
- **Phases**: sequential steps the agent must follow
- **Rules**: constraints the agent must obey

When a user installs a plugin and invokes the skill, the SKILL.md content is injected
into the agent's context as instructions.

## Design Principles

### 0. Ring Ecosystem Required
Optimus requires the Ring ecosystem (droids + pre-dev workflow). All tasks flow
through Ring's pre-dev for specification, and Ring droids for execution. There is
no standalone mode. Ring pre-dev artifacts are the source of truth for task content.
The location of Ring artifacts is configurable via `tasksDir` in `.optimus/config.json`
(default: `docs/pre-dev`). Optimus tracks structural data (dependencies, versions,
priorities) in `<tasksDir>/optimus-tasks.md` — co-located with the Ring pre-dev artifacts —
and operational state (status, branch) in `.optimus/state.json` (gitignored). The
`TaskSpec` column in optimus-tasks.md points to each task's Ring spec. `tasksDir` may live
in the same git repo as the project code (default) or in a **separate git repo** for
teams that keep task tracking independent from production code.

### 1. User Authority Over Decisions
The agent NEVER decides whether a finding should be fixed or skipped. ALL findings
(CRITICAL, HIGH, MEDIUM, LOW) MUST be presented to the user for decision. The agent
recommends but the user decides.

### 2. No False Convergence
Convergence loops use the **Full Roster Model**: round 1 dispatches all specialist agents
in parallel. Rounds 2+ dispatch the **same agent roster** via `Task` tool, each with zero
prior context, and are gated behind explicit user prompts (opt-in). The orchestrator
deduplicates, not the sub-agents. LOW severity is NOT a stop condition — all findings
are presented to the user.

### 3. Atomic Thread Resolution
When replying to PR threads: reply → resolve → confirm per thread. Never batch
"all replies first, then all resolves".

### 4. Source-Aware Reply Methods
PR review threads from native GitHub Apps (deepsource-io, codacy-production) require
GraphQL for replies (REST returns 404). Workflow comments (github-actions[bot]) use REST.
Always classify threads by author login before replying.

### 5. CI Checks Are Findings
Any failing check shown by `gh pr checks` is a finding (HIGH severity). This includes
Codacy, DeepSource, Merge Gate — not just GitHub Actions workflows. The agent must not
rationalize these away.

## Editing Rules

### SKILL.md Files
- Preserve YAML frontmatter structure (---, name, description, trigger, skip_when, etc.)
- Keep phase numbering sequential starting from 1 (Phase 1, Phase 2, ...)
- Step numbering within phases: Step X.Y where X matches the phase number (e.g., Step 1.3, Step 2.2). Sub-steps use X.Y.Z notation (e.g., Step 1.0.3) when a step needs sub-steps for organization. Deeper nesting (X.Y.Z.W) is allowed but discouraged — prefer promoting to a separate step
- Use `**HARD BLOCK:**` for steps the agent must never skip
- Use `**CRITICAL:**` for rules that override normal behavior
- Use `**IMPORTANT:**` for emphasis without hard blocking
- When adding anti-rationalization rules, list specific excuses the agent might use
- Include concrete command examples (bash blocks) — agents follow examples better than prose
- Always include example output showing what success/failure looks like

### marketplace.json
- Must list ALL plugins in the repo
- `source` paths are relative to repo root (e.g., `./pr-check`)
- Description should be concise (1-2 sentences)

### plugin.json
- Located at `<plugin>/.factory-plugin/plugin.json`
- Must match the marketplace.json entry

### README.md
- Keep the install instructions and skill table up to date
- Update when adding/removing plugins

## Multi-Platform Support

Optimus skills can be installed on two platforms simultaneously, each using its
native plugin system:

| Aspect | Droid (Factory) | Claude Code |
|--------|-----------------|-------------|
| **Install mechanism** | `droid plugin install/update/uninstall` | `claude plugin install/update/uninstall` |
| **Marketplace** | `.factory-plugin/marketplace.json` (added via `droid plugin marketplace add`) | `.claude-plugin/marketplace.json` (added via `claude plugin marketplace add`) |
| **Skill discovery** | Plugin registry | Plugin registry |
| **Plugin name format** | Bare (`plan`, `build`) | Prefixed (`optimus-plan`, `optimus-build`) |
| **Command aliases** | Supported (`/sp`, `/bd`, etc.) | Not supported (platform limitation) |
| **Invocation** | `/optimus-<name>` or alias | `/optimus-<name>` only |

The sync script (`sync/scripts/sync-user-plugins.sh`) detects which platforms
are available and syncs both in a single run via the platforms' native plugin APIs.

Platform detection:
- **Droid**: `command -v droid` succeeds
- **Claude Code**: `command -v claude` succeeds

At least one platform must be available. The script uses the platform's
marketplace cache as its source of truth for expected plugins.

### Marketplace JSON resolution

The script resolves the EXPECTED plugin list from one of three sources, in priority order:

1. **Droid cache**: `~/.factory/marketplaces/optimus/.factory-plugin/marketplace.json`
2. **Claude Code cache**: `~/.claude/plugins/marketplaces/optimus/.claude-plugin/marketplace.json`
3. **In-repo**: when running from a clone of the Optimus repo, the local `.factory-plugin/marketplace.json` (preferred) or `.claude-plugin/marketplace.json`.

Both schemas list the same set of plugins, but with different name conventions
(see table above). The script normalizes to bare names internally.

### Claude Code specifics

- Skills are installed via `claude plugin install <name>@optimus --scope user`
- Plugin name format on Claude Code is `optimus-<plugin>` (e.g., `optimus-plan`)
- Updates and uninstalls go through `claude plugin update/uninstall`
- Claude Code manages its own plugin cache at `~/.claude/plugins/cache/optimus/`;
  the script does not create or manage `~/.optimus/repo/` for Claude Code

### Environment variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `OPTIMUS_REPO_URL` | `https://github.com/alexgarzao/optimus` | Repo URL (used for non-default forks; both platforms honor) |
| `OPTIMUS_MARKETPLACE_NAME` | `optimus` | Droid marketplace identifier |
| `OPTIMUS_DROID_TIMEOUT` | `60` | Per-call timeout for Droid plugin operations (seconds) |
| `CLAUDE_MARKETPLACE_FILE` | `~/.claude/plugins/marketplaces/optimus/.claude-plugin/marketplace.json` | Override Source 2 location (mostly for tests) |

## Plugin Lifecycle

### Dual-platform parity (Claude Code ↔ Droid) — ENFORCED

Every Optimus plugin MUST ship surfaces for both platforms. This is enforced
by the `TestDualPlatformParity` class in `scripts/test_skill_consistency.py`,
which asserts three invariants:

1. **Marketplace parity** — every plugin in `.claude-plugin/marketplace.json`
   must also be in `.factory-plugin/marketplace.json` (Claude uses
   `optimus-<name>`, Droid uses bare `<name>`; the test normalizes the prefix).
2. **Surface parity** — every plugin must ship both `<plugin>/skills/optimus-<plugin>/SKILL.md`
   (Claude Code) and `<plugin>/.factory-plugin/plugin.json` (Droid).
3. **Command alias integrity** — every `<plugin>/commands/<alias>.md` must
   correspond to a real plugin in the marketplace AND its body must redirect
   to `/optimus-<plugin>`. (Aliases are Claude Code only — Droid does not
   support slash-command aliases.)

A plugin that only ships one platform's surface will fail tests and CI. Without
these guards, a contributor could add a plugin to one marketplace and forget
the other; the sync script reads ONE marketplace and applies it to both
platforms, so the missing-side plugin would silently disappear from the
discovered set on `/optimus-sync`.

### Adding a new plugin
1. Add directory to repo (e.g., `myplugin/skills/optimus-myplugin/SKILL.md`)
2. Add entry to `.factory-plugin/marketplace.json` (bare name: `myplugin`)
3. Add entry to `.claude-plugin/marketplace.json` (prefixed name: `optimus-myplugin`, source `./myplugin`)
4. Update README plugin list if applicable
5. Commit, push
6. **Droid**: `droid plugin install myplugin@optimus`
7. **Claude Code**: `claude plugin install optimus-myplugin@optimus`
8. Or just run `/optimus-sync` after the marketplace caches are refreshed (`droid plugin marketplace update optimus` and `claude plugin marketplace update optimus`)

### Updating a plugin
1. Edit the SKILL.md
2. Commit, push
3. Run `/optimus-sync` (or `make sync-plugins`) — script handles both platforms

### Removing a plugin
1. Remove directory
2. Remove from BOTH `.factory-plugin/marketplace.json` AND `.claude-plugin/marketplace.json`
3. Update README if applicable
4. Commit, push
5. Run `/optimus-sync` to remove the orphan from both platforms

**Note for end users:** Claude Code plugins do NOT auto-update. Users must run
`/optimus-sync` to receive removed plugins (orphan removal) and updates. The
`installed_plugins.json` cache in `~/.claude/plugins/` tracks installed state
between sessions.

### Syncing all plugins (for end users)
Run `/optimus-sync` or `make sync-plugins`. This command:
- Detects available platforms (Droid, Claude Code, or both)
- Refreshes the marketplace cache on each available platform
- Installs new plugins that were added to the marketplace
- Removes orphaned plugins that were removed from the marketplace
- Updates all existing plugins (with automatic scope conflict resolution on Droid)
- Shows a per-platform summary

This is the recommended way for end users to stay up to date.

## optimus-tasks.md Format

Every project using the cycle pipeline MUST have an `optimus-tasks.md` file. This is the single
source of truth for task tracking.

### File Location

Optimus splits its files into two trees:

**Operational tree (`.optimus/`) — 100% gitignored, per-user/per-machine:**

```
.optimus/
├── config.json          # gitignored — optional overrides (tasksDir, defaultScope)
├── state.json           # gitignored — operational state (status, branch per task)
├── stats.json           # gitignored — stage execution counters per task
├── sessions/            # gitignored — session state for crash recovery
└── reports/             # gitignored — exported reports
```

**Planning tree (`<tasksDir>/`) — versioned, shared with the team:**

```
<tasksDir>/              # default: docs/pre-dev/
├── optimus-tasks.md     # versioned — structural task data (NO status, NO branch)
├── tasks/               # versioned — Ring pre-dev task specs (task_001.md, ...)
└── subtasks/            # versioned — Ring pre-dev subtask specs (T-001/, ...)
```

**Configuration** (optional) is stored in `.optimus/config.json`:

```json
{
  "tasksDir": "docs/pre-dev",
  "defaultScope": "ativa"
}
```

- **`tasksDir`** (optional): Path to the Ring pre-dev artifacts root. Default:
  `docs/pre-dev`. The import and stage agents look for `optimus-tasks.md`, `tasks/`, and
  `subtasks/` inside this directory. Can point to a path inside the project repo
  (default case) OR to a path in a separate git repo (for teams that separate task
  tracking from code).
- **`defaultScope`** (optional): Default version scope used by `report` and `quick-report`
  when the user does not specify one in the invocation. Valid values: `ativa`, `upcoming`,
  `all`, or a specific version name (must exist in the Versions table). When set, skills
  skip the "Which version scope do you want to see?" prompt. See Protocol: Default Scope
  Resolution.

Since `config.json` is gitignored, it exists ONLY when the user overrides a default.
Projects using the defaults do not need a `config.json`.

**Tasks file** is always at `<tasksDir>/optimus-tasks.md` (derived from `tasksDir`).

**Operational state** is stored in `.optimus/state.json` (gitignored):

```json
{
  "T-001": { "status": "DONE", "branch": "feat/t-001-setup-auth", "updated_at": "2025-01-15T10:30:00Z" },
  "T-003": { "status": "Em Andamento", "branch": "feat/t-003-user-registration", "updated_at": "2025-01-16T14:00:00Z" }
}
```

- Each key is a task ID. A task with no entry is `Pendente` (implicit default).
- `status`: current pipeline stage (see Valid Status Values).
- `branch`: the derived branch name, stored for quick reference (always re-derivable).
- Stage agents read and write this file — never optimus-tasks.md — for status changes.
- If state.json is lost, status can be reconstructed: task with a worktree = in progress,
  without = Pendente. The agent asks the user to confirm before proceeding.

**Stage execution stats** are stored in `.optimus/stats.json` (gitignored):

```json
{
  "T-001": { "plan_runs": 2, "review_runs": 3, "last_plan": "2025-01-15T10:30:00Z", "last_review": "2025-01-16T14:00:00Z" },
  "T-002": { "plan_runs": 1, "review_runs": 0 }
}
```

- Each key is a task ID. Values track how many times `plan` and `review` executed on the task.
- A high `plan_runs` signals unclear or problematic specs. A high `review_runs` signals
  complex review cycles or specification gaps.
- The file is created on first use by `plan` or `review`. If missing, agents treat all
  counters as 0.
- `report` reads this file to display churn metrics.

Agents resolve paths:
1. **Read `.optimus/config.json`** for `tasksDir` if it exists. Fallback: `docs/pre-dev`.
2. **Tasks file:** `${tasksDir}/optimus-tasks.md` (derived, not configurable separately).
3. **If `<tasksDir>/optimus-tasks.md` not found:** **STOP** and suggest running `import` to create one.

Everything inside `.optimus/` is gitignored. The planning tree (`<tasksDir>/optimus-tasks.md`,
`<tasksDir>/tasks/`, `<tasksDir>/subtasks/`) is versioned (structural data shared with
the team) — but the repo that versions it depends on `tasksDir`: if `tasksDir` is inside
the project repo, it is committed alongside the code; if `tasksDir` is in a separate
repo, it is committed there.

## Worktree Location Convention

Optimus creates linked git worktrees during the task lifecycle:

- `/optimus-plan` creates a worktree when a task starts (Step 1.0.5).
- `/optimus-resume` creates a worktree on recovery if branch exists but worktree is missing (Step 3.3).
- `Protocol: Workspace Auto-Navigation` creates a worktree as a fallback when an Optimus skill is invoked from the default branch and the task's worktree is missing.

**Canonical path:** `${MAIN_WORKTREE}/.worktrees/<branch-name>` — gitignored (see project `.gitignore`), project-rooted, and resolved against the main worktree (so the path is correct even when invoked from a linked worktree).

**Why nested under the project repo:**

| Concern | Resolution |
|---|---|
| Discoverability | All worktrees for a project are listed by `ls <repo>/.worktrees/` |
| Cleanup lifecycle | Removing the project directory also removes all worktrees |
| `.optimus/` companion | Both `.optimus/` (operational state) and `.worktrees/` (operational worktrees) live inside the repo, gitignored — same pattern |
| Cross-repo safety | Worktrees always belong to the **project repo**, never the tasks repo (separate-repo `tasksDir` config does not affect worktree location) |
| Main-worktree resolution | `git worktree list --porcelain` correctly identifies main as the first entry regardless of nested linked worktrees — Protocol: Resolve Main Worktree Path is unaffected |

**IDE exclusion (recommended):** add `.worktrees/` to your editor's search/index exclusions to prevent double-indexing the same files in main and linked worktrees. Examples:

- VS Code (`.vscode/settings.json`): `"search.exclude": { "**/.worktrees": true }, "files.watcherExclude": { "**/.worktrees/**": true }`
- IntelliJ: mark `.worktrees/` as Excluded in Project Structure.

**Backwards compatibility:** existing worktrees in older locations (e.g., sibling `../<repo>-<task>`) continue to work — `git worktree list` finds them regardless of path. New worktrees created by `/optimus-plan` and resume's recovery land in `.worktrees/`. There is no forced migration; users may relocate manually with `git worktree move <old-path> <repo>/.worktrees/<branch-name>` when convenient.

### Protocol: Resolve Main Worktree Path

**Referenced by:** all skills that read or write `.optimus/` operational files (state.json, stats.json, sessions, reports, logs, and checkpoint markers).

**Why:** `.optimus/` is gitignored. Git does NOT propagate ignored files across linked worktrees (`git worktree add` creates a sibling working tree but does not share gitignored files). When a skill runs from a linked worktree (the common case for `/optimus-build`, `/optimus-review`, `/optimus-done` which default to the task's worktree), reads and writes against `.optimus/state.json` resolve to the worktree's isolated copy. Updates never reach the main worktree. When the linked worktree is later removed (e.g., by `/optimus-done` cleanup), the writes are lost — silent data loss.

**Recipe:**

```bash
MAIN_WORKTREE="$(git worktree list --porcelain 2>/dev/null | awk '/^worktree / {print $2; exit}')"
if [ -z "$MAIN_WORKTREE" ]; then
  echo "ERROR: Cannot determine main worktree — not in a git repository." >&2
  exit 1
fi
```

The first `worktree` line in `git worktree list --porcelain` is always the main worktree (where the bare `.git/` directory or the repo's HEAD lives), regardless of where the command is run from.

**Path resolution pattern:**

After resolving `MAIN_WORKTREE`, every `.optimus/` path MUST be prefixed:

```bash
# RIGHT (works from any worktree):
STATE_FILE="${MAIN_WORKTREE}/.optimus/state.json"
SESSION_FILE="${MAIN_WORKTREE}/.optimus/sessions/session-${TASK_ID}.json"
STATS_FILE="${MAIN_WORKTREE}/.optimus/stats.json"
mkdir -p "${MAIN_WORKTREE}/.optimus/sessions" \
         "${MAIN_WORKTREE}/.optimus/reports" \
         "${MAIN_WORKTREE}/.optimus/logs"

# WRONG (resolves against PWD, breaks in linked worktrees):
STATE_FILE=".optimus/state.json"
SESSION_FILE=".optimus/sessions/session-${TASK_ID}.json"
STATS_FILE=".optimus/stats.json"
mkdir -p .optimus/sessions .optimus/reports .optimus/logs
```

**What does NOT need this protocol:**

- `<tasksDir>/optimus-tasks.md` and `<tasksDir>/tasks/`, `<tasksDir>/subtasks/` — versioned content, propagated by git across worktrees automatically.
- `.optimus/config.json` — when **versioned** (legacy projects), it propagates via git; when **gitignored** (current default), it suffers the same isolation as state.json. **Treat `.optimus/config.json` as gitignored and resolve via `$MAIN_WORKTREE` for safety in current projects** — the cost is a single `git worktree list` call.
- `.gitignore` itself — versioned, propagated via git.

**Idempotency:** the resolution is read-only against git metadata; safe to call multiple times in the same skill execution. Cache `MAIN_WORKTREE` in a local variable rather than re-running `git worktree list` for each path.

Skills reference this as: "Resolve main worktree — see AGENTS.md Protocol: Resolve Main Worktree Path."

### Format Marker

The **first line** of `optimus-tasks.md` MUST be the format marker:

```
<!-- optimus:tasks-v1 -->
```

This marker tells agents that the file is in valid optimus format. Agents check this
line FIRST — if it's missing, the file is treated as non-optimus format and the agent
suggests running `/optimus-import`.

### Format:

```markdown
<!-- optimus:tasks-v1 -->
# Tasks

## Versions
| Version | Status | Description |
|---------|--------|-------------|
| MVP | Ativa | Core functionality for launch |
| v2 | Próxima | Post-launch improvements |
| Futuro | Backlog | Ideas not yet scheduled |

| ID | Title | Tipo | Depends | Priority | Version | Estimate | TaskSpec |
|----|-------|------|---------|----------|---------|----------|----------|
| T-001 | Setup auth module | Feature | - | Alta | MVP | S | tasks/task_001.md |
| T-002 | User registration API | Feature | T-001 | Alta | MVP | M | tasks/task_002.md |
| T-003 | Login page | Feature | T-001 | Alta | MVP | M | tasks/task_003.md |
| T-004 | Password reset flow | Fix | T-002, T-003 | Media | v2 | L | tasks/task_004.md |
| T-005 | E2E auth tests | Test | T-002, T-003 | Media | MVP | S | tasks/task_005.md |
```

The `TaskSpec` column contains the path to the Ring pre-dev task spec, **relative to
`tasksDir`**. Stage agents resolve the full path as `<tasksDir>/<TaskSpec>`. The subtasks
directory is derived automatically: if TaskSpec is `tasks/task_001.md`, the subtasks
directory is `subtasks/T-001/` (relative to `tasksDir`).

### Column Specification

| Column | Required | Description |
|--------|----------|-------------|
| ID | Yes | Unique identifier. Format: `T-NNN` (e.g., T-001, T-042) |
| Title | Yes | Short description of the task |
| Tipo | Yes | Task type: `Feature`, `Fix`, `Refactor`, `Chore`, `Docs`, or `Test` |
| Depends | Yes | Comma-separated list of task IDs this task depends on. `-` if no dependencies |
| Priority | Yes | `Alta`, `Media`, or `Baixa` |
| Version | Yes | Must match a version name from the Versions table |
| Estimate | No | Task size estimate. Free text (e.g., `S`, `M`, `L`, `XL`, `2h`, `1d`). `-` if not estimated |
| TaskSpec | Yes | Path to Ring pre-dev task spec, relative to `tasksDir`. `-` if not yet linked |

**NOTE:** Status and Branch are NOT stored in optimus-tasks.md. They live in `.optimus/state.json`
(gitignored). See Protocol: State Management for read/write operations.

### Valid Tipo Values

| Tipo | Meaning | Conventional commit prefix |
|------|---------|---------------------------|
| `Feature` | New functionality | `feat` |
| `Fix` | Bug fix | `fix` |
| `Refactor` | Internal improvement, no behavior change | `refactor` |
| `Chore` | Infra, config, CI, dependencies | `chore` |
| `Docs` | Documentation only | `docs` |
| `Test` | Add/improve tests without changing production code | `test` |

### Conventional Commits (PR Titles and Commit Messages)

All PR titles and commit messages MUST follow the **Conventional Commits 1.0.0**
specification (https://www.conventionalcommits.org/en/v1.0.0/).

**Format:**
```
<type>[optional scope]: <description>
```

- **type** (REQUIRED): one of the prefixes from the Tipo table above (`feat`, `fix`,
  `refactor`, `chore`, `docs`, `test`). Additional types allowed by the spec: `build`,
  `ci`, `style`, `perf`.
- **scope** (OPTIONAL): a noun in parentheses describing the section of the codebase,
  e.g., `feat(auth):`, `fix(parser):`. For task-linked PRs, the task ID is a valid scope:
  `feat(T-003):`.
- **description** (REQUIRED): short imperative summary after the colon+space.
- **`!`** (OPTIONAL): append before `:` to signal a breaking change, e.g., `feat(api)!:`.
- Types are **lowercase**.

**PR title examples (task-linked):**
```
feat(T-003): add user registration API
fix(T-007): prevent duplicate login sessions
refactor(T-012): extract auth middleware into shared module
chore(T-015): upgrade Go to 1.22
docs(T-020): add API reference for payments endpoint
test(T-025): add E2E tests for checkout flow
```

**PR title examples (standalone / no task):**
```
feat: add dark mode toggle
fix: resolve race condition in request handler
feat(api)!: change authentication response format
```

**Deriving the type from Tipo:** When a PR is linked to a task, the `type` in the PR
title MUST match the task's Tipo mapping (Feature→`feat`, Fix→`fix`, etc.). If the PR
covers multiple tasks, use the type of the primary/largest change.

**Administrative commits (optimus-tasks.md structural changes):** Structural changes to optimus-tasks.md
(new task, dependency edit, version move) use `chore(tasks):` regardless of the task's
Tipo. Status changes are NOT committed — they live in state.json (gitignored).

**Reference:** Conventional Commits 1.0.0 — https://www.conventionalcommits.org/en/v1.0.0/

### Valid Status Values (stored in state.json)

Status lives in `.optimus/state.json`, NOT in optimus-tasks.md. A task with no entry in
state.json is implicitly `Pendente`.

| Status | Set by | Meaning |
|--------|--------|---------|
| `Pendente` | Initial (implicit) | Not started — no entry in state.json |
| `Validando Spec` | plan | Spec being validated |
| `Em Andamento` | build | Implementation in progress |
| `Validando Impl` | review | Implementation being reviewed |
| `DONE` | done | Completed |
| `Cancelado` | tasks, done | Task abandoned, will not be implemented |

**Administrative status operations** (managed by tasks, not by stage agents):
- **Reopen:** `DONE` → `Pendente` (remove entry from state.json) or `Em Andamento` (if worktree exists) — when a bug is found after close. Also accepts `Cancelado` → `Pendente` — when a cancellation decision is reversed.
- **Advance:** move forward one stage — when work was done manually outside the pipeline
- **Demote:** move backward one stage — when rework is needed after review
- **Cancel:** any non-terminal → `Cancelado` — task will not be implemented

These operations require explicit user confirmation.

### Dependency Rules

1. **A task can only start if ALL its dependencies are `DONE`**. If any dependency
   is not done, the task is BLOCKED. `Cancelado` does NOT satisfy dependencies —
   if a dependency is cancelled, the dependent task is blocked until the dependency
   is removed or replaced.
2. **Dependencies are by task ID**, not by status. `Depends: T-001, T-003` means
   both T-001 AND T-003 must be `DONE` before this task can start.
3. **`-` means no dependencies** — the task can start immediately.
4. **Circular dependencies are invalid** — agents must detect and refuse them.
5. **The execution order is determined by dependencies + status**, NOT by the order
   of rows in the table. Agents must compute the dependency graph to find which
   tasks are ready.

### Task Spec Resolution

Every task MUST have a Ring pre-dev reference in the `TaskSpec` column. Stage agents
(plan, build, review) resolve the full path as `<tasksDir>/<TaskSpec>` and read the
referenced file for objective, acceptance criteria, and implementation details.

The subtasks directory is derived automatically from the TaskSpec path:
- TaskSpec: `tasks/task_001.md` → Subtasks: `<tasksDir>/subtasks/T-001/`
- The `T-NNN` identifier is extracted from the task spec filename convention

Agents read objective and acceptance criteria directly from the Ring source files.
The optimus-tasks.md table only tracks structural data (dependencies, versions, priorities)
— it does NOT duplicate content from Ring.

### Version Management

The `## Versions` section in optimus-tasks.md is **mandatory** and defines the available versions
(milestones) for the project. It is managed by `tasks` (version operations).

#### Versions Table

| Column | Required | Description |
|--------|----------|-------------|
| Version | Yes | Version name (free text, e.g., `MVP`, `v2`, `Sprint 3`, `Futuro`) |
| Status | Yes | One of: `Ativa`, `Próxima`, `Planejada`, `Backlog`, `Concluída` |
| Description | Yes | Short description of the version's scope |

#### Valid Version Status Values

| Status | Meaning |
|--------|---------|
| `Ativa` | Current focus — auto-detect and reports prioritize tasks in this version |
| `Próxima` | Next cycle — fallback for auto-detect when no Ativa tasks are available |
| `Planejada` | Planned for the future |
| `Backlog` | Ideas not yet scheduled |
| `Concluída` | All tasks delivered, version complete |

#### Version Rules

1. **Exactly one `Ativa` version** at any time. Agents refuse to set two versions as `Ativa`.
   **At most one `Próxima` version** at any time. If setting a new `Próxima`, the existing one
   is demoted to `Planejada` (with user confirmation).
2. **Version blocks execution** — a task can only be executed if it belongs to the `Ativa`
   version. When a stage agent detects a task outside the active version, it offers to move
   the task to the active version or cancel. See Protocol: Active Version Guard.
3. **Cross-version dependencies are allowed** — T-003 (v2) can depend on T-001 (MVP).
   The dependency system already validates that dependencies are `DONE`.
4. **Moving tasks between versions** does not alter Depends, Priority, or any other field (status in state.json is also unchanged).
5. **Tasks keep their version when DONE** — they are not moved automatically.
6. **Version lifecycle is manual** — the user changes version status via `tasks`.
   `report` shows progress but never alters version status.
7. **Every task must reference a valid version** — the Version column value must exist
   in the Versions table. Agents validate this during format validation.
8. **Auto-detect priority**: when auto-detecting the next task, stages 1-2 prioritize
   tasks from the `Ativa` version, then `Próxima`, then any other version (with a warning).

### Format Validation

Every stage agent (1-4) MUST validate the optimus-tasks.md format before operating:
1. **First line** is `<!-- optimus:tasks-v1 -->` (format marker)
2. A `## Versions` section exists with a table containing columns: Version, Status, Description
3. All Version Status values are valid (`Ativa`, `Próxima`, `Planejada`, `Backlog`, `Concluída`)
4. Exactly one version has Status `Ativa`
5. At most one version has Status `Próxima`
6. A markdown table exists with columns: ID, Title, Tipo, Depends, Priority, Version (Estimate and TaskSpec are optional — tables without them are still valid). **Status and Branch columns are NOT expected** — they live in state.json.
7. All task IDs follow the `T-NNN` pattern
8. All Tipo values are one of: `Feature`, `Fix`, `Refactor`, `Chore`, `Docs`, `Test`
9. All Depends values are either `-` or comma-separated valid task IDs that exist as rows in the tasks table (not just matching `T-NNN` pattern — the referenced task must actually exist)
10. All Priority values are one of: `Alta`, `Media`, `Baixa`
11. All Version values reference a version name that exists in the Versions table
12. No duplicate task IDs
13. No circular dependencies in the dependency graph (e.g., T-001 → T-002 → T-001)

If the format marker is missing or validation fails, the agent must **STOP** and suggest
running `/optimus-import` to fix the format. Do NOT attempt to interpret malformed data.

14. No unescaped pipe characters (`|`) in task titles (breaks markdown table parsing)
15. **Empty table handling:** If the tasks table exists but has zero data rows (only headers),
format validation PASSES. Stage agents (1-4) MUST check for this condition immediately after
format validation and before task identification. If zero data rows: **STOP** and inform the
user: "No tasks found in optimus-tasks.md. Use `/optimus-tasks` to create a task or `/optimus-import`
to import from Ring pre-dev." Do NOT proceed to task identification with an empty table.

**NOTE:** For circular dependency detection (item 13), trace the full dependency chain for
each task. If any task appears twice in the chain, a cycle exists. Report ALL tasks involved
in the cycle so the user can fix it with `/optimus-tasks`.

### Parallelization

Tasks with no dependencies or all dependencies satisfied can run in parallel.
The report agent computes and displays parallelization opportunities.

---

## Task Lifecycle

Tasks flow through 4 stages. Status lives in `.optimus/state.json`
(gitignored). Each stage is a separate skill. The optimus-tasks.md file contains only structural
data — no stage agent commits to optimus-tasks.md for status changes.

```
Pendente → Validando Spec → Em Andamento → Validando Impl → DONE
           (plan)            (build)        (review)         (done)

Any status → Cancelado  (via tasks cancel operation)
```

**NOTE:** pr-check exists as a standalone tool (like deep-review) for reviewing PRs.
It does NOT change task status and is NOT part of the pipeline stages.

### Rules

1. **Each agent changes status ONLY at the start** — when the agent is invoked, it
   updates the status in `state.json` to its stage. It NEVER advances to the next stage.
   Status changes are NOT committed — they are written to state.json (gitignored).
2. **Only the user decides to move to the next stage** — by manually invoking the
   next agent. Agents may suggest but NEVER auto-invoke the next stage.
3. **Status never goes backwards** — if a stage fails, the agent keeps working in
   the current status until it succeeds or the user stops it.
4. **Anti-pulo** — each agent validates that the task is in the expected predecessor
   status (read from state.json) before proceeding. If not, it refuses and tells
   the user which agent to run first.
5. **Re-execution allowed** — every agent (stages 1-3) accepts being re-run when
   the task is already in its own output status. For example, build accepts
   `Em Andamento` (its own status) as well as `Validando Spec` (its predecessor).
   This allows the user to re-run a stage without resetting status.
   **Exception:** done does NOT support re-execution — once a task is
   `DONE`, it cannot be re-closed.
6. **Dependency check** — every agent verifies that ALL dependencies (Depends column
   from optimus-tasks.md) have status `DONE` (read from state.json) before proceeding. If
   any dependency is not done, the agent fires the `task-blocked` hook (if configured)
   and then refuses with a clear message identifying which dependency is blocking.
   **If the blocking dependency has status `Cancelado`**, the message must differentiate:
   "T-YYY was cancelled (Cancelado). Consider removing this dependency via `/optimus-tasks`."
   **If ALL dependencies are `Cancelado`**, add resolution guidance:
   "All dependencies of T-XXX are cancelled. To unblock, run `/optimus-tasks edit T-XXX`
   and either: (a) remove all dependencies, (b) replace with alternative task IDs, or
   (c) cancel T-XXX as well."
7. **Expanded confirmation on status change** — when a stage agent is about to change
   a task's status, it shows the task summary (title and version) and asks for
   explicit confirmation via `AskUser`. This
   prevents accidental status changes on the wrong task, especially during auto-detect.

   **Show expanded confirmation when:**
   - The status will actually change (not re-execution), AND
   - The user did NOT specify the task ID explicitly (auto-detect picked the task)

   **Skip expanded confirmation when:**
   - Re-execution (status already equals the stage's output status — user knows the task)
   - The user specified the task ID explicitly (e.g., "execute T-012" — user has context)

   **Exception:** done always changes status (no re-execution), so the
   re-execution skip does not apply. It still skips when the user specified the task ID.

8. **Branch protection** — execution skills (stages 1-4) require a feature branch.
   Administrative skills can run on any branch. See the classification table below:

   **Skills are classified as Administrative or Execution:**

   | Type | Agent | Allowed on main/default? | Reason |
   |------|-------|-------------------------|--------|
   | Admin | import | Yes | Only creates/modifies optimus-tasks.md |
   | Admin | report | Yes | Read-only, no modifications |
   | Admin | quick-report | Yes | Read-only, no modifications |
   | Admin | tasks | Yes | Only creates/edits/removes tasks in optimus-tasks.md and state.json |
   | Execution | plan | Yes (creates worktree) | Writes state.json and creates worktree |
   | Execution | build | Yes (auto-navigates) | Finds task worktree and navigates to it |
   | Execution | review | Yes (auto-navigates) | Finds task worktree and navigates to it |
   | Admin | pr-check | Yes | Standalone PR review tool, does not change task status |
   | Execution | done | Yes (auto-navigates) | Finds task worktree and navigates to it |
   | Admin | batch | Yes | Orchestrates stages, delegates to stage skills |
   | Admin | resolve | Yes | Only resolves merge conflicts in optimus-tasks.md |
   | Admin | resume | Yes | Read-only on state.json EXCEPT for the user-confirmed Reset-to-Pendente recovery; creates a worktree only as recovery when branch exists but worktree is missing |

   **Administrative skills** manage optimus-tasks.md metadata and state.json. They never modify
   project code and can run on any branch.

   **Execution skills** modify code or run verification. They require a feature branch
   (workspace). Stage-1 writes state.json (status + branch) and creates the worktree.
   Stages 2-4 auto-navigate to the task's worktree when invoked on the default branch
   (see Protocol: Workspace Auto-Navigation).

   To detect the default branch:
   ```bash
   DEFAULT_BRANCH=$(git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's@^refs/remotes/origin/@@')
   if [ -z "$DEFAULT_BRANCH" ]; then
     DEFAULT_BRANCH=$(git branch --list main master 2>/dev/null | head -1 | tr -d ' *')
   fi
   if [ -z "$DEFAULT_BRANCH" ]; then
     echo "ERROR: Cannot determine default branch. Set it with: git remote set-head origin <branch>"
     exit 1
   fi
   ```

9. **Branch-task cross-validation** — stages 2-4 derive the expected branch name from
   the task's Tipo + ID + Title (see Protocol: Branch Name Derivation) and verify it
   matches the current branch. If the branch does not match, the agent warns the user
   and asks whether to continue or switch.

### Transition Table

| Agent | Expects status | Changes to | Re-execution? |
|-------|---------------|------------|---------------|
| plan | `Pendente` or `Validando Spec` | `Validando Spec` | Yes (accepts own status) |
| build | `Validando Spec` or `Em Andamento` | `Em Andamento` | Yes (accepts own status) |
| review | `Em Andamento` or `Validando Impl` | `Validando Impl` | Yes (accepts own status) |
| done | `Validando Impl` | `DONE` | No (final stage) |

**NOTE:** `Cancelado` is a terminal status. No stage agent accepts it — all stages refuse
tasks with status `Cancelado`. Cancellation is managed exclusively by `tasks`.

### done Gates

Before marking done, done runs 3 sequential hard gates:
1. No uncommitted changes (`git status --porcelain` = empty) — HARD BLOCK
2. No unpushed commits (`git log @{u}..HEAD` = empty) — HARD BLOCK
3. PR in final state (MERGED or CLOSED) or no PR exists — HARD BLOCK if OPEN

Lint, tests, and CI validation are the responsibility of the PR pipeline (branch
protection rules, CI workflows), not done. If the PR was merged, these already passed.

If any gate fails, done stops immediately and status in state.json stays unchanged.

## Dry-Run Mode (all stages)

All stage agents (1-4) support **dry-run mode**. When the user includes "dry-run" or
"preview" in their invocation (e.g., "dry-run spec T-003", "preview review T-012"):

1. **Run all analysis/validation phases normally** — agent dispatch, findings, etc.
2. **Do NOT change task status** — skip the status update step
3. **Do NOT commit or push anything** — no git operations that modify state
4. **Do NOT create workspaces** — skip branch/worktree creation (stage-1)
5. **Do NOT apply fixes** — skip batch-apply phases
6. **Present results as informational** — "what would happen" without side effects
7. **Do NOT write session files** — session state is for crash recovery of real executions, not previews

This allows users to preview what a stage would do before committing to it.

## Reusable Protocols

The protocols below are referenced by SKILL.md files with "Execute protocol X from AGENTS.md".
Each SKILL.md specifies its stage-specific parameters (stage name, expected status, etc.)
and delegates the common logic to these protocols. This avoids duplicating the same steps
in every SKILL.md.

### Protocol: optimus-tasks.md Validation (HARD BLOCK)

**Referenced by:** all stage agents (1-4), tasks, batch. Note: resolve performs inline format validation in its own Step 4.2.

Every stage agent MUST validate optimus-tasks.md before operating. The full validation rules are
defined in the "Format Validation" section above (items 1-15). This protocol is the
executable version:

1. **Resolve paths and git scope:** Execute Protocol: Resolve Tasks Git Scope (below) to
   resolve `TASKS_DIR`, `TASKS_FILE`, `TASKS_GIT_SCOPE`, and the `tasks_git` helper.
2. **Find optimus-tasks.md:** Check if `TASKS_FILE` exists. If not found, **STOP** and suggest `/optimus-import`.
3. **Validate format:** Execute all 15 validation checks from the "Format Validation" section. If the format marker is missing or any check fails, **STOP** and suggest `/optimus-import`.

**All subsequent references to `optimus-tasks.md` in the skill use the resolved `TASKS_FILE` path.
All references to Ring pre-dev artifacts use `TASKS_DIR` as the root** — never hardcoded paths.
**All git operations on optimus-tasks.md use the `tasks_git` helper** (which handles both same-repo
and separate-repo scopes).

Skills reference this as: "Find and validate optimus-tasks.md (HARD BLOCK) — see AGENTS.md Protocol: optimus-tasks.md Validation."

### Protocol: Resolve Tasks Git Scope

**Referenced by:** all stage agents (1-4), tasks, batch, resolve, import, resume, report, quick-report

Resolves `TASKS_DIR` (Ring pre-dev root) and `TASKS_FILE` (`<tasksDir>/optimus-tasks.md`), then
detects whether `tasksDir` lives in the same git repo as the project code or in a
**separate** git repo. Exposes a `tasks_git` helper function so skills can run git
commands on optimus-tasks.md uniformly regardless of scope.

```bash
# Step 0: Resolve main worktree — see AGENTS.md Protocol: Resolve Main Worktree Path.
# Required because .optimus/config.json is gitignored and lives only in the main
# worktree's filesystem; resolving it relative to PWD would miss it from a linked
# worktree.
MAIN_WORKTREE="$(git worktree list --porcelain 2>/dev/null | awk '/^worktree / {print $2; exit}')"
if [ -z "$MAIN_WORKTREE" ]; then
  echo "ERROR: Cannot determine main worktree — not in a git repository." >&2
  exit 1
fi
# Step 1: Resolve tasksDir from config.json (if present) or fall back to default.
CONFIG_FILE="${MAIN_WORKTREE}/.optimus/config.json"
if [ -f "$CONFIG_FILE" ] && jq empty "$CONFIG_FILE" 2>/dev/null; then
  TASKS_DIR=$(jq -r '.tasksDir // "docs/pre-dev"' "$CONFIG_FILE")
else
  TASKS_DIR="docs/pre-dev"
fi
# Reject "null" (jq -r prints literal "null" for JSON null) or empty string.
case "$TASKS_DIR" in
  ""|"null") TASKS_DIR="docs/pre-dev" ;;
esac
# Security: reject TASKS_DIR values starting with "-" (git option injection via
# `git -C --exec-path=...` or similar). Trust boundary: config.json is now gitignored,
# but a user could still receive a malicious config via Slack/email.
case "$TASKS_DIR" in
  -*)
    echo "ERROR: tasksDir cannot start with '-' (security)." >&2
    exit 1
    ;;
esac

# Step 2: Derive TASKS_FILE.
TASKS_FILE="${TASKS_DIR}/optimus-tasks.md"

# Step 3: Detect git scope.
PROJECT_ROOT=$(git rev-parse --show-toplevel 2>/dev/null)
if [ -z "$PROJECT_ROOT" ]; then
  echo "ERROR: Not inside a git repository — optimus requires git." >&2
  exit 1
fi

TASKS_REPO_ROOT=""
if [ -d "$TASKS_DIR" ]; then
  TASKS_REPO_ROOT=$(git -C "$TASKS_DIR" rev-parse --show-toplevel 2>/dev/null || echo "")
fi

if [ -z "$TASKS_REPO_ROOT" ]; then
  if [ -d "$TASKS_DIR" ]; then
    # Directory exists but is NOT inside a git repository — this is a
    # misconfiguration. Without this guard, operations would silently target
    # the project repo and fail confusingly.
    echo "ERROR: tasksDir '$TASKS_DIR' exists but is not inside a git repository." >&2
    echo "Options:" >&2
    echo "  1. Initialize git in tasksDir: git -C \"$TASKS_DIR\" init" >&2
    echo "  2. Point tasksDir to an existing git repo." >&2
    echo "  3. Remove tasksDir to let optimus create it inside the project repo." >&2
    exit 1
  fi
  # Fresh project: tasksDir does not exist yet — assume same-repo.
  # Skills that create optimus-tasks.md will mkdir -p "$TASKS_DIR" first.
  TASKS_GIT_SCOPE="same-repo"
elif [ "$TASKS_REPO_ROOT" = "$PROJECT_ROOT" ]; then
  TASKS_GIT_SCOPE="same-repo"
else
  TASKS_GIT_SCOPE="separate-repo"
fi

# Step 4: Compute the path to pass to git commands.
# In same-repo, git runs from project root and we pass TASKS_FILE as is.
# In separate-repo, git runs with -C "$TASKS_DIR" so paths are relative to TASKS_DIR.
if [ "$TASKS_GIT_SCOPE" = "separate-repo" ]; then
  # python3 is REQUIRED in separate-repo mode to compute the path from the tasks
  # repo root. A naive "optimus-tasks.md" fallback would be wrong when TASKS_DIR is a
  # subdir of the tasks repo (e.g., `tasks-repo/project-alfa/`), because
  # `git show origin/main:optimus-tasks.md` resolves from repo root, not CWD.
  if ! command -v python3 >/dev/null 2>&1; then
    echo "ERROR: python3 is required for separate-repo mode (path computation)." >&2
    echo "Install python3 or point tasksDir inside the project repo." >&2
    exit 1
  fi
  TASKS_GIT_REL=$(python3 -c "import os,sys; print(os.path.relpath(sys.argv[1], sys.argv[2]))" \
    "$TASKS_FILE" "$TASKS_REPO_ROOT" 2>/dev/null)
  if [ -z "$TASKS_GIT_REL" ]; then
    echo "ERROR: Failed to compute TASKS_GIT_REL for '$TASKS_FILE' relative to '$TASKS_REPO_ROOT'." >&2
    exit 1
  fi
else
  TASKS_GIT_REL="$TASKS_FILE"
fi

# Step 5: Resolve the tasks repo's default branch once (used by tasks_git
# operations that reference origin/$DEFAULT). This is DIFFERENT from
# $DEFAULT_BRANCH (the project repo's default).
if [ "$TASKS_GIT_SCOPE" = "separate-repo" ]; then
  TASKS_DEFAULT_BRANCH=$(git -C "$TASKS_DIR" symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's@^refs/remotes/origin/@@')
  if [ -z "$TASKS_DEFAULT_BRANCH" ]; then
    # Fallback: check origin/main vs origin/master existence (deterministic,
    # unlike `git branch --list main master` which can return either arbitrarily).
    if git -C "$TASKS_DIR" show-ref --verify refs/remotes/origin/main >/dev/null 2>&1; then
      TASKS_DEFAULT_BRANCH="main"
    elif git -C "$TASKS_DIR" show-ref --verify refs/remotes/origin/master >/dev/null 2>&1; then
      TASKS_DEFAULT_BRANCH="master"
    fi
  fi
else
  TASKS_DEFAULT_BRANCH=$(git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's@^refs/remotes/origin/@@')
  if [ -z "$TASKS_DEFAULT_BRANCH" ]; then
    if git show-ref --verify refs/remotes/origin/main >/dev/null 2>&1; then
      TASKS_DEFAULT_BRANCH="main"
    elif git show-ref --verify refs/remotes/origin/master >/dev/null 2>&1; then
      TASKS_DEFAULT_BRANCH="master"
    fi
  fi
fi

# Security: reject malformed branch names (prevents injection via
# `git diff origin/<weird>`).
if [ -n "$TASKS_DEFAULT_BRANCH" ] && ! [[ "$TASKS_DEFAULT_BRANCH" =~ ^[a-zA-Z0-9._/-]+$ ]]; then
  echo "ERROR: Invalid TASKS_DEFAULT_BRANCH format: '$TASKS_DEFAULT_BRANCH'" >&2
  exit 1
fi

# Step 6: Define the tasks_git helper.
tasks_git() {
  if [ "$TASKS_GIT_SCOPE" = "separate-repo" ]; then
    git -C "$TASKS_DIR" "$@"
  else
    git "$@"
  fi
}
```

**Usage:**
```bash
tasks_git add "$TASKS_GIT_REL"
tasks_git commit -F "$COMMIT_MSG_FILE"
# IMPORTANT: use $TASKS_DEFAULT_BRANCH (tasks repo default) — NOT $DEFAULT_BRANCH
# (project repo default). They are the same in same-repo mode but may differ in
# separate-repo mode (e.g., tasks repo is `master`, project repo is `main`).
tasks_git diff "origin/$TASKS_DEFAULT_BRANCH" -- "$TASKS_GIT_REL"
tasks_git show "origin/$TASKS_DEFAULT_BRANCH:$TASKS_GIT_REL"
```

**Rule:** Skills MUST use `tasks_git` (never raw `git`) when operating on `$TASKS_FILE`.
Raw `git` on `$TASKS_FILE` breaks in separate-repo mode.

**Rule:** When committing in separate-repo mode, commits land in the tasks repo (not the
project repo). `tasks_git push` pushes the tasks repo. The project repo is unaffected.

Skills reference this as: "Resolve tasks git scope — see AGENTS.md Protocol: Resolve Tasks Git Scope."

### Protocol: GitHub CLI Check (HARD BLOCK)

**Referenced by:** all stage agents (1-4), tasks, batch

```bash
gh auth status 2>/dev/null
```

If this command fails (exit code != 0), **STOP** immediately:
```
GitHub CLI (gh) is not authenticated. Run `gh auth login` to authenticate before proceeding.
```

### Protocol: Initialize .optimus Directory

**Referenced by:** import, tasks, report (export), quick-report, batch, pr-check, deep-review, coderabbit-review, all stage agents (1-4) for session files

Before creating ANY file inside `.optimus/`, ensure the directory structure exists
and that the entire `.optimus/` tree is gitignored (it is 100% operational/per-user).

```bash
# Requires Protocol: Resolve Main Worktree Path to have run first
# (or resolve inline; see that protocol).
MAIN_WORKTREE="$(git worktree list --porcelain 2>/dev/null | awk '/^worktree / {print $2; exit}')"
mkdir -p "${MAIN_WORKTREE}/.optimus/sessions" "${MAIN_WORKTREE}/.optimus/reports" "${MAIN_WORKTREE}/.optimus/logs"
if ! grep -q '^# optimus-operational-files' .gitignore 2>/dev/null; then
  printf '\n# optimus-operational-files\n.optimus/config.json\n.optimus/state.json\n.optimus/stats.json\n.optimus/sessions/\n.optimus/reports/\n.optimus/logs/\n' >> .gitignore
fi
# Linked worktrees managed by Optimus live at ${MAIN_WORKTREE}/.worktrees/
# (see Worktree Location Convention). Add the gitignore entry idempotently
# on a separate marker so existing projects whose `.gitignore` already
# carries the operational-files block still get the worktree exclusion.
if ! grep -q '^# optimus-operational-worktrees' .gitignore 2>/dev/null; then
  printf '\n# optimus-operational-worktrees\n.worktrees/\n' >> .gitignore
fi
# Log retention (idempotent — fires once per init): age-based + count-cap prune.
# Also duplicated in Protocol: Session State so stage agents (which call Session
# State but not Initialize Directory) get pruning at every phase transition.
# Both prune sites are no-ops on clean directories; running both is harmless.
find "${MAIN_WORKTREE}/.optimus/logs" -type f -name '*.log' -mtime +30 -delete 2>/dev/null
if [ -d "${MAIN_WORKTREE}/.optimus/logs" ]; then
  ls -1t "${MAIN_WORKTREE}/.optimus/logs"/*.log 2>/dev/null | tail -n +501 \
    | while IFS= read -r _log_to_rm; do rm -f -- "$_log_to_rm"; done
fi
```

**Log retention** for `.optimus/logs/` runs at TWO sites for full coverage:
- **Protocol: Initialize .optimus Directory** (this protocol) — fires when
  admin/standalone skills (`import`, `tasks`, `report`, `quick-report`, `batch`,
  `pr-check`, `deep-review`, `coderabbit-review`) initialize `.optimus/`.
- **Protocol: Session State** — fires at every stage agent (`plan`, `build`,
  `review`, `done`) phase transition.

Both sites are idempotent (no-op on clean directories) and use the same prune
logic (30-day age cap + 500-file count cap). Running both per session is a
harmless cheap operation.

Everything inside `.optimus/` is gitignored. The planning tree is versioned
separately at `<tasksDir>/optimus-tasks.md` (and `<tasksDir>/tasks/`, `<tasksDir>/subtasks/`
for Ring specs) — see the File Location section above.

Skills reference this as: "Initialize .optimus directory — see AGENTS.md Protocol: Initialize .optimus Directory."

### Protocol: Quiet Command Execution

**Referenced by:** build, review, pr-check, coderabbit-review, deep-review (for `make test`, `make lint`, `make test-integration`, coverage runs)

Long-running verification commands (`make test`, `make lint`, `make test-coverage`,
`make test-integration`, `make test-integration-coverage`) often emit thousands of
output lines. Capturing that output in the agent's context wastes tokens and slows
down every turn, even when the command passes cleanly.

This protocol defines `_optimus_quiet_run`, a bash helper that runs a command with
stdout/stderr redirected to a log file under `.optimus/logs/` and emits **a single
verdict line** based on the exit code. On failure it also prints the last 50 lines of
the log so the agent can diagnose without ingesting the full output. The exit code
is preserved, so downstream control flow (`if ...; then ... fi`) keeps working.

**Helper (auto-inlined — do NOT manually copy):**

This helper is automatically inlined into every consumer skill by
`scripts/inline-protocols.py` (see Shared Protocols block at the end of each
SKILL.md). You do NOT need to paste it into skills manually — editing this single
source of truth is enough.

```bash
_optimus_quiet_run() {
  # Usage: _optimus_quiet_run <label> <command> [args...]
  # Runs <command> with stdout+stderr redirected to
  # .optimus/logs/<timestamp>-<label>-<pid>.log. Prints a single PASS/FAIL line;
  # on FAIL also prints last 50 lines of the log (terminal escapes stripped).
  # Returns the command's exit code unchanged.
  local label="$1"; shift
  if [ -z "$label" ] || [ $# -eq 0 ]; then
    echo "ERROR: _optimus_quiet_run requires <label> and <command>" >&2
    return 2
  fi
  local safe
  safe=$(printf '%s' "$label" | tr -c '[:alnum:]-_' '-' | sed 's/--*/-/g;s/^-//;s/-$//')
  [ -z "$safe" ] && safe="run"
  local ts
  ts=$(date +%Y%m%d-%H%M%S)
  # PID suffix prevents same-second same-label collisions (parallel or fast sequential).
  local log=".optimus/logs/${ts}-${safe}-$$.log"
  if ! mkdir -p "$(dirname "$log")" 2>/dev/null; then
    echo "ERROR: _optimus_quiet_run cannot create $(dirname "$log") (permission denied, disk full, or read-only FS)" >&2
    return 3
  fi
  # umask 0077 ensures log file is owner-read/write only (logs may contain
  # sensitive test output: credentials in debug lines, internal stack traces).
  if ( umask 0077; "$@" > "$log" 2>&1 ); then
    echo "PASS: $label (log: $log)"
    return 0
  else
    local rc=$?
    echo "FAIL: $label (exit=$rc, log: $log)"
    echo "--- last 50 lines ---"
    # `cat -v` strips terminal escape sequences (non-printable bytes become ^X
    # notation), preventing a malicious test from hijacking the terminal title
    # or obscuring errors via ANSI/OSC sequences.
    tail -n 50 "$log" | cat -v
    return $rc
  fi
}
```

**Usage examples:**

```bash
_optimus_quiet_run "make-lint" make lint
_optimus_quiet_run "make-test" make test
_optimus_quiet_run "make-test-coverage" make test-coverage
_optimus_quiet_run "make-test-integration" make test-integration
```

**Contract:**

1. **Success path (exit 0):** one line `PASS: <label> (log: <path>)` — this is ALL the
   output the agent reads. The full log stays on disk for manual inspection.
2. **Failure path (exit != 0):** `FAIL: <label> (exit=N, log: <path>)` + a separator
   line + the last 50 lines of the log (with terminal escape sequences stripped via
   `cat -v`). The agent has enough context to diagnose or dispatch a fix droid
   without loading the full output.
3. **Exit code preserved:** the helper returns the same exit code as the wrapped
   command. Downstream `if _optimus_quiet_run ...; then ... fi` works the same as
   `if make test; then ... fi` would.
4. **Log retention:** logs accumulate under `.optimus/logs/` (gitignored). Both
   Protocol: Initialize .optimus Directory (admin/standalone skills) and
   Protocol: Session State (stage agents at phase transitions) automatically
   prune logs older than 30 days AND cap the directory at 500 most-recent
   files, whichever limit hits first. Users may `rm .optimus/logs/*.log` at any
   time to reclaim space manually.
5. **Reserved exit codes:** `2` = missing/empty label or missing command;
   `3` = cannot create `.optimus/logs/` (perm denied, disk full, read-only FS).
   Any other exit code comes from the wrapped command.

**Label naming convention:**
- `make-<target>` for Makefile targets: `make-lint`, `make-test`, `make-test-coverage`, `make-test-integration`, `make-test-integration-coverage`
- `<tool>` for direct tool invocations: `go-vet`, `goimports`, `gofmt`, `prettier`
- `<tool>-<action>` when a single tool has multiple modes: `npm-test-coverage`, `pytest-cov`

Keep labels short (≤30 chars) and filesystem-safe — the helper sanitizes aggressively,
but readable labels produce readable log filenames in `.optimus/logs/`.

**When the agent needs full output:** use `cat "${MAIN_WORKTREE}/.optimus/logs/<filename>.log"` or
point a sub-agent to the log path (`Read` tool). Never re-run the command just to
see the output — the log already has it.

**Output parsing (e.g., coverage %):** do NOT parse the stdout of
`_optimus_quiet_run`. Read the log file or, better, use a separate command that
prints only the metric (example in Protocol: Coverage Measurement).

**When NOT to use this helper:**
- Commands whose output must be parsed by the agent turn-by-turn (rare for
  verification, common for `git log`, `gh pr view`, etc.) — use normal Execute.
- Interactive commands that expect TTY input.
- Commands under 20 lines of output where the savings are negligible.

Skills reference this as: "Run quietly — see AGENTS.md Protocol: Quiet Command Execution."

### Protocol: Increment Stage Stats

**Referenced by:** plan, review

After the status change in state.json (and BEFORE any analysis work begins), increment
the execution counter for the current stage in `.optimus/stats.json`. This tracks how many
times each stage ran on each task — useful for spotting spec churn and review cycles.

**NOTE:** Only increment when NOT in dry-run mode.

1. Read `.optimus/stats.json`. If the file does not exist, start with an empty object `{}`.
   If the file exists but is corrupted, reset it:
   ```bash
   # Requires Protocol: Resolve Main Worktree Path to have run first
   # (or resolve inline; see that protocol).
   MAIN_WORKTREE="$(git worktree list --porcelain 2>/dev/null | awk '/^worktree / {print $2; exit}')"
   STATS_FILE="${MAIN_WORKTREE}/.optimus/stats.json"
   if [ -f "$STATS_FILE" ] && ! jq empty "$STATS_FILE" 2>/dev/null; then
     echo "WARNING: stats.json is corrupted. Resetting counters."
     echo '{}' > "$STATS_FILE"
   fi
   ```
2. If the task ID key does not exist, initialize it:
   ```json
   { "plan_runs": 0, "review_runs": 0 }
   ```
3. Increment the appropriate counter (`plan_runs` for plan, `review_runs` for review).
4. Set the timestamp field (`last_plan` or `last_review`) to the current UTC ISO 8601 time.
5. Write the updated JSON back to `.optimus/stats.json` (pretty-printed, sorted keys).

**NOTE:** stats.json is gitignored — no commit needed.

Skills reference this as: "Increment stage stats — see AGENTS.md Protocol: Increment Stage Stats."

### Protocol: Shell Safety Guidelines

**Referenced by:** plan, batch

All bash examples in AGENTS.md and SKILL.md files are templates that agents execute literally.
Follow these rules to prevent injection and silent failures:

1. **Always quote variables:** Use `"$VAR"` not `$VAR` — especially for paths, branch names, and user-derived values
2. **Check exit codes for critical commands:**
   ```bash
   tasks_git add "$TASKS_GIT_REL"
   COMMIT_MSG_FILE=$(mktemp)
   printf '%s' "chore(tasks): $COMMIT_MSG" > "$COMMIT_MSG_FILE"
   if ! tasks_git commit -F "$COMMIT_MSG_FILE"; then
     echo "ERROR: git commit failed. Check pre-commit hooks or git config." >&2
     rm -f "$COMMIT_MSG_FILE"
     exit 1
   fi
   rm -f "$COMMIT_MSG_FILE"
   ```
3. **Never interpolate user-derived values directly into shell commands** — task titles,
   branch names, and other user input may contain shell metacharacters
4. **Use `grep -F` for fixed string matching** — never pass branch names or task IDs
   as regex patterns to `grep` without `-F`
5. **Use `grep -E '^\| T-NNN \|'`** to match task rows in optimus-tasks.md — plain `grep "T-NNN"`
   matches titles and dependency columns too
6. **Validate tool availability** before use: `command -v jq >/dev/null 2>&1` before running `jq`
7. **Validate JSON files** before parsing: `jq empty "$FILE" 2>/dev/null` before reading keys
8. **Sanitize user-derived values in commit messages** — task titles and descriptions may
   contain shell metacharacters (backticks, `$(...)`, double quotes). **Mandatory pattern:**
   write the commit message to a temporary file and use `git commit -F`:
   ```bash
   COMMIT_MSG_FILE=$(mktemp)
   printf '%s' "chore(tasks): $OPERATION" > "$COMMIT_MSG_FILE"
   git commit -F "$COMMIT_MSG_FILE"
   rm -f "$COMMIT_MSG_FILE"
   ```
   This avoids all shell expansion issues. If using `-m` directly, sanitize with:
   `SAFE_VALUE=$(printf '%s' "$VALUE" | tr -d '`$')` before interpolation.

Skills reference this as: "Follow shell safety guidelines — see AGENTS.md Protocol: Shell Safety Guidelines."

### Protocol: Session State

**Referenced by:** all stage agents (1-4)

Stage agents write a session state file to track progress. This enables resumption
when a session is interrupted (agent crash, user closes terminal, context window limit).

**IMPORTANT — Write timing:** The session file MUST be written **immediately after the
status change in state.json** (before any work begins). This ensures crash recovery has
a record even if the agent fails before producing any output. Do NOT wait until
"key phase transitions" to write the initial session file.

**Session file location:** `${MAIN_WORKTREE}/.optimus/sessions/session-<task-id>.json` (gitignored).
Each task gets its own file (e.g., `${MAIN_WORKTREE}/.optimus/sessions/session-T-003.json`).
The `$MAIN_WORKTREE` prefix is REQUIRED — see Protocol: Resolve Main Worktree Path.

```json
{
  "task_id": "T-003",
  "stage": "<stage-name>",
  "status": "<stage-output-status>",
  "branch": "feat/t-003-user-auth",
  "started_at": "2025-01-15T10:30:00Z",
  "updated_at": "2025-01-15T11:45:00Z",
  "phase": "Phase 1: Implementation",
  "convergence_round": 0,
  "convergence_status": null,
  "findings_count": 0,
  "notes": "Implementation in progress"
}
```

**Convergence checkpoint:** During the convergence loop, update `convergence_round`,
`convergence_status`, and `findings_count` after each round completes (and after each
user gate decision). The `convergence_status` field MUST be persisted **before**
proceeding past any user gate so crash recovery does not re-prompt an already-answered
gate. Valid values: `null` (loop not entered yet, or round 1 not complete),
`"IN_PROGRESS"` (a round was dispatched and the orchestrator has not yet recorded the
exit status), `"CONVERGED"`, `"USER_STOPPED"`, `"SKIPPED"`, `"HARD_LIMIT"`,
`"DISPATCH_FAILED_ABORTED"`. On resume, the orchestrator reads `convergence_status`
to decide whether to skip the remainder of the loop (terminal status set), continue
with the next gate (still `IN_PROGRESS`), or re-show the entry gate (`null`).

**On stage start (after task ID is known):**

```bash
# Requires Protocol: Resolve Main Worktree Path to have run first
# (or resolve inline; see that protocol).
MAIN_WORKTREE="$(git worktree list --porcelain 2>/dev/null | awk '/^worktree / {print $2; exit}')"
SESSION_FILE="${MAIN_WORKTREE}/.optimus/sessions/session-${TASK_ID}.json"
if [ -f "$SESSION_FILE" ]; then
  if ! jq empty "$SESSION_FILE" 2>/dev/null; then
    echo "WARNING: Session file is corrupted. Deleting and proceeding fresh."
    rm -f "$SESSION_FILE"
  else
    cat "$SESSION_FILE"
  fi
fi
```

- If the file exists AND the task's status in `state.json` matches the session's `status`:
  - Present via `AskUser`:
    ```
    Previous session found:
      Task: T-XXX — [title]
      Stage: <stage-name>
      Last active: <time since updated_at>
      Progress: <phase from session>
    Resume this session?
    ```
    Options: Resume / Start fresh (delete session) / Continue (keep session file)
  - If **Resume**: skip to the phase indicated in the session file
  - If **Start fresh (delete session)**: delete the session file and proceed from the beginning
  - If **Continue (keep session file)**: proceed from the beginning without deleting the session file
- If the file is stale (>24h) or the task status has changed → delete and proceed normally.
  **Staleness check example:**
  ```bash
  UPDATED=$(jq -r '.updated_at // empty' "$SESSION_FILE" 2>/dev/null)
  if [ -z "$UPDATED" ]; then
    # Session file has no updated_at (corrupted or incomplete write) — treat as
    # stale to prevent orphan session files from accumulating.
    echo "WARNING: Session file has no updated_at. Deleting as stale."
    rm -f "$SESSION_FILE"
  else
    NOW_EPOCH=$(date +%s)
    if [ "$(uname)" = "Darwin" ]; then
      UPDATED_EPOCH=$(date -j -f "%Y-%m-%dT%H:%M:%SZ" "$UPDATED" +%s 2>/dev/null || echo 0)
    else
      UPDATED_EPOCH=$(date -d "$UPDATED" +%s 2>/dev/null || echo 0)
    fi
    AGE=$(( NOW_EPOCH - UPDATED_EPOCH ))
    if [ "$AGE" -gt 86400 ]; then
      echo "Session file is stale (>24h). Deleting."
      rm -f "$SESSION_FILE"
    fi
  fi
  ```
- **External status change detection:** If the session file exists AND the task's status
  does NOT match the session's `status`, check if the difference is explainable by normal
  stage progression (e.g., session says `Em Andamento` but task is now `Validando Impl` —
  the task was advanced externally via `/optimus-tasks`). If the status change is NOT
  explainable by forward progression, treat the session as stale and delete it.
- If no file exists → proceed normally

**On stage progress (at key phase transitions):**

```bash
# Requires Protocol: Resolve Main Worktree Path to have run first
# (or resolve inline; see that protocol).
MAIN_WORKTREE="$(git worktree list --porcelain 2>/dev/null | awk '/^worktree / {print $2; exit}')"
# Mirror Protocol: Initialize .optimus Directory (mkdir + gitignore) so stage
# agents — which call Session State but not Initialize Directory — also create
# the dirs and update .gitignore on first phase transition.
mkdir -p "${MAIN_WORKTREE}/.optimus/sessions" "${MAIN_WORKTREE}/.optimus/reports" "${MAIN_WORKTREE}/.optimus/logs"
if ! grep -q '^# optimus-operational-files' .gitignore 2>/dev/null; then
  printf '\n# optimus-operational-files\n.optimus/config.json\n.optimus/state.json\n.optimus/stats.json\n.optimus/sessions/\n.optimus/reports/\n.optimus/logs/\n' >> .gitignore
fi
# Linked worktrees managed by Optimus live at ${MAIN_WORKTREE}/.worktrees/
# (see Worktree Location Convention). Add the gitignore entry idempotently
# on a separate marker so existing projects whose `.gitignore` already
# carries the operational-files block still get the worktree exclusion.
if ! grep -q '^# optimus-operational-worktrees' .gitignore 2>/dev/null; then
  printf '\n# optimus-operational-worktrees\n.worktrees/\n' >> .gitignore
fi
# Log retention (idempotent — runs every phase transition): age-based + count-cap
# prune. Stage agents are the heaviest log producers, so placing prune here
# ensures it fires for build/review/plan/done (which call Session State but not
# Initialize .optimus Directory).
find "${MAIN_WORKTREE}/.optimus/logs" -type f -name '*.log' -mtime +30 -delete 2>/dev/null
# Count-cap: keep at most 500 most-recent log files. Uses `while read -r` (not
# `xargs`) for portability across GNU/BSD (`xargs -r` is GNU-only). Filename
# safety: `_optimus_quiet_run` sanitizes labels to `[:alnum:]-_`, so log
# filenames cannot contain spaces or newlines.
if [ -d "${MAIN_WORKTREE}/.optimus/logs" ]; then
  ls -1t "${MAIN_WORKTREE}/.optimus/logs"/*.log 2>/dev/null | tail -n +501 \
    | while IFS= read -r _log_to_rm; do rm -f -- "$_log_to_rm"; done
fi
BRANCH_NAME=$(git branch --show-current 2>/dev/null)
# `git branch --show-current` exits 0 with empty stdout on detached HEAD; the
# `|| echo "detached"` fallback was dead code. Use an explicit check instead.
[ -z "$BRANCH_NAME" ] && BRANCH_NAME="detached"
jq -n \
  --arg task_id "${TASK_ID}" --arg stage "<stage-name>" --arg status "<status>" \
  --arg branch "${BRANCH_NAME}" --arg started "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --arg updated "$(date -u +%Y-%m-%dT%H:%M:%SZ)" --arg phase "<current-phase>" \
  --arg notes "<progress>" \
  '{task_id: $task_id, stage: $stage, status: $status, branch: $branch,
    started_at: $started, updated_at: $updated, phase: $phase, notes: $notes}' \
  > "${MAIN_WORKTREE}/.optimus/sessions/session-${TASK_ID}.json"
```

**On stage completion:** Delete the session file:
```bash
rm -f "${MAIN_WORKTREE}/.optimus/sessions/session-${TASK_ID}.json"
```

Skills reference this as: "Execute session state protocol from AGENTS.md using stage=`<name>`, status=`<status>`."

### Protocol: Terminal Identification

**Referenced by:** all stage agents (1-4), batch

After the task ID is identified and confirmed, set the terminal title to show the
current stage and task. This allows users running multiple agents in parallel terminals
to identify each terminal at a glance.

**Set title (after task ID is known):**

```bash
_optimus_set_title() {
  # iTerm2 AppleScript title updater. Empirical testing showed that Optimus
  # tasks always run in "divorced" iTerm2 sessions where the profile's
  # autoNameFormat is locked to a literal — OSC 0/1/2 and OSC 1337
  # SetUserVar are both ineffective in that state, so AppleScript's
  # `set name of s` is the only channel that actually mutates session.name.
  # The Execute tool runs bash without a controlling TTY, so /dev/tty fails
  # with ENODEV; we resolve the parent process's TTY via ps instead. Walk
  # up to 4 ancestors in case of nested shells. First run triggers a macOS
  # TCC prompt ("droid wants to control iTerm"); approving enables this
  # permanently. Silent no-op outside macOS/iTerm2 or when osascript is
  # unavailable — non-iTerm2 / non-macOS users get no title update.
  local title="$1"
  local pid="$PPID" tty=""
  for _ in 1 2 3 4; do
    [ -z "$pid" ] || [ "$pid" = "1" ] && break
    tty=$(ps -o tty= -p "$pid" 2>/dev/null | tr -d ' ')
    case "$tty" in
      ""|"?"|"??") pid=$(ps -o ppid= -p "$pid" 2>/dev/null | tr -d ' ') ;;
      *) break ;;
    esac
  done
  if { [ "$LC_TERMINAL" = "iTerm2" ] || [ "$TERM_PROGRAM" = "iTerm.app" ]; } \
     && command -v osascript >/dev/null 2>&1 && [ -n "$tty" ] \
     && [ "$tty" != "?" ] && [ "$tty" != "??" ]; then
    osascript \
      -e 'on run argv' \
      -e '  set targetTty to "/dev/" & item 1 of argv' \
      -e '  set newName to item 2 of argv' \
      -e '  tell application "iTerm2"' \
      -e '    repeat with w in windows' \
      -e '      repeat with t in tabs of w' \
      -e '        repeat with s in sessions of t' \
      -e '          if (tty of s as string) is targetTty then' \
      -e '            try' \
      -e '              set name of s to newName' \
      -e '            end try' \
      -e '          end if' \
      -e '        end repeat' \
      -e '      end repeat' \
      -e '    end repeat' \
      -e '  end tell' \
      -e 'end run' \
      -- "$tty" "$title" >/dev/null 2>&1 || true
  fi
}
_optimus_set_title "optimus: <STAGE> $TASK_ID — $TASK_TITLE"
```

Example output in terminal tab: `optimus: REVIEW T-003 — User Auth JWT`

**Why the parent-process TTY:** The Execute tool runs `bash -c` without a controlling
terminal, so `/dev/tty` returns `ENODEV` ("Device not configured"). The resolver above
asks `ps` for the parent's controlling TTY device path and matches it against iTerm2's
session list via AppleScript — that device is connected to the user's real iTerm2
session. If no ancestor has a TTY (Docker/CI) or osascript is unavailable, the
function silently no-ops.

**Restore title (at stage completion or exit):**

```bash
_optimus_set_title ""
```

**NOTE:** This helper is iTerm2-on-macOS only. Optimus tasks always run in
"divorced" iTerm2 sessions, where AppleScript's `set name of s` is the only
channel that reliably mutates `session.name`. Non-iTerm2 / non-macOS users
will not see a title update.

**Troubleshooting iTerm2 (if the title still doesn't update):**

1. **Window > Edit Tab Title** must be empty. A manually-set tab title is
   sticky on the tab label and overrides the session name visually, even
   when `session.name` is updated correctly underneath.
2. The first run on macOS triggers a TCC prompt ("`droid` wants to control
   `iTerm`"). Approve it to enable the helper. Denying makes the helper a
   silent no-op.
3. The helper requires the parent process to have a controlling TTY. Inside
   Docker/CI without a TTY, no ancestor will resolve and the helper will
   silently no-op.

Skills reference this as: "Set terminal title — see AGENTS.md Protocol: Terminal Identification."

### Protocol: Workspace Auto-Navigation (HARD BLOCK)

**Referenced by:** stages 2-4

Execution stages (2-4) resolve the correct workspace automatically. The agent MUST
be in the task's worktree before proceeding with any work.

```bash
DEFAULT_BRANCH=$(git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's@^refs/remotes/origin/@@')
if [ -z "$DEFAULT_BRANCH" ]; then
  # Use show-ref for deterministic fallback (unlike `git branch --list` which can
  # return either arbitrarily when both branches exist).
  if git show-ref --verify refs/remotes/origin/main >/dev/null 2>&1; then
    DEFAULT_BRANCH="main"
  elif git show-ref --verify refs/remotes/origin/master >/dev/null 2>&1; then
    DEFAULT_BRANCH="master"
  fi
fi
if [ -z "$DEFAULT_BRANCH" ]; then
  echo "ERROR: Cannot determine default branch. Set it with: git remote set-head origin <branch>" >&2
  exit 1
fi
CURRENT_BRANCH=$(git branch --show-current 2>/dev/null)
if [ -z "$CURRENT_BRANCH" ]; then
  echo "ERROR: Cannot determine current branch (detached HEAD state). Checkout a branch first." >&2
  exit 1
fi
```

**Resolution order:**

1. **Already on a feature branch?**
   - Derive the expected branch name from the task's Tipo + ID + Title (see Protocol:
     Branch Name Derivation). Also read the `branch` field from state.json if available.
   - Cross-validate: check that `CURRENT_BRANCH` matches the expected/derived branch.
   - If matches → proceed silently.
   - If does not match → warn via `AskUser`: "Expected branch `<expected>` for T-XXX,
     but you are on `<current>`. Continue on current branch, or switch?"

2. **On the default branch (auto-navigate)?**
   - Read state.json and list tasks with status compatible with the current stage
     (use the Transition Table to determine which statuses are valid).
     Tasks with no entry in state.json are `Pendente`.
   - **If 0 eligible tasks** → **STOP**: "No tasks in `<expected-status>` found."
   - **If 1 eligible task** → suggest via `AskUser`: "Found task T-XXX — [title] in
     worktree `<path>`. Continue with this task?"
   - **If N eligible tasks** → list all with worktree paths via `AskUser`:
     ```
     Multiple tasks available:
       T-001 — User auth (Em Andamento) → /projeto-t-001-.../
       T-002 — Login page (Em Andamento) → /projeto-t-002-.../
     Which task should I continue?
     ```
   - After task is identified, locate the worktree by task ID:
     ```bash
     git worktree list | grep -iF "<task-id>"
     ```
   - **If worktree found** → change working directory to the worktree path.
   - **If worktree NOT found** → derive the branch name (Protocol: Branch Name Derivation)
     and verify it exists:
     ```bash
     if ! git rev-parse --verify "<branch-name>" >/dev/null 2>&1; then
       # Branch doesn't exist — ask user for recovery
       # AskUser: "No worktree or branch found for T-XXX.
       #   This may indicate stage-1 crashed before creating it.
       #   Options: Create branch from HEAD / Re-run /optimus-plan"
     fi
     ```
     If the branch exists, create the worktree automatically. Worktrees live
     under `${MAIN_WORKTREE}/.worktrees/<branch-name>` (gitignored, project-rooted —
     see Worktree Location Convention below).
     ```bash
     # Resolve main worktree first — see Protocol: Resolve Main Worktree Path.
     MAIN_WORKTREE="$(git worktree list --porcelain 2>/dev/null | awk '/^worktree / {print $2; exit}')"
     WORKTREE_DIR="${MAIN_WORKTREE}/.worktrees/<branch-name>"
     git worktree add "$WORKTREE_DIR" "<branch-name>"
     ```
     Then change working directory to the new worktree.

Skills reference this as: "Resolve workspace (HARD BLOCK) — see AGENTS.md Protocol: Workspace Auto-Navigation."

### Protocol: Discover Review Droids

**Referenced by:** deep-review, pr-check

**Why:** Both review skills need a roster of installed review droids. Hardcoding the
list traps users on a fixed slate; rolling each skill's own discovery duplicates the
exclusion list and the description-based relevance filter. This protocol is the single
source of truth: callers invoke it, get back a categorized roster (or `MIN_NOT_MET`),
and render their own confirmation UX.

**Inputs:**

- `INCLUDE_NON_RING` (env var or caller flag, default `false`). When `false`, only
  `ring-*.md` agents are considered. When `true`, every `*.md` agent under
  `~/.factory/droids/` is considered, subject to the exclusion list and relevance
  filter below.

**Discovery glob:**

```bash
if [ "${INCLUDE_NON_RING:-false}" = "true" ]; then
  ls ~/.factory/droids/*.md 2>/dev/null
else
  ls ~/.factory/droids/ring-*.md 2>/dev/null
fi
```

For each candidate, read the `description` field from the YAML frontmatter — relevance
classification depends on it.

**Permanent exclusion list** (never dispatch for code review, regardless of
`INCLUDE_NON_RING`):

Droids whose purpose is implementation, design, operations, or non-code domains:

- `ring-default-codebase-explorer` — exploration, not review
- `ring-default-write-plan` — planning, not review
- `ring-default-review-slicer` — internal classification, not code review
- `ring-dev-team-devops-engineer` — DevOps implementation
- `ring-dev-team-frontend-designer` — UX design
- `ring-dev-team-helm-engineer` — Helm charts
- `ring-dev-team-sre` — observability validation
- `ring-dev-team-ui-engineer` — UI implementation
- `ring-dev-team-frontend-bff-engineer-*` — BFF implementation
- `ring-dev-team-prompt-quality-reviewer` — reviews AI prompts, not code
- All `ring-finance-*`, `ring-finops-*`, `ring-ops-*`, `ring-pm-*`, `ring-pmm-*`, `ring-pmo-*`, `ring-tw-*` — non-code domains

**Description-based relevance filter:**

| Classification | Selection rule | Examples |
|----------------|---------------|----------|
| **Core reviewer** | Description matches `code review|security|testing|safety|reviewer|audit` | `code-reviewer`, `business-logic-reviewer`, `security-reviewer`, `test-reviewer`, `nil-safety-reviewer`, `consequences-reviewer`, `dead-code-reviewer` |
| **QA analyst** | Description matches `test strategy|acceptance criteria` | `qa-analyst`, `qa-analyst-frontend` |
| **Stack specialist** | Description mentions a specific language/framework — include only if the project uses that stack | `backend-engineer-golang` (if `go.mod` exists), `backend-engineer-typescript` (if `package.json`), `frontend-engineer` (if frontend files in scope) |
| **Domain specialist** | Description mentions a specific technology — include only if the project uses it | `lib-commons-reviewer` (if `go.mod` imports `lib-commons`), `multi-tenant-reviewer` (if project uses multi-tenancy), `performance-reviewer` (always relevant) |
| **Non-reviewer (EXCLUDE)** | Description indicates implementation, design, ops, finance, planning, or infrastructure — NOT code review | See exclusion list above |

For non-ring entries (only present when `INCLUDE_NON_RING=true`), apply the same
description filter. Non-ring agents that pass the filter are returned in the `Non-Ring`
group regardless of stack/domain category — the caller decides whether to default-select
them in its UX.

**Output format:**

The protocol returns a grouped roster. Each entry carries `id`, `focus` (one-line
summary derived from the description), and `source` (`ring` or `non-ring`):

```
Ring Core
  - ring-default-code-reviewer — Code quality, SOLID, DRY, maintainability
  - ring-default-security-reviewer — Vulnerabilities, OWASP, input validation
  - ...

Ring Stack
  - ring-dev-team-backend-engineer-golang — Go idiomaticity (project has go.mod)

Ring Domain
  - ring-dev-team-performance-reviewer — Performance hotspots
  - ring-dev-team-lib-commons-reviewer — lib-commons usage (project imports it)

Non-Ring                       (only when INCLUDE_NON_RING=true)
  - my-custom-reviewer — User-installed reviewer
```

The caller renders this for user confirmation per its own UX (e.g., AskUser table
with default-selected ring entries and default-deselected non-ring entries).

**Minimum-roster contract:**

The protocol MUST yield at least both:

- `ring-default-code-reviewer` AND
- `ring-default-security-reviewer`

If either is missing from the discovered roster, the protocol returns `MIN_NOT_MET`
instead of a roster. The caller is responsible for STOP semantics — typically a
message instructing the user to install the missing droids and re-run.

Skills reference this as: "Execute Protocol: Discover Review Droids — see AGENTS.md Protocol: Discover Review Droids."

### Protocol: Divergence Warning

**Referenced by:** all stage agents (1-4)

Since status and branch data live in state.json (gitignored), optimus-tasks.md rarely changes
on feature branches. This protocol detects the uncommon case where optimus-tasks.md WAS modified
(e.g., Active Version Guard moved a task). It uses `tasks_git` so it works in both
same-repo and separate-repo scopes.

**Prerequisite:** Protocol: Resolve Tasks Git Scope must have been executed so
`TASKS_FILE`, `TASKS_GIT_REL`, `TASKS_GIT_SCOPE`, `TASKS_DEFAULT_BRANCH`, and
`tasks_git` are defined.

```bash
# Requires Protocol: Resolve Main Worktree Path to have run first
# (or resolve inline; see that protocol).
MAIN_WORKTREE="$(git worktree list --porcelain 2>/dev/null | awk '/^worktree / {print $2; exit}')"
if [ -z "$TASKS_DEFAULT_BRANCH" ]; then
  echo "WARNING: Cannot determine default branch for tasks repo. Skipping divergence check."
  # Skip — this is a warning, not a HARD BLOCK
else
  # Throttle fetch: only re-fetch if the cached timestamp is older than 5 minutes.
  # Each stage skill would otherwise pay ~2s network latency per invocation.
  # The cache lives in the PROJECT repo's .optimus/ (always present, gitignored).
  FETCH_MARKER="${MAIN_WORKTREE}/.optimus/.last-tasks-fetch"
  NOW_EPOCH=$(date +%s)
  SHOULD_FETCH=1
  if [ -f "$FETCH_MARKER" ]; then
    LAST_EPOCH=$(cat "$FETCH_MARKER" 2>/dev/null || echo 0)
    if [ -n "$LAST_EPOCH" ] && [ "$((NOW_EPOCH - LAST_EPOCH))" -lt 300 ]; then
      SHOULD_FETCH=0
    fi
  fi
  if [ "$SHOULD_FETCH" = "1" ]; then
    if tasks_git fetch origin "$TASKS_DEFAULT_BRANCH" --quiet 2>/dev/null; then
      mkdir -p "${MAIN_WORKTREE}/.optimus"
      printf '%s' "$NOW_EPOCH" > "$FETCH_MARKER"
    else
      echo "WARNING: Could not fetch from origin. Divergence check may use stale data."
    fi
  fi
  tasks_git diff "origin/$TASKS_DEFAULT_BRANCH" -- "$TASKS_GIT_REL" 2>/dev/null | head -20
fi
```

- If diff output is non-empty → warn via `AskUser`:
  ```
  optimus-tasks.md has diverged between your branch and <default_branch>.
  This may cause merge conflicts when the PR is merged.
  ```
  Options:
  - **Sync now** — run `tasks_git merge origin/<default_branch>` to incorporate changes
  - **Continue without syncing** — I'll handle conflicts later
- If diff output is empty → proceed silently (files are in sync)
- **NOTE:** This is a warning, not a HARD BLOCK. The user may choose to continue.
- **NOTE:** In separate-repo scope, "diverged" means the tasks repo branches diverge —
  not the project code branches.

Skills reference this as: "Check optimus-tasks.md divergence — see AGENTS.md Protocol: Divergence Warning."

### Protocol: Notification Hooks

**Referenced by:** all stage agents (1-4), tasks

After writing a status change to state.json, invoke notification hooks if present.

**IMPORTANT — Capture timing:** Read the current status from state.json and store it as
`OLD_STATUS` BEFORE writing the new status. The sequence is:
1. Read current status (with guard for missing/empty state.json):
   ```bash
   if [ -f "$STATE_FILE" ]; then
     OLD_STATUS=$(jq -r --arg id "$TASK_ID" '.[$id].status // "Pendente"' "$STATE_FILE" 2>/dev/null)
     [ -z "$OLD_STATUS" ] && OLD_STATUS="Pendente"
   else
     OLD_STATUS="Pendente"
   fi
   ```
2. Write new status to state.json
3. Invoke hooks with `OLD_STATUS` and new status

**IMPORTANT:** Always quote all arguments and sanitize user-derived values to prevent
shell injection. Hook scripts MUST NOT pass their arguments to `eval` or shell
interpretation — treat all arguments as untrusted data.

```bash
# Sanitize: allow only safe characters. Does NOT allow `.` or `/` (which would
# enable path-traversal if hook args flow into file paths).
_optimus_sanitize() { printf '%s' "$1" | tr -cd '[:alnum:][:space:]-_:'; }

# Resolve HOOKS_FILE with an explicit if-elif-else (instead of the fragile
# `test && echo || (test && echo)` pattern).
if [ -f ./tasks-hooks.sh ]; then
  HOOKS_FILE="./tasks-hooks.sh"
elif [ -f ./docs/tasks-hooks.sh ]; then
  HOOKS_FILE="./docs/tasks-hooks.sh"
else
  HOOKS_FILE=""
fi

if [ -n "$HOOKS_FILE" ] && [ -x "$HOOKS_FILE" ]; then
  "$HOOKS_FILE" "$(_optimus_sanitize "$event")" "$(_optimus_sanitize "$task_id")" "$(_optimus_sanitize "$old_status")" "$(_optimus_sanitize "$new_status")" 2>/dev/null &
fi
```

Events and their parameter signatures:

| Event | Parameters | Description |
|-------|-----------|-------------|
| `status-change` | `event task_id old_status new_status` | Any status transition |
| `task-done` | `event task_id old_status "DONE"` | Task marked as done |
| `task-cancelled` | `event task_id old_status "Cancelado"` | Task cancelled |
| `task-blocked` | `event task_id current_status current_status reason` | Dependency check failed (5 args — includes reason) |

When a dependency check fails (provide defaults so hook payload is never malformed):
```bash
: "${dep_id:=unknown}"
: "${dep_status:=unknown}"
if [ -n "$HOOKS_FILE" ] && [ -x "$HOOKS_FILE" ]; then
  "$HOOKS_FILE" "task-blocked" "$(_optimus_sanitize "$task_id")" "$(_optimus_sanitize "$current_status")" "$(_optimus_sanitize "$current_status")" "$(_optimus_sanitize "blocked by $dep_id ($dep_status)")" 2>/dev/null &
fi
```

Hooks run in background (`&`) and their failure does NOT block the pipeline.
If `tasks-hooks.sh` does not exist, hooks are silently skipped.

Skills reference this as: "Invoke notification hooks — see AGENTS.md Protocol: Notification Hooks."

### Protocol: Ring Droid Requirement Check

**Referenced by:** review, deep-doc-review, coderabbit-review, plan, build

Before dispatching ring droids, verify the required droids are available. If any required
droid is not installed, **STOP** and list missing droids.

**Core review droids** (required by review, pr-check, deep-review, coderabbit-review):
- `ring-default-code-reviewer`
- `ring-default-business-logic-reviewer`
- `ring-default-security-reviewer`
- `ring-default-ring-test-reviewer`

**Extended review droids** (required by review, pr-check, deep-review, coderabbit-review):
- `ring-default-ring-nil-safety-reviewer`
- `ring-default-ring-consequences-reviewer`
- `ring-default-ring-dead-code-reviewer`

**QA droids** (required by review, deep-review, build):
- `ring-dev-team-qa-analyst`

**Documentation droids** (required by deep-doc-review):
- `ring-tw-team-docs-reviewer`
- `ring-default-business-logic-reviewer`
- `ring-default-code-reviewer`

**Implementation droids** (required by build):
- `ring-dev-team-backend-engineer-golang` (Go)
- `ring-dev-team-backend-engineer-typescript` (TypeScript)
- `ring-dev-team-frontend-engineer` (React/Next.js)

**Spec validation droids** (required by plan):
- `ring-default-business-logic-reviewer`
- `ring-default-security-reviewer`
- `ring-dev-team-qa-analyst`
- `ring-default-code-reviewer`

Skills reference this as: "Verify ring droids — see AGENTS.md Protocol: Ring Droid Requirement Check."

### Protocol: Coverage Measurement

**Referenced by:** review, pr-check, coderabbit-review, deep-review, build

Measure test coverage using Makefile targets with stack-specific fallbacks.

**Run coverage quietly.** Coverage commands are the single biggest source of
verbose output (N packages × per-file coverage lines). Wrap them with
`_optimus_quiet_run` (see Protocol: Quiet Command Execution) so the full output
lands on disk and only a PASS/FAIL line reaches the agent. Then read only the
"total" summary line to extract the percentage.

**Unit coverage command resolution order:**
1. `make test-coverage` (if Makefile target exists), run via `_optimus_quiet_run`
2. Stack-specific fallback:
   - Go: `go test -coverprofile=coverage-unit.out ./...` (wrapped) then `go tool cover -func=coverage-unit.out`
   - Node: `npm test -- --coverage` (wrapped)
   - Python: `pytest --cov=. --cov-report=term` (wrapped)

If no unit coverage command is available, mark as **SKIP** — do not fail the verification.

**Integration coverage command resolution order:**
1. `make test-integration-coverage` (if Makefile target exists), run via `_optimus_quiet_run`
2. Stack-specific fallback:
   - Go: `go test -tags=integration -coverprofile=coverage-integration.out ./...` (wrapped) then `go tool cover -func=coverage-integration.out`
   - Node: `npm run test:integration -- --coverage` (wrapped)
   - Python: `pytest -m integration --cov=. --cov-report=term` (wrapped)

If no integration coverage command is available, mark as **SKIP** — do not fail the verification.

**Extracting the percentage (agent-visible output):** after the wrapped run, emit
only the total line. Examples:

```bash
# Go
_optimus_quiet_run "make-test-coverage" make test-coverage
if [ -f coverage-unit.out ]; then
  go tool cover -func=coverage-unit.out | awk '/^total:/ {print "Unit coverage: " $NF}'
fi

# Node (Istanbul JSON/text-summary)
_optimus_quiet_run "npm-test-coverage" npm test -- --coverage
if [ -f coverage/coverage-summary.json ]; then
  jq -r '.total.lines.pct | "Unit coverage: \(.)%"' coverage/coverage-summary.json
fi

# Python (pytest-cov)
_optimus_quiet_run "pytest-cov" pytest --cov=. --cov-report=term --cov-report=json:coverage.json
if [ -f coverage.json ]; then
  jq -r '.totals.percent_covered_display | "Unit coverage: \(.)%"' coverage.json
fi
```

The agent sees ~2 lines total (PASS verdict + "Unit coverage: 87.4%"). The full
per-file breakdown stays in `.optimus/logs/` and in the native coverage files.

**Thresholds:**

| Test Type | Threshold | Verdict if Below |
|-----------|-----------|-----------------|
| Unit tests | 85% | NEEDS_FIX / HIGH finding |
| Integration tests | 70% | NEEDS_FIX / HIGH finding |

**Coverage gap analysis:** When scanning for untested functions/methods (0% coverage),
read the coverage output file (not the agent turn stdout) — either the native
`coverage-*.out` / `coverage-summary.json` / `coverage.json` file, or the
`.optimus/logs/<timestamp>-*-coverage-*.log` file produced by `_optimus_quiet_run`
(the trailing `-<pid>` segment is part of every helper-produced log filename).
Flag business-logic functions with 0% as HIGH, infrastructure/generated code with
0% as SKIP.

Skills reference this as: "Measure coverage — see AGENTS.md Protocol: Coverage Measurement."

### Protocol: PR Title Validation

**Referenced by:** stages 2-4

Check if a PR exists for the current branch:
```bash
gh pr view --json number,title --jq '{number, title}' 2>/dev/null
```

If a PR exists, validate its title follows **Conventional Commits 1.0.0**:
- Regex: `^(feat|fix|refactor|chore|docs|test|build|ci|style|perf)(\([a-zA-Z0-9_\-]+\))?!?: .+$`
- Cross-check the type against the task's **Tipo** column (Feature→`feat`, Fix→`fix`, Refactor→`refactor`, Chore→`chore`, Docs→`docs`, Test→`test`)
- **If title is invalid:** warn via `AskUser`: "PR #N title `<current>` does not follow Conventional Commits. Suggested: `<corrected>`. Fix now with `gh pr edit <number> --title \"<corrected>\"`?"
- **If title is valid:** proceed silently
- If no PR exists, skip.

Skills reference this as: "Validate PR title — see AGENTS.md Protocol: PR Title Validation."

### Protocol: TaskSpec Resolution

**Referenced by:** plan, build, review

Resolve the full path to a task's Ring pre-dev spec and its subtasks directory:

1. Read the task's `TaskSpec` column from `optimus-tasks.md`
2. If `TaskSpec` is `-` → **STOP**: "Task T-XXX has no Ring pre-dev spec. Link one via `/optimus-tasks` or `/optimus-import`."
3. Resolve full path: `TASK_SPEC_PATH = <TASKS_DIR>/<TaskSpec>`
4. **Path traversal validation (HARD BLOCK):** `TaskSpec` must resolve to a file **inside `TASKS_DIR`**.
   This prevents a malicious TaskSpec value like `../../../etc/passwd` from escaping the
   Ring pre-dev tree. Also rejects symlinks to prevent symlink-bypass TOCTOU attacks:
   ```bash
   TASKS_DIR_ABS=$(cd "$TASKS_DIR" 2>/dev/null && pwd) || { echo "ERROR: tasksDir does not exist." >&2; exit 1; }
   RESOLVED_PATH=$(cd "$TASKS_DIR_ABS" && realpath -m "$TASK_SPEC" 2>/dev/null \
     || python3 -c "import os,sys; print(os.path.realpath(os.path.join(sys.argv[1], sys.argv[2])))" "$TASKS_DIR_ABS" "$TASK_SPEC" 2>/dev/null)
   if [ -z "$RESOLVED_PATH" ]; then
     echo "ERROR: Cannot resolve TaskSpec path — realpath and python3 both unavailable." >&2
     exit 1
   fi
   case "$RESOLVED_PATH" in
     "$TASKS_DIR_ABS"/*) ;; # OK — within tasksDir
     *) echo "ERROR: TaskSpec path traversal detected — resolved path is outside tasksDir." >&2; exit 1 ;;
   esac
   # Reject symlinks: if TASK_SPEC itself or any intermediate component is a
   # symlink, a TOCTOU attacker could swap the target between validation and
   # read. realpath -m resolves symlinks transparently; this post-check ensures
   # no symlink is present in the final path.
   if [ -L "$RESOLVED_PATH" ]; then
     echo "ERROR: TaskSpec resolves to a symlink — refusing to read." >&2
     exit 1
   fi
   ```

   **Validate `TASKS_DIR` itself:** `TASKS_DIR` must be inside a valid git repository
   (same repo as project, OR a separate repo — both are allowed). Resolution of
   `TASKS_GIT_SCOPE` (Protocol: Resolve Tasks Git Scope) already enforces this by
   running `git -C "$TASKS_DIR" rev-parse --show-toplevel`. If that call fails,
   `TASKS_DIR` is not a git repository and skills STOP.

   **NOTE:** `TASKS_DIR` is NO LONGER required to be inside `PROJECT_ROOT`. Teams using
   separate-repo scope (e.g., `tasksDir: ../tasks-repo/project-alfa`) are supported.
   The security guarantee is that the **TaskSpec value** cannot escape `TASKS_DIR`.

5. Read the task spec file at `TASK_SPEC_PATH`
6. Derive subtasks directory: if TaskSpec is `tasks/task_001.md`, subtasks are at `<TASKS_DIR>/subtasks/T-001/`
7. If subtasks directory exists, read all `.md` files inside it

Skills reference this as: "Resolve TaskSpec — see AGENTS.md Protocol: TaskSpec Resolution."

### Protocol: Project Rules Discovery

**Referenced by:** stages 1-4, deep-review, coderabbit-review

Every skill that reviews, validates, or generates code MUST search for project rules
and AI instruction files before starting. Search for these files in order and read ALL
that exist:

```
AGENTS.md                    # Primary agent instructions
CLAUDE.md                    # Claude-specific rules
DROIDS.md                    # Droid-specific rules
.cursorrules                 # Cursor-specific rules
PROJECT_RULES.md             # Coding standards (root or docs/)
docs/PROJECT_RULES.md
.editorconfig                # Editor formatting rules
docs/coding-standards.md     # Explicit coding conventions
docs/conventions.md
.github/CONTRIBUTING.md      # Contribution guidelines
CONTRIBUTING.md
.eslintrc*                   # Linter configs (implicit rules)
biome.json
.golangci.yml
.prettierrc*
```

If NONE exist, warn the user. If any are found, they become the source of truth
for coding standards and must be passed to every dispatched sub-agent.

Skills reference this as: "Discover project rules — see AGENTS.md Protocol: Project Rules Discovery."

### Protocol: Re-run Guard

**Referenced by:** plan, review

After the convergence loop exits and the final report/summary is presented, evaluate
whether to suggest advancement or offer a re-run. This protocol replaces the static
"Next step suggestion" in plan and review.

**Logic:**

1. Count `total_findings` produced during this execution (all findings from round 1 AND
   any convergence rounds that were dispatched — note: with opt-in gating, the user may
   have skipped them all, in which case only round 1 contributes — from all agents and
   static analysis, regardless of whether they were fixed or skipped by the user). If
   findings were grouped (per Finding Presentation item 3), count grouped entries, not
   individual occurrences.
2. **If `total_findings == 0`:** The analysis is clean. Suggest the next stage:
   - plan: "Spec validation clean — 0 findings. Next step: run `/optimus-build` to implement this task."
   - review: "Implementation review clean — 0 findings. Next step: run `/optimus-done` to close this task."
3. **If `total_findings > 0`:** Ask via `AskUser`:
   ```
   Validation found N findings (X fixed, Y skipped).
   Re-running dispatches ALL review agents again with clean context (no memory of
   previous findings — findings you previously skipped will reappear for review).
   This will consume similar tokens to the initial run. Workspace and status are preserved.
   ```
   Options:
   - **Re-run with clean context** — re-analyze from scratch
   - **Advance to next stage** — proceed despite findings

4. **If "Re-run with clean context":**
   - Increment stage stats (new execution)
   - **Skip:** GitHub CLI check, optimus-tasks.md validation, task identification, session state
     check, status validation/change, workspace creation, divergence check
   - **Re-execute:** project structure discovery, document loading, static analysis,
     coverage profiling, agent dispatch (ALL agents), finding presentation, fix application,
     convergence loop entry gate (and any rounds the user opts into)
   - **Session file:** After re-run starts, the session protocol (Protocol: Session State)
     resumes normal operation — update the session file at each phase transition as usual.
     This ensures crash recovery during a re-run resumes from the correct phase.
   - After the re-run completes, apply this protocol again (evaluate findings count)
   - There is no limit on re-runs — the user controls when to stop

5. **If "Advance to next stage":** Proceed to push commits and present the next step suggestion.

**NOTE:** "0 findings" means the analysis produced zero findings — not that all findings
were resolved. If the user skipped findings in a previous run, they will reappear on
re-run (clean context has no memory of previous decisions). This is by design.

**NOTE:** Re-run analyzes the current codebase state, including any fixes applied and
committed during the previous run. It does NOT revert commits. This validates that
applied fixes are correct and checks for any issues introduced by the fixes.

Skills reference this as: "Execute re-run guard — see AGENTS.md Protocol: Re-run Guard."

### Protocol: Push Commits (optional)

**Referenced by:** plan, build, review, coderabbit-review. Note: done handles pushing inline in its own cleanup phase. pr-check and deep-review have their own push phases.

After stage work is complete, offer to push all local commits:

**Step 1 — Check if upstream tracking exists:**

```bash
git rev-parse --abbrev-ref @{u} 2>/dev/null
```

- **If command fails (no upstream):** The branch was never pushed. All local commits are unpushed.
  Ask via `AskUser`:
  ```
  Branch has no upstream (never pushed). Push now?
  ```
  Options:
  - **Push now** — `git push -u origin "$(git branch --show-current)"`
  - **Skip** — I'll push manually later

- **If command succeeds (upstream exists):** Check for unpushed commits:
  ```bash
  git log @{u}..HEAD --oneline 2>/dev/null
  ```
  If there are unpushed commits, ask via `AskUser`:
  ```
  There are N unpushed commits on this branch. Push now?
  ```
  Options:
  - **Push now** — `git push`
  - **Skip** — I'll push manually later

**Why check upstream first:** `git log @{u}..HEAD` silently produces empty output when no
upstream exists, making it appear there's nothing to push. Without this check, the push step
would be silently skipped even though ALL local commits are unpushed.

**Step 2 — Check tasks repo in separate-repo mode:**

If `$TASKS_GIT_SCOPE = "separate-repo"`, the tasks repo is independent from the project
repo. Commits made via `tasks_git commit` (e.g., Active Version Guard) land in the tasks
repo and must be pushed separately. Skipping this makes team members pull project main
without seeing version/task changes.

```bash
if [ "$TASKS_GIT_SCOPE" = "separate-repo" ]; then
  # Check if tasks-repo current branch has upstream
  if ! tasks_git rev-parse --abbrev-ref @{u} >/dev/null 2>&1; then
    TASKS_BRANCH=$(tasks_git branch --show-current 2>/dev/null)
    # AskUser: "Tasks repo branch '$TASKS_BRANCH' has no upstream. Push now?"
    # Options: Push now — `tasks_git push -u origin "$TASKS_BRANCH"` / Skip
  else
    TASKS_UNPUSHED=$(tasks_git log @{u}..HEAD --oneline 2>/dev/null)
    if [ -n "$TASKS_UNPUSHED" ]; then
      TASKS_UNPUSHED_COUNT=$(printf '%s\n' "$TASKS_UNPUSHED" | wc -l | tr -d ' ')
      # AskUser: "Tasks repo has $TASKS_UNPUSHED_COUNT unpushed commits. Push now?"
      # Options: Push now — `tasks_git push` / Skip
    fi
  fi
fi
```

**After a successful push**, check if the current repo is the Optimus plugin repository
and update installed plugins to pick up the changes just pushed:

```bash
if jq -e '.name == "optimus"' .factory-plugin/marketplace.json >/dev/null 2>&1; then
  echo "Optimus repo detected — updating installed plugins..."
  for skill in $(droid plugin list 2>/dev/null | grep optimus | awk '{print $1}'); do
    droid plugin update "$skill" 2>/dev/null
  done
fi
```

This ensures that agents running in the Optimus repo itself always use the latest
skill versions after pushing changes.

Skills reference this as: "Offer to push commits — see AGENTS.md Protocol: Push Commits."

### Protocol: State Management

**Referenced by:** all stage agents (1-4), tasks, report, quick-report, import, batch

All status and branch data is stored in `.optimus/state.json` (gitignored).

**Prerequisites:**

```bash
if ! command -v jq >/dev/null 2>&1; then
  echo "ERROR: jq is required for state management but not installed." >&2
  exit 1
fi
```

**Reading state:**

```bash
# Requires Protocol: Resolve Main Worktree Path to have run first
# (or resolve inline; see that protocol).
MAIN_WORKTREE="$(git worktree list --porcelain 2>/dev/null | awk '/^worktree / {print $2; exit}')"
STATE_FILE="${MAIN_WORKTREE}/.optimus/state.json"
if [ -f "$STATE_FILE" ]; then
  # Validate JSON integrity before reading
  if ! jq empty "$STATE_FILE" 2>/dev/null; then
    echo "WARNING: state.json is corrupted. Running reconciliation."
    rm -f "$STATE_FILE"
    # Fall through to missing-file handling below
  fi
fi
if [ -f "$STATE_FILE" ]; then
  TASK_STATUS=$(jq -r --arg id "$TASK_ID" '.[$id].status // "Pendente"' "$STATE_FILE")
  TASK_BRANCH=$(jq -r --arg id "$TASK_ID" '.[$id].branch // ""' "$STATE_FILE")
else
  TASK_STATUS="Pendente"
  TASK_BRANCH=""
fi
```

A task with no entry in state.json is implicitly `Pendente`.

**Writing state:**

```bash
# Requires Protocol: Resolve Main Worktree Path to have run first
# (or resolve inline; see that protocol).
MAIN_WORKTREE="$(git worktree list --porcelain 2>/dev/null | awk '/^worktree / {print $2; exit}')"
# Initialize .optimus directory — see AGENTS.md Protocol: Initialize .optimus Directory.
STATE_FILE="${MAIN_WORKTREE}/.optimus/state.json"
if [ ! -f "$STATE_FILE" ]; then
  echo '{}' > "$STATE_FILE"
fi
if [ -z "$TASK_ID" ] || [ -z "$NEW_STATUS" ]; then
  echo "ERROR: Cannot write state — TASK_ID or NEW_STATUS is empty." >&2
  exit 1
fi
UPDATED_AT=$(date -u +%Y-%m-%dT%H:%M:%SZ)
if jq --arg id "$TASK_ID" --arg status "$NEW_STATUS" --arg branch "$BRANCH_NAME" --arg ts "$UPDATED_AT" \
  '.[$id] = {status: $status, branch: $branch, updated_at: $ts}' "$STATE_FILE" > "${STATE_FILE}.tmp"; then
  if jq empty "${STATE_FILE}.tmp" 2>/dev/null; then
    mv "${STATE_FILE}.tmp" "$STATE_FILE"
  else
    rm -f "${STATE_FILE}.tmp"
    echo "ERROR: jq produced invalid JSON — state.json unchanged" >&2
    exit 1
  fi
else
  rm -f "${STATE_FILE}.tmp"
  echo "ERROR: jq failed to update state.json" >&2
  exit 1
fi
```

**Removing entry (for Pendente reset):**

```bash
# Requires Protocol: Resolve Main Worktree Path to have run first
# (or resolve inline; see that protocol).
MAIN_WORKTREE="$(git worktree list --porcelain 2>/dev/null | awk '/^worktree / {print $2; exit}')"
STATE_FILE="${MAIN_WORKTREE}/.optimus/state.json"
if [ ! -f "$STATE_FILE" ]; then
  echo "state.json does not exist — task is already implicitly Pendente."
else
  if jq --arg id "$TASK_ID" 'del(.[$id])' "$STATE_FILE" > "${STATE_FILE}.tmp"; then
    mv "${STATE_FILE}.tmp" "$STATE_FILE"
  else
    rm -f "${STATE_FILE}.tmp"
    echo "ERROR: jq failed to update state.json"
  fi
fi
```

**Listing all tasks with status (for report/quick-report):**

```bash
# Requires Protocol: Resolve Main Worktree Path to have run first
# (or resolve inline; see that protocol).
MAIN_WORKTREE="$(git worktree list --porcelain 2>/dev/null | awk '/^worktree / {print $2; exit}')"
STATE_FILE="${MAIN_WORKTREE}/.optimus/state.json"
# TASKS_FILE is resolved via Protocol: Resolve Tasks Git Scope (<tasksDir>/optimus-tasks.md).
# Validate state.json if it exists
if [ -f "$STATE_FILE" ] && ! jq empty "$STATE_FILE" 2>/dev/null; then
  echo "WARNING: state.json is corrupted. Treating all tasks as Pendente."
  rm -f "$STATE_FILE"
fi
# Get all task IDs from optimus-tasks.md
TASK_IDS=$(grep -E '^\| T-[0-9]+ \|' "$TASKS_FILE" | awk -F'|' '{print $2}' | tr -d ' ')
# For each task, read status from state.json (default: Pendente)
for TASK_ID in $TASK_IDS; do
  if [ -f "$STATE_FILE" ]; then
    STATUS=$(jq -r --arg id "$TASK_ID" '.[$id].status // "Pendente"' "$STATE_FILE")
  else
    STATUS="Pendente"
  fi
  echo "$TASK_ID: $STATUS"
done
```

**state.json is NEVER committed.** It is gitignored. No `git add` or `git commit`
for state changes.

**Reconciliation (if state.json is lost or empty):**
1. List all worktrees: `git worktree list`
2. For each worktree matching a task ID pattern (e.g., `t-003` in the path),
   infer status as `Em Andamento` (most common in-progress status)
3. Tasks without worktrees are `Pendente`
4. Ask the user to confirm before proceeding

**Automatic mismatch detection:** Stage agents SHOULD check for inconsistencies on startup:
if state.json is missing or empty AND worktrees exist for known task IDs, warn the user
and offer to run reconciliation before proceeding. This prevents tasks from silently
appearing as `Pendente` when they actually have active worktrees.

Skills reference this as: "Read/write state.json — see AGENTS.md Protocol: State Management."

### Protocol: Branch Name Derivation

**Referenced by:** plan, build, review, pr-check, done (workspace auto-navigation)

Branch names are derived deterministically from the task's structural data in optimus-tasks.md.
They are NOT stored in optimus-tasks.md — they are stored in state.json for quick reference
and can always be re-derived.

**Derivation rule:**

```
<tipo-prefix>/<task-id-lowercase>-<keywords>
```

Where:
- `<tipo-prefix>` is mapped from the Tipo column: Feature→`feat`, Fix→`fix`,
  Refactor→`refactor`, Chore→`chore`, Docs→`docs`, Test→`test`
- `<task-id-lowercase>` is the task ID in lowercase (e.g., `t-003`)
- `<keywords>` are 2-4 lowercase words from the Title, stripping articles,
  prepositions, and generic words (implement, add, create, update)

**Sanitization (applied to keywords before constructing branch name):**
1. Convert to lowercase
2. Replace non-alphanumeric characters (except hyphens) with hyphens
3. Collapse consecutive hyphens to a single hyphen
4. Remove leading/trailing hyphens from each keyword
5. Truncate the full branch name to 100 characters

**Examples:**
- T-003 "User Auth JWT" (Feature) → `feat/t-003-user-auth-jwt`
- T-007 "Duplicate Login" (Fix) → `fix/t-007-duplicate-login`
- T-012 "Extract Middleware" (Refactor) → `refactor/t-012-extract-middleware`
- T-015 "User Auth: JWT/OAuth2 Support" (Feature) → `feat/t-015-user-auth-jwt-oauth2-support`

**Resolution order when looking for a task's branch:**
1. Read `branch` from state.json (fastest)
2. Search by task ID: `git branch --list "*<task-id>*"` or `git worktree list | grep -iF "<task-id>"`
3. Derive from Tipo + ID + Title (always works)

Skills reference this as: "Derive branch name — see AGENTS.md Protocol: Branch Name Derivation."

### Protocol: Default Scope Resolution

**Referenced by:** report, quick-report

Both `report` and `quick-report` support a version scope filter (`ativa`, `upcoming`,
`all`, or a specific version name). Resolve the effective scope in this order:

1. **Invocation wins.** If the user specified a scope in the invocation (e.g.,
   "quick report all", "report v2", "report upcoming"), use that scope directly.
   Skip steps 2-3.

   **Force-ask keywords:** If the invocation contains `ask` or `menu`
   (e.g., "quick report ask", "report menu"), skip step 2 and go straight to step 3
   (the AskUser prompt). This lets the user override the saved default for a single run
   and optionally overwrite it.

2. **Config fallback.** If `.optimus/config.json` has a `defaultScope` key, use it:
   ```bash
   CONFIG_FILE="${MAIN_WORKTREE}/.optimus/config.json"
   if [ -f "$CONFIG_FILE" ] && jq -e '.defaultScope' "$CONFIG_FILE" >/dev/null 2>&1; then
     SCOPE=$(jq -r '.defaultScope' "$CONFIG_FILE")
   fi
   ```
   **Validation:** `SCOPE` must be `ativa`, `upcoming`, `all`, or match a version name in
   the `## Versions` table of `optimus-tasks.md`. If invalid (empty, unknown keyword, or a version
   name that no longer exists), warn the user and fall through to step 3.
   ```
   WARNING: .optimus/config.json has defaultScope="<value>" but it is not valid
   (must be ativa/upcoming/all or an existing version name). Falling back to prompt.
   ```

3. **Ask user.** Present the standard AskUser prompt:
   ```
   Which version scope do you want to see?
   ```
   Options:
   - **Ativa** — only tasks from the active version (`<active_version_name>`)
   - **Upcoming** — active + planned (Ativa, Próxima, Planejada — excludes Backlog and Concluída)
   - **All** — all tasks across all versions
   - **Specific version** — pick one version by name (follow-up AskUser lists versions)

4. **Offer to persist (only when step 3 ran).** After the user picks a scope in step 3,
   ask a follow-up via AskUser:
   ```
   Save "<chosen_scope>" as the default in .optimus/config.json?
   You can still override per-invocation (e.g., "quick report all") or
   use "quick report ask" to be prompted again.
   ```
   Options:
   - **Save as default** — write `defaultScope` to `.optimus/config.json`
   - **Just this time** — do not persist

5. **Persist the scope (if user chose to save):**
   ```bash
   # Initialize .optimus directory — see AGENTS.md Protocol: Initialize .optimus Directory.
   CONFIG_FILE="${MAIN_WORKTREE}/.optimus/config.json"
   if [ ! -f "$CONFIG_FILE" ]; then
     echo '{}' > "$CONFIG_FILE"
   fi
   if jq --arg s "$SCOPE" '.defaultScope = $s' "$CONFIG_FILE" > "${CONFIG_FILE}.tmp"; then
     if jq empty "${CONFIG_FILE}.tmp" 2>/dev/null; then
       mv "${CONFIG_FILE}.tmp" "$CONFIG_FILE"
     else
       rm -f "${CONFIG_FILE}.tmp"
       echo "ERROR: jq produced invalid JSON — config.json unchanged"
     fi
   else
     rm -f "${CONFIG_FILE}.tmp"
     echo "ERROR: jq failed to update config.json"
   fi
   ```
   **NOTE:** `config.json` is gitignored (per-user preference). The saved `defaultScope`
   affects only the local environment — each user can choose their own default. These
   skills are read-only for code/tasks — writing to `config.json` is the single allowed
   side-effect, and only when the user explicitly agrees.

**NOTE:** Scope names are case-insensitive for user input. Normalize to lowercase for
`ativa`/`upcoming`/`all`, but preserve the original casing when the scope is a specific
version name (version names are case-sensitive to match the Versions table).

Skills reference this as: "Resolve default scope — see AGENTS.md Protocol: Default Scope Resolution."

### Protocol: Active Version Guard

**Referenced by:** all stage agents (1-4)

After the task ID is confirmed and dependencies are validated, check if the task belongs
to the `Ativa` version. If not, present options before proceeding.

1. Read the task's **Version** column from `optimus-tasks.md`
2. Read the **Versions** table and find the version with Status `Ativa`
   - **If no version has Status `Ativa`** → **STOP**: "No active version found in the Versions table. Run `/optimus-tasks` to set a version as Ativa before proceeding."
3. **If the task's version matches the `Ativa` version** → proceed silently
4. **If the task's version does NOT match the `Ativa` version** → present via `AskUser`:
   ```
   Task T-XXX is in version '<task_version>' (<version_status>),
   but the active version is '<active_version>'.
   To execute this task, it must be moved to the active version first.
   ```
   Options:
   - **Move to active version and continue** — updates the Version column to the active version, commits, and proceeds
   - **Cancel** — stops execution

5. **If "Move to active version and continue":**
   - Update the task's Version column in `optimus-tasks.md` to the `Ativa` version name
   - Commit using `tasks_git` so the change lands in the correct repo (same-repo or
     separate-repo, as resolved by Protocol: Resolve Tasks Git Scope):
     ```bash
     tasks_git add "$TASKS_GIT_REL"
     COMMIT_MSG_FILE=$(mktemp -t optimus.XXXXXX) || { echo "ERROR: mktemp failed" >&2; exit 1; }
     chmod 600 "$COMMIT_MSG_FILE"
     printf '%s' "chore(tasks): move T-XXX to active version <active_version>" > "$COMMIT_MSG_FILE"
     tasks_git commit -F "$COMMIT_MSG_FILE"
     rm -f "$COMMIT_MSG_FILE"
     ```
   - Proceed with the stage

6. **If "Cancel":** **STOP** — do not proceed with the stage

Skills reference this as: "Check active version guard — see AGENTS.md Protocol: Active Version Guard."

## Verification Command Convention

All projects using Optimus MUST have a `Makefile` with standardized targets.
Skills call `make <target>` directly — no configuration needed.

### Required Makefile Targets (HARD BLOCK if missing)

| Target | Purpose |
|--------|---------|
| `make lint` | Run linters |
| `make test` | Run unit tests |

### Optional Makefile Targets (SKIP if missing)

| Target | Purpose |
|--------|---------|
| `make test-integration` | Run integration tests |
| `make test-coverage` | Run unit tests with coverage report |
| `make test-integration-coverage` | Run integration tests with coverage report |

If an optional target does not exist, skills mark that check as **SKIP** — they do NOT
fail or ask the user. For coverage targets, if `make test-coverage` is missing, skills
fall back to stack-specific commands (see Protocol: Coverage Measurement).

## Common Patterns Across Skills

The patterns below apply to **cycle review skills** (plan, review,
pr-check, coderabbit-review). `deep-doc-review` follows the same user-authority and finding
presentation principles, applies fixes inline (not batch-apply), and offers the convergence
loop (opt-in) to catch issues introduced by fixes. `deep-review` requires ring droids for
analysis, has its own opt-in convergence loop (Phase 7), and uses batch-apply (Phase 6) —
but applies fixes directly rather than via ring droid TDD cycle.

### Finding Presentation (Unified Model)
All cycle review skills follow this pattern:
1. Collect findings from agents/tools
2. Consolidate and deduplicate
3. **Group same-nature findings** — after deduplication, identify findings that share the
   same root cause or fix pattern (e.g., "missing error handling" in 5 handlers, "inconsistent
   import path" in 4 files). If 2+ findings are of the same nature, merge them into a **single
   grouped entry** listing all affected files/locations. Each group counts as ONE item in the
   `"(X/N)"` sequence. The user makes ONE decision for the entire group.
4. Announce total findings count: `"### Total findings to review: N"` (where N reflects
   grouped entries — a group of 5 same-nature findings counts as 1)
5. Present overview table with severity counts
6. **Deep research BEFORE presenting each finding** (see research checklist below)
7. Walk through findings ONE AT A TIME with `"(X/N)"` progress prefix in the header, ordered by severity
   (CRITICAL first, then HIGH, MEDIUM, LOW). **ALL findings MUST be presented regardless of
   severity** — the agent NEVER skips, filters, or auto-resolves any finding. The decision to
   fix or skip is ALWAYS the user's. For grouped entries, list all affected files/locations
   within the single presentation.
8. For each finding: present research-backed analysis + options, collect decision via AskUser.
   **Every AskUser for a finding decision MUST include these options:**
   - One option per proposed solution (Option A, Option B, Option C, etc.)
   - Skip — no action
   - Tell me more — if selected, STOP and answer immediately (do NOT continue to next finding)

   **AskUser template (MANDATORY — follow this exact structure for every finding):**
   ```
   1. [question] (X/N) SEVERITY — Finding title summary
   [topic] (X/N) F#-Category
   [option] Option A: recommended fix
   [option] Option B: alternative approach
   [option] Skip
   [option] Tell me more
   ```

9. **HARD BLOCK — IMMEDIATE RESPONSE RULE — If the user selects "Tell me more" OR responds
   with free text (a question, disagreement, or request for clarification):**
   **STOP IMMEDIATELY.** Do NOT continue to the next finding. Do NOT batch the response.
   Research the user's concern RIGHT NOW using `WebSearch`, codebase analysis, or both.
   Provide a thorough answer with evidence (links, code references, best practice citations).
   Only AFTER the user is satisfied, re-present the SAME finding's options and ask for
   their decision again. This may go back and forth multiple times — that is expected.
   **NEVER defer the response to the end of the findings loop.**

   **Anti-rationalization (excuses the agent MUST NOT use to skip immediate response):**
   - "I'll address all questions after presenting the remaining findings" — NO
   - "Let me continue with the next finding and come back to this" — NO
   - "I'll research this after the findings loop" — NO
   - "This is noted, moving to the next finding" — NO
10. After ALL N decisions collected: apply ALL approved fixes (see below)
11. Run verification (see Verification Timing below)
12. Present final summary

### Fix Implementation (Complexity-Based Dispatch)

Fixes are classified by complexity. **Simple fixes** are applied directly by the
orchestrator. **Complex fixes** (or fixes whose complexity cannot be determined) are
delegated to specialist ring droids.

#### Complexity Classification

For each approved fix, assess complexity BEFORE applying:

**Simple fix (apply directly):**
- The review agent already provided the exact code change needed
- Single file, localized change (few lines)
- Obvious resolution: typo, missing error check, wrong variable name, missing nil guard,
  import fix, formatting, adding a log line, renaming, removing dead code
- No new logic, no architectural impact, no new test scenarios needed

**Complex fix (dispatch ring droid):**
- Multiple files affected
- Requires understanding broader codebase context or architectural decisions
- New functionality, significant refactoring, or new integration points
- Requires new test scenarios (not just updating existing ones)
- Security-sensitive changes (auth, crypto, input validation)
- Database schema, API contract, or config changes
- The orchestrator is unsure how to fix it

**When in doubt → dispatch ring droid.** If you cannot confidently classify a fix as
simple, treat it as complex.

#### Direct Fix (simple findings)

The orchestrator applies the fix directly using Edit/MultiEdit tools. After applying:
1. Run unit tests to verify no regression
2. If tests fail, revert and escalate to ring droid dispatch

#### Ring Droid Dispatch (complex findings)

**Code fixes** → dispatch ring backend/frontend/QA droids with **TDD cycle** (RED-GREEN-REFACTOR):
- `ring-dev-team-backend-engineer-golang` (Go), `ring-dev-team-backend-engineer-typescript` (TS),
  `ring-dev-team-frontend-engineer` (React/Next.js), `ring-dev-team-qa-analyst` (tests)

**Documentation fixes** → dispatch ring documentation droids **without TDD** (no tests for docs):
- `ring-tw-team-functional-writer` (guides), `ring-tw-team-api-writer` (API docs),
  `ring-tw-team-docs-reviewer` (quality fixes)

**Ring droids are REQUIRED for complex fixes** — there is no alternative dispatch mechanism. If the
required droids are not installed and a complex fix is needed, the skill MUST stop and
inform the user which droids need to be installed.

### Verification Timing (cycle review skills)

Verification commands are expensive. The timing rules below optimize for fast feedback
during development while ensuring full validation before push.

| Check | When to run | Skills affected |
|-------|-------------|----------------|
| **Unit tests** (`make test`) | BEFORE review (baseline) + AFTER each fix (regression) | stages 3, 4, coderabbit |
| **Lint** (`make lint`) | ONCE after ALL fixes applied | stages 3, 4, coderabbit |
| **Integration tests** (`make test-integration`) | ONCE before push (or when user invokes directly) | stages 3, 4 |

**Rationale:**
- Unit tests are fast and catch regressions immediately — run often
- Lint is fast but only matters after all code is finalized — run once at end
- Integration tests are slow (seconds to minutes) — run once before push to avoid
  blocking the review loop. If targets don't exist, skip.

### Coverage Thresholds

| Test Type | Threshold | Verdict if Below |
|-----------|-----------|-----------------|
| Unit tests | 85% | NEEDS_FIX / HIGH finding |
| Integration tests | 70% | NEEDS_FIX / HIGH finding |

All skills that measure coverage MUST use these thresholds. If coverage profiles cannot
be generated (command fails or tool missing), report as SKIP — do not fail the verification.

### Deep Research Before Presenting (MANDATORY for cycle review skills)
Applies to: plan, review, pr-check, coderabbit-review

**BEFORE presenting any finding to the user, the agent MUST research it deeply.** This
research is done SILENTLY — do not show the research process. Present only the conclusions.

**Research checklist (ALL items, every finding):**

1. **Project patterns:** Read the affected file(s) fully. Check how similar cases are handled
   elsewhere in the codebase. Identify existing conventions the finding might violate or follow.
2. **Architectural decisions:** Review project rules (AGENTS.md, PROJECT_RULES.md, etc.) and
   architecture docs (TRD, ADRs). Understand WHY the project is structured this way before
   suggesting changes.
3. **Existing codebase:** Search for precedent. If the codebase already does the same thing
   in 10 other places without issue, that context changes the finding's weight.
4. **Current task focus:** Is this finding within the scope of the task being worked on?
   Tangential findings should be flagged as such (not dismissed, but contextualized).
5. **User/consumer use cases:** Who consumes this code — end users, other services, internal
   modules? How does the finding affect them? Trace the impact to real user scenarios.
6. **UX impact:** For user-facing changes, evaluate usability, accessibility, error messaging,
   and workflows. Would the user notice? Would it block their work?
7. **API best practices:** For API changes, check REST conventions, error handling patterns,
   idempotency, status codes, pagination, versioning, and backward compatibility.
8. **Engineering best practices:** SOLID principles, DRY, separation of concerns, error
   handling, resilience patterns, observability, testability.
9. **Language-specific best practices:** Use `WebSearch` to research idioms and conventions
   for the specific language (Go, TypeScript, Python, etc.). Check official style guides,
   common linter rules, and community-accepted patterns.
10. **Correctness over convenience:** Always recommend the correct approach, regardless of
    effort. The easy option may be presented as an alternative, but Option A must be what
    the agent believes is right based on all the research above.
11. **Production resilience:** Would this code survive production conditions? Consider:
    timeouts on external calls, retry with backoff, circuit breakers, graceful degradation,
    resource cleanup (connections, handles, goroutines), graceful shutdown, and behavior
    under load (N+1 queries, unbounded queries, connection pool exhaustion).
12. **Data integrity and privacy:** Are transaction boundaries correct? Could partial writes
    occur? Is PII properly handled (not logged, masked in responses)? LGPD/GDPR compliance?

**After research, form the recommendation:** Option A MUST be the approach the agent
believes is correct based on the research. It must be backed by evidence (project patterns,
best practice references, official documentation), not just a generic suggestion.

### Finding Option Format (MANDATORY for cycle review skills)

Every finding must present 2-3 options with this structure:

```
**Option A: [name] (RECOMMENDED)**
[Concrete steps — what to do, which files to change, what code to write]
- Why recommended: [reference to research — best practice, project pattern, official docs]
- Impact: [UX / Task focus / Project focus / Engineering quality]
- Effort: [low / medium / high / very high]
- Estimated time: [< 5 min / 5-15 min / 15-60 min / 1-4h / > 4h]

**Option B: [name]**
[Alternative approach]
- Impact: [UX / Task focus / Project focus / Engineering quality]
- Effort: [low / medium / high / very high]
- Estimated time: [< 5 min / 5-15 min / 15-60 min / 1-4h / > 4h]
```

**Effort scale:**
- **Low:** Localized change, single file, no tests needed
- **Medium:** Multiple files, straightforward, may need test updates
- **High:** Significant refactoring, new tests, multiple modules affected
- **Very high:** Architectural change, many files, extensive testing, risk of regressions

### Protocol: Convergence Loop (Full Roster Model — Opt-In, Gated)
Applies to: plan, review, pr-check, coderabbit-review, deep-review, deep-doc-review, build

Round 1 (the skill's primary agent dispatch) is MANDATORY and uses the per-skill
default ring roster. Convergence rounds 2+ are OPTIONAL and gated behind explicit
user prompts. Convergence detection (zero new findings) exits the loop silently
without offering further rounds.

- **Round 1:** Orchestrator dispatches the per-skill default roster of specialist
  ring droids in parallel (with full session context). This round is NOT counted
  as a "convergence round" — it is the skill's primary review pass.
- **Rounds 2-5 (each gated by user prompt):** The **same agent roster** as round 1
  is dispatched in parallel via `Task` tool, each with zero prior context. Each
  agent reads all files fresh from disk.
- **Sub-agents do NOT receive the findings ledger.** Dedup is performed entirely
  by the orchestrator after agents return, using **strict matching**: same file +
  same line range (±5 lines) + same category. "Description similarity" is NOT
  sufficient for dedup — the file, location, and category must all match.
- LOW severity findings are NOT a reason to skip presentation — ALL findings are
  presented to the user.

**Entry gate (before round 2 — MANDATORY):** After round 1 completes (decisions
collected, fixes applied), ask via `AskUser`:
```
1. [question] Round 1 produced N findings (X fixed, Y skipped). Run convergence
   round 2 (re-dispatches the same roster with clean context)?
[topic] Convergence-Entry
[option] Run round 2
[option] Skip convergence loop
```
- "Skip convergence loop" → exit with status `SKIPPED`.
- "Run round 2" → dispatch round 2.

**Per-round gate (before rounds 3, 4, 5 — MANDATORY):** After each round 2+
completes (findings presented, fixes applied), before dispatching the next round:
```
1. [question] Round N-1 produced M new findings. Run round N?
[topic] Convergence-RoundN
[option] Continue (run round N)
[option] Stop here
```
- "Stop here" → exit with status `USER_STOPPED`.
- "Continue" → dispatch round N.

**Convergence detection (after each dispatched round — DO NOT ASK):** If a
dispatched round returns ZERO new findings (using the strict matching rules
above), the orchestrator MUST:
1. Print: `Convergence reached at round N: zero new findings.`
2. Exit immediately with status `CONVERGED`.
3. NEVER offer to run another round — the user is informed, not asked.

**Hard limit:** Round 5 is the maximum. After round 5 completes (with new
findings present), exit with status `HARD_LIMIT` without asking.

**Dispatch failure (default):** If a `Task` dispatch fails entirely (transport error,
ring droid unavailable, etc.), do NOT count as zero findings (would falsely
mark `CONVERGED`). Ask via `AskUser`:
```
1. [question] Round N dispatch failed: <error>. Retry, or stop here?
[topic] Convergence-DispatchFail
[option] Retry round N
[option] Stop here
```
- "Retry round N" → re-dispatch.
- "Stop here" → exit with status `DISPATCH_FAILED_ABORTED`.

**Dispatch failure (build-specific carve-out):** `build` runs the convergence loop
deep inside Phase 2.3 of a potentially hours-long multi-subtask implementation. A
blocking prompt at this point is disruptive. `build` therefore MAY treat a single
failed slot as "zero new findings for that slot" and continue silently with a
printed warning. The user is informed via the Final Summary. If multiple slots
fail in the same round, `build` falls back to the default behavior (ask immediately).
This carve-out applies ONLY to `build`; all other skills use the default.

**Exit statuses (recorded for the Final Summary):**

| Status | Trigger |
|--------|---------|
| `CONVERGED` | A dispatched round returned zero new findings |
| `USER_STOPPED` | User chose "Stop here" at a per-round gate (before rounds 3, 4, or 5) |
| `SKIPPED` | User chose "Skip convergence loop" at the entry gate |
| `HARD_LIMIT` | Round 5 completed with new findings still present |
| `DISPATCH_FAILED_ABORTED` | Dispatch failure followed by user choosing to stop |

**Why full roster, not a single agent:** A single generalist agent structurally cannot
replicate the coverage of 8-10 domain specialists. The security-reviewer catches injection
risks a code-reviewer won't. The nil-safety-reviewer catches empty guards a QA analyst won't.
Dispatching a single agent in rounds 2+ creates false convergence — the agent declares
"zero new findings" because it lacks the domain depth, not because the code is clean.

### Agent Dispatch
Skills dispatch specialist ring droids in parallel via Task tool:
- ring-default-* droids (code-reviewer, business-logic-reviewer, security-reviewer, etc.)
- ring-dev-team-* droids (backend-engineer-golang, frontend-engineer, qa-analyst, etc.)
- ring-tw-team-* droids (functional-writer, api-writer, docs-reviewer)

**Ring droids are REQUIRED** — there is no fallback. If the required droids are not
installed, the skill MUST stop and list which droids need to be installed.

**Navigation-enabled prompts:** All agent prompts use a path-based model. Instead of
pasting full file content into the prompt, skills provide file paths and instruct droids
to use Read, Grep, and Glob tools to explore the codebase autonomously. This enables
droids to discover context the orchestrator didn't anticipate (e.g., similar patterns
elsewhere, related test files, existing conventions).

**Per-droid quality checklists:** Each droid type has specific dimensions it MUST verify
beyond its core domain. These are defined in Protocol: Per-Droid Quality Checklists below.
Skills that dispatch review droids MUST reference this protocol in their agent prompts.

**Cross-cutting analysis:** Every droid prompt MUST include the universal cross-cutting
section:
1. What would break in production under load with this code?
2. What's MISSING that should be here? (not just what's wrong)
3. Does this code trace back to a spec requirement? Flag orphan code without spec backing
4. How would a new developer understand this code 6 months from now?
5. Search the codebase for how similar problems were solved — flag inconsistencies

### Protocol: Per-Droid Quality Checklists

**Referenced by:** review, pr-check, deep-review, coderabbit-review, plan, build

Each droid type has specific dimensions it MUST verify beyond its core domain. Skills
that dispatch review droids MUST include the applicable checklists in agent prompts.

**Code Quality agent** (`ring-default-code-reviewer`) must additionally verify:
- Resilience: external calls have timeout, retry with backoff, circuit breaker where appropriate
- Resource lifecycle: all opened connections/handles are closed (defer, cleanup, graceful shutdown)
- Concurrency: shared state has proper synchronization, no goroutine leaks, no deadlock risk
- Performance: no N+1 queries, no unbounded queries, indexes exist for query patterns, no hot-path allocations
- Configuration: no hardcoded values that should be environment-configurable, safe defaults
- Cognitive complexity: functions with >3 nesting levels or >30 lines flagged for decomposition
- Error handling: errors wrapped with context, consistent with codebase error patterns
- Domain purity: no infrastructure concerns in domain layer, dependency direction correct
- Resource leaks: DB connections, HTTP clients, file handles, channels properly closed

**Business Logic agent** (`ring-default-business-logic-reviewer`) must additionally verify:
- Spec traceability: each code path maps to a spec requirement (flag orphan logic with no spec backing)
- Data integrity: transaction boundaries correct, partial writes impossible, rollback defined
- Backward compatibility: existing consumers/contracts not broken by this change
- API semantics: correct HTTP status codes, idempotent operations marked as such, pagination consistent
- Domain edge cases: what happens with zero, negative, maximum, duplicate, concurrent values?
- Business rule completeness: all business rules from spec have implementation AND test

**Security agent** (`ring-default-security-reviewer`) must additionally verify:
- Data privacy: PII not logged, sensitive fields masked in responses, LGPD/GDPR compliance
- Error responses: no internal details leaked (stack traces, DB schemas, internal paths, SQL)
- Rate limiting: high-throughput or public endpoints have rate limiting consideration
- Input validation: happens at the right layer (not just client-side), consistent with codebase
- Secrets: no hardcoded credentials, tokens, API keys in code or config files
- Auth propagation: authentication context properly propagated through the call chain

**Test Quality agent** (`ring-default-ring-test-reviewer`) must additionally verify:
- Test effectiveness: do tests verify BEHAVIOR or just mock internals? Flag tests where assertions only check mock.Called() without verifying output/state
- False positive risk: could these tests pass while the feature is actually broken?
- Test coupling: are tests coupled to implementation details (private fields, internal struct layout)?
- Spec traceability: for each acceptance criterion in the task spec, is there a test?
- Integration tests: do they use real dependencies (testcontainers/docker) or just mocks?
- Test isolation: can tests run in parallel without interference? Shared state between tests?
- Error scenario completeness: each error return path has a corresponding test?
- Boundary values: min, max, zero, empty, nil, negative tested where applicable?

**Nil/Null Safety agent** (`ring-default-ring-nil-safety-reviewer`) must additionally verify:
- Resource cleanup: nil checks before Close/Release calls
- Channel safety: sends to nil/closed channels
- Map safety: reads/writes to nil maps
- Slice safety: index bounds after filtering/transforming

**Ripple Effects agent** (`ring-default-ring-consequences-reviewer`) must additionally verify:
- Values duplicated between files that should be a shared constant
- Imports follow the project's layer architecture (no circular deps, no backwards imports)
- New code follows the same patterns as existing code in the same domain
- Backward compatibility: does this change break any existing consumer or API contract?
- Configuration drift: new defaults reasonable? existing config overrides still valid?
- Migration path: if breaking change, is migration strategy documented?
- Shared state: new global/package-level state that could cause issues across modules?
- Event/message contracts: changes to event payloads affect downstream consumers?

**Dead Code agent** (`ring-default-ring-dead-code-reviewer`) must additionally verify:
- Dead code: unused imports, unreachable branches, commented-out code
- Zombie test infrastructure: test helpers, fixtures, mocks no longer used by any test
- Feature flags: stale feature flag checks for flags that were already fully rolled out
- Deprecated paths: code paths behind deprecated API versions with no remaining consumers

**Spec Compliance / QA agent** (`ring-dev-team-qa-analyst`) must additionally verify:
- Testability assessment: is the code structured for testability? (dependency injection, interfaces)
- Operational readiness: can ops monitor, debug, and rollback this in production?
- Acceptance criteria coverage: each AC has both success AND failure test scenarios
- Cross-cutting scenarios: concurrent modifications, large datasets, special characters, timezone handling

**Frontend specialist** (`ring-dev-team-frontend-engineer`) must additionally verify:
- UX completeness: loading states, empty states, error states all handled
- Accessibility: keyboard navigation, screen reader support, ARIA labels, color contrast
- Responsive behavior: works across viewport sizes (mobile, tablet, desktop)
- i18n readiness: no hardcoded user-facing strings, date/number formatting locale-aware
- Performance: no unnecessary re-renders, large lists virtualized, images optimized

**Backend specialist** (`ring-dev-team-backend-engineer-golang` or TS equivalent) must additionally verify:
- Language idiomaticity: follows official style guide conventions
- Graceful shutdown: SIGTERM handling, in-flight request draining
- Connection pool sizing: appropriate for expected load
- Context propagation: request context passed through the full call chain
- Structured logging: logs include correlation IDs, operation names, durations

Skills reference this as: "Include per-droid quality checklists — see AGENTS.md Protocol: Per-Droid Quality Checklists."

## Known Issues and Decisions

- `codacy:ignore` does NOT exist — use the underlying linter's syntax (biome-ignore, eslint-disable, //nolint)
- DeepSource `// skipcq: <shortcode>` is the inline suppression syntax
- Native app review threads (deepsource-io, codacy-production) cannot be replied to via REST API — use GraphQL `addPullRequestReviewThreadReply`
- Biome has a known bug with JSX comments for `biome-ignore` (#8980, #9469, #7473) — exclude test files from Codacy instead

## Known Limitations

### Parallel Task Execution
Since status and branch data live in `.optimus/state.json` (gitignored), parallel task
execution via worktrees does NOT cause merge conflicts in optimus-tasks.md. The optimus-tasks.md file
is only modified by administrative operations (new tasks, dependency changes, version
moves), which are infrequent and happen on the default branch.

If optimus-tasks.md IS modified on a feature branch (e.g., Active Version Guard moves a task),
standard git merge conflict resolution applies — keep both changes.

### Concurrent state.json Writes
The state.json read-modify-write pattern is not atomic across processes. If two stage
agents run simultaneously (e.g., two terminals), the last write wins and the first
task's status update may be lost. This is an accepted limitation — Optimus processes
one task at a time. For parallel task work, use separate worktrees but run stage
commands sequentially.

### Standalone Skills vs Ring Droid Dispatch
The `deep-review` and `deep-doc-review` standalone skills apply fixes directly in their
interactive resolution phase, rather than dispatching specialist ring droids for fixes.
However, both skills **require ring droids for analysis dispatch**:

- `deep-review` dispatches ring review droids (code-reviewer, business-logic-reviewer,
  security-reviewer, test-reviewer, consequences-reviewer) for parallel code analysis.
- `deep-doc-review` dispatches ring documentation and review droids (docs-reviewer,
  business-logic-reviewer, code-reviewer) for parallel documentation analysis.

Ring droids are required for both skills — there is no fallback. If the required droids
are not installed, the skill will stop and list which droids need to be installed.

The ring droid **fix dispatch** pattern (TDD cycle via specialist droids, described in
"Common Patterns Across Skills") applies only to cycle review skills (stages 1, 3, 4,
and coderabbit-review). Standalone skills apply approved fixes directly.


