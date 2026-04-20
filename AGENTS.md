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
| T-004 | Password reset flow | Fix | Pendente | T-002, T-003 | Media | fix/t-004-password-reset |
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

### Acceptance Criteria Tracking

The checkboxes in **Critérios de Aceite** are updated by stage agents as the task progresses:
- **cycle-impl-stage-2** marks criteria as `- [x]` as each is implemented
- **cycle-impl-review-stage-3** validates that marked criteria are actually satisfied
  (flags mismatches: `[x]` but not implemented → HIGH, `[ ]` but implemented → MEDIUM)

This ensures tasks.md accurately reflects what was delivered at every point in the lifecycle.

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
  `ring-dev-team-frontend-engineer` (React/Next.js), `ring-dev-team-qa-analyst` (tests),
  `worker` with domain instructions (fallback)

**Documentation fixes** → dispatch ring documentation droids **without TDD** (no tests for docs):
- `ring-tw-team-functional-writer` (guides), `ring-tw-team-api-writer` (API docs),
  `ring-tw-team-docs-reviewer` (quality fixes), `worker` (fallback)

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
Skills dispatch specialist droids in parallel via Task tool:
- Preferred: ring-default-* droids (code-reviewer, business-logic-reviewer, security-reviewer, etc.)
- Fallback: worker droid with domain-specific instructions

## Known Issues and Decisions

- `codacy:ignore` does NOT exist — use the underlying linter's syntax (biome-ignore, eslint-disable, //nolint)
- DeepSource `// skipcq: <shortcode>` is the inline suppression syntax
- Native app review threads (deepsource-io, codacy-production) cannot be replied to via REST API — use GraphQL `addPullRequestReviewThreadReply`
- Biome has a known bug with JSX comments for `biome-ignore` (#8980, #9469, #7473) — exclude test files from Codacy instead
