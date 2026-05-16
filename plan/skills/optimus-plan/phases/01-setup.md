# Phase 1 (Setup): Task Identification, Validation, and Workspace

Loaded by `SKILL.md` Phase 1 pointer. Covers Steps 1.0 through 1.0.7: GitHub CLI
check, task identification, terminal marking, status validation, dependency
checks, abandoned-workspace recovery, missing-spec self-heal, workspace
creation, divergence check, and stats increment.

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
  # badge does not render as a bare "PLAN" with no task context.
  TASK_TITLE="(title unavailable)"
fi

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

**On stage completion or exit**, restore the title:

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

> **Note:** the script is a silent no-op outside iTerm2/macOS or when the
> parent TTY cannot be resolved. The badge is informational — failure to
> mark must NOT block the stage flow.

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
