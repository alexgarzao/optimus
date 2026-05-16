# Phase 7 (Convergence Loop): Optional Multi-Round Validation

Loaded by `SKILL.md` after Phase 6 commits. This was the original "Phase 6:
Convergence Loop (Optional — Gated)".

## Step 6.1: Convergence Loop

Execute the opt-in convergence loop — see AGENTS.md "Common Patterns > Protocol: Convergence Loop (Full Roster Model — Opt-In, Gated)".

**Behavioral contract for THIS phase:**
- Round 1 already ran in Phase 3 Step 2.4. THIS phase only handles rounds 2 through 5.
- Present the **entry gate** before round 2 (`Run round 2` / `Skip convergence loop`).
- Present the **per-round gate** before rounds 3, 4, 5 (`Continue` / `Stop here`).
- If a dispatched round produces ZERO new findings, declare convergence and exit
  silently — DO NOT ask the user whether to run another round.
- Record the final loop status (`CONVERGED` / `USER_STOPPED` / `SKIPPED` /
  `HARD_LIMIT` / `DISPATCH_FAILED_ABORTED`) for the Final Summary (Validation Report).

**Stage-specific scope for convergence rounds 2+:**
Dispatch the **same 4 droids** from Phase 3 Step 2.4 (business-logic-reviewer, security-reviewer,
qa-analyst, code-reviewer). Each agent receives the SAME compact context as round 1: the
Doc Brief (`.optimus/sessions/T-XXX/doc-brief.md`) and the round-1 findings ledger. Do NOT
instruct agents to "re-read fresh from disk" — that defeats the brief's caching purpose.
Agents may consult full pre-dev docs only if a finding requires verbatim reference. The
orchestrator handles dedup using strict matching (same file + same line range ±5 + same
category).

Include analysis instructions: cross-reference (Step 2.1), test gaps (Step 2.2),
observability (Step 2.3), DoD, ambiguities. Include the same items from the Phase 3 Step 2.4 prompt
(both the Verification scope block and the Cross-cutting analysis 5 items).

**Failure handling:** If a fresh sub-agent dispatch fails (Task tool error, ring droid
unavailable), do NOT count as zero findings. Ask the user via `AskUser` whether to
retry the round or stop (status `DISPATCH_FAILED_ABORTED` if user stops).

When the loop exits (any status), proceed to Phase 8 (Re-run Guard).
