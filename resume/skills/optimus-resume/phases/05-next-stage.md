# Phase 5: Offer Next Stage

Loaded after Phase 4 prints the summary. Asks the user via AskUser which stage to invoke next. Dependency-aware and PR-state-aware option suppression. On delegation, restore terminal via mark-session.sh clear.

Ask the user via `AskUser`:

```
Next step for T-XXX (<status>):
```

**Dependency-aware options.** If `BLOCKING_DEPS` is non-empty, the stage options are
hidden — delegating would fail immediately on the dependency gate. Offer only:

- **Run /optimus-report** — to review the blocking dependencies.
- **Skip** — workspace is ready; user decides how to proceed.

**PR-state suppressor.** If `PR_STATE` starts with `UNKNOWN` (gh failure: unavailable,
unauthenticated, network/rate-limit), the `Validando Impl` options collapse to:

- **Re-run /optimus-review** / **Skip**

The user is asked to investigate gh before picking a stage that depends on PR state.

Otherwise (no blocking deps, PR state known), options are chosen from status + PR state:

- `Validando Spec`: **Run /optimus-build** / **Skip**
- `Em Andamento`: **Run /optimus-review** / **Re-run /optimus-build** / **Skip**
- `Validando Impl` + PR OPEN: **Run /optimus-pr-check** / **Run /optimus-done** / **Re-run /optimus-review** / **Skip**
- `Validando Impl` + PR MERGED/CLOSED: **Run /optimus-done** / **Re-run /optimus-review** / **Skip**
- `Validando Impl` + no PR (NONE): **Run /optimus-done** (will likely require a PR) / **Re-run /optimus-review** / **Skip**

**Skill tool contract (accurate wording).** If the user picks a stage, invoke the
corresponding skill via the `Skill` tool (e.g., `optimus-build`, `optimus-pr-check`,
`optimus-done`). The `Skill` tool accepts only the skill name — it has no argument
channel for `TASK_ID`. The delegate will locate the task from the conversation context
and run its own expanded confirmation via `AskUser` (it does NOT skip this step).
Resume does NOT bypass any predecessor checks the delegate performs.

**If the user picks Skip:** inform them the workspace is ready and they can run the
recommended command whenever they like.

**Skip the whole Phase 5 step** when running in dry-run mode.

---
