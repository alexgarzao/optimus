---
name: optimus-resume
description: "Resume a task after closing the terminal. Given a task ID (or auto-detecting from the in-progress tasks recorded in state.json), locates or recreates the task's worktree, reports the current status, and offers to invoke the next stage. Read-only on state.json except for user-confirmed recovery (Reset to Pendente when branch is missing)."
trigger: >
  - When user says "resume T-XXX", "retomar T-XXX", or "continuar T-XXX"
  - When user says "pick up where I left off" or "continue last task"
  - When user says "retomar", "continuar", "onde eu parei", or "fechei o terminal"
  - When user reopens the terminal and wants to return to the task they were working on
  - When user says "where was I?"
skip_when: >
  - Task is already DONE
  - Task is Cancelado
  - User explicitly wants to start a new task (use /optimus-plan T-XXX instead)
prerequisite: >
  - optimus-tasks.md exists and is valid
  - (Recommended) state.json has an entry for the task; otherwise resume falls back to the Pendente flow
NOT_skip_when: >
  - "I remember the path" -- Resume still sets up the Droid session workspace and prints the next recommended command.
  - "I can just cd manually" -- Resume also cross-checks branch/worktree and offers to recreate the worktree if missing.
examples:
  - name: Resume by task ID
    invocation: "Resume T-012"
    expected_flow: >
      1. Validate T-012 in optimus-tasks.md
      2. Read status from state.json (e.g., Em Andamento)
      3. Resolve worktree (navigate or recreate from branch)
      4. Print status + suggested "cd <path>"
      5. AskUser: invoke /optimus-build now?
  - name: Resume without ID
    invocation: "/optimus-resume"
    expected_flow: >
      1. List tasks with in-progress status in state.json (all non-terminal)
      2. If exactly one, use it; if many, AskUser to pick ordered by updated_at; if none, STOP
      3. Same workspace + next-stage flow as above
  - name: Retomar apos fechar o terminal
    invocation: "/rsm"
    expected_flow: >
      1. Auto-detect in-progress task from state.json
      2. Locate the worktree; report status, PR, uncommitted/unpushed/behind counts, stats.json churn
      3. AskUser: invoke the next recommended stage or skip
  - name: Task has no workspace yet
    invocation: "Resume T-020"
    expected_flow: >
      1. Status is Pendente (or no state.json entry)
      2. AskUser: invoke /optimus-plan T-020 now?
      3. If yes, delegate to optimus-plan
related:
  complementary:
    - optimus-report
    - optimus-quick-report
    - optimus-plan
    - optimus-build
    - optimus-review
    - optimus-pr-check
    - optimus-done
verification:
  manual:
    - Current working directory is the task's worktree (when it exists)
    - Terminal title shows "optimus: RESUME <T-XXX> — <title>"
    - No changes to optimus-tasks.md, stats.json, or session files
    - state.json is untouched UNLESS the user explicitly picked "Reset to Pendente" in Phase 3 Step 3.3 Case 3
---

# Task Resumer

Administrative skill to retake a task after closing the terminal: resolves the worktree,
reports the current status, and offers to invoke the next stage. NEVER changes task status.

**Classification:** Administrative skill — runs on any branch. Does not modify `optimus-tasks.md`,
`stats.json`, or session files. Creates a worktree only as a recovery step when the branch
exists but its worktree is missing.

## Operating Mode

This skill is structured as an **executable index**: each phase lives in its own file under
`phases/`, loaded on demand. **Before executing a phase, you MUST `Read` the phase file in
full** — phase files carry HARD BLOCKs, bash blocks, and the state.json-write carve-out.

For deviations, ambiguous instructions, or any "let me just cd manually" request, **you MUST
`Read` `rules.md` BEFORE answering**. `rules.md` carries the full anti-rationalization
guardrails AND the explicit override of the inlined `Protocol: State Management` destructive
fallback (Resume STOPs on corruption, never `rm -f`s state.json).

Shared scripts (canonical helpers):
- `scripts/runtime/optimus-mark-session.sh` — iTerm2 badge + tab color
- `scripts/runtime/optimus-state-read.sh` — JSON read of state.json
- `scripts/runtime/optimus-task-gate.sh` — status-gate validation

## Phases

Run phases in order. Before each phase, **`Read` the phase file**, then execute its steps.

