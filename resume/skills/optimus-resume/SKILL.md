---
name: optimus-resume
description: "Resume a task after closing the terminal. Given a task ID (or auto-detecting a single in-progress task), locates or recreates the task's worktree, reports the current status, and offers to invoke the next stage. Read-only on state.json."
trigger: >
  - When user says "resume T-XXX", "retomar T-XXX", or "continuar T-XXX"
  - When user reopens the terminal and wants to return to the task they were working on
  - When user says "where was I?" or "continue last task"
skip_when: >
  - Task is already DONE
  - Task is Cancelado
  - User explicitly wants to start a new task (use /optimus-plan T-XXX instead)
prerequisite: >
  - tasks.md exists and is valid
  - (Recommended) state.json has an entry for the task; otherwise resume falls back to the Pendente flow
NOT_skip_when: >
  - "I remember the path" -- Resume still sets up the Droid session workspace and prints the next recommended command.
  - "I can just cd manually" -- Resume also cross-checks branch/worktree and offers to recreate the worktree if missing.
examples:
  - name: Resume by task ID
    invocation: "Resume T-012"
    expected_flow: >
      1. Validate T-012 in tasks.md
      2. Read status from state.json (e.g., Em Andamento)
      3. Resolve worktree (navigate or recreate from branch)
      4. Print status + suggested "cd <path>"
      5. AskUser: invoke /optimus-build now?
  - name: Resume without ID
    invocation: "/optimus-resume"
    expected_flow: >
      1. List tasks with in-progress status in state.json
      2. If exactly one, use it; if many, AskUser to pick; if none, STOP
      3. Same workspace + next-stage flow as above
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
    - optimus-done
verification:
  manual:
    - Current working directory is the task's worktree (when it exists)
    - Terminal title shows "optimus: RESUME <T-XXX> — <title>"
    - No changes to state.json or tasks.md
---

# Task Resumer

Administrative skill to retake a task after closing the terminal: resolves the worktree,
reports the current status, and offers to invoke the next stage. NEVER changes task status.

**Classification:** Administrative skill — runs on any branch. Does not modify `state.json`,
`tasks.md`, `stats.json`, or session files. Creates a worktree only as a recovery step when
the branch exists but its worktree is missing.

---

## Phase 1: Prerequisites

### Step 1.1: Check jq (HARD BLOCK)

```bash
command -v jq >/dev/null 2>&1
```

If `jq` is not available, **STOP**: "jq is required by /optimus-resume. Install it and retry."

### Step 1.2: Find and Validate tasks.md (HARD BLOCK)

Find and validate tasks.md — see AGENTS.md Protocol: tasks.md Validation.

---

## Phase 2: Identify Task

### Step 2.1: Task ID Provided

If the user supplied an argument matching `T-[0-9]+`, use it as `TASK_ID`.

Verify the task exists in tasks.md:

```bash
grep -E "^\| ${TASK_ID} \|" "$TASKS_FILE" >/dev/null
```

If no match → **STOP**: `"Task ${TASK_ID} not found in tasks.md. Run /optimus-report to see available tasks."`

### Step 2.2: Auto-Detect (no ID provided)

Read `.optimus/state.json` and list tasks whose status is one of
`Validando Spec`, `Em Andamento`, or `Validando Impl` (the in-progress statuses):

```bash
STATE_FILE=".optimus/state.json"
if [ ! -f "$STATE_FILE" ]; then
  echo "ERROR: No state.json found and no task ID provided."
  # STOP
fi
IN_PROGRESS=$(jq -r 'to_entries[]
  | select(.value.status == "Validando Spec" or .value.status == "Em Andamento" or .value.status == "Validando Impl")
  | "\(.key)\t\(.value.status)\t\(.value.branch // "")"' "$STATE_FILE")
```

- **If 0 tasks** → **STOP**: `"No in-progress tasks found. Run /optimus-report to see the project status, or /optimus-plan T-XXX to start a new task."`
- **If exactly 1 task** → use that ID as `TASK_ID` (no AskUser — resume does not change status, so there is no expanded-confirmation requirement).
- **If N tasks** → present via `AskUser` with one option per task (`T-XXX — <title> (<status>)`) plus **Cancel**. Do NOT offer Resume/Start fresh/Continue.

### Step 2.3: Read Task Metadata

From tasks.md, extract the row for `TASK_ID` and capture:

- `TASK_TITLE`
- `TASK_TIPO`
- `TASK_VERSION`

