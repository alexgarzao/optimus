---
name: optimus-build
description: "Stage 2 of the task lifecycle. Executes a validated task specification end-to-end: identifies the task, loads context from Ring pre-dev artifacts, questions ambiguities upfront, then delegates execution to the dev-cycle skill. Commits only after user approval."
trigger: >
  - After optimus-plan has PASSED for a task
  - When user requests full task execution with a task ID (e.g., "execute T-012")
  - When starting implementation of a validated task from a tasks file
skip_when: >
  - Already inside a dev-cycle execution (dev-cycle orchestrates its own gates)
  - Task is pure research or documentation (no code to verify)
  - No tasks file exists yet (use pre-dev workflow first)
prerequisite: >
  - Task exists in a tasks file (user provides ID or skill auto-detects next pending task)
  - Pre-task validation has passed
  - Reference docs exist (PRD, TRD, API design, data model)
  - Project rules file exists with coding standards
  - Project has lint, test, integration test, and E2E test commands configured
NOT_skip_when: >
  - "Task is simple" -- Simple tasks still need the full dev-cycle gates.
  - "I already know the codebase" -- Always explore before coding.
  - "Tests can come later" -- dev-cycle enforces testing gates.
  - "Code review is optional" -- dev-cycle Gate 4 is mandatory.
examples:
  - name: Execute a full-stack task
    invocation: "Execute task T-012"
    expected_flow: >
      1. User specified task ID -- confirm with user
      2. Load context from reference docs
      3. Explore existing codebase patterns
      4. Ask all questions upfront
      5. Invoke dev-cycle to execute 6-gate pipeline
      6. Present summary and wait for commit approval
  - name: Execute next task (auto-detect)
    invocation: "Execute the next task"
    expected_flow: >
      1. Discover tasks file, identify next pending task
      2. Suggest to user and confirm via AskUser
      3. Standard execution flow via dev-cycle
  - name: Resume interrupted execution
    invocation: "Resume task T-012"
    expected_flow: >
      1. Invoke dev-cycle --resume
      2. dev-cycle resumes from last completed gate
related:
  complementary:
    - dev-cycle  # external: ring ecosystem
    - dev-implementation  # external: ring ecosystem
    - dev-testing  # external: ring ecosystem
    - requesting-code-review  # external: ring ecosystem
    - dev-validation  # external: ring ecosystem
  differentiation:
    - name: dev-cycle
      difference: >
        dev-cycle is the 6-gate execution engine. optimus-build is the
        preparation layer that handles task identification, context loading,
        upfront questioning, and codebase exploration BEFORE invoking dev-cycle.
        Use build when you need the full workflow; use dev-cycle directly
        when context is already loaded and the task file path is known.
  sequence:
    after:
      - optimus-plan
      - pre-dev-task-breakdown  # external: ring ecosystem
      - pre-dev-subtask-creation  # external: ring ecosystem
    before:
      - dev-feedback-loop  # external: ring ecosystem
verification:
  manual:
    - All 6 dev-cycle gates passed
    - Code review findings resolved or explicitly skipped
    - User approved final summary before commit
---

# Task Executor

Executes a validated task specification end-to-end: identifies the task, loads context, questions ambiguities upfront, then delegates execution to the dev-cycle skill for the 6-gate pipeline. Commits only after user approval.

---

## Phase 1: Load Context & Question Everything

### Step 1.0: Verify GitHub CLI (HARD BLOCK)

**HARD BLOCK:** Verify GitHub CLI — see AGENTS.md Protocol: GitHub CLI Check.

### Step 1.1: Find and Validate tasks.md

**HARD BLOCK:** Find and validate tasks.md — see AGENTS.md Protocol: tasks.md Validation.

### Step 1.2: Identify Task to Execute

**If the user specified a task ID** (e.g., "execute T-012"):
- Use the provided task ID
- Confirm with the user using `AskUser`: "I'll execute task T-012: [task title]. Correct?"

**If the user did NOT specify a task ID** (e.g., "execute the next task", or just invoked the skill):
1. **Identify the next task ready for implementation:** Read state.json and scan for the first task that:
   - Has status `Validando Spec` (plan completed) or `Em Andamento` (re-execution)
   - Has all dependencies (Depends column from tasks.md) with status `DONE` in state.json (or Depends is `-`)
   - **Version priority:** prefer tasks from the `Ativa` version first. If none found, try `Próxima`. If none found, pick from any version and warn the user: "No eligible tasks in the active version (<name>). Suggesting T-XXX from version '<other>'."
