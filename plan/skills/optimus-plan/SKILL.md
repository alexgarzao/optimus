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
  - Task exists in optimus-tasks.md (user provides ID or skill auto-detects next pending task). If TaskSpec is `-`, plan offers to generate it via ring:pre-dev-feature in Step 1.0.4.5 (self-heal).
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

Then execute the title-setter NOW. Mark terminal session (iTerm2 badge + tab color). The function body is inlined here on purpose: each Bash tool invocation is a fresh shell, so a definition pasted in another code block does NOT survive into this one. See AGENTS.md Protocol: Terminal Identification. The canonical body of the function lives there.

```bash
_optimus_mark_session() {
  local stage="$1" task_id="$2" title="$3"
  [ "$LC_TERMINAL" = "iTerm2" ] || [ "$TERM_PROGRAM" = "iTerm.app" ] || return 0
  local pid="$PPID" target_tty=""
  for _ in 1 2 3 4; do
    [ -z "$pid" ] || [ "$pid" = "1" ] && break
    target_tty=$(ps -o tty= -p "$pid" 2>/dev/null | tr -d ' ')
    case "$target_tty" in
      ""|"?"|"??") pid=$(ps -o ppid= -p "$pid" 2>/dev/null | tr -d ' '); target_tty="" ;;
      *) break ;;
    esac
  done
  _optimus_emit() {
    if [ -n "$target_tty" ] && [ -w "/dev/$target_tty" ]; then
      printf '%s' "$1" > "/dev/$target_tty" 2>/dev/null || printf '%s' "$1"
    else
      printf '%s' "$1"
    fi
  }
  local badge_b64
  badge_b64=$(printf '%s %s\n%s' "$stage" "$task_id" "$title" | base64 | tr -d '\n')
  _optimus_emit "$(printf '\e]1337;SetBadgeFormat=%s\a' "$badge_b64")"
  local r g b
  case "$stage" in
    PLAN)   r=66;  g=135; b=245 ;;
    BUILD)  r=34;  g=197; b=94  ;;
    REVIEW) r=234; g=179; b=8   ;;
    DONE)   r=148; g=163; b=184 ;;
    *)      r=168; g=85;  b=247 ;;
  esac
  _optimus_emit "$(printf '\e]6;1;bg;red;brightness;%d\a\e]6;1;bg;green;brightness;%d\a\e]6;1;bg;blue;brightness;%d\a' "$r" "$g" "$b")"
}
_optimus_mark_session PLAN "$TASK_ID" "$TASK_TITLE"
```

**On stage completion or exit**, restore the title (body inlined for the same reason as above):

