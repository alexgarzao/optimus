---
name: optimus-done
description: "Stage 4 of the task lifecycle. Validates the PR's review feedback (Gate 3) and final state (Gate 4) before marking task as done. If reviewers flagged unresolved comments, suggests /optimus-pr-check before proceeding. Cleans up worktree and branch interactively."
trigger: >
  - After the PR has been merged or closed
  - When user requests closing a task (e.g., "close T-012", "mark T-012 as done")
skip_when: >
  - Task has not been through at least review yet
  - Task is already done
  - PR is still open (hard block — merge or close the PR first)
prerequisite: >
  - Task exists in optimus-tasks.md with status "Validando Impl" in state.json
  - review has completed
  - PR must be in final state (MERGED or CLOSED) or not exist
NOT_skip_when: >
  - "The PR was already merged" -- Still need to mark DONE and clean up worktree/branch.
  - "It's a small task" -- All tasks need the same close verification.
examples:
  - name: Close after PR merged
    invocation: "Close task T-012"
    expected_flow: >
      1. Confirm task ID
      2. Validate status and gates (uncommitted, unpushed, PR final)
      3. Mark as DONE
      4. Clean up worktree and branch
  - name: PR still open
    invocation: "Close task T-012"
    expected_flow: >
      1. Confirm task ID
      2. Gate 3 fails — PR #N is still open
      3. STOP — inform user to merge/close PR first
related:
  complementary:
    - optimus-pr-check
    - optimus-review
  sequence:
    after:
      - optimus-review
      - optimus-pr-check
verification:
  manual:
    - All 4 gates passed
    - PR review feedback addressed (or explicitly skipped via override)
    - Task status updated to DONE in state.json
    - Worktree and branch cleaned up
---

# Task Closer

Stage 4 of the task lifecycle. Verifies all prerequisites before marking a task as done.

## Operating Mode

This skill is structured as an **executable index**: each phase lives in its own
file under `phases/`, loaded on demand. **Before executing a phase, you MUST
`Read` the phase file in full** — phase files contain the binding instructions,
guardrails, and bash blocks for that step.

For deviations, ambiguous instructions, dry-run mode, or any "skip this gate"
request from the user, **you MUST `Read` `rules.md` BEFORE answering**. The
core rules are summarized at the bottom of this file; the full guardrails live
in `rules.md`.

Shared scripts (canonical helpers):
- `scripts/runtime/optimus-mark-session.sh` — iTerm2 badge + tab color
- `scripts/runtime/optimus-state-read.sh` — JSON read of state.json
- `scripts/runtime/optimus-task-gate.sh` — status-gate validation

## Phases

Run phases in order. Before each phase, **`Read` the phase file**, then execute
its steps.

1. **Phase 1 — Identify and Validate Task.** Read `phases/01-identify-and-validate.md`.
   Covers GitHub CLI check, optimus-tasks.md validation, workspace resolution
   (current-branch rule), default-branch refusal, task ID resolution, session-state
   handling (done-specific: no resume/redo), terminal marking
   (`bash scripts/runtime/optimus-mark-session.sh mark DONE ...`), status validation
   (`Validando Impl` required), dependency checks, and divergence warning.

2. **Phase 2 — Close Gates (4 sequential HARD BLOCKS).** Read `phases/02-close-gates.md`.
   Gate 1: no uncommitted changes. Gate 2: no unpushed commits. Gate 3: PR review
   feedback (CHANGES_REQUESTED → AskUser to run pr-check / override / cancel;
   REVIEW_REQUIRED → AskUser to wait / proceed). Gate 4: PR final state
   (MERGED→pass; CLOSED→AskUser; OPEN→HARD BLOCK).

3. **Phase 3 — Mark Task as Done.** Read `phases/03-mark-done.md`. Updates state.json
   to `DONE` (or `Cancelado` if Gate 4 chose that), emits notification hooks.

4. **Phase 4 — Cleanup.** Read `phases/04-cleanup.md`. Interactive removal of
   worktree and branch (local + remote). User decides what to keep. Partial-state
   contract: failed remote deletion flags `pending_remote_delete` in state.json
   for later retry. On completion, clears the iTerm2 marker via
   `bash scripts/runtime/optimus-mark-session.sh clear`.

<a id="step-resolve-current-workspace"></a>
**Anchor reference:** other skills point at the workspace-resolution step via
`#step-resolve-current-workspace`. The full step body lives in
`phases/01-identify-and-validate.md` at Step 1.0.2.

## Rules Summary

The full ruleset lives in `rules.md` — **`Read` it before any deviation, dry-run,
or skip request**. The non-negotiables:

- **Gates are sequential hard blocks** — stop at the first failure.
- **No status change unless ALL gates pass** — do NOT mark a task DONE while a gate is open.
- **Lint/tests/CI are NOT done's job** — those belong to the PR pipeline.
- **To cancel without gates, use `/optimus-tasks cancel`** — done is for the success path.
- **At any moment if instruction is ambiguous, conflicting, or the user requests deviation → Read `rules.md` before answering.**

<!-- INLINE-PROTOCOLS:START -->
## Shared Protocols (from AGENTS.md)

The following protocols are referenced by this skill. They are
extracted from the Optimus AGENTS.md to make this plugin self-contained.

### Protocol: Default Branch Resolution

**Referenced by:** done (cleanup), Workspace Auto-Navigation, Default Branch Refusal,
Resolve Tasks Git Scope, Push Commits.

