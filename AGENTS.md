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
├── TEMPLATE.md                        # Template for catalog entries
├── catalog/                           # Skill reference cards (read-only docs)
│   ├── analysis/                      # Review/analysis skill cards
│   ├── coding/                        # Coding skill cards
│   ├── system/                        # Orchestration skill cards
│   └── writing/                       # Writing skill cards
├── cycle-migrate/                   # Admin: Task format migrator (one-time)
├── cycle-report/                    # Admin: Task status dashboard (read-only)
├── cycle-crud/                      # Admin: Create, edit, remove, reorder tasks
├── cycle-batch/                     # Execution: Pipeline orchestrator (stages 1-5)
├── cycle-conflict-resolve/          # Admin: Resolve tasks.md merge conflicts
├── cycle-spec-stage-1/              # Execution Stage 1: Spec validation + workspace creation
├── cycle-impl-stage-2/              # Execution Stage 2: Task implementation
├── cycle-impl-review-stage-3/       # Execution Stage 3: Implementation review
├── cycle-pr-review-stage-4/         # Execution Stage 4 (optional): PR review orchestrator
├── cycle-close-stage-5/             # Execution Stage 5: Close task (verify & mark done)
├── deep-review/                       # Parallel code review (no PR context)
├── deep-doc-review/                   # Documentation review
├── coderabbit-review/                 # CodeRabbit CLI + TDD cycle
├── verify/                            # Automated verification (lint/test/build)
└── help/                              # Skill discovery and help
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
- Keep phase numbering sequential (Phase 0, Phase 1, ...)
- Step numbering within phases: Step X.Y (e.g., Step 0.3, Step 8.2)
- Use `**HARD BLOCK:**` for steps the agent must never skip
- Use `**CRITICAL:**` for rules that override normal behavior
- Use `**IMPORTANT:**` for emphasis without hard blocking
- When adding anti-rationalization rules, list specific excuses the agent might use
- Include concrete command examples (bash blocks) — agents follow examples better than prose
- Always include example output showing what success/failure looks like

### marketplace.json
- Must list ALL plugins in the repo
- `source` paths are relative to repo root (e.g., `./pr-review`)
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

All agents look for `tasks.md` in a single fixed location:

```
.optimus/tasks.md
```

There are no fallback locations. If `.optimus/tasks.md` does not exist, the agent must
inform the user and suggest running `cycle-migrate` to create one.

The `.optimus/` directory is also used for `config.json` and session state files.
The `.gitignore` should be configured to commit `tasks.md` and `config.json` but
ignore session files:
```
.optimus/*
!.optimus/tasks.md
!.optimus/config.json
```

### Format Marker

The **first line** of `tasks.md` MUST be the format marker:

```
<!-- optimus:tasks-v1 -->
```

This marker tells agents that the file is in valid optimus format. Agents check this
line FIRST — if it's missing, the file is treated as non-optimus format and the agent
suggests running `/optimus-cycle-migrate`.

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

| ID | Title | Tipo | Status | Depends | Priority | Version | Branch | Estimate |
|----|-------|------|--------|---------|----------|---------|--------|----------|
| T-001 | Setup auth module | Feature | **DONE** | - | Alta | MVP | - | S |
| T-002 | User registration API | Feature | Em Andamento | T-001 | Alta | MVP | feat/t-002-user-registration | M |
| T-003 | Login page | Feature | Pendente | T-001 | Alta | MVP | - | M |
| T-004 | Password reset flow | Fix | Pendente | T-002, T-003 | Media | v2 | fix/t-004-password-reset | L |
| T-005 | E2E auth tests | Test | Pendente | T-002, T-003 | Media | MVP | - | S |

## T-001: Setup auth module

**Objetivo:** Configurar o módulo de autenticação...

**Critérios de Aceite:**
- [x] JWT middleware configurado
- [x] Testes unitários passando

## T-002: User registration API

**Objetivo:** ...

