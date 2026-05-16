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

Executes a validated task specification end-to-end: identifies the task, loads
context, questions ambiguities upfront, then executes each subtask via ring
droid dispatch with mandatory user checkpoints between subtasks. Commits only
after user approval.

## Operating Mode

This skill is structured as an **executable index**: each phase lives in its own
file under `phases/`, loaded on demand. **Before executing a phase, you MUST
`Read` the phase file in full** — phase files contain the binding instructions,
HARD BLOCKs, anti-rationalization rules, and bash blocks for that step.

For deviations, ambiguous instructions, dry-run mode, or any "implement this
directly without a droid" request, **you MUST `Read` `rules.md` BEFORE
answering**. The core rules are summarized at the bottom of this file; the
full guardrails (Scope Discipline, Error Handling, Communication, Dry-Run
Mode) live in `rules.md`.

Shared scripts (canonical helpers):
- `scripts/runtime/optimus-mark-session.sh` — iTerm2 badge + tab color
- `scripts/runtime/optimus-state-read.sh` — JSON read of state.json
- `scripts/runtime/optimus-task-gate.sh` — status-gate validation

## Phases

Run phases in order. Before each phase, **`Read` the phase file**, then execute
its steps.

1. **Phase 1 — Load Context & Question Everything.** Read `phases/01-load-context.md`.
   Covers GitHub CLI check, tasks.md validation, task ID resolution, session
   state, terminal marking
   (`bash scripts/runtime/optimus-mark-session.sh mark BUILD ...`), status
   validation (`Validando Spec` or `Em Andamento`), dependency checks, workspace
   verification, default-branch refusal, PR title validation, ring droid
   requirement check, project structure discovery (Makefile lint/test HARD
   BLOCK), doc-brief loading, codebase exploration, and upfront questioning.

2. **Phase 2 — Execute Implementation.** Read `phases/02-execute-implementation.md`.
   Subtask loop with **MANDATORY ring droid dispatch** (anti-rationalization
   block carried verbatim — the orchestrator MUST NEVER implement directly),
   prior-subtask context gathering (F12a), per-subtask TDD cycle, user
   checkpoint after each subtask, post-implementation lint/coverage/integration
   verification, parallel review droid dispatch (8 droids), and optional
   convergence loop with build-specific failure carve-out.

3. **Phase 3 — Post-Execution.** Read `phases/03-post-execution.md`. Test-gap
   cross-reference with future tasks, final summary, commit (only after
   explicit user approval), and optional push. On completion, clears the iTerm2
   marker via `bash scripts/runtime/optimus-mark-session.sh clear`.

## Rules Summary

The full ruleset lives in `rules.md` — **`Read` it before any deviation, dry-run,
or skip request**. The non-negotiables:

- **Ring droid dispatch is MANDATORY for every subtask** — the orchestrator MUST
  NEVER implement code directly, regardless of size or complexity. The
  anti-rationalization block in `phases/02-execute-implementation.md` lists the
  excuses you MUST NOT use.
- **Implement EXACTLY what the task spec says** — no refactors, no "nice to
  haves", no unrelated bug fixes.
- **User checkpoint after EVERY subtask** — never batch, never silently
  continue, never silently stop.
- **TDD per subtask** — RED-GREEN-REFACTOR in the droid prompt.
- **Commit only after explicit user approval** — never commit unilaterally.
- **At any moment if instruction is ambiguous, conflicting, or the user requests deviation → Read `rules.md` before answering.**

<!-- INLINE-PROTOCOLS:START -->
## Shared Protocols (from AGENTS.md)

The following protocols are referenced by this skill. They are
extracted from the Optimus AGENTS.md to make this plugin self-contained.

### Task Spec Resolution

Every task SHOULD have a Ring pre-dev reference in the `TaskSpec` column. Tasks may be created with `TaskSpec=-` (deferred); the next `/optimus-plan` run will offer to generate or link a spec. Stage agents
(plan, build, review) resolve the full path as `<tasksDir>/<TaskSpec>` and read the
referenced file for objective, acceptance criteria, and implementation details.

The subtasks directory is derived automatically from the TaskSpec path:
- TaskSpec: `tasks/task_001.md` → Subtasks: `<tasksDir>/subtasks/T-001/`
- The `T-NNN` identifier is extracted from the task spec filename convention

Agents read objective and acceptance criteria directly from the Ring source files.
The optimus-tasks.md table only tracks structural data (dependencies, versions, priorities)
— it does NOT duplicate content from Ring.


### Protocol: Coverage Measurement (summarized)

> **Summary inlined here. Full recipe at `AGENTS.md -> Protocol: Coverage Measurement`.**

**Summary:** Measure unit + integration test coverage via Makefile targets with stack-specific fallbacks (Go: `go test -coverprofile`; Node: `npm test -- --coverage`; Python: `pytest --cov=. --cov-report=term`). Run wrapped in `_optimus_quiet_run` (Protocol: Quiet Command Execution) to keep agent context clean — the agent sees only PASS/FAIL + extracted total percentage; full per-file breakdown stays in `.optimus/logs/` and native coverage files. Thresholds: unit 85%, integration 70% (NEEDS_FIX/HIGH finding below). When scanning untested functions, read coverage output FILE (not stdout) — flag business-logic functions at 0% as HIGH; infrastructure/generated code as SKIP. If no coverage command resolves, mark SKIP — do not fail verification. See full extraction recipes in AGENTS.md.

### Protocol: Notification Hooks (summarized)

> **Summary inlined here. Full recipe at `AGENTS.md -> Protocol: Notification Hooks`.**