**Why:** Several skills need to resolve the project repo's default branch (the
branch to checkout before deleting a feature branch, the branch the workspace
auto-navigation refuses to mutate, etc.). Non-deterministic resolutions like
`git branch --list main master | head -1` return whichever entry git happens to
list first — which depends on collation and on whether both branches exist
locally. The recipe below is fully deterministic.

**Recipe:**

```bash
# Deterministic default-branch resolution: prefer remote symbolic-ref
# (origin/HEAD), then verify against `main` first, then `master`, then bail.
DEFAULT_BRANCH=""
if symref=$(git symbolic-ref --short refs/remotes/origin/HEAD 2>/dev/null); then
  DEFAULT_BRANCH="${symref#origin/}"
elif git show-ref --verify --quiet refs/heads/main; then
  DEFAULT_BRANCH="main"
elif git show-ref --verify --quiet refs/heads/master; then
  DEFAULT_BRANCH="master"
fi

if [ -z "$DEFAULT_BRANCH" ]; then
  echo "ERROR: Could not determine default branch (no origin/HEAD, no main, no master)" >&2
  exit 1
fi
```

**Resolution order (deterministic):**

1. `origin/HEAD` symbolic-ref — the canonical answer when `gh repo clone`/
   `git clone` has set it. Fastest and works even when neither `main` nor
   `master` exists locally.
2. Local `refs/heads/main` — second-best signal: if the user has `main`
   checked out at all, it is overwhelmingly the default.
3. Local `refs/heads/master` — fall-back for legacy repos.
4. None of the above → hard error. The user must run
   `git remote set-head origin <branch>` (or fetch from origin) before any
   skill that needs the default branch can proceed.

**Why prefer `main` before `master` in the fallback chain:** when
`origin/HEAD` is absent (e.g., shallow clone, fresh repo, broken remote),
both `main` and `master` may exist locally as orphans. Probing `main` first
biases toward the modern default rather than the historical one.

**`git branch --list main master | head -1` is forbidden:** it returns
whichever name sorts first alphabetically (`main` always wins), which only
*happens* to look correct — but it also returns `main` when only `master`
actually exists locally (because `head -1` on empty stdout is empty). Any
skill that needs the default branch MUST use the recipe above.

Skills reference this as: "Resolve default branch — see AGENTS.md Protocol: Default Branch Resolution."


### Protocol: Notification Hooks (summarized)

> **Summary inlined here. Full recipe at `AGENTS.md -> Protocol: Notification Hooks`.**

**Summary:** Optional hook system: stages emit events (`status-change`, `task-blocked`, `task-done`, `task-cancelled`) by invoking `<repo>/tasks-hooks.sh <event> <task_id> <args...>` (or `<repo>/docs/tasks-hooks.sh`) if the file exists and is executable. Hook receives sanitized args (alphanumeric + space + `-_:` only — does NOT allow `.` or `/` to prevent path-traversal if hook authors interpolate args into file paths). Argument shape: 4 args for `status-change`/`task-done`/`task-cancelled` (`event task_id old_status new_status`); 4 args for `task-blocked` (`event task_id current_status reason`). Hooks run in background (`&`) — failures NEVER block the pipeline. Capture `OLD_STATUS` BEFORE writing the new status. See full event signatures + sanitization recipe in AGENTS.md.

### Protocol: State Management (summarized)

> **Summary inlined here. Full recipe at `AGENTS.md -> Protocol: State Management`.**

**Summary:** Read/write/delete entries in `${MAIN_WORKTREE}/.optimus/state.json` with `jq`. Schema: `{task_id: {status, branch, updated_at}}`. Status values: `Pendente | Validando Spec | Em Andamento | Validando Impl | DONE | Cancelado`. All writes use `jq --arg id "$TASK_ID" --arg status "$NEW_STATUS" '.[$id] = {...}'` (injection-safe), with a tmp-file + `jq empty` validation step before `mv` to guarantee atomicity. Cancelado entries keep `branch: ""` (empty string, NOT absent — readers must treat both as Cancelado-state). Corrupted state.json is removed and treated as empty (reconciliation via worktree scan). state.json is gitignored; never committed. See full recipe in AGENTS.md for jq templates and reconciliation steps.

### Protocol: Terminal Identification (summarized)

> **Summary inlined here. Full recipe at `AGENTS.md -> Protocol: Terminal Identification`.**

**Summary:** `_optimus_mark_session <stage> <task_id> <title>` marks the current iTerm2 session with two **focus-independent** signals: an iTerm2 Badge (OSC 1337 SetBadgeFormat) — large semi-transparent overlay text always visible (incl. Mission Control thumbnails and Dock previews) — and a Tab Color (OSC 6 SetColors) tinting the tab per stage (PLAN=blue, BUILD=green, REVIEW=yellow, DONE=gray, RESUME/BATCH=purple). Used by stage skills so users running multiple Optimus sessions can identify each at a glance, even with the window unfocused or backgrounded. Replaces the previous AppleScript title approach which only updated reliably when the iTerm2 tab had focus and required TCC permission. Helper writes to the parent shell's controlling TTY; silent no-op outside iTerm2/macOS. Companion `_optimus_clear_session` resets badge and tab color at stage completion. See full bash function in AGENTS.md.

<!-- INLINE-PROTOCOLS:END -->