Read operational state from `.optimus/state.json` — see AGENTS.md Protocol: State Management. Capture:

- `TASK_STATUS` (default `Pendente` if no entry)
- `TASK_BRANCH` (empty if no entry)

### Step 2.4: Refuse Terminal Statuses

- If `TASK_STATUS` is `DONE` → **STOP**: `"Task ${TASK_ID} is already DONE. Nothing to resume. To reopen, use /optimus-tasks."`
- If `TASK_STATUS` is `Cancelado` → **STOP**: `"Task ${TASK_ID} is Cancelado. Reopen via /optimus-tasks before resuming."`

---

## Phase 3: Resolve Workspace

### Step 3.1: Derive Expected Branch

Derive the expected branch name — see AGENTS.md Protocol: Branch Name Derivation. Prefer the
`branch` field from state.json; fall back to deriving from Tipo + ID + Title.

### Step 3.2: Look Up Worktree

```bash
WORKTREE_PATH=$(git worktree list --porcelain 2>/dev/null \
  | awk -v id="$(echo "$TASK_ID" | tr '[:upper:]' '[:lower:]')" '
      /^worktree / { wt=$2 }
      /^branch /   { if (tolower(wt) ~ id || tolower($2) ~ id) print wt }
    ' | head -1)
```

If the awk above yields nothing, fall back to a simpler lookup:

```bash
WORKTREE_PATH=$(git worktree list | grep -iF "$TASK_ID" | awk '{print $1}' | head -1)
```

### Step 3.3: Apply Resolution Order

1. **Worktree found** → `cd "$WORKTREE_PATH"` for the rest of the session. Continue to Phase 4.

2. **Worktree missing, branch exists locally** (`git rev-parse --verify "$TASK_BRANCH" >/dev/null 2>&1` succeeds):

   ```bash
   REPO_NAME=$(basename "$(git rev-parse --show-toplevel)")
   SLUG=$(echo "$TASK_ID" | tr '[:upper:]' '[:lower:]')
   WORKTREE_DIR="../${REPO_NAME}-${SLUG}-$(echo "$TASK_TITLE" | tr '[:upper:]' '[:lower:]' \
     | tr -c 'a-z0-9-' '-' | tr -s '-' | sed 's/^-//;s/-$//' | cut -c1-40)"
   git worktree add "$WORKTREE_DIR" "$TASK_BRANCH"
   WORKTREE_PATH="$WORKTREE_DIR"
   ```

   Then `cd "$WORKTREE_PATH"`.

3. **Worktree missing AND branch missing:**
   - **If status is `Pendente` or has no state.json entry:** present via `AskUser`:
     ```
     Task T-XXX has no worktree and no branch yet — it has not been through /optimus-plan.
     Run /optimus-plan T-XXX now?
     ```
     Options:
     - **Yes, invoke /optimus-plan** — delegate to the `optimus-plan` skill via the `Skill` tool (pass `T-XXX` as the task ID).
     - **Cancel** — **STOP** with: `"No workspace for T-XXX. Run /optimus-plan T-XXX when ready."`

   - **If status is in-progress but branch is missing:** this is an inconsistent state.
     **STOP** with a clear message:
     ```
     Inconsistency: T-XXX has status <status> but branch <expected> does not exist.
     Possible recovery:
       - /optimus-plan T-XXX   (recreate workspace)
       - /optimus-tasks        (demote status to Pendente)
     ```

### Step 3.4: Dry-Run Short-Circuit

If the user invoked a dry-run (e.g., "dry-run resume T-XXX", "preview resume"):

- Perform Steps 3.1–3.2 normally (read-only)
- Do NOT run `git worktree add`
- Do NOT `cd`
- Proceed to Phase 4 and label the summary as **(dry-run, no changes applied)**
- Skip Phase 5 entirely

---

## Phase 4: Set Terminal Title and Report

### Step 4.1: Set Terminal Title

Set terminal title — see AGENTS.md Protocol: Terminal Identification. Use stage label `RESUME`:

```bash
printf '\033]0;optimus: RESUME %s — %s\007' "$TASK_ID" "$TASK_TITLE" > /dev/tty 2>/dev/null || true
```

**On exit or after Phase 5 delegates to another stage skill**, restore the title:

```bash
printf '\033]0;\007' > /dev/tty 2>/dev/null || true
```

### Step 4.2: Print Summary

Emit a `<json-render>` block with the resume summary. Include:

