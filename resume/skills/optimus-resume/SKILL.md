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
    - state.json is untouched UNLESS the user explicitly picked "Reset to Pendente" in Step 3.3 Case 3
---

# Task Resumer

Administrative skill to retake a task after closing the terminal: resolves the worktree,
reports the current status, and offers to invoke the next stage. NEVER changes task status.

**Classification:** Administrative skill — runs on any branch. Does not modify `optimus-tasks.md`,
`stats.json`, or session files. Creates a worktree only as a recovery step when the branch
exists but its worktree is missing.

**State.json contract:** Resume is effectively **read-only** on `state.json`. The single
exception is the user-confirmed "Reset to Pendente" recovery option in Step 3.3 Case 3 —
which requires an explicit `AskUser` confirmation before running `jq 'del(.[$id])'` and
is clearly disclosed to the user.

**Override vs inlined protocol:** The inlined Protocol: State Management (auto-generated
below the shared-protocols block at the end of this file) contains destructive fallbacks —
`rm -f "$STATE_FILE"` on corruption and a one-time `Revisando PR → Validando Impl`
migration. **Resume explicitly DOES NOT apply those fallbacks**: on corruption it STOPs
with guidance (Step 2.2a), and it NEVER runs the migration. Treat the inlined block as
foundational context only; the rules in this body override it.

---

## Phase 1: Prerequisites

### Step 1.1: Check jq (HARD BLOCK)

```bash
command -v jq >/dev/null 2>&1
```

If `jq` is not available, **STOP**: "jq is required by /optimus-resume. Install it and retry."

### Step 1.2: Resolve and Validate optimus-tasks.md (HARD BLOCK)

Check tasks.md → optimus-tasks.md rename — see AGENTS.md Protocol: Rename tasks.md to optimus-tasks.md.

Find and validate optimus-tasks.md — see AGENTS.md Protocol: optimus-tasks.md Validation.

### Step 1.3: Reject Empty Tasks Table (HARD BLOCK)

AGENTS.md Format Validation item 15 requires checking for zero-data-row tables. A valid
but empty `optimus-tasks.md` would otherwise surface as a misleading "No in-progress tasks found"
message in Step 2.2.

```bash
# Step 1.2 resolved TASKS_FILE via Protocol: optimus-tasks.md Validation (which calls
# Protocol: Resolve Tasks Git Scope). If TASKS_FILE is unset here, that means
# Step 1.2 did NOT execute — surface the control-flow bug immediately instead
# of masking it with a silent fallback (which would produce misleading
# "docs/pre-dev/optimus-tasks.md not found" errors for users who customized tasksDir).
if [ -z "${TASKS_FILE:-}" ]; then
  echo "ERROR: TASKS_FILE is unset — Step 1.2 (optimus-tasks.md Validation) did not execute." >&2
  echo "Protocol: Resolve Tasks Git Scope must run before Step 1.3." >&2
  exit 1
fi
if [ ! -f "$TASKS_FILE" ]; then
  echo "ERROR: $TASKS_FILE not found. Run /optimus-import to create it."
  # STOP
fi
TASK_ROWS=$(grep -cE '^\| T-[0-9]+ \|' "$TASKS_FILE" || echo 0)
if ! [[ "$TASK_ROWS" =~ ^[0-9]+$ ]] || [ "$TASK_ROWS" -eq 0 ]; then
  echo "ERROR: No tasks found in $TASKS_FILE. Use /optimus-tasks to create a task or /optimus-import to import from Ring pre-dev."
  # STOP
fi
```

### Step 1.4: Validate state.json Integrity (HARD BLOCK) — Single Authoritative Check

All subsequent steps reference `$STATE_JSON` (cached) instead of re-reading or
re-validating `$STATE_FILE`. This is the ONLY place where resume does integrity checks
on state.json — downstream steps trust this.

```bash
# Resolve main worktree so .optimus/* paths are not isolated to a linked worktree.
# All .optimus/* state lives in the main worktree; linked worktrees do not propagate it.
MAIN_WORKTREE="$(git worktree list --porcelain 2>/dev/null | awk '/^worktree / {print $2; exit}')"
if [ -z "$MAIN_WORKTREE" ]; then
  echo "ERROR: Cannot determine main worktree — not in a git repository." >&2
  exit 1
fi

STATE_FILE="${MAIN_WORKTREE}/.optimus/state.json"
STATE_JSON=""
if [ -f "$STATE_FILE" ]; then
  if ! jq empty "$STATE_FILE" 2>/dev/null; then
    echo "ERROR: state.json is corrupted and cannot be parsed."
    echo "Resume is read-only and will NOT apply the destructive 'rm -f' recovery described in the inlined Protocol: State Management."
    echo "Run /optimus-tasks to rebuild the operational state, or restore state.json from backup."
    # STOP
  fi
  STATE_JSON=$(cat "$STATE_FILE")
fi
# STATE_JSON is now either valid JSON or the empty string (no state.json yet).
```

---

## Phase 2: Identify Task

### Step 2.1: Task ID Provided

If the user supplied an argument as the task ID, set `TASK_ID` to that value.

**Validate format (HARD BLOCK):**

```bash
if [ -z "$TASK_ID" ]; then
  echo "ERROR: TASK_ID is empty."
  # STOP
fi
if ! [[ "$TASK_ID" =~ ^T-[0-9]+$ ]]; then
  echo "ERROR: Malformed TASK_ID '$TASK_ID' — expected format T-NNN (e.g., T-001, T-042)."
  # STOP
fi
```

Verify the task exists in optimus-tasks.md:

```bash
grep -E "^\| ${TASK_ID} \|" "$TASKS_FILE" >/dev/null
```

If no match → **STOP**: `"Task ${TASK_ID} not found in optimus-tasks.md. Run /optimus-report to see available tasks."`

### Step 2.2: Auto-Detect (no ID provided)

Filter for a concrete non-terminal status (whitelist — prevents malformed `null`/missing
status entries from surfacing as resumable tasks). Order by `updated_at` descending
(most recent first) for stable UX.

```bash
if [ -z "$STATE_JSON" ]; then
  echo "ERROR: No state.json found and no task ID provided. Run /optimus-report to see the project status."
  # STOP
fi
IN_PROGRESS=$(printf '%s' "$STATE_JSON" | jq -r '
  to_entries
  | map(select(
      .value.status == "Validando Spec"
      or .value.status == "Em Andamento"
      or .value.status == "Validando Impl"
    ))
  | sort_by(.value.updated_at // "")
  | reverse
  | .[]
  | "\(.key)\t\(.value.status)\t\(.value.branch // "")\t\(.value.updated_at // "")"
')
```

- **If 0 tasks** → **STOP**: `"No in-progress tasks found. Run /optimus-report to see the project status, or /optimus-plan T-XXX to start a new task."`
- **If exactly 1 task** → use that ID as `TASK_ID` (no AskUser — resume does not change status, so there is no expanded-confirmation requirement).
- **If N tasks** → present via `AskUser` with one option per task (`T-XXX — <title> (<status>, updated <relative-time>)`) plus **Cancel**. Do NOT offer Resume/Start fresh/Continue.

### Step 2.3: Read Task Metadata (HARD BLOCK)

Extract task metadata from optimus-tasks.md. The agent MUST execute the bash snippet literally;
prose-level "capture TASK_TITLE…" is not sufficient because downstream steps consume the
vars directly.

