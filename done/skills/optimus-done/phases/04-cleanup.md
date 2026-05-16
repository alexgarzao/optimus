# Phase 4 (Cleanup): Remove Worktree + Branch (after DONE)

Loaded by `SKILL.md` AFTER the task has been marked as `DONE` (or
`Cancelado`). This phase is interactive — user decides what to keep.

## Step 4.1: Check for Task Worktree

**IMPORTANT:** Worktree must be removed BEFORE attempting branch deletion.

Resolve the worktree from the source-of-truth: read the task's branch from
state.json (set by Workspace Auto-Navigation in earlier stages), then match it
against `git worktree list --porcelain`. This avoids substring false positives
on short task IDs (e.g., `T-1` matching `T-10`, `T-100`).

```bash
# Resolve main worktree — see AGENTS.md Protocol: Resolve Main Worktree Path.
MAIN_WORKTREE="${MAIN_WORKTREE:-$(git worktree list --porcelain 2>/dev/null | awk '/^worktree / {print $2; exit}')}"
MAIN_WORKTREE="${MAIN_WORKTREE:?MAIN_WORKTREE not resolved — not in a git repository}"
TASK_BRANCH=$(jq -r --arg id "$TASK_ID" '.[$id].branch // ""' "${MAIN_WORKTREE}/.optimus/state.json" 2>/dev/null)

WORKTREE_PATH=""
if [ -n "$TASK_BRANCH" ]; then
  # Match by branch (exact, deterministic) — porcelain output has one
  # `worktree <path>` line followed by `branch refs/heads/<name>` per entry.
  WORKTREE_PATH=$(git worktree list --porcelain 2>/dev/null | awk -v br="refs/heads/$TASK_BRANCH" '
    /^worktree / { path=$2 }
    /^branch /   { if ($2 == br) { print path; exit } }
  ')
fi

if [ -z "$WORKTREE_PATH" ]; then
  # Fallback: anchored kebab-cased path-segment match — never `grep -iF "$TASK_ID"`,
  # which would match T-1 against T-10/T-100.
  TASK_KEBAB="-$(echo "$TASK_ID" | tr '[:upper:]' '[:lower:]')-"
  WORKTREE_PATH=$(git worktree list --porcelain 2>/dev/null \
    | awk -v anchor="$TASK_KEBAB" '/^worktree / { path=$2; if (index(tolower(path), anchor) > 0) { print path; exit } }')
fi
```

If a worktree is found (`WORKTREE_PATH` non-empty), ask via `AskUser`:
```
Task T-XXX is done. A worktree still exists at '<path>'. What should I do?
```
Options:
- **Remove worktree**: `git worktree remove <path>` then prune empty parent dirs (see snippet below)
- **Keep**: Leave the worktree as is

**Removal snippet** — after the user picks "Remove worktree":

```bash
git worktree remove "$WORKTREE_PATH"
# Cleanup empty parent dirs (legacy nested layout only — flat layout's parent
# is .worktrees/ directly, so the loop exits after one iteration).
# Idempotent: rmdir refuses non-empty dirs silently.
parent="$(dirname "$WORKTREE_PATH")"
while [ "$parent" != "${MAIN_WORKTREE}/.worktrees" ] && [ "$parent" != "/" ]; do
  rmdir "$parent" 2>/dev/null || break
  parent="$(dirname "$parent")"
done
```

This loop walks up from the removed worktree to `${MAIN_WORKTREE}/.worktrees/` and removes empty parent dirs. With the FLAT layout (`Protocol: Worktree Location`), a flat worktree's parent is `.worktrees/` directly so the loop exits after one iteration. Legacy nested worktrees (still supported for backwards-compat) trigger the loop to clean up their `feat/` / `fix/` parent dir as before.

**Edge case — running INSIDE the worktree:** If the agent's current working directory IS
the worktree being removed, `cd` to the main repository first:
1. Identify the main repository path from `git worktree list` (first entry)
2. `cd <main-repo-path>`
3. Then run the **Removal snippet** above.

## Step 4.2: Check for Task Branch

Identify the task's branch (resolve `MAIN_WORKTREE` first so `state.json` is
read from the main worktree, not from a linked worktree's isolated copy):

```bash
# Resolve main worktree — see AGENTS.md Protocol: Resolve Main Worktree Path.
MAIN_WORKTREE="${MAIN_WORKTREE:-$(git worktree list --porcelain 2>/dev/null | awk '/^worktree / {print $2; exit}')}"
MAIN_WORKTREE="${MAIN_WORKTREE:?MAIN_WORKTREE not resolved — not in a git repository}"
TASK_BRANCH=$(jq -r --arg id "$TASK_ID" '.[$id].branch // ""' "${MAIN_WORKTREE}/.optimus/state.json" 2>/dev/null)
if [ -z "$TASK_BRANCH" ]; then
  TASK_BRANCH=$(git branch --list "*$(echo "$TASK_ID" | tr '[:upper:]' '[:lower:]')*" 2>/dev/null | head -1 | tr -d ' *')
fi
```

If the branch exists (locally and/or remotely), ask via `AskUser`:
```
Task T-XXX is done. The branch '<branch>' still exists. What should I do?
```
Options:
- **Delete local and remote**: switch to default branch, pull, then delete
- **Delete local only**: switch to default branch, delete local
- **Keep**: Leave the branch as is

