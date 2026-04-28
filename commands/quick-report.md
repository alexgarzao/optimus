---
description: Compact daily status dashboard. Shows version progress, active tasks with current status, ready-to-start, and blocked tasks. Mostly read-only — only writes .optimus/config.json defaultScope when user opts in.
---

# Quick Report

Compact daily status dashboard. Parses `optimus-tasks.md` and presents a focused overview:
version progress, active tasks with current status, ready-to-start tasks,
and blocked tasks.

**CRITICAL:** This agent is mostly read-only. The ONE allowed write is
`.optimus/config.json` `defaultScope` when the user explicitly opts in (see
`Protocol: Default Scope Resolution` in AGENTS.md). It NEVER modifies
`optimus-tasks.md`, `state.json`, code, or any other project file.

---

## Phase 1: Parse optimus-tasks.md

### Step 1.0: Resolve Paths and Git Scope

Execute AGENTS.md Protocol: Resolve Tasks Git Scope. This obtains `TASKS_DIR`,
`TASKS_FILE`, `TASKS_GIT_SCOPE`, `TASKS_GIT_REL`, and the `tasks_git` helper.

### Step 1.1: Locate and Validate

Tasks file is always at `<tasksDir>/optimus:tasks.md` (derived from `tasksDir`, default `docs/pre-dev`). If not found, inform the user and suggest `/optimus:import`.

Check the first line for `<!-- optimus:tasks-v1 -->`. If missing, warn but attempt best-effort parsing.

### Step 1.2: Parse Tables

1. Parse the `## Versions` table (Version, Status, Description)
2. Parse the tasks table (ID, Title, Tipo, Depends, Priority, Version, Estimate, TaskSpec)
3. Read status and branch for each task from `.optimus/state.json` — see AGENTS.md Protocol: State Management. Tasks with no entry are `Pendente`.
4. Identify the `Ativa` version

---

## Phase 2: Filter by Version and Classify Tasks

### Step 2.1: Determine Version Scope

Resolve the effective scope in this order — see AGENTS.md Protocol: Default Scope Resolution.

1. **Invocation wins.** If the user specified a scope in the invocation (e.g.,
   "quick report ativa", "quick report all", "quick report v2",
   "quick report upcoming"), use that scope directly. Skip sub-steps 2-4.

   **Force-ask keywords:** If the invocation contains `ask` or `menu` (e.g.,
   "quick report ask", "quick report menu"), skip sub-step 2 and go straight to the
   AskUser prompt (sub-step 3). Use this to override a saved default and optionally
   overwrite it.

2. **Config fallback.** If `.optimus/config.json` has a `defaultScope` key, use it
   without prompting. Validate the value (`ativa`, `upcoming`, `all`, or an existing
   version name). If invalid, warn and fall through to sub-step 3.

3. **Ask user.** Via `AskUser`:

   ```
   Which version scope do you want to see?
   ```
   Options:
   - **Ativa** — only tasks from the active version (<active_version_name>)
   - **Upcoming** — active + planned versions (Ativa, Próxima, Planejada — excludes Backlog and Concluída)
   - **All** — all tasks across all versions
   - **Specific version** — pick one version by name

   If the user selects **Specific version**, follow up with `AskUser` listing available
   version names as options.

4. **Offer to persist (only when sub-step 3 ran).** After the user picks a scope, ask:

   ```
   Save "<chosen_scope>" as the default in .optimus/config.json?
   You can still override per-invocation (e.g., "quick report all") or use
   "quick report ask" to be prompted again.
   ```
   Options:
   - **Save as default** — write `defaultScope` to `.optimus/config.json`
   - **Just this time** — do not persist

   **Exception to the read-only rule:** writing `defaultScope` to `.optimus/config.json`
   is the ONLY side-effect this skill is allowed to perform, and only when the user
   explicitly chooses "Save as default".

### Step 2.2: Apply Filter

**Scope mapping:**

| Scope | Versions included |
|-------|-------------------|
| `ativa` | Only the version with Status `Ativa` |
| `upcoming` | Versions with Status `Ativa`, `Próxima`, or `Planejada` |
| `all` | All versions |
| `<version_name>` | Only the named version |

Filter the task list to include only tasks whose **Version** column matches the selected
scope. Tasks from other versions are excluded from the ACTIVE, READY, BLOCKED,
and DONE sections below.

