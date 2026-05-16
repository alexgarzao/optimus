---
name: optimus-report
description: "Task status dashboard. Reads optimus-tasks.md, computes dependency graph, and presents a comprehensive project status report. Shows progress, active tasks, blocked tasks, ready-to-start tasks, dependency graph, and parallelization opportunities. Mostly read-only — only writes .optimus/config.json defaultScope when user opts in."
trigger: >
  - When user asks for project status (e.g., "show tasks", "project status", "what's ready?")
  - When user wants to know what can be parallelized
  - When user asks "what should I work on next?"
  - Before starting a new task (to see the full picture)
  - When user asks "quick status", "what am I working on?", "current task"
skip_when: >
  - No optimus-tasks.md exists in the project
  - User wants to run a specific stage agent (use that agent directly)
prerequisite: >
  - <tasksDir>/optimus-tasks.md exists in the project (default tasksDir: docs/pre-dev)
NOT_skip_when: >
  - "I already know the status" -- The dashboard shows dependencies and parallelization you might miss.
  - "There's only one task" -- Even single tasks benefit from status verification.
examples:
  - name: Full project status
    invocation: "Show project status"
    expected_flow: >
      1. Find and parse optimus-tasks.md
      2. Compute dependency graph
      3. Classify tasks (done, active, ready, blocked)
      4. Present dashboard with all sections
  - name: What to work on next
    invocation: "What can I work on next?"
    expected_flow: >
      1. Parse optimus-tasks.md
      2. Find tasks with status Pendente and all dependencies DONE
      3. Present ready-to-start tasks with priority ordering
  - name: Quick status check
    invocation: "Quick status" or "What am I working on?"
    expected_flow: >
      1. Parse optimus-tasks.md
      2. Show only: current active task, its progress status, and next-up
      3. Skip dependency graph, parallelization, velocity, and completed tasks
related:
  complementary:
    - optimus-plan
    - optimus-build
verification:
  manual:
    - Dashboard displays correctly
    - Dependency graph is accurate
    - Blocked tasks correctly identified
    - Parallelization opportunities are valid
---

# Task Status Dashboard

Read-only agent that parses `optimus-tasks.md` and presents a comprehensive
project status report.

**CRITICAL:** This agent is effectively read-only. It may write ONLY to
`.optimus/config.json` (`defaultScope`) and to `.optimus/reports/` (exports),
and only when the user explicitly opts in. It never modifies
`optimus-tasks.md`, `state.json`, code, or any other project file.

## Operating Mode

This skill is structured as an **executable index**: each phase lives in its
own file under `phases/`, loaded on demand. **Before executing a phase, you
MUST `Read` the phase file in full**.

For deviations, ambiguous instructions, or any "write to a project file"
request, **you MUST `Read` `rules.md` BEFORE answering** — the write-allowlist
is narrow and enforced there.

## Phases

Run phases in order. Before each phase, **`Read` the phase file**, then execute its steps.

1. **Phase 1 — Discover and Detect Mode.** Read `phases/01-discover.md`. Find and parse optimus-tasks.md, detect quick-status mode from command intent.
2. **Phase 2 — Classify, Filter, and Summarize.** Read `phases/02-classify-and-filter.md`. Classify tasks by status, filter by active version, version-progress summary.
3. **Phase 3 — Dependency Graph and Parallelization.** Read `phases/03-graph-and-parallel.md`. Compute the dependency graph and identify parallelization opportunities.
4. **Phase 4 — Present Dashboard.** Read `phases/04-present-dashboard.md`. Render the full dashboard (active/ready/blocked queues, graph, parallelization, churn).
5. **Phase 5 — Velocity and Stage Stats.** Read `phases/05-velocity-stats.md`. Velocity history metrics and stage execution counters from stats.json.
6. **Phase 6 — Warnings and Export.** Read `phases/06-warnings-export.md`. Surface warnings (stale tasks, missed deps, format issues) and offer optional export.

## Rules Summary

The full ruleset lives in `rules.md` — **`Read` it before any deviation, dry-run, or skip request**. The non-negotiables:

- **Strictly read-only** with two narrow exceptions: exports to `.optimus/reports/` and `defaultScope` writes to `.optimus/config.json` (only when user opts in).
- **NEVER changes task status** — only reports.
- **NEVER invokes other stage agents** — only recommends.
- **Always shows the dependency graph** — even for small projects.
- **At any moment if instruction is ambiguous, conflicting, or the user requests a write outside the allowlist → Read `rules.md` before answering.**

<!-- INLINE-PROTOCOLS:START -->
## Shared Protocols (from AGENTS.md)

The following protocols are referenced by this skill. They are
extracted from the Optimus AGENTS.md to make this plugin self-contained.

### Protocol: Initialize .optimus Directory (summarized)

> **Summary inlined here. Full recipe at `AGENTS.md -> Protocol: Initialize .optimus Directory`.**

**Summary:** Create `${MAIN_WORKTREE}/.optimus/{sessions,reports,logs}/` with `mkdir -p`. Add `# optimus-operational-files` and `# optimus-operational-worktrees` markers to `${MAIN_WORKTREE}/.gitignore` idempotently (grep-anchor before append). Refuse symlinked `.gitignore`. Auto-prune `.optimus/logs/` (30 days, 500 files). See full recipe in AGENTS.md.

### Protocol: State Management (summarized)

> **Summary inlined here. Full recipe at `AGENTS.md -> Protocol: State Management`.**

**Summary:** Read/write/delete entries in `${MAIN_WORKTREE}/.optimus/state.json` with `jq`. Schema: `{task_id: {status, branch, updated_at}}`. Status values: `Pendente | Validando Spec | Em Andamento | Validando Impl | DONE | Cancelado`. All writes use `jq --arg id "$TASK_ID" --arg status "$NEW_STATUS" '.[$id] = {...}'` (injection-safe), with a tmp-file + `jq empty` validation step before `mv` to guarantee atomicity. Cancelado entries keep `branch: ""` (empty string, NOT absent — readers must treat both as Cancelado-state). Corrupted state.json is removed and treated as empty (reconciliation via worktree scan). state.json is gitignored; never committed. See full recipe in AGENTS.md for jq templates and reconciliation steps.

<!-- INLINE-PROTOCOLS:END -->