2. **If multiple candidates exist in the same version priority**, pick the one with highest Priority (`Alta` > `Media` > `Baixa`), then lowest ID
3. **Suggest to the user** using `AskUser`: "I identified the next task to execute: T-XXX — [task title]. Is this correct, or would you like to execute a different task?"
4. **If no eligible tasks exist**, ask the user to provide a task ID

**BLOCKING**: Do NOT proceed until the user confirms which task to execute.

### Step 1.2.1: Check Session State

Execute session state protocol — see AGENTS.md Protocol: Session State. Use stage=`build`, status=`Em Andamento`.

**On stage completion** (after Phase 3 post-execution): delete the session file.

### Step 1.3: Validate and Update Task Status

**HARD BLOCK:** This step is mandatory. Do NOT skip it.

1. Read `tasks.md` and find the row for the confirmed task ID
2. Read the task's status from state.json — see AGENTS.md Protocol: State Management.
   - If status is `Validando Spec` → proceed (plan has completed, workspace will be resolved in Step 1.4 via Workspace Auto-Navigation protocol which handles missing worktrees with branch recovery)
   - If status is `Em Andamento` → proceed (re-execution of this stage)
   - If status is `Pendente` → **STOP**: "Task T-XXX is in 'Pendente'. Run plan first."
   - If status is `Validando Impl`, `Revisando PR`, `DONE`, or `Cancelado` → **STOP**: "Task T-XXX is in '<status>'. It has already moved past this stage or was cancelled."
3. **Check dependencies (HARD BLOCK):** Read the Depends column for this task from tasks.md.
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

### Step 1.3.1: Check tasks.md Divergence (warning)

Check tasks.md divergence — see AGENTS.md Protocol: Divergence Warning.

### Step 1.4: Verify Workspace

**HARD BLOCK:** Resolve workspace — see AGENTS.md Protocol: Workspace Auto-Navigation.

Branch-task cross-validation is part of the workspace protocol above.

### Step 1.5: Validate PR Title (if PR exists)

Validate PR title — see AGENTS.md Protocol: PR Title Validation.

### Step 1.6: Discover Project Structure

Before loading docs, discover the project's structure and tooling:

1. **Identify stack:** Check for `go.mod`, `package.json`, `Makefile`, `Cargo.toml`, etc.
2. **Identify test commands:** Look in `Makefile`, `package.json` scripts, or CI config for lint, test, integration test, and E2E test commands.
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

### Step 2.0: Choose Execution Strategy

**Tipo-aware gate selection:** Not all task types need all gates. Before choosing the
execution strategy, check the task's **Tipo** column and adapt:

| Tipo | Skip Gates | Reason |
|------|-----------|--------|
| `Feature`, `Fix`, `Refactor` | None — run all gates | Code changes need full validation |
| `Chore` | Gate 1 (DevOps) may be the primary gate | Depends on task content |
| `Docs` | Gate 1 (DevOps), Gate 2 (SRE), Gate 3 (Testing) | No production code — skip TDD, coverage, observability |
| `Test` | Gate 1 (DevOps), Gate 2 (SRE) | Tests ARE the deliverable — skip DevOps and SRE but run Gate 3 for coverage |

Pass the Tipo so dev-cycle can adapt its gate execution.

### Step 2.1: Execute via dev-cycle

Use the `Skill` tool to load and execute the dev-cycle:

```
Skill("dev-cycle")
```

Pass the tasks file path that contains the confirmed task. The dev-cycle handles:

| Gate | Purpose | Sub-Skill |
|------|---------|-----------|
| Gate 0 | Implementation (TDD) | dev-implementation |
| Gate 1 | DevOps (Docker, IaC) | dev-devops |
| Gate 2 | SRE (observability validation) | dev-sre |
| Gate 3 | Testing (unit tests, coverage ≥ 85%) | dev-testing |
| Gate 4 | Code Review (3+ parallel reviewers) | requesting-code-review |
| Gate 5 | Validation (user approval) | dev-validation |

