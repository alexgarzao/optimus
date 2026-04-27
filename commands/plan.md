---
description: Stage 1 of the task lifecycle. Validates a task specification against project docs BEFORE code generation begins. Catches gaps, contradictions, ambiguities, test coverage holes, and observability issues. Creates workspace (branch/worktree). Analysis only -- does not generate code.
---

# Pre-Task Validator

Validates a task specification against project docs BEFORE code generation begins.
Catches gaps, contradictions, and ambiguities that would cause rework.

---

## Phase 1: Discover and Load Context

### Step 1.0: Verify GitHub CLI (HARD BLOCK)

**HARD BLOCK:** Verify GitHub CLI — see AGENTS.md Protocol: GitHub CLI Check.

**Why check here:** Stage-1 dispatches ring droids (Step 2.4) that may use `gh`, and
subsequent stages (2-5) all require `gh`. Failing early prevents the user from completing
spec validation only to discover `gh` is not set up when they try to run Stage-2.

### Step 1.0.1: Resolve and Validate optimus-tasks.md

**HARD BLOCK:** Find and validate optimus-tasks.md — see AGENTS.md Protocol: optimus-tasks.md Validation.

### Step 1.0.2: Identify Task to Validate

**If the user specified a task ID** (e.g., "validate T-006"):
- Use the provided task ID
- Confirm with the user using `AskUser`: "I'll validate task T-006: [task title]. Correct?"

**If the user did NOT specify a task ID** (e.g., "validate the next task", or just invoked the skill):
1. **Identify the next eligible task:** Read state.json and scan for the first task that:
   - Has status `Pendente` (no entry in state.json) or `Validando Spec` (re-execution)
   - Has all dependencies (Depends column from optimus-tasks.md) with status `DONE` in state.json (or Depends is `-`)
   - **Version priority:** prefer tasks from the `Ativa` version first. If none found, try `Próxima`. If none found, pick from any version and warn the user: "No eligible tasks in the active version (<name>). Suggesting T-XXX from version '<other>'."
2. **If multiple candidates exist in the same version priority**, pick the one with highest Priority (`Alta` > `Media` > `Baixa`), then lowest ID
3. **Suggest to the user** using `AskUser`: "I identified the next task to validate: T-XXX — [task title]. Is this correct, or would you like to validate a different task?"
4. **If no eligible tasks exist**, ask the user to provide a task ID

**BLOCKING**: Do NOT proceed until the user confirms which task to validate.

### Step 1.0.2.1: Check Session State

Execute session state protocol — see AGENTS.md Protocol: Session State. Use stage=`plan`, status=`Validando Spec`.

**On stage completion** (after Phase 7 Re-run Guard resolves to advance): delete the session file and restore terminal title.

### Step 1.0.2.2: Set Terminal Title

**CRITICAL:** Set the terminal title so the user can identify this terminal at a glance.

**First, parse `TASK_TITLE` from optimus-tasks.md** — the title is interpolated
into the terminal title below, and parsing it lazily (after the title is set)
results in `optimus: PLAN T-XXX — ` with an empty trailing dash:

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

Then execute the title-setter NOW. Set terminal title — see AGENTS.md Protocol: Terminal Identification. Use stage label `PLAN`:

```bash
_optimus_set_title "optimus: PLAN $TASK_ID — $TASK_TITLE"
```

**On stage completion or exit**, restore the title:

```bash
_optimus_set_title ""
```

### Step 1.0.3: Validate Task Status (DO NOT modify yet)

**HARD BLOCK:** This step is mandatory. Do NOT skip it.

1. Read `optimus-tasks.md` and find the row for the confirmed task ID
2. Read the task's status from state.json — see AGENTS.md Protocol: State Management.
   - If status is `Pendente` (or no entry) → proceed
   - If status is `Validando Spec` → proceed (re-execution of this stage)
   - If status is anything else → **STOP** and tell the user:
     ```
     Task T-XXX is in '<current_status>'. To run plan,
     it must be in 'Pendente' or 'Validando Spec'. This task has already moved past this stage.
     ```
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
   - **If status will change** (current status is NOT `Validando Spec`) AND the user did NOT specify the task ID explicitly (auto-detect):
     - Present to the user via `AskUser`:
       ```
       I'm about to change task T-XXX status from '<current>' to 'Validando Spec'.

       **T-XXX: [title]**
       **Version:** [version from table]

       Confirm status change?
       ```
     - **BLOCKING:** Do NOT change status until the user confirms
   - **If re-execution** (status is already `Validando Spec`) OR the user specified the task ID explicitly:
     - Skip expanded confirmation (user already has context)

**Anti-rationalization:** This agent accepts tasks in `Pendente` or `Validando Spec` (re-execution) status. If a task is in any other status (`Em Andamento`, `Validando Impl`, `DONE`, `Cancelado`), refuse to proceed — the task has already passed this stage or was cancelled.

### Step 1.0.4: Detect and Clean Abandoned Workspaces

**ALWAYS run this step** — regardless of task status. This detects orphaned workspaces
from a previous run that was interrupted (crash, user closed terminal, etc.).

1. Check if any branch or worktree already exists for this task. Use anchored
   matches to avoid substring false positives (`T-1` against `T-10`/`T-100`).
   Prefer state.json's `branch` field when present:
   ```bash
   # Source-of-truth: branch from state.json (fastest, set by previous plan run).
   TASK_BRANCH=$(jq -r --arg id "$TASK_ID" '.[$id].branch // ""' \
     "${MAIN_WORKTREE}/.optimus/state.json" 2>/dev/null)

   # Fallback: anchored kebab-cased search (avoids T-1 vs T-10 collision).
   TASK_KEBAB="-$(echo "$TASK_ID" | tr '[:upper:]' '[:lower:]')-"
   if [ -z "$TASK_BRANCH" ]; then
     TASK_BRANCH=$(git branch --list "*${TASK_KEBAB#-}*" 2>/dev/null | head -1 | tr -d ' *')
   fi
   WORKTREE_PATH=""
   if [ -n "$TASK_BRANCH" ]; then
     WORKTREE_PATH=$(git worktree list --porcelain 2>/dev/null | awk -v br="refs/heads/$TASK_BRANCH" '
       /^worktree / { path=$2 }
       /^branch /   { if ($2 == br) { print path; exit } }
     ')
   fi
   if [ -z "$WORKTREE_PATH" ]; then
     WORKTREE_PATH=$(git worktree list --porcelain 2>/dev/null \
       | awk -v anchor="$TASK_KEBAB" '/^worktree / { path=$2; if (index(tolower(path), anchor) > 0) { print path; exit } }')
   fi
   ```
2. The state.json read above already covers the "Also read the `branch` field
   from state.json if available" step.
3. **If a branch or worktree exists:**
   - Ask via `AskUser`:
     ```
     Task T-XXX has an existing workspace from a previous run:
       Branch: <branch>
       Worktree: <path> (if applicable)
       Status in state.json: <current-status>

     What should I do?
     ```
     Options:
     - **Reuse** — switch to the existing workspace and continue from where it left off
     - **Clean and recreate** — delete the old workspace and create a fresh one
     - **Clean and reset to Pendente** — delete the workspace and reset the task (abandon)

   If the user chooses **Reuse**:
   - If a worktree exists, change working directory to it and proceed to Step 1.0.6
   - If only a branch exists (no worktree), create a worktree for it and proceed to Step 1.0.6

   If the user chooses **Clean and recreate**:
   1. Remove worktree if exists: `git worktree remove <path>`
   2. Delete branch: `git branch -D <branch>` and `git push origin --delete <branch>` (if pushed)
   3. Continue to Step 1.0.5 (will create fresh workspace)

   If the user chooses **Clean and reset to Pendente**:
   1. Remove worktree if exists: `git worktree remove <path>`
   2. Delete branch: `git branch -D <branch>` and `git push origin --delete <branch>` (if pushed)
   3. Remove the task entry from state.json (resets to Pendente)
   4. **STOP** — task is back to Pendente, user can re-run stage-1 when ready

4. **If no branch or worktree exists** → proceed to Step 1.0.4.5

### Step 1.0.4.5: Resolve Missing Spec

Before reserving the task and creating the workspace, detect and self-heal a missing spec.
This runs BEFORE Step 1.0.5 so that a Cancel here leaves the task untouched (no orphan
workspace, no `Validando Spec` status leak).

> Note: This prompt offers Cancel (not Defer) because plan needs the spec to do its work. To create a task without a spec, use `/optimus:tasks` and pick Defer.

1. Parse `optimus-tasks.md` and read the task row's `TaskSpec` column.
2. If `TaskSpec` is NOT `-`, skip this step (proceed to Step 1.0.5).
3. If `TaskSpec` is `-`, ask via `AskUser`:

   ```
   [topic] (1/1) Task T-XXX has no Ring pre-dev spec. How should I proceed?
   ```

   Options:
   - **Generate via Ring** (recommended) — invoke `ring:pre-dev-feature`
   - **Link existing spec** — search `<TASKS_DIR>/tasks/*.md`
   - **Cancel** — abort plan