**Cross-version dependencies:** When a filtered task depends on a task from another version,
show the dependency with its version in brackets (e.g., `T-001 [MVP, DONE]`).

### Step 2.3: Classify Filtered Tasks

For each task **in the filtered set**:

- **Done:** Status is `DONE`
- **Cancelled:** Status is `Cancelado`
- **Active:** Status is `Validando Spec`, `Em Andamento`, or `Validando Impl`
- **Ready:** Status is `Pendente` AND all dependencies are `DONE` (or Depends is `-`)
- **Blocked:** Status is `Pendente` AND at least one dependency is NOT `DONE`

---

## Phase 3: Present Dashboard

Present a compact ASCII art dashboard. No json-render. Use box-drawing characters and
visual indicators to make task status immediately scannable.

### Version Progress Bar

Build an ASCII progress bar for the `Ativa` version. Width = 20 characters.
Filled chars = round(done / effective_total * 20). Effective total = Total - Cancelled.

```
═══════════════════════════════════════════════════
  <version> (<status>)  [████████████░░░░░░░░] Z% (X/Y)
═══════════════════════════════════════════════════
```

If other versions have non-done tasks, show a one-line summary below:
```
  Also: v2 (0/6), Futuro (0/3)
```

If ALL tasks are done:
```
═══════════════════════════════════════════════════
  <version>  [████████████████████] 100% (X/X) ALL DONE
═══════════════════════════════════════════════════
```

### Status Indicators

Each section uses a distinct ASCII symbol for instant visual recognition:

- **Active:** `⚙` (work in progress)
- **Ready:** `◇` (available, waiting to start)
- **Blocked:** `⊘` (cannot proceed)
- **Done:** `✓` (completed)

### Stage Progress Mini-Bar

For active tasks, render a mini progress bar showing how far the task
has advanced through the pipeline. The mapping is:

| Status | Stage | Filled chars |
|--------|-------|-------------|
| `Validando Spec` | 1/3 | 1 |
| `Em Andamento` | 2/3 | 2 |
| `Validando Impl` | 3/3 | 3 |

Examples: `[█░░] 1/3`, `[██░] 2/3`, `[███] 3/3`

### Section Format

```
  ✓ DONE (N)
    T-NNN <title>
    T-NNN <title>

  ⚙ ACTIVE (N)
    T-NNN <status>       — <title>              [██░] 2/3
    T-NNN <status>       — <title>              [███] 3/3

  ◇ READY (N)
    T-NNN [<priority>]   <title>
    T-NNN [<priority>]   <title>

  ⊘ BLOCKED (N)
    T-NNN <title>
        ├── T-XXX [⚙ <dep-status>]
        └── T-YYY [◇ <dep-status>]
    T-NNN <title>
        └── T-XXX [✓ DONE pending refresh]
```

### Rules

1. **Version progress** shows the `Ativa` version. Progress = Done / (Total - Cancelled).
   The progress bar counts only tasks from the active version.

2. **All sections (DONE, ACTIVE, READY, BLOCKED)** show only tasks from the filtered
   version(s) selected in Step 2.2.

3. **Active tasks** are sorted by status advancement (Validando Impl first, then
   Em Andamento, Validando Spec). Show stage progress mini-bar next to each task.

4. **Ready tasks** are sorted by Priority (`Alta` > `Media` > `Baixa`), then by ID.

5. **Blocked tasks** render dependencies as a tree using box-drawing characters.
   Each dependency appears on its own line with the appropriate status indicator symbol
   (`⚙` active, `◇` pending, `✓` done, `⊘` blocked, `✗` cancelled).
   Use `├──` for intermediate dependencies and `└──` for the last one.
   If a blocker has status `Cancelado`, show as `[✗ Cancelado — remove dep via /optimus:tasks]`.
   If a dependency is from another version, append the version: `[⚙ Em Andamento, v2]`.
   Example with multiple blockers:
   ```
     T-004 Password reset flow
         ├── T-002 [⚙ Em Andamento]
         └── T-003 [◇ Pendente]
   ```

6. **Omit empty sections.** If there are no active tasks, skip the ACTIVE section entirely.
   Same for READY, BLOCKED, and DONE.

7. **Progress bar characters:** Use `█` for filled and `░` for empty in the version
   progress bar (20 chars).

---

## Rules

