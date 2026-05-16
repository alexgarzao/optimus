---
name: optimus-plan
description: "Stage 1 of the task lifecycle. Validates a task specification against project docs BEFORE code generation begins. Catches gaps, contradictions, ambiguities, test coverage holes, and observability issues. Creates workspace (branch/worktree). Analysis only -- does not generate code."
trigger: >
  - Before starting any task implementation
  - When user requests spec validation (e.g., "validate spec for T-006")
  - Before invoking optimus-build for a task
skip_when: >
  - Task is already implemented (use optimus-review instead)
  - Task is pure research with no implementation deliverables
prerequisite: >
  - Task exists in optimus-tasks.md (user provides ID or skill auto-detects next pending task). If TaskSpec is `-`, plan offers to generate it via ring:pre-dev-feature in Phase 1 Step 1.0.4.5 (self-heal).
  - Reference docs exist (PRD, TRD, API design, data model)
  - Coding standards / project rules file exists
NOT_skip_when: >
  - "Task spec looks complete" -- Completeness is not correctness. Cross-doc contradictions are invisible without validation.
  - "We already reviewed the spec" -- Human review misses field-level contradictions. Automated validation catches what eyes skip.
  - "Time pressure" -- Validation prevents rework, saving more time than it costs.
  - "Simple task" -- Simple tasks still need dependency and test coverage checks.
examples:
  - name: Validate a full-stack task
    invocation: "Validate spec for T-006"
    expected_flow: >
      1. User specified task ID -- confirm with user
      2. Discover project structure and reference docs
      3. Load task spec and all reference docs
      4. Cross-reference across all docs
      5. Analyze test coverage gaps
      6. Analyze observability gaps
      7. Present summary table, then walk through findings one at a time
      8. Batch apply all approved corrections
  - name: Validate next task (auto-detect)
    invocation: "Validate the next task"
    expected_flow: >
      1. Discover tasks file, identify next pending task
      2. Suggest to user and confirm via AskUser
      3. Standard validation flow
  - name: Validate a backend-only task
    invocation: "Validate spec for T-010"
    expected_flow: >
      1. User specified task ID -- confirm with user
      2. Load context, skip frontend-related checks
      3. Focus on API contracts, data model, integration tests
      4. Present and resolve findings
related:
  complementary:
    - optimus-build
    - optimus-review
  differentiation:
    - name: optimus-review
      difference: >
        optimus-review validates AFTER implementation (code correctness,
        test quality, code review). optimus-plan validates BEFORE
        implementation (spec correctness, doc consistency, test design).
  sequence:
    before:
      - optimus-build
verification:
  manual:
    - All contradictions between docs resolved
    - All test coverage gaps addressed or explicitly accepted
    - Convergence loop run, skipped, or stopped (status recorded)
    - Task spec updated with corrections before implementation begins
---

# Pre-Task Validator

Validates a task specification against project docs BEFORE code generation begins.
Catches gaps, contradictions, and ambiguities that would cause rework.

## Operating Mode

This skill is structured as an **executable index**: each phase lives in its own
file under `phases/`, loaded on demand. **Before executing a phase, you MUST
`Read` the phase file in full** — phase files contain the binding instructions,
guardrails, and bash blocks for that step.

For deviations, ambiguous instructions, dry-run mode, or any "skip this phase"
request from the user, **you MUST `Read` `rules.md` BEFORE answering**. The
core rules are summarized at the bottom of this file; the full guardrails live
in `rules.md`.

Templates referenced by phases:
- `templates/validation-dimensions.md` — the 8 dimensions Phase 3 must cover
- `templates/output-format.md` — the final Validation Report layout

## Phases

Run phases in order. Before each phase, **`Read` the phase file**, then execute
its steps.

1. **Phase 1 — Setup, Task Identification, Workspace.** Read `phases/01-setup.md`.
   Covers GitHub CLI check, optimus-tasks.md validation, task ID resolution,
   terminal marking (iTerm2 badge + tab color via inline helper),
   status/dependency validation, abandoned-workspace recovery, missing-spec
   self-heal, worktree creation, divergence warning, stats increment.

