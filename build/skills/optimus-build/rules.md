# Rules — Anti-Patterns and Guardrails for optimus-build

**Load this file BEFORE deviating from the happy path, when the user asks to skip a
subtask checkpoint, or when you encounter an ambiguous instruction.** Claude
should consult this file proactively; smaller models can run the happy path
without it but MUST load it when a deviation is requested.

## Scope Discipline

- Implement EXACTLY what the task spec says — no more, no less
- Do not refactor existing code unless the task requires it
- Do not fix unrelated bugs found during implementation (flag them to the user)
- Do not add "nice to have" improvements

## Error Handling

- If a ring droid reports a blocker, present it to the user with context from Phase 1
- If you discover a gap in the task spec during Phase 1, ask the user before starting implementation

## Communication

- Update the todo list at Phase 1 completion and after each subtask completes
- Report subtask progress as each completes (X/N)
- Never go silent — always present results and ask before proceeding
- **Next step suggestion:** After the final commit, inform the user: "Implementation
  complete. Next step: run `/optimus-review` to validate this task."

## Dry-Run Mode

Follow AGENTS.md Protocol: Dry-Run Mode. The canonical rules apply uniformly
to plan/build/review/done — see the inlined Protocol: Dry-Run Mode block in
`SKILL.md` Shared Protocols section.

**Stage-2 (build) specifics:**
- The "no status change" rule means skip the state.json write in Phase 1 Step 1.3.
- The "no fix application" rule means skip Phase 2 (implementation) entirely.
- The "no commit/push" rule means skip Phase 3 commits.
- Phase 1 still runs in full so the user gets a complete preview of what would
  be implemented, estimated effort, and identified risks.