**Critérios de Aceite:**
- [ ] Endpoint POST /api/users
- [ ] Validação de email
```

### Column Specification

| Column | Required | Description |
|--------|----------|-------------|
| ID | Yes | Unique identifier. Format: `T-NNN` (e.g., T-001, T-042) |
| Title | Yes | Short description of the task |
| Tipo | Yes | Task type: `Feature`, `Fix`, `Refactor`, `Chore`, `Docs`, or `Test` |
| Status | Yes | Current stage status (see valid values below) |
| Depends | Yes | Comma-separated list of task IDs this task depends on. `-` if no dependencies |
| Priority | Yes | `Alta`, `Media`, or `Baixa` |
| Version | Yes | Must match a version name from the Versions table |
| Branch | No | Git branch name. `-` if not yet created |
| Estimate | No | Task size estimate. Free text (e.g., `S`, `M`, `L`, `XL`, `2h`, `1d`). `-` if not estimated |

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

**Administrative commits (tasks.md status changes):** All status change commits across
stages 1-5 use `chore(tasks):` regardless of the task's Tipo. The Tipo-derived prefix
applies only to PR titles and code-change commits, not to task management operations.
Examples: `chore(tasks): start T-003 — set status to Validando Spec`,
`chore(tasks): mark T-003 as done`.

**Reference:** Conventional Commits 1.0.0 — https://www.conventionalcommits.org/en/v1.0.0/

### Valid Status Values

| Status | Set by | Meaning |
|--------|--------|---------|
| `Pendente` | Initial | Not started |
| `Validando Spec` | cycle-spec-stage-1 | Spec being validated |
| `Em Andamento` | cycle-impl-stage-2 | Implementation in progress |
| `Validando Impl` | cycle-impl-review-stage-3 | Implementation being reviewed |
| `Revisando PR` | cycle-pr-review-stage-4 | PR being reviewed (optional stage) |
| `**DONE**` | cycle-close-stage-5 | Completed |
| `Cancelado` | cycle-crud | Task abandoned, will not be implemented |

**Administrative status operations** (managed by cycle-crud, not by stage agents):
- **Reopen:** `**DONE**` → `Pendente` (if branch deleted) or `Em Andamento` (if branch exists) — when a bug is found after close. Also accepts `Cancelado` → `Pendente` — when a cancellation decision is reversed.
- **Advance:** move forward one stage — when work was done manually outside the pipeline
- **Demote:** move backward one stage — when rework is needed after review
- **Cancel:** any non-terminal → `Cancelado` — task will not be implemented

These operations require explicit user confirmation and a justification that is logged
in the commit message for audit trail.

### Dependency Rules

1. **A task can only start if ALL its dependencies are `**DONE**`**. If any dependency
   is not done, the task is BLOCKED. `Cancelado` does NOT satisfy dependencies —
   if a dependency is cancelled, the dependent task is blocked until the dependency
   is removed or replaced.
2. **Dependencies are by task ID**, not by status. `Depends: T-001, T-003` means
   both T-001 AND T-003 must be `**DONE**` before this task can start.
3. **`-` means no dependencies** — the task can start immediately.
4. **Circular dependencies are invalid** — agents must detect and refuse them.
5. **The execution order is determined by dependencies + status**, NOT by the order
   of rows in the table. Agents must compute the dependency graph to find which
   tasks are ready.

### Task Detail Sections

Below the table, each task has an H2 section (`## T-NNN: Title`) containing:
- **Objetivo:** What the task achieves
- **Critérios de Aceite:** Checklist of acceptance criteria (use `- [ ]` / `- [x]`)
- Any additional context: API specs, data model, references, etc.

Agents read these sections to understand what to implement and validate.

### Acceptance Criteria Tracking

The checkboxes in **Critérios de Aceite** are updated by stage agents as the task progresses:
- **cycle-impl-stage-2** marks criteria as `- [x]` as each is implemented
- **cycle-impl-review-stage-3** validates that marked criteria are actually satisfied
  (flags mismatches: `[x]` but not implemented → HIGH, `[ ]` but implemented → MEDIUM)

This ensures tasks.md accurately reflects what was delivered at every point in the lifecycle.

### Version Management

The `## Versions` section in tasks.md is **mandatory** and defines the available versions
(milestones) for the project. It is managed by `cycle-crud` (version operations).

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
2. **Version does NOT block execution** — a task in `Futuro` can be executed if the user wants.
   The version is organizational, not a gate.
3. **Cross-version dependencies are allowed** — T-003 (v2) can depend on T-001 (MVP).
   The dependency system already validates that dependencies are `**DONE**`.