Provide to dev-cycle:
- The tasks file path and confirmed task ID
- All Ring pre-dev artifacts loaded in Step 1.7
- Codebase patterns found in Step 1.8
- Answers to all questions from Step 1.9
- Any user preferences or constraints mentioned during questioning

While dev-cycle executes:
- The dev-cycle manages its own state persistence, gate transitions, and agent dispatch
- If dev-cycle encounters a blocker or needs user input, it will handle it through its own flow
- Do NOT interfere with dev-cycle's gate execution — let it run its full pipeline

---

## Phase 3: Post-Execution

After implementation completes (via dev-cycle):

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
- dev-cycle gate results (all 6 gates)
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
- If dev-cycle reports a blocker, present it to the user with context from Phase 1
- If you discover a gap in the task spec during Phase 1, ask the user before invoking dev-cycle

### Communication
- Update the todo list at Phase 1 completion and after dev-cycle finishes
- Report dev-cycle gate results as they complete
- Never go silent — if dev-cycle is running, inform the user of progress
- **Next step suggestion:** After the final commit, inform the user: "Implementation
  complete. Next step: run `/optimus-check` to validate this task."

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

All Optimus files live in the `.optimus/` directory at the project root:

```
.optimus/
├── config.json          # versionado — tasksDir, commands
├── tasks.md             # versionado — structural task data (NO status, NO branch)
├── state.json           # gitignored — operational state (status, branch per task)
├── stats.json           # gitignored — stage execution counters per task
├── sessions/            # gitignored — session state for crash recovery
└── reports/             # gitignored — exported reports
```

**Configuration** is stored in `.optimus/config.json`:

```json
{
  "tasksDir": "docs/pre-dev"
}
```

- **`tasksDir`**: Path to the Ring pre-dev artifacts root. Default: `docs/pre-dev`.
  The import and stage agents look for task specs at `<tasksDir>/tasks/` and subtasks
  at `<tasksDir>/subtasks/`.

**Tasks file** is always `.optimus/tasks.md` — not configurable.

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
- Stage agents read and write this file — never tasks.md — for status changes.
- If state.json is lost, status can be reconstructed: task with a worktree = in progress,
  without = Pendente. The agent asks the user to confirm before proceeding.

**Stage execution stats** are stored in `.optimus/stats.json` (gitignored):

```json
{
  "T-001": { "plan_runs": 2, "check_runs": 3, "last_plan": "2025-01-15T10:30:00Z", "last_check": "2025-01-16T14:00:00Z" },
  "T-002": { "plan_runs": 1, "check_runs": 0 }
}
```

- Each key is a task ID. Values track how many times `plan` and `check` executed on the task.
- A high `plan_runs` signals unclear or problematic specs. A high `check_runs` signals
  complex review cycles or specification gaps.
- The file is created on first use by `plan` or `check`. If missing, agents treat all
  counters as 0.
- `report` reads this file to display churn metrics.

Agents resolve paths:
1. **Read `.optimus/config.json`** for `tasksDir`. Fallback: `docs/pre-dev`.
2. **Tasks file:** `.optimus/tasks.md` (fixed path).
3. **If tasks.md not found:** **STOP** and suggest running `import` to create one.

The `.optimus/state.json`, `.optimus/stats.json`, `.optimus/sessions/`, and
`.optimus/reports/` are gitignored (operational/temporary state).
The `.optimus/config.json` and `.optimus/tasks.md` are versioned (structural data).


### Valid Status Values (stored in state.json)

Status lives in `.optimus/state.json`, NOT in tasks.md. A task with no entry in
state.json is implicitly `Pendente`.

| Status | Set by | Meaning |
|--------|--------|---------|
| `Pendente` | Initial (implicit) | Not started — no entry in state.json |
| `Validando Spec` | plan | Spec being validated |
| `Em Andamento` | build | Implementation in progress |
| `Validando Impl` | check | Implementation being reviewed |
| `Revisando PR` | pr-check | PR being reviewed (optional stage) |
| `DONE` | done | Completed |
| `Cancelado` | tasks | Task abandoned, will not be implemented |

**Administrative status operations** (managed by tasks, not by stage agents):
- **Reopen:** `DONE` → `Pendente` (remove entry from state.json) or `Em Andamento` (if worktree exists) — when a bug is found after close. Also accepts `Cancelado` → `Pendente` — when a cancellation decision is reversed.
- **Advance:** move forward one stage — when work was done manually outside the pipeline
- **Demote:** move backward one stage — when rework is needed after review
- **Cancel:** any non-terminal → `Cancelado` — task will not be implemented

