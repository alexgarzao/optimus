# Phase 1: Load Context

Loaded by `SKILL.md` first. Covers Steps 1.0 through 1.4: GitHub CLI check, tasks.md validation, workspace verification, default-branch refusal, divergence warning, branch-task cross-validation, PR title check, task ID resolution, session state, terminal marking, status validation, dependency checks, stats increment, project structure discovery, doc-brief loading, changed-file identification, and task scope classification.

### Step 1.0: Verify GitHub CLI (HARD BLOCK)
Verify GitHub CLI — see AGENTS.md Protocol: GitHub CLI Check.

### Step 1.0.1: Resolve and Validate optimus-tasks.md
**HARD BLOCK:** Find and validate optimus-tasks.md — see AGENTS.md Protocol: optimus-tasks.md Validation.

### Step 1.0.2: Verify Workspace (HARD BLOCK)
Resolve workspace — see AGENTS.md Protocol: Workspace Auto-Navigation.

### Step 1.0.2.1: Refuse Default Branch (HARD BLOCK)
Refuse to run on default branch — see AGENTS.md Protocol: Default Branch Refusal.

Defense-in-depth: even if Workspace Auto-Navigation was bypassed, this guard prevents
review state mutations (status writes, etc.) on the default branch.

### Step 1.0.3: Check optimus-tasks.md Divergence (warning)
Check optimus-tasks.md divergence — see AGENTS.md Protocol: Divergence Warning.

### Step 1.0.4: Branch-Task Cross-Validation
Branch-task cross-validation — included in AGENTS.md Protocol: Workspace Auto-Navigation.

### Step 1.0.5: Validate PR Title (if PR exists)
Validate PR title — see AGENTS.md Protocol: PR Title Validation.

### Step 1.0.6: Identify Task to Validate

**If the user specified a task ID** (e.g., "validate T-012"):
- Use the provided task ID
- Confirm with the user using `AskUser`: "I'll validate task T-012: [task title]. Correct?"

**If the user did NOT specify a task ID** (e.g., "validate the last task", or just invoked the skill):
1. **Identify the task to validate:** Scan the table for tasks with status `Em Andamento` (build completed) or `Validando Impl` (re-execution). If exactly one, suggest it. If multiple, ask user which one.
2. **If no tasks with `Em Andamento` or `Validando Impl`:** Check git branch name for task ID references, then ask the user.
3. **Suggest to the user** using `AskUser`: "I identified the task to validate: T-XXX — [task title]. Is this correct, or would you like to validate a different task?"
4. **If no task can be identified**, ask the user to provide a task ID

**BLOCKING**: Do NOT proceed until the user confirms which task to validate.

### Step 1.0.7: Check Session State
Execute session state protocol — see AGENTS.md Protocol: Session State. Use stage=`review`, status=`Validando Impl`.

**On stage completion** (after Phase 9 Re-run Guard resolves to advance): delete the session file and restore terminal title.

### Step 1.0.7.1: Set Terminal Title

**CRITICAL:** Set the terminal title so the user can identify this terminal at a glance.

### Step 1.0.7.1: Set Terminal Title

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
  # badge does not render as a bare "REVIEW" with no task context.
  TASK_TITLE="(title unavailable)"
fi

# Canonical helper (badge + tab color). Silent no-op outside iTerm2/macOS.
bash scripts/runtime/optimus-mark-session.sh mark REVIEW "$TASK_ID" "$TASK_TITLE"
```

**On stage completion or exit**, restore the title:

```bash
bash scripts/runtime/optimus-mark-session.sh clear
```

### Step 1.0.8: Validate and Update Task Status

**HARD BLOCK:** This step is mandatory. Do NOT skip it.

1. Read `optimus-tasks.md` and find the row for the confirmed task ID
2. Read the task's status from state.json — see AGENTS.md Protocol: State Management.
   - If status is `Em Andamento` → proceed (build has completed)
   - If status is `Validando Impl` → proceed (re-execution of this stage)
   - If status is `Pendente` → **STOP**: "Task T-XXX is in 'Pendente'. Run plan and build first."
   - If status is `Validando Spec` → **STOP**: "Task T-XXX is in 'Validando Spec'. Run build first."
   - If status is `DONE` → **STOP**: "Task T-XXX is in 'DONE'. It has already moved past this stage."
   - If status is `Cancelado` → **STOP**: "Task T-XXX was cancelled. Cannot validate a cancelled task."
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
   - **If status will change** (current status is NOT `Validando Impl`) AND the user did NOT specify the task ID explicitly (auto-detect):
     - Present to the user via `AskUser`:
       ```
       I'm about to change task T-XXX status from '<current>' to 'Validando Impl'.

       **T-XXX: [title]**
       **Version:** [version from table]

       Confirm status change?
       ```
     - **BLOCKING:** Do NOT change status until the user confirms
   - **If re-execution** (status is already `Validando Impl`) OR the user specified the task ID explicitly:
     - Skip expanded confirmation (user already has context)
5. Update status to `Validando Impl` in state.json (if not already) — see AGENTS.md Protocol: State Management.
6. Invoke notification hooks (event=`status-change`) — see AGENTS.md Protocol: Notification Hooks.

### Step 1.0.9: Increment Stage Stats

Increment stage stats — see AGENTS.md Protocol: Increment Stage Stats. Use counter=`review_runs`, timestamp=`last_review`.

### Step 1.1: Discover Project Structure

Before loading docs, discover the project's structure and tooling (reuse discoveries from optimus-build if available):

1. **Identify stack:** Check for `go.mod`, `package.json`, `Makefile`, `Cargo.toml`, etc.
2. **Verify Makefile targets (HARD BLOCK):** The project MUST have a `Makefile` with `lint` and `test` targets. If either is missing, **STOP**: "Project is missing required Makefile targets (`make lint`, `make test`). Add them before running check."
3. **Identify project rules and AI instructions (MANDATORY):** Execute project rules discovery — see AGENTS.md Protocol: Project Rules Discovery.

4. **Identify reference docs:** Look for task specs, API design, data model, and architecture docs.

### Step 1.2: Load Reference Documents

- Resolve TaskSpec — see AGENTS.md Protocol: TaskSpec Resolution.
- Load the Doc Brief — see AGENTS.md Protocol: Doc Brief Cache.
  - If `.optimus/sessions/T-XXX/doc-brief.md` exists with matching `task_spec_hash`: load it. The brief contains the task-scoped excerpt of PRD, TRD, API, data-model, plus the relevant AGENTS.md protocols.
  - Otherwise: generate the brief now per the protocol, using the protocol set: `Per-Droid Quality Checklists`, `Deep Research Before Presenting`, `Convergence Loop`, `Re-run Guard`, `Coverage Measurement`, `Quiet Command Execution`, `Ring Droid Requirement Check`.

The Doc Brief is the primary context for downstream agent dispatches in Phase 3 and beyond; do NOT instruct agents to read PRD/TRD/API/data-model directly unless the Doc Brief is explicitly insufficient for a finding.

### Step 1.3: Identify Changed Files

Identify all files created/modified by the task. Use the appropriate method:
- If changes are uncommitted: `git diff --name-only` and `git diff --name-only --cached`
- If committed: `git diff --name-only <base>..HEAD`

Read ALL changed files — the full content of every changed file is required for agent prompts.

### Step 1.4: Determine Task Scope

Classify the task based on the file extensions of changed files:
- **Backend-only** — only backend source files, migrations, backend tests changed
- **Frontend-only** — only frontend source files, styles, frontend tests, E2E tests changed
- **Full-stack** — both backend and frontend files changed

This determines which specialist agents to dispatch in Phase 3.

---