**Summary:** Optional hook system: stages emit events (`status-change`, `task-blocked`, `task-done`, `task-cancelled`) by invoking `<repo>/tasks-hooks.sh <event> <task_id> <args...>` (or `<repo>/docs/tasks-hooks.sh`) if the file exists and is executable. Hook receives sanitized args (alphanumeric + space + `-_:` only — does NOT allow `.` or `/` to prevent path-traversal if hook authors interpolate args into file paths). Argument shape: 4 args for `status-change`/`task-done`/`task-cancelled` (`event task_id old_status new_status`); 4 args for `task-blocked` (`event task_id current_status reason`). Hooks run in background (`&`) — failures NEVER block the pipeline. Capture `OLD_STATUS` BEFORE writing the new status. See full event signatures + sanitization recipe in AGENTS.md.

### Protocol: Per-Droid Quality Checklists (summarized)

> **Summary inlined here. Full recipe at `AGENTS.md -> Protocol: Per-Droid Quality Checklists`.**

**Summary:** Per-droid quality dimensions that review/pr-check/deep-review/coderabbit-review/plan/build skills MUST include in their agent prompts beyond the core review domain. Examples: code-reviewer adds resilience/concurrency/cognitive-complexity/error-handling checks; security-reviewer adds PII/error-response-leakage/rate-limiting/secrets; test-reviewer adds effectiveness/false-positive-risk/spec-traceability; nil-safety adds channel/map/slice safety; consequences adds backward-compat/migration-path/event-contract; dead-code adds zombie test infrastructure and stale feature flags; qa-analyst adds testability/operational-readiness; frontend adds UX states/accessibility/i18n; backend adds graceful-shutdown/context-propagation/structured-logging. Skills reference this when building specialist droid prompts so agents review uniformly. See full per-droid lists in AGENTS.md.

### Protocol: Quiet Command Execution (summarized)

> **Summary inlined here. Full recipe at `AGENTS.md -> Protocol: Quiet Command Execution`.**

**Summary:** `_optimus_quiet_run <label> <command>` redirects stdout+stderr to `${MAIN_WORKTREE}/.optimus/logs/<ts>-<label>-<pid>.log`, emits a single `PASS`/`FAIL` line, and on failure dumps the last 50 lines (with `cat -v` to neutralize ANSI/OSC escape sequences). Uses `umask 0077` on the log file (output may contain credentials/stack traces). Exit code preserved so `if _optimus_quiet_run ...; then ... fi` works. Reserved exit codes: `2` = missing label/command; `3` = cannot create logs dir. Log retention (30-day age cap + 500-file count cap) is pruned at every Initialize Directory + Session State call. Use for verification commands only; never for output the agent must parse turn-by-turn. See full recipe in AGENTS.md.

### Protocol: State Management (summarized)

> **Summary inlined here. Full recipe at `AGENTS.md -> Protocol: State Management`.**

**Summary:** Read/write/delete entries in `${MAIN_WORKTREE}/.optimus/state.json` with `jq`. Schema: `{task_id: {status, branch, updated_at}}`. Status values: `Pendente | Validando Spec | Em Andamento | Validando Impl | DONE | Cancelado`. All writes use `jq --arg id "$TASK_ID" --arg status "$NEW_STATUS" '.[$id] = {...}'` (injection-safe), with a tmp-file + `jq empty` validation step before `mv` to guarantee atomicity. Cancelado entries keep `branch: ""` (empty string, NOT absent — readers must treat both as Cancelado-state). Corrupted state.json is removed and treated as empty (reconciliation via worktree scan). state.json is gitignored; never committed. See full recipe in AGENTS.md for jq templates and reconciliation steps.

### Protocol: TaskSpec Resolution (summarized)

> **Summary inlined here. Full recipe at `AGENTS.md -> Protocol: TaskSpec Resolution`.**

**Summary:** Resolves the full path to a task's Ring pre-dev spec file by combining `<TASKS_DIR>` with the task's `TaskSpec` column from `optimus-tasks.md`. If `TaskSpec` is `-`, STOPs with a hint to run `/optimus-plan T-XXX`. HARD BLOCK on path traversal: resolves via `realpath -m` (or python3 `os.path.realpath` fallback) and rejects any result outside `$TASKS_DIR_ABS`. Also rejects symlinks (TOCTOU defence: realpath dereferences transparently, so a post-`-L` check guarantees no symlink in the final path). `TASKS_DIR` itself must be a valid git repo (enforced upstream by Resolve Tasks Git Scope) but is no longer required to live under `PROJECT_ROOT` — separate-repo scope is supported. Subtasks live at `<TASKS_DIR>/subtasks/T-NNN/`. See full recipe in AGENTS.md.

### Protocol: Terminal Identification (summarized)

> **Summary inlined here. Full recipe at `AGENTS.md -> Protocol: Terminal Identification`.**

**Summary:** `_optimus_mark_session <stage> <task_id> <title>` marks the current iTerm2 session with two **focus-independent** signals: an iTerm2 Badge (OSC 1337 SetBadgeFormat) — large semi-transparent overlay text always visible (incl. Mission Control thumbnails and Dock previews) — and a Tab Color (OSC 6 SetColors) tinting the tab per stage (PLAN=blue, BUILD=green, REVIEW=yellow, DONE=gray, RESUME/BATCH=purple). Used by stage skills so users running multiple Optimus sessions can identify each at a glance, even with the window unfocused or backgrounded. Replaces the previous AppleScript title approach which only updated reliably when the iTerm2 tab had focus and required TCC permission. Helper writes to the parent shell's controlling TTY; silent no-op outside iTerm2/macOS. Companion `_optimus_clear_session` resets badge and tab color at stage completion. See full bash function in AGENTS.md.

<!-- INLINE-PROTOCOLS:END -->
