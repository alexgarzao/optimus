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
├── batch/                     # Admin: Pipeline orchestrator (stages 1-5)
├── resolve/          # Admin: Resolve tasks.md merge conflicts
├── plan/              # Execution Stage 1: Spec validation + workspace creation
├── build/              # Execution Stage 2: Task implementation
├── check/       # Execution Stage 3: Implementation review
├── pr-check/         # Execution Stage 4 (optional): PR review orchestrator
├── done/             # Execution Stage 5: Close task (verify & mark done)
├── deep-review/                       # Parallel code review (no PR context)
├── deep-doc-review/                   # Documentation review
├── coderabbit-review/                 # CodeRabbit CLI + TDD cycle
├── verify/                            # Automated verification (lint/test/build)
├── help/                              # Skill discovery and help
├── quick-report/                      # Compact daily status dashboard
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
priorities) in `.optimus/tasks.md` and operational state (status, branch) in
`.optimus/state.json` (gitignored). The `TaskSpec` column in tasks.md points to each
task's Ring spec.

### 1. User Authority Over Decisions
The agent NEVER decides whether a finding should be fixed or skipped. ALL findings
(CRITICAL, HIGH, MEDIUM, LOW) MUST be presented to the user for decision. The agent
recommends but the user decides.

### 2. No False Convergence
Convergence loops use the **fresh sub-agent model**: round 1 is analyzed by the
orchestrator, rounds 2+ are executed by a fresh sub-agent (via `Task` tool) with zero
prior context. Round 2 is mandatory. The orchestrator deduplicates, not the sub-agent.
LOW severity is NOT a stop condition.

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

## Plugin Lifecycle

### Adding a new plugin
1. Create directory: `<name>/skills/optimus-<name>/SKILL.md`
2. Create manifest: `<name>/.factory-plugin/plugin.json`
3. Add entry to `.factory-plugin/marketplace.json`
4. Update README.md table
5. Commit, push, then `droid plugin install <name>@optimus`

### Updating a plugin
1. Edit the SKILL.md
2. Commit, push
3. Run `droid plugin update <name>@optimus`

### Removing a plugin
1. Remove from marketplace.json
2. Remove directory
3. Update README.md
4. Commit, push
5. Run `droid plugin uninstall <name>@optimus`

## tasks.md Format

Every project using the cycle pipeline MUST have a `tasks.md` file. This is the single
source of truth for task tracking.

### File Location

All Optimus files live in the `.optimus/` directory at the project root:

```
.optimus/
├── config.json          # versionado — tasksDir, commands
├── tasks.md             # versionado — structural task data (NO status, NO branch)
├── state.json           # gitignored — operational state (status, branch per task)
├── stats.json           # gitignored — stage execution counters per task
├── sessions/            # gitignored — session state for crash recovery
└── reports/             # gitignored — exported reports
```

**Configuration** is stored in `.optimus/config.json`:

```json
{
  "tasksDir": "docs/pre-dev"
}
```

- **`tasksDir`**: Path to the Ring pre-dev artifacts root. Default: `docs/pre-dev`.
  The import and stage agents look for task specs at `<tasksDir>/tasks/` and subtasks
  at `<tasksDir>/subtasks/`.

**Tasks file** is always `.optimus/tasks.md` — not configurable.

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
- Stage agents read and write this file — never tasks.md — for status changes.
- If state.json is lost, status can be reconstructed: task with a worktree = in progress,
  without = Pendente. The agent asks the user to confirm before proceeding.

**Stage execution stats** are stored in `.optimus/stats.json` (gitignored):

```json
{
  "T-001": { "plan_runs": 2, "check_runs": 3, "last_plan": "2025-01-15T10:30:00Z", "last_check": "2025-01-16T14:00:00Z" },
  "T-002": { "plan_runs": 1, "check_runs": 0 }
}
```

- Each key is a task ID. Values track how many times `plan` and `check` executed on the task.
- A high `plan_runs` signals unclear or problematic specs. A high `check_runs` signals
  complex review cycles or specification gaps.
- The file is created on first use by `plan` or `check`. If missing, agents treat all
  counters as 0.
- `report` reads this file to display churn metrics.

Agents resolve paths:
1. **Read `.optimus/config.json`** for `tasksDir`. Fallback: `docs/pre-dev`.
2. **Tasks file:** `.optimus/tasks.md` (fixed path).
3. **If tasks.md not found:** **STOP** and suggest running `import` to create one.

The `.optimus/state.json`, `.optimus/stats.json`, `.optimus/sessions/`, and
`.optimus/reports/` are gitignored (operational/temporary state).
The `.optimus/config.json` and `.optimus/tasks.md` are versioned (structural data).

### Format Marker

The **first line** of `tasks.md` MUST be the format marker:

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

**NOTE:** Status and Branch are NOT stored in tasks.md. They live in `.optimus/state.json`
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

