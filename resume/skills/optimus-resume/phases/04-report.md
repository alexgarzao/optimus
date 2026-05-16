# Phase 4: Set Terminal Title and Report

Loaded after Phase 3 places the agent inside the task's worktree. Marks the
session, gathers read-only telemetry (git/PR/session/stats), and prints the
resume summary.

## Step 4.1: Set Terminal Title

**Substitute `$TASK_ID` and `$TASK_TITLE`** with the values resolved in Phase 2
before running this block. The mark call **MUST live in the SAME bash
invocation** that already has these variables in scope — each Bash tool
invocation is a fresh shell, so calling without substitution renders a bare
"RESUME" badge with no task context. See AGENTS.md Protocol: Terminal
Identification.

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
_optimus_mark_session RESUME "$TASK_ID" "$TASK_TITLE"
```

**On exit or after Phase 5 delegates to another stage skill**, restore the title:

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

## Step 4.2: Collect Worktree Telemetry

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

## Step 4.3: Print Summary

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

## Step 4.4: Next-Stage Recommendation

Map current status + PR state to the recommended next command:

| Current status     | PR state                      | Next recommended                               |
|--------------------|-------------------------------|------------------------------------------------|
| `Validando Spec` + `TaskSpec=-` | any              | `/optimus-plan` (spec is missing — re-run plan to resolve) |
| `Validando Spec`   | any                           | `/optimus-build`                               |
| `Em Andamento`     | any                           | `/optimus-review` (or re-run `/optimus-build`) |
| `Validando Impl`   | OPEN                          | `/optimus-pr-check` (then `/optimus-done`)     |
| `Validando Impl`   | MERGED / CLOSED               | `/optimus-done` (or re-run `/optimus-review`)  |
| `Validando Impl`   | NONE                          | `/optimus-done` (will require a PR — create one first) |
| `Validando Impl`   | UNKNOWN (gh failure)          | **Suppressed** — show warning: "PR state could not be determined; inspect the branch manually before choosing /optimus-done or /optimus-pr-check." |

Show the chosen recommendation in the summary. When `PR_STATE` starts with `UNKNOWN`,
the Phase 5 options must also omit any stage that depends on PR state (see Phase 5).