**Final confirmation for destructive options:** If the user selects "Delete local and remote"
or "Delete local only", present a final confirmation via `AskUser`:
"This will permanently delete branch `<branch>`. Are you sure?" Options: Yes, delete / Cancel.

**Before deleting:** switch to the default branch first. Use the canonical
deterministic recipe — see AGENTS.md Protocol: Default Branch Resolution.

```bash
# Resolve DEFAULT_BRANCH deterministically — see AGENTS.md Protocol: Default Branch Resolution.
DEFAULT_BRANCH=""
if symref=$(git symbolic-ref --short refs/remotes/origin/HEAD 2>/dev/null); then
  DEFAULT_BRANCH="${symref#origin/}"
elif git show-ref --verify --quiet refs/heads/main; then
  DEFAULT_BRANCH="main"
elif git show-ref --verify --quiet refs/heads/master; then
  DEFAULT_BRANCH="master"
fi
if [ -z "$DEFAULT_BRANCH" ]; then
  echo "ERROR: Could not determine default branch (no origin/HEAD, no main, no master)." >&2
  echo "       Set it with: git remote set-head origin <branch>" >&2
  # STOP — do not proceed with branch deletion
fi
git checkout "$DEFAULT_BRANCH"
git pull

# Local delete first; -d (safe) preferred over -D
if ! git branch -d "$TASK_BRANCH" 2>/dev/null; then
  if ! LOCAL_DELETE_OUTPUT=$(git branch -D "$TASK_BRANCH" 2>&1); then
    echo "ERROR: Could not delete local branch $TASK_BRANCH: $LOCAL_DELETE_OUTPUT" >&2
    # AskUser:
    #   "Local branch delete failed. How should I proceed?"
    #   - **Continue cleanup anyway** — proceed (e.g., the user will clean up manually)
    #   - **Abort cleanup** — STOP without attempting remote deletion
  fi
fi

# Remote delete with explicit failure-cause classification.
# `DELETE_REMOTE` is "yes" only when the user picked "Delete local and remote".
if [ "$DELETE_REMOTE" = "yes" ]; then
  if ! PUSH_OUTPUT=$(git push origin --delete "$TASK_BRANCH" 2>&1); then
    PUSH_RC=$?
    # Classify the failure so the user gets actionable diagnostics.
    case "$PUSH_OUTPUT" in
      *"remote ref does not exist"*|*"deleted reference"*)
        echo "ℹ Remote branch already deleted upstream (rc=$PUSH_RC) — local cleanup complete." >&2
        REMOTE_DELETE_RESULT="already-deleted"
        ;;
      *"protected branch"*|*"protection"*)
        echo "✗ Remote branch is protected — cannot delete (rc=$PUSH_RC)." >&2
        echo "  Local branch deleted; remote branch will need manual cleanup or branch-protection adjustment." >&2
        REMOTE_DELETE_RESULT="protected"
        ;;
      *"could not read"*|*"unable to access"*|*"connection"*|*"timed out"*|*"timeout"*|*"Network"*)
        echo "✗ Network error pushing branch deletion (rc=$PUSH_RC):" >&2
        echo "  $PUSH_OUTPUT" >&2
        echo "  Local branch deleted; retry or run \`git push origin --delete $TASK_BRANCH\` manually after restoring connectivity." >&2
        REMOTE_DELETE_RESULT="network-error"
        ;;
      *)
        echo "✗ Remote branch delete failed (rc=$PUSH_RC): $PUSH_OUTPUT" >&2
        REMOTE_DELETE_RESULT="other-error"
        ;;
    esac

    # AskUser (integrate the classification message above into the body):
    #   "Remote branch deletion failed (<classification>). What should I do?"
    #   - **Ignore and continue** — leave the remote branch as is (logged with `pending-remote-delete`)
    #   - **Retry now** — re-run `git push origin --delete "$TASK_BRANCH"` once
    #   - **Abort cleanup** — STOP; user will resolve manually
    #
    # Notify the user via Hooks if available (event=`pending-remote-delete`).
    # Tag the task in state.json with `pending_remote_delete: true` so a future
    # operation (e.g., a follow-up `done`, or a maintenance script) can retry.
  else
    REMOTE_DELETE_RESULT="ok"
  fi
fi
```

**Partial-state contract on failure:** if remote deletion fails after local
deletion succeeds, the task is `DONE` and the local branch is gone, but the
remote branch may persist. The task is flagged with `pending_remote_delete`
in state.json so it can be retried later. The Cleanup Summary (Step 4.3) MUST
reflect this partial state — do NOT report "Deleted" for the remote when the
push failed.

## Step 4.3: Cleanup Summary

```markdown
## Cleanup Summary for T-XXX

| Resource | Status | Action Taken |
|----------|--------|-------------|
| Worktree `/path/to/wt` | Found | Removed / Kept |
| Branch `<tipo>/t-xxx-...` (local) | Found | Deleted / Kept |
| Branch `<tipo>/t-xxx-...` (remote) | Found | Deleted / Kept |
```

On completion, clear the iTerm2 marker:

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