**Administrative commits (tasks.md structural changes):** Structural changes to tasks.md
(new task, dependency edit, version move) use `chore(tasks):` regardless of the task's
Tipo. Status changes are NOT committed — they live in state.json (gitignored).

**Reference:** Conventional Commits 1.0.0 — https://www.conventionalcommits.org/en/v1.0.0/

### Valid Status Values (stored in state.json)

Status lives in `.optimus/state.json`, NOT in tasks.md. A task with no entry in
state.json is implicitly `Pendente`.

| Status | Set by | Meaning |
|--------|--------|---------|
| `Pendente` | Initial (implicit) | Not started — no entry in state.json |
| `Validando Spec` | plan | Spec being validated |
| `Em Andamento` | build | Implementation in progress |
| `Validando Impl` | check | Implementation being reviewed |
| `Revisando PR` | pr-check | PR being reviewed (optional stage) |
| `DONE` | done | Completed |
| `Cancelado` | tasks | Task abandoned, will not be implemented |

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
(plan, build, check) resolve the full path as `<tasksDir>/<TaskSpec>` and read the
referenced file for objective, acceptance criteria, and implementation details.

The subtasks directory is derived automatically from the TaskSpec path:
- TaskSpec: `tasks/task_001.md` → Subtasks: `<tasksDir>/subtasks/T-001/`
- The `T-NNN` identifier is extracted from the task spec filename convention

Agents read objective and acceptance criteria directly from the Ring source files.
The tasks.md table only tracks structural data (dependencies, versions, priorities)
— it does NOT duplicate content from Ring.

### Version Management

The `## Versions` section in tasks.md is **mandatory** and defines the available versions
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

Every stage agent (1-5) MUST validate the tasks.md format before operating:
1. **First line** is `<!-- optimus:tasks-v1 -->` (format marker)
2. A `## Versions` section exists with a table containing columns: Version, Status, Description
3. All Version Status values are valid (`Ativa`, `Próxima`, `Planejada`, `Backlog`, `Concluída`)
4. Exactly one version has Status `Ativa`
5. At most one version has Status `Próxima`
6. A markdown table exists with columns: ID, Title, Tipo, Depends, Priority, Version (Estimate and TaskSpec are optional — tables without them are still valid). **Status and Branch columns are NOT expected** — they live in state.json.
7. All task IDs follow the `T-NNN` pattern
8. All Tipo values are one of: `Feature`, `Fix`, `Refactor`, `Chore`, `Docs`, `Test`
9. All Depends values are either `-` or comma-separated valid task IDs
10. All Priority values are one of: `Alta`, `Media`, `Baixa`
11. All Version values reference a version name that exists in the Versions table
12. No duplicate task IDs
13. No circular dependencies in the dependency graph (e.g., T-001 → T-002 → T-001)

If the format marker is missing or validation fails, the agent must **STOP** and suggest
running `/optimus-import` to fix the format. Do NOT attempt to interpret malformed data.

14. No unescaped pipe characters (`|`) in task titles (breaks markdown table parsing)
15. **Empty table handling:** If the tasks table exists but has zero data rows (only headers),
format validation PASSES. Stage agents (1-5) should inform the user: "No tasks found in
tasks.md. Use `/optimus-tasks` to create a task or `/optimus-import` to import from Ring pre-dev."

**NOTE:** For circular dependency detection (item 14), trace the full dependency chain for
each task. If any task appears twice in the chain, a cycle exists. Report ALL tasks involved
in the cycle so the user can fix it with `/optimus-tasks`.

### Parallelization

Tasks with no dependencies or all dependencies satisfied can run in parallel.
The report agent computes and displays parallelization opportunities.

---

## Task Lifecycle

Tasks flow through 5 stages (pr-check is optional). Status lives in `.optimus/state.json`
(gitignored). Each stage is a separate skill. The tasks.md file contains only structural
data — no stage agent commits to tasks.md for status changes.

```
Pendente → Validando Spec → Em Andamento → Validando Impl → [Revisando PR] → DONE
           (plan)   (build)  (check)  (pr-check)  (done)
                                                               [optional]

Any status → Cancelado  (via tasks cancel operation)
```

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
5. **Re-execution allowed** — every agent (stages 1-4) accepts being re-run when
   the task is already in its own output status. For example, build accepts
   `Em Andamento` (its own status) as well as `Validando Spec` (its predecessor).
   This allows the user to re-run a stage without resetting status.
   **Exception:** done does NOT support re-execution — once a task is
   `DONE`, it cannot be re-closed.
6. **Dependency check** — every agent verifies that ALL dependencies (Depends column
   from tasks.md) have status `DONE` (read from state.json) before proceeding. If
   any dependency is not done, the agent fires the `task-blocked` hook (if configured)
   and then refuses with a clear message identifying which dependency is blocking.
   **If the blocking dependency has status `Cancelado`**, the message must differentiate:
   "T-YYY was cancelled (Cancelado). Consider removing this dependency via `/optimus-tasks`."
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