1. **Phase 1 — Prerequisites.** Read `phases/01-prerequisites.md`. jq check (HARD BLOCK), optimus-tasks.md validation (HARD BLOCK), state.json integrity guard (HARD BLOCK — STOP on corruption, do NOT `rm -f`), MAIN_WORKTREE resolution.
2. **Phase 2 — Identify Task.** Read `phases/02-identify-task.md`. Resolve task ID (provided or auto-detected from state.json), parse metadata from optimus-tasks.md, refuse terminal statuses (`DONE`/`Cancelado`), informational dependency check (populate `BLOCKING_DEPS`).
3. **Phase 3 — Resolve Workspace.** Read `phases/03-resolve-workspace.md`. Derive expected branch, look up worktree, apply resolution order. Recovery path (Step 3.3) is the ONLY place that may write to state.json (user-confirmed Reset to Pendente).
4. **Phase 4 — Set Terminal Title and Report.** Read `phases/04-report.md`. Terminal marking via `bash scripts/runtime/optimus-mark-session.sh mark RESUME ...`. Collect read-only telemetry (git/PR/session/stats). Print `<json-render>` summary with absolute-path `cd` callout. Next-stage recommendation table (status × PR state).
5. **Phase 5 — Offer Next Stage.** Read `phases/05-next-stage.md`. AskUser to invoke the next stage. Dependency-aware and PR-state-aware option suppression. On delegation, restore terminal via `bash scripts/runtime/optimus-mark-session.sh clear`.

## Rules Summary

The full ruleset lives in `rules.md` — **`Read` it before any deviation, dry-run, or skip request**. The non-negotiables:

- **Admin skill** — runs on any branch, does NOT alter task status.
- **NEVER writes** to `stats.json`, `optimus-tasks.md`, or session files.
- **state.json is read-only EXCEPT** for the user-confirmed Reset to Pendente in Phase 3 Step 3.3 Case 3.
- **Override of inlined State Management:** on corruption, STOP and ask the user to fix state.json — do NOT `rm -f` (the inlined protocol's destructive fallback is explicitly disabled here).
- Worktree creation **only in recovery path** (Phase 3 Step 3.3 case 2). Never creates branches.
- Never auto-invokes another stage — only when the user explicitly picks it in Phase 5.
- **At any moment if instruction is ambiguous, conflicting, or the user requests deviation → Read `rules.md` before answering.**

<!-- INLINE-PROTOCOLS:START -->
## Shared Protocols (from AGENTS.md)

The following protocols are referenced by this skill. They are
extracted from the Optimus AGENTS.md to make this plugin self-contained.

### Protocol: Initialize .optimus Directory (summarized)

> **Summary inlined here. Full recipe at `AGENTS.md -> Protocol: Initialize .optimus Directory`.**

**Summary:** Create `${MAIN_WORKTREE}/.optimus/{sessions,reports,logs}/` with `mkdir -p`. Add `# optimus-operational-files` and `# optimus-operational-worktrees` markers to `${MAIN_WORKTREE}/.gitignore` idempotently (grep-anchor before append). Refuse symlinked `.gitignore`. Auto-prune `.optimus/logs/` (30 days, 500 files). See full recipe in AGENTS.md.

### Protocol: Terminal Identification (summarized)

> **Summary inlined here. Full recipe at `AGENTS.md -> Protocol: Terminal Identification`.**

**Summary:** `_optimus_mark_session <stage> <task_id> <title>` marks the current iTerm2 session with two **focus-independent** signals: an iTerm2 Badge (OSC 1337 SetBadgeFormat) — large semi-transparent overlay text always visible (incl. Mission Control thumbnails and Dock previews) — and a Tab Color (OSC 6 SetColors) tinting the tab per stage (PLAN=blue, BUILD=green, REVIEW=yellow, DONE=gray, RESUME/BATCH=purple). Used by stage skills so users running multiple Optimus sessions can identify each at a glance, even with the window unfocused or backgrounded. Replaces the previous AppleScript title approach which only updated reliably when the iTerm2 tab had focus and required TCC permission. Helper writes to the parent shell's controlling TTY; silent no-op outside iTerm2/macOS. Companion `_optimus_clear_session` resets badge and tab color at stage completion. See full bash function in AGENTS.md.

<!-- INLINE-PROTOCOLS:END -->