```bash
# optimus-tasks.md columns by pipe index: | 1=<blank> | 2=ID | 3=Title | 4=Tipo | 5=Depends | 6=Priority | 7=Version | 8=Estimate | 9=TaskSpec | 10=<blank> |
TASK_ROW=$(awk -F'|' -v id="$TASK_ID" '
  { gsub(/^ +| +$/,"",$2) }
  $2 == id { print; exit }
' "$TASKS_FILE")

if [ -z "$TASK_ROW" ]; then
  echo "ERROR: Could not read row for $TASK_ID from $TASKS_FILE."
  # STOP
fi

_trim() { printf '%s' "$1" | sed -E 's/^[[:space:]]+//; s/[[:space:]]+$//'; }
TASK_TITLE=$(_trim   "$(printf '%s' "$TASK_ROW" | awk -F'|' '{print $3}')")
TASK_TIPO=$(_trim    "$(printf '%s' "$TASK_ROW" | awk -F'|' '{print $4}')")
TASK_DEPENDS=$(_trim "$(printf '%s' "$TASK_ROW" | awk -F'|' '{print $5}')")
TASK_VERSION=$(_trim "$(printf '%s' "$TASK_ROW" | awk -F'|' '{print $7}')")

for v in TASK_TITLE TASK_TIPO TASK_DEPENDS TASK_VERSION; do
  eval "val=\${$v}"
  if [ -z "$val" ]; then
    echo "ERROR: $v is empty for $TASK_ID (could not parse optimus-tasks.md row)."
    # STOP
  fi
done
```

Read operational state from the cached `STATE_JSON` (integrity already validated in
Step 1.4; no re-validation here):

```bash
if [ -n "$STATE_JSON" ]; then
  TASK_STATUS=$(printf '%s' "$STATE_JSON" | jq -r --arg id "$TASK_ID" '.[$id].status // "Pendente"')
  TASK_BRANCH=$(printf '%s' "$STATE_JSON" | jq -r --arg id "$TASK_ID" '.[$id].branch // ""')
else
  TASK_STATUS="Pendente"
  TASK_BRANCH=""
fi
```

### Step 2.4: Refuse Terminal Statuses

- If `TASK_STATUS` is `DONE` → **STOP**: `"Task ${TASK_ID} is already DONE. Nothing to resume. To reopen, use /optimus-tasks."`
- If `TASK_STATUS` is `Cancelado` → **STOP**: `"Task ${TASK_ID} is Cancelado. Reopen via /optimus-tasks before resuming."`

### Step 2.5: Dependency Check (informational)

To avoid recommending a next stage that the delegate would immediately refuse (Rule 6 in
AGENTS.md Task Lifecycle), compute whether all `TASK_DEPENDS` are `DONE`. This does NOT
block resume itself — the user may still want to inspect the workspace — but it constrains
the Phase 5 options.

Step 2.3 guarantees `TASK_DEPENDS` is non-empty (either `-` or a comma-separated list of
`T-NNN`), so a bare `[ -z "$TASK_DEPENDS" ]` here would indicate a contract violation.

```bash
BLOCKING_DEPS=""
if [ -z "$TASK_DEPENDS" ]; then
  echo "ERROR: TASK_DEPENDS empty after Step 2.3 — contract violation."
  # STOP
fi
if [ "$TASK_DEPENDS" != "-" ]; then
  # Build a JSON array of dep IDs (trimmed). Single jq pass resolves all statuses.
  DEPS_JSON=$(printf '%s' "$TASK_DEPENDS" | jq -Rc '
    split(",") | map(gsub("^\\s+|\\s+$"; "")) | map(select(length > 0))
  ')
  BLOCKING_DEPS=$(printf '%s' "${STATE_JSON:-{}}" | jq -r --argjson deps "$DEPS_JSON" '
    [ $deps[] as $d
      | { id: $d, status: (.[$d].status // "Pendente") }
      | select(.status != "DONE")
      | "\(.id) (\(.status))"
    ] | join(", ")
  ')
fi
```

If `BLOCKING_DEPS` is non-empty, Phase 5 will **replace** the stage options with
`Skip` + `Run /optimus-report` and surface a warning in the Phase 4 summary
(see Step 4.2).

---

## Phase 3: Resolve Workspace

### Step 3.1: Derive Expected Branch

Prefer the `branch` field from state.json. If empty, derive the expected branch name
from Tipo + ID + Title per AGENTS.md Protocol: Branch Name Derivation.

```bash
# Sanitize title slug; the "2-4 words" guideline in AGENTS.md Protocol: Branch Name
# Derivation is advisory, not enforced — the full sanitized slug is accepted.
if [ -z "$TASK_BRANCH" ]; then
  case "$TASK_TIPO" in
    Feature)   TIPO_PREFIX="feat" ;;
    Fix)       TIPO_PREFIX="fix" ;;
    Refactor)  TIPO_PREFIX="refactor" ;;
    Chore)     TIPO_PREFIX="chore" ;;
    Docs)      TIPO_PREFIX="docs" ;;
    Test)      TIPO_PREFIX="test" ;;
    *)
      echo "ERROR: Unknown Tipo '$TASK_TIPO' for $TASK_ID — cannot derive branch prefix."
      # STOP
      ;;
  esac
  SLUG=$(echo "$TASK_ID" | tr '[:upper:]' '[:lower:]')
  KEYWORDS=$(echo "$TASK_TITLE" \
    | tr '[:upper:]' '[:lower:]' \
    | tr -c 'a-z0-9-' '-' \
    | tr -s '-' \
    | sed 's/^-//; s/-$//')
  if [ -n "$KEYWORDS" ]; then
    TASK_BRANCH="${TIPO_PREFIX}/${SLUG}-${KEYWORDS}"
  else
    TASK_BRANCH="${TIPO_PREFIX}/${SLUG}"
  fi
  # Truncate to 100 chars per protocol
  TASK_BRANCH=$(echo "$TASK_BRANCH" | cut -c1-100 | sed 's/-$//')
fi

if [ -z "$TASK_BRANCH" ]; then
  echo "ERROR: TASK_BRANCH is empty after derivation for $TASK_ID — cannot proceed."
  # STOP
fi
```

### Step 3.2: Look Up Worktree

**Hard guard (HARD BLOCK):** an empty or malformed `TASK_ID` would make the regex
`tolower(wt) ~ ""` match every worktree (the primary repo first), silently leading the
user into implementing on `main`. Refuse before querying git.

```bash
if [ -z "$TASK_ID" ] || ! [[ "$TASK_ID" =~ ^T-[0-9]+$ ]]; then
  echo "ERROR: Invalid TASK_ID '$TASK_ID' at Step 3.2. Refusing worktree lookup to avoid matching main repo."
  # STOP
fi

# Use awk's literal index() (not regex ~) so a future relaxation of the TASK_ID format
# (e.g., alphanumeric suffix) does not suddenly change semantics through regex metachars.
WORKTREE_PATH=$(git worktree list --porcelain 2>/dev/null \
  | awk -v id="$(echo "$TASK_ID" | tr '[:upper:]' '[:lower:]')" '
      BEGIN { if (id == "") exit 1 }
      /^worktree / { wt=$2 }
      /^branch /   { if (index(tolower(wt), id) > 0 || index(tolower($2), id) > 0) print wt }
    ' | head -1)

if [ -z "$WORKTREE_PATH" ]; then
  # Fallback: literal task-ID search. The Step 3.2 hard guard above already refused empty
  # TASK_ID, so grep -F has a non-empty pattern here.
  WORKTREE_PATH=$(git worktree list | grep -iF "$TASK_ID" | awk '{print $1}' | head -1)
fi
```

### Step 3.3: Apply Resolution Order

1. **Worktree found** → `cd "$WORKTREE_PATH"` for the rest of the session. Continue to Phase 4.