8. **Branch protection** — execution skills (stages 1-5) require a feature branch.
   Administrative skills can run on any branch. See the classification table below:

   **Skills are classified as Administrative or Execution:**

   | Type | Agent | Allowed on main/default? | Reason |
   |------|-------|-------------------------|--------|
   | Admin | import | Yes | Only creates/modifies tasks.md |
   | Admin | report | Yes | Read-only, no modifications |
   | Admin | quick-report | Yes | Read-only, no modifications |
   | Admin | tasks | Yes | Only creates/edits/removes tasks in tasks.md and state.json |
   | Execution | plan | Yes (creates worktree) | Writes state.json and creates worktree |
   | Execution | build | Yes (auto-navigates) | Finds task worktree and navigates to it |
   | Execution | check | Yes (auto-navigates) | Finds task worktree and navigates to it |
   | Execution | pr-check | Yes (auto-navigates) | Finds task worktree and navigates to it |
   | Execution | done | Yes (auto-navigates) | Finds task worktree and navigates to it |
   | Admin | batch | Yes | Orchestrates stages, delegates to stage skills |
   | Admin | resolve | Yes | Only resolves merge conflicts in tasks.md |

   **Administrative skills** manage tasks.md metadata and state.json. They never modify
   project code and can run on any branch.

   **Execution skills** modify code or run verification. They require a feature branch
   (workspace). Stage-1 writes state.json (status + branch) and creates the worktree.
   Stages 2-5 auto-navigate to the task's worktree when invoked on the default branch
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

9. **Branch-task cross-validation** — stages 2-5 derive the expected branch name from
   the task's Tipo + ID + Title (see Protocol: Branch Name Derivation) and verify it
   matches the current branch. If the branch does not match, the agent warns the user
   and asks whether to continue or switch.

### Transition Table

| Agent | Expects status | Changes to | Re-execution? |
|-------|---------------|------------|---------------|
| plan | `Pendente` or `Validando Spec` | `Validando Spec` | Yes (accepts own status) |
| build | `Validando Spec` or `Em Andamento` | `Em Andamento` | Yes (accepts own status) |
| check | `Em Andamento` or `Validando Impl` | `Validando Impl` | Yes (accepts own status) |
| pr-check | `Validando Impl` or `Revisando PR` | `Revisando PR` | Yes (accepts own status) |
| done | `Validando Impl` or `Revisando PR` | `DONE` | No (final stage) |

**NOTE:** `Cancelado` is a terminal status. No stage agent accepts it — all stages refuse
tasks with status `Cancelado`. Cancellation is managed exclusively by `tasks`.

**NOTE:** pr-check is optional. done accepts both `Validando Impl`
(if pr-check was skipped) and `Revisando PR` (if pr-check ran).

**NOTE:** pr-check also works in standalone mode (without a task). In standalone
mode, it skips all task status logic. See its SKILL.md for detection rules.

**NOTE:** O merge do PR pode ser feito pelo done durante a fase de cleanup
(o agente pergunta ao usuário via AskUser com opções: merge commit, squash, rebase, keep open,
close without merging), ou manualmente pelo usuário depois.

### done Checklist

Before marking done, done runs 8 checks:
1. No uncommitted changes (`git status --porcelain` = empty)
2. No unpushed commits (`git log @{u}..HEAD` = empty)
3. PR ready to merge (if PR exists) — includes PR title validation (Conventional Commits)
4. CI passing (if PR exists)
5. `make lint` passes (or command from `.optimus/config.json`)
6. `make test` passes (or command from `.optimus/config.json`)
7. `make test-integration` passes (if target exists, or from config.json)
8. `make test-e2e` passes (if target exists, or from config.json)

ALL must pass (SKIP counts as pass). If any fails, status in state.json stays unchanged.

## Dry-Run Mode (all stages)

All stage agents (1-5) support **dry-run mode**. When the user includes "dry-run" or
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

### Protocol: tasks.md Validation (HARD BLOCK)

**Referenced by:** all stage agents (1-5), tasks, batch, resolve

Every stage agent MUST validate tasks.md before operating. The full validation rules are
defined in the "Format Validation" section above (items 1-15). This protocol is the
executable version:

1. **Resolve paths:**
   - `TASKS_FILE` is always `.optimus/tasks.md` (fixed path).
   - Read `.optimus/config.json`. If `tasksDir` key exists, use that path. Otherwise, use `docs/pre-dev` (default).
   - Store as `TASKS_FILE` and `TASKS_DIR`.
2. **Find tasks.md:** Check if `TASKS_FILE` exists. If not found, **STOP** and suggest `/optimus-import`.
3. **Validate format:** Execute all 15 validation checks from the "Format Validation" section. If the format marker is missing or any check fails, **STOP** and suggest `/optimus-import`.

**All subsequent references to `tasks.md` in the skill use the resolved `TASKS_FILE` path.
All references to Ring pre-dev artifacts use `TASKS_DIR` as the root** — never hardcoded paths.