2. **Phase 2 — Load Context, Build Doc Brief.** Read `phases/02-load-context.md`.
   Project structure discovery, docs loading, Doc Brief cache, existing-code
   verification.

3. **Phase 3 — Execution (Cross-Ref, Test/Observability Gaps, Agent Dispatch).**
   Read `phases/03-execution.md` AND `templates/validation-dimensions.md`.
   Dispatches 4 ring droids in parallel.

4. **Phase 4 — Present and Resolve Findings.** Read `phases/04-present-findings.md`
   AND `templates/output-format.md`. **HARD BLOCK on Tell-me-more rule** —
   the phase file carries the anti-rationalization guardrails verbatim.

5. **Phase 5 — Apply Approved Corrections.** Read `phases/05-apply-corrections.md`.

6. **Phase 6 — Commit Changes.** Read `phases/06-commit.md`.

7. **Phase 7 — Convergence Loop (optional, gated).** Read `phases/07-convergence.md`.

8. **Phase 8 — Re-run Guard.** Read `phases/08-rerun-guard.md`.

9. **Phase 9 — Push Commits (optional).** Read `phases/09-push.md`.
   On completion, clear the iTerm2 marker:
   the inline `_optimus_clear_session` helper (defined in the phase file).

## Rules Summary

The full ruleset lives in `rules.md` — **`Read` it before any deviation, dry-run,
or skip request**. The non-negotiables:

- **No code generation** — analysis only.
- **No auto-decisions on findings** — the USER decides every finding, regardless of severity.
- **Tell-me-more = IMMEDIATE response** — never defer to the end of the findings loop.
- **Deep research before every finding** — Option A must be backed by evidence (project patterns, docs, best practices).
- **Test coverage gaps (Dimension 5) and observability (Dimension 7) are MANDATORY** — NEVER skip a sub-section.
- **Re-run guard replaces "suggest next stage"** — see `phases/08-rerun-guard.md`.
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


### Protocol: Notification Hooks (summarized)

> **Summary inlined here. Full recipe at `AGENTS.md -> Protocol: Notification Hooks`.**

**Summary:** Optional hook system: stages emit events (`status-change`, `task-blocked`, `task-done`, `task-cancelled`) by invoking `<repo>/tasks-hooks.sh <event> <task_id> <args...>` (or `<repo>/docs/tasks-hooks.sh`) if the file exists and is executable. Hook receives sanitized args (alphanumeric + space + `-_:` only — does NOT allow `.` or `/` to prevent path-traversal if hook authors interpolate args into file paths). Argument shape: 4 args for `status-change`/`task-done`/`task-cancelled` (`event task_id old_status new_status`); 4 args for `task-blocked` (`event task_id current_status reason`). Hooks run in background (`&`) — failures NEVER block the pipeline. Capture `OLD_STATUS` BEFORE writing the new status. See full event signatures + sanitization recipe in AGENTS.md.

### Protocol: Per-Droid Quality Checklists (summarized)

> **Summary inlined here. Full recipe at `AGENTS.md -> Protocol: Per-Droid Quality Checklists`.**

**Summary:** Per-droid quality dimensions that review/pr-check/deep-review/coderabbit-review/plan/build skills MUST include in their agent prompts beyond the core review domain. Examples: code-reviewer adds resilience/concurrency/cognitive-complexity/error-handling checks; security-reviewer adds PII/error-response-leakage/rate-limiting/secrets; test-reviewer adds effectiveness/false-positive-risk/spec-traceability; nil-safety adds channel/map/slice safety; consequences adds backward-compat/migration-path/event-contract; dead-code adds zombie test infrastructure and stale feature flags; qa-analyst adds testability/operational-readiness; frontend adds UX states/accessibility/i18n; backend adds graceful-shutdown/context-propagation/structured-logging. Skills reference this when building specialist droid prompts so agents review uniformly. See full per-droid lists in AGENTS.md.

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
