# Phase 1 (Identify and Validate): Task Resolution + Status Checks

Loaded by `SKILL.md` first. Covers Steps 1.0 through 1.2: GitHub CLI check,
tasks file validation, workspace resolution, default-branch refusal, task
identification, session-state handling, terminal marking, status validation
(with dependency checks), and divergence warning.

## Step 1.0: Verify GitHub CLI (HARD BLOCK)

Verify GitHub CLI — see AGENTS.md Protocol: GitHub CLI Check.

## Step 1.0.1: Resolve and Validate optimus-tasks.md

**HARD BLOCK:** Find and validate optimus-tasks.md — see AGENTS.md Protocol: optimus-tasks.md Validation.

<a id="step-resolve-current-workspace"></a>
## Step 1.0.2: Resolve Current Workspace (HARD BLOCK)

Use the Workspace Auto-Navigation guardrails, but for `done` apply a stricter rule:
when the user does **not** specify a task ID, close only the task from the **current**
feature branch/worktree. Never offer a list of multiple tasks to close.

1. If the user specified a task ID explicitly, resolve that task and perform the usual
   branch-task cross-validation.
2. If the user did **not** specify a task ID:
   - If the current branch is a task feature branch/worktree, resolve the task from the
     current branch and continue.
   - If the current branch is the default branch (or the workspace does not map to exactly
     one task), **STOP** and tell the user:
     ```
     /optimus-done only closes the current task from the current branch.
     Switch to the task branch/worktree first, or run `/optimus-done T-XXX`.
     ```
3. Do NOT scan all `Validando Impl` tasks and do NOT present a multi-task chooser.

## Step 1.0.2.1: Refuse Default Branch (HARD BLOCK)

Refuse to run on default branch — see AGENTS.md Protocol: Default Branch Refusal.

Defense-in-depth: even though Step 1.0.2 already STOPs on the default branch when no
task ID is given, this guard catches the explicit-task-ID path as well — closing a
task while sitting on the default branch is never correct, regardless of how the
skill was invoked.

## Step 1.0.3: Identify Task to Close

**If the user specified a task ID** (e.g., "close T-012"):
- Use the provided task ID
- Confirm with the user using `AskUser`: "I'll close task T-012: [task title]. Correct?"

**If the user did NOT specify a task ID:**
1. Use the task resolved from the current feature branch/worktree in Step 1.0.2
2. If no current task can be resolved safely, **STOP** and ask the user to switch to the
   task branch/worktree or invoke `/optimus-done T-XXX`
3. Do NOT offer multiple tasks as choices

**BLOCKING**: Do NOT proceed until the user confirms which task to close.

## Step 1.0.3.1: Session State (done-specific)

`done` must not offer to resume, start fresh, redo previous stages, or restart the
stage from zero.

If `.optimus/sessions/session-T-XXX.json` exists:
- If it is corrupted or stale, delete it silently and proceed
- Otherwise, reuse/overwrite it for the current `done` execution and proceed
- Do NOT present options like `Resume`, `Start fresh`, or `Continue`

`done` either continues with the current close gates or stops with a clear blocking
message. It never offers to redo `plan`, `build`, or `review`.

**On marking DONE** (Phase 3): delete the session file and restore terminal title.

## Step 1.0.3.2: Set Terminal Title

**CRITICAL:** Set the terminal title so the user can identify this terminal at a glance.

**Substitute `$TASK_ID` and `$TASKS_FILE`** with the confirmed task ID and resolved
optimus-tasks.md path before running the block. The parse and the mark call
**MUST live in the SAME bash invocation** — each Bash tool invocation is a
fresh shell, so a `TASK_TITLE` parsed in a previous block would NOT survive
into a separate mark call. See AGENTS.md Protocol: Terminal Identification.

```bash
# optimus-tasks.md columns by pipe index:
# | 1=<blank> | 2=ID | 3=Title | 4=Tipo | 5=Depends | 6=Priority | 7=Version | 8=Estimate | 9=TaskSpec | 10=<blank> |
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
  # Non-fatal: the badge text is informational. Fall back to a stub so the
  # badge does not render as a bare "DONE" with no task context.
  TASK_TITLE="(title unavailable)"
fi

# Canonical helper (badge + tab color). Silent no-op outside iTerm2/macOS.
bash scripts/runtime/optimus-mark-session.sh mark DONE "$TASK_ID" "$TASK_TITLE"
```

**On stage completion or exit**, restore the title:

```bash
bash scripts/runtime/optimus-mark-session.sh clear
```

## Step 1.1: Validate Task Status

**HARD BLOCK:** This step is mandatory. Do NOT skip it.

1. Read `optimus-tasks.md` and find the row for the confirmed task ID
2. Read the task's status from state.json — see AGENTS.md Protocol: State Management.
   - If status is `Validando Impl` → proceed (review has completed)
   - If status is `Pendente` → **STOP**: "Task T-XXX is in 'Pendente'. It must go through plan, build, and review first."
   - If status is `Validando Spec` → **STOP**: "Task T-XXX is in 'Validando Spec'. Run build and review first."
   - If status is `Em Andamento` → **STOP**: "Task T-XXX is in 'Em Andamento'. Run review first."
   - If status is `DONE` → **STOP**: "Task T-XXX is already done. Re-execution of done is not supported."
   - If status is `Cancelado` → **STOP**: "Task T-XXX was cancelled. Cannot close a cancelled task."
3. **Check dependencies (HARD BLOCK):** Read the Depends column for this task from optimus-tasks.md.
   - If Depends is `-` → proceed (no dependencies)
   - For each dependency ID listed, read its status from state.json (collecting all statuses into a `DEP_STATUSES` array as you go):
     - If ALL dependencies have status `DONE` → proceed
     - If ANY dependency is NOT `DONE`:
       - Invoke notification hooks (event=`task-blocked`) — see AGENTS.md Protocol: Notification Hooks.
       - **Check all-deps-cancelled** — see AGENTS.md Protocol: All-Dependencies-Cancelled Resolution.
       - If the dependency has status `Cancelado` → **STOP**: `"T-YYY was cancelled (Cancelado). Consider removing this dependency via /optimus-tasks."`
       - Otherwise → **STOP**: `"Task T-XXX depends on T-YYY (status: '<status>'). T-YYY must be DONE first."`
3.1. **Active version guard:** Check active version guard — see AGENTS.md Protocol: Active Version Guard.
4. **Expanded confirmation before status change:**
   - **If the user did NOT specify the task ID explicitly** (auto-detect):
     - Present to the user via `AskUser`:
       ```
       I'm about to close task T-XXX and mark it as DONE (from '<current>').

       **T-XXX: [title]**
       **Version:** [version from table]

       Confirm close?
       ```
     - **BLOCKING:** Do NOT proceed to the close checklist until the user confirms
   - **If the user specified the task ID explicitly** (e.g., "close T-012"):
     - Skip expanded confirmation (user already has context)

   **NOTE:** done does not support re-execution (status always changes to `DONE`), so the re-execution skip does not apply here.

## Step 1.2: Check optimus-tasks.md Divergence (warning)

Check optimus-tasks.md divergence — see AGENTS.md Protocol: Divergence Warning.