Skills reference this as: "Find and validate tasks.md (HARD BLOCK) — see AGENTS.md Protocol: tasks.md Validation."

### Protocol: GitHub CLI Check (HARD BLOCK)

**Referenced by:** all stage agents (1-5), tasks, batch

```bash
gh auth status 2>/dev/null
```

If this command fails (exit code != 0), **STOP** immediately:
```
GitHub CLI (gh) is not authenticated. Run `gh auth login` to authenticate before proceeding.
```

### Protocol: Initialize .optimus Directory

**Referenced by:** import, tasks, report (export), all stage agents (1-5) for session files

Before creating ANY file inside `.optimus/`, ensure the directory structure exists
and operational/temporary files are gitignored:

```bash
mkdir -p .optimus/sessions .optimus/reports
if ! grep -q '^# optimus-operational-files' .gitignore 2>/dev/null; then
  printf '\n# optimus-operational-files\n.optimus/state.json\n.optimus/stats.json\n.optimus/sessions/\n.optimus/reports/\n' >> .gitignore
fi
```

The `.optimus/config.json` and `.optimus/tasks.md` are versioned (structural data).
The `.optimus/state.json`, `.optimus/stats.json`, `sessions/`, and `reports/` are
gitignored (operational/temporary state).

Skills reference this as: "Initialize .optimus directory — see AGENTS.md Protocol: Initialize .optimus Directory."

### Protocol: Increment Stage Stats

**Referenced by:** plan, check

After the status change in state.json (and BEFORE any analysis work begins), increment
the execution counter for the current stage in `.optimus/stats.json`. This tracks how many
times each stage ran on each task — useful for spotting spec churn and review cycles.

**NOTE:** Only increment when NOT in dry-run mode.

1. Read `.optimus/stats.json`. If the file does not exist, start with an empty object `{}`.
2. If the task ID key does not exist, initialize it:
   ```json
   { "plan_runs": 0, "check_runs": 0 }
   ```
3. Increment the appropriate counter (`plan_runs` for plan, `check_runs` for check).
4. Set the timestamp field (`last_plan` or `last_check`) to the current UTC ISO 8601 time.
5. Write the updated JSON back to `.optimus/stats.json` (pretty-printed, sorted keys).

**NOTE:** stats.json is gitignored — no commit needed.

Skills reference this as: "Increment stage stats — see AGENTS.md Protocol: Increment Stage Stats."

### Protocol: Shell Safety Guidelines

**Referenced by:** plan, build, check, pr-check, done, tasks, import, resolve, batch

All bash examples in AGENTS.md and SKILL.md files are templates that agents execute literally.
Follow these rules to prevent injection and silent failures:

1. **Always quote variables:** Use `"$VAR"` not `$VAR` — especially for paths, branch names, and user-derived values
2. **Check exit codes for critical commands:**
   ```bash
   git add "$TASKS_FILE"
   if ! git commit -m "chore(tasks): $COMMIT_MSG"; then
     echo "ERROR: git commit failed. Check pre-commit hooks or git config."
     # STOP — do not proceed
   fi
   ```
3. **Never interpolate user-derived values directly into shell commands** — task titles,
   branch names, and other user input may contain shell metacharacters
4. **Use `grep -F` for fixed string matching** — never pass branch names or task IDs
   as regex patterns to `grep` without `-F`
5. **Use `grep -E '^\| T-NNN \|'`** to match task rows in tasks.md — plain `grep "T-NNN"`
   matches titles and dependency columns too
6. **Validate tool availability** before use: `command -v jq &>/dev/null` before running `jq`
7. **Validate JSON files** before parsing: `jq empty "$FILE" 2>/dev/null` before reading keys
8. **Sanitize user-derived values in commit messages** — task titles and descriptions may
   contain shell metacharacters (backticks, `$(...)`, double quotes). When constructing
   commit messages, prefer using git's `-m` flag with the message in double quotes and
   ensure the interpolated values don't contain unescaped special characters. If in doubt,
   use `printf '%s' "$VALUE"` to safely handle the content.

Skills reference this as: "Follow shell safety guidelines — see AGENTS.md Protocol: Shell Safety Guidelines."

### Protocol: Session State

**Referenced by:** all stage agents (1-5)

Stage agents write a session state file to track progress. This enables resumption
when a session is interrupted (agent crash, user closes terminal, context window limit).

**IMPORTANT — Write timing:** The session file MUST be written **immediately after the
status change in state.json** (before any work begins). This ensures crash recovery has
a record even if the agent fails before producing any output. Do NOT wait until
"key phase transitions" to write the initial session file.

**Session file location:** `.optimus/sessions/session-<task-id>.json` (gitignored).
Each task gets its own file (e.g., `.optimus/sessions/session-T-003.json`).

