---
description: Stage 2 of the task lifecycle. Executes a validated task specification end-to-end: identifies the task, loads context from Ring pre-dev artifacts, questions ambiguities upfront, then executes each subtask via ring droid dispatch with mandatory user checkpoints. Commits only after user approval.
---

# Task Executor

Executes a validated task specification end-to-end: identifies the task, loads context, questions ambiguities upfront, then executes each subtask via ring droid dispatch with mandatory user checkpoints between subtasks. Commits only after user approval.

---

## Phase 1: Load Context & Question Everything

### Step 1.0: Verify GitHub CLI (HARD BLOCK)

**HARD BLOCK:** Verify GitHub CLI — see AGENTS.md Protocol: GitHub CLI Check.

### Step 1.1: Resolve and Validate optimus-tasks.md

**HARD BLOCK:** Find and validate optimus-tasks.md — see AGENTS.md Protocol: optimus-tasks.md Validation.

### Step 1.2: Identify Task to Execute

**If the user specified a task ID** (e.g., "execute T-012"):
- Use the provided task ID
- Confirm with the user using `AskUser`: "I'll execute task T-012: [task title]. Correct?"

**If the user did NOT specify a task ID** (e.g., "execute the next task", or just invoked the skill):
1. **Identify the next task ready for implementation:** Read state.json and scan for the first task that:
   - Has status `Validando Spec` (plan completed) or `Em Andamento` (re-execution)
   - Has all dependencies (Depends column from optimus-tasks.md) with status `DONE` in state.json (or Depends is `-`)
   - **Version priority:** prefer tasks from the `Ativa` version first. If none found, try `Próxima`. If none found, pick from any version and warn the user: "No eligible tasks in the active version (<name>). Suggesting T-XXX from version '<other>'."
2. **If multiple candidates exist in the same version priority**, pick the one with highest Priority (`Alta` > `Media` > `Baixa`), then lowest ID
3. **Suggest to the user** using `AskUser`: "I identified the next task to execute: T-XXX — [task title]. Is this correct, or would you like to execute a different task?"
4. **If no eligible tasks exist**, ask the user to provide a task ID

**BLOCKING**: Do NOT proceed until the user confirms which task to execute.

### Step 1.2.1: Check Session State

Execute session state protocol — see AGENTS.md Protocol: Session State. Use stage=`build`, status=`Em Andamento`.

**On stage completion** (after Phase 3 post-execution): delete the session file and restore terminal title.

### Step 1.2.2: Set Terminal Title

**CRITICAL:** Set the terminal title so the user can identify this terminal at a glance.

**First, parse `TASK_TITLE` from optimus-tasks.md** — the title is interpolated
into the terminal title below, and parsing it lazily (after the title is set)
results in `optimus: BUILD T-XXX — ` with an empty trailing dash:

```bash
# optimus-tasks.md columns by pipe index:
# | 1=<blank> | 2=ID | 3=Title | 4=Tipo | 5=Depends | 6=Priority | 7=Version | 8=Estimate | 9=TaskSpec | 10=<blank> |
# Use the same parser pattern as resume/SKILL.md Step 2.3 (Read Task Metadata).
TASK_TITLE=$(awk -F'|' -v id="$TASK_ID" '
  { gsub(/^[[:space:]]+|[[:space:]]+$/,"",$2) }
  $2 == id {
    title=$3
    gsub(/^[[:space:]]+|[[:space:]]+$/, "", title)
    print title
    exit
  }
' "$TASKS_FILE")

if [ -z "$TASK_TITLE" ]; then
  # Non-fatal: the terminal title is informational. Fall back to a stub so the
  # later interpolation does not produce a trailing-dash artifact.
  TASK_TITLE="(title unavailable)"
fi
```

Then execute the title-setter NOW. Set terminal title — see AGENTS.md Protocol: Terminal Identification. Use stage label `BUILD`:

```bash
_optimus_set_title "optimus: BUILD $TASK_ID — $TASK_TITLE"
```

**On stage completion or exit**, restore the title:

```bash
_optimus_set_title ""
```

### Step 1.3: Validate and Update Task Status

**HARD BLOCK:** This step is mandatory. Do NOT skip it.

1. Read `optimus-tasks.md` and find the row for the confirmed task ID
2. Read the task's status from state.json — see AGENTS.md Protocol: State Management.
   - If status is `Validando Spec` → proceed (plan has completed, workspace will be resolved in Step 1.4 via Workspace Auto-Navigation protocol which handles missing worktrees with branch recovery)
   - If status is `Em Andamento` → proceed (re-execution of this stage)
   - If status is `Pendente` → **STOP**: "Task T-XXX is in 'Pendente'. Run plan first."
   - If status is `Validando Impl`, `DONE`, or `Cancelado` → **STOP**: "Task T-XXX is in '<status>'. It has already moved past this stage or was cancelled."
3. **Check dependencies (HARD BLOCK):** Read the Depends column for this task from optimus-tasks.md.
   - If Depends is `-` → proceed (no dependencies)
   - For each dependency ID listed, read its status from state.json (collecting all statuses into a `DEP_STATUSES` array as you go):
     - If ALL dependencies have status `DONE` → proceed
     - If ANY dependency is NOT `DONE`:
       - Invoke notification hooks (event=`task-blocked`) — see AGENTS.md Protocol: Notification Hooks.
       - **Check all-deps-cancelled** — see AGENTS.md Protocol: All-Dependencies-Cancelled Resolution.
       - If the dependency has status `Cancelado` → **STOP**: `"T-YYY was cancelled (Cancelado). Consider removing this dependency via /optimus:tasks."`
       - Otherwise → **STOP**: `"Task T-XXX depends on T-YYY (status: '<status>'). T-YYY must be DONE first."`
