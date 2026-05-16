# Phase 2: Create Task

Loaded when user wants to add a new task. Generates next ID, collects metadata via AskUser, validates format, handles TaskSpec=- (Defer) flow, commits.

### Step 2.0: Gather Task Information

**Option A: From template.** Ask the user if they want to use a template via `AskUser`:

```
Create from a template or from scratch?
```
Options:
- **API Endpoint** — pre-fills Feature tipo
- **Bug Fix** — pre-fills Fix tipo
- **UI Component** — pre-fills Feature tipo
- **Chore/Infra** — pre-fills Chore tipo
- **Refactor** — pre-fills Refactor tipo
- **Documentation** — pre-fills Docs tipo
- **Test** — pre-fills Test tipo
- **From scratch** — manual entry (no template)

#### Built-in Templates

Templates pre-fill Tipo and Priority. The task creation flow delegates to Step 2.3.1 (Resolve TaskSpec for the New Task) which offers Generate/Link/Defer.

**API Endpoint template:** Tipo: `Feature`, Priority: `Alta`
**Bug Fix template:** Tipo: `Fix`, Priority: `Alta`
**UI Component template:** Tipo: `Feature`, Priority: `Media`
**Chore/Infra template:** Tipo: `Chore`, Priority: `Media`
**Refactor template:** Tipo: `Refactor`, Priority: `Media`
**Documentation template:** Tipo: `Docs`, Priority: `Baixa`
**Test template:** Tipo: `Test`, Priority: `Media`

When a template is selected, pre-fill the Tipo and Priority.
The user can then modify any field before confirming.

**Option B: From scratch.** Ask the user for task details using `AskUser` (one question at a time or batch if info provided):

1. **Title** (required): Short description of the task
2. **Tipo** (required): `Feature`, `Fix`, `Refactor`, `Chore`, `Docs`, or `Test`. The Tipo determines the Conventional Commits prefix used downstream by `plan` (branch name), `build` (commit messages), and `review` (PR title) — see AGENTS.md "Valid Tipo Values" table for the full mapping.
3. **Priority** (required): `Alta`, `Media`, or `Baixa`
4. **Estimate** (optional): Task size estimate (`S`, `M`, `L`, `XL`, `2h`, `1d`, etc.). Default: `-`
5. **Version** (required): Must match a version in the Versions table. Default: the version with Status `Ativa`
6. **Dependencies** (optional): Comma-separated task IDs (e.g., `T-001, T-003`) or `-` for none
7. **Ring pre-dev reference** (optional): If not provided, Step 2.3.1 will offer to generate via Ring, link an existing spec, or defer (TaskSpec=-).

If the user provided some of these in the initial request, use them and ask only for missing fields.

### Step 2.1: Check for Similar Tasks (duplicate detection)

Before creating, search existing tasks for potential duplicates:

1. **Compare by title:** For each existing task, check if the new title shares 2+ significant
   keywords with an existing title (ignore articles, prepositions, and generic words like
   "implement", "add", "create", "update", "fix")
2. **Compare by Ring source:** If a Ring pre-dev task was linked, check if any existing task's
   `TaskSpec` column already references the same Ring task spec file

If similar tasks are found, present them to the user via `AskUser`:

```
I found N existing tasks that look similar to your new task:

| ID | Title | Version | Status | Ring Source |
|----|-------|---------|--------|------------|
| T-003 | User login page | MVP | Pendente | task_005.md |
| T-008 | Auth login flow | v2 | Em Andamento | task_005.md |

Your new task: "<new title>"

Create anyway?
```

Options:
- **Create anyway** — the new task is different enough
- **Cancel** — one of the existing tasks already covers this

If no similar tasks are found, proceed silently.

### Step 2.1.1: Validate Title Characters

**HARD BLOCK:** The task title must not contain unescaped pipe characters (`|`) because
optimus-tasks.md uses markdown tables where `|` is the column delimiter.

If the title contains `|`:
- Automatically replace `|` with `—` (em dash) or `\|` (escaped pipe)
- Inform the user: "Title contained pipe characters which would break the optimus-tasks.md table format. Replaced with '—'."

Also reject titles longer than 120 characters — longer titles break table formatting.
If too long, ask the user to shorten it.

### Step 2.2: Generate Task ID

Collect IDs from ALL sources to avoid collisions with parallel branches:

1. **Local:** Parse all existing task IDs from the current branch's optimus-tasks.md table
2. **Remote:** Fetch and parse IDs from the tasks repo's default branch on origin
   (uses `tasks_git` so it works in both same-repo and separate-repo scopes):
   ```bash
   if [ "$TASKS_GIT_SCOPE" = "separate-repo" ]; then
     TASKS_DEFAULT_BRANCH=$(tasks_git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's@^refs/remotes/origin/@@')
     if [ -z "$TASKS_DEFAULT_BRANCH" ]; then
       TASKS_DEFAULT_BRANCH=$(tasks_git branch --list main master 2>/dev/null | head -1 | tr -d ' *')
     fi
   else
     TASKS_DEFAULT_BRANCH=$(git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's@^refs/remotes/origin/@@')
     if [ -z "$TASKS_DEFAULT_BRANCH" ]; then
       TASKS_DEFAULT_BRANCH=$(git branch --list main master 2>/dev/null | head -1 | tr -d ' *')
     fi
   fi
   if [ -n "$TASKS_DEFAULT_BRANCH" ]; then
     tasks_git fetch origin "$TASKS_DEFAULT_BRANCH" --quiet 2>/dev/null
     tasks_git show "origin/${TASKS_DEFAULT_BRANCH}:${TASKS_GIT_REL}" 2>/dev/null | grep -oE 'T-[0-9]+'
   fi
   ```
   If `TASKS_DEFAULT_BRANCH` is empty or fetch fails, warn the user: "Could not determine
   default branch or reach remote — ID may collide with tasks created on other
   branches. Continuing with local IDs only."