```json
{
  "task_id": "T-003",
  "stage": "<stage-name>",
  "status": "<stage-output-status>",
  "branch": "feat/t-003-user-auth",
  "started_at": "2025-01-15T10:30:00Z",
  "updated_at": "2025-01-15T11:45:00Z",
  "phase": "Phase 1: Implementation",
  "notes": "Implementation in progress"
}
```

**On stage start (after task ID is known):**

```bash
SESSION_FILE=".optimus/sessions/session-${TASK_ID}.json"
if [ -f "$SESSION_FILE" ]; then
  cat "$SESSION_FILE"
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
- If the file is stale (>24h) or the task status has changed → delete and proceed normally
- **External status change detection:** If the session file exists AND the task's status
  does NOT match the session's `status`, check if the difference is explainable by normal
  stage progression (e.g., session says `Em Andamento` but task is now `Validando Impl` —
  the task was advanced externally via `/optimus-tasks`). If the status change is NOT
  explainable by forward progression, treat the session as stale and delete it.
- If no file exists → proceed normally

**On stage progress (at key phase transitions):**

```bash
# Initialize .optimus directory — see AGENTS.md Protocol: Initialize .optimus Directory.
mkdir -p .optimus/sessions .optimus/reports
BRANCH_NAME=$(git branch --show-current 2>/dev/null || echo "detached")
jq -n \
  --arg task_id "${TASK_ID}" --arg stage "<stage-name>" --arg status "<status>" \
  --arg branch "${BRANCH_NAME}" --arg started "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --arg updated "$(date -u +%Y-%m-%dT%H:%M:%SZ)" --arg phase "<current-phase>" \
  --arg notes "<progress>" \
  '{task_id: $task_id, stage: $stage, status: $status, branch: $branch,
    started_at: $started, updated_at: $updated, phase: $phase, notes: $notes}' \
  > ".optimus/sessions/session-${TASK_ID}.json"
```

**On stage completion:** Delete the session file:
```bash
rm -f ".optimus/sessions/session-${TASK_ID}.json"
```

Skills reference this as: "Execute session state protocol from AGENTS.md using stage=`<name>`, status=`<status>`."

### Protocol: Workspace Auto-Navigation (HARD BLOCK)

**Referenced by:** stages 2-5

Execution stages (2-5) resolve the correct workspace automatically. The agent MUST
be in the task's worktree before proceeding with any work.

```bash
DEFAULT_BRANCH=$(git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's@^refs/remotes/origin/@@')
if [ -z "$DEFAULT_BRANCH" ]; then
  DEFAULT_BRANCH=$(git branch --list main master 2>/dev/null | head -1 | tr -d ' *')
fi
CURRENT_BRANCH=$(git branch --show-current)
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
     If the branch exists, create the worktree automatically:
     ```bash
     REPO_NAME=$(basename "$(git rev-parse --show-toplevel)")
     WORKTREE_DIR="../${REPO_NAME}-$(echo <task-id> | tr '[:upper:]' '[:lower:]')-<keywords>"
     git worktree add "$WORKTREE_DIR" "<branch-name>"
     ```
     Then change working directory to the new worktree.

Skills reference this as: "Resolve workspace (HARD BLOCK) — see AGENTS.md Protocol: Workspace Auto-Navigation."

### Protocol: Divergence Warning

**Referenced by:** all stage agents (1-5)

Since status and branch data live in state.json (gitignored), tasks.md rarely changes
on feature branches. This protocol detects the uncommon case where tasks.md WAS modified
(e.g., Active Version Guard moved a task).

```bash
DEFAULT_BRANCH=$(git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's@^refs/remotes/origin/@@')
if [ -z "$DEFAULT_BRANCH" ]; then
  DEFAULT_BRANCH=$(git branch --list main master 2>/dev/null | head -1 | tr -d ' *')
fi
TASKS_FILE=".optimus/tasks.md"
git fetch origin "$DEFAULT_BRANCH" --quiet 2>/dev/null
git diff "origin/$DEFAULT_BRANCH" -- "$TASKS_FILE" 2>/dev/null | head -20
```

- If diff output is non-empty → warn via `AskUser`:
  ```
  tasks.md has diverged between your branch and <default_branch>.
  This may cause merge conflicts when the PR is merged.
  ```
  Options:
  - **Sync now** — run `git merge origin/<default_branch>` to incorporate changes
  - **Continue without syncing** — I'll handle conflicts later
- If diff output is empty → proceed silently (files are in sync)
- **NOTE:** This is a warning, not a HARD BLOCK. The user may choose to continue.

Skills reference this as: "Check tasks.md divergence — see AGENTS.md Protocol: Divergence Warning."

### Protocol: Notification Hooks

**Referenced by:** all stage agents (1-5), tasks

After writing a status change to state.json, invoke notification hooks if present.

**IMPORTANT — Capture timing:** Read the current status from state.json and store it as
`OLD_STATUS` BEFORE writing the new status. The sequence is:
1. Read current status: `OLD_STATUS=$(jq -r --arg id "$TASK_ID" '.[$id].status // "Pendente"' "$STATE_FILE")`
2. Write new status to state.json
3. Invoke hooks with `OLD_STATUS` and new status