4. **Moving tasks between versions** does not alter Status, Branch, Depends, or any other field.
5. **Tasks keep their version when DONE** — they are not moved automatically.
6. **Version lifecycle is manual** — the user changes version status via `cycle-crud`.
   `cycle-report` shows progress but never alters version status.
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
6. A markdown table exists with columns: ID, Title, Tipo, Status, Depends, Priority, Version, Branch, Estimate (Estimate is optional — tables without it are still valid)
7. All task IDs follow the `T-NNN` pattern
8. All Tipo values are one of: `Feature`, `Fix`, `Refactor`, `Chore`, `Docs`, `Test`
9. All Status values are one of: `Pendente`, `Validando Spec`, `Em Andamento`, `Validando Impl`, `Revisando PR`, `**DONE**`, `Cancelado`
10. All Depends values are either `-` or comma-separated valid task IDs
11. All Priority values are one of: `Alta`, `Media`, `Baixa`
12. All Version values reference a version name that exists in the Versions table
13. No duplicate task IDs
14. No circular dependencies in the dependency graph (e.g., T-001 → T-002 → T-001)

If the format marker is missing or validation fails, the agent must **STOP** and suggest
running `/optimus-cycle-migrate` to fix the format. Do NOT attempt to interpret malformed data.

15. No unescaped pipe characters (`|`) in task titles (breaks markdown table parsing)

**NOTE:** For circular dependency detection (item 14), trace the full dependency chain for
each task. If any task appears twice in the chain, a cycle exists. Report ALL tasks involved
in the cycle so the user can fix it with `/optimus-cycle-crud`.

### Parallelization

Tasks with no dependencies or all dependencies satisfied can run in parallel.
The cycle-report agent computes and displays parallelization opportunities.

---

## Task Lifecycle

Tasks flow through 5 stages (cycle-pr-review-stage-4 is optional). Status lives in `tasks.md`
(the markdown table in the target project). Each stage is a separate skill.

```
Pendente → Validando Spec → Em Andamento → Validando Impl → [Revisando PR] → **DONE**
           (cycle-spec-stage-1)   (cycle-impl-stage-2)  (cycle-impl-review-stage-3)  (cycle-pr-review-stage-4)  (cycle-close-stage-5)
                                                               [optional]

Any status → Cancelado  (via cycle-crud cancel operation)
```

### Rules

1. **Each agent changes status ONLY at the start** — when the agent is invoked, it
   updates the status to its stage. It NEVER advances to the next stage.
2. **Only the user decides to move to the next stage** — by manually invoking the
   next agent. Agents may suggest but NEVER auto-invoke the next stage.
3. **Status never goes backwards** — if a stage fails, the agent keeps working in
   the current status until it succeeds or the user stops it.
4. **Anti-pulo** — each agent validates that the task is in the expected predecessor
   status before proceeding. If not, it refuses and tells the user which agent to
   run first.
5. **Re-execution allowed** — every agent (stages 1-4) accepts being re-run when
   the task is already in its own output status. For example, cycle-impl-stage-2 accepts
   `Em Andamento` (its own status) as well as `Validando Spec` (its predecessor).
   This allows the user to re-run a stage without resetting status.
   **Exception:** cycle-close-stage-5 does NOT support re-execution — once a task is
   `**DONE**`, it cannot be re-closed.
6. **Dependency check** — every agent verifies that ALL dependencies (Depends column)
   have status `**DONE**` before proceeding. If any dependency is not done, the agent
   fires the `task-blocked` hook (if configured) and then refuses with a clear message
   identifying which dependency is blocking. **If the blocking dependency has status
   `Cancelado`**, the message must differentiate: "T-YYY was cancelled (Cancelado).
   Consider removing this dependency via `/optimus-cycle-crud`." This helps the user
   understand the blocker requires a dependency edit, not waiting for completion.
