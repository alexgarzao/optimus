# Rules — Anti-Patterns and Guardrails for optimus-resume

**Load this file BEFORE deviating from the happy path, when the user asks to
skip a step, or when you encounter an ambiguous instruction.** Resume is an
administrative skill — the rules below are non-negotiable.

## Core Rules

- **Admin skill** — runs on any branch, does not alter task status.
- NEVER writes to `stats.json`, `optimus-tasks.md`, or `.optimus/sessions/session-T-XXX.json`.
- **state.json is read-only EXCEPT** for the user-confirmed "Reset to Pendente" recovery
  option in Phase 3 Step 3.3 Case 3 (inconsistent state). No other mutation is permitted.
- Creates a worktree ONLY in the recovery path (Phase 3 Step 3.3 case 2). Never creates branches.
- Does NOT offer `Resume / Start fresh / Continue` prompts (coherent with `/optimus-done`).
- Does NOT invoke another stage automatically — only when the user explicitly picks it in Phase 5.
- Respects dry-run mode: no worktree creation, no delegation to other skills, no mutation of state.json.
- Does NOT run `make lint` / `make test` — verification is the responsibility of the target stage.
- **Skill tool contract:** when delegating to another skill, invoke it via the `Skill` tool;
  the `Skill` tool has no argument channel, so `TASK_ID` is carried by conversation context.
  The delegate will perform its own expanded-confirmation via `AskUser`. Resume does NOT
  bypass any predecessor checks.

## Override vs Inlined Protocol: State Management

The inlined `Protocol: State Management` (auto-generated below the shared-protocols
block in `SKILL.md`) contains a destructive fallback — `rm -f "$STATE_FILE"` on
corruption. **Resume explicitly DOES NOT apply that fallback**: on corruption it
STOPs with guidance (Phase 1 Step 1.4 / Phase 2 Step 2.2a). Treat the inlined block
as foundational context only; the rules here override it.

## Anti-rationalization

The agent MUST NOT use these excuses to skip or reorder steps:

- "I know the worktree path, I'll just cd manually" — the skill still needs to validate the task and render the summary.
- "The user clearly wants /optimus-build, let me just run it" — wait for the Phase 5 AskUser decision.
- "state.json is missing or corrupted, let me `rm -f` to recover" — NO. The inlined Protocol
  does that, but resume explicitly overrides it: STOP and ask the user to fix state.json.
- "state.json is missing, let me infer from git worktree list" — that triggers the reconciliation guidance in State Management, not a silent recovery.
- "The branch exists but the name differs from the derivation, close enough" — prefer the state.json branch field; do not use fuzzy matches silently.
- "TASK_ID is empty but the only worktree is the right one" — NO. An empty TASK_ID is a HARD BLOCK; refuse before touching git.
- "I'll skip the dependency check because the user will figure it out" — NO. If BLOCKING_DEPS is non-empty, hide the stage options and surface the warning.