3.1. **Active version guard:** Check active version guard — see AGENTS.md Protocol: Active Version Guard.
4. **Expanded confirmation before status change:**
   - **If status will change** (current status is NOT `Em Andamento`) AND the user did NOT specify the task ID explicitly (auto-detect):
     - Present to the user via `AskUser`:
       ```
       I'm about to change task T-XXX status from '<current>' to 'Em Andamento'.

       **T-XXX: [title]**
       **Version:** [version from table]

       Confirm status change?
       ```
     - **BLOCKING:** Do NOT change status until the user confirms
   - **If re-execution** (status is already `Em Andamento`) OR the user specified the task ID explicitly:
     - Skip expanded confirmation (user already has context)
5. Update status to `Em Andamento` in state.json (if not already) — see AGENTS.md Protocol: State Management.
6. Invoke notification hooks (event=`status-change`) — see AGENTS.md Protocol: Notification Hooks.

### Step 1.3.1: Check optimus-tasks.md Divergence (warning)

Check optimus-tasks.md divergence — see AGENTS.md Protocol: Divergence Warning.

### Step 1.4: Verify Workspace

**HARD BLOCK:** Resolve workspace — see AGENTS.md Protocol: Workspace Auto-Navigation.

Branch-task cross-validation is part of the workspace protocol above.

### Step 1.4.1: Refuse Default Branch (HARD BLOCK)

**HARD BLOCK:** Refuse to run on default branch — see AGENTS.md Protocol: Default Branch Refusal.

Defense-in-depth: even if Workspace Auto-Navigation was bypassed (user cancelled the
prompt, silent failure, etc.), this guard prevents commits or state mutations on the
default branch.

### Step 1.5: Validate PR Title (if PR exists)

Validate PR title — see AGENTS.md Protocol: PR Title Validation.

### Step 1.5.1: Verify Ring Droids (HARD BLOCK)

**HARD BLOCK:** Verify ring droids — see AGENTS.md Protocol: Ring Droid Requirement Check.

Build requires both **implementation droids** (for subtask dispatch) and **core review droids**
(for post-implementation review). If any are missing, **STOP** and list missing droids:
```
Required ring droids are not installed. Install them before running this skill:
  Implementation: ring-dev-team-backend-engineer-golang (Go) / ring-dev-team-backend-engineer-typescript (TS) / ring-dev-team-frontend-engineer (React)
  Review: ring-default-code-reviewer, ring-default-business-logic-reviewer, ring-default-security-reviewer, ring-default-ring-test-reviewer, ring-default-ring-nil-safety-reviewer, ring-default-ring-consequences-reviewer, ring-default-ring-dead-code-reviewer
  Spec Compliance: ring-dev-team-qa-analyst
```

### Step 1.6: Discover Project Structure

Before loading docs, discover the project's structure and tooling:

1. **Identify stack:** Check for `go.mod`, `package.json`, `Makefile`, `Cargo.toml`, etc.
2. **Verify Makefile targets (HARD BLOCK):** The project MUST have a `Makefile` with `lint` and `test` targets. If either is missing, **STOP**: "Project is missing required Makefile targets (`make lint`, `make test`). Add them before running build."
3. **Identify project rules and AI instructions (MANDATORY):** Execute project rules discovery — see AGENTS.md Protocol: Project Rules Discovery.

4. **Identify reference docs:** Look for `docs/pre-dev/`, `docs/`, or project-specific locations for tasks, PRD, TRD, API design, data model.

### Step 1.7: Load All Reference Documents

Resolve TaskSpec — see AGENTS.md Protocol: TaskSpec Resolution. Load the Ring pre-dev
task spec for objective, acceptance criteria, API contracts, data model, and implementation
guidance. Read ALL subtask files for step-by-step implementation instructions. Check for
`PARALLEL-PLAN.md` in the subtasks directory.

Also load other project reference docs:
- API contracts
- DB schema / data model
- Technical architecture (TRD)
- Business requirements (PRD)
- Coding standards / project rules
- Dependency relationships

**Ring pre-dev artifacts are the primary implementation guide.** The subtask files
contain validated code examples and exact implementation steps reviewed by multiple
AI agents during pre-dev — use them as the source of truth for HOW to implement.
The task spec's acceptance criteria are the source of truth for WHAT to validate.

### Step 1.8: Explore Existing Codebase

Before planning, understand what already exists:
- **Grep for existing patterns** in the relevant domain packages. Understand the handler/service/repository structure, error patterns, test patterns.
- **Check for migrations** and identify the latest migration number.
- **Check existing test files** for patterns (table-driven tests, testcontainers, Playwright fixtures, Vitest, etc.).

### Step 1.9: Identify and Ask ALL Questions Upfront

Before writing a single line of code, analyze the task spec for:

1. **Ambiguities:** Anything a developer would need to ask to proceed
2. **Design decisions:** UI layout choices, component structure, state management approach
3. **Missing details:** Error messages, edge cases, exact file paths for new code
4. **Conflicts with existing code:** Patterns in the codebase that differ from what the task implies

Use the `AskUser` tool to ask ALL questions at once (max 4 per call, multiple calls if needed). Group questions by topic.

**Rules:**
- Never assume — if the task spec doesn't say it explicitly, ask
- Never start coding before all questions are answered
- Questions must be specific and actionable (not "how should I do X?" but "should X use pattern A or pattern B?")
- Include your recommendation with each question so the user can just approve

---

## Phase 2: Execute Implementation

After context is loaded and all questions are answered, execute the implementation.

### Step 2.1: Load Subtasks

Read all subtask `.md` files from the subtasks directory (derived from TaskSpec in
Step 1.7). Sort by filename (`subtask_001.md`, `subtask_002.md`, etc.).

If `PARALLEL-PLAN.md` exists in the subtasks directory, read it for informational
purposes (to understand implementation structure and dependencies between subtasks).
**NOTE:** All subtasks are executed sequentially with user checkpoints between each.
Future versions may support parallel execution.

**HARD BLOCK — Zero subtasks guard:**
If 0 subtask `.md` files are found (subtasks directory missing, empty, or contains
no `.md` files):
- **STOP**: "No subtask files found for T-XXX in `<subtasks_dir>`. Subtask breakdown
  is required for implementation. Run Ring pre-dev subtask creation first
  (`/pre-dev-subtask-creation`), or create subtask files manually."
