# Phase 1: Discover and Detect Mode

Loaded by SKILL.md first. Find and parse optimus-tasks.md, then detect quick-status mode (filter by command intent).

### Step 1.0: Resolve Paths and Git Scope

Execute AGENTS.md Protocol: Resolve Tasks Git Scope. This obtains `TASKS_DIR`,
`TASKS_FILE`, `TASKS_GIT_SCOPE`, `TASKS_GIT_REL`, and the `tasks_git` helper.

### Step 1.1: Locate optimus-tasks.md

Tasks file is always at `<tasksDir>/optimus-tasks.md` (derived from `tasksDir`, default `docs/pre-dev`).

If not found, inform the user and suggest: "No optimus-tasks.md found. Run `/optimus-import` to create one from existing task files, or create it manually following the optimus format."

### Step 1.1.1: Validate Format Marker

Check that the **first line** of `optimus-tasks.md` is `<!-- optimus:tasks-v1 -->`.

If missing, warn the user: "optimus-tasks.md exists but is not in optimus format (missing `<!-- optimus:tasks-v1 -->` marker). Run `/optimus-import` to convert it."

The report agent still ATTEMPTS to parse and display data even without the marker (best effort), but shows the warning prominently.

### Step 1.1.2: Default Branch Warning

Detect if the report is being run on the default branch:

```bash
DEFAULT_BRANCH=$(git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's@^refs/remotes/origin/@@')
if [ -z "$DEFAULT_BRANCH" ]; then
  DEFAULT_BRANCH=$(git branch --list main master 2>/dev/null | head -1 | tr -d ' *')
fi
CURRENT_BRANCH=$(git branch --show-current 2>/dev/null)
```

If `CURRENT_BRANCH` equals `DEFAULT_BRANCH` (or is `main`/`master`):

Since status lives in `.optimus/state.json` (local), it is always up-to-date regardless
of which branch is checked out. No branch-specific warning is needed.

Skip this step silently.

### Step 1.2: Parse the Tasks Table

Read `optimus-tasks.md` and extract the markdown table. Expected columns:

| Column | Description |
|--------|-------------|
| ID | Task identifier (e.g., T-001) |
| Title | Short description |
| Tipo | Task type: Feature, Fix, Refactor, Chore, Docs, or Test |
| Depends | Comma-separated dependency IDs, or `-` for none |
| Priority | Alta, Media, or Baixa |
| Version | Version/milestone this task belongs to |
| Estimate | Task size estimate (S, M, L, XL, etc.), or `-` |
| TaskSpec | Path to Ring pre-dev task spec (optional — `-` if not linked) |

**Status and Branch** are read from `.optimus/state.json` — see AGENTS.md Protocol: State Management.
Tasks with no entry in state.json are `Pendente`.

### Step 1.2.1: Parse Versions Table

Read the `## Versions` section and extract the versions table. Expected columns:
- Version (name), Status (`Ativa`, `Próxima`, `Planejada`, `Backlog`, `Concluída`), Description

Identify the version with Status `Ativa` — this is the **active version** used for default filtering.

For each task, check if the `TaskSpec` column has a value (not `-`) to verify completeness.

### Step 1.3: Validate Dependencies

For each task with dependencies:
1. Verify all referenced task IDs exist in the table
2. Check for circular dependencies (A→B→A)
3. If invalid dependencies found, report them as warnings in the dashboard

---

### Phase 2: Quick Status Mode Detection

If the user's invocation matches quick status triggers ("quick status", "what am I working on?",
"current task", "status rápido"):

1. Parse optimus-tasks.md (Phase 1 still runs fully)
2. Find tasks with status other than `Pendente`, `DONE`, and `Cancelado` (active tasks)
3. For each active task, read its Ring source via the `TaskSpec` column for context
4. Present ONLY:

```
Quick Status:
  Active: T-XXX — [title] (Em Andamento)
  Next up: T-YYY — [title] (Pendente, ready to start)
```

5. **STOP here** — do NOT proceed to the remaining phases (dependency graph, parallelization, velocity, etc.)

If the invocation does NOT match quick status triggers, proceed to Phase 3 normally.

---
