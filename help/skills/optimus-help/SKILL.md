---
name: optimus-help
description: >
  Lists all available Optimus skills with descriptions, usage commands, and
  when to use each one. Helps users discover what's available and choose the
  right skill for their situation.
trigger: >
  - When user asks "what skills are available?" or "help"
  - When user asks "what can Optimus do?"
  - When user is unsure which skill to use
  - When user says "optimus help" or "list skills"
skip_when: >
  - User already knows which skill to use and invoked it directly
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

## Phase 0: Present Skill Catalog

Present the following catalog to the user. Use the `<json-render>` format for rich
terminal display when available, otherwise use markdown tables.

### Administrative Skills (run on any branch)

| Skill | Command | When to Use |
|-------|---------|-------------|
| **cycle-migrate** | `/optimus-cycle-migrate` | Setting up Optimus on a project for the first time. Converts existing task files to the standard `tasks.md` format. |
| **cycle-report** | `/optimus-cycle-report` | Checking project status — shows progress, active/blocked/ready tasks, dependency graph, parallelization opportunities, and velocity metrics. Read-only. |
| **cycle-crud** | `/optimus-cycle-crud` | Creating, editing, removing, reordering, cancelling, or reopening tasks. Managing versions. Any administrative task management. |
| **help** | `/optimus-help` | This skill — discovering what's available. |

### Execution Skills (task lifecycle, stages 1-5)

These skills form the task execution pipeline. Run them in order for each task:

```
Pendente → Validando Spec → Em Andamento → Validando Impl → [Revisando PR] → DONE
           (stage-1)          (stage-2)       (stage-3)        (stage-4)       (stage-5)
```

| Skill | Command | When to Use |
|-------|---------|-------------|
| **cycle-spec-stage-1** | `/optimus-cycle-spec-stage-1` | Before implementing a task — validates the spec against project docs, catches gaps and contradictions. Creates the workspace (branch/worktree). |
| **cycle-impl-stage-2** | `/optimus-cycle-impl-stage-2` | After spec validation — implements the task end-to-end with TDD, verification gates, and code review. |
| **cycle-impl-review-stage-3** | `/optimus-cycle-impl-review-stage-3` | After implementation — validates code quality, spec compliance, and test coverage using parallel specialist agents. |
| **cycle-pr-review-stage-4** | `/optimus-cycle-pr-review-stage-4` | (Optional) After impl review — orchestrates PR review collecting findings from Codacy, DeepSource, CodeRabbit, and human reviewers. Also works standalone without a task. |
| **cycle-close-stage-5** | `/optimus-cycle-close-stage-5` | Final step — verifies all prerequisites (tests, lint, PR ready) and marks the task as DONE. Offers to merge the PR. |

### Review & Verification Skills (standalone, no task required)

| Skill | Command | When to Use |
|-------|---------|-------------|
| **deep-review** | `/optimus-deep-review` | Generic code review without task context — reviews entire project, git diff, or specific directory with parallel specialist agents. |
| **deep-doc-review** | `/optimus-deep-doc-review` | Documentation review — finds errors, inconsistencies, and gaps across project docs with cross-referencing. |
| **coderabbit-review** | `/optimus-coderabbit-review` | Code review using CodeRabbit CLI with TDD fix cycle and agent validation. Requires CodeRabbit CLI installed. |
| **verify** | `/optimus-verify-code` | Quick automated verification — runs lint, vet, format checks, and tests in parallel. Reports MERGE_READY or NEEDS_FIX verdict. |

---

## Phase 1: Situational Guidance

If the user asked for help choosing a skill (not just listing), provide guidance based
on their situation:

### "I want to review code"
- **For a PR:** Use `/optimus-cycle-pr-review-stage-4` (collects all review sources)
- **For code without a PR:** Use `/optimus-deep-review` (parallel agent review)
- **Using CodeRabbit:** Use `/optimus-coderabbit-review` (CodeRabbit + TDD cycle)
- **Quick pass/fail check:** Use `/optimus-verify-code` (automated checks only)

### "I want to start working on a task"
1. First: `/optimus-cycle-report` to see what's ready
2. Then: `/optimus-cycle-spec-stage-1` to validate and create workspace
3. Then: `/optimus-cycle-impl-stage-2` to implement

### "I want to check project status"
- Use `/optimus-cycle-report` for the full dashboard

### "I want to manage tasks"
- Use `/optimus-cycle-crud` for create/edit/remove/cancel/reopen

### "I want to review documentation"
- Use `/optimus-deep-doc-review` for cross-doc analysis

---

## Rules

- This skill is read-only — it NEVER modifies any files
- Present the full catalog even if the user asked about a specific category
- If the user's situation doesn't match any guidance, suggest `/optimus-cycle-report` as a starting point