- Do NOT proceed to Step 2.2.

Present the execution plan to the user:
```
Subtasks to implement (N total):
  1. subtask_001.md — [title from first heading]
  2. subtask_002.md — [title from first heading]
  ...
```

### Step 2.2: Execute Each Subtask via Ring Droid

**HARD BLOCK — Ring droid dispatch is MANDATORY for every subtask:**

The orchestrator (this agent) MUST NOT implement code directly — it MUST delegate
to a ring droid via `Task` tool for every single subtask, regardless of size or
complexity. The orchestrator's role is to manage the loop, run tests, and present
results — never to write production code.

**Anti-rationalization (excuses the agent MUST NOT use):**
- "I can implement this small subtask directly" — NO. Dispatch a ring droid.
- "The droid will take longer" — NO. Dispatch a ring droid.
- "I already know what to do" — NO. Dispatch a ring droid.
- "This is just a config change" — NO. Dispatch a ring droid.
- "There's only one subtask" — NO. Dispatch a ring droid.

For EACH subtask (sequentially, unless PARALLEL-PLAN.md allows parallel):

**0. Gather prior-subtask summaries (F12a — required before dispatch):**

Before dispatching `subtask_NNN`, collect short summaries of subtasks
`001..NNN-1` so the droid has full continuity context. Without this, the droid
for `subtask_002` does not know what `subtask_001` produced (file paths,
exported symbols, contract decisions) and can re-derive or contradict prior
work. Two complementary sources:

- **Session/state file:** if a post-subtask state file exists in
  `.optimus/sessions/` with a `completed_subtasks[]` array (filename + 1-line
  summary + key files/symbols), read it.
