# Phase 3 (Mark Task as Done): Update Status + Notify

Loaded by `SKILL.md` after all 4 gates in Phase 2 pass. All gates passed —
mark the task and emit notifications.

1. Update status to `DONE` (or `Cancelado` if user chose that in Gate 4) in state.json — see AGENTS.md Protocol: State Management.
2. Invoke notification hooks (event=`status-change`) — see AGENTS.md Protocol: Notification Hooks.
3. If DONE: invoke notification hooks (event=`task-done`).
   If Cancelado: invoke notification hooks (event=`task-cancelled`).
4. Proceed to Phase 4 (cleanup).
