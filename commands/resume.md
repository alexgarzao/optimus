---
description: Resume a task after closing the terminal. Given a task ID (or auto-detecting from the in-progress tasks recorded in state.json), locates or recreates the task's worktree, reports the current status, and offers to invoke the next stage. Read-only on state.json except for user-confirmed recovery (Reset to Pendente when branch is missing).
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
below the shared-protocols block at the end of this file) contains a destructive fallback
— `rm -f "$STATE_FILE"` on corruption. **Resume explicitly DOES NOT apply that fallback**:
on corruption it STOPs with guidance (Step 2.2a). Treat the inlined block as foundational
context only; the rules in this body override it.

---

## Phase 1: Prerequisites

### Step 1.1: Check jq (HARD BLOCK)

```bash
command -v jq >/dev/null 2>&1
```

If `jq` is not available, **STOP**: "jq is required by /optimus:resume. Install it and retry."

### Step 1.2: Resolve and Validate optimus-tasks.md (HARD BLOCK)

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
# "docs/pre-dev/optimus:tasks.md not found" errors for users who customized tasksDir).
if [ -z "${TASKS_FILE:-}" ]; then
  echo "ERROR: TASKS_FILE is unset — Step 1.2 (optimus-tasks.md Validation) did not execute." >&2
  echo "Protocol: Resolve Tasks Git Scope must run before Step 1.3." >&2
  exit 1
fi
if [ ! -f "$TASKS_FILE" ]; then
  echo "ERROR: $TASKS_FILE not found. Run /optimus:import to create it."
  # STOP
fi
TASK_ROWS=$(grep -cE '^\| T-[0-9]+ \|' "$TASKS_FILE" || echo 0)
if ! [[ "$TASK_ROWS" =~ ^[0-9]+$ ]] || [ "$TASK_ROWS" -eq 0 ]; then
  echo "ERROR: No tasks found in $TASKS_FILE. Use /optimus:tasks to create a task or /optimus:import to import from Ring pre-dev."
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
    echo "Run /optimus:tasks to rebuild the operational state, or restore state.json from backup."
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

If no match → **STOP**: `"Task ${TASK_ID} not found in optimus-tasks.md. Run /optimus:report to see available tasks."`

### Step 2.2: Auto-Detect (no ID provided)

Filter for a concrete non-terminal status (whitelist — prevents malformed `null`/missing
status entries from surfacing as resumable tasks). Order by `updated_at` descending
(most recent first) for stable UX.

```bash
if [ -z "$STATE_JSON" ]; then
  echo "ERROR: No state.json found and no task ID provided. Run /optimus:report to see the project status."
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

- **If 0 tasks** → **STOP**: `"No in-progress tasks found. Run /optimus:report to see the project status, or /optimus:plan T-XXX to start a new task."`
- **If exactly 1 task** → use that ID as `TASK_ID` (no AskUser — resume does not change status, so there is no expanded-confirmation requirement).
- **If N tasks** → present via `AskUser` with one option per task (`T-XXX — <title> (<status>, updated <relative-time>)`) plus **Cancel**. Do NOT offer Resume/Start fresh/Continue.

<a id="step-read-task-metadata"></a>
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

- If `TASK_STATUS` is `DONE` → **STOP**: `"Task ${TASK_ID} is already DONE. Nothing to resume. To reopen, use /optimus:tasks."`
- If `TASK_STATUS` is `Cancelado` → **STOP**: `"Task ${TASK_ID} is Cancelado. Reopen via /optimus:tasks before resuming."`

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
`Skip` + `Run /optimus:report` and surface a warning in the Phase 4 summary
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

# Anchor the match on the kebab-cased task ID (e.g., `-t-1-`) so substrings like
# `t-1` cannot match `t-10`/`t-100`. Worktree paths follow Protocol: Worktree
# Location: ${MAIN_WORKTREE}/.worktrees/<flat-branch-name> (branch slashes
# replaced with hyphens; legacy sibling paths ../<repo>-<id>-<keywords> still
# resolve via git worktree list metadata).
# Feature branches follow `<tipo>/<id>-<keywords>` — both surround the
# lowercased ID with hyphens.
TASK_KEBAB="-$(echo "$TASK_ID" | tr '[:upper:]' '[:lower:]')-"
WORKTREE_PATH=$(git worktree list --porcelain 2>/dev/null \
  | awk -v anchor="$TASK_KEBAB" '
      BEGIN { if (anchor == "--") exit 1 }
      /^worktree / { wt=$2 }
      /^branch /   { if (index(tolower(wt), anchor) > 0 || index(tolower($2), anchor) > 0) { print wt; exit } }
    ')

if [ -z "$WORKTREE_PATH" ]; then
  # Fallback: anchored kebab match against the path field only. NEVER use a bare
  # `grep -iF "$TASK_ID"` — that produces false positives for short IDs
  # (e.g., `T-1` matching `T-10`, `T-100`).
  WORKTREE_PATH=$(git worktree list --porcelain 2>/dev/null \
    | awk -v anchor="$TASK_KEBAB" '/^worktree / { path=$2; if (index(tolower(path), anchor) > 0) { print path; exit } }')
fi
```

