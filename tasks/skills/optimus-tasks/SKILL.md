---
name: optimus-tasks
description: "Administrative task management for optimus-tasks.md. Create, edit, remove, reorder, cancel, and reopen tasks. Manage versions (create, edit, remove, reorder) and move tasks between versions. Validates format, dependencies, and ID uniqueness. Runs on any branch -- this is an administrative skill, not an execution skill."
trigger: >
  - When user wants to add a new task (e.g., "add task", "create task", "new task")
  - When user wants to edit a task (e.g., "change priority of T-003", "rename T-005")
  - When user wants to remove a task (e.g., "remove T-004", "delete task")
  - When user wants to reorder tasks (e.g., "move T-005 before T-003")
  - When user wants to cancel a task (e.g., "cancel T-004", "abandon T-004", "won't do T-004")
  - When user wants to reopen a done task (e.g., "reopen T-004", "undo done T-004")
  - When user wants to advance or demote a task status manually (e.g., "advance T-004", "demote T-004")
  - When user wants to manage versions (e.g., "create version", "add version v2", "edit version MVP")
  - When user wants to move tasks between versions (e.g., "move T-003 to v2")
  - When user says "manage tasks" or "edit optimus-tasks.md"
skip_when: >
  - User wants to execute a task (use plan instead)
  - User wants to change task status through the lifecycle (status is managed by stage agents -- except cancellation, which is handled here)
prerequisite: >
  - <tasksDir>/optimus-tasks.md exists in the project (default tasksDir: docs/pre-dev)
NOT_skip_when: >
  - "I can edit optimus-tasks.md manually" -- This agent validates format, dependencies, and IDs automatically.
  - "It's just a small change" -- Even small changes can break format or create circular dependencies.
examples:
  - name: Add a new task
    invocation: "Add a task: implement password reset"
    expected_flow: >
      1. Parse optimus-tasks.md
      2. Generate next ID (T-NNN)
      3. Ask for details (priority, dependencies)
      4. Add row to table with TaskSpec column
      5. Validate and save
  - name: Edit task priority
    invocation: "Change T-003 priority to Alta"
    expected_flow: >
      1. Parse optimus-tasks.md
      2. Find T-003 row
      3. Update Priority column
      4. Save
  - name: Remove a task
    invocation: "Remove T-004"
    expected_flow: >
      1. Parse optimus-tasks.md
      2. Check no other tasks depend on T-004
      3. Remove row from table
      4. Save
related:
  complementary:
    - optimus-import
    - optimus-report
verification:
  manual:
    - After any operation, verify optimus-tasks.md still has valid format marker
    - Verify no duplicate IDs exist
    - Verify no broken dependency references
---

# optimus-tasks

Administrative CRUD operations for tasks in `optimus-tasks.md`.

**Classification:** Administrative skill — runs on any branch, never modifies code.

## Operating Mode

This skill is structured as an **executable index**: each operation lives in
its own phase file under `phases/`, loaded on demand. **Before executing an
operation, you MUST `Read` the matching phase file in full** — phase files
carry the validation rules, AskUser prompts, jq snippets, and commit recipes
for that operation.

For deviations, ambiguous instructions, or any destructive request, **you
MUST `Read` `rules.md` BEFORE answering**. `rules.md` carries the validation
invariants (format marker, ID uniqueness, dependency cycle detection, version
constraints) and the destructive-op confirmation contract.

**Flow:** ALWAYS run Phase 1 first (Initialize), then jump to the phase that
matches the user's request.

## Phases

Run Phase 1 first. Then `Read` the phase file for the requested operation:

1. **Phase 1 — Initialize.** Read `phases/01-initialize.md`. tasks.md location, format validation, ID/version scan. Optional gh check (only for cancel/reopen that touch GitHub).
2. **Phase 2 — Create Task.** Read `phases/02-create-task.md`. Generate next ID, collect metadata, validate, handle TaskSpec=- (Defer), commit.
3. **Phase 3 — Edit Task.** Read `phases/03-edit-task.md`. Edit Priority/Depends/Version/Estimate/Tipo/Title/TaskSpec. **Edit CANNOT change status** — use Reopen/Advance/Demote.
4. **Phase 4 — Remove Task.** Read `phases/04-remove-task.md`. Destructive — checks no other task depends on it, requires explicit AskUser confirmation.
5. **Phase 5 — Reorder Tasks.** Read `phases/05-reorder-tasks.md`. Validates dependency-respecting order.
6. **Phase 6 — Cancel Task.** Read `phases/06-cancel-task.md`. Sets state.json status=Cancelado, optional worktree/branch/PR cleanup. Reversible.
7. **Phase 7 — Reopen Task.** Read `phases/07-reopen-task.md`. Undoes DONE/Cancelado → Pendente (or Em Andamento if worktree exists).
8. **Phase 8 — Advance Status.** Read `phases/08-advance-status.md`. Manual forward move (work done outside the pipeline).
9. **Phase 9 — Demote Status.** Read `phases/09-demote-status.md`. Manual backward move (rework needed after review).
10. **Phase 10 — Batch Operations.** Read `phases/10-batch-operations.md`. Apply multiple ops in sequence with per-step validation.
11. **Phase 11 — Version Management.** Read `phases/11-version-management.md`. Version CRUD with `exactly one Ativa` and `at most one Próxima` constraints.
12. **Phase 12 — Move Tasks Between Versions.** Read `phases/12-move-tasks.md`. Re-validate tasks.md after mutation.