4. **If "Generate via Ring":**
   1. Verify `ring:pre-dev-feature` is available. If unavailable → fall back to "Link existing spec" automatically and warn the user.
   2. Invoke `ring:pre-dev-feature` via the `Skill` tool. The Skill tool has no argument channel — state the task title and tipo in conversation context immediately before the invocation (e.g., "Generating spec for T-XXX: <title> (Tipo: <tipo>)"). Ring will read these from context.
   3. **If Ring fails or returns no spec path:**
      - Warn the user: "Ring failed to generate the spec: <error>."
      - Re-prompt with `Link existing spec` / `Cancel`. Do NOT silently fall through.
      - If user picks Cancel → STOP — "Plan cancelled — task spec required."
   4. **If Ring succeeds:**
      - Capture the generated spec file path (relative to `<TASKS_DIR>`). Save in a variable `SPEC_PATH`.
      - Update the task's `TaskSpec` column in `optimus-tasks.md`.
   5. **Re-validate** optimus-tasks.md — see AGENTS.md Protocol: optimus-tasks.md Validation.
      - If validation fails:
        a. Revert the in-memory edit to the TaskSpec column.
        b. Remove the spec file Ring just created at `<TASKS_DIR>/<SPEC_PATH>` (rollback Ring's side effect).
        c. STOP and report the validation error.
   6. Commit the TaskSpec update:
      ```bash
      tasks_git add "$TASKS_GIT_REL"
      COMMIT_MSG_FILE=$(mktemp -t optimus.XXXXXX) || { echo "ERROR: mktemp failed" >&2; exit 1; }
      chmod 600 "$COMMIT_MSG_FILE"
      printf '%s' "chore(tasks): heal TaskSpec for T-XXX (self-heal)" > "$COMMIT_MSG_FILE"
      tasks_git commit -F "$COMMIT_MSG_FILE"
      rm -f "$COMMIT_MSG_FILE"
      ```

5. **If "Link existing spec":**
   1. Glob `<TASKS_DIR>/tasks/*.md`. Rank candidates by keyword overlap with the task title.
   2. Present the top 5 matches via `AskUser`; user picks one or types a custom relative path under `<TASKS_DIR>/tasks/`.
   3. **HARD BLOCK** — Validate the chosen path: (a) exists, (b) is a regular file (NOT a symlink), (c) resolves inside `<TASKS_DIR>` with no intermediate symlink components, (d) contains no pipe (`|`), control characters, newlines. Apply the realpath/case-glob/symlink rejection block from AGENTS.md Protocol: TaskSpec Resolution. If validation fails, do NOT write to optimus-tasks.md; loop back to the picker.
   4. Update the task's `TaskSpec` column in `optimus-tasks.md`.
   5. **Re-validate** optimus-tasks.md — see AGENTS.md Protocol: optimus-tasks.md Validation. If validation fails, abort and revert the in-memory edit; do not commit.
   6. Commit the TaskSpec update:
      ```bash
      tasks_git add "$TASKS_GIT_REL"
      COMMIT_MSG_FILE=$(mktemp -t optimus.XXXXXX) || { echo "ERROR: mktemp failed" >&2; exit 1; }
      chmod 600 "$COMMIT_MSG_FILE"
      printf '%s' "chore(tasks): heal TaskSpec for T-XXX (self-heal)" > "$COMMIT_MSG_FILE"
      tasks_git commit -F "$COMMIT_MSG_FILE"
      rm -f "$COMMIT_MSG_FILE"
      ```

6. **If "Cancel":** **STOP** — "Plan cancelled — task spec required."

7. Post-condition: `TaskSpec` is now a valid relative path (not `-`). Proceed to Step 1.0.5.

### Step 1.0.5: Reserve Task and Create Workspace

**Canonical worktree path** — see AGENTS.md Protocol: Worktree Location.

Follow shell safety guidelines — see AGENTS.md Protocol: Shell Safety Guidelines.

**If already on a feature branch** (not default/main/master): skip to Step 1.0.6
(check divergence — the task was already reserved in a previous run or by the user manually).

**If on the default branch:**

1. **Derive branch name** — see AGENTS.md Protocol: Branch Name Derivation.

2. **Update state.json:**
   Write status `Validando Spec` and the derived branch name to state.json — see
   AGENTS.md Protocol: State Management.

3. **Invoke notification hooks** (event=`status-change`) — see AGENTS.md Protocol: Notification Hooks.

4. **Create worktree:**
   ```bash
   # Resolve main worktree first — see AGENTS.md Protocol: Resolve Main Worktree Path.
   # Reuse cached MAIN_WORKTREE if caller already resolved (per Protocol: Resolve Main Worktree Path).
   if [ -z "${MAIN_WORKTREE:-}" ]; then
     MAIN_WORKTREE="$(git worktree list --porcelain 2>/dev/null | awk '/^worktree / {print $2; exit}')"
   fi
   MAIN_WORKTREE="${MAIN_WORKTREE:?MAIN_WORKTREE not resolved — not in a git repository}"

   # BRANCH_NAME must be a real branch name (substituted from Protocol: Branch Name Derivation), not the placeholder.
   BRANCH_NAME="<tipo-prefix>/<task-id>-<keywords>"
   # Path-traversal guard (defense in depth).
   case "$BRANCH_NAME" in
     *..*|/*) echo "ERROR: refusing unsafe branch '$BRANCH_NAME'." >&2; exit 1 ;;
   esac
   WORKTREE_DIR="${MAIN_WORKTREE}/.worktrees/${BRANCH_NAME}"
   ```
   **Pre-check:** If `WORKTREE_DIR` already exists but is not a git worktree, ask via
   `AskUser`: "Directory `<path>` already exists but is not a git worktree."
   Options: Remove and create worktree / Rename existing directory / Cancel.

   ```bash
   # Pre-check: directory exists but is not a git worktree?
   if [ -e "$WORKTREE_DIR" ] && ! git -C "$WORKTREE_DIR" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
     echo "WARNING: $WORKTREE_DIR exists but is not a git worktree." >&2
     # Present AskUser: Remove and create / Rename existing / Cancel
     # (Agent: invoke the AskUser flow with these 3 options. If user picks Remove,
     # rm -rf "$WORKTREE_DIR". If Rename, propose mv "$WORKTREE_DIR" "${WORKTREE_DIR}.bak-$(date +%s)".
     # If Cancel, exit 1.)
   fi
   if ! git worktree add "$WORKTREE_DIR" -b "${BRANCH_NAME}"; then
     echo "ERROR: 'git worktree add $WORKTREE_DIR' failed (branch already checked out, dir collision, or filesystem error)." >&2
     # Rollback: state.json reservation is removed in Step 5 below.
     exit 1
   fi
   ```
   Then change working directory to the new worktree path for all subsequent steps.

   *Optional:* Configure your editor to exclude `.worktrees/` (see Protocol: Worktree Location → IDE exclusion).

5. **Rollback on failure:** If worktree creation fails:
   - Remove the entry from state.json
   - **STOP** and report the error to the user

**BLOCKING**: Do NOT proceed until the worktree is created.

### Step 1.0.6: Check optimus-tasks.md Divergence (warning)

Check optimus-tasks.md divergence — see AGENTS.md Protocol: Divergence Warning.

### Step 1.0.7: Increment Stage Stats

Increment stage stats — see AGENTS.md Protocol: Increment Stage Stats. Use counter=`plan_runs`, timestamp=`last_plan`.

### Step 1.1: Discover Project Structure

Before loading docs, discover the project's structure:

1. **Identify stack:** Check for `go.mod`, `package.json`, `Makefile`, `Cargo.toml`, etc.
2. **Identify test commands:** Look in `Makefile`, `package.json` scripts, or CI config for lint, test, and integration test commands. These are needed for DoD validation.
3. **Identify project rules and AI instructions (MANDATORY):** Execute project rules discovery — see AGENTS.md Protocol: Project Rules Discovery.

4. **Identify reference docs:** Look for task specs, API design, data model, architecture docs, business requirements, and dependency maps.
5. **Identify doc hierarchy:** Determine the source-of-truth ordering for conflicting docs (typically: project rules/AI instructions > API design > data model > architecture > business requirements > task specs).

### Step 1.2: Load Documents

Resolve TaskSpec — see AGENTS.md Protocol: TaskSpec Resolution. Load the Ring pre-dev
task spec for objective, acceptance criteria, API contracts, and data model.

Also load other project reference docs:
- API contracts
- DB schema / data model
- Technical architecture
- Business requirements
- Coding standards (source of truth)
- Dependency relationships

Ring pre-dev artifacts are the primary specification source.

### Step 1.3: Verify Existing Code

Check the codebase for:
- Are dependencies (required tasks) actually implemented?
- Do shared packages/interfaces referenced exist?
- Does the DB schema match the data model doc?
- Are there existing patterns to follow?

---

## Validation Dimensions

### 1. Spec Completeness
- Does the task have ALL required sections? (Scope, Success Criteria, Testing Strategy, Dependencies, Definition of Done)
- Are all fields/entities referenced actually defined in the data model?
- Are all endpoints referenced actually defined in the API contracts?
- Are all business rules explicitly stated (not implied)?

### 2. Cross-Doc Consistency
Check for contradictions BETWEEN docs using the discovered source-of-truth hierarchy:

- **Task spec vs API contracts**: HTTP methods, request/response formats, error codes, query params, field names
- **Task spec vs data model**: Column types, constraints (lengths, nullability, uniqueness), relationships
- **Task spec vs architecture**: Patterns, libraries, configuration values
- **Task spec vs business requirements**: Feature scope, user stories, acceptance criteria
- **API contracts vs data model**: Field names (API naming vs DB naming), types, nullable fields

### 3. Dependency Readiness
- Are ALL "Requires" tasks actually implemented and merged?
- Are DB tables/migrations that this task needs already created?
- Are shared packages/middleware this task depends on available?
- Are there circular dependencies with other tasks?

### 4. API Contract Completeness
For each endpoint in the task:
- Request format fully defined? (body, query params, path params, headers)
- Response format fully defined? (success + all error codes with HTTP status)
- Pagination format matches global convention?
- Authentication/authorization specified?
- Edge cases: empty body, missing fields, invalid types, boundary values

### 5. Test Coverage Gaps (MANDATORY)

This section is MANDATORY. You MUST analyze ALL three test types below and for EACH type either:
- List specific missing scenarios as gaps, OR
- Explicitly state "NONE — all code paths covered" with a brief justification listing the paths verified.

Skipping a test type or leaving it empty is NOT allowed.

**"NONE" is a load-bearing claim, not a shortcut.** "NONE" is acceptable
only when BOTH of the following hold:

  (a) the verified function / method / flow list under this test type is
      **non-empty** (you actually enumerated each unit/integration/e2e
      target), AND
  (b) for **each** verified item, you cite the **test name** (e.g.,
      `TestUserService_Create_ReturnsConflictWhenEmailExists`) and the
      **specific scenarios** that test covers.

Phrases like "Existing tests cover this", "Unit tests are adequate", or
"Standard coverage applies" are NOT valid justifications — name the
tests. If you cannot name them, the correct answer is to list the
missing scenarios as gaps, not to claim NONE.

#### 5a. Unit Test Gaps (REQUIRED)
For EACH function/method that the task will create or modify, verify:
- [ ] Happy path covered?
- [ ] Each validation rule has a corresponding test?
- [ ] Each error return path has a corresponding test?
- [ ] Boundary values tested (min, max, empty, nil, zero)?
- [ ] Each branch/condition in business logic has a test?

Enumerate every function and check each bullet. If ANY bullet is not covered, add it as a gap.

#### 5b. Integration Test Gaps (REQUIRED)
For EACH database operation that the task will create or modify, verify:
- [ ] CRUD cycle covered?
- [ ] Constraint violations tested (unique, FK, not null)?
- [ ] Data isolation tested (user A cannot see user B's data)?
- [ ] Pagination with real DB (first page, last page, beyond last page)?
- [ ] Sort/filter with real DB (each filter param, combined filters)?
- [ ] Edge cases: empty result set, single result, exact page boundary?

#### 5c. E2E Test Gaps (REQUIRED)
For EACH user-facing flow the task introduces, verify:
- [ ] Happy path covered (full flow from start to completion)?
- [ ] Each form field validation has a test?
- [ ] Error states covered (server error, network timeout, 4xx responses)?
- [ ] Navigation flows covered (create -> list -> detail -> edit -> delete)?
- [ ] Empty state (zero records) has a test?
- [ ] URL state persistence (query params survive refresh)?

#### 5d. Cross-Cutting Scenarios (REQUIRED)
For EACH of the following, verify if it applies to the task:
- [ ] Concurrent modifications (optimistic locking needed?)
- [ ] Large datasets (pagination boundary: last page, beyond last page)
- [ ] Special characters in text fields (unicode, injection via parameterized queries, XSS via framework escaping)
- [ ] Input truncation (fields exceeding length limits)
- [ ] Timezone handling (if dates are involved)

### 6. Definition of Done (DoD) Validation
Verify the task has a Definition of Done section with ALL required items:

**Required items (every task MUST have):**
- [ ] Code reviewed (specify reviewers as applicable)
- [ ] Tests passing with coverage threshold
- [ ] All verification commands passing (lint, unit tests, integration tests)
- [ ] Documentation updated (if applicable)

**Validate DoD quality:**
- Are coverage thresholds specified and realistic?
- Does the DoD explicitly list the project's verification commands?
- Are reviewer roles appropriate for the task type?
- Does the DoD include ALL deliverables?
- Are there measurable criteria (not vague like "works correctly")?
- Does the DoD match the task's Testing Strategy?
- Compare with DoD from completed tasks to ensure consistency

### 7. Observability Gaps

Analyze whether the task has adequate logging and metrics coverage. Check existing codebase patterns and verify:

#### 7a. Logging Gaps (REQUIRED)
For EACH new component the task creates:
- [ ] Success operations logged? (with entity IDs, operation name)
- [ ] Error paths logged? (with error message, context IDs)
- [ ] Security-relevant events logged? (auth failures, rate limits, suspicious input)
- [ ] Async/background operations logged? (start/end with duration, items processed)
- [ ] Sensitive data excluded from logs? (no passwords, tokens, PII)

Cross-cutting:
- [ ] Slow query logging exists?
- [ ] Server lifecycle logging exists?
- [ ] External service calls logged?

#### 7b. Metrics Gaps (REQUIRED)
Check if the task should emit structured fields that enable metrics:
- [ ] Operation counters?
- [ ] Duration tracking for batch/external operations?
- [ ] Error counters by type?
- [ ] Business KPIs relevant to the feature?

### 8. Implementability Check
- Can a developer implement each item WITHOUT asking questions?
- Are UI wireframes/designs referenced or described enough?
- Are external API contracts documented?
- Are feature flags or gradual rollout needed?
- Are there performance requirements with measurable thresholds?

---

## Phase 2: Execution

### Step 2.1: Cross-Reference
For EACH item in the task spec, verify it exists and is consistent in the reference docs.
Flag any item that:
- Exists in the task spec but NOT in API contracts or data model
- Has different values between docs (field type, HTTP method, error code)
- References something that doesn't exist yet (table, endpoint, component)

### Step 2.2: Analyze Test Gaps (MANDATORY — do NOT skip)
For EACH test type (unit, integration, E2E):
1. List every function/method/flow the task will create or modify
2. For each one, check every bullet from Dimension 5
3. For each uncovered bullet, add a row to the Test Coverage Gaps table
4. If all bullets are covered, write "NONE — verified: [list functions/flows checked]"

You MUST produce output for all 4 sub-sections (5a, 5b, 5c, 5d).

### Step 2.2.1: Cross-Reference Test Gaps with Future Tasks (MANDATORY)
For EACH test gap identified in Step 2.2:
1. **Search future tasks:** Scan the tasks file for any task that explicitly covers the missing test scenario (look for test-related acceptance criteria, testing strategy sections, or test IDs that match the gap)
2. **Classify each gap:**
   - **NOT PLANNED** — no future task covers this test. Flag as a gap in the current task.
   - **PLANNED IN T-XXX** — a future task explicitly includes this test. Note which task and what it covers.
3. **For gaps planned in future tasks**, evaluate and present to the user:
   - **Which future task** covers it (task ID and title)
   - **Opinion on timing:** Should the test be created now or is it reasonable to defer? Consider:
     - Does the current task introduce the code path that needs testing? If yes, recommend testing now.
     - Is the future task a dedicated testing task? If yes, deferring may be acceptable.
     - Does the gap create a risk window (untested code in production between tasks)?
   - **Ask the user** via `AskUser`: "Test gap [description] is planned for T-XXX. I recommend [now/deferring] because [reason]. Do you want to add this test to the current task?"

Add a column to the Test Coverage Gaps table:

```
| # | Type | Scenario Missing | Priority | Future Task | Recommendation |
|---|------|------------------|----------|-------------|----------------|
| 1 | Unit | Error path for X  | HIGH     | NOT PLANNED | Add to current task |
| 2 | Integration | Pagination edge case | MEDIUM | T-015 | Defer — dedicated test task |
| 3 | E2E | Empty state flow | HIGH | T-018 | Anticipate — current task creates this flow |
```

### Step 2.3: Analyze Observability Gaps (MANDATORY — do NOT skip)
For EACH new component:
1. Check existing logging patterns in the codebase
2. Verify new components follow them
3. Flag missing logs and missing structured fields for metrics

### Step 2.4: Dispatch Validation Agents (MANDATORY)

**HARD BLOCK:** Dispatch specialist ring droids in parallel to validate the task spec. Each agent receives file paths and can navigate the codebase autonomously.

**Ring droids are REQUIRED** — verify ring droids — see AGENTS.md Protocol: Ring Droid Requirement Check. **If any of the droids below are not available, STOP and inform the user:**
```
Required ring droids are not installed. Install them before running this skill:
  - ring-default-business-logic-reviewer
  - ring-default-security-reviewer
  - ring-dev-team-qa-analyst
  - ring-default-code-reviewer
```

**Droids to dispatch:**

1. `ring-default-business-logic-reviewer` — validate business rules completeness, edge cases, and domain correctness in the task spec
2. `ring-default-security-reviewer` — identify security gaps in the spec (missing auth, input validation, data exposure risks)
3. `ring-dev-team-qa-analyst` — validate testing strategy completeness, identify untested scenarios
4. `ring-default-code-reviewer` — assess architectural feasibility, identify patterns that may conflict with the codebase

**Agent prompt MUST include:**
```
Goal: Pre-implementation validation of task T-XXX — [your domain]

Context:
  - Project root: <absolute path to project worktree>
  - Task spec: <TASKS_DIR>/<TaskSpec> (READ this file)
  - Subtasks dir: <TASKS_DIR>/subtasks/T-XXX/ (READ all .md files if dir exists)
  - Reference docs dir: <TASKS_DIR>/ (explore for PRD, TRD, API design, data model)
  - Project rules: AGENTS.md, PROJECT_RULES.md, docs/PROJECT_RULES.md (READ all that exist)
  - Gaps already identified: [list from Steps 2.1-2.3]

IMPORTANT: You have access to Read, Grep, and Glob tools. USE THEM to:
  - Read files at the paths above
  - Search the codebase for patterns similar to what the spec describes
  - Find how similar features were implemented in the project
  - Discover existing test patterns, error handling conventions, and architectural styles
  - Explore related files not listed above when needed for context

Your job:
  Validate the task spec from your domain perspective BEFORE implementation.
  Identify risks, gaps, contradictions, or missing requirements.
  Report findings ONLY — do NOT generate code.

Required output:
  For each finding: severity, category, description, recommendation
  If no issues: "PASS — [domain] validation clean"

Cross-cutting analysis (MANDATORY for all agents):
  1. What would break in production under load if this spec is implemented as-is?
  2. What's MISSING from the spec that should be there? (not just what's wrong)
  3. Does this spec trace back to business requirements? Flag orphan requirements
  4. How would a new developer understand and implement this spec 6 months from now?
  5. Search the codebase for how similar features were built — flag inconsistencies with existing patterns
```

**Special Instructions per Agent:**

Include per-droid quality checklists — see AGENTS.md Protocol: Per-Droid Quality Checklists.
Adapt checklist items to spec validation context (e.g., "verify X exists in spec" instead of
"verify X is implemented in code").

**QA agent** (`ring-dev-team-qa-analyst`) must additionally (beyond the protocol):
- Spec quality: are ACs measurable and testable? (not vague like "works correctly")
- Does each AC specify both success AND failure behavior?
- Rollback/recovery strategy defined for failure cases
- Can a developer implement each item WITHOUT asking questions?

Merge agent findings with the findings from Steps 2.1-2.3. Deduplicate and sort by severity before presenting.

## Phase 3: Present and Resolve Findings

### Step 3.1: Present Summary, then Walk Through Each Finding

1. **Announce total findings count:** Display `"### Total findings to review: N"` prominently before presenting the first finding
2. **Present the summary report** (tables from Output Format) for bird's-eye view
3. **Then present findings ONE AT A TIME** in priority order: contradictions > missing specs > test gaps > observability > DoD > ambiguities

**For EACH finding**, present with `"(X/N)"` progress prefix in the header:

#### Deep Research Before Presenting (MANDATORY)

Execute deep research before presenting each finding — see AGENTS.md "Common Patterns > Deep Research Before Presenting". All 12 checklist items apply.

#### Present the Finding

- **Problem:** Clear description, referencing exact doc locations
- **Why it matters:** Impact analysis through four lenses:
  - **UX:** How does this affect the end user?
  - **Task focus:** Within task scope or tangential?
  - **Project focus:** MVP-critical or gold-plating?
  - **Engineering quality:** Maintainability, testability, reliability impact

#### Proposed Solutions (2-3 options)

Present 2-3 options using the format from AGENTS.md "Common Patterns > Finding Option Format".

#### Collect Decision

   **AskUser `[topic]` format:** Format: `(X/N) F#-Category`.
   Example: `[topic] (8/12) F8-DeadCode`.

4. Use `AskUser` tool. **BLOCKING**: Do NOT advance to the next finding until the user decides.
   **Every AskUser MUST include these options:**
   - One option per proposed solution (Option A, Option B, Option C, etc.)
   - Skip — no action
   - Tell me more — if selected, STOP and answer immediately (do NOT continue to next finding)

   **AskUser template (MANDATORY — follow this exact structure for every finding):**
   ```
   1. [question] (X/N) SEVERITY — Finding title summary
   [topic] (X/N) F#-Category
   [option] Option A: recommended fix
   [option] Option B: alternative approach
   [option] Skip
   [option] Tell me more
   ```

5. **HARD BLOCK — IMMEDIATE RESPONSE RULE:** If the user selects "Tell me more" or responds
   with free text: **STOP IMMEDIATELY.** Do NOT continue to the next finding. Research and
   answer RIGHT NOW. Only after the user is satisfied, re-present the SAME finding's options.
   **NEVER defer to the end of the findings loop.**

   **Anti-rationalization (excuses the agent MUST NOT use):**
   - "I'll address all questions after presenting the remaining findings" — NO
   - "Let me continue with the next finding and come back to this" — NO
   - "I'll research this after the findings loop" — NO
   - "This is noted, moving to the next finding" — NO
6. **Track all decisions** internally. Do NOT apply any fix yet — all fixes are applied in Phase 4.

## Phase 4: Apply Approved Corrections

### Step 4.1: Apply ALL Approved Corrections

After the user has responded to ALL findings:
1. Present a pre-apply summary listing every change grouped by file
2. Apply ALL approved changes to the docs in a single pass
3. Present a final summary of what was changed vs skipped/rejected

## Phase 5: Commit Changes

### Step 5.1: Commit Changes (if any modifications were made)

If any corrections were applied in Phase 4:
1. Run `git status` and `git diff` to review all changes
2. Check for sensitive data (secrets, keys, tokens) — if found, STOP and warn the user
3. Present the summary of changes and ask the user for commit approval via `AskUser`
4. If approved, stage all modified files and commit using the task's Tipo for the conventional commit prefix (Feature→`feat`, Fix→`fix`, Refactor→`refactor`, Chore→`chore`, Docs→`docs`, Test→`test`). Example: `feat(T-003): fix spec — [brief summary of corrections]`
5. Run `git status` to confirm the commit succeeded

If no corrections were applied (all findings skipped), skip this step.

## Phase 6: Convergence Loop (Optional — Gated)

### Step 6.1: Convergence Loop

Execute the opt-in convergence loop — see AGENTS.md "Common Patterns > Protocol: Convergence Loop (Full Roster Model — Opt-In, Gated)".

**Behavioral contract for THIS phase:**
- Round 1 already ran in Step 2.4. THIS phase only handles rounds 2 through 5.
- Present the **entry gate** before round 2 (`Run round 2` / `Skip convergence loop`).
- Present the **per-round gate** before rounds 3, 4, 5 (`Continue` / `Stop here`).
- If a dispatched round produces ZERO new findings, declare convergence and exit
  silently — DO NOT ask the user whether to run another round.
- Record the final loop status (`CONVERGED` / `USER_STOPPED` / `SKIPPED` /
  `HARD_LIMIT` / `DISPATCH_FAILED_ABORTED`) for the Final Summary (Validation Report).

**Stage-specific scope for convergence rounds 2+:**
Dispatch the **same 4 droids** from Step 2.4 (business-logic-reviewer, security-reviewer,
qa-analyst, code-reviewer). Each agent receives file paths to task spec, reference docs,
optimus-tasks.md, and project rules (re-read fresh from disk). Do NOT include the findings ledger
in agent prompts — the orchestrator handles dedup using strict matching (same file + same
line range ±5 + same category).

Include analysis instructions: cross-reference (Step 2.1), test gaps (Step 2.2),
observability (Step 2.3), DoD, ambiguities. Include the cross-cutting analysis instructions
(same 5 items from Step 2.4 prompt).

**Failure handling:** If a fresh sub-agent dispatch fails (Task tool error, ring droid
unavailable), do NOT count as zero findings. Ask the user via `AskUser` whether to
retry the round or stop (status `DISPATCH_FAILED_ABORTED` if user stops).

When the loop exits (any status), proceed to Phase 7 (Re-run Guard).

## Phase 7: Re-run Guard

### Step 7.1: Evaluate Re-run or Advance

Execute re-run guard — see AGENTS.md Protocol: Re-run Guard.

- If the user chooses **Re-run with clean context**: go back to Step 1.1 (Discover Project
  Structure). Skip all prior setup steps (GitHub CLI check, optimus-tasks.md validation, task
  identification, session state, status validation, workspace creation, divergence check).
  Increment stage stats before re-starting analysis. Apply the **Re-run reset semantics**: reset `convergence_status` to `null`; reset `phase` to the first re-executed phase; overwrite `started_at`; preserve `task_id`, `task_branch`, `created_at`. See AGENTS.md Protocol: Re-run Guard.
- If the user chooses **Advance** (or 0 findings): proceed to Phase 8 (Push).

## Phase 8: Push Commits

### Step 8.1: Push Commits (optional)

Offer to push commits — see AGENTS.md Protocol: Push Commits.

---

## Output Format

```markdown
# Pre-Task Validation Report: T-XXX

## Status: PASS | FAIL | PASS WITH WARNINGS

## Convergence
- Rounds dispatched (round 1 + convergence rounds): X
- Status: CONVERGED | USER_STOPPED | SKIPPED | HARD_LIMIT | DISPATCH_FAILED_ABORTED

## 1. Contradictions Found
| # | Doc A | Doc B | Field/Topic | Doc A Says | Doc B Says | Recommendation |
|---|-------|-------|-------------|------------|------------|----------------|

## 2. Missing Specifications
| # | What's Missing | Where Expected | Impact | Recommendation |
|---|----------------|----------------|--------|----------------|

## 3. Dependency Issues
| # | Dependency | Status | Blocker? | Resolution |
|---|------------|--------|----------|------------|

## 4. Test Coverage Gaps (MANDATORY — all 4 sub-sections required)

### 4a. Unit Test Gaps
Functions/methods verified: [list each function checked]
| # | Function/Method | Scenario Missing | Priority |
|---|----------------|------------------|----------|
(or: NONE — all paths covered. Justification: ...)

### 4b. Integration Test Gaps
Repository methods verified: [list each method checked]
| # | Repository Method | Scenario Missing | Priority |
|---|------------------|------------------|----------|
(or: NONE — all paths covered. Justification: ...)

### 4c. E2E Test Gaps
User flows verified: [list each flow checked]
| # | User Flow | Scenario Missing | Priority |
|---|-----------|------------------|----------|
(or: NONE — all paths covered. Justification: ...)

### 4d. Cross-Cutting Gaps
| # | Scenario | Applies? | Covered? | Gap Description |
|---|----------|----------|----------|-----------------|

## 5. Observability Gaps (MANDATORY)

### 5a. Logging Gaps
Components verified: [list each component checked]
| # | Component | Gap Description | Priority |
|---|-----------|-----------------|----------|
(or: NONE — all components have adequate logging. Justification: ...)

### 5b. Metrics Gaps
| # | Metric Missing | Where Expected | Priority |
|---|---------------|----------------|----------|
(or: NONE — all operations emit structured fields. Justification: ...)

## 6. Definition of Done Issues
| # | Issue | Current DoD Says | Expected | Recommendation |
|---|-------|-----------------|----------|----------------|

## 7. Ambiguities (developer would need to ask)
| # | Question | Context | Suggested Answer |
|---|----------|---------|-----------------|

## 8. Recommendations
- [ ] Fix before starting: ...
- [ ] Clarify with stakeholder: ...
- [ ] Add to backlog: ...
```

---

## Rules
- Do NOT generate code — this is analysis only
- Do NOT assume — if something is ambiguous, flag it
- ALWAYS check both happy path AND error paths
- Prioritize findings: contradictions > missing specs > test gaps > observability gaps > DoD issues > ambiguities
- Reference exact file locations when citing docs
- Test Coverage Gaps (Dimension 5) is MANDATORY and MUST enumerate gaps for ALL three test types plus cross-cutting scenarios
- Observability Gaps (Dimension 7) is MANDATORY. Check existing codebase logging patterns and verify new components follow them
- ALWAYS use the two-phase flow: Phase 1 presents summary then walks through each finding one at a time. Phase 2 applies all approved corrections at once
- If corrections were applied, ask the user for commit approval — do NOT commit without explicit approval
- Every finding must reference a specific doc section or standard — "I would do it differently" is not a valid finding
- BEFORE presenting each finding: deep research is MANDATORY — project patterns, architectural decisions, existing codebase, task focus, user/consumer use cases, UX impact, API best practices, engineering best practices, language-specific idioms. Option A must be the correct approach backed by research evidence, regardless of effort
- The agent NEVER decides whether a finding should be fixed or skipped — the USER always decides
- ALL findings (CRITICAL, HIGH, MEDIUM, and LOW) MUST be presented to the user for decision
- The agent may recommend an option, but MUST wait for user approval via AskUser before proceeding
- Do NOT auto-skip, auto-dismiss, or auto-resolve any finding regardless of severity
- **Re-run guard:** After the convergence loop exits, execute the Re-run Guard protocol
  (Phase 7) instead of unconditionally suggesting the next stage. The next stage is only
  suggested when the analysis produces 0 findings. See AGENTS.md Protocol: Re-run Guard.

### Dry-Run Mode

Follow AGENTS.md Protocol: Dry-Run Mode. The canonical rules apply uniformly
to plan/build/review/done — see the inlined Protocol: Dry-Run Mode block below.

**Stage-1 (plan) specifics:**
- The "no workspace creation" rule means skip Step 1.0.5 (status reservation
  AND workspace creation).
- The "no stats" rule means skip Step 1.0.7 (Increment Stage Stats).
- The "no commit/push/re-run" rule means skip Phases 4, 5, 7, and 8.
- The "skip convergence rounds 2+" rule means stop after Phase 6 round 1.

<!-- INLINE-PROTOCOLS:START -->
## Shared Protocols (from AGENTS.md)

The following protocols are referenced by this skill. They are
extracted from the Optimus AGENTS.md to make this plugin self-contained.

### File Location (summarized)

> **Summary inlined here. Full recipe at `AGENTS.md -> File Location`.**

**Summary:** Defines where Optimus operational files live: `${MAIN_WORKTREE}/.optimus/{state.json, stats.json, sessions/, reports/, logs/}` (gitignored, per-user) vs `<tasksDir>/optimus:tasks.md` + `<tasksDir>/{tasks,subtasks}/` (versioned, project-team-shared, propagated by git). Also: `${MAIN_WORKTREE}/.gitignore` (versioned), `${MAIN_WORKTREE}/.worktrees/` (gitignored linked-worktree dir). Critical contract: `.optimus/*` paths NEVER propagate across linked worktrees (gitignored = not shared by `git worktree add`); use `${MAIN_WORKTREE}/` prefix consistently. See full table in AGENTS.md.

Optimus splits its files into two trees:

### Valid Status Values (stored in state.json)

Status lives in `.optimus/state.json`, NOT in optimus-tasks.md. A task with no entry in
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


### Format Validation (summarized)

> **Summary inlined here. Full recipe at `AGENTS.md -> Format Validation`.**

**Summary:** 15-rule validation for `<tasksDir>/optimus:tasks.md` enforced at Step 1.0.1 of every stage agent (1-4): format marker `<!-- optimus:tasks-v1 -->` present; `## Versions` table with valid columns; all Version Status values valid (`Ativa`/`Próxima`/`Planejada`/`Backlog`/`Concluída`); exactly one `Ativa`, at most one `Próxima`; tasks table columns correct (Status/Branch live in state.json, NOT here); IDs match `T-NNN`; Tipo ∈ {Feature, Fix, Refactor, Chore, Docs, Test}; Priority ∈ {Alta, Media, Baixa}; Depends resolves to existing task rows; Version cells reference existing version rows; no duplicate IDs; no circular dependencies; no unescaped pipes; empty-table guard. HARD BLOCK on any failure — STOP and suggest `/optimus:import`. See full 15-item enumeration in AGENTS.md.

Every stage agent (1-4) MUST validate the optimus-tasks.md format before operating:
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
running `/optimus:import` to fix the format. Do NOT attempt to interpret malformed data.

14. No unescaped pipe characters (`|`) in task titles (breaks markdown table parsing)
15. **Empty table handling:** If the tasks table exists but has zero data rows (only headers),
format validation PASSES. Stage agents (1-4) MUST check for this condition immediately after
format validation and before task identification. If zero data rows: **STOP** and inform the
user: "No tasks found in optimus-tasks.md. Use `/optimus:tasks` to create a task or `/optimus:import`
to import from Ring pre-dev." Do NOT proceed to task identification with an empty table.

### Protocol: Resolve Tasks Git Scope (summarized)

> **Summary inlined here. Full recipe at `AGENTS.md -> Protocol: Resolve Tasks Git Scope`.**

**Summary:** Resolves `TASKS_DIR` (from `.optimus/config.json` `tasksDir` key, default `docs/pre-dev`) and `TASKS_FILE` (`<tasksDir>/optimus:tasks.md`), then detects whether tasksDir lives inside the project repo (`same-repo`) or a separate git repo (`separate-repo`). Sets `TASKS_REPO_ROOT`, `TASKS_GIT_REL`, `TASKS_DEFAULT_BRANCH`, and exposes a `tasks_git()` helper that wraps `git -C "$TASKS_DIR"` in separate-repo mode. Hard guards: reject `tasksDir` starting with `-` (git-option injection), require `python3` for separate-repo path computation, validate `TASKS_DEFAULT_BRANCH` against `^[a-zA-Z0-9._/-]+$`. Skills MUST use `tasks_git` (never raw `git`) on `$TASKS_FILE`. See full recipe in AGENTS.md.

### Deep Research Before Presenting (MANDATORY for cycle review skills)
Applies to: plan, review, pr-check, coderabbit-review

**BEFORE presenting any finding to the user, the agent MUST research it deeply.** This
research is done SILENTLY — do not show the research process. Present only the conclusions.

**Research checklist (ALL items, every finding):**

1. **Project patterns:** Read the affected file(s) fully. Check how similar cases are handled
   elsewhere in the codebase. Identify existing conventions the finding might violate or follow.
2. **Architectural decisions:** Review project rules (AGENTS.md, PROJECT_RULES.md, etc.) and
   architecture docs (TRD, ADRs). Understand WHY the project is structured this way before
   suggesting changes.
3. **Existing codebase:** Search for precedent. If the codebase already does the same thing
   in 10 other places without issue, that context changes the finding's weight.
4. **Current task focus:** Is this finding within the scope of the task being worked on?
   Tangential findings should be flagged as such (not dismissed, but contextualized).
5. **User/consumer use cases:** Who consumes this code — end users, other services, internal
   modules? How does the finding affect them? Trace the impact to real user scenarios.
6. **UX impact:** For user-facing changes, evaluate usability, accessibility, error messaging,
   and workflows. Would the user notice? Would it block their work?
7. **API best practices:** For API changes, check REST conventions, error handling patterns,
   idempotency, status codes, pagination, versioning, and backward compatibility.
8. **Engineering best practices:** SOLID principles, DRY, separation of concerns, error
   handling, resilience patterns, observability, testability.
9. **Language-specific best practices:** Use `WebSearch` to research idioms and conventions
   for the specific language (Go, TypeScript, Python, etc.). Check official style guides,
   common linter rules, and community-accepted patterns.
10. **Correctness over convenience:** Always recommend the correct approach, regardless of
    effort. The easy option may be presented as an alternative, but Option A must be what
    the agent believes is right based on all the research above.
11. **Production resilience:** Would this code survive production conditions? Consider:
    timeouts on external calls, retry with backoff, circuit breakers, graceful degradation,
    resource cleanup (connections, handles, goroutines), graceful shutdown, and behavior
    under load (N+1 queries, unbounded queries, connection pool exhaustion).
12. **Data integrity and privacy:** Are transaction boundaries correct? Could partial writes
    occur? Is PII properly handled (not logged, masked in responses)? LGPD/GDPR compliance?

**After research, form the recommendation:** Option A MUST be the approach the agent
believes is correct based on the research. It must be backed by evidence (project patterns,
best practice references, official documentation), not just a generic suggestion.


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


### Protocol: Active Version Guard

**Referenced by:** all stage agents (1-4)

After the task ID is confirmed and dependencies are validated, check if the task belongs
to the `Ativa` version. If not, present options before proceeding.

1. Read the task's **Version** column from `optimus-tasks.md`
2. Read the **Versions** table and find the version with Status `Ativa`
   - **If no version has Status `Ativa`** → **STOP**: "No active version found in the Versions table. Run `/optimus:tasks` to set a version as Ativa before proceeding."
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
   - Update the task's Version column in `optimus-tasks.md` to the `Ativa` version name
   - Commit using `tasks_git` so the change lands in the correct repo (same-repo or
     separate-repo, as resolved by Protocol: Resolve Tasks Git Scope):
     ```bash
     tasks_git add "$TASKS_GIT_REL"
     COMMIT_MSG_FILE=$(mktemp -t optimus.XXXXXX) || { echo "ERROR: mktemp failed" >&2; exit 1; }
     chmod 600 "$COMMIT_MSG_FILE"
     printf '%s' "chore(tasks): move T-XXX to active version <active_version>" > "$COMMIT_MSG_FILE"
     tasks_git commit -F "$COMMIT_MSG_FILE"
     rm -f "$COMMIT_MSG_FILE"
     ```
   - Proceed with the stage

6. **If "Cancel":** **STOP** — do not proceed with the stage

Skills reference this as: "Check active version guard — see AGENTS.md Protocol: Active Version Guard."


### Protocol: All-Dependencies-Cancelled Resolution

**Referenced by:** plan, build, review, done, batch

When all dependencies of a task are status `Cancelado`, emit a multi-option resolution
message AFTER the per-dependency status check (i.e., after detecting that every dep is
`Cancelado`, before the per-dep error-and-exit). The check supplements the per-dep loop;
it does not replace it.

**Variable contract:** the caller's dep-check loop populates an array `DEP_STATUSES`
with one status string per dependency (the same status read from `state.json` for each
dep ID listed in the Depends column). If the existing skill code uses a different
variable name, adapt the recipe below to match — the contract is "an iterable of
dependency status strings".

**Bash recipe:**

```bash
# Assumes DEP_STATUSES is an array of dependency status strings,
# already populated by the caller's dep-check loop.
ALL_CANCELLED=true
for dep_status in "${DEP_STATUSES[@]}"; do
  if [ "$dep_status" != "Cancelado" ]; then
    ALL_CANCELLED=false
    break
  fi
done

if [ "$ALL_CANCELLED" = true ] && [ "${#DEP_STATUSES[@]}" -gt 0 ]; then
  echo "All dependencies of $TASK_ID are cancelled. To unblock:" >&2
  echo "  (a) remove all dependencies: /optimus:tasks edit $TASK_ID" >&2
  echo "  (b) replace with alternative task IDs: /optimus:tasks edit $TASK_ID" >&2
  echo "  (c) cancel $TASK_ID: /optimus:tasks cancel $TASK_ID" >&2
  exit 1
fi
# Per-dep message follows here (existing logic).
```

Skills reference this as: "Check all-deps-cancelled — see AGENTS.md Protocol: All-Dependencies-Cancelled Resolution."


### Protocol: Branch Name Derivation

**Referenced by:** plan, build, review, pr-check, done (workspace auto-navigation)

Branch names are derived deterministically from the task's structural data in optimus-tasks.md.
They are NOT stored in optimus-tasks.md — they are stored in state.json for quick reference
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
1. Read `branch` from state.json (fastest, source-of-truth).
2. Search by task ID using the kebab-anchored fallback (NEVER an unanchored
   `grep -iF "$TASK_ID"`, which matches `T-1` against `T-10`/`T-100`):
   ```bash
   TASK_KEBAB="-$(echo "$TASK_ID" | tr '[:upper:]' '[:lower:]')-"
   git branch --list "*${TASK_KEBAB#-}*" 2>/dev/null
   git worktree list --porcelain 2>/dev/null \
     | awk -v anchor="$TASK_KEBAB" '/^worktree / { path=$2; if (index(tolower(path), anchor) > 0) print path }'
   ```
3. Derive from Tipo + ID + Title (always works).

Skills reference this as: "Derive branch name — see AGENTS.md Protocol: Branch Name Derivation."


### Protocol: Convergence Loop (Full Roster Model — Opt-In, Gated) (summarized)

> **Summary inlined here. Full recipe at `AGENTS.md -> Protocol: Convergence Loop (Full Roster Model — Opt-In, Gated)`.**

**Summary:** Multi-round review pattern for plan, build, review, pr-check, coderabbit-review, deep-review, deep-doc-review. Round 1 is mandatory (the skill's primary dispatch). Rounds 2-5 are gated behind explicit `AskUser` prompts (entry gate before round 2, per-round gate before 3/4/5). Each gated round dispatches the SAME droid roster as round 1 in parallel via `Task` tool with zero prior context — agents read files fresh from disk. Convergence detection (zero new findings, strict `same file + ±5 lines + same category` matching) exits silently with status `CONVERGED` — never asks for another round. Hard limit at round 5. Exit statuses: `CONVERGED`, `USER_STOPPED`, `SKIPPED`, `HARD_LIMIT`, `DISPATCH_FAILED_ABORTED` (build has a single-slot carve-out). See full recipe in AGENTS.md.

### Protocol: Divergence Warning

**Referenced by:** all stage agents (1-4)

Since status and branch data live in state.json (gitignored), optimus-tasks.md rarely changes
on feature branches. This protocol detects the uncommon case where optimus-tasks.md WAS modified
(e.g., Active Version Guard moved a task). It uses `tasks_git` so it works in both
same-repo and separate-repo scopes.

**Prerequisite:** Protocol: Resolve Tasks Git Scope must have been executed so
`TASKS_FILE`, `TASKS_GIT_REL`, `TASKS_GIT_SCOPE`, `TASKS_DEFAULT_BRANCH`, and
`tasks_git` are defined.

```bash
# Requires Protocol: Resolve Main Worktree Path to have run first
# (or resolve inline; see that protocol).
MAIN_WORKTREE="$(git worktree list --porcelain 2>/dev/null | awk '/^worktree / {print $2; exit}')"
MAIN_WORKTREE="${MAIN_WORKTREE:?MAIN_WORKTREE not resolved — not in a git repository}"
if [ -z "$TASKS_DEFAULT_BRANCH" ]; then
  echo "WARNING: Cannot determine default branch for tasks repo. Skipping divergence check."
  # Skip — this is a warning, not a HARD BLOCK
else
  # Throttle fetch: only re-fetch if the cached timestamp is older than 5 minutes.
  # Each stage skill would otherwise pay ~2s network latency per invocation.
  # The cache lives in the PROJECT repo's .optimus/ (always present, gitignored).
  FETCH_MARKER="${MAIN_WORKTREE}/.optimus/.last-tasks-fetch"
  NOW_EPOCH=$(date +%s)
  SHOULD_FETCH=1
  if [ -f "$FETCH_MARKER" ]; then
    LAST_EPOCH=$(cat "$FETCH_MARKER" 2>/dev/null || echo 0)
    # Defense-in-depth: ensure marker contents are numeric before arithmetic.
    # A corrupted/manually-edited marker file would otherwise crash the
    # `$((NOW_EPOCH - LAST_EPOCH))` expression under `set -euo pipefail`.
    [[ "$LAST_EPOCH" =~ ^[0-9]+$ ]] || LAST_EPOCH=0
    if [ -n "$LAST_EPOCH" ] && [ "$((NOW_EPOCH - LAST_EPOCH))" -lt 300 ]; then
      SHOULD_FETCH=0
    fi
  fi
  if [ "$SHOULD_FETCH" = "1" ]; then
    if tasks_git fetch origin "$TASKS_DEFAULT_BRANCH" --quiet 2>/dev/null; then
      mkdir -p "${MAIN_WORKTREE}/.optimus"
      printf '%s' "$NOW_EPOCH" > "$FETCH_MARKER"
    else
      echo "WARNING: Could not fetch from origin. Divergence check may use stale data."
    fi
  fi
  tasks_git diff "origin/$TASKS_DEFAULT_BRANCH" -- "$TASKS_GIT_REL" 2>/dev/null | head -20
fi
```

- If diff output is non-empty → warn via `AskUser`:
  ```
  optimus-tasks.md has diverged between your branch and <default_branch>.
  This may cause merge conflicts when the PR is merged.
  ```
  Options:
  - **Sync now** — run `tasks_git merge origin/<default_branch>` to incorporate changes
  - **Continue without syncing** — I'll handle conflicts later
- If diff output is empty → proceed silently (files are in sync)
- **NOTE:** This is a warning, not a HARD BLOCK. The user may choose to continue.
- **NOTE:** In separate-repo scope, "diverged" means the tasks repo branches diverge —
  not the project code branches.

Skills reference this as: "Check optimus-tasks.md divergence — see AGENTS.md Protocol: Divergence Warning."


## Protocol: Dry-Run Mode

**Referenced by:** plan, build, review, done (all stage agents 1-4).

All stage agents support **dry-run mode**. When the user includes "dry-run" or
"preview" in their invocation (e.g., "dry-run spec T-003", "preview review T-012"),
the agent MUST:

1. **Run all analysis/validation phases normally** — agent dispatch, findings, etc.
2. **Do NOT change task status** — skip the status update step in state.json.
3. **Do NOT commit or push anything** — no git operations that modify state.
4. **Do NOT create workspaces** — skip branch/worktree creation (stage-1 only).
5. **Do NOT apply fixes** — skip batch-apply phases.
6. **Do NOT increment stage stats** — skip the Increment Stage Stats protocol.
7. **Do NOT write session files** — session state is for crash recovery of real
   executions, not previews.
8. **Skip convergence rounds 2+** — round 1 (primary review pass) is sufficient
   for preview; do NOT enter the convergence loop.
9. **Present results as informational** — phrase the summary as "what would happen"
   without implying any side effects occurred.

Stage agents may add stage-specific dry-run notes (e.g., which phase numbers
to skip), but MUST NOT relax any of the rules above. The point of dry-run is
to give the user a reliable preview with zero state mutation.


### Protocol: GitHub CLI Check (HARD BLOCK)

**Referenced by:** all stage agents (1-4), tasks, batch

```bash
gh auth status 2>/dev/null
```

If this command fails (exit code != 0), **STOP** immediately:
```
GitHub CLI (gh) is not authenticated. Run `gh auth login` to authenticate before proceeding.
```


### Protocol: Increment Stage Stats

**Referenced by:** plan, review

After the status change in state.json (and BEFORE any analysis work begins), increment
the execution counter for the current stage in `.optimus/stats.json`. This tracks how many
times each stage ran on each task — useful for spotting spec churn and review cycles.

**NOTE:** Only increment when NOT in dry-run mode.

1. Read `.optimus/stats.json`. If the file does not exist, start with an empty object `{}`.
   If the file exists but is corrupted, reset it:
   ```bash
   # Requires Protocol: Resolve Main Worktree Path to have run first
   # (or resolve inline; see that protocol).
   MAIN_WORKTREE="$(git worktree list --porcelain 2>/dev/null | awk '/^worktree / {print $2; exit}')"
   MAIN_WORKTREE="${MAIN_WORKTREE:?MAIN_WORKTREE not resolved — not in a git repository}"
   STATS_FILE="${MAIN_WORKTREE}/.optimus/stats.json"
   if [ -f "$STATS_FILE" ] && ! jq empty "$STATS_FILE" 2>/dev/null; then
     echo "WARNING: stats.json is corrupted. Resetting counters."
     echo '{}' > "$STATS_FILE"
   fi
   ```
2. If the task ID key does not exist, initialize it:
   ```json
   { "plan_runs": 0, "review_runs": 0 }
   ```
3. Increment the appropriate counter (`plan_runs` for plan, `review_runs` for review).
4. Set the timestamp field (`last_plan` or `last_review`) to the current UTC ISO 8601 time.
5. Write the updated JSON back to `.optimus/stats.json` (pretty-printed, sorted keys).

**NOTE:** stats.json is gitignored — no commit needed.

Skills reference this as: "Increment stage stats — see AGENTS.md Protocol: Increment Stage Stats."


### Protocol: Notification Hooks (summarized)

> **Summary inlined here. Full recipe at `AGENTS.md -> Protocol: Notification Hooks`.**

**Summary:** Optional hook system: stages emit events (`status-change`, `task-blocked`, `task-done`, `task-cancelled`) by invoking `<repo>/tasks-hooks.sh <event> <task_id> <args...>` (or `<repo>/docs/tasks-hooks.sh`) if the file exists and is executable. Hook receives sanitized args (alphanumeric + space + `-_:` only — does NOT allow `.` or `/` to prevent path-traversal if hook authors interpolate args into file paths). Argument shape: 4 args for `status-change`/`task-done`/`task-cancelled` (`event task_id old_status new_status`); 4 args for `task-blocked` (`event task_id current_status reason`). Hooks run in background (`&`) — failures NEVER block the pipeline. Capture `OLD_STATUS` BEFORE writing the new status. See full event signatures + sanitization recipe in AGENTS.md.

### Protocol: Per-Droid Quality Checklists (summarized)

> **Summary inlined here. Full recipe at `AGENTS.md -> Protocol: Per-Droid Quality Checklists`.**

**Summary:** Per-droid quality dimensions that review/pr-check/deep-review/coderabbit-review/plan/build skills MUST include in their agent prompts beyond the core review domain. Examples: code-reviewer adds resilience/concurrency/cognitive-complexity/error-handling checks; security-reviewer adds PII/error-response-leakage/rate-limiting/secrets; test-reviewer adds effectiveness/false-positive-risk/spec-traceability; nil-safety adds channel/map/slice safety; consequences adds backward-compat/migration-path/event-contract; dead-code adds zombie test infrastructure and stale feature flags; qa-analyst adds testability/operational-readiness; frontend adds UX states/accessibility/i18n; backend adds graceful-shutdown/context-propagation/structured-logging. Skills reference this when building specialist droid prompts so agents review uniformly. See full per-droid lists in AGENTS.md.

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

**Referenced by:** plan, build, review, coderabbit-review. Note: done handles pushing inline in its own cleanup phase. pr-check and deep-review have their own push phases.

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

**Step 2 — Check tasks repo in separate-repo mode:**

If `$TASKS_GIT_SCOPE = "separate-repo"`, the tasks repo is independent from the project
repo. Commits made via `tasks_git commit` (e.g., Active Version Guard) land in the tasks
repo and must be pushed separately. Skipping this makes team members pull project main
without seeing version/task changes.

```bash
if [ "$TASKS_GIT_SCOPE" = "separate-repo" ]; then
  # Check if tasks-repo current branch has upstream
  if ! tasks_git rev-parse --abbrev-ref @{u} >/dev/null 2>&1; then
    TASKS_BRANCH=$(tasks_git branch --show-current 2>/dev/null)
    # AskUser: "Tasks repo branch '$TASKS_BRANCH' has no upstream. Push now?"
    # Options: Push now — `tasks_git push -u origin "$TASKS_BRANCH"` / Skip
  else
    TASKS_UNPUSHED=$(tasks_git log @{u}..HEAD --oneline 2>/dev/null)
    if [ -n "$TASKS_UNPUSHED" ]; then
      TASKS_UNPUSHED_COUNT=$(printf '%s\n' "$TASKS_UNPUSHED" | wc -l | tr -d ' ')
      # AskUser: "Tasks repo has $TASKS_UNPUSHED_COUNT unpushed commits. Push now?"
      # Options: Push now — `tasks_git push` / Skip
    fi
  fi
fi
```

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


### Protocol: Re-run Guard

**Referenced by:** plan, review

After the convergence loop exits and the final report/summary is presented, evaluate
whether to suggest advancement or offer a re-run. This protocol replaces the static
"Next step suggestion" in plan and review.

**Logic:**

1. Count `total_findings` produced during this execution (all findings from round 1 AND
   any convergence rounds that were dispatched — note: with opt-in gating, the user may
   have skipped them all, in which case only round 1 contributes — from all agents and
   static analysis, regardless of whether they were fixed or skipped by the user). If
   findings were grouped (per Finding Presentation item 3), count grouped entries, not
   individual occurrences.
2. **If `total_findings == 0`:** The analysis is clean. Suggest the next stage:
   - plan: "Spec validation clean — 0 findings. Next step: run `/optimus:build` to implement this task."
   - review: "Implementation review clean — 0 findings. Next step: run `/optimus:done` to close this task."
3. **If `total_findings > 0`:** Ask via `AskUser`:
   ```
   Validation found N findings (X fixed, Y skipped).
   Re-running dispatches ALL review agents again with clean context (no memory of
   previous findings — findings you previously skipped will reappear for review).
   This will consume similar tokens to the initial run. Workspace and status are preserved.
   ```
   Options:
   - **Re-run with clean context** — re-analyze from scratch
   - **Advance to next stage** — proceed despite findings

4. **If "Re-run with clean context":**
   - Increment stage stats (new execution)
   - **Skip:** GitHub CLI check, optimus-tasks.md validation, task identification, session state
     check, status validation/change, workspace creation, divergence check
   - **Re-execute:** project structure discovery, document loading, static analysis,
     coverage profiling, agent dispatch (ALL agents), finding presentation, fix application,
     convergence loop entry gate (and any rounds the user opts into)
   - **Session file:** After re-run starts, the session protocol (Protocol: Session State)
     resumes normal operation — update the session file at each phase transition as usual.
     This ensures crash recovery during a re-run resumes from the correct phase.
   - After the re-run completes, apply this protocol again (evaluate findings count)
   - There is no limit on re-runs — the user controls when to stop

   **Re-run reset semantics (MANDATORY):** When the user chooses "Re-run with clean
   context", the orchestrator MUST:

   1. Reset `convergence_status` to `null` in the session file (was set to `"CONVERGED"`
      or another terminal state at the previous run's end).
   2. Reset `phase` to the entry of the re-executed flow (typically the first phase
      that performs work, NOT the load-only phases).
   3. Overwrite `started_at` with the new run's timestamp; preserve `created_at`.
   4. Preserve `task_id`, `task_branch`, and any other identity fields.
   5. After reset, normal `Protocol: Session State` updates resume.

   WITHOUT this reset, a previous run's `convergence_status: "CONVERGED"` would
   short-circuit the re-run's loop, producing a phantom "no findings" result.

5. **If "Advance to next stage":** Proceed to push commits and present the next step suggestion.

**NOTE:** "0 findings" means the analysis produced zero findings — not that all findings
were resolved. If the user skipped findings in a previous run, they will reappear on
re-run (clean context has no memory of previous decisions). This is by design.

**NOTE:** Re-run analyzes the current codebase state, including any fixes applied and
committed during the previous run. It does NOT revert commits. This validates that
applied fixes are correct and checks for any issues introduced by the fixes.

Skills reference this as: "Execute re-run guard — see AGENTS.md Protocol: Re-run Guard."


### Protocol: Resolve Main Worktree Path (summarized)

> **Summary inlined here. Full recipe at `AGENTS.md -> Protocol: Resolve Main Worktree Path`.**

**Summary:** Resolve `MAIN_WORKTREE` once via `git worktree list --porcelain | awk '/^worktree / {print $2; exit}'` with `${MAIN_WORKTREE:?…}` defensive guard. Use `${MAIN_WORKTREE}/.optimus/...` for ALL `.optimus/` paths (gitignored, so doesn't propagate across linked worktrees). See full recipe in AGENTS.md.

### Protocol: Ring Droid Requirement Check

**Referenced by:** review, deep-doc-review, coderabbit-review, plan, build

Before dispatching ring droids, verify the required droids are available. If any required
droid is not installed, **STOP** and list missing droids.

**Core review droids** (required by review, pr-check, deep-review, coderabbit-review):
- `ring-default-code-reviewer`
- `ring-default-business-logic-reviewer`
- `ring-default-security-reviewer`
- `ring-default-ring-test-reviewer`

**Extended review droids** (required by review, pr-check, deep-review, coderabbit-review):
- `ring-default-ring-nil-safety-reviewer`
- `ring-default-ring-consequences-reviewer`
- `ring-default-ring-dead-code-reviewer`

**QA droids** (required by review, deep-review, build):
- `ring-dev-team-qa-analyst`

**Documentation droids** (required by deep-doc-review):
- `ring-tw-team-docs-reviewer`
- `ring-default-business-logic-reviewer`
- `ring-default-code-reviewer`

**Implementation droids** (required by build):
- `ring-dev-team-backend-engineer-golang` (Go)
- `ring-dev-team-backend-engineer-typescript` (TypeScript)
- `ring-dev-team-frontend-engineer` (React/Next.js)

**Spec validation droids** (required by plan):
- `ring-default-business-logic-reviewer`
- `ring-default-security-reviewer`
- `ring-dev-team-qa-analyst`
- `ring-default-code-reviewer`

Skills reference this as: "Verify ring droids — see AGENTS.md Protocol: Ring Droid Requirement Check."


### Protocol: Session State (summarized)

> **Summary inlined here. Full recipe at `AGENTS.md -> Protocol: Session State`.**

**Summary:** Session lifecycle state at `${MAIN_WORKTREE}/.optimus/sessions/session-${TASK_ID}.json` tracks `task_id`, `branch`, `phase`, `convergence_status`, `started_at`. Update at every phase transition. Initialize `.optimus/` directory + auto-prune `.optimus/logs/` (30-day, 500-file cap) on transition. See full recipe in AGENTS.md.

### Protocol: Shell Safety Guidelines

**Referenced by:** plan, batch

All bash examples in AGENTS.md and SKILL.md files are templates that agents execute literally.
Follow these rules to prevent injection and silent failures:

1. **Always quote variables:** Use `"$VAR"` not `$VAR` — especially for paths, branch names, and user-derived values
2. **Check exit codes for critical commands:**
   ```bash
   tasks_git add "$TASKS_GIT_REL"
   COMMIT_MSG_FILE=$(mktemp)
   printf '%s' "chore(tasks): $COMMIT_MSG" > "$COMMIT_MSG_FILE"
   if ! tasks_git commit -F "$COMMIT_MSG_FILE"; then
     echo "ERROR: git commit failed. Check pre-commit hooks or git config." >&2
     rm -f "$COMMIT_MSG_FILE"
     exit 1
   fi
   rm -f "$COMMIT_MSG_FILE"
   ```
3. **Never interpolate user-derived values directly into shell commands** — task titles,
   branch names, and other user input may contain shell metacharacters
4. **Use `grep -F` for fixed string matching** — never pass branch names or task IDs
   as regex patterns to `grep` without `-F`
5. **Use `grep -E '^\| T-NNN \|'`** to match task rows in optimus-tasks.md — plain `grep "T-NNN"`
   matches titles and dependency columns too
6. **Validate tool availability** before use: `command -v jq >/dev/null 2>&1` before running `jq`
7. **Validate JSON files** before parsing: `jq empty "$FILE" 2>/dev/null` before reading keys
8. **Sanitize user-derived values in commit messages** — task titles and descriptions may
   contain shell metacharacters (backticks, `$(...)`, double quotes). **Mandatory pattern:**
   write the commit message to a temporary file and use `git commit -F`:
   ```bash
   COMMIT_MSG_FILE=$(mktemp)
   printf '%s' "chore(tasks): $OPERATION" > "$COMMIT_MSG_FILE"
   git commit -F "$COMMIT_MSG_FILE"
   rm -f "$COMMIT_MSG_FILE"
   ```
   This avoids all shell expansion issues. If using `-m` directly, sanitize with:
   `SAFE_VALUE=$(printf '%s' "$VALUE" | tr -d '`$')` before interpolation.

Skills reference this as: "Follow shell safety guidelines — see AGENTS.md Protocol: Shell Safety Guidelines."


### Protocol: State Management (summarized)

> **Summary inlined here. Full recipe at `AGENTS.md -> Protocol: State Management`.**

**Summary:** Read/write/delete entries in `${MAIN_WORKTREE}/.optimus/state.json` with `jq`. Schema: `{task_id: {status, branch, updated_at}}`. Status values: `Pendente | Validando Spec | Em Andamento | Validando Impl | DONE | Cancelado`. All writes use `jq --arg id "$TASK_ID" --arg status "$NEW_STATUS" '.[$id] = {...}'` (injection-safe), with a tmp-file + `jq empty` validation step before `mv` to guarantee atomicity. Cancelado entries keep `branch: ""` (empty string, NOT absent — readers must treat both as Cancelado-state). Corrupted state.json is removed and treated as empty (reconciliation via worktree scan). state.json is gitignored; never committed. See full recipe in AGENTS.md for jq templates and reconciliation steps.

### Protocol: TaskSpec Resolution

**Referenced by:** plan, build, review

Resolve the full path to a task's Ring pre-dev spec and its subtasks directory:

1. Read the task's `TaskSpec` column from `optimus-tasks.md`
2. If `TaskSpec` is `-` → **STOP**: "Task T-XXX has no Ring pre-dev spec. Run `/optimus:plan T-XXX` to generate one (it will offer to invoke `ring:pre-dev-feature` interactively)."
3. Resolve full path: `TASK_SPEC_PATH = <TASKS_DIR>/<TaskSpec>`
4. **Path traversal validation (HARD BLOCK):** `TaskSpec` must resolve to a file **inside `TASKS_DIR`**.
   This prevents a malicious TaskSpec value like `../../../etc/passwd` from escaping the
   Ring pre-dev tree. Also rejects symlinks to prevent symlink-bypass TOCTOU attacks:
   ```bash
   TASKS_DIR_ABS=$(cd "$TASKS_DIR" 2>/dev/null && pwd) || { echo "ERROR: tasksDir does not exist." >&2; exit 1; }
   RESOLVED_PATH=$(cd "$TASKS_DIR_ABS" && realpath -m "$TASK_SPEC" 2>/dev/null \
     || python3 -c "import os,sys; print(os.path.realpath(os.path.join(sys.argv[1], sys.argv[2])))" "$TASKS_DIR_ABS" "$TASK_SPEC" 2>/dev/null)
   if [ -z "$RESOLVED_PATH" ]; then
     echo "ERROR: Cannot resolve TaskSpec path — realpath and python3 both unavailable." >&2
     exit 1
   fi
   case "$RESOLVED_PATH" in
     "$TASKS_DIR_ABS"/*) ;; # OK — within tasksDir
     *) echo "ERROR: TaskSpec path traversal detected — resolved path is outside tasksDir." >&2; exit 1 ;;
   esac
   # Reject symlinks: if TASK_SPEC itself or any intermediate component is a
   # symlink, a TOCTOU attacker could swap the target between validation and
   # read. realpath -m resolves symlinks transparently; this post-check ensures
   # no symlink is present in the final path.
   if [ -L "$RESOLVED_PATH" ]; then
     echo "ERROR: TaskSpec resolves to a symlink — refusing to read." >&2
     exit 1
   fi
   ```

   **Validate `TASKS_DIR` itself:** `TASKS_DIR` must be inside a valid git repository
   (same repo as project, OR a separate repo — both are allowed). Resolution of
   `TASKS_GIT_SCOPE` (Protocol: Resolve Tasks Git Scope) already enforces this by
   running `git -C "$TASKS_DIR" rev-parse --show-toplevel`. If that call fails,
   `TASKS_DIR` is not a git repository and skills STOP.

   **NOTE:** `TASKS_DIR` is NO LONGER required to be inside `PROJECT_ROOT`. Teams using
   separate-repo scope (e.g., `tasksDir: ../tasks-repo/project-alfa`) are supported.
   The security guarantee is that the **TaskSpec value** cannot escape `TASKS_DIR`.

5. Read the task spec file at `TASK_SPEC_PATH`
6. Derive subtasks directory: if TaskSpec is `tasks/task_001.md`, subtasks are at `<TASKS_DIR>/subtasks/T-001/`
7. If subtasks directory exists, read all `.md` files inside it

Skills reference this as: "Resolve TaskSpec — see AGENTS.md Protocol: TaskSpec Resolution."


### Protocol: Terminal Identification (summarized)

> **Summary inlined here. Full recipe at `AGENTS.md -> Protocol: Terminal Identification`.**

**Summary:** `_optimus_set_title <text>` updates the terminal title for iTerm2-on-macOS via AppleScript (`osascript ... set name of s to newName`) — the only channel that reliably mutates `session.name` in "divorced" iTerm2 sessions where OSC 0/1/2 and SetUserVar are ineffective. Used by stage skills to surface task context (e.g., `optimus: PLAN T-007 — User auth`) so users running multiple Optimus sessions can identify them at a glance. The function is auto-inlined into 6 SKILLs by `inline-protocols.py` (do NOT manually paste the body in SKILL.md — F12f rule). Title is informational; failure to set it is non-fatal (silent no-op outside iTerm2/macOS, in Docker/CI without TTY, or when osascript denied). See full bash function in AGENTS.md.

### Protocol: Worktree Location

**Referenced by:** plan (Step 1.0.5), resume (Step 3.3 Case 2), Protocol: Workspace Auto-Navigation (see Reusable Protocols), done (Phase 4.1 cleanup)

Optimus creates linked git worktrees during the task lifecycle:

- `/optimus:plan` creates a worktree when a task starts (Step 1.0.5).
- `/optimus:resume` creates a worktree on recovery if branch exists but worktree is missing (Step 3.3).
- Protocol: Workspace Auto-Navigation (see Reusable Protocols) creates a worktree as a fallback when an Optimus skill is invoked from the default branch and the task's worktree is missing.

**Canonical path:** `${MAIN_WORKTREE}/.worktrees/<branch-name>` — gitignored (auto-injected by `Protocol: Initialize .optimus Directory` and `Protocol: Session State`), project-rooted, and resolved against the main worktree (path correct even when invoked from a linked worktree, per Protocol: Resolve Main Worktree Path).

**Note on branch names with `/`:** branch names contain `/` (see `Protocol: Branch Name Derivation`). Used as a directory under `.worktrees/`, the `/` creates intermediate subdirectories — `<repo>/.worktrees/feat/t-007-user-auth/`. `git worktree add` creates these automatically. `ls .worktrees/` shows the tipo-prefix dirs (`feat/`, `fix/`, `chore/`); `find .worktrees/ -mindepth 2 -maxdepth 2 -type d` lists each leaf.

**Why nested under the project repo:**

| Concern | Resolution |
|---|---|
| Discoverability | All worktrees for a project listed by `ls <repo>/.worktrees/` |
| Cleanup lifecycle | Removing the project directory also removes worktrees |
| `.optimus/` companion | Both `.optimus/` and `.worktrees/` live inside the repo, gitignored — same operational pattern |
| Cross-repo safety | Worktrees always belong to the **project repo**, never the tasks repo (separate-repo `tasksDir` does not affect worktree location) |
| Main-worktree resolution | `git worktree list --porcelain` correctly identifies main first regardless of nested linked worktrees — Protocol: Resolve Main Worktree Path unaffected |

**IDE exclusion (recommended):** add `.worktrees/` to your editor's search/index exclusions to prevent double-indexing the same files in main and linked worktrees.

- VS Code (`.vscode/settings.json`): `"search.exclude": { "**/.worktrees": true }, "files.watcherExclude": { "**/.worktrees/**": true }`
- IntelliJ: mark `.worktrees/` as Excluded in Project Structure.

**Backwards compatibility:**

- Existing worktrees in older sibling locations (`../<repo>-<task>`) continue to work — `git worktree list` finds them regardless of path.
- New worktrees from `/optimus:plan` and `resume`'s recovery land in `.worktrees/`.
- No forced migration.
- Users may relocate manually with `git worktree move <old-path> ${MAIN_WORKTREE}/.worktrees/<branch-name>` when convenient.

Skills reference this as: "see AGENTS.md Protocol: Worktree Location."


### Protocol: optimus-tasks.md Validation (HARD BLOCK)

**Referenced by:** all stage agents (1-4), tasks, batch. Note: resolve performs inline format validation in its own Step 4.2.

Every stage agent MUST validate optimus-tasks.md before operating. The full validation rules are
defined in the "Format Validation" section above (items 1-15). This protocol is the
executable version:

1. **Resolve paths and git scope:** Execute Protocol: Resolve Tasks Git Scope (below) to
   resolve `TASKS_DIR`, `TASKS_FILE`, `TASKS_GIT_SCOPE`, and the `tasks_git` helper.
2. **Find optimus-tasks.md:** Check if `TASKS_FILE` exists. If not found, **STOP** and suggest `/optimus:import`.
3. **Validate format:** Execute all 15 validation checks from the "Format Validation" section. If the format marker is missing or any check fails, **STOP** and suggest `/optimus:import`.

**All subsequent references to `optimus-tasks.md` in the skill use the resolved `TASKS_FILE` path.
All references to Ring pre-dev artifacts use `TASKS_DIR` as the root** — never hardcoded paths.
**All git operations on optimus-tasks.md use the `tasks_git` helper** (which handles both same-repo
and separate-repo scopes).

Skills reference this as: "Find and validate optimus-tasks.md (HARD BLOCK) — see AGENTS.md Protocol: optimus-tasks.md Validation."


<!-- INLINE-PROTOCOLS:END -->