```bash
_optimus_clear_session() {
  [ "$LC_TERMINAL" = "iTerm2" ] || [ "$TERM_PROGRAM" = "iTerm.app" ] || return 0
  local pid="$PPID" target_tty=""
  for _ in 1 2 3 4; do
    [ -z "$pid" ] || [ "$pid" = "1" ] && break
    target_tty=$(ps -o tty= -p "$pid" 2>/dev/null | tr -d ' ')
    case "$target_tty" in
      ""|"?"|"??") pid=$(ps -o ppid= -p "$pid" 2>/dev/null | tr -d ' '); target_tty="" ;;
      *) break ;;
    esac
  done
  _optimus_emit_clear() {
    if [ -n "$target_tty" ] && [ -w "/dev/$target_tty" ]; then
      printf '%s' "$1" > "/dev/$target_tty" 2>/dev/null || printf '%s' "$1"
    else
      printf '%s' "$1"
    fi
  }
  _optimus_emit_clear "$(printf '\e]1337;SetBadgeFormat=\a')"
  _optimus_emit_clear "$(printf '\e]6;1;bg;*;default\a')"
}
_optimus_clear_session
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
       - If the dependency has status `Cancelado` → **STOP**: `"T-YYY was cancelled (Cancelado). Consider removing this dependency via /optimus-tasks."`
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

> Note: This prompt offers Cancel (not Defer) because plan needs the spec to do its work. To create a task without a spec, use `/optimus-tasks` and pick Defer.

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
   1. **Choose the Ring track.** Read the task's `Estimate` column and apply the auto-suggestion rule below to pick the recommended default. Ask via `AskUser`:

      ```
      [topic] (1/1) Which Ring track for T-XXX? (Estimate: <estimate>)
      ```

      Options (mark the auto-suggested one with " (recommended)"):
      - **Lightweight** (`ring:pre-dev-feature`) — 4 gates, for tasks <2 days
      - **Full** (`ring:pre-dev-full`) — 9 gates, for tasks ≥2 days or multi-component features

      Save the user's choice as `RING_TRACK` ∈ {`feature`, `full`}. The selected skill name is `ring:pre-dev-feature` (when `feature`) or `ring:pre-dev-full` (when `full`).

      **Auto-suggestion rule** (suggest the matching option as "(recommended)"; the user can always override):

      | Estimate value | Suggested default |
      |----------------|-------------------|
      | `S`, `M` | Lightweight |
      | `L`, `XL` | Full |
      | Hour-based (e.g. `2h`, `8h`) | Lightweight |
      | `1d` | Lightweight |
      | Multi-day (`2d`, `3d`, `1w`, etc.) | Full |
      | `-` or unknown | Lightweight |

   2. Verify the chosen Ring skill (`ring:pre-dev-feature` OR `ring:pre-dev-full`) is available. If unavailable → fall back to the OTHER track if it is available; if neither is available → fall back to "Link existing spec" automatically and warn the user.
   3. Invoke the chosen Ring skill via the `Skill` tool. The Skill tool has no argument channel — state the task title and tipo in conversation context immediately before the invocation (e.g., "Generating spec for T-XXX: <title> (Tipo: <tipo>)"). Ring will read these from context.
   4. **If Ring fails or returns no spec path:**
      - Warn the user: "Ring failed to generate the spec: <error>."
      - Re-prompt with `Link existing spec` / `Cancel`. Do NOT silently fall through.
      - If user picks Cancel → STOP — "Plan cancelled — task spec required."
   5. **If Ring succeeds:**
      - Capture the generated spec file path (relative to `<TASKS_DIR>`). Save in a variable `SPEC_PATH`.
      - Update the task's `TaskSpec` column in `optimus-tasks.md`.
   6. **Re-validate** optimus-tasks.md — see AGENTS.md Protocol: optimus-tasks.md Validation.
      - If validation fails:
        a. Revert the in-memory edit to the TaskSpec column.
        b. Remove the spec file Ring just created at `<TASKS_DIR>/<SPEC_PATH>` (rollback Ring's side effect).
        c. STOP and report the validation error.
   7. **Record the chosen Ring track in state.json** — see AGENTS.md Protocol: State Management. The snippet below performs an idempotent merge into the task's existing record (preserving `status`, `branch`, `updated_at`):

      ```bash
      # Record the chosen Ring track (idempotent merge into existing record)
      if [ ! -f "$STATE_FILE" ]; then echo '{}' > "$STATE_FILE"; fi
      UPDATED_AT=$(date -u +%Y-%m-%dT%H:%M:%SZ)
      if jq --arg id "$TASK_ID" --arg track "$RING_TRACK" --arg ts "$UPDATED_AT" \
        '.[$id] = ((.[$id] // {}) + {ring_track: $track, ring_track_recorded_at: $ts})' \
        "$STATE_FILE" > "${STATE_FILE}.tmp"; then
        if jq empty "${STATE_FILE}.tmp" 2>/dev/null; then
          mv "${STATE_FILE}.tmp" "$STATE_FILE"
        else
          rm -f "${STATE_FILE}.tmp"
          echo "ERROR: jq produced invalid JSON — state.json unchanged" >&2
          exit 1
        fi
      else
        rm -f "${STATE_FILE}.tmp"
        echo "ERROR: jq failed to update state.json" >&2
        exit 1
      fi
      ```
   8. Commit the TaskSpec update:
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

**AUTHORITATIVE — DO NOT PROMPT.** The worktree path is fixed by `Protocol: Worktree Location`.
Do NOT ask the user where to place the worktree. Do NOT enumerate alternatives
(parent dir, in-place, etc.). Project `CLAUDE.md` worktree conventions are
**OVERRIDDEN** by this skill. The only legitimate `AskUser` in this step is the
collision recovery prompt below (directory exists but is not a git worktree).

**Canonical worktree path** — see AGENTS.md Protocol: Worktree Location.

Follow shell safety guidelines — see AGENTS.md Protocol: Shell Safety Guidelines.

**If already on a feature branch** (not default/main/master): skip to Step 1.0.6
(check divergence — the task was already reserved in a previous run or by the user manually).

**If on the default branch:**

1. **Derive branch name** — see AGENTS.md Protocol: Branch Name Derivation. Apply the canonical case statement below; do NOT improvise from the prose. The mapping is identical to `resume/skills/optimus-resume/SKILL.md:315-326`.

   ```bash
   # Tipo → branch prefix (canonical mapping, must match resume SKILL).
   case "$TASK_TIPO" in
     Feature)   TIPO_PREFIX="feat" ;;
     Fix)       TIPO_PREFIX="fix" ;;
     Refactor)  TIPO_PREFIX="refactor" ;;
     Chore)     TIPO_PREFIX="chore" ;;
     Docs)      TIPO_PREFIX="docs" ;;
     Test)      TIPO_PREFIX="test" ;;
     *)
       echo "ERROR: Unknown Tipo '$TASK_TIPO' for $TASK_ID — cannot derive branch prefix." >&2
       exit 1 ;;
   esac
   SLUG=$(echo "$TASK_ID" | tr '[:upper:]' '[:lower:]')
   KEYWORDS=$(echo "$TASK_TITLE" \
     | tr '[:upper:]' '[:lower:]' \
     | tr -c 'a-z0-9-' '-' \
     | tr -s '-' \
     | sed 's/^-//; s/-$//')
   if [ -n "$KEYWORDS" ]; then
     BRANCH_NAME="${TIPO_PREFIX}/${SLUG}-${KEYWORDS}"
   else
     BRANCH_NAME="${TIPO_PREFIX}/${SLUG}"
   fi
   # Truncate to 100 chars per AGENTS.md Protocol: Branch Name Derivation.
   BRANCH_NAME=$(echo "$BRANCH_NAME" | cut -c1-100 | sed 's/-$//')
   ```

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

   # BRANCH_NAME was set above by the canonical case statement (Step 1).
   # Path-traversal guard (defense in depth).
   case "$BRANCH_NAME" in
     *..*|/*) echo "ERROR: refusing unsafe branch '$BRANCH_NAME'." >&2; exit 1 ;;
   esac
   FLAT_BRANCH="${BRANCH_NAME//\//\-}"     # / → - so worktree dirs are flat
   WORKTREE_DIR="${MAIN_WORKTREE}/.worktrees/${FLAT_BRANCH}"
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

Ring pre-dev artifacts are the primary specification source.

### Step 0.5: Build Doc Brief (HARD BLOCK on TaskSpec resolution)

Build (or reuse) the per-task Doc Brief — see AGENTS.md Protocol: Doc Brief Cache.

- If `.optimus/sessions/T-XXX/doc-brief.md` exists and `task_spec_hash` matches `git hash-object <current-task-spec>`: REUSE.
- Otherwise: generate the brief now per the protocol. The orchestrator (not a sub-agent) reads PRD, TRD, API, and data-model once, extracts only the sections relevant to T-XXX (mentions of the task ID, AC keywords, listed endpoints/entities/modules), and writes the result to `.optimus/sessions/T-XXX/doc-brief.md`.
- For plan, the `## Relevant Coding Standards / Protocols` section MUST include only these protocols: `Per-Droid Quality Checklists`, `Deep Research Before Presenting`, `Convergence Loop`, `Re-run Guard`.