7. **Expanded confirmation on status change** — when a stage agent is about to change
   a task's status, it shows the task description (Objetivo + Critérios de Aceite) and
   asks for explicit confirmation via `AskUser`. This prevents accidental status changes
   on the wrong task, especially during auto-detect.

   **Show expanded confirmation when:**
   - The status will actually change (not re-execution), AND
   - The user did NOT specify the task ID explicitly (auto-detect picked the task)

   **Skip expanded confirmation when:**
   - Re-execution (status already equals the stage's output status — user knows the task)
   - The user specified the task ID explicitly (e.g., "execute T-012" — user has context)

   **Exception:** cycle-close-stage-5 always changes status (no re-execution), so the
   re-execution skip does not apply. It still skips when the user specified the task ID.

8. **Branch protection** — execution skills (stages 1-5) require a feature branch.
   Administrative skills can run on any branch. See the classification table below:

   **Skills are classified as Administrative or Execution:**

   | Type | Agent | Allowed on main/default? | Reason |
   |------|-------|-------------------------|--------|
   | Admin | cycle-migrate | Yes | Only creates/modifies tasks.md |
   | Admin | cycle-report | Yes | Read-only, no modifications |
   | Admin | cycle-crud | Yes | Only creates/edits/removes tasks in tasks.md |
   | Execution | cycle-spec-stage-1 | Yes (creates workspace) | Creates branch/worktree, then works there |
   | Execution | cycle-impl-stage-2 | **No** | Modifies code, verifies workspace exists |
   | Execution | cycle-impl-review-stage-3 | **No** | Modifies code (applies fixes), verifies workspace |
   | Execution | cycle-pr-review-stage-4 | **No** | Modifies code (applies fixes), verifies workspace |
   | Execution | cycle-close-stage-5 | **No** | Runs verification on task branch, then cleanup |
   | Admin | cycle-batch | Yes | Orchestrates stages, delegates to stage skills |
   | Admin | cycle-conflict-resolve | Yes | Only resolves merge conflicts in tasks.md |

   **Administrative skills** manage tasks.md metadata. They never modify project code
   and can run on any branch.

   **Execution skills** modify code or run verification. They require a feature branch
   (workspace). Stage-1 is special: it creates the workspace when invoked on the default
   branch, then switches to it. Stages 2-5 verify the workspace exists and refuse to
   run on the default branch.

   To detect the default branch:
   ```bash
   git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's@^refs/remotes/origin/@@'
   # fallback: check if current branch is "main" or "master"
   ```

9. **Branch-task cross-validation** — stages 2-5 verify that the current branch matches
   the **Branch** column in `tasks.md` for the task being worked on. This prevents
   working on the wrong branch without detection. If the branch does not match, the
   agent warns the user and asks whether to continue or switch.

### Transition Table

| Agent | Expects status | Changes to | Re-execution? |
|-------|---------------|------------|---------------|
| cycle-spec-stage-1 | `Pendente` or `Validando Spec` | `Validando Spec` | Yes (accepts own status) |
| cycle-impl-stage-2 | `Validando Spec` or `Em Andamento` | `Em Andamento` | Yes (accepts own status) |
| cycle-impl-review-stage-3 | `Em Andamento` or `Validando Impl` | `Validando Impl` | Yes (accepts own status) |
| cycle-pr-review-stage-4 | `Validando Impl` or `Revisando PR` | `Revisando PR` | Yes (accepts own status) |
| cycle-close-stage-5 | `Validando Impl` or `Revisando PR` | `**DONE**` | No (final stage) |

**NOTE:** `Cancelado` is a terminal status. No stage agent accepts it — all stages refuse
tasks with status `Cancelado`. Cancellation is managed exclusively by `cycle-crud`.

**NOTE:** cycle-pr-review-stage-4 is optional. cycle-close-stage-5 accepts both `Validando Impl`
(if pr-review was skipped) and `Revisando PR` (if pr-review ran).

**NOTE:** cycle-pr-review-stage-4 also works in standalone mode (without a task). In standalone
mode, it skips all task status logic. See its SKILL.md for detection rules.

**NOTE:** O merge do PR pode ser feito pelo cycle-close-stage-5 durante a fase de cleanup
(o agente pergunta ao usuário via AskUser com opções: merge commit, squash, rebase, keep open,
close without merging), ou manualmente pelo usuário depois.

### cycle-close-stage-5 Checklist

Before marking done, cycle-close-stage-5 runs 8 checks:
1. No uncommitted changes (`git status --porcelain` = empty)
2. No unpushed commits (`git log @{u}..HEAD` = empty)
3. PR ready to merge (if PR exists) — includes PR title validation (Conventional Commits)
4. CI passing (if PR exists)
5. `make lint` passes (all quality checks — linter, vet, format, imports)
6. `make test` passes (unit tests)
7. `make test-integration` passes (if target exists)
8. `make test-e2e` passes (if target exists)

ALL must pass (SKIP counts as pass). If any fails, status stays unchanged.

## Dry-Run Mode (all stages)

All stage agents (1-5) support **dry-run mode**. When the user includes "dry-run" or
"preview" in their invocation (e.g., "dry-run spec T-003", "preview review T-012"):

1. **Run all analysis/validation phases normally** — agent dispatch, findings, etc.
2. **Do NOT change task status** — skip the status update step
3. **Do NOT commit or push anything** — no git operations that modify state
4. **Do NOT create workspaces** — skip branch/worktree creation (stage-1)
5. **Do NOT apply fixes** — skip batch-apply phases
6. **Present results as informational** — "what would happen" without side effects

This allows users to preview what a stage would do before committing to it.

## Reusable Protocols

The protocols below are referenced by SKILL.md files with "Execute protocol X from AGENTS.md".
Each SKILL.md specifies its stage-specific parameters (stage name, expected status, etc.)
and delegates the common logic to these protocols. This avoids duplicating the same steps
in every SKILL.md.

### Protocol: tasks.md Validation (HARD BLOCK)

**Referenced by:** all stage agents (1-5), cycle-crud, cycle-batch, cycle-conflict-resolve

Every stage agent MUST validate tasks.md before operating. The full validation rules are
defined in the "Format Validation" section above (items 1-15). This protocol is the
executable version:

1. **Find tasks.md:** Look in `.optimus/tasks.md`. If not found, **STOP** and suggest `/optimus-cycle-migrate`.
2. **Validate format:** Execute all 15 validation checks from the "Format Validation" section. If the format marker is missing or any check fails, **STOP** and suggest `/optimus-cycle-migrate`.

Skills reference this as: "Find and validate tasks.md (HARD BLOCK) — see AGENTS.md Protocol: tasks.md Validation."

### Protocol: GitHub CLI Check (HARD BLOCK)

**Referenced by:** all stage agents (1-5), cycle-pr-review-stage-4, cycle-crud

```bash
gh auth status 2>/dev/null
```

If this command fails (exit code != 0), **STOP** immediately:
```
GitHub CLI (gh) is not authenticated. Run `gh auth login` to authenticate before proceeding.
```

### Protocol: Session State

**Referenced by:** all stage agents (1-5)

Stage agents write a session state file to track progress. This enables resumption
when a session is interrupted (agent crash, user closes terminal, context window limit).

**Session file location:** `.optimus/session-<task-id>.json` (project root, gitignored).
Each task gets its own file (e.g., `.optimus/session-T-003.json`).

```json
{
  "task_id": "T-003",
  "stage": "<stage-name>",
  "status": "<stage-output-status>",
  "branch": "feat/t-003-user-auth",
  "started_at": "2025-01-15T10:30:00Z",
  "updated_at": "2025-01-15T11:45:00Z",
  "phase": "Phase 1: Implementation",
  "notes": "Implementation in progress, 3 of 5 acceptance criteria done"
}
```

**On stage start (after task ID is known):**

```bash
SESSION_FILE=".optimus/session-${TASK_ID}.json"
if [ -f "$SESSION_FILE" ]; then
  cat "$SESSION_FILE"
fi
```

- If the file exists AND the task's status in `tasks.md` matches the session's `status`:
  - Present via `AskUser`:
    ```
    Previous session found:
      Task: T-XXX — [title]
      Stage: <stage-name>
      Last active: <time since updated_at>
      Progress: <phase from session>
    Resume this session?
    ```
    Options: Resume / Start fresh / Ignore
  - If **Resume**: skip to the phase indicated in the session file
  - If **Start fresh**: delete the session file and proceed normally
  - If **Ignore**: proceed normally
- If the file is stale (>24h) or the task status has changed → delete and proceed normally
- If no file exists → proceed normally

**On stage progress (at key phase transitions):**

```bash
mkdir -p .optimus
# Ensure .optimus/ session files are gitignored but tasks.md and config.json are tracked
if ! grep -q '.optimus/\*' .gitignore 2>/dev/null; then
  printf '\n.optimus/*\n!.optimus/tasks.md\n!.optimus/config.json\n' >> .gitignore
fi
cat > ".optimus/session-${TASK_ID}.json" << EOF
{"task_id":"${TASK_ID}","stage":"<stage-name>","status":"<status>","branch":"$(git branch --show-current)","started_at":"$(date -u +%Y-%m-%dT%H:%M:%SZ)","updated_at":"$(date -u +%Y-%m-%dT%H:%M:%SZ)","phase":"<current-phase>","notes":"<progress>"}
EOF
```

**On stage completion:** Delete the session file:
```bash
rm -f ".optimus/session-${TASK_ID}.json"
```

Skills reference this as: "Execute session state protocol from AGENTS.md using stage=`<name>`, status=`<status>`."

### Protocol: Workspace Verification (HARD BLOCK)

**Referenced by:** stages 2-5 (stage 1 creates the workspace instead of verifying)

Execution stages (2-5) MUST verify they are NOT on the default branch:

```bash
DEFAULT_BRANCH=$(git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's@^refs/remotes/origin/@@')
CURRENT_BRANCH=$(git branch --show-current)
```

- If `CURRENT_BRANCH` equals `DEFAULT_BRANCH` (or is `main`/`master`) → **STOP**:
  ```
  Cannot run <stage-name> on the default branch (<branch>).
  Switch to the task's feature branch first.
  ```

**Branch-task cross-validation:** After confirming the task ID, check that the current
branch matches the **Branch** column in `tasks.md` for this task:
- If Branch is `-` or empty → warn via `AskUser`: "tasks.md shows no branch for T-XXX, but you are on `<current>`. Continue anyway?"
- If Branch has a value AND does not match `CURRENT_BRANCH` → warn via `AskUser`: "tasks.md shows branch `<expected>` for T-XXX, but you are on `<current>`. Continue on current branch, or switch?"
- If Branch matches `CURRENT_BRANCH` → proceed silently

Skills reference this as: "Verify workspace (HARD BLOCK) — see AGENTS.md Protocol: Workspace Verification."

### Protocol: Divergence Warning

**Referenced by:** all stage agents (1-5)

Compare `tasks.md` on the current branch with the default branch to detect concurrent
edits that could cause merge conflicts later:

```bash
DEFAULT_BRANCH=$(git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's@^refs/remotes/origin/@@')
git fetch origin "$DEFAULT_BRANCH" --quiet 2>/dev/null
git diff "origin/$DEFAULT_BRANCH" -- .optimus/tasks.md 2>/dev/null | head -20
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

**Referenced by:** all stage agents (1-5), cycle-crud

After committing a status change, invoke notification hooks if present:

```bash
HOOKS_FILE=$(test -f ./tasks-hooks.sh && echo ./tasks-hooks.sh || (test -f ./docs/tasks-hooks.sh && echo ./docs/tasks-hooks.sh))
if [ -n "$HOOKS_FILE" ] && [ -x "$HOOKS_FILE" ]; then
  "$HOOKS_FILE" <event> <task-id> <old-status> <new-status> 2>/dev/null &
fi
```

Events: `status-change`, `task-done`, `task-cancelled`, `task-blocked`.

When a dependency check fails:
```bash
if [ -n "$HOOKS_FILE" ] && [ -x "$HOOKS_FILE" ]; then
  "$HOOKS_FILE" task-blocked <task-id> "<current-status>" "<current-status>" "blocked by <dep-id> (<dep-status>)" 2>/dev/null &
fi
```

Hooks run in background (`&`) and their failure does NOT block the pipeline.
If `tasks-hooks.sh` does not exist, hooks are silently skipped.

Skills reference this as: "Invoke notification hooks — see AGENTS.md Protocol: Notification Hooks."

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

### Protocol: Project Rules Discovery

**Referenced by:** all stage agents (1-5), deep-review, deep-doc-review, coderabbit-review

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

```bash
git log @{u}..HEAD --oneline 2>/dev/null
```

If there are unpushed commits, ask via `AskUser`:
```
There are N unpushed commits on this branch. Push now?
```
Options:
- **Push now** — `git push` (or `git push -u origin $(git branch --show-current)` if no upstream)
- **Skip** — I'll push manually later

Skills reference this as: "Offer to push commits — see AGENTS.md Protocol: Push Commits."

## Verification Command Configuration

Projects can customize verification commands via `.optimus/config.json` instead of relying
on auto-detection from Makefile or stack conventions.

### Config File

Location: `.optimus/config.json` (project root)

```json
{
  "commands": {
    "lint": "npm run lint",
    "test": "npm test",
    "test-integration": "npm run test:integration",
    "test-e2e": "npx playwright test",
    "format-check": "npx prettier --check .",
    "typecheck": "npx tsc --noEmit"
  }
}
```

### Behavior

All skills that run verification commands (verify, cycle-close-stage-5, cycle-impl-stage-2,
cycle-impl-review-stage-3) MUST check for `.optimus/config.json` BEFORE auto-detecting
commands. If the config file exists, use its commands instead of auto-detection.

If a command key is missing from the config, fall back to auto-detection for that command.
If a command key is present but empty (`""`), skip that check entirely.

## Common Patterns Across Skills

The patterns below apply to **cycle review skills** (cycle-spec-stage-1, cycle-impl-review-stage-3,
cycle-pr-review-stage-4, coderabbit-review). The standalone skills (deep-review, deep-doc-review)
use a simplified model — they follow the same user-authority and finding presentation principles
but do not require ring droid dispatch, convergence loops, or batch-apply.

### Finding Presentation (Unified Model)
All cycle review skills follow this pattern:
1. Collect findings from agents/tools
2. Consolidate and deduplicate
3. Announce total findings count: `"### Total findings to review: N"`
4. Present overview table with severity counts
5. **Deep research BEFORE presenting each finding** (see research checklist below)
6. Walk through findings ONE AT A TIME with `"Finding X of N"` header, severity order
7. For each finding: present research-backed analysis + options, collect decision via AskUser
8. **If the user responds with a question or disagreement** instead of a decision:
   STOP immediately, research the concern RIGHT NOW (WebSearch, codebase analysis),
   provide a thorough answer with evidence, then re-ask for decision. Do NOT advance.
9. After ALL N decisions collected: apply ALL approved fixes via ring droids (see below)
10. Run verification (see Verification Timing below)
11. Present final summary

### Fix Implementation (Ring Droids — MANDATORY for cycle review skills)

ALL fixes MUST be implemented by dispatching specialist ring droids via `Task` tool — the
orchestrator does NOT apply fixes directly. This ensures consistent code quality.

**Code fixes** → dispatch ring backend/frontend/QA droids with **TDD cycle** (RED-GREEN-REFACTOR):
- `ring-dev-team-backend-engineer-golang` (Go), `ring-dev-team-backend-engineer-typescript` (TS),
  `ring-dev-team-frontend-engineer` (React/Next.js), `ring-dev-team-qa-analyst` (tests)

**Documentation fixes** → dispatch ring documentation droids **without TDD** (no tests for docs):
- `ring-tw-team-functional-writer` (guides), `ring-tw-team-api-writer` (API docs),
  `ring-tw-team-docs-reviewer` (quality fixes)

**Ring droids are REQUIRED** — there is no fallback to `worker`. If the required droids are
not installed, the skill MUST stop and inform the user which droids need to be installed.

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

### Deep Research Before Presenting (MANDATORY for cycle review skills)
Applies to: cycle-spec-stage-1, cycle-impl-review-stage-3, cycle-pr-review-stage-4, coderabbit-review

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
Applies to: cycle-spec-stage-1, cycle-impl-review-stage-3, cycle-pr-review-stage-4, coderabbit-review

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

### Parallel Task Execution and tasks.md Conflicts
When using git worktrees to work on multiple tasks in parallel, each stage commits
status changes to `tasks.md` on its feature branch. When both branches are merged,
`tasks.md` will have a merge conflict. Stages 3 and 5 include a "divergence warning"
that detects this situation, but the conflict resolution is left to the user.

**Mitigation strategies (in priority order):**
1. **Merge PRs sequentially** — after merging one PR, pull the changes into the other
   feature branch before merging its PR
2. **Sync before close** — when Stage-3 or Stage-5 shows the divergence warning, choose
   "Sync now" to merge the default branch into the feature branch, resolving conflicts early
3. **Resolve conflicts in the PR** — if both PRs are already open, GitHub/GitLab will
   show a merge conflict. Resolve `tasks.md` conflicts by keeping ALL status changes
   from both branches (each task's row should reflect its own status independently)

**Conflict resolution rule for tasks.md:** When resolving merge conflicts in `tasks.md`,
keep the **most advanced status** for each task. Never revert a task's status backward
during conflict resolution. Each task's row is independent — conflicts arise from
concurrent edits to the same file, not from conflicting statuses on the same task.

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


