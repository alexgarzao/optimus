---
name: optimus-review
description: "Stage 3 of the task lifecycle. Validates that a completed task was implemented correctly: spec compliance, coding standards adherence, engineering best practices, test coverage, and production readiness. Uses parallel specialist agents for deep analysis, then presents findings interactively. Runs AFTER optimus-build finishes to validate code quality and spec compliance before the task can proceed to PR review or close."
trigger: >
  - After optimus-build completes all phases and verification gates pass
  - When user requests validation of a completed task (e.g., "validate T-012")
  - Before the final commit of a task execution
skip_when: >
  - Task is pure research or documentation (no code to validate)
  - Already inside a code review skill execution
prerequisite: >
  - Task execution is complete (user provides ID or skill auto-detects last executed task)
  - Changed files exist (committed or uncommitted -- both are supported)
  - Reference docs exist (task spec, coding standards)
  - Project has a Makefile with `lint` and `test` targets
NOT_skip_when: >
  - "Task was simple" -- Simple tasks still need spec compliance checks.
  - "Tests already pass" -- Passing tests do not guarantee spec compliance or code quality.
  - "optimus-build already ran verification gates" -- Gates check pass/fail; this validates correctness.
  - "Time pressure" -- Validation prevents rework, saving time overall.
examples:
  - name: Validate a full-stack task
    invocation: "Validate task T-012"
    expected_flow: >
      1. User specified task ID -- confirm with user
      2. Load task spec and reference docs
      3. Identify changed files
      4. Dispatch 8 parallel agents (code, business logic, security, QA, frontend, backend, cross-file, spec compliance)
      5. Consolidate and deduplicate findings
      6. Present overview table
      7. Interactive finding-by-finding resolution
      8. Batch apply approved fixes
      9. Run verification gate
      10. Present validation summary
  - name: Validate last executed task (auto-detect)
    invocation: "Validate the last task"
    expected_flow: >
      1. Check session state files or git diff for context
      2. Identify the task that was just executed
      3. Suggest to user and confirm via AskUser
      4. Standard validation flow
  - name: Validate a frontend-only task
    invocation: "Validate task T-015"
    expected_flow: >
      1. User specified task ID -- confirm with user
      2. Load context, classify as frontend-only
      3. Dispatch 7 agents (skip backend specialist)
      4. Consolidate, present, resolve findings
      5. Apply fixes, verify
related:
  complementary:
    - optimus-plan
    - optimus-build
    - optimus-deep-doc-review
  sequence:
    after:
      - optimus-build
verification:
  automated:
    - command: "git diff --name-only 2>/dev/null | wc -l"
      description: Changed files exist (uncommitted changes to validate)
      success_pattern: '[1-9]'
  manual:
    - All findings resolved (fixed or explicitly skipped by user)
    - Verification gate passed after fixes applied
    - Convergence loop run, skipped, or stopped (status recorded)
    - Validation summary presented to user
---

# Post-Task Validator

Validates that a completed task was implemented correctly: spec compliance, coding standards
adherence, engineering best practices, test coverage, and production readiness. Uses parallel
specialist agents for deep analysis, then presents findings interactively.

Runs AFTER optimus-build finishes. Validates both committed and uncommitted
changes — it handles both cases (use `git diff` for uncommitted, `git diff base..HEAD`
for committed code).

## Operating Mode

This skill is structured as an **executable index**: each phase lives in its own
file under `phases/`, loaded on demand. **Before executing a phase, you MUST
`Read` the phase file in full** — phase files contain the binding instructions,
HARD BLOCKs, agent roster, and bash blocks for that step.

For deviations, ambiguous instructions, dry-run mode, or any "skip this
finding" request, **you MUST `Read` `rules.md` BEFORE answering**. The
core rules are summarized at the bottom of this file; the full guardrails
(Agent Dispatch, Scope, Objectivity, Prioritization, Test Gap Cross-Reference,
No False Positives, User Authority, Communication, Dry-Run Mode) live in
`rules.md`.

## Phases

Run phases in order. Before each phase, **`Read` the phase file**, then execute
its steps.

1. **Phase 1 — Load Context.** Read `phases/01-load-context.md`. GH CLI, tasks.md, workspace, default-branch refusal, terminal marking (iTerm2 badge + tab color via inline helper), status validation (`Em Andamento` → `Validando Impl`), deps, project structure, doc-brief, changed-files, scope.
2. **Phase 2 — Static Analysis and Coverage.** Read `phases/02-static-analysis.md`. Lint/vet/format in parallel, unit tests with coverage, gap analysis.
3. **Phase 3 — Parallel Agent Dispatch.** Read `phases/03-agent-dispatch.md`. Agent roster, prompt template, per-agent instructions, severity classification.
4. **Phase 4 — Consolidate and Present.** Read `phases/04-consolidate-and-present.md`. Merge, dedupe, sort, overview table.
5. **Phase 5 — Resolve Findings (Interactive).** Read `phases/05-resolve-findings.md`. **HARD BLOCK on Tell-me-more — anti-rationalization block carried verbatim.**
6. **Phase 6 — Apply Fixes.** Read `phases/06-apply-fixes.md`. Batch-apply approved fixes, re-run tests, summary.
7. **Phase 7 — Finalize.** Read `phases/07-finalize.md`. Convergence loop (opt-in), Re-run Guard, integration tests, validation summary, optional push + PR. Clears iTerm2 marker via the inline `_optimus_clear_session` helper (defined in the phase file).

## Rules Summary

The full ruleset lives in `rules.md` — **`Read` it before any deviation, dry-run,
or skip request**. The non-negotiables:

- **Agents run in PARALLEL** — do NOT serialize the dispatch.
- **Scope is the task's changed files** — never the entire codebase. Pre-existing
  issues don't count as findings.
- **Every finding cites a specific rule** — "I'd do it differently" is NOT valid.
- **No auto-decisions on findings** — the USER decides every finding, regardless of severity.
- **Tell-me-more = IMMEDIATE response** — never defer to the end of the findings loop.
- **Deep research before every finding** — Option A must be backed by evidence.
- **Re-run guard replaces "suggest next stage"** — see `phases/07-finalize.md`.
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

### Protocol: Re-run Guard (summarized)

> **Summary inlined here. Full recipe at `AGENTS.md -> Protocol: Re-run Guard`.**

**Summary:** Replaces the static "next step" suggestion in plan and review. Counts `total_findings` from this execution (grouped entries count as 1). If 0 → suggest next stage (build for plan, done for review). If >0 → `AskUser` offering "Re-run with clean context" (re-dispatches ALL agents with no memory of prior decisions — skipped findings will reappear) or "Advance to next stage". Re-run reset semantics (MANDATORY): reset `convergence_status` to `null`, `phase` to entry, overwrite `started_at`; preserve identity fields. Skip GitHub CLI/tasks validation/workspace/divergence checks; re-execute discovery + dispatch. No re-run limit. See full reset checklist in AGENTS.md.

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
