---
name: optimus-help
description: "Lists all available Optimus skills with descriptions, usage commands, and when to use each one. Helps users discover what's available and choose the right skill for their situation."
trigger: >
  - When user asks "what skills are available?" or "help"
  - When user asks "what can Optimus do?"
  - When user is unsure which skill to use
  - When user says "optimus help" or "list skills"
skip_when: >
  - User already knows which skill to use and invoked it directly
prerequisite: >
  - None — this skill works without any project context
NOT_skip_when: >
  - "I know what I want" -- Help may reveal skills you didn't know existed.
examples:
  - name: List all skills
    invocation: "What Optimus skills are available?"
    expected_flow: >
      1. Present categorized skill list with descriptions and commands
  - name: Help choosing a skill
    invocation: "I want to review code, which skill should I use?"
    expected_flow: >
      1. Present the review/analysis skills with comparison
      2. Recommend based on user's situation
---

# Optimus Help

Lists all available Optimus skills organized by category.

---

## Phase 1: Present Skill Catalog

**Prerequisites:** Optimus requires the Ring ecosystem (droids + pre-dev workflow).
Execution skills (plan, build, review, done) and review skills (pr-check, deep-review,
coderabbit-review) require Ring droids to be installed. Administrative skills (import,
report, tasks, resolve, resume, quick-report, help) work without Ring droids.

Present the following catalog to the user. Use the `<json-render>` format for rich
terminal display when available, otherwise use markdown tables.

### Administrative Skills (run on any branch)

| Skill | Command | When to Use |
|-------|---------|-------------|
| **import** | `/optimus-import` | Import Ring pre-dev artifacts into optimus format. Creates tasks.md with TaskSpec column. Re-runnable — only imports what's new. |
| **report** | `/optimus-report` | Task status dashboard — shows progress, active/blocked/ready tasks, dependency graph, and parallelization opportunities. Read-only. |
| **tasks** | `/optimus-tasks` | Creating, editing, removing, reordering, cancelling, or reopening tasks. Managing versions. Any administrative task management. |
| **resolve** | `/optimus-resolve` | Resolving merge conflicts in `tasks.md` caused by parallel task execution across feature branches. |
| **resume** | `/optimus-resume` | Resume a task after closing the terminal — locates/recreates the worktree for a given T-XXX, reports current status, and offers to invoke the next stage. Read-only on state.json except for a user-confirmed Reset-to-Pendente recovery. |
| **quick-report** | `/optimus-quick-report` | Compact daily status dashboard — shows version progress, active tasks with current status, ready-to-start, and blocked tasks. Read-only. |
| **batch** | `/optimus-batch` | Pipeline orchestrator — chains stages 1-4 for one or more tasks with user checkpoints between stages. |
| **help** | `/optimus-help` | This skill — discovering what's available. |
| **sync** | `/optimus-sync` | Sync all Optimus plugins — install new, update existing, remove orphaned. Recommended after new releases. |

### Execution Skills (task lifecycle, stages 1-4)

These skills form the task execution pipeline. Run them in order for each task:

```
Pendente → Validando Spec → Em Andamento → Validando Impl → DONE
           (plan)            (build)        (review)         (done)
```

| Skill | Command | When to Use |
|-------|---------|-------------|
| **plan** | `/optimus-plan` | Before implementing a task — validates the spec against project docs, catches gaps, contradictions, and test coverage holes. Creates the workspace (branch/worktree). |
| **build** | `/optimus-build` | After spec validation — implements the task end-to-end with TDD, verification gates, and code review. |
| **review** | `/optimus-review` | After implementation — validates code quality, spec compliance, and test coverage using parallel specialist agents. |
| **done** | `/optimus-done` | Final step — requires PR in final state (merged or closed), then marks task as DONE. Cleans up worktree and branch interactively. |

### Review & Verification Skills (standalone, no task required)

| Skill | Command | When to Use |
|-------|---------|-------------|
| **pr-check** | `/optimus-pr-check` | PR review — collects findings from Codacy, DeepSource, CodeRabbit, and human reviewers. Standalone tool, does not change task status. |
| **deep-review** | `/optimus-deep-review` | Code review with auto-discovered Ring droids — reviews entire project, git diff, or specific directory. Dispatches all installed review droids in parallel. |
| **deep-doc-review** | `/optimus-deep-doc-review` | Documentation review — finds errors, inconsistencies, gaps, and improvements with interactive one-by-one resolution. |
| **coderabbit-review** | `/optimus-coderabbit-review` | Code review using CodeRabbit CLI with TDD fix cycle and agent validation. Requires CodeRabbit CLI installed. |


### Command Aliases

Each plugin includes a short alias for quick access:

| Alias | Full Command | Alias | Full Command |
|-------|-------------|-------|-------------|
| `/sp` | `/optimus-plan` | `/dr` | `/optimus-deep-review` |
| `/bd` | `/optimus-build` | `/ddr` | `/optimus-deep-doc-review` |
| `/rv` | `/optimus-review` | `/cr` | `/optimus-coderabbit-review` |
| `/dn` | `/optimus-done` | `/prc` | `/optimus-pr-check` |
| `/bt` | `/optimus-batch` | `/im` | `/optimus-import` |
| `/qr` | `/optimus-quick-report` | `/rs` | `/optimus-resolve` |
| `/rp` | `/optimus-report` | `/t` | `/optimus-tasks` |
| `/rsm` | `/optimus-resume` | | |

---

## Phase 2: Situational Guidance

If the user asked for help choosing a skill (not just listing), provide guidance based
on their situation:

### "I want to review code"
- **For a PR:** Use `/optimus-pr-check` (collects all review sources)
- **For code without a PR:** Use `/optimus-deep-review` (parallel agent review)
- **Using CodeRabbit:** Use `/optimus-coderabbit-review` (CodeRabbit + TDD cycle)
- **Quick pass/fail check:** Run `make lint && make test` directly

### "I want to start working on a task"
1. First: `/optimus-report` to see what's ready
2. Then: `/optimus-plan` to validate and create workspace
3. Then: `/optimus-build` to implement
4. Or use `/optimus-batch` to run all stages in sequence with checkpoints

### "I closed the terminal, how do I resume the task I was working on?"
- Use `/optimus-resume T-XXX` — sets up the worktree for T-XXX and offers to invoke the next stage
- If you forgot which task, run `/optimus-resume` alone — it auto-detects if there is exactly one in-progress task

### "I want a quick status check"
- Use `/optimus-report` with "quick status" — shows only current task and next-up

### "I have a merge conflict in tasks.md"
- Use `/optimus-resolve` to auto-resolve structural conflicts (each task row is independent)

### "I completed a task outside the pipeline"
- Use `/optimus-tasks advance T-XXX` to move the task forward manually

### "I want to preview what a stage would do"
- Add "dry-run" to any stage command (e.g., "dry-run spec T-003", "preview review T-012")

### "I want to check project status"
- Use `/optimus-report` for the full dashboard

### "I want to manage tasks"
- Use `/optimus-tasks` for create/edit/remove/cancel/reopen

### "I want to review documentation"
- Use `/optimus-deep-doc-review` for cross-doc analysis

---

## Rules

- This skill is read-only — it NEVER modifies any files
- Present the full catalog even if the user asked about a specific category
- If the user's situation doesn't match any guidance, suggest `/optimus-report` as a starting point
