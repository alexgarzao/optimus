# Rules — Anti-Patterns and Guardrails for optimus-done

**Load this file BEFORE deviating from the happy path, when the user asks to skip a
gate, or when you encounter an ambiguous instruction.** Claude should consult this
file proactively; smaller models can run the happy path without it but MUST load it
when a deviation is requested.

## Core Rules

- Gates are sequential hard blocks — stop at the first failure
- Do NOT change task status unless ALL gates pass
- After marking as done, update state.json (no commit needed — it's gitignored)
- Lint, tests, and CI are the responsibility of the PR pipeline — done does NOT run them
- To cancel a task without going through gates, use `/optimus-tasks cancel`
- **Next step suggestion:** After the cleanup summary, inform the user: "Task T-XXX is done.
  Run `/optimus-report` to see updated project status and what to work on next."

## Dry-Run Mode

Follow AGENTS.md Protocol: Dry-Run Mode. The canonical rules apply uniformly
to plan/build/review/done — see the inlined Protocol: Dry-Run Mode block in
`SKILL.md` Shared Protocols section.

**Stage-4 (done) specifics:**
- The "no status change" rule means skip the DONE status update.
- The "no fix application" rule means skip Phase 4 (cleanup) entirely.
- All 4 gates (Phase 2) still run in full so the user sees what would have
  happened.