**IMPORTANT:** Always quote all arguments to prevent shell injection from user-derived values.

```bash
HOOKS_FILE=$(test -f ./tasks-hooks.sh && echo ./tasks-hooks.sh || (test -f ./docs/tasks-hooks.sh && echo ./docs/tasks-hooks.sh))
if [ -n "$HOOKS_FILE" ] && [ -x "$HOOKS_FILE" ]; then
  "$HOOKS_FILE" "$event" "$task_id" "$old_status" "$new_status" 2>/dev/null &
fi
```

Events and their parameter signatures:

| Event | Parameters | Description |
|-------|-----------|-------------|
| `status-change` | `event task_id old_status new_status` | Any status transition |
| `task-done` | `event task_id old_status "DONE"` | Task marked as done |
| `task-cancelled` | `event task_id old_status "Cancelado"` | Task cancelled |
| `task-blocked` | `event task_id current_status current_status reason` | Dependency check failed (5 args — includes reason) |

When a dependency check fails:
```bash
if [ -n "$HOOKS_FILE" ] && [ -x "$HOOKS_FILE" ]; then
  "$HOOKS_FILE" "task-blocked" "$task_id" "$current_status" "$current_status" "blocked by $dep_id ($dep_status)" 2>/dev/null &
fi
```

Hooks run in background (`&`) and their failure does NOT block the pipeline.
If `tasks-hooks.sh` does not exist, hooks are silently skipped.

Skills reference this as: "Invoke notification hooks — see AGENTS.md Protocol: Notification Hooks."

### Protocol: Ring Droid Requirement Check

**Referenced by:** check, pr-check, deep-review, deep-doc-review, coderabbit-review, plan (build delegates droid dispatch to dev-cycle)

Before dispatching ring droids, verify the required droids are available. If any required
droid is not installed, **STOP** and list missing droids.

**Core review droids** (required by check, pr-check, deep-review, coderabbit-review):
- `ring-default-code-reviewer`
- `ring-default-business-logic-reviewer`
- `ring-default-security-reviewer`
- `ring-default-ring-test-reviewer`

**Extended review droids** (required by check, pr-check, deep-review, coderabbit-review):
- `ring-default-ring-nil-safety-reviewer`
- `ring-default-ring-consequences-reviewer`
- `ring-default-ring-dead-code-reviewer`

**QA droids** (required by check, deep-review):
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

**Referenced by:** check, pr-check, coderabbit-review, verify

Measure test coverage using the project's configured commands. Check `.optimus/config.json`
for custom commands first, then fall back to Makefile targets, then stack-specific commands.

**Command resolution order:**
1. `.optimus/config.json` → `commands.test-coverage` (if present)
2. `make test-coverage` (if Makefile target exists)
3. Stack-specific fallback:
   - Go: `go test -coverprofile=coverage-unit.out ./... && go tool cover -func=coverage-unit.out`
   - Node: `npm test -- --coverage`
   - Python: `pytest --cov=. --cov-report=term`

If no coverage command is available, mark as **SKIP** — do not fail the verification.

**Thresholds:**

| Test Type | Threshold | Verdict if Below |
|-----------|-----------|-----------------|
| Unit tests | 85% | NEEDS_FIX / HIGH finding |
| Integration tests | 70% | NEEDS_FIX / HIGH finding |

**Coverage gap analysis:** Parse the coverage output to identify untested functions/methods
(0% coverage). Flag business-logic functions with 0% as HIGH, infrastructure/generated
code with 0% as SKIP.

Skills reference this as: "Measure coverage — see AGENTS.md Protocol: Coverage Measurement."

### Protocol: PR Title Validation

**Referenced by:** stages 2-5

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

**Referenced by:** plan, build, check

Resolve the full path to a task's Ring pre-dev spec and its subtasks directory:

1. Read the task's `TaskSpec` column from `tasks.md`
2. If `TaskSpec` is `-` → **STOP**: "Task T-XXX has no Ring pre-dev spec. Link one via `/optimus-tasks` or `/optimus-import`."
3. Resolve full path: `TASK_SPEC_PATH = <TASKS_DIR>/<TaskSpec>`
4. Read the task spec file at `TASK_SPEC_PATH`
5. Derive subtasks directory: if TaskSpec is `tasks/task_001.md`, subtasks are at `<TASKS_DIR>/subtasks/T-001/`
6. If subtasks directory exists, read all `.md` files inside it

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

### Protocol: Push Commits (optional)

**Referenced by:** all stage agents (1-5)

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

**After a successful push**, check if the current repo is the Optimus plugin repository
and update installed plugins to pick up the changes just pushed:

