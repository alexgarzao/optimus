# Phase 3: Resolve Workspace

Loaded after Phase 2. Derive expected branch, look up worktree, apply resolution order. HARD BLOCK on missing-branch case with interactive recovery options (Reset to Pendente is the only allowed state.json write).

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

**AUTHORITATIVE — DO NOT PROMPT.** When recreating a missing worktree, the path
is fixed by `Protocol: Worktree Location`. Do NOT ask the user where to place
the worktree. Do NOT enumerate alternatives (parent dir, in-place, etc.).
Project `CLAUDE.md` worktree conventions are **OVERRIDDEN** by this skill.

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

<a id="step-dry-run-short-circuit"></a>
### Step 3.4: Dry-Run Short-Circuit

If the user invoked a dry-run (e.g., "dry-run resume T-XXX", "preview resume"):

- Perform Steps 3.1–3.2 normally (read-only)
- Do NOT run `git worktree add`
- Do NOT `cd`
- Do NOT run the "Reset to Pendente, then /optimus-plan" recovery (anchor
  `step-reset-to-pendente-recovery`) — if reached, STOP with: `"dry-run: no recovery
  attempted. Re-run without dry-run to repair state."`
- Do NOT delegate to any other skill (no `Skill` tool invocation)
- Proceed to Phase 4 and label the summary as **(dry-run, no changes applied)**
- Skip Phase 5 entirely

---