### Step 3.3: Apply Resolution Order

**Canonical worktree path** — see AGENTS.md Protocol: Worktree Location.

1. **Worktree found** → `cd "$WORKTREE_PATH"` for the rest of the session. Continue to Phase 4.

2. **Worktree missing, branch exists locally** (`git rev-parse --verify "$TASK_BRANCH" >/dev/null 2>&1` succeeds):

   **Hard guards (HARD BLOCK) BEFORE attempting `git worktree add`:**

   ```bash
   # Resolve main worktree first — see AGENTS.md Protocol: Resolve Main Worktree Path.
   # Reuse cached MAIN_WORKTREE if caller already resolved (per Protocol: Resolve Main Worktree Path).
   if [ -z "${MAIN_WORKTREE:-}" ]; then
     MAIN_WORKTREE="$(git worktree list --porcelain 2>/dev/null | awk '/^worktree / {print $2; exit}')"
   fi
   MAIN_WORKTREE="${MAIN_WORKTREE:?MAIN_WORKTREE not resolved — not in a git repository}"

   # Belt-and-suspenders: upstream guards (Step 2.1, Step 3.1, Step 3.2) already validated
   # these, but we are at a filesystem-mutation boundary — refuse one more time.
   if [ -z "$TASK_ID" ] || [ -z "$TASK_BRANCH" ]; then
     echo "ERROR: TASK_ID or TASK_BRANCH empty before 'git worktree add'. Refusing."
     # STOP
   fi

   # Path-traversal guard (defense in depth): branch comes from state.json.
   case "$TASK_BRANCH" in
     *..*|/*) echo "ERROR: refusing unsafe branch '$TASK_BRANCH'." >&2; exit 1 ;;
   esac
   FLAT_BRANCH="${TASK_BRANCH//\//\-}"     # / → - so worktree dirs are flat
   WORKTREE_DIR="${MAIN_WORKTREE}/.worktrees/${FLAT_BRANCH}"

   # HARD BLOCK on git worktree add failure (dir exists, branch checked out elsewhere, etc.)
   if ! git worktree add "$WORKTREE_DIR" "$TASK_BRANCH"; then
     echo "ERROR: 'git worktree add $WORKTREE_DIR $TASK_BRANCH' failed (branch already checked out, dir collision, or filesystem error)."
     echo "       Possible causes: directory exists, branch checked out elsewhere, or local repo state."
     # STOP
   fi
   WORKTREE_PATH="$WORKTREE_DIR"
   if ! cd "$WORKTREE_PATH"; then
     echo "ERROR: cd to $WORKTREE_PATH failed after successful worktree creation."
     # STOP
   fi
   ```

   **Initialize .optimus directory** (ensures `.optimus/logs/`, `.gitignore` exclusions for `.optimus/` and `.worktrees/`) — see AGENTS.md Protocol: Initialize .optimus Directory.