These operations require explicit user confirmation.


### Task Spec Resolution

Every task MUST have a Ring pre-dev reference in the `TaskSpec` column. Stage agents
(plan, build, check) resolve the full path as `<tasksDir>/<TaskSpec>` and read the
referenced file for objective, acceptance criteria, and implementation details.

The subtasks directory is derived automatically from the TaskSpec path:
- TaskSpec: `tasks/task_001.md` → Subtasks: `<tasksDir>/subtasks/T-001/`
- The `T-NNN` identifier is extracted from the task spec filename convention

Agents read objective and acceptance criteria directly from the Ring source files.
The tasks.md table only tracks structural data (dependencies, versions, priorities)
— it does NOT duplicate content from Ring.


### Format Validation

Every stage agent (1-5) MUST validate the tasks.md format before operating:
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
format validation PASSES. Stage agents (1-5) MUST check for this condition immediately after
format validation and before task identification. If zero data rows: **STOP** and inform the
user: "No tasks found in tasks.md. Use `/optimus-tasks` to create a task or `/optimus-import`
to import from Ring pre-dev." Do NOT proceed to task identification with an empty table.

**NOTE:** For circular dependency detection (item 13), trace the full dependency chain for
each task. If any task appears twice in the chain, a cycle exists. Report ALL tasks involved
in the cycle so the user can fix it with `/optimus-tasks`.


### Protocol: Active Version Guard

**Referenced by:** all stage agents (1-5)

After the task ID is confirmed and dependencies are validated, check if the task belongs
to the `Ativa` version. If not, present options before proceeding.

1. Read the task's **Version** column from `tasks.md`
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
   - Update the task's Version column in `tasks.md` to the `Ativa` version name
   - Commit:
     ```bash
     git add "$TASKS_FILE"
     COMMIT_MSG_FILE=$(mktemp)
     printf '%s' "chore(tasks): move T-XXX to active version <active_version>" > "$COMMIT_MSG_FILE"
     git commit -F "$COMMIT_MSG_FILE"
     rm -f "$COMMIT_MSG_FILE"
     ```
   - Proceed with the stage

6. **If "Cancel":** **STOP** — do not proceed with the stage

Skills reference this as: "Check active version guard — see AGENTS.md Protocol: Active Version Guard."


### Protocol: Divergence Warning

**Referenced by:** all stage agents (1-5)

Since status and branch data live in state.json (gitignored), tasks.md rarely changes
on feature branches. This protocol detects the uncommon case where tasks.md WAS modified
(e.g., Active Version Guard moved a task).

```bash
DEFAULT_BRANCH=$(git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's@^refs/remotes/origin/@@')
if [ -z "$DEFAULT_BRANCH" ]; then
  DEFAULT_BRANCH=$(git branch --list main master 2>/dev/null | head -1 | tr -d ' *')
fi
if [ -z "$DEFAULT_BRANCH" ]; then
  echo "WARNING: Cannot determine default branch. Skipping divergence check."
  # Skip — this is a warning, not a HARD BLOCK
else
  TASKS_FILE=".optimus/tasks.md"
  git fetch origin "$DEFAULT_BRANCH" --quiet 2>/dev/null
  git diff "origin/$DEFAULT_BRANCH" -- "$TASKS_FILE" 2>/dev/null | head -20
fi
```

- If diff output is non-empty → warn via `AskUser`:
  ```
  tasks.md has diverged between your branch and <default_branch>.
  This may cause merge conflicts when the PR is merged.
  ```
  Options:
  - **Sync now** — run `git merge origin/<default_branch>` to incorporate changes
  - **Continue without syncing** — I'll handle conflicts later
- If diff output is empty → proceed silently (files are in sync)
- **NOTE:** This is a warning, not a HARD BLOCK. The user may choose to continue.

Skills reference this as: "Check tasks.md divergence — see AGENTS.md Protocol: Divergence Warning."


### Protocol: GitHub CLI Check (HARD BLOCK)

**Referenced by:** all stage agents (1-5), tasks, batch

```bash
gh auth status 2>/dev/null
```

