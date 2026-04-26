---
name: optimus-build
description: "Stage 2 of the task lifecycle. Executes a validated task specification end-to-end: identifies the task, loads context from Ring pre-dev artifacts, questions ambiguities upfront, then executes each subtask via ring droid dispatch with mandatory user checkpoints. Commits only after user approval."
trigger: >
  - After optimus-plan has PASSED for a task
  - When user requests full task execution with a task ID (e.g., "execute T-012")
  - When starting implementation of a validated task from a tasks file
skip_when: >
  - Task is pure research or documentation (no code to verify)
  - No tasks file exists yet (use pre-dev workflow first)
prerequisite: >
  - Task exists in a tasks file (user provides ID or skill auto-detects next pending task)
  - Pre-task validation has passed
  - Reference docs exist (PRD, TRD, API design, data model)
  - Project rules file exists with coding standards
  - Project has a Makefile with `lint` and `test` targets
  - Ring droids installed (backend-engineer-golang and/or backend-engineer-typescript, frontend-engineer)
NOT_skip_when: >
  - "Task is simple" -- Simple tasks still need ring droid dispatch and code review.
  - "I already know the codebase" -- Always explore before coding.
  - "Tests can come later" -- TDD is enforced per subtask.
  - "Code review is optional" -- Post-implementation review is mandatory.
  - "I can implement this directly" -- Ring droid dispatch is mandatory for every subtask.
examples:
  - name: Execute a full-stack task
    invocation: "Execute task T-012"
    expected_flow: >
      1. User specified task ID -- confirm with user
      2. Load context from reference docs
      3. Explore existing codebase patterns
      4. Ask all questions upfront
      5. Execute each subtask via ring droid dispatch
      6. User checkpoint after each subtask
      7. Post-implementation code review
      8. Present summary and wait for commit approval
  - name: Execute next task (auto-detect)
    invocation: "Execute the next task"
    expected_flow: >
      1. Discover tasks file, identify next pending task
      2. Suggest to user and confirm via AskUser
      3. Standard execution flow with subtask loop
related:
  complementary:
    - ring-dev-team-backend-engineer-golang  # ring droid: Go implementation
    - ring-dev-team-backend-engineer-typescript  # ring droid: TS implementation
    - ring-dev-team-frontend-engineer  # ring droid: React/Next.js implementation
    - ring-dev-team-qa-analyst  # ring droid: test implementation
    - ring-default-code-reviewer  # ring droid: code review
    - ring-default-business-logic-reviewer  # ring droid: business logic review
    - ring-default-security-reviewer  # ring droid: security review
  sequence:
    after:
      - optimus-plan
      - pre-dev-task-breakdown  # external: ring ecosystem
      - pre-dev-subtask-creation  # external: ring ecosystem
    before:
      - optimus-review
verification:
  manual:
    - All subtasks implemented via ring droid dispatch (not directly)
    - User checkpoint passed after each subtask
    - Code review findings resolved or explicitly skipped
    - Convergence loop run, skipped, or stopped (status recorded)
    - User approved final summary before commit
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

**CRITICAL:** Set the terminal title so the user can identify this terminal at a glance. Execute this command NOW:

```bash
_optimus_set_title() {
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
   - For each dependency ID listed, read its status from state.json:
     - If ALL dependencies have status `DONE` → proceed
     - If ANY dependency is NOT `DONE`:
       - Invoke notification hooks (event=`task-blocked`) — see AGENTS.md Protocol: Notification Hooks.
       - If the dependency has status `Cancelado` → **STOP**: `"T-YYY was cancelled (Cancelado). Consider removing this dependency via /optimus-tasks."`
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
  complete. Next step: run `/optimus-review` to validate this task."

### Dry-Run Mode
If the user requests a dry-run (e.g., "dry-run impl T-003", "preview implementation"):
- Run ALL discovery and context-loading phases (Phase 1) normally
- Present the implementation plan and all questions (Step 1.9)
- **Do NOT change task status** — skip the status update in Step 1.3 (state.json write)
- **Do NOT execute implementation** — skip Phase 2 entirely
- **Do NOT commit or push anything** — skip Phase 3 commits
- Present a summary of: what would be implemented, estimated effort, identified risks

<!-- INLINE-PROTOCOLS:START -->
## Shared Protocols (from AGENTS.md)

The following protocols are referenced by this skill. They are
extracted from the Optimus AGENTS.md to make this plugin self-contained.

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

Every task MUST have a Ring pre-dev reference in the `TaskSpec` column. Stage agents
(plan, build, review) resolve the full path as `<tasksDir>/<TaskSpec>` and read the
referenced file for objective, acceptance criteria, and implementation details.

The subtasks directory is derived automatically from the TaskSpec path:
- TaskSpec: `tasks/task_001.md` → Subtasks: `<tasksDir>/subtasks/T-001/`
- The `T-NNN` identifier is extracted from the task spec filename convention

Agents read objective and acceptance criteria directly from the Ring source files.
The optimus-tasks.md table only tracks structural data (dependencies, versions, priorities)
— it does NOT duplicate content from Ring.


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


### Protocol: GitHub CLI Check (HARD BLOCK)

**Referenced by:** all stage agents (1-4), tasks, batch

```bash
gh auth status 2>/dev/null
```

If this command fails (exit code != 0), **STOP** immediately:
```
GitHub CLI (gh) is not authenticated. Run `gh auth login` to authenticate before proceeding.
```


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


<!-- INLINE-PROTOCOLS:END -->