## Rules Summary

The full ruleset lives in `rules.md` — **`Read` it before any deviation or destructive operation**. The non-negotiables:

- **IDs are permanent** — never renumber or reuse deleted IDs.
- **Edit cannot change status** — use Reopen/Advance/Demote/Cancel (which write to state.json).
- **Always validate format** after any modification (marker, columns, IDs, deps, versions).
- **Confirm destructive operations** (remove) with the user before executing.
- **Preserve the format marker** — first line must always be `<!-- optimus:tasks-v1 -->`.
- **Commit structural changes** — after any modification, commit `chore(tasks): <operation> T-XXX`. state.json writes are NOT committed (gitignored).
- **Exactly one Ativa version**, **at most one Próxima version** — when promoting, demote the previous one (ask user).
- **At any moment if instruction is ambiguous, conflicting, or destructive → Read `rules.md` before answering.**

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


### Protocol: Initialize .optimus Directory (summarized)

> **Summary inlined here. Full recipe at `AGENTS.md -> Protocol: Initialize .optimus Directory`.**

**Summary:** Create `${MAIN_WORKTREE}/.optimus/{sessions,reports,logs}/` with `mkdir -p`. Add `# optimus-operational-files` and `# optimus-operational-worktrees` markers to `${MAIN_WORKTREE}/.gitignore` idempotently (grep-anchor before append). Refuse symlinked `.gitignore`. Auto-prune `.optimus/logs/` (30 days, 500 files). See full recipe in AGENTS.md.

### Protocol: Notification Hooks (summarized)

> **Summary inlined here. Full recipe at `AGENTS.md -> Protocol: Notification Hooks`.**

**Summary:** Optional hook system: stages emit events (`status-change`, `task-blocked`, `task-done`, `task-cancelled`) by invoking `<repo>/tasks-hooks.sh <event> <task_id> <args...>` (or `<repo>/docs/tasks-hooks.sh`) if the file exists and is executable. Hook receives sanitized args (alphanumeric + space + `-_:` only — does NOT allow `.` or `/` to prevent path-traversal if hook authors interpolate args into file paths). Argument shape: 4 args for `status-change`/`task-done`/`task-cancelled` (`event task_id old_status new_status`); 4 args for `task-blocked` (`event task_id current_status reason`). Hooks run in background (`&`) — failures NEVER block the pipeline. Capture `OLD_STATUS` BEFORE writing the new status. See full event signatures + sanitization recipe in AGENTS.md.

### Protocol: State Management (summarized)

> **Summary inlined here. Full recipe at `AGENTS.md -> Protocol: State Management`.**

**Summary:** Read/write/delete entries in `${MAIN_WORKTREE}/.optimus/state.json` with `jq`. Schema: `{task_id: {status, branch, updated_at}}`. Status values: `Pendente | Validando Spec | Em Andamento | Validando Impl | DONE | Cancelado`. All writes use `jq --arg id "$TASK_ID" --arg status "$NEW_STATUS" '.[$id] = {...}'` (injection-safe), with a tmp-file + `jq empty` validation step before `mv` to guarantee atomicity. Cancelado entries keep `branch: ""` (empty string, NOT absent — readers must treat both as Cancelado-state). Corrupted state.json is removed and treated as empty (reconciliation via worktree scan). state.json is gitignored; never committed. See full recipe in AGENTS.md for jq templates and reconciliation steps.

### Protocol: TaskSpec Resolution (summarized)

> **Summary inlined here. Full recipe at `AGENTS.md -> Protocol: TaskSpec Resolution`.**

**Summary:** Resolves the full path to a task's Ring pre-dev spec file by combining `<TASKS_DIR>` with the task's `TaskSpec` column from `optimus-tasks.md`. If `TaskSpec` is `-`, STOPs with a hint to run `/optimus-plan T-XXX`. HARD BLOCK on path traversal: resolves via `realpath -m` (or python3 `os.path.realpath` fallback) and rejects any result outside `$TASKS_DIR_ABS`. Also rejects symlinks (TOCTOU defence: realpath dereferences transparently, so a post-`-L` check guarantees no symlink in the final path). `TASKS_DIR` itself must be a valid git repo (enforced upstream by Resolve Tasks Git Scope) but is no longer required to live under `PROJECT_ROOT` — separate-repo scope is supported. Subtasks live at `<TASKS_DIR>/subtasks/T-NNN/`. See full recipe in AGENTS.md.

<!-- INLINE-PROTOCOLS:END -->