If this command fails (exit code != 0), **STOP** immediately:
```
GitHub CLI (gh) is not authenticated. Run `gh auth login` to authenticate before proceeding.
```


### Protocol: Notification Hooks

**Referenced by:** all stage agents (1-5), tasks

After writing a status change to state.json, invoke notification hooks if present.

**IMPORTANT — Capture timing:** Read the current status from state.json and store it as
`OLD_STATUS` BEFORE writing the new status. The sequence is:
1. Read current status: `OLD_STATUS=$(jq -r --arg id "$TASK_ID" '.[$id].status // "Pendente"' "$STATE_FILE")`
2. Write new status to state.json
3. Invoke hooks with `OLD_STATUS` and new status

**IMPORTANT:** Always quote all arguments and sanitize user-derived values to prevent
shell injection. Hook scripts MUST NOT pass their arguments to `eval` or shell
interpretation — treat all arguments as untrusted data.

```bash
_optimus_sanitize() { printf '%s' "$1" | tr -cd '[:alnum:][:space:]-_./:'; }
HOOKS_FILE=$(test -f ./tasks-hooks.sh && echo ./tasks-hooks.sh || (test -f ./docs/tasks-hooks.sh && echo ./docs/tasks-hooks.sh))
if [ -n "$HOOKS_FILE" ] && [ -x "$HOOKS_FILE" ]; then
  "$HOOKS_FILE" "$event" "$(_optimus_sanitize "$task_id")" "$(_optimus_sanitize "$old_status")" "$(_optimus_sanitize "$new_status")" 2>/dev/null &
fi
```

Events and their parameter signatures:

| Event | Parameters | Description |
|-------|-----------|-------------|
| `status-change` | `event task_id old_status new_status` | Any status transition |
| `task-done` | `event task_id old_status "DONE"` | Task marked as done |
| `task-cancelled` | `event task_id old_status "Cancelado"` | Task cancelled |
| `task-blocked` | `event task_id current_status current_status reason` | Dependency check failed (5 args — includes reason) |

When a dependency check fails:
```bash
if [ -n "$HOOKS_FILE" ] && [ -x "$HOOKS_FILE" ]; then
  "$HOOKS_FILE" "task-blocked" "$(_optimus_sanitize "$task_id")" "$(_optimus_sanitize "$current_status")" "$(_optimus_sanitize "$current_status")" "$(_optimus_sanitize "blocked by $dep_id ($dep_status)")" 2>/dev/null &
fi
```

Hooks run in background (`&`) and their failure does NOT block the pipeline.
If `tasks-hooks.sh` does not exist, hooks are silently skipped.

Skills reference this as: "Invoke notification hooks — see AGENTS.md Protocol: Notification Hooks."


### Protocol: PR Title Validation

**Referenced by:** stages 2-5

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

**Referenced by:** plan, build, check, coderabbit-review. Note: done handles pushing inline in its own cleanup phase. pr-check and deep-review have their own push phases.

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


### Protocol: Session State

**Referenced by:** all stage agents (1-5)

Stage agents write a session state file to track progress. This enables resumption
when a session is interrupted (agent crash, user closes terminal, context window limit).

**IMPORTANT — Write timing:** The session file MUST be written **immediately after the
status change in state.json** (before any work begins). This ensures crash recovery has
a record even if the agent fails before producing any output. Do NOT wait until
"key phase transitions" to write the initial session file.

**Session file location:** `.optimus/sessions/session-<task-id>.json` (gitignored).
Each task gets its own file (e.g., `.optimus/sessions/session-T-003.json`).

```json
{
  "task_id": "T-003",
  "stage": "<stage-name>",
  "status": "<stage-output-status>",
  "branch": "feat/t-003-user-auth",
  "started_at": "2025-01-15T10:30:00Z",
  "updated_at": "2025-01-15T11:45:00Z",
  "phase": "Phase 1: Implementation",
  "notes": "Implementation in progress"
}
```

**On stage start (after task ID is known):**