```bash
if jq -e '.name == "optimus"' .factory-plugin/marketplace.json &>/dev/null; then
  echo "Optimus repo detected — updating installed plugins..."
  for skill in $(droid plugin list 2>&1 | grep optimus | awk '{print $1}'); do
    droid plugin update "$skill" 2>/dev/null
  done
fi
```

This ensures that agents running in the Optimus repo itself always use the latest
skill versions after pushing changes.

Skills reference this as: "Offer to push commits — see AGENTS.md Protocol: Push Commits."

### Protocol: State Management

**Referenced by:** all stage agents (1-5), tasks, report, quick-report

All status and branch data is stored in `.optimus/state.json` (gitignored).

**Prerequisites:**

```bash
if ! command -v jq &>/dev/null; then
  echo "ERROR: jq is required for state management but not installed."
  # STOP — do not proceed
fi
```

**Reading state:**

```bash
STATE_FILE=".optimus/state.json"
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
# Initialize .optimus directory — see AGENTS.md Protocol: Initialize .optimus Directory.
STATE_FILE=".optimus/state.json"
if [ ! -f "$STATE_FILE" ]; then
  echo '{}' > "$STATE_FILE"
fi
UPDATED_AT=$(date -u +%Y-%m-%dT%H:%M:%SZ)
jq --arg id "$TASK_ID" --arg status "$NEW_STATUS" --arg branch "$BRANCH_NAME" --arg ts "$UPDATED_AT" \
  '.[$id] = {status: $status, branch: $branch, updated_at: $ts}' "$STATE_FILE" > "${STATE_FILE}.tmp" \
  && mv "${STATE_FILE}.tmp" "$STATE_FILE"
```

**Removing entry (for Pendente reset):**

```bash
STATE_FILE=".optimus/state.json"
if [ ! -f "$STATE_FILE" ]; then
  echo "state.json does not exist — task is already implicitly Pendente."
else
  jq --arg id "$TASK_ID" 'del(.[$id])' "$STATE_FILE" > "${STATE_FILE}.tmp" \
    && mv "${STATE_FILE}.tmp" "$STATE_FILE"
fi
```

**Listing all tasks with status (for report/quick-report):**