- Heading: `Resume T-XXX`
- KeyValue rows: Title, Version, Status, Branch, Worktree
- StatusLine: success — `Workspace ready` (or a warning StatusLine if dry-run)
- Callout with the shell command the user must run in their own terminal to change cwd:
  `cd <absolute-worktree-path>`

**IMPORTANT:** Print the absolute path. The Droid session's internal `cd` does NOT change
the user's interactive shell cwd — the user must run `cd` themselves to have their shell
match. Subsequent tool calls in this Droid session will still use the internal cwd.

### Step 4.3: Next-Stage Recommendation

Map current status to the recommended next command:

| Current status     | Next recommended                               |
|--------------------|------------------------------------------------|
| `Validando Spec`   | `/optimus-build`                               |
| `Em Andamento`     | `/optimus-review` (or re-run `/optimus-build`) |
| `Validando Impl`   | `/optimus-done` (or re-run `/optimus-review`)  |

Show this in the summary.

---

## Phase 5: Offer Next Stage

Ask the user via `AskUser`:

```
Next step for T-XXX (<status>):
```

Options depend on status:

- `Validando Spec`: **Run /optimus-build** / **Skip**
- `Em Andamento`: **Run /optimus-review** / **Re-run /optimus-build** / **Skip**
- `Validando Impl`: **Run /optimus-done** / **Re-run /optimus-review** / **Skip**

**If the user picks a stage:** delegate to the corresponding skill via the `Skill` tool
(e.g., `optimus-build`). The target stage skill will run its normal validation and
auto-navigation — resume does NOT bypass its predecessor checks.

**If the user picks Skip:** inform them the workspace is ready and they can run the
recommended command whenever they like.

**Skip the whole Phase 5 step** when running in dry-run mode.

---

## Rules

- **Admin skill** — runs on any branch, does not alter task status.
- NEVER writes to `state.json`, `stats.json`, `tasks.md`, or `.optimus/sessions/session-T-XXX.json`.
- Creates a worktree ONLY in the recovery path (Step 3.3 case 2). Never creates branches.
- Does NOT offer `Resume / Start fresh / Continue` prompts (coherent with `/optimus-done`).
- Does NOT invoke another stage automatically — only when the user explicitly picks it in Phase 5.
- Respects dry-run mode: no worktree creation, no delegation to other skills.
- Does NOT run `make lint` / `make test` — verification is the responsibility of the target stage.
- When delegating to another skill, pass `TASK_ID` explicitly so the delegate skips its own auto-detect.

### Anti-rationalization

The agent MUST NOT use these excuses to skip or reorder steps:

- "I know the worktree path, I'll just cd manually" — the skill still needs to validate the task and render the summary.
- "The user clearly wants /optimus-build, let me just run it" — wait for the Phase 5 AskUser decision.
- "state.json is missing, let me infer from git worktree list" — that triggers the reconciliation guidance in State Management, not a silent recovery.
- "The branch exists but the name differs from the derivation, close enough" — prefer the state.json branch field; do not use fuzzy matches silently.

<!-- INLINE-PROTOCOLS:START -->
## Shared Protocols (from AGENTS.md)

The following protocols are referenced by this skill. They are
extracted from the Optimus AGENTS.md to make this plugin self-contained.

### File Location

All Optimus files live in the `.optimus/` directory at the project root:

