# Rules — Anti-Patterns and Guardrails for optimus-tasks

**Load this file BEFORE deviating from the happy path, when the user asks for
a destructive operation, or when you encounter an ambiguous instruction.**
Tasks is an administrative skill — the rules below define the validation
invariants and the destructive-op confirmation contract.

## Core Rules

1. **Status changes are restricted** — the Edit operation cannot change status (use Reopen, Advance, or Demote operations instead, which write to state.json). Status and Branch live in state.json, not in optimus-tasks.md.
2. **Always validate format** after any modification (re-check marker, columns, IDs, deps, versions)
3. **IDs are permanent** — never renumber or reuse deleted IDs
4. **Circular dependency detection is mandatory** — check before saving
5. **Confirm destructive operations** (remove) with the user before executing
6. **Preserve format marker** — first line must always be `<!-- optimus:tasks-v1 -->`
7. **Commit changes** — after any structural modification to optimus-tasks.md, commit with message: `chore(tasks): <operation> T-XXX`. Status changes (state.json) are NOT committed — state.json is gitignored.
8. **Version validation** — every task must reference a version that exists in the Versions table
9. **Exactly one Ativa version** — when setting a version to `Ativa`, the current `Ativa` must be demoted (ask user)
10. **At most one Próxima version** — when setting a version to `Próxima`, the current `Próxima` must be demoted to `Planejada` (ask user)