```bash
STATE_FILE=".optimus/state.json"
TASKS_FILE=".optimus/tasks.md"
# Validate state.json if it exists
if [ -f "$STATE_FILE" ] && ! jq empty "$STATE_FILE" 2>/dev/null; then
  echo "WARNING: state.json is corrupted. Treating all tasks as Pendente."
  rm -f "$STATE_FILE"
fi
# Get all task IDs from tasks.md
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

**Referenced by:** plan, build, check, pr-check, done (workspace auto-navigation)

Branch names are derived deterministically from the task's structural data in tasks.md.
They are NOT stored in tasks.md — they are stored in state.json for quick reference
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

### Protocol: Active Version Guard

**Referenced by:** all stage agents (1-5)

After the task ID is confirmed and dependencies are validated, check if the task belongs
to the `Ativa` version. If not, present options before proceeding.

1. Read the task's **Version** column from `tasks.md`
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
   - Update the task's Version column in `tasks.md` to the `Ativa` version name
   - Commit:
     ```bash
     git add "$TASKS_FILE"
     git commit -m "chore(tasks): move T-XXX to active version <active_version>"
     ```
   - Proceed with the stage

6. **If "Cancel":** **STOP** — do not proceed with the stage

Skills reference this as: "Check active version guard — see AGENTS.md Protocol: Active Version Guard."

## Verification Command Configuration

Projects can customize verification commands via `.optimus/config.json` instead of relying
on auto-detection from Makefile or stack conventions.

### Config File

Location: `.optimus/config.json` (versioned)

```json
{
  "tasksDir": "docs/pre-dev",
  "commands": {
    "lint": "npm run lint",
    "test": "npm test",
    "test-integration": "npm run test:integration",
    "test-e2e": "npx playwright test",
    "test-coverage": "npm test -- --coverage"
  }
}
```

### Behavior

All skills that run verification commands (verify, done, build,
check, pr-check, coderabbit-review) MUST check for `.optimus/config.json` BEFORE auto-detecting
commands. If the config file exists, use its commands instead of auto-detection.

If a command key is missing from the config, fall back to auto-detection for that command.
If a command key is present but empty (`""`), skip that check entirely.

## Common Patterns Across Skills

The patterns below apply to **cycle review skills** (plan, check,
pr-check, coderabbit-review). `deep-doc-review` uses a simplified model — it
follows the same user-authority and finding presentation principles but applies fixes inline
without convergence loops or batch-apply. `deep-review` requires ring droids for analysis,
has its own convergence loop (Phase 7), and uses batch-apply (Phase 6) — but applies fixes
directly rather than via ring droid TDD cycle.

### Finding Presentation (Unified Model)
All cycle review skills follow this pattern:
1. Collect findings from agents/tools
2. Consolidate and deduplicate
3. **Group same-nature findings** — after deduplication, identify findings that share the
   same root cause or fix pattern (e.g., "missing error handling" in 5 handlers, "inconsistent
   import path" in 4 files). If 2+ findings are of the same nature, merge them into a **single
   grouped entry** listing all affected files/locations. Each group counts as ONE item in the
   "Finding X of N" sequence. The user makes ONE decision for the entire group.
4. Announce total findings count: `"### Total findings to review: N"` (where N reflects
   grouped entries — a group of 5 same-nature findings counts as 1)
5. Present overview table with severity counts
6. **Deep research BEFORE presenting each finding** (see research checklist below)
7. Walk through findings ONE AT A TIME with `"Finding X of N"` header, ordered by severity
   (CRITICAL first, then HIGH, MEDIUM, LOW). **ALL findings MUST be presented regardless of
   severity** — the agent NEVER skips, filters, or auto-resolves any finding. The decision to
   fix or skip is ALWAYS the user's. For grouped entries, list all affected files/locations
   within the single presentation.
8. For each finding: present research-backed analysis + options, collect decision via AskUser.
   **Every AskUser for a finding decision MUST include a "Tell me more" option.** This option
   is always the **second-to-last** option (right before the free-text input that AskUser
   provides automatically). This lets the user request deeper analysis with one click.
9. **IMMEDIATE RESPONSE RULE — If the user selects "Tell me more" OR responds with free text
   (a question, disagreement, or request for clarification) instead of a decision:**
   **STOP IMMEDIATELY.** Do NOT continue to the next finding. Do NOT batch the response.
   Research the user's concern RIGHT NOW using `WebSearch`, codebase analysis, or both.
   Provide a thorough answer with evidence (links, code references, best practice citations).
   Only AFTER the user is satisfied, re-present the options and ask for their decision again.
   This may go back and forth multiple times — that is expected and correct behavior.
   **NEVER defer the response to the end of the findings loop.**
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
| **E2E tests** (`make test-e2e`) | ONCE before push (or when user invokes directly) | stages 3, 4 |

**Rationale:**
- Unit tests are fast and catch regressions immediately — run often
- Lint is fast but only matters after all code is finalized — run once at end
- Integration/E2E tests are slow (seconds to minutes) — run once before push to avoid
  blocking the review loop. If targets don't exist, skip.

### Coverage Thresholds

| Test Type | Threshold | Verdict if Below |
|-----------|-----------|-----------------|
| Unit tests | 85% | NEEDS_FIX / HIGH finding |
| Integration tests | 70% | NEEDS_FIX / HIGH finding |

All skills that measure coverage MUST use these thresholds. If coverage profiles cannot
be generated (command fails or tool missing), report as SKIP — do not fail the verification.

### Deep Research Before Presenting (MANDATORY for cycle review skills)
Applies to: plan, check, pr-check, coderabbit-review

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

### Convergence Loop (Fresh Sub-Agent Model)
Applies to: plan, check, pr-check, coderabbit-review

The convergence loop eliminates false convergence caused by session bias:
- **Round 1:** Orchestrator performs initial analysis (with full session context)
- **Rounds 2-5:** A **fresh sub-agent** (via `Task` tool) re-analyzes from scratch with zero prior context
- **Round 2 is MANDATORY** — the "zero new findings" stop condition only applies from round 3 onward
- The sub-agent receives the findings ledger for **deduplication only**, not to bias its analysis
- The orchestrator deduplicates sub-agent findings against the cumulative ledger
- Stop only when: zero new findings (round 3+), round 5 reached, or user explicitly stops
- LOW severity findings are NOT a reason to stop — ALL findings are presented to the user

### Agent Dispatch
Skills dispatch specialist ring droids in parallel via Task tool:
- ring-default-* droids (code-reviewer, business-logic-reviewer, security-reviewer, etc.)
- ring-dev-team-* droids (backend-engineer-golang, frontend-engineer, qa-analyst, etc.)
- ring-tw-team-* droids (functional-writer, api-writer, docs-reviewer)

**Ring droids are REQUIRED** — there is no fallback. If the required droids are not
installed, the skill MUST stop and list which droids need to be installed.

## Known Issues and Decisions

- `codacy:ignore` does NOT exist — use the underlying linter's syntax (biome-ignore, eslint-disable, //nolint)
- DeepSource `// skipcq: <shortcode>` is the inline suppression syntax
- Native app review threads (deepsource-io, codacy-production) cannot be replied to via REST API — use GraphQL `addPullRequestReviewThreadReply`
- Biome has a known bug with JSX comments for `biome-ignore` (#8980, #9469, #7473) — exclude test files from Codacy instead

## Known Limitations

### Parallel Task Execution
Since status and branch data live in `.optimus/state.json` (gitignored), parallel task
execution via worktrees does NOT cause merge conflicts in tasks.md. The tasks.md file
is only modified by administrative operations (new tasks, dependency changes, version
moves), which are infrequent and happen on the default branch.

If tasks.md IS modified on a feature branch (e.g., Active Version Guard moves a task),
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