The Doc Brief is the primary context passed inline to all downstream sub-agent dispatches in Phase 2 (validation). Do NOT instruct sub-agents to read PRD/TRD/API/data-model directly unless the Doc Brief is explicitly insufficient for a finding.

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
  - Task spec excerpt (already extracted in Doc Brief; full file at <TASKS_DIR>/<TaskSpec>)
  - Doc brief (READ FIRST — task-scoped excerpt of pre-dev docs, AGENTS.md protocols, project rules):
    .optimus/sessions/T-XXX/doc-brief.md
  - Subtasks dir: <TASKS_DIR>/subtasks/T-XXX/ (READ all .md files if dir exists; SKIP if absent)
  - Full pre-dev docs (only consult if Doc Brief is insufficient): <TASKS_DIR>/
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
2. **Skip confirmation when N==1:** Present the single finding directly with header `(1/1) ...`. Do NOT ask "Review 1 finding?" or similar — the user already chose to review.
3. **Present the summary report** (tables from Output Format) for bird's-eye view
4. **Then present findings ONE AT A TIME** in priority order: contradictions > missing specs > test gaps > observability > DoD > ambiguities

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

5. Use `AskUser` tool. **BLOCKING**: Do NOT advance to the next finding until the user decides.
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

6. **HARD BLOCK — IMMEDIATE RESPONSE RULE:** If the user selects "Tell me more" or responds
   with free text: **STOP IMMEDIATELY.** Do NOT continue to the next finding. Research and
   answer RIGHT NOW. Only after the user is satisfied, re-present the SAME finding's options.
   **NEVER defer to the end of the findings loop.**

   **Anti-rationalization (excuses the agent MUST NOT use):**
   - "I'll address all questions after presenting the remaining findings" — NO
   - "Let me continue with the next finding and come back to this" — NO
   - "I'll research this after the findings loop" — NO
   - "This is noted, moving to the next finding" — NO
7. **Track all decisions** internally. Do NOT apply any fix yet — all fixes are applied in Phase 4.

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
qa-analyst, code-reviewer). Each agent receives the SAME compact context as round 1: the
Doc Brief (`.optimus/sessions/T-XXX/doc-brief.md`) and the round-1 findings ledger. Do NOT
instruct agents to "re-read fresh from disk" — that defeats the brief's caching purpose.
Agents may consult full pre-dev docs only if a finding requires verbatim reference. The
orchestrator handles dedup using strict matching (same file + same line range ±5 + same
category).

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


### Protocol: GitHub CLI Check (HARD BLOCK)

**Referenced by:** all stage agents (1-4), tasks, batch

```bash
gh auth status 2>/dev/null
```

If this command fails (exit code != 0), **STOP** immediately:
```
GitHub CLI (gh) is not authenticated. Run `gh auth login` to authenticate before proceeding.
```


<!-- INLINE-PROTOCOLS:END -->