- **NEVER modify any files** — read-only, with ONE exception: the user may opt in to
  persist their chosen scope to `.optimus/config.json` (see Step 2.1, sub-step 4).
  No other writes are allowed — no optimus-tasks.md, no state.json, no code.
- **NEVER run git commands** — this skill avoids git operations for speed
- **NEVER invoke other skills** — only report
- Present the dashboard even if there's only 1 task
- If optimus-tasks.md has no table or invalid format, suggest `/optimus:import`

<!-- INLINE-PROTOCOLS:START -->
## Shared Protocols (from AGENTS.md)

The following protocols are referenced by this skill. They are
extracted from the Optimus AGENTS.md to make this plugin self-contained.

### File Location (summarized)

> **Summary inlined here. Full recipe at `AGENTS.md -> File Location`.**

**Summary:** Defines where Optimus operational files live: `${MAIN_WORKTREE}/.optimus/{state.json, stats.json, sessions/, reports/, logs/}` (gitignored, per-user) vs `<tasksDir>/optimus:tasks.md` + `<tasksDir>/{tasks,subtasks}/` (versioned, project-team-shared, propagated by git). Also: `${MAIN_WORKTREE}/.gitignore` (versioned), `${MAIN_WORKTREE}/.worktrees/` (gitignored linked-worktree dir). Critical contract: `.optimus/*` paths NEVER propagate across linked worktrees (gitignored = not shared by `git worktree add`); use `${MAIN_WORKTREE}/` prefix consistently. See full table in AGENTS.md.

Optimus splits its files into two trees:

### Valid Status Values (stored in state.json) (summarized)

> **Summary inlined here. Full recipe at `AGENTS.md -> Valid Status Values (stored in state.json)`.**

**Summary:** state.json status values: `Pendente` (implicit, no entry), `Validando Spec` (plan), `Em Andamento` (build), `Validando Impl` (review), `DONE` (done), `Cancelado` (tasks/done). Administrative ops (Reopen, Advance, Demote, Cancel) require explicit user confirmation. See full table + transitions in AGENTS.md.

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

### Protocol: Resolve Main Worktree Path (summarized)

> **Summary inlined here. Full recipe at `AGENTS.md -> Protocol: Resolve Main Worktree Path`.**