```bash
SESSION_FILE=".optimus/sessions/session-${TASK_ID}.json"
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
  if [ -n "$UPDATED" ]; then
    NOW_EPOCH=$(date +%s)
    UPDATED_EPOCH=$(date -j -f "%Y-%m-%dT%H:%M:%SZ" "$UPDATED" +%s 2>/dev/null || date -d "$UPDATED" +%s 2>/dev/null || echo 0)
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
# Initialize .optimus directory — see AGENTS.md Protocol: Initialize .optimus Directory.
mkdir -p .optimus/sessions .optimus/reports
BRANCH_NAME=$(git branch --show-current 2>/dev/null || echo "detached")
jq -n \
  --arg task_id "${TASK_ID}" --arg stage "<stage-name>" --arg status "<status>" \
  --arg branch "${BRANCH_NAME}" --arg started "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --arg updated "$(date -u +%Y-%m-%dT%H:%M:%SZ)" --arg phase "<current-phase>" \
  --arg notes "<progress>" \
  '{task_id: $task_id, stage: $stage, status: $status, branch: $branch,
    started_at: $started, updated_at: $updated, phase: $phase, notes: $notes}' \
  > ".optimus/sessions/session-${TASK_ID}.json"
```

**On stage completion:** Delete the session file:
```bash
rm -f ".optimus/sessions/session-${TASK_ID}.json"
```

Skills reference this as: "Execute session state protocol from AGENTS.md using stage=`<name>`, status=`<status>`."


### Protocol: State Management

**Referenced by:** all stage agents (1-5), tasks, report, quick-report, import, batch

All status and branch data is stored in `.optimus/state.json` (gitignored).

**Prerequisites:**

```bash
if ! command -v jq >/dev/null 2>&1; then
  echo "ERROR: jq is required for state management but not installed."
  # STOP — do not proceed
fi
```

**Reading state:**

```bash
STATE_FILE=".optimus/state.json"
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
# Initialize .optimus directory — see AGENTS.md Protocol: Initialize .optimus Directory.
STATE_FILE=".optimus/state.json"
if [ ! -f "$STATE_FILE" ]; then
  echo '{}' > "$STATE_FILE"
fi
if [ -z "$TASK_ID" ] || [ -z "$NEW_STATUS" ]; then
  echo "ERROR: Cannot write state — TASK_ID or NEW_STATUS is empty."
  # STOP — do not proceed
fi
UPDATED_AT=$(date -u +%Y-%m-%dT%H:%M:%SZ)
if jq --arg id "$TASK_ID" --arg status "$NEW_STATUS" --arg branch "$BRANCH_NAME" --arg ts "$UPDATED_AT" \
  '.[$id] = {status: $status, branch: $branch, updated_at: $ts}' "$STATE_FILE" > "${STATE_FILE}.tmp"; then
  mv "${STATE_FILE}.tmp" "$STATE_FILE"
else
  rm -f "${STATE_FILE}.tmp"
  echo "ERROR: jq failed to update state.json"
  # STOP — do not proceed
fi
```

**Removing entry (for Pendente reset):**

