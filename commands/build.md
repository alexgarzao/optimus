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

Then execute the title-setter NOW. Mark terminal session (iTerm2 badge + tab color). The function body is inlined here on purpose: each Bash tool invocation is a fresh shell, so a definition pasted in another code block does NOT survive into this one. See AGENTS.md Protocol: Terminal Identification. The canonical body of the function lives there.

```bash
_optimus_mark_session() {
  local stage="$1" task_id="$2" title="$3"
  [ "$LC_TERMINAL" = "iTerm2" ] || [ "$TERM_PROGRAM" = "iTerm.app" ] || return 0
  local pid="$PPID" target_tty=""
  for _ in 1 2 3 4; do
    [ -z "$pid" ] || [ "$pid" = "1" ] && break
    target_tty=$(ps -o tty= -p "$pid" 2>/dev/null | tr -d ' ')
    case "$target_tty" in
      ""|"?"|"??") pid=$(ps -o ppid= -p "$pid" 2>/dev/null | tr -d ' '); target_tty="" ;;
      *) break ;;
    esac
  done
  _optimus_emit() {
    if [ -n "$target_tty" ] && [ -w "/dev/$target_tty" ]; then
      printf '%s' "$1" > "/dev/$target_tty" 2>/dev/null || printf '%s' "$1"
    else
      printf '%s' "$1"
    fi
  }
  local badge_b64
  badge_b64=$(printf '%s %s\n%s' "$stage" "$task_id" "$title" | base64 | tr -d '\n')
  _optimus_emit "$(printf '\e]1337;SetBadgeFormat=%s\a' "$badge_b64")"
  local r g b
  case "$stage" in
    PLAN)   r=66;  g=135; b=245 ;;
    BUILD)  r=34;  g=197; b=94  ;;
    REVIEW) r=234; g=179; b=8   ;;
    DONE)   r=148; g=163; b=184 ;;
    *)      r=168; g=85;  b=247 ;;
  esac
  _optimus_emit "$(printf '\e]6;1;bg;red;brightness;%d\a\e]6;1;bg;green;brightness;%d\a\e]6;1;bg;blue;brightness;%d\a' "$r" "$g" "$b")"
}
_optimus_mark_session BUILD "$TASK_ID" "$TASK_TITLE"
```

**On stage completion or exit**, restore the title (body inlined for the same reason as above):

```bash
_optimus_clear_session() {
  [ "$LC_TERMINAL" = "iTerm2" ] || [ "$TERM_PROGRAM" = "iTerm.app" ] || return 0
  local pid="$PPID" target_tty=""
  for _ in 1 2 3 4; do
    [ -z "$pid" ] || [ "$pid" = "1" ] && break
    target_tty=$(ps -o tty= -p "$pid" 2>/dev/null | tr -d ' ')
    case "$target_tty" in
      ""|"?"|"??") pid=$(ps -o ppid= -p "$pid" 2>/dev/null | tr -d ' '); target_tty="" ;;
      *) break ;;
    esac
  done
  _optimus_emit_clear() {
    if [ -n "$target_tty" ] && [ -w "/dev/$target_tty" ]; then
      printf '%s' "$1" > "/dev/$target_tty" 2>/dev/null || printf '%s' "$1"
    else
      printf '%s' "$1"
    fi
  }
  _optimus_emit_clear "$(printf '\e]1337;SetBadgeFormat=\a')"
  _optimus_emit_clear "$(printf '\e]6;1;bg;*;default\a')"
}
_optimus_clear_session
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


### Protocol: GitHub CLI Check (HARD BLOCK)

**Referenced by:** all stage agents (1-4), tasks, batch

```bash
gh auth status 2>/dev/null
```

If this command fails (exit code != 0), **STOP** immediately:
```
GitHub CLI (gh) is not authenticated. Run `gh auth login` to authenticate before proceeding.
```


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


<!-- INLINE-PROTOCOLS:END -->