<a id="step-reset-to-pendente-recovery"></a>
3. **Worktree missing AND branch missing:**
   - **If status is `Pendente` or has no state.json entry:** present via `AskUser`:
     ```
     Task T-XXX has no worktree and no branch yet — it has not been through /optimus:plan.
     Run /optimus:plan T-XXX now?
     ```
     Options:
     - **Yes, invoke /optimus:plan** — invoke the `optimus-plan` skill via the `Skill`
       tool. The conversation context carries `TASK_ID`; the delegate will locate the
       task and run its own expanded confirmation. Resume does NOT bypass the delegate's
       validation.
     - **Cancel** — **STOP** with: `"No workspace for T-XXX. Run /optimus:plan T-XXX when ready."`

   - **If status is in-progress but branch is missing (inconsistent state):**

     Present via `AskUser` with two options. The first is a **user-confirmed recovery**
     that mutates state.json — the only place where resume writes state. The second is
     a plain abort. A "Re-run /optimus:plan" option without first resetting is **not
     offered**: `/optimus:plan`'s anti-pulo rejects any status other than `Pendente` /
     `Validando Spec`, so it would immediately STOP.

     ```
     Inconsistency: T-XXX has status <status> but branch <$TASK_BRANCH> does not exist.
     Possible recovery:
     ```
     Options:
     - **Reset to Pendente, then run /optimus:plan** — resume performs a user-confirmed
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
         echo "T-$TASK_ID has been reset to Pendente. Invoking /optimus:plan via the Skill tool..."
         # Then delegate to the optimus-plan skill via the Skill tool.
       else
         echo "T-$TASK_ID remains in its pre-existing state — no reset applied."
         # STOP
       fi
       ```

     - **Abort** — **STOP** with: `"Inconsistency not resolved. Investigate via /optimus:tasks edit T-$TASK_ID before retrying."`

<a id="step-dry-run-short-circuit"></a>
### Step 3.4: Dry-Run Short-Circuit

If the user invoked a dry-run (e.g., "dry-run resume T-XXX", "preview resume"):

- Perform Steps 3.1–3.2 normally (read-only)
- Do NOT run `git worktree add`
- Do NOT `cd`
- Do NOT run the "Reset to Pendente, then /optimus:plan" recovery (anchor
  `step-reset-to-pendente-recovery`) — if reached, STOP with: `"dry-run: no recovery
  attempted. Re-run without dry-run to repair state."`
- Do NOT delegate to any other skill (no `Skill` tool invocation)
- Proceed to Phase 4 and label the summary as **(dry-run, no changes applied)**
- Skip Phase 5 entirely

---

## Phase 4: Set Terminal Title and Report

### Step 4.1: Set Terminal Title

Mark terminal session — see AGENTS.md Protocol: Terminal Identification. Use stage label `RESUME`:

```bash
_optimus_mark_session RESUME "$TASK_ID" "$TASK_TITLE"
```

**On exit or after Phase 5 delegates to another stage skill**, restore the title:

```bash
_optimus_clear_session
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
Review these dependencies first via /optimus:report.
```

**IMPORTANT:** Print the absolute path. The Droid session's internal `cd` does NOT change
the user's interactive shell cwd — the user must run `cd` themselves to have their shell
match. Subsequent tool calls in this Droid session will still use the internal cwd.

### Step 4.4: Next-Stage Recommendation

Map current status + PR state to the recommended next command:

| Current status     | PR state                      | Next recommended                               |
|--------------------|-------------------------------|------------------------------------------------|
| `Validando Spec` + `TaskSpec=-` | any              | `/optimus:plan` (spec is missing — re-run plan to resolve) |
| `Validando Spec`   | any                           | `/optimus:build`                               |
| `Em Andamento`     | any                           | `/optimus:review` (or re-run `/optimus:build`) |
| `Validando Impl`   | OPEN                          | `/optimus:pr-check` (then `/optimus:done`)     |
| `Validando Impl`   | MERGED / CLOSED               | `/optimus:done` (or re-run `/optimus:review`)  |
| `Validando Impl`   | NONE                          | `/optimus:done` (will require a PR — create one first) |
| `Validando Impl`   | UNKNOWN (gh failure)          | **Suppressed** — show warning: "PR state could not be determined; inspect the branch manually before choosing /optimus:done or /optimus:pr-check." |

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

- **Run /optimus:report** — to review the blocking dependencies.
- **Skip** — workspace is ready; user decides how to proceed.

**PR-state suppressor.** If `PR_STATE` starts with `UNKNOWN` (gh failure: unavailable,
unauthenticated, network/rate-limit), the `Validando Impl` options collapse to:

- **Re-run /optimus:review** / **Skip**

The user is asked to investigate gh before picking a stage that depends on PR state.

Otherwise (no blocking deps, PR state known), options are chosen from status + PR state:

- `Validando Spec`: **Run /optimus:build** / **Skip**
- `Em Andamento`: **Run /optimus:review** / **Re-run /optimus:build** / **Skip**
- `Validando Impl` + PR OPEN: **Run /optimus:pr-check** / **Run /optimus:done** / **Re-run /optimus:review** / **Skip**
- `Validando Impl` + PR MERGED/CLOSED: **Run /optimus:done** / **Re-run /optimus:review** / **Skip**
- `Validando Impl` + no PR (NONE): **Run /optimus:done** (will likely require a PR) / **Re-run /optimus:review** / **Skip**

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
- Does NOT offer `Resume / Start fresh / Continue` prompts (coherent with `/optimus:done`).
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
- "The user clearly wants /optimus:build, let me just run it" — wait for the Phase 5 AskUser decision.
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

<!-- INLINE-PROTOCOLS:END -->