```
.optimus/
├── config.json          # versionado — tasksDir
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
| `Validando Impl` | review | Implementation being reviewed |
| `DONE` | done | Completed |
| `Cancelado` | tasks, done | Task abandoned, will not be implemented |

**Administrative status operations** (managed by tasks, not by stage agents):
- **Reopen:** `DONE` → `Pendente` (remove entry from state.json) or `Em Andamento` (if worktree exists) — when a bug is found after close. Also accepts `Cancelado` → `Pendente` — when a cancellation decision is reversed.
- **Advance:** move forward one stage — when work was done manually outside the pipeline
- **Demote:** move backward one stage — when rework is needed after review
- **Cancel:** any non-terminal → `Cancelado` — task will not be implemented

These operations require explicit user confirmation.


### Format Validation

Every stage agent (1-4) MUST validate the tasks.md format before operating:
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
user: "No tasks found in tasks.md. Use `/optimus-tasks` to create a task or `/optimus-import`
to import from Ring pre-dev." Do NOT proceed to task identification with an empty table.

**NOTE:** For circular dependency detection (item 13), trace the full dependency chain for
each task. If any task appears twice in the chain, a cycle exists. Report ALL tasks involved
in the cycle so the user can fix it with `/optimus-tasks`.


### Protocol: Branch Name Derivation

**Referenced by:** plan, build, review, pr-check, done (workspace auto-navigation)

Branch names are derived deterministically from the task's structural data in tasks.md.
They are NOT stored in tasks.md — they are stored in state.json for quick reference
and can always be re-derived.

**Derivation rule:**

```
<tipo-prefix>/<task-id-lowercase>-<keywords>
```

Where:
- `<tipo-prefix>` is mapped from the Tipo column: Feature→`feat`, Fix→`fix`,
  Refactor→`refactor`, Chore→`chore`, Docs→`docs`, Test→`test`
- `<task-id-lowercase>` is the task ID in lowercase (e.g., `t-003`)
- `<keywords>` are 2-4 lowercase words from the Title, stripping articles,
  prepositions, and generic words (implement, add, create, update)

**Sanitization (applied to keywords before constructing branch name):**
1. Convert to lowercase
2. Replace non-alphanumeric characters (except hyphens) with hyphens
3. Collapse consecutive hyphens to a single hyphen
4. Remove leading/trailing hyphens from each keyword
5. Truncate the full branch name to 100 characters

**Examples:**
- T-003 "User Auth JWT" (Feature) → `feat/t-003-user-auth-jwt`
- T-007 "Duplicate Login" (Fix) → `fix/t-007-duplicate-login`
- T-012 "Extract Middleware" (Refactor) → `refactor/t-012-extract-middleware`
- T-015 "User Auth: JWT/OAuth2 Support" (Feature) → `feat/t-015-user-auth-jwt-oauth2-support`

**Resolution order when looking for a task's branch:**
1. Read `branch` from state.json (fastest)
2. Search by task ID: `git branch --list "*<task-id>*"` or `git worktree list | grep -iF "<task-id>"`
3. Derive from Tipo + ID + Title (always works)

Skills reference this as: "Derive branch name — see AGENTS.md Protocol: Branch Name Derivation."


### Protocol: State Management

**Referenced by:** all stage agents (1-4), tasks, report, quick-report, import, batch

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
# One-time migration: Revisando PR → Validando Impl (status removed)
if [ -f "$STATE_FILE" ] && jq -e 'to_entries[] | select(.value.status == "Revisando PR")' "$STATE_FILE" >/dev/null 2>&1; then
  jq 'with_entries(if .value.status == "Revisando PR" then .value.status = "Validando Impl" else . end)' "$STATE_FILE" > "${STATE_FILE}.tmp" \
    && mv "${STATE_FILE}.tmp" "$STATE_FILE"
  echo "NOTE: Migrated tasks from 'Revisando PR' to 'Validando Impl' (status removed in this version)."
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
  if jq empty "${STATE_FILE}.tmp" 2>/dev/null; then
    mv "${STATE_FILE}.tmp" "$STATE_FILE"
  else
    rm -f "${STATE_FILE}.tmp"
    echo "ERROR: jq produced invalid JSON — state.json unchanged"
    # STOP — do not proceed
  fi
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


### Protocol: Terminal Identification

**Referenced by:** all stage agents (1-4), batch

After the task ID is identified and confirmed, set the terminal title to show the
current stage and task. This allows users running multiple agents in parallel terminals
to identify each terminal at a glance.

**Set title (after task ID is known):**

```bash
printf '\033]0;optimus: %s %s — %s\007' "<STAGE>" "$TASK_ID" "$TASK_TITLE" > /dev/tty 2>/dev/null || true
```

Example output in terminal tab: `optimus: REVIEW T-003 — User Auth JWT`

**Why `/dev/tty`:** The Execute tool captures stdout, so escape sequences written to
stdout never reach the terminal emulator. Redirecting to `/dev/tty` writes directly to
the controlling terminal, bypassing capture. The `2>/dev/null || true` ensures silent
failure in environments without a TTY (Docker, CI).

**Restore title (at stage completion or exit):**

```bash
printf '\033]0;\007' > /dev/tty 2>/dev/null || true
```

**NOTE:** This uses the standard OSC (Operating System Command) escape sequence
supported by iTerm2, Terminal.app, VS Code terminal, tmux, and most modern terminals.
The sequence is silent — it produces no visible output.

Skills reference this as: "Set terminal title — see AGENTS.md Protocol: Terminal Identification."


### Protocol: tasks.md Validation (HARD BLOCK)

**Referenced by:** all stage agents (1-4), tasks, batch. Note: resolve performs inline format validation in its own Step 4.2.

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