- **Git history (always available):** since the task started (find the
  branch's first commit on `$TASK_BRANCH`), enumerate subtask commits:
  ```bash
  git log --oneline --grep='subtask_' "$(git merge-base HEAD origin/main)"..HEAD
  ```
  For each commit, derive the subtask number from the message and a 1-line
  summary of files touched (`git show --stat --format= <sha>`).

Compose a list of entries shaped like:

```
- subtask_001.md — Added `internal/auth/jwt.go` (SignToken, VerifyToken); updated config schema with `jwt.secret`.
- subtask_002.md — Added `internal/auth/middleware.go` (RequireAuth); updated router to apply it on /api/*.
```

Pass this list as the **Previously completed subtasks** context block in the
dispatch prompt below. For `subtask_001` the list is empty (and the prompt
section says "(none — this is the first subtask)").

**1. Dispatch the stack-appropriate ring droid** via `Task` tool:

| Stack | Ring Droid |
|-------|-----------|
| Go | `ring-dev-team-backend-engineer-golang` |
| TypeScript/Node.js | `ring-dev-team-backend-engineer-typescript` |
| React/Next.js | `ring-dev-team-frontend-engineer` |
| Tests only | `ring-dev-team-qa-analyst` |

**2. The droid prompt MUST include:**
- The subtask file content (full implementation steps + code examples from Ring pre-dev)
- The task spec objective and acceptance criteria
- Project rules and coding standards (from Step 1.6)
- Codebase patterns discovered in Step 1.8
- File paths for the droid to navigate (Read/Grep/Glob enabled)
- Answers to questions from Step 1.9
- **Previously completed subtasks:** populated by the orchestrator from prior
  subtask state (Step 0 above). For each completed subtask: `subtask_NNN.md`
  filename + 1-line summary of files created/modified + relevant exported
  symbols/contracts. For `subtask_001`, this section reads `(none — this is
  the first subtask)`. The droid uses this to avoid re-creating files,
  re-exporting symbols, or contradicting earlier contract decisions.
- Instruction: "Implement this subtask following TDD (RED-GREEN-REFACTOR).
  Write failing test first, then minimal implementation, then refactor."

**3. After the droid returns:**

a. Run unit tests quietly — see AGENTS.md Protocol: Quiet Command Execution:
```bash
_optimus_quiet_run "make-test" make test
```
The agent sees only a PASS/FAIL verdict; the full test log lives in
`.optimus/logs/` if needed for diagnosis.

b. **If tests fail (max 3 attempts per subtask):**
   1. **Logic bug** — dispatch the same ring droid with failure output and instruction:
      "Test failed after your implementation: <output>. Diagnose and fix." Re-run tests.
   2. **Flaky test** — re-execute at least 3 times in a clean environment to confirm
      flakiness. Maximum 1 test skipped per subtask. Document explicit justification
      (error message, flakiness evidence) and tag with `pending-test-fix`.
   3. **External dependency** — pause and wait for restoration.
   If tests fail after 3 attempts, ask user via `AskUser`:
   "Unit tests failing after subtask X (3 attempts). Skip and continue, or stop?"
c. If tests pass → present a summary of what changed (files created/modified, tests added)

**4. MANDATORY USER CHECKPOINT:**

**HARD BLOCK:** After EVERY subtask, the agent MUST ask the user before proceeding.
The agent MUST NOT silently stop. The agent MUST NOT silently continue. The agent
MUST NOT batch multiple subtasks without checkpoints.

Ask via `AskUser`:
```
[topic] (X/N) Subtask-X
[question] Subtask X/N complete: [one-line summary of what was done].
  Unit tests: PASS (Y tests). Ready to proceed?
[option] Continue to subtask X+1
[option] Review changes first (git diff)
[option] Stop here — I'll resume later
```

- If **Continue** → proceed to next subtask (loop back to step 1)
- If **Review changes** → run `git diff` and present, then re-ask
- If **Stop** → present partial progress summary and stop

**If this is the LAST subtask** → proceed to Step 2.3 instead of asking to continue.

### Step 2.3: Post-Implementation Verification

After ALL subtasks are complete:

1. **Run lint quietly** — see AGENTS.md Protocol: Quiet Command Execution:
   ```bash
   _optimus_quiet_run "make-lint" make lint   # MANDATORY (first run of this stage)
   ```
   If lint fails, fix formatting.

   Unit tests already passed after the last subtask (Step 2.2 loop) — no need to re-run here.

2. **Measure coverage** — see AGENTS.md Protocol: Coverage Measurement. Coverage
   commands are wrapped in `_optimus_quiet_run` by the protocol.

3. **Run integration tests (only if integration coverage was SKIPped):**
   If item 2 measured integration coverage via `make test-integration-coverage`,
   integration tests already ran — skip this step (no-op).
   Otherwise (coverage target missing, marked SKIP in item 2), run quietly:
   ```bash
   _optimus_quiet_run "make-test-integration" make test-integration   # Optional fallback — SKIP if missing
   ```
   If the target does not exist, mark as SKIP. If it fails, the helper prints
   the last 50 lines of the log automatically — then ask user via `AskUser`:
   "Integration tests failing. Fix or defer to check?"

4. **Dispatch code review and spec compliance droids** in parallel via `Task` tool:
   - `ring-default-code-reviewer`
   - `ring-default-business-logic-reviewer`
   - `ring-default-security-reviewer`
   - `ring-default-ring-test-reviewer`
   - `ring-default-ring-nil-safety-reviewer`
   - `ring-default-ring-consequences-reviewer`
   - `ring-default-ring-dead-code-reviewer`
   - `ring-dev-team-qa-analyst`

   Each droid receives all files changed by this task + project rules + task spec.
   Include per-droid quality checklists — see AGENTS.md Protocol: Per-Droid Quality Checklists.

   **Spec Compliance agent** (`ring-dev-team-qa-analyst`) must additionally (beyond the protocol):
   1. List every acceptance criterion from the Ring source (via `TaskSpec` column) and mark PASS/FAIL/PARTIAL
   2. List every test ID and verify a corresponding test exists
   3. If the task has API endpoints, verify request/response format matches API contracts
   4. If the task has DB changes, verify column types/constraints match the data model

5. **Consolidate review findings:** merge, deduplicate, sort by severity.

6. **Present findings interactively** — one at a time, severity order, collect decisions
   (same pattern as AGENTS.md "Common Patterns > Finding Presentation").

7. **Apply approved fixes** — for each approved fix, apply directly (simple) or dispatch
   ring droid (complex). Run unit tests after each fix.

8. **Convergence loop (Optional — Gated):** Execute the opt-in convergence loop — see
   AGENTS.md "Common Patterns > Protocol: Convergence Loop (Full Roster Model — Opt-In, Gated)".
   Round 1 already happened in Step 2.3 item 4 (parallel review dispatch). THIS step
   only handles rounds 2 through 5. Present the **entry gate** before round 2 (`Run round 2` / `Skip
   convergence loop`); present the **per-round gate** before rounds 3, 4, 5. If a
   dispatched round produces ZERO new findings, declare convergence and exit silently.
   Dispatch the same 8 review droids in each round. Record the final loop status
   (`CONVERGED` / `USER_STOPPED` / `SKIPPED` / `HARD_LIMIT` / `DISPATCH_FAILED_ABORTED`)
   for the Final Summary. **Failure handling (build-specific carve-out):** Long
   multi-subtask builds make a deep-Phase-2.3 blocking prompt disruptive. For `build`
   specifically, when a dispatched agent slot fails (Task tool error, ring droid
   unavailable), the orchestrator MAY treat the failed slot as "zero new findings for
   that slot" and continue silently with a warning printed to the user — diverging
   from the protocol's default behavior of asking. The user is informed via the Final
   Summary which slots were skipped and why. If multiple slots fail in the same round,
   the orchestrator falls back to the protocol default and asks `AskUser` whether to
   retry or stop (status `DISPATCH_FAILED_ABORTED`). Other skills that consume this
   protocol use the default behavior (ask immediately on first failure).

---

## Phase 3: Post-Execution

After implementation and review complete:

### Step 3.1: Test Gap Cross-Reference

Review any test gaps identified during implementation:

1. **Search future tasks** in the tasks file to check if the test is planned for a later task
2. **If planned in a future task (T-XXX):**
   - Inform the user: "Test for [scenario] is planned in T-XXX: [task title]"
   - Provide your opinion on timing: should it be created now or deferred?
   - Ask via `AskUser`: "Do you want to anticipate this test in the current task, or keep it for T-XXX?"
3. **If NOT planned in any future task:**
   - Flag as a gap and recommend adding the test to the current task
4. Do NOT silently skip test gaps because they might be covered later — always verify and ask

### Step 3.2: Present Final Summary

Present a structured summary including:
- Task ID and title
- Files created and modified
- Tests added
- Subtask execution results (X/N completed, tests passing)
- Spec compliance: X/Y acceptance criteria PASS (table with Criterion, Status, Notes)
- Code review findings summary (fixed, skipped)
- Convergence loop result:
  - Rounds dispatched (round 1 + convergence rounds): X
  - Status: CONVERGED | USER_STOPPED | SKIPPED | HARD_LIMIT | DISPATCH_FAILED_ABORTED
- Decisions made during questioning and review phases

### Step 3.3: Commit

Only after explicit user approval:

1. Run `git status` and `git diff --stat` to review
2. Run `git diff` to check for sensitive data (secrets, keys, tokens)
3. If clean, stage all relevant files and commit with a descriptive message
4. Run `git status` to confirm the commit succeeded

### Step 3.4: Push Commits (optional)

Offer to push commits — see AGENTS.md Protocol: Push Commits.

---

## Rules

### Scope Discipline
- Implement EXACTLY what the task spec says — no more, no less
- Do not refactor existing code unless the task requires it
- Do not fix unrelated bugs found during implementation (flag them to the user)
- Do not add "nice to have" improvements

### Error Handling
- If a ring droid reports a blocker, present it to the user with context from Phase 1
- If you discover a gap in the task spec during Phase 1, ask the user before starting implementation

### Communication
- Update the todo list at Phase 1 completion and after each subtask completes
- Report subtask progress as each completes (X/N)
- Never go silent — always present results and ask before proceeding
- **Next step suggestion:** After the final commit, inform the user: "Implementation
  complete. Next step: run `/optimus:review` to validate this task."

### Dry-Run Mode

Follow AGENTS.md Protocol: Dry-Run Mode. The canonical rules apply uniformly
to plan/build/review/done — see the inlined Protocol: Dry-Run Mode block below.

**Stage-2 (build) specifics:**
- The "no status change" rule means skip the state.json write in Step 1.3.
- The "no fix application" rule means skip Phase 2 (implementation) entirely.
- The "no commit/push" rule means skip Phase 3 commits.
- Phase 1 still runs in full so the user gets a complete preview of what would
  be implemented, estimated effort, and identified risks.

<!-- INLINE-PROTOCOLS:START -->
## Shared Protocols (from AGENTS.md)

The following protocols are referenced by this skill. They are
extracted from the Optimus AGENTS.md to make this plugin self-contained.

### File Location (summarized)

> **Summary inlined here. Full recipe at `AGENTS.md -> File Location`.**

**Summary:** Defines where Optimus operational files live: `${MAIN_WORKTREE}/.optimus/{state.json, stats.json, sessions/, reports/, logs/}` (gitignored, per-user) vs `<tasksDir>/optimus:tasks.md` + `<tasksDir>/{tasks,subtasks}/` (versioned, project-team-shared, propagated by git). Also: `${MAIN_WORKTREE}/.gitignore` (versioned), `${MAIN_WORKTREE}/.worktrees/` (gitignored linked-worktree dir). Critical contract: `.optimus/*` paths NEVER propagate across linked worktrees (gitignored = not shared by `git worktree add`); use `${MAIN_WORKTREE}/` prefix consistently. See full table in AGENTS.md.

Optimus splits its files into two trees:

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


### Task Spec Resolution

Every task SHOULD have a Ring pre-dev reference in the `TaskSpec` column. Tasks may be created with `TaskSpec=-` (deferred); the next `/optimus:plan` run will offer to generate or link a spec. Stage agents
(plan, build, review) resolve the full path as `<tasksDir>/<TaskSpec>` and read the
referenced file for objective, acceptance criteria, and implementation details.

The subtasks directory is derived automatically from the TaskSpec path:
- TaskSpec: `tasks/task_001.md` → Subtasks: `<tasksDir>/subtasks/T-001/`
- The `T-NNN` identifier is extracted from the task spec filename convention

Agents read objective and acceptance criteria directly from the Ring source files.
The optimus-tasks.md table only tracks structural data (dependencies, versions, priorities)
— it does NOT duplicate content from Ring.


### Format Validation (summarized)

> **Summary inlined here. Full recipe at `AGENTS.md -> Format Validation`.**

**Summary:** 15-rule validation for `<tasksDir>/optimus:tasks.md` enforced at Step 1.0.1 of every stage agent (1-4): format marker `<!-- optimus:tasks-v1 -->` present; `## Versions` table with valid columns; all Version Status values valid (`Ativa`/`Próxima`/`Planejada`/`Backlog`/`Concluída`); exactly one `Ativa`, at most one `Próxima`; tasks table columns correct (Status/Branch live in state.json, NOT here); IDs match `T-NNN`; Tipo ∈ {Feature, Fix, Refactor, Chore, Docs, Test}; Priority ∈ {Alta, Media, Baixa}; Depends resolves to existing task rows; Version cells reference existing version rows; no duplicate IDs; no circular dependencies; no unescaped pipes; empty-table guard. HARD BLOCK on any failure — STOP and suggest `/optimus:import`. See full 15-item enumeration in AGENTS.md.

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
running `/optimus:import` to fix the format. Do NOT attempt to interpret malformed data.

14. No unescaped pipe characters (`|`) in task titles (breaks markdown table parsing)
15. **Empty table handling:** If the tasks table exists but has zero data rows (only headers),
format validation PASSES. Stage agents (1-4) MUST check for this condition immediately after
format validation and before task identification. If zero data rows: **STOP** and inform the
user: "No tasks found in optimus-tasks.md. Use `/optimus:tasks` to create a task or `/optimus:import`
to import from Ring pre-dev." Do NOT proceed to task identification with an empty table.

### Protocol: Resolve Tasks Git Scope (summarized)

> **Summary inlined here. Full recipe at `AGENTS.md -> Protocol: Resolve Tasks Git Scope`.**

**Summary:** Resolves `TASKS_DIR` (from `.optimus/config.json` `tasksDir` key, default `docs/pre-dev`) and `TASKS_FILE` (`<tasksDir>/optimus:tasks.md`), then detects whether tasksDir lives inside the project repo (`same-repo`) or a separate git repo (`separate-repo`). Sets `TASKS_REPO_ROOT`, `TASKS_GIT_REL`, `TASKS_DEFAULT_BRANCH`, and exposes a `tasks_git()` helper that wraps `git -C "$TASKS_DIR"` in separate-repo mode. Hard guards: reject `tasksDir` starting with `-` (git-option injection), require `python3` for separate-repo path computation, validate `TASKS_DEFAULT_BRANCH` against `^[a-zA-Z0-9._/-]+$`. Skills MUST use `tasks_git` (never raw `git`) on `$TASKS_FILE`. See full recipe in AGENTS.md.

### Protocol: Resolve Main Worktree Path (summarized)

> **Summary inlined here. Full recipe at `AGENTS.md -> Protocol: Resolve Main Worktree Path`.**

**Summary:** Resolve `MAIN_WORKTREE` once via `git worktree list --porcelain | awk '/^worktree / {print $2; exit}'` with `${MAIN_WORKTREE:?…}` defensive guard. Use `${MAIN_WORKTREE}/.optimus/...` for ALL `.optimus/` paths (gitignored, so doesn't propagate across linked worktrees). See full recipe in AGENTS.md.

### Finding Presentation (Unified Model) (summarized)

> **Summary inlined here. Full recipe at `AGENTS.md -> Finding Presentation (Unified Model)`.**

**Summary:** Common pattern for cycle review skills (plan, build, review, pr-check, deep-review, deep-doc-review, coderabbit-review): collect findings, dedup, group same-nature, present ONE-AT-A-TIME via AskUser with strict `[topic]/[option]` template, collect ALL decisions before applying ANY fixes. Mandatory: `(X/N)` progress prefix per finding; ALL findings presented (no auto-skip by severity); HARD BLOCK on "Tell me more" or free-text response — STOP and answer immediately, never defer to end of loop. Anti-rationalization defenses listed inline ("I'll address questions at end" — NO). Scope of structured template: finding-decision AskUsers in cycle review skills only; admin AskUsers MAY use prose. See full pattern + anti-rationalization examples in AGENTS.md.

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

### Protocol: Active Version Guard

**Referenced by:** all stage agents (1-4)

After the task ID is confirmed and dependencies are validated, check if the task belongs
to the `Ativa` version. If not, present options before proceeding.

1. Read the task's **Version** column from `optimus-tasks.md`
2. Read the **Versions** table and find the version with Status `Ativa`
   - **If no version has Status `Ativa`** → **STOP**: "No active version found in the Versions table. Run `/optimus:tasks` to set a version as Ativa before proceeding."
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


### Protocol: All-Dependencies-Cancelled Resolution (summarized)

> **Summary inlined here. Full recipe at `AGENTS.md -> Protocol: All-Dependencies-Cancelled Resolution`.**

**Summary:** When every dependency in a task's `Depends:` column has status `Cancelado`, emit a multi-option resolution message AFTER the per-dep status check loop populates the `DEP_STATUSES` array. Recipe: iterate `DEP_STATUSES`, set `ALL_CANCELLED=true` if every entry equals `Cancelado`; when `ALL_CANCELLED=true` AND the array is non-empty, print three options to stderr — (a) remove all dependencies, (b) replace with alternative task IDs, (c) cancel the task itself — each with the corresponding `/optimus:tasks` invocation, then `exit 1`. If the array is empty or any dep is non-Cancelado, fall through to per-dep error. Variable contract: `DEP_STATUSES` is the canonical name; adapt if existing skill code uses another. See full recipe in AGENTS.md.

### Protocol: Convergence Loop (Full Roster Model — Opt-In, Gated) (summarized)

> **Summary inlined here. Full recipe at `AGENTS.md -> Protocol: Convergence Loop (Full Roster Model — Opt-In, Gated)`.**

**Summary:** Multi-round review pattern for plan, build, review, pr-check, coderabbit-review, deep-review, deep-doc-review. Round 1 is mandatory (the skill's primary dispatch). Rounds 2-5 are gated behind explicit `AskUser` prompts (entry gate before round 2, per-round gate before 3/4/5). Each gated round dispatches the SAME droid roster as round 1 in parallel via `Task` tool with zero prior context — agents read files fresh from disk. Convergence detection (zero new findings, strict `same file + ±5 lines + same category` matching) exits silently with status `CONVERGED` — never asks for another round. Hard limit at round 5. Exit statuses: `CONVERGED`, `USER_STOPPED`, `SKIPPED`, `HARD_LIMIT`, `DISPATCH_FAILED_ABORTED` (build has a single-slot carve-out). See full recipe in AGENTS.md.

### Protocol: Coverage Measurement (summarized)

> **Summary inlined here. Full recipe at `AGENTS.md -> Protocol: Coverage Measurement`.**

**Summary:** Measure unit + integration test coverage via Makefile targets with stack-specific fallbacks (Go: `go test -coverprofile`; Node: `npm test -- --coverage`; Python: `pytest --cov=. --cov-report=term`). Run wrapped in `_optimus_quiet_run` (Protocol: Quiet Command Execution) to keep agent context clean — the agent sees only PASS/FAIL + extracted total percentage; full per-file breakdown stays in `.optimus/logs/` and native coverage files. Thresholds: unit 85%, integration 70% (NEEDS_FIX/HIGH finding below). When scanning untested functions, read coverage output FILE (not stdout) — flag business-logic functions at 0% as HIGH; infrastructure/generated code as SKIP. If no coverage command resolves, mark SKIP — do not fail verification. See full extraction recipes in AGENTS.md.

### Protocol: Default Branch Refusal (HARD BLOCK)

**Referenced by:** build, review, done

**Why:** Workspace Auto-Navigation is the primary safeguard, but it can be bypassed
in edge cases (user cancels the AskUser prompt, silent failure, future skill that
forgets to invoke the protocol). A second, unconditional refusal at the start of any
mutating stage prevents accidental commits, worktree removals, or status writes on
the default branch.

```bash
DEFAULT_BRANCH=$(git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's@^refs/remotes/origin/@@')
if [ -z "$DEFAULT_BRANCH" ]; then
  if git show-ref --verify refs/remotes/origin/main >/dev/null 2>&1; then
    DEFAULT_BRANCH="main"
  elif git show-ref --verify refs/remotes/origin/master >/dev/null 2>&1; then
    DEFAULT_BRANCH="master"
  fi
fi
CURRENT=$(git branch --show-current 2>/dev/null)
if [ -n "$DEFAULT_BRANCH" ] && [ "$CURRENT" = "$DEFAULT_BRANCH" ]; then
  echo "ERROR: refusing to run /optimus-<stage> on default branch '$CURRENT'." >&2
  echo "       Switch to the task's feature branch (Workspace Auto-Navigation should have handled this)." >&2
  exit 1
fi
```

**Where to invoke:** immediately after Workspace Auto-Navigation completes, before
the skill performs any state.json write, git commit, git worktree mutation, or
status transition.

Skills reference this as: "Refuse to run on default branch (HARD BLOCK) — see AGENTS.md Protocol: Default Branch Refusal."


### Protocol: Divergence Warning (summarized)

> **Summary inlined here. Full recipe at `AGENTS.md -> Protocol: Divergence Warning`.**

**Summary:** Detects when `optimus-tasks.md` has diverged between the current branch and the tasks repo's default branch. Uses `tasks_git` so it works in both same-repo and separate-repo scopes. Throttles `tasks_git fetch` via a 5-minute cache marker at `${MAIN_WORKTREE}/.optimus/.last-tasks-fetch` (defense-in-depth: validates marker contents are numeric before arithmetic to survive corrupted marker files under `set -euo pipefail`). Compares against `origin/$TASKS_DEFAULT_BRANCH` via `tasks_git diff` limited to `$TASKS_GIT_REL`. On non-empty diff, warns via `AskUser` with options to **Sync now** (merge `origin/<default>`) or **Continue without syncing**. NOT a HARD BLOCK — divergence is a soft warning. Skipped silently when `TASKS_DEFAULT_BRANCH` is unresolved. See full recipe in AGENTS.md.

## Protocol: Dry-Run Mode

**Referenced by:** plan, build, review, done (all stage agents 1-4).

All stage agents support **dry-run mode**. When the user includes "dry-run" or
"preview" in their invocation (e.g., "dry-run spec T-003", "preview review T-012"),
the agent MUST:

1. **Run all analysis/validation phases normally** — agent dispatch, findings, etc.
2. **Do NOT change task status** — skip the status update step in state.json.
3. **Do NOT commit or push anything** — no git operations that modify state.
4. **Do NOT create workspaces** — skip branch/worktree creation (stage-1 only).
5. **Do NOT apply fixes** — skip batch-apply phases.
6. **Do NOT increment stage stats** — skip the Increment Stage Stats protocol.
7. **Do NOT write session files** — session state is for crash recovery of real
   executions, not previews.
8. **Skip convergence rounds 2+** — round 1 (primary review pass) is sufficient
   for preview; do NOT enter the convergence loop.
9. **Present results as informational** — phrase the summary as "what would happen"
   without implying any side effects occurred.

Stage agents may add stage-specific dry-run notes (e.g., which phase numbers
to skip), but MUST NOT relax any of the rules above. The point of dry-run is
to give the user a reliable preview with zero state mutation.


### Protocol: GitHub CLI Check (HARD BLOCK)

**Referenced by:** all stage agents (1-4), tasks, batch

```bash
gh auth status 2>/dev/null
```

If this command fails (exit code != 0), **STOP** immediately:
```
GitHub CLI (gh) is not authenticated. Run `gh auth login` to authenticate before proceeding.
```


### Protocol: Notification Hooks (summarized)

> **Summary inlined here. Full recipe at `AGENTS.md -> Protocol: Notification Hooks`.**

**Summary:** Optional hook system: stages emit events (`status-change`, `task-blocked`, `task-done`, `task-cancelled`) by invoking `<repo>/tasks-hooks.sh <event> <task_id> <args...>` (or `<repo>/docs/tasks-hooks.sh`) if the file exists and is executable. Hook receives sanitized args (alphanumeric + space + `-_:` only — does NOT allow `.` or `/` to prevent path-traversal if hook authors interpolate args into file paths). Argument shape: 4 args for `status-change`/`task-done`/`task-cancelled` (`event task_id old_status new_status`); 4 args for `task-blocked` (`event task_id current_status reason`). Hooks run in background (`&`) — failures NEVER block the pipeline. Capture `OLD_STATUS` BEFORE writing the new status. See full event signatures + sanitization recipe in AGENTS.md.

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


### Protocol: Per-Droid Quality Checklists (summarized)

> **Summary inlined here. Full recipe at `AGENTS.md -> Protocol: Per-Droid Quality Checklists`.**

**Summary:** Per-droid quality dimensions that review/pr-check/deep-review/coderabbit-review/plan/build skills MUST include in their agent prompts beyond the core review domain. Examples: code-reviewer adds resilience/concurrency/cognitive-complexity/error-handling checks; security-reviewer adds PII/error-response-leakage/rate-limiting/secrets; test-reviewer adds effectiveness/false-positive-risk/spec-traceability; nil-safety adds channel/map/slice safety; consequences adds backward-compat/migration-path/event-contract; dead-code adds zombie test infrastructure and stale feature flags; qa-analyst adds testability/operational-readiness; frontend adds UX states/accessibility/i18n; backend adds graceful-shutdown/context-propagation/structured-logging. Skills reference this when building specialist droid prompts so agents review uniformly. See full per-droid lists in AGENTS.md.

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


### Protocol: Push Commits (optional) (summarized)

> **Summary inlined here. Full recipe at `AGENTS.md -> Protocol: Push Commits (optional)`.**

**Summary:** Optional commit-push pattern for stage skills (plan, build, review, coderabbit-review). After committing locally, offer to push via `AskUser`. Step 1: detect upstream with `git rev-parse --abbrev-ref @{u}` — if missing, all local commits are unpushed and `git push -u origin <branch>` sets upstream; if present, count unpushed via `git log @{u}..HEAD`. Step 2: in `separate-repo` tasks scope, repeat the same upstream/unpushed dance against the tasks repo via `tasks_git`. After successful push, if the current repo is the Optimus plugin repo, run `droid plugin update` for each installed optimus skill so agents pick up the latest version. See full recipe in AGENTS.md.

### Protocol: Quiet Command Execution (summarized)

> **Summary inlined here. Full recipe at `AGENTS.md -> Protocol: Quiet Command Execution`.**

**Summary:** `_optimus_quiet_run <label> <command>` redirects stdout+stderr to `${MAIN_WORKTREE}/.optimus/logs/<ts>-<label>-<pid>.log`, emits a single `PASS`/`FAIL` line, and on failure dumps the last 50 lines (with `cat -v` to neutralize ANSI/OSC escape sequences). Uses `umask 0077` on the log file (output may contain credentials/stack traces). Exit code preserved so `if _optimus_quiet_run ...; then ... fi` works. Reserved exit codes: `2` = missing label/command; `3` = cannot create logs dir. Log retention (30-day age cap + 500-file count cap) is pruned at every Initialize Directory + Session State call. Use for verification commands only; never for output the agent must parse turn-by-turn. See full recipe in AGENTS.md.

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


### Protocol: Session State (summarized)

> **Summary inlined here. Full recipe at `AGENTS.md -> Protocol: Session State`.**

**Summary:** Session lifecycle state at `${MAIN_WORKTREE}/.optimus/sessions/session-${TASK_ID}.json` tracks `task_id`, `branch`, `phase`, `convergence_status`, `started_at`. Update at every phase transition. Initialize `.optimus/` directory + auto-prune `.optimus/logs/` (30-day, 500-file cap) on transition. See full recipe in AGENTS.md.

### Protocol: State Management (summarized)

> **Summary inlined here. Full recipe at `AGENTS.md -> Protocol: State Management`.**

**Summary:** Read/write/delete entries in `${MAIN_WORKTREE}/.optimus/state.json` with `jq`. Schema: `{task_id: {status, branch, updated_at}}`. Status values: `Pendente | Validando Spec | Em Andamento | Validando Impl | DONE | Cancelado`. All writes use `jq --arg id "$TASK_ID" --arg status "$NEW_STATUS" '.[$id] = {...}'` (injection-safe), with a tmp-file + `jq empty` validation step before `mv` to guarantee atomicity. Cancelado entries keep `branch: ""` (empty string, NOT absent — readers must treat both as Cancelado-state). Corrupted state.json is removed and treated as empty (reconciliation via worktree scan). state.json is gitignored; never committed. See full recipe in AGENTS.md for jq templates and reconciliation steps.

### Protocol: TaskSpec Resolution (summarized)

> **Summary inlined here. Full recipe at `AGENTS.md -> Protocol: TaskSpec Resolution`.**

**Summary:** Resolves the full path to a task's Ring pre-dev spec file by combining `<TASKS_DIR>` with the task's `TaskSpec` column from `optimus-tasks.md`. If `TaskSpec` is `-`, STOPs with a hint to run `/optimus:plan T-XXX`. HARD BLOCK on path traversal: resolves via `realpath -m` (or python3 `os.path.realpath` fallback) and rejects any result outside `$TASKS_DIR_ABS`. Also rejects symlinks (TOCTOU defence: realpath dereferences transparently, so a post-`-L` check guarantees no symlink in the final path). `TASKS_DIR` itself must be a valid git repo (enforced upstream by Resolve Tasks Git Scope) but is no longer required to live under `PROJECT_ROOT` — separate-repo scope is supported. Subtasks live at `<TASKS_DIR>/subtasks/T-NNN/`. See full recipe in AGENTS.md.

### Protocol: Terminal Identification (summarized)

> **Summary inlined here. Full recipe at `AGENTS.md -> Protocol: Terminal Identification`.**

**Summary:** `_optimus_set_title <text>` updates the terminal title for iTerm2-on-macOS via AppleScript (`osascript ... set name of s to newName`) — the only channel that reliably mutates `session.name` in "divorced" iTerm2 sessions where OSC 0/1/2 and SetUserVar are ineffective. Used by stage skills to surface task context (e.g., `optimus: PLAN T-007 — User auth`) so users running multiple Optimus sessions can identify them at a glance. The function is auto-inlined into 6 SKILLs by `inline-protocols.py` (do NOT manually paste the body in SKILL.md — F12f rule). Title is informational; failure to set it is non-fatal (silent no-op outside iTerm2/macOS, in Docker/CI without TTY, or when osascript denied). See full bash function in AGENTS.md.

### Protocol: Workspace Auto-Navigation (HARD BLOCK) (summarized)

> **Summary inlined here. Full recipe at `AGENTS.md -> Protocol: Workspace Auto-Navigation (HARD BLOCK)`.**

**Summary:** When an Optimus stage skill (build, review, done) is invoked from the default branch (main/master) instead of from the task's linked worktree, automatically detect the correct workspace and navigate there before any mutation. Resolution order: (1) state.json `branch` field for the task; (2) match against `git worktree list` by branch ref; (3) fallback path-segment match by anchored kebab task-ID (`-t-NNN-`); (4) recovery: if branch exists but worktree is missing, create at `${MAIN_WORKTREE}/.worktrees/<branch-name>` per Protocol: Worktree Location. HARD BLOCK on default branch — refuses to mutate from main/master regardless of resolution outcome. See full recipe + Default Branch Refusal cross-reference in AGENTS.md.

### Protocol: optimus-tasks.md Validation (HARD BLOCK)

**Referenced by:** all stage agents (1-4), tasks, batch. Note: resolve performs inline format validation in its own Step 4.2.

Every stage agent MUST validate optimus-tasks.md before operating. The full validation rules are
defined in the "Format Validation" section above (items 1-15). This protocol is the
executable version:

1. **Resolve paths and git scope:** Execute Protocol: Resolve Tasks Git Scope (below) to
   resolve `TASKS_DIR`, `TASKS_FILE`, `TASKS_GIT_SCOPE`, and the `tasks_git` helper.
2. **Find optimus-tasks.md:** Check if `TASKS_FILE` exists. If not found, **STOP** and suggest `/optimus:import`.
3. **Validate format:** Execute all 15 validation checks from the "Format Validation" section. If the format marker is missing or any check fails, **STOP** and suggest `/optimus:import`.

**All subsequent references to `optimus-tasks.md` in the skill use the resolved `TASKS_FILE` path.
All references to Ring pre-dev artifacts use `TASKS_DIR` as the root** — never hardcoded paths.
**All git operations on optimus-tasks.md use the `tasks_git` helper** (which handles both same-repo
and separate-repo scopes).

Skills reference this as: "Find and validate optimus-tasks.md (HARD BLOCK) — see AGENTS.md Protocol: optimus-tasks.md Validation."


<!-- INLINE-PROTOCOLS:END -->