```bash
STATE_FILE=".optimus/state.json"
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
STATE_FILE=".optimus/state.json"
TASKS_FILE=".optimus/tasks.md"
# Validate state.json if it exists
if [ -f "$STATE_FILE" ] && ! jq empty "$STATE_FILE" 2>/dev/null; then
  echo "WARNING: state.json is corrupted. Treating all tasks as Pendente."
  rm -f "$STATE_FILE"
fi
# Get all task IDs from tasks.md
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

**Referenced by:** plan, build, check

Resolve the full path to a task's Ring pre-dev spec and its subtasks directory:

1. Read the task's `TaskSpec` column from `tasks.md`
2. If `TaskSpec` is `-` → **STOP**: "Task T-XXX has no Ring pre-dev spec. Link one via `/optimus-tasks` or `/optimus-import`."
3. Resolve full path: `TASK_SPEC_PATH = <TASKS_DIR>/<TaskSpec>`
4. **Path traversal validation (HARD BLOCK):** Verify the resolved path stays within the project:
   ```bash
   PROJECT_ROOT=$(git rev-parse --show-toplevel)
   RESOLVED_PATH=$(cd "$PROJECT_ROOT" && realpath -m "${TASKS_DIR}/${TASK_SPEC}" 2>/dev/null \
     || python3 -c "import os,sys; print(os.path.realpath(sys.argv[1]))" "${TASKS_DIR}/${TASK_SPEC}" 2>/dev/null)
   if [ -z "$RESOLVED_PATH" ]; then
     echo "ERROR: Cannot resolve TaskSpec path '${TASKS_DIR}/${TASK_SPEC}' — neither realpath nor python3 available."
     exit 1
   fi
   case "$RESOLVED_PATH" in
     "$PROJECT_ROOT"/*) ;; # OK — within project
     *) echo "ERROR: TaskSpec path traversal detected — resolved path is outside the project root."; exit 1 ;;
   esac
   ```
   Also apply the same validation to `TASKS_DIR` when reading from `.optimus/config.json`:
   ```bash
   TASKS_DIR_RESOLVED=$(cd "$PROJECT_ROOT" && realpath -m "$TASKS_DIR" 2>/dev/null \
     || python3 -c "import os,sys; print(os.path.realpath(sys.argv[1]))" "$TASKS_DIR" 2>/dev/null)
   if [ -z "$TASKS_DIR_RESOLVED" ]; then
     echo "ERROR: Cannot resolve tasksDir path '$TASKS_DIR'."
     exit 1
   fi
   case "$TASKS_DIR_RESOLVED" in
     "$PROJECT_ROOT"/*) ;; # OK — within project
     *) echo "ERROR: tasksDir path traversal detected — '$TASKS_DIR' resolves outside the project root."; exit 1 ;;
   esac
   ```
5. Read the task spec file at `TASK_SPEC_PATH`
6. Derive subtasks directory: if TaskSpec is `tasks/task_001.md`, subtasks are at `<TASKS_DIR>/subtasks/T-001/`
7. If subtasks directory exists, read all `.md` files inside it

Skills reference this as: "Resolve TaskSpec — see AGENTS.md Protocol: TaskSpec Resolution."


### Protocol: Workspace Auto-Navigation (HARD BLOCK)

**Referenced by:** stages 2-5

Execution stages (2-5) resolve the correct workspace automatically. The agent MUST
be in the task's worktree before proceeding with any work.

```bash
DEFAULT_BRANCH=$(git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's@^refs/remotes/origin/@@')
if [ -z "$DEFAULT_BRANCH" ]; then
  DEFAULT_BRANCH=$(git branch --list main master 2>/dev/null | head -1 | tr -d ' *')
fi
CURRENT_BRANCH=$(git branch --show-current 2>/dev/null)
if [ -z "$CURRENT_BRANCH" ]; then
  echo "ERROR: Cannot determine current branch (detached HEAD state). Checkout a branch first."
  # STOP — do not proceed
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
     If the branch exists, create the worktree automatically:
     ```bash
     REPO_NAME=$(basename "$(git rev-parse --show-toplevel)")
     WORKTREE_DIR="../${REPO_NAME}-$(echo <task-id> | tr '[:upper:]' '[:lower:]')-<keywords>"
     git worktree add "$WORKTREE_DIR" "<branch-name>"
     ```
     Then change working directory to the new worktree.

Skills reference this as: "Resolve workspace (HARD BLOCK) — see AGENTS.md Protocol: Workspace Auto-Navigation."


### Protocol: tasks.md Validation (HARD BLOCK)

**Referenced by:** all stage agents (1-5), tasks, batch. Note: resolve performs inline format validation in its own Step 4.2.

Every stage agent MUST validate tasks.md before operating. The full validation rules are
defined in the "Format Validation" section above (items 1-15). This protocol is the
executable version:

1. **Resolve paths:**
   - `TASKS_FILE` is always `.optimus/tasks.md` (fixed path).
   - Read `.optimus/config.json`. If `tasksDir` key exists, use that path. Otherwise, use `docs/pre-dev` (default).
   - Store as `TASKS_FILE` and `TASKS_DIR`.
2. **Find tasks.md:** Check if `TASKS_FILE` exists. If not found, **STOP** and suggest `/optimus-import`.
3. **Validate format:** Execute all 15 validation checks from the "Format Validation" section. If the format marker is missing or any check fails, **STOP** and suggest `/optimus-import`.

**All subsequent references to `tasks.md` in the skill use the resolved `TASKS_FILE` path.
All references to Ring pre-dev artifacts use `TASKS_DIR` as the root** — never hardcoded paths.

Skills reference this as: "Find and validate tasks.md (HARD BLOCK) — see AGENTS.md Protocol: tasks.md Validation."


<!-- INLINE-PROTOCOLS:END -->
