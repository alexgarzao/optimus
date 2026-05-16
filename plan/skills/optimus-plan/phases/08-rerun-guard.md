# Phase 8 (Re-run Guard): Evaluate Re-run or Advance

Loaded by `SKILL.md` after Phase 7 convergence exits. This was the original
"Phase 7: Re-run Guard".

## Step 7.1: Evaluate Re-run or Advance

Execute re-run guard — see AGENTS.md Protocol: Re-run Guard.

- If the user chooses **Re-run with clean context**: go back to Phase 2 Step 1.1 (Discover Project
  Structure). Skip all prior setup steps (GitHub CLI check, optimus-tasks.md validation, task
  identification, session state, status validation, workspace creation, divergence check).
  Increment stage stats before re-starting analysis. Apply the **Re-run reset semantics**: reset `convergence_status` to `null`; reset `phase` to the first re-executed phase; overwrite `started_at`; preserve `task_id`, `task_branch`, `created_at`. See AGENTS.md Protocol: Re-run Guard.
- If the user chooses **Advance** (or 0 findings): proceed to Phase 9 (Push).