3. **Worktrees:** Scan parallel worktrees of the tasks repo for IDs (in separate-repo,
   worktrees are per-tasks-repo; in same-repo, worktrees are the project's):
   ```bash
   tasks_git worktree list --porcelain 2>/dev/null | grep "^worktree " | while read _ path; do
     # In separate-repo, path is absolute to tasks repo; append TASKS_GIT_REL
     # In same-repo, path is absolute to project repo; append TASKS_GIT_REL as well
     cat "$path/$TASKS_GIT_REL" 2>/dev/null | grep -oE 'T-[0-9]+'
   done
   ```
4. **Next ID:** `max(local, remote, worktrees) + 1`
5. Format as `T-NNN` with zero-padding to 3 digits

### Step 2.3: Validate Dependencies

If the user specified dependencies:
1. **Self-reference check:** If any dependency ID matches the task's own ID → **STOP** immediately: "Task cannot depend on itself."
2. Verify each dependency ID exists in the table
3. Check for circular dependencies: if T-NEW depends on T-X, and T-X (directly or transitively) would depend on T-NEW → reject
4. If any dependency ID is invalid → ask the user to correct it

### Step 2.3.1: Resolve TaskSpec for the New Task

Ask the user how to handle the spec for this task. Always ask, even when Ring is available — the user may want to defer spec generation (e.g., creating multiple tasks in a row, batch-generating specs later).

> Note: This prompt offers Defer (not Cancel) because task creation can succeed without an immediate spec; the next `/optimus-plan T-XXX` will offer to resolve.

Ask via `AskUser`:

```
[topic] (1/1) How should I handle the spec for this task?
```

Options:
- **Generate via Ring** (recommended) — invoke `ring:pre-dev-feature` now
- **Link existing spec** — search `<TASKS_DIR>/tasks/` for matching specs
- **Defer** — set TaskSpec to `-`. The next `/optimus-plan T-XXX` run will offer to generate it later.

**If "Generate via Ring":**

1. **Choose the Ring track.** Read the task's `Estimate` column (the value the user just provided for this new task) and apply the auto-suggestion rule below to pick the recommended default. Ask via `AskUser`:

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

2. Verify the chosen Ring skill (`ring:pre-dev-feature` OR `ring:pre-dev-full`) is available. If unavailable → fall back to the OTHER track if it is available; if neither is available → warn and fall back to "Link existing spec" automatically.
3. Invoke the chosen Ring skill via the `Skill` tool. The Skill tool has no argument channel — state the task title and tipo in conversation context immediately before the invocation (e.g., "Generating spec for T-XXX: <title> (Tipo: <tipo>)"). Ring will read these from context.
4. **If Ring fails or returns no spec path:**
   - Warn the user: "Ring failed to generate the spec: <error>."
   - Re-prompt with `Link existing spec` / `Defer`. Do NOT silently fall through.
5. **If Ring succeeds:**
   - Ring generates the spec file in `<TASKS_DIR>/tasks/`.
   - Capture the generated spec file path (relative to `TASKS_DIR`).
   - Store as the `TaskSpec` value for this task.
6. **Record the chosen Ring track in state.json** — see AGENTS.md Protocol: State Management. If `.optimus/` does not yet exist, see AGENTS.md Protocol: Initialize .optimus Directory first. The snippet below performs an idempotent merge into the task's existing record (preserving any `status`, `branch`, `updated_at` fields):

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

**If "Link existing spec":**

1. Search `<TASKS_DIR>/tasks/*.md` for task files.
2. Rank candidates by keyword overlap with the task title; present the top 5 matches via `AskUser`.
3. User picks one or types a custom relative path under `<TASKS_DIR>/tasks/`.
4. **HARD BLOCK** — Validate the chosen path: (a) exists, (b) is a regular file (NOT a symlink), (c) resolves inside `<TASKS_DIR>` with no intermediate symlink components, (d) contains no pipe (`|`), control characters, newlines. Apply the realpath/case-glob/symlink rejection block from AGENTS.md Protocol: TaskSpec Resolution. If validation fails, do NOT write to optimus-tasks.md; loop back to the picker.
5. Store the chosen path as the `TaskSpec` value for this task.

**If "Defer":**

1. Set TaskSpec to `-`.
2. Note to user: "Task created without spec. Run `/optimus-plan T-XXX` later to generate or link one."

### Step 2.4: Apply Create

1. Add a new row to the table:
   ```
   | T-NNN | <title> | <tipo> | <depends> | <priority> | <version> | <estimate or -> | <taskspec or -> |
   ```
2. Save the file
3. **Re-validate after mutation** — see AGENTS.md Protocol: optimus-tasks.md Validation.
   If validation fails, abort and revert the in-memory edits; do not commit.

### Step 2.5: Confirm

Show the user the added task:
```
Created task T-NNN: <title>
  Tipo: <tipo>
  Priority: <priority>
  Version: <version>
  Depends on: <depends>
  Status: Pendente
```