2. **Worktree missing, branch exists locally** (`git rev-parse --verify "$TASK_BRANCH" >/dev/null 2>&1` succeeds):

   **Hard guards (HARD BLOCK) BEFORE attempting `git worktree add`:**

   ```bash
   PROJECT_ROOT=$(git rev-parse --show-toplevel 2>/dev/null)
   if [ -z "$PROJECT_ROOT" ]; then
     echo "ERROR: Not inside a git repository — cannot recover worktree."
     # STOP
   fi
   REPO_NAME=$(basename "$PROJECT_ROOT")
   if [ -z "$REPO_NAME" ]; then
     echo "ERROR: Empty repo name derived from '$PROJECT_ROOT'."
     # STOP
   fi
   # Belt-and-suspenders: upstream guards (Step 2.1, Step 3.1, Step 3.2) already validated
   # these, but we are at a filesystem-mutation boundary — refuse one more time.
   if [ -z "$TASK_ID" ] || [ -z "$TASK_BRANCH" ]; then
     echo "ERROR: TASK_ID or TASK_BRANCH empty before 'git worktree add'. Refusing."
     # STOP
   fi

   SLUG=$(echo "$TASK_ID" | tr '[:upper:]' '[:lower:]')
   SANITIZED_TITLE=$(echo "$TASK_TITLE" | tr '[:upper:]' '[:lower:]' \
     | tr -c 'a-z0-9-' '-' | tr -s '-' | sed 's/^-//;s/-$//' | cut -c1-40)
   # No trailing dash when sanitized title is empty
   if [ -n "$SANITIZED_TITLE" ]; then
     WORKTREE_DIR="../${REPO_NAME}-${SLUG}-${SANITIZED_TITLE}"
   else
     WORKTREE_DIR="../${REPO_NAME}-${SLUG}"
   fi

   # HARD BLOCK on git worktree add failure (dir exists, branch checked out elsewhere, etc.)
   if ! git worktree add "$WORKTREE_DIR" "$TASK_BRANCH"; then
     echo "ERROR: 'git worktree add $WORKTREE_DIR $TASK_BRANCH' failed."
     echo "       Possible causes: directory exists, branch checked out elsewhere, or local repo state."
     # STOP
   fi
   WORKTREE_PATH="$WORKTREE_DIR"
   if ! cd "$WORKTREE_PATH"; then
     echo "ERROR: cd to $WORKTREE_PATH failed after successful worktree creation."
     # STOP
   fi
   ```