**Summary:** Resolve `MAIN_WORKTREE` once via `git worktree list --porcelain | awk '/^worktree / {print $2; exit}'` with `${MAIN_WORKTREE:?…}` defensive guard. Use `${MAIN_WORKTREE}/.optimus/...` for ALL `.optimus/` paths (gitignored, so doesn't propagate across linked worktrees). See full recipe in AGENTS.md.

### Protocol: Default Scope Resolution

**Referenced by:** report, quick-report

Both `report` and `quick-report` support a version scope filter (`ativa`, `upcoming`,
`all`, or a specific version name). Resolve the effective scope in this order:

1. **Invocation wins.** If the user specified a scope in the invocation (e.g.,
   "quick report all", "report v2", "report upcoming"), use that scope directly.
   Skip steps 2-3.

   **Force-ask keywords:** If the invocation contains `ask` or `menu`
   (e.g., "quick report ask", "report menu"), skip step 2 and go straight to step 3
   (the AskUser prompt). This lets the user override the saved default for a single run
   and optionally overwrite it.

2. **Config fallback.** If `.optimus/config.json` has a `defaultScope` key, use it:
   ```bash
   CONFIG_FILE="${MAIN_WORKTREE}/.optimus/config.json"
   if [ -f "$CONFIG_FILE" ] && jq -e '.defaultScope' "$CONFIG_FILE" >/dev/null 2>&1; then
     SCOPE=$(jq -r '.defaultScope' "$CONFIG_FILE")
   fi
   ```
   **Validation:** `SCOPE` must be `ativa`, `upcoming`, `all`, or match a version name in
   the `## Versions` table of `optimus-tasks.md`. If invalid (empty, unknown keyword, or a version
   name that no longer exists), warn the user and fall through to step 3.
   ```
   WARNING: .optimus/config.json has defaultScope="<value>" but it is not valid
   (must be ativa/upcoming/all or an existing version name). Falling back to prompt.
   ```

3. **Ask user.** Present the standard AskUser prompt:
   ```
   Which version scope do you want to see?
   ```
   Options:
   - **Ativa** — only tasks from the active version (`<active_version_name>`)
   - **Upcoming** — active + planned (Ativa, Próxima, Planejada — excludes Backlog and Concluída)
   - **All** — all tasks across all versions
   - **Specific version** — pick one version by name (follow-up AskUser lists versions)

4. **Offer to persist (only when step 3 ran).** After the user picks a scope in step 3,
   ask a follow-up via AskUser:
   ```
   Save "<chosen_scope>" as the default in .optimus/config.json?
   You can still override per-invocation (e.g., "quick report all") or
   use "quick report ask" to be prompted again.
   ```
   Options:
   - **Save as default** — write `defaultScope` to `.optimus/config.json`
   - **Just this time** — do not persist

5. **Persist the scope (if user chose to save):**
   ```bash
   # Initialize .optimus directory — see AGENTS.md Protocol: Initialize .optimus Directory.
   CONFIG_FILE="${MAIN_WORKTREE}/.optimus/config.json"
   if [ ! -f "$CONFIG_FILE" ]; then
     echo '{}' > "$CONFIG_FILE"
   fi
   if jq --arg s "$SCOPE" '.defaultScope = $s' "$CONFIG_FILE" > "${CONFIG_FILE}.tmp"; then
     if jq empty "${CONFIG_FILE}.tmp" 2>/dev/null; then
       mv "${CONFIG_FILE}.tmp" "$CONFIG_FILE"
     else
       rm -f "${CONFIG_FILE}.tmp"
       echo "ERROR: jq produced invalid JSON — config.json unchanged"
     fi
   else
     rm -f "${CONFIG_FILE}.tmp"
     echo "ERROR: jq failed to update config.json"
   fi
   ```
   **NOTE:** `config.json` is gitignored (per-user preference). The saved `defaultScope`
   affects only the local environment — each user can choose their own default. These
   skills are read-only for code/tasks — writing to `config.json` is the single allowed
   side-effect, and only when the user explicitly agrees.

**NOTE:** Scope names are case-insensitive for user input. Normalize to lowercase for
`ativa`/`upcoming`/`all`, but preserve the original casing when the scope is a specific
version name (version names are case-sensitive to match the Versions table).

Skills reference this as: "Resolve default scope — see AGENTS.md Protocol: Default Scope Resolution."


### Protocol: Resolve Tasks Git Scope (summarized)

> **Summary inlined here. Full recipe at `AGENTS.md -> Protocol: Resolve Tasks Git Scope`.**

**Summary:** Resolves `TASKS_DIR` (from `.optimus/config.json` `tasksDir` key, default `docs/pre-dev`) and `TASKS_FILE` (`<tasksDir>/optimus:tasks.md`), then detects whether tasksDir lives inside the project repo (`same-repo`) or a separate git repo (`separate-repo`). Sets `TASKS_REPO_ROOT`, `TASKS_GIT_REL`, `TASKS_DEFAULT_BRANCH`, and exposes a `tasks_git()` helper that wraps `git -C "$TASKS_DIR"` in separate-repo mode. Hard guards: reject `tasksDir` starting with `-` (git-option injection), require `python3` for separate-repo path computation, validate `TASKS_DEFAULT_BRANCH` against `^[a-zA-Z0-9._/-]+$`. Skills MUST use `tasks_git` (never raw `git`) on `$TASKS_FILE`. See full recipe in AGENTS.md.

### Protocol: State Management (summarized)

> **Summary inlined here. Full recipe at `AGENTS.md -> Protocol: State Management`.**

**Summary:** Read/write/delete entries in `${MAIN_WORKTREE}/.optimus/state.json` with `jq`. Schema: `{task_id: {status, branch, updated_at}}`. Status values: `Pendente | Validando Spec | Em Andamento | Validando Impl | DONE | Cancelado`. All writes use `jq --arg id "$TASK_ID" --arg status "$NEW_STATUS" '.[$id] = {...}'` (injection-safe), with a tmp-file + `jq empty` validation step before `mv` to guarantee atomicity. Cancelado entries keep `branch: ""` (empty string, NOT absent — readers must treat both as Cancelado-state). Corrupted state.json is removed and treated as empty (reconciliation via worktree scan). state.json is gitignored; never committed. See full recipe in AGENTS.md for jq templates and reconciliation steps.

<!-- INLINE-PROTOCOLS:END -->
