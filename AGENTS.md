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
├── cycle-spec-stage-1/              # Execution Stage 1: Spec validation + workspace creation
├── cycle-impl-stage-2/              # Execution Stage 2: Task implementation
├── cycle-impl-review-stage-3/       # Execution Stage 3: Implementation review
├── cycle-pr-review-stage-4/         # Execution Stage 4 (optional): PR review orchestrator
├── cycle-close-stage-5/             # Execution Stage 5: Close task (verify & mark done)
├── deep-review/                       # Parallel code review (no PR context)
├── deep-doc-review/                   # Documentation review
├── coderabbit-review/                 # CodeRabbit CLI + TDD cycle
└── verify/                            # Automated verification (lint/test/build)
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
Convergence loops must use escalating scrutiny (5 rounds). Agents in re-validation
rounds should analyze from scratch — the orchestrator deduplicates, not the agent.
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

All agents search for `tasks.md` in this order:
1. `./tasks.md` (project root) — **preferred**
2. `./docs/tasks.md` — fallback

If not found in either location, the agent must inform the user and suggest running
`cycle-migrate` to create one. Do NOT look in other locations.

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

| ID | Title | Tipo | Status | Depends | Priority | Branch |
|----|-------|------|--------|---------|----------|--------|
| T-001 | Setup auth module | Feature | **DONE** | - | Alta | - |
| T-002 | User registration API | Feature | Em Andamento | T-001 | Alta | feat/t-002-user-registration |
| T-003 | Login page | Feature | Pendente | T-001 | Alta | - |
| T-004 | Password reset flow | Fix | Pendente | T-002, T-003 | Media | - |
| T-005 | E2E auth tests | Test | Pendente | T-002, T-003 | Media | - |

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
| Branch | No | Git branch name. `-` if not yet created |

### Valid Tipo Values

| Tipo | Meaning | Conventional commit prefix |
|------|---------|---------------------------|
| `Feature` | New functionality | `feat` |
| `Fix` | Bug fix | `fix` |
| `Refactor` | Internal improvement, no behavior change | `refactor` |
| `Chore` | Infra, config, CI, dependencies | `chore` |
| `Docs` | Documentation only | `docs` |
| `Test` | Add/improve tests without changing production code | `test` |

### Valid Status Values

| Status | Set by | Meaning |
|--------|--------|---------|
| `Pendente` | Initial | Not started |
| `Validando Spec` | cycle-spec-stage-1 | Spec being validated |
| `Em Andamento` | cycle-impl-stage-2 | Implementation in progress |
| `Validando Impl` | cycle-impl-review-stage-3 | Implementation being reviewed |
| `Revisando PR` | cycle-pr-review-stage-4 | PR being reviewed (optional stage) |
| `**DONE**` | cycle-close-stage-5 | Completed |

### Dependency Rules

1. **A task can only start if ALL its dependencies are `**DONE**`**. If any dependency
   is not done, the task is BLOCKED.
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

### Format Validation

Every stage agent (1-5) MUST validate the tasks.md format before operating:
1. **First line** is `<!-- optimus:tasks-v1 -->` (format marker)
2. A markdown table exists with columns: ID, Title, Tipo, Status, Depends, Priority, Branch
3. All task IDs follow the `T-NNN` pattern
4. All Tipo values are one of: `Feature`, `Fix`, `Refactor`, `Chore`, `Docs`, `Test`
5. All Status values are one of: `Pendente`, `Validando Spec`, `Em Andamento`, `Validando Impl`, `Revisando PR`, `**DONE**`
6. All Depends values are either `-` or comma-separated valid task IDs
7. No duplicate task IDs

If the format marker is missing or validation fails, the agent must **STOP** and suggest
running `/optimus-cycle-migrate` to fix the format. Do NOT attempt to interpret malformed data.

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
   refuses with a clear message identifying which dependency is blocking.
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

### Transition Table

| Agent | Expects status | Changes to | Re-execution? |
|-------|---------------|------------|---------------|
| cycle-spec-stage-1 | `Pendente` or `Validando Spec` | `Validando Spec` | Yes (accepts own status) |
| cycle-impl-stage-2 | `Validando Spec` or `Em Andamento` | `Em Andamento` | Yes (accepts own status) |
| cycle-impl-review-stage-3 | `Em Andamento` or `Validando Impl` | `Validando Impl` | Yes (accepts own status) |
| cycle-pr-review-stage-4 | `Validando Impl` or `Revisando PR` | `Revisando PR` | Yes (accepts own status) |
| cycle-close-stage-5 | `Validando Impl` or `Revisando PR` | `**DONE**` | No (final stage) |

**NOTE:** cycle-pr-review-stage-4 is optional. cycle-close-stage-5 accepts both `Validando Impl`
(if pr-review was skipped) and `Revisando PR` (if pr-review ran).

**NOTE:** cycle-pr-review-stage-4 also works in standalone mode (without a task). In standalone
mode, it skips all task status logic. See its SKILL.md for detection rules.

**NOTE:** Merge do PR é manual, feito pelo usuário DEPOIS do cycle-close-stage-5 marcar DONE.

### cycle-close-stage-5 Checklist

Before marking done, cycle-close-stage-5 runs 8 checks:
1. No uncommitted changes (`git status --porcelain` = empty)
2. No unpushed commits (`git log @{u}..HEAD` = empty)
3. PR ready to merge (if PR exists) — does NOT merge, user merges manually after
4. CI passing (if PR exists)
5. `make lint` passes (all quality checks — linter, vet, format, imports)
6. `make test` passes (unit tests)
7. `make test-integration` passes (if target exists)
8. `make test-e2e` passes (if target exists)

ALL must pass (SKIP counts as pass). If any fails, status stays unchanged.

## Project Rules Discovery (all skills)

Every skill that reviews, validates, or generates code MUST search for project rules
and AI instruction files before starting. The checklist (in priority order):

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

If NONE exist, the agent must warn the user. If any are found, they become the
source of truth for coding standards and must be passed to every dispatched sub-agent.

## Common Patterns Across Skills

### Finding Presentation
All review/validation skills follow this pattern:
1. Collect findings from agents/tools
2. Consolidate and deduplicate
3. Present overview table with severity counts
4. Walk through findings one by one (AskUser for each decision)
5. Batch apply approved fixes
6. Present final summary

### Convergence Loop
Used by: cycle-spec-stage-1, cycle-impl-review-stage-3, cycle-pr-review-stage-4, coderabbit-review
- 5 rounds maximum (round 1 = initial analysis)
- Escalating scrutiny: standard → skeptical → adversarial → cross-cutting → final sweep
- Stop only when: zero new findings, round 5 reached, or user explicitly stops

### Agent Dispatch
Skills dispatch specialist droids in parallel via Task tool:
- Preferred: ring-default-* droids (code-reviewer, business-logic-reviewer, security-reviewer, etc.)
- Fallback: worker droid with domain-specific instructions

## Known Issues and Decisions

- `codacy:ignore` does NOT exist — use the underlying linter's syntax (biome-ignore, eslint-disable, //nolint)
- DeepSource `// skipcq: <shortcode>` is the inline suppression syntax
- Native app review threads (deepsource-io, codacy-production) cannot be replied to via REST API — use GraphQL `addPullRequestReviewThreadReply`
- Biome has a known bug with JSX comments for `biome-ignore` (#8980, #9469, #7473) — exclude test files from Codacy instead