3. **Worktree missing AND branch missing:**
   - **If status is `Pendente` or has no state.json entry:** present via `AskUser`:
     ```
     Task T-XXX has no worktree and no branch yet — it has not been through /optimus-plan.
     Run /optimus-plan T-XXX now?
     ```
     Options:
     - **Yes, invoke /optimus-plan** — invoke the `optimus-plan` skill via the `Skill`
       tool. The conversation context carries `TASK_ID`; the delegate will locate the
       task and run its own expanded confirmation. Resume does NOT bypass the delegate's
       validation.
     - **Cancel** — **STOP** with: `"No workspace for T-XXX. Run /optimus-plan T-XXX when ready."`

   - **If status is in-progress but branch is missing (inconsistent state):**

     Present via `AskUser` with two options. The first is a **user-confirmed recovery**
     that mutates state.json — the only place where resume writes state. The second is
     a plain abort. A "Re-run /optimus-plan" option without first resetting is **not
     offered**: `/optimus-plan`'s anti-pulo rejects any status other than `Pendente` /
     `Validando Spec`, so it would immediately STOP.

     ```
     Inconsistency: T-XXX has status <status> but branch <$TASK_BRANCH> does not exist.
     Possible recovery:
     ```
     Options:
     - **Reset to Pendente, then run /optimus-plan** — resume performs a user-confirmed
       `jq del(.[$id])` on state.json (the ONE exception to resume's read-only contract),
       clearing the task back to implicit Pendente. Then the agent invokes `optimus-plan`
       via the `Skill` tool; plan's anti-pulo now accepts the task and will recreate the
       workspace. Implemented as:

       ```bash
       # MAIN_WORKTREE was resolved in Step 1.4; reuse it. If somehow unset, abort
       # rather than writing into an isolated linked-worktree copy.
       if [ -z "${MAIN_WORKTREE:-}" ]; then
         echo "ERROR: MAIN_WORKTREE is unset — Step 1.4 must run before Step 3.3 Case 3 reset." >&2
         exit 1
       fi
       STATE_FILE="${MAIN_WORKTREE}/.optimus/state.json"
       RESET_DONE=0
       # STATE_JSON is already validated in Step 1.4, so STATE_FILE is guaranteed to exist
       # and be parseable here (guarded upstream — no re-validation needed).
       if jq --arg id "$TASK_ID" 'del(.[$id])' "$STATE_FILE" > "${STATE_FILE}.tmp"; then
         if jq empty "${STATE_FILE}.tmp" 2>/dev/null; then
           mv "${STATE_FILE}.tmp" "$STATE_FILE"
           RESET_DONE=1
           echo "state.json: removed entry for $TASK_ID (reset to Pendente)."
         else
           rm -f "${STATE_FILE}.tmp"
           echo "ERROR: jq produced invalid JSON — state.json unchanged."
           # STOP
         fi
       else
         rm -f "${STATE_FILE}.tmp"
         echo "ERROR: jq failed to update state.json."
         # STOP
       fi
       if [ "$RESET_DONE" -eq 1 ]; then
         echo "T-$TASK_ID has been reset to Pendente. Invoking /optimus-plan via the Skill tool..."
         # Then delegate to the optimus-plan skill via the Skill tool.
       else
         echo "T-$TASK_ID remains in its pre-existing state — no reset applied."
         # STOP
       fi
       ```

     - **Abort** — **STOP** with: `"Inconsistency not resolved. Investigate via /optimus-tasks edit T-$TASK_ID before retrying."`

### Step 3.4: Dry-Run Short-Circuit

If the user invoked a dry-run (e.g., "dry-run resume T-XXX", "preview resume"):

- Perform Steps 3.1–3.2 normally (read-only)
- Do NOT run `git worktree add`
- Do NOT `cd`
- Do NOT run the Step 3.3 Case 3 "Reset to Pendente, then /optimus-plan" recovery — if
  reached, STOP with: `"dry-run: no recovery attempted. Re-run without dry-run to repair state."`
- Do NOT delegate to any other skill (no `Skill` tool invocation)
- Proceed to Phase 4 and label the summary as **(dry-run, no changes applied)**
- Skip Phase 5 entirely

---

## Phase 4: Set Terminal Title and Report

### Step 4.1: Set Terminal Title

Set terminal title — see AGENTS.md Protocol: Terminal Identification. Use stage label `RESUME`:

```bash
_optimus_set_title() {
  local title="$1"
  local pid="$PPID" tty=""
  for _ in 1 2 3 4; do
    [ -z "$pid" ] || [ "$pid" = "1" ] && break
    tty=$(ps -o tty= -p "$pid" 2>/dev/null | tr -d ' ')
    case "$tty" in
      ""|"?"|"??") pid=$(ps -o ppid= -p "$pid" 2>/dev/null | tr -d ' ') ;;
      *) break ;;
    esac
  done
  if { [ "$LC_TERMINAL" = "iTerm2" ] || [ "$TERM_PROGRAM" = "iTerm.app" ]; } \
     && command -v osascript >/dev/null 2>&1 && [ -n "$tty" ] \
     && [ "$tty" != "?" ] && [ "$tty" != "??" ]; then
    osascript \
      -e 'on run argv' \
      -e '  set targetTty to "/dev/" & item 1 of argv' \
      -e '  set newName to item 2 of argv' \
      -e '  tell application "iTerm2"' \
      -e '    repeat with w in windows' \
      -e '      repeat with t in tabs of w' \
      -e '        repeat with s in sessions of t' \
      -e '          if (tty of s as string) is targetTty then' \
      -e '            try' \
      -e '              set name of s to newName' \
      -e '            end try' \
      -e '          end if' \
      -e '        end repeat' \
      -e '      end repeat' \
      -e '    end repeat' \
      -e '  end tell' \
      -e 'end run' \
      -- "$tty" "$title" >/dev/null 2>&1 || true
  fi
}
_optimus_set_title "optimus: RESUME $TASK_ID — $TASK_TITLE"
```

**On exit or after Phase 5 delegates to another stage skill**, restore the title:

```bash
_optimus_set_title ""
```

### Step 4.2: Collect Worktree Telemetry

With `cd` into the worktree already done, gather read-only signals the user will want
to see at a glance. All commands are silent-on-failure so a new/unusual repo layout
degrades gracefully rather than blocking the summary.

All telemetry vars are pre-initialized to stable defaults OUTSIDE the conditionals so
consumers never touch an unset variable under `set -u`.

```bash
# Pre-initialize all telemetry vars (consistent convention)
GIT_UNCOMMITTED=0
GIT_UNPUSHED=-1           # -1 sentinel: numeric-safe for arithmetic, "unknown" for humans
GIT_BEHIND=-1
GIT_UPSTREAM_OK=0         # 0 = no upstream; 1 = upstream available
SESSION_INFO=""
STATS_INFO=""
PR_INFO=""
PR_STATE="UNKNOWN"        # Sentinel for "neither NONE nor a concrete gh state"

# Git status of the worktree
GIT_UNCOMMITTED=$(git status --porcelain 2>/dev/null | wc -l | tr -d ' ')
if git rev-parse --abbrev-ref '@{u}' >/dev/null 2>&1; then
  GIT_UPSTREAM_OK=1
  GIT_UNPUSHED=$(git log @{u}..HEAD --oneline 2>/dev/null | wc -l | tr -d ' ')
  GIT_BEHIND=$(git rev-list HEAD..@{u} --count 2>/dev/null || echo -1)
fi

# MAIN_WORKTREE resolved in Step 1.4 — reuse for .optimus/* lookups so we do not
# read a stale or empty copy isolated to the current linked worktree.
if [ -z "${MAIN_WORKTREE:-}" ]; then
  echo "ERROR: MAIN_WORKTREE is unset — Step 1.4 must run before Step 4.2." >&2
  exit 1
fi

# Session file for this task (crash-recovery data from a stage skill)
SESSION_FILE="${MAIN_WORKTREE}/.optimus/sessions/session-${TASK_ID}.json"
if [ -f "$SESSION_FILE" ] && jq empty "$SESSION_FILE" 2>/dev/null; then
  SESSION_INFO=$(jq -r '"stage=\(.stage // "?"), phase=\(.phase // "?"), round=\(.convergence_round // 0), updated=\(.updated_at // "?")"' "$SESSION_FILE")
fi

# Stats.json churn signal — single jq pass for both counters + numeric-safe coercion
STATS_FILE="${MAIN_WORKTREE}/.optimus/stats.json"
PLAN_RUNS=0
REVIEW_RUNS=0
if [ -f "$STATS_FILE" ]; then
  STATS_PAIR=$(jq -r --arg id "$TASK_ID" '
    "\((.[$id].plan_runs // 0) | tonumber? // 0 | floor) \((.[$id].review_runs // 0) | tonumber? // 0 | floor)"
  ' "$STATS_FILE" 2>/dev/null)
  if [ -n "$STATS_PAIR" ]; then
    read -r PLAN_RUNS REVIEW_RUNS <<< "$STATS_PAIR"
  fi
  [[ "$PLAN_RUNS"   =~ ^[0-9]+$ ]] || PLAN_RUNS=0
  [[ "$REVIEW_RUNS" =~ ^[0-9]+$ ]] || REVIEW_RUNS=0
  if [ "$PLAN_RUNS" -ge 2 ] || [ "$REVIEW_RUNS" -ge 2 ]; then
    STATS_INFO="plan_runs=${PLAN_RUNS}, review_runs=${REVIEW_RUNS}"
    if [ "$PLAN_RUNS" -ge 3 ] || [ "$REVIEW_RUNS" -ge 3 ]; then
      STATS_INFO="${STATS_INFO} (possible churn)"
    fi
  fi
fi

# PR state for the task branch — three-state result:
#   NONE    = gh confirmed no PR exists
#   OPEN / CLOSED / MERGED = concrete gh state
#   UNKNOWN = gh unavailable, unauthenticated, or transient error (network/rate-limit)
# UNKNOWN must suppress PR-based recommendations in Step 4.4.
if command -v gh >/dev/null 2>&1; then
  if gh auth status >/dev/null 2>&1; then
    if PR_JSON=$(gh pr view "$TASK_BRANCH" --json number,state,title,url 2>/dev/null); then
      if [ -n "$PR_JSON" ]; then
        # Single jq pass extracting both state and summary line
        PR_DATA=$(printf '%s' "$PR_JSON" | jq -r '
          "\(.state // "UNKNOWN")\t#\(.number // "?") \(.state // "?") — \(.title // "?")"
        ')
        PR_STATE=$(printf '%s' "$PR_DATA" | awk -F'\t' '{print $1}')
        PR_INFO=$(printf '%s' "$PR_DATA" | awk -F'\t' '{print $2}')
      else
        PR_STATE="NONE"
      fi
    else
      PR_STATE="UNKNOWN (gh pr view failed — possibly network/rate-limit)"
    fi
  else
    PR_STATE="UNKNOWN (gh not authenticated)"
  fi
else
  PR_STATE="UNKNOWN (gh not available)"
fi
```

### Step 4.3: Print Summary

Emit a `<json-render>` block with the resume summary. Include:

- Heading: `Resume T-XXX`
- KeyValue rows: **Title, Version, Status, Depends, Branch, Worktree**
- KeyValue rows (when non-empty): **PR, Session, Stats, Uncommitted, Unpushed, Behind upstream**
- StatusLine: success — `Workspace ready` (or a warning StatusLine if dry-run, or a
  warning StatusLine if `BLOCKING_DEPS` is non-empty)
- Callout with the shell command the user must run in their own terminal to change cwd:
  `cd <absolute-worktree-path>`

**Surface blocking deps.** If `BLOCKING_DEPS` is non-empty, add a warning Callout:
```
Next stage is BLOCKED — T-XXX depends on: <BLOCKING_DEPS>.
Review these dependencies first via /optimus-report.
```

**IMPORTANT:** Print the absolute path. The Droid session's internal `cd` does NOT change
the user's interactive shell cwd — the user must run `cd` themselves to have their shell
match. Subsequent tool calls in this Droid session will still use the internal cwd.

### Step 4.4: Next-Stage Recommendation

Map current status + PR state to the recommended next command:

| Current status     | PR state                      | Next recommended                               |
|--------------------|-------------------------------|------------------------------------------------|
| `Validando Spec`   | any                           | `/optimus-build`                               |
| `Em Andamento`     | any                           | `/optimus-review` (or re-run `/optimus-build`) |
| `Validando Impl`   | OPEN                          | `/optimus-pr-check` (then `/optimus-done`)     |
| `Validando Impl`   | MERGED / CLOSED               | `/optimus-done` (or re-run `/optimus-review`)  |
| `Validando Impl`   | NONE                          | `/optimus-done` (will require a PR — create one first) |
| `Validando Impl`   | UNKNOWN (gh failure)          | **Suppressed** — show warning: "PR state could not be determined; inspect the branch manually before choosing /optimus-done or /optimus-pr-check." |

Show the chosen recommendation in the summary. When `PR_STATE` starts with `UNKNOWN`,
the Phase 5 options must also omit any stage that depends on PR state (see Phase 5).

---

## Phase 5: Offer Next Stage

Ask the user via `AskUser`:

```
Next step for T-XXX (<status>):
```

**Dependency-aware options.** If `BLOCKING_DEPS` is non-empty, the stage options are
hidden — delegating would fail immediately on the dependency gate. Offer only:

- **Run /optimus-report** — to review the blocking dependencies.
- **Skip** — workspace is ready; user decides how to proceed.

**PR-state suppressor.** If `PR_STATE` starts with `UNKNOWN` (gh failure: unavailable,
unauthenticated, network/rate-limit), the `Validando Impl` options collapse to:

- **Re-run /optimus-review** / **Skip**

The user is asked to investigate gh before picking a stage that depends on PR state.

Otherwise (no blocking deps, PR state known), options are chosen from status + PR state:

- `Validando Spec`: **Run /optimus-build** / **Skip**
- `Em Andamento`: **Run /optimus-review** / **Re-run /optimus-build** / **Skip**
- `Validando Impl` + PR OPEN: **Run /optimus-pr-check** / **Run /optimus-done** / **Re-run /optimus-review** / **Skip**
- `Validando Impl` + PR MERGED/CLOSED: **Run /optimus-done** / **Re-run /optimus-review** / **Skip**
- `Validando Impl` + no PR (NONE): **Run /optimus-done** (will likely require a PR) / **Re-run /optimus-review** / **Skip**

**Skill tool contract (accurate wording).** If the user picks a stage, invoke the
corresponding skill via the `Skill` tool (e.g., `optimus-build`, `optimus-pr-check`,
`optimus-done`). The `Skill` tool accepts only the skill name — it has no argument
channel for `TASK_ID`. The delegate will locate the task from the conversation context
and run its own expanded confirmation via `AskUser` (it does NOT skip this step).
Resume does NOT bypass any predecessor checks the delegate performs.

**If the user picks Skip:** inform them the workspace is ready and they can run the
recommended command whenever they like.

**Skip the whole Phase 5 step** when running in dry-run mode.

---

## Rules

- **Admin skill** — runs on any branch, does not alter task status.
- NEVER writes to `stats.json`, `optimus-tasks.md`, or `.optimus/sessions/session-T-XXX.json`.
- **state.json is read-only EXCEPT** for the user-confirmed "Reset to Pendente" recovery
  option in Step 3.3 Case 3 (inconsistent state). No other mutation is permitted.
- Creates a worktree ONLY in the recovery path (Step 3.3 case 2). Never creates branches.
- Does NOT offer `Resume / Start fresh / Continue` prompts (coherent with `/optimus-done`).
- Does NOT invoke another stage automatically — only when the user explicitly picks it in Phase 5.
- Respects dry-run mode: no worktree creation, no delegation to other skills, no mutation of state.json.
- Does NOT run `make lint` / `make test` — verification is the responsibility of the target stage.
- **Skill tool contract:** when delegating to another skill, invoke it via the `Skill` tool;
  the `Skill` tool has no argument channel, so `TASK_ID` is carried by conversation context.
  The delegate will perform its own expanded-confirmation via `AskUser`. Resume does NOT
  bypass any predecessor checks.

### Anti-rationalization

The agent MUST NOT use these excuses to skip or reorder steps:

- "I know the worktree path, I'll just cd manually" — the skill still needs to validate the task and render the summary.
- "The user clearly wants /optimus-build, let me just run it" — wait for the Phase 5 AskUser decision.
- "state.json is missing or corrupted, let me `rm -f` to recover" — NO. The inlined Protocol
  does that, but resume explicitly overrides it: STOP and ask the user to fix state.json.
- "state.json is missing, let me infer from git worktree list" — that triggers the reconciliation guidance in State Management, not a silent recovery.
- "The branch exists but the name differs from the derivation, close enough" — prefer the state.json branch field; do not use fuzzy matches silently.
- "TASK_ID is empty but the only worktree is the right one" — NO. An empty TASK_ID is a HARD BLOCK; refuse before touching git.
- "I'll skip the dependency check because the user will figure it out" — NO. If BLOCKING_DEPS is non-empty, hide the stage options and surface the warning.

<!-- INLINE-PROTOCOLS:START -->
## Shared Protocols (from AGENTS.md)

The following protocols are referenced by this skill. They are
extracted from the Optimus AGENTS.md to make this plugin self-contained.

### Format Validation

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
running `/optimus-import` to fix the format. Do NOT attempt to interpret malformed data.

14. No unescaped pipe characters (`|`) in task titles (breaks markdown table parsing)
15. **Empty table handling:** If the tasks table exists but has zero data rows (only headers),
format validation PASSES. Stage agents (1-4) MUST check for this condition immediately after
format validation and before task identification. If zero data rows: **STOP** and inform the
user: "No tasks found in optimus-tasks.md. Use `/optimus-tasks` to create a task or `/optimus-import`
to import from Ring pre-dev." Do NOT proceed to task identification with an empty table.

**NOTE:** For circular dependency detection (item 13), trace the full dependency chain for
each task. If any task appears twice in the chain, a cycle exists. Report ALL tasks involved
in the cycle so the user can fix it with `/optimus-tasks`.


### Protocol: Resolve Tasks Git Scope

**Referenced by:** all stage agents (1-4), tasks, batch, resolve, import, resume, report, quick-report

Resolves `TASKS_DIR` (Ring pre-dev root) and `TASKS_FILE` (`<tasksDir>/optimus-tasks.md`), then
detects whether `tasksDir` lives in the same git repo as the project code or in a
**separate** git repo. Exposes a `tasks_git` helper function so skills can run git
commands on optimus-tasks.md uniformly regardless of scope.

```bash
# Step 0: Resolve main worktree — see AGENTS.md Protocol: Resolve Main Worktree Path.
# Required because .optimus/config.json is gitignored and lives only in the main
# worktree's filesystem; resolving it relative to PWD would miss it from a linked
# worktree.
MAIN_WORKTREE="$(git worktree list --porcelain 2>/dev/null | awk '/^worktree / {print $2; exit}')"
if [ -z "$MAIN_WORKTREE" ]; then
  echo "ERROR: Cannot determine main worktree — not in a git repository." >&2
  exit 1
fi
# Step 1: Resolve tasksDir from config.json (if present) or fall back to default.
CONFIG_FILE="${MAIN_WORKTREE}/.optimus/config.json"
if [ -f "$CONFIG_FILE" ] && jq empty "$CONFIG_FILE" 2>/dev/null; then
  TASKS_DIR=$(jq -r '.tasksDir // "docs/pre-dev"' "$CONFIG_FILE")
else
  TASKS_DIR="docs/pre-dev"
fi
# Reject "null" (jq -r prints literal "null" for JSON null) or empty string.
case "$TASKS_DIR" in
  ""|"null") TASKS_DIR="docs/pre-dev" ;;
esac
# Security: reject TASKS_DIR values starting with "-" (git option injection via
# `git -C --exec-path=...` or similar). Trust boundary: config.json is now gitignored,
# but a user could still receive a malicious config via Slack/email.
case "$TASKS_DIR" in
  -*)
    echo "ERROR: tasksDir cannot start with '-' (security)." >&2
    exit 1
    ;;
esac

# Step 2: Derive TASKS_FILE.
TASKS_FILE="${TASKS_DIR}/optimus-tasks.md"

# Step 3: Detect git scope.
PROJECT_ROOT=$(git rev-parse --show-toplevel 2>/dev/null)
if [ -z "$PROJECT_ROOT" ]; then
  echo "ERROR: Not inside a git repository — optimus requires git." >&2
  exit 1
fi

TASKS_REPO_ROOT=""
if [ -d "$TASKS_DIR" ]; then
  TASKS_REPO_ROOT=$(git -C "$TASKS_DIR" rev-parse --show-toplevel 2>/dev/null || echo "")
fi

if [ -z "$TASKS_REPO_ROOT" ]; then
  if [ -d "$TASKS_DIR" ]; then
    # Directory exists but is NOT inside a git repository — this is a
    # misconfiguration. Without this guard, operations would silently target
    # the project repo and fail confusingly.
    echo "ERROR: tasksDir '$TASKS_DIR' exists but is not inside a git repository." >&2
    echo "Options:" >&2
    echo "  1. Initialize git in tasksDir: git -C \"$TASKS_DIR\" init" >&2
    echo "  2. Point tasksDir to an existing git repo." >&2
    echo "  3. Remove tasksDir to let optimus create it inside the project repo." >&2
    exit 1
  fi
  # Fresh project: tasksDir does not exist yet — assume same-repo.
  # Skills that create optimus-tasks.md will mkdir -p "$TASKS_DIR" first.
  TASKS_GIT_SCOPE="same-repo"
elif [ "$TASKS_REPO_ROOT" = "$PROJECT_ROOT" ]; then
  TASKS_GIT_SCOPE="same-repo"
else
  TASKS_GIT_SCOPE="separate-repo"
fi

# Step 4: Compute the path to pass to git commands.
# In same-repo, git runs from project root and we pass TASKS_FILE as is.
# In separate-repo, git runs with -C "$TASKS_DIR" so paths are relative to TASKS_DIR.
if [ "$TASKS_GIT_SCOPE" = "separate-repo" ]; then
  # python3 is REQUIRED in separate-repo mode to compute the path from the tasks
  # repo root. A naive "optimus-tasks.md" fallback would be wrong when TASKS_DIR is a
  # subdir of the tasks repo (e.g., `tasks-repo/project-alfa/`), because
  # `git show origin/main:optimus-tasks.md` resolves from repo root, not CWD.
  if ! command -v python3 >/dev/null 2>&1; then
    echo "ERROR: python3 is required for separate-repo mode (path computation)." >&2
    echo "Install python3 or point tasksDir inside the project repo." >&2
    exit 1
  fi
  TASKS_GIT_REL=$(python3 -c "import os,sys; print(os.path.relpath(sys.argv[1], sys.argv[2]))" \
    "$TASKS_FILE" "$TASKS_REPO_ROOT" 2>/dev/null)
  if [ -z "$TASKS_GIT_REL" ]; then
    echo "ERROR: Failed to compute TASKS_GIT_REL for '$TASKS_FILE' relative to '$TASKS_REPO_ROOT'." >&2
    exit 1
  fi
else
  TASKS_GIT_REL="$TASKS_FILE"
fi

# Step 5: Resolve the tasks repo's default branch once (used by tasks_git
# operations that reference origin/$DEFAULT). This is DIFFERENT from
# $DEFAULT_BRANCH (the project repo's default).
if [ "$TASKS_GIT_SCOPE" = "separate-repo" ]; then
  TASKS_DEFAULT_BRANCH=$(git -C "$TASKS_DIR" symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's@^refs/remotes/origin/@@')
  if [ -z "$TASKS_DEFAULT_BRANCH" ]; then
    # Fallback: check origin/main vs origin/master existence (deterministic,
    # unlike `git branch --list main master` which can return either arbitrarily).
    if git -C "$TASKS_DIR" show-ref --verify refs/remotes/origin/main >/dev/null 2>&1; then
      TASKS_DEFAULT_BRANCH="main"
    elif git -C "$TASKS_DIR" show-ref --verify refs/remotes/origin/master >/dev/null 2>&1; then
      TASKS_DEFAULT_BRANCH="master"
    fi
  fi
else
  TASKS_DEFAULT_BRANCH=$(git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's@^refs/remotes/origin/@@')
  if [ -z "$TASKS_DEFAULT_BRANCH" ]; then
    if git show-ref --verify refs/remotes/origin/main >/dev/null 2>&1; then
      TASKS_DEFAULT_BRANCH="main"
    elif git show-ref --verify refs/remotes/origin/master >/dev/null 2>&1; then
      TASKS_DEFAULT_BRANCH="master"
    fi
  fi
fi

# Security: reject malformed branch names (prevents injection via
# `git diff origin/<weird>`).
if [ -n "$TASKS_DEFAULT_BRANCH" ] && ! [[ "$TASKS_DEFAULT_BRANCH" =~ ^[a-zA-Z0-9._/-]+$ ]]; then
  echo "ERROR: Invalid TASKS_DEFAULT_BRANCH format: '$TASKS_DEFAULT_BRANCH'" >&2
  exit 1
fi

# Step 6: Define the tasks_git helper.
tasks_git() {
  if [ "$TASKS_GIT_SCOPE" = "separate-repo" ]; then
    git -C "$TASKS_DIR" "$@"
  else
    git "$@"
  fi
}
```

**Usage:**
```bash
tasks_git add "$TASKS_GIT_REL"
tasks_git commit -F "$COMMIT_MSG_FILE"
# IMPORTANT: use $TASKS_DEFAULT_BRANCH (tasks repo default) — NOT $DEFAULT_BRANCH
# (project repo default). They are the same in same-repo mode but may differ in
# separate-repo mode (e.g., tasks repo is `master`, project repo is `main`).
tasks_git diff "origin/$TASKS_DEFAULT_BRANCH" -- "$TASKS_GIT_REL"
tasks_git show "origin/$TASKS_DEFAULT_BRANCH:$TASKS_GIT_REL"
```

**Rule:** Skills MUST use `tasks_git` (never raw `git`) when operating on `$TASKS_FILE`.
Raw `git` on `$TASKS_FILE` breaks in separate-repo mode.

**Rule:** When committing in separate-repo mode, commits land in the tasks repo (not the
project repo). `tasks_git push` pushes the tasks repo. The project repo is unaffected.

Skills reference this as: "Resolve tasks git scope — see AGENTS.md Protocol: Resolve Tasks Git Scope."


### Protocol: Resolve Main Worktree Path

**Referenced by:** all skills that read or write `.optimus/` operational files (state.json, stats.json, sessions, reports, logs, and checkpoint markers).

**Why:** `.optimus/` is gitignored. Git does NOT propagate ignored files across linked worktrees (`git worktree add` creates a sibling working tree but does not share gitignored files). When a skill runs from a linked worktree (the common case for `/optimus-build`, `/optimus-review`, `/optimus-done` which default to the task's worktree), reads and writes against `.optimus/state.json` resolve to the worktree's isolated copy. Updates never reach the main worktree. When the linked worktree is later removed (e.g., by `/optimus-done` cleanup), the writes are lost — silent data loss.

**Recipe:**

```bash
MAIN_WORKTREE="$(git worktree list --porcelain 2>/dev/null | awk '/^worktree / {print $2; exit}')"
if [ -z "$MAIN_WORKTREE" ]; then
  echo "ERROR: Cannot determine main worktree — not in a git repository." >&2
  exit 1
fi
```

The first `worktree` line in `git worktree list --porcelain` is always the main worktree (where the bare `.git/` directory or the repo's HEAD lives), regardless of where the command is run from.

**Path resolution pattern:**

After resolving `MAIN_WORKTREE`, every `.optimus/` path MUST be prefixed:

```bash
# RIGHT (works from any worktree):
STATE_FILE="${MAIN_WORKTREE}/.optimus/state.json"
SESSION_FILE="${MAIN_WORKTREE}/.optimus/sessions/session-${TASK_ID}.json"
STATS_FILE="${MAIN_WORKTREE}/.optimus/stats.json"
mkdir -p "${MAIN_WORKTREE}/.optimus/sessions" \
         "${MAIN_WORKTREE}/.optimus/reports" \
         "${MAIN_WORKTREE}/.optimus/logs"

# WRONG (resolves against PWD, breaks in linked worktrees):
STATE_FILE=".optimus/state.json"
SESSION_FILE=".optimus/sessions/session-${TASK_ID}.json"
STATS_FILE=".optimus/stats.json"
mkdir -p .optimus/sessions .optimus/reports .optimus/logs
```

**What does NOT need this protocol:**

- `<tasksDir>/optimus-tasks.md` and `<tasksDir>/tasks/`, `<tasksDir>/subtasks/` — versioned content, propagated by git across worktrees automatically.
- `.optimus/config.json` — when **versioned** (legacy projects), it propagates via git; when **gitignored** (current default), it suffers the same isolation as state.json. **Treat `.optimus/config.json` as gitignored and resolve via `$MAIN_WORKTREE` for safety in current projects** — the cost is a single `git worktree list` call.
- `.gitignore` itself — versioned, propagated via git.

**Idempotency:** the resolution is read-only against git metadata; safe to call multiple times in the same skill execution. Cache `MAIN_WORKTREE` in a local variable rather than re-running `git worktree list` for each path.

Skills reference this as: "Resolve main worktree — see AGENTS.md Protocol: Resolve Main Worktree Path."


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
1. Read `branch` from state.json (fastest)
2. Search by task ID: `git branch --list "*<task-id>*"` or `git worktree list | grep -iF "<task-id>"`
3. Derive from Tipo + ID + Title (always works)

Skills reference this as: "Derive branch name — see AGENTS.md Protocol: Branch Name Derivation."


### Protocol: Rename tasks.md to optimus-tasks.md

**Referenced by:** import, tasks, plan, build, review, done, resume, report, quick-report, batch, resolve, pr-check

Detects and renames projects whose Optimus tracking file is at `<tasksDir>/tasks.md`
(the prior default name) to `<tasksDir>/optimus-tasks.md`. The format marker
(`<!-- optimus:tasks-v1 -->`) is unchanged — this protocol only renames the file on disk.

**Detection (run at the start of every skill that reads/writes the tasks tracking file
to detect and offer rename of `<tasksDir>/tasks.md` to `<tasksDir>/optimus-tasks.md`):**

```bash
# Requires Protocol: Resolve Tasks Git Scope to have been executed first
# (TASKS_DIR, TASKS_FILE, TASKS_GIT_SCOPE, TASKS_GIT_REL, tasks_git available).
# TASKS_FILE already points to <tasksDir>/optimus-tasks.md.
OLD_TASKS_FILE="${TASKS_DIR}/tasks.md"
NEEDS_RENAME=0

# Symlink HARD BLOCK — refuse to inspect or operate on symlinked paths.
# Must run BEFORE detection (head -n 1 follows symlinks).
if [ -L "$OLD_TASKS_FILE" ] || [ -L "$TASKS_FILE" ]; then
  echo "ERROR: $OLD_TASKS_FILE or $TASKS_FILE is a symlink — refusing to inspect or rename." >&2
  exit 1
fi

if [ -f "$OLD_TASKS_FILE" ] && [ -f "$TASKS_FILE" ]; then
  if ! head -n 1 "$OLD_TASKS_FILE" 2>/dev/null | grep -q '^<!-- optimus:tasks-v1 -->'; then
    # OLD lacks the optimus marker — it is an unrelated file (Ring pre-dev's
    # Gate 7 tasks.md, etc.). The actual Optimus file is already at TASKS_FILE.
    NEEDS_RENAME=0
  else
    echo "ERROR: Both ${OLD_TASKS_FILE} and ${TASKS_FILE} exist and both appear to be Optimus tracking files." >&2
    echo "       Confirm which is current, remove the stale one, and re-run the skill." >&2
    exit 1
  fi
elif [ -f "$OLD_TASKS_FILE" ] && [ ! -f "$TASKS_FILE" ]; then
  # Only proceed if the legacy file actually has the optimus format marker — otherwise
  # it is some other unrelated tasks.md (e.g., Ring pre-dev's Gate 7 tasks.md) and
  # MUST NOT be touched.
  if head -n 1 "$OLD_TASKS_FILE" 2>/dev/null | grep -q '^<!-- optimus:tasks-v1 -->'; then
    NEEDS_RENAME=1
  fi
fi
```

If `NEEDS_RENAME=0`, the protocol is a no-op (either the new name already exists, the
legacy file is unrelated to optimus, or neither exists).

**Dry-run mode:** If the skill is running in dry-run (per Dry-Run Mode section above),
DO NOT execute the rename. Emit the plan and proceed:

```
[DRY-RUN] Rename would be offered for this task:
[DRY-RUN]   Old name: $OLD_TASKS_FILE
[DRY-RUN]   New name: $TASKS_FILE
[DRY-RUN]   Scope:    $TASKS_GIT_SCOPE
[DRY-RUN]   Would use: git mv (same-repo) OR tasks_git mv (separate-repo)
```

**If `NEEDS_RENAME=1`, ask the user via `AskUser`:**

```
The Optimus tracking file at $OLD_TASKS_FILE uses the previous default name.
Rename to $TASKS_FILE now? (Recommended — Ring pre-dev also produces a tasks.md
in this directory, so the previous name causes a collision.)
```

Options:
- **Rename now** — perform the rename and commit
- **Skip this time** — continue with the legacy name (emit warning; this will collide with Ring pre-dev)
- **Abort** — stop the current command so you can rename manually

**Rename flow (when user chooses "Rename now"):**

Checkpoint file: write `${MAIN_WORKTREE}/.optimus/.rename-in-progress` BEFORE starting.
This marker lets subsequent invocations detect interrupted renames:

```bash
# Requires Protocol: Resolve Main Worktree Path to have run first
# (or resolve inline; see that protocol).
MAIN_WORKTREE="$(git worktree list --porcelain 2>/dev/null | awk '/^worktree / {print $2; exit}')"
mkdir -p "${MAIN_WORKTREE}/.optimus"
printf '%s\n' "$TASKS_FILE" > "${MAIN_WORKTREE}/.optimus/.rename-in-progress"
```

**Scope-branched rename:** explicit `if` so the agent executes the correct branch:

```bash
if [ "$TASKS_GIT_SCOPE" = "same-repo" ]; then
  # Same-repo: atomic git mv in a single commit (preserves history via rename-detect).
  if ! git mv "$OLD_TASKS_FILE" "$TASKS_FILE"; then
    echo "ERROR: git mv failed. Rename aborted — no changes made." >&2
    rm -f "${MAIN_WORKTREE}/.optimus/.rename-in-progress"
    exit 1
  fi
  COMMIT_MSG_FILE=$(mktemp -t optimus.XXXXXX) || { echo "ERROR: mktemp failed" >&2; exit 1; }
  chmod 600 "$COMMIT_MSG_FILE"
  printf '%s' "chore(tasks): rename tasks.md to optimus-tasks.md" > "$COMMIT_MSG_FILE"
  if ! git commit -F "$COMMIT_MSG_FILE"; then
    echo "ERROR: Commit failed. Reverting git mv..." >&2
    # Revert: restore old name from HEAD, remove new name from working tree
    git reset HEAD -- "$OLD_TASKS_FILE" "$TASKS_FILE" 2>/dev/null
    git checkout HEAD -- "$OLD_TASKS_FILE" 2>/dev/null
    rm -f "$TASKS_FILE"
    rm -f "$COMMIT_MSG_FILE" "${MAIN_WORKTREE}/.optimus/.rename-in-progress"
    exit 1
  fi
  rm -f "$COMMIT_MSG_FILE"
else
  # Separate-repo: rename via tasks_git mv, single commit in tasks repo.
  OLD_TASKS_GIT_REL=$(python3 -c "import os,sys; print(os.path.relpath(sys.argv[1], sys.argv[2]))" \
    "$OLD_TASKS_FILE" "$TASKS_REPO_ROOT" 2>/dev/null)
  if [ -z "$OLD_TASKS_GIT_REL" ]; then
    echo "ERROR: Failed to compute path for legacy file relative to tasks repo." >&2
    rm -f "${MAIN_WORKTREE}/.optimus/.rename-in-progress"
    exit 1
  fi
  if ! tasks_git mv "$OLD_TASKS_GIT_REL" "$TASKS_GIT_REL"; then
    echo "ERROR: tasks_git mv failed. Rename aborted — no changes made." >&2
    rm -f "${MAIN_WORKTREE}/.optimus/.rename-in-progress"
    exit 1
  fi
  COMMIT_MSG_FILE=$(mktemp -t optimus.XXXXXX) || { echo "ERROR: mktemp failed" >&2; exit 1; }
  chmod 600 "$COMMIT_MSG_FILE"
  printf '%s' "chore(tasks): rename tasks.md to optimus-tasks.md" > "$COMMIT_MSG_FILE"
  if ! tasks_git commit -F "$COMMIT_MSG_FILE"; then
    echo "ERROR: Commit failed in tasks repo. Manual cleanup needed:" >&2
    echo "  cd $TASKS_DIR && git reset HEAD -- $OLD_TASKS_GIT_REL $TASKS_GIT_REL" >&2
    echo "  git checkout HEAD -- $OLD_TASKS_GIT_REL && rm -f $TASKS_GIT_REL" >&2
    rm -f "$COMMIT_MSG_FILE" "${MAIN_WORKTREE}/.optimus/.rename-in-progress"
    exit 1
  fi
  rm -f "$COMMIT_MSG_FILE"
fi
```

**Rename success: clear checkpoint marker and log.**
```bash
rm -f "${MAIN_WORKTREE}/.optimus/.rename-in-progress"
echo "INFO: Rename completed successfully:" >&2
echo "  - Old name:  $OLD_TASKS_FILE" >&2
echo "  - New name:  $TASKS_FILE" >&2
echo "  - Git scope: $TASKS_GIT_SCOPE" >&2
```

**Post-rename validation:** Verify the moved file still passes Format Validation (see
AGENTS.md Format Validation section). If it fails (e.g., the legacy file was manually
edited and lost the marker), inform user and suggest running `/optimus-import` to rebuild:

```bash
# Post-rename validation — verify the moved file still passes Format Validation.
if ! grep -q '^<!-- optimus:tasks-v1 -->' "$TASKS_FILE"; then
  echo "WARNING: Renamed optimus-tasks.md does not have the optimus format marker." >&2
  echo "         Run /optimus-import to rebuild in the correct format." >&2
fi
if ! grep -q '^## Versions' "$TASKS_FILE"; then
  echo "WARNING: Renamed optimus-tasks.md has no ## Versions section." >&2
  echo "         Run /optimus-import to rebuild in the correct format." >&2
fi
```

**Report success:**
```
Rename complete. The tracking file is now at ${TASKS_FILE}.
Remember to push the tasks repo when you're ready.
```

**Interrupted rename recovery (on skill startup):**

```bash
# Requires Protocol: Resolve Main Worktree Path to have run first
# (or resolve inline; see that protocol).
MAIN_WORKTREE="$(git worktree list --porcelain 2>/dev/null | awk '/^worktree / {print $2; exit}')"
if [ -f "${MAIN_WORKTREE}/.optimus/.rename-in-progress" ]; then
  INTERRUPTED_FILE=$(cat "${MAIN_WORKTREE}/.optimus/.rename-in-progress" 2>/dev/null)
  echo "WARNING: Previous rename was interrupted. Expected target: $INTERRUPTED_FILE" >&2
  # AskUser: Retry rename / Clear marker / Abort
fi
```

**If user chose "Skip this time":** Emit a warning and proceed using the legacy name
for this invocation only. The skill MUST use `$OLD_TASKS_FILE` as `$TASKS_FILE` for the
remainder of this execution.

**If user chose "Abort":** **STOP** the current command.

Skills reference this as: "Check optimus-tasks.md rename — see AGENTS.md Protocol: Rename tasks.md to optimus-tasks.md."


### Protocol: Terminal Identification

**Referenced by:** all stage agents (1-4), batch

After the task ID is identified and confirmed, set the terminal title to show the
current stage and task. This allows users running multiple agents in parallel terminals
to identify each terminal at a glance.

**Set title (after task ID is known):**

```bash
_optimus_set_title() {
  # iTerm2 AppleScript title updater. Empirical testing showed that Optimus
  # tasks always run in "divorced" iTerm2 sessions where the profile's
  # autoNameFormat is locked to a literal — OSC 0/1/2 and OSC 1337
  # SetUserVar are both ineffective in that state, so AppleScript's
  # `set name of s` is the only channel that actually mutates session.name.
  # The Execute tool runs bash without a controlling TTY, so /dev/tty fails
  # with ENODEV; we resolve the parent process's TTY via ps instead. Walk
  # up to 4 ancestors in case of nested shells. First run triggers a macOS
  # TCC prompt ("droid wants to control iTerm"); approving enables this
  # permanently. Silent no-op outside macOS/iTerm2 or when osascript is
  # unavailable — non-iTerm2 / non-macOS users get no title update.
  local title="$1"
  local pid="$PPID" tty=""
  for _ in 1 2 3 4; do
    [ -z "$pid" ] || [ "$pid" = "1" ] && break
    tty=$(ps -o tty= -p "$pid" 2>/dev/null | tr -d ' ')
    case "$tty" in
      ""|"?"|"??") pid=$(ps -o ppid= -p "$pid" 2>/dev/null | tr -d ' ') ;;
      *) break ;;
    esac
  done
  if { [ "$LC_TERMINAL" = "iTerm2" ] || [ "$TERM_PROGRAM" = "iTerm.app" ]; } \
     && command -v osascript >/dev/null 2>&1 && [ -n "$tty" ] \
     && [ "$tty" != "?" ] && [ "$tty" != "??" ]; then
    osascript \
      -e 'on run argv' \
      -e '  set targetTty to "/dev/" & item 1 of argv' \
      -e '  set newName to item 2 of argv' \
      -e '  tell application "iTerm2"' \
      -e '    repeat with w in windows' \
      -e '      repeat with t in tabs of w' \
      -e '        repeat with s in sessions of t' \
      -e '          if (tty of s as string) is targetTty then' \
      -e '            try' \
      -e '              set name of s to newName' \
      -e '            end try' \
      -e '          end if' \
      -e '        end repeat' \
      -e '      end repeat' \
      -e '    end repeat' \
      -e '  end tell' \
      -e 'end run' \
      -- "$tty" "$title" >/dev/null 2>&1 || true
  fi
}
_optimus_set_title "optimus: <STAGE> $TASK_ID — $TASK_TITLE"
```

Example output in terminal tab: `optimus: REVIEW T-003 — User Auth JWT`

**Why the parent-process TTY:** The Execute tool runs `bash -c` without a controlling
terminal, so `/dev/tty` returns `ENODEV` ("Device not configured"). The resolver above
asks `ps` for the parent's controlling TTY device path and matches it against iTerm2's
session list via AppleScript — that device is connected to the user's real iTerm2
session. If no ancestor has a TTY (Docker/CI) or osascript is unavailable, the
function silently no-ops.

**Restore title (at stage completion or exit):**

```bash
_optimus_set_title ""
```

**NOTE:** This helper is iTerm2-on-macOS only. Optimus tasks always run in
"divorced" iTerm2 sessions, where AppleScript's `set name of s` is the only
channel that reliably mutates `session.name`. Non-iTerm2 / non-macOS users
will not see a title update.

**Troubleshooting iTerm2 (if the title still doesn't update):**

1. **Window > Edit Tab Title** must be empty. A manually-set tab title is
   sticky on the tab label and overrides the session name visually, even
   when `session.name` is updated correctly underneath.
2. The first run on macOS triggers a TCC prompt ("`droid` wants to control
   `iTerm`"). Approve it to enable the helper. Denying makes the helper a
   silent no-op.
3. The helper requires the parent process to have a controlling TTY. Inside
   Docker/CI without a TTY, no ancestor will resolve and the helper will
   silently no-op.

Skills reference this as: "Set terminal title — see AGENTS.md Protocol: Terminal Identification."


### Protocol: optimus-tasks.md Validation (HARD BLOCK)

**Referenced by:** all stage agents (1-4), tasks, batch. Note: resolve performs inline format validation in its own Step 4.2.

Every stage agent MUST validate optimus-tasks.md before operating. The full validation rules are
defined in the "Format Validation" section above (items 1-15). This protocol is the
executable version:

1. **Resolve paths and git scope:** Execute Protocol: Resolve Tasks Git Scope (below) to
   resolve `TASKS_DIR`, `TASKS_FILE`, `TASKS_GIT_SCOPE`, and the `tasks_git` helper.
2. **Find optimus-tasks.md:** Check if `TASKS_FILE` exists. If not found, **STOP** and suggest `/optimus-import`.
3. **Validate format:** Execute all 15 validation checks from the "Format Validation" section. If the format marker is missing or any check fails, **STOP** and suggest `/optimus-import`.

**All subsequent references to `optimus-tasks.md` in the skill use the resolved `TASKS_FILE` path.
All references to Ring pre-dev artifacts use `TASKS_DIR` as the root** — never hardcoded paths.
**All git operations on optimus-tasks.md use the `tasks_git` helper** (which handles both same-repo
and separate-repo scopes).

Skills reference this as: "Find and validate optimus-tasks.md (HARD BLOCK) — see AGENTS.md Protocol: optimus-tasks.md Validation."


<!-- INLINE-PROTOCOLS:END -->
