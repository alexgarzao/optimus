# Phase 5: Verify, Converge, and Push

Loaded by `SKILL.md` after fixes are applied. Coverage verification, optional convergence loop (rounds 2-5), integration tests, push commits to trigger Codacy/DeepSource reanalysis.

### Phase 9: Coverage Verification and Test Gap Analysis

**IMPORTANT:** This phase runs ONLY ONCE, after ALL fixes from Phase 8 have been applied.

### Step 9.1: Coverage Measurement (Unit Tests)

Measure coverage — see AGENTS.md Protocol: Coverage Measurement.

**NOTE:** Integration test coverage is measured in Phase 11 (before push), not here.

### Step 9.2: Test Gap Analysis

Dispatch a test gap analyzer — see AGENTS.md Protocol: Test Gap Analyzer Dispatch. Use `ring-default-ring-test-reviewer` or `ring-dev-team-qa-analyst`.

HIGH priority gaps are presented as findings for user decision.

---

### Phase 10: Convergence Loop (Optional — Gated)

Execute the opt-in convergence loop — see AGENTS.md "Common Patterns > Protocol: Convergence Loop (Full Roster Model — Opt-In, Gated)".

**Behavioral contract for THIS phase:**
- Round 1 already ran in Phase 3. THIS phase only handles rounds 2 through 5.
- Present the **entry gate** before round 2 (`Run round 2` / `Skip convergence loop`).
- Present the **per-round gate** before rounds 3, 4, 5 (`Continue` / `Stop here`).
- If a dispatched round produces ZERO new findings, declare convergence and exit
  silently — DO NOT ask the user whether to run another round.
- Record the final loop status (`CONVERGED` / `USER_STOPPED` / `SKIPPED` /
  `HARD_LIMIT` / `DISPATCH_FAILED_ABORTED`) for the Final Summary in Phase 14.

**Stage-specific scope for convergence rounds 2+:**
Dispatch the **same agent roster** from Phase 3 (the roster confirmed in Step 3.3). Each agent
receives file paths, PR context (description, linked issues, base branch), and project
rules (re-read fresh from disk). Do NOT include the findings ledger in agent prompts —
the orchestrator handles dedup using strict matching (same file + same line range ±5 +
same category).

Include existing PR comments from all sources (reuse data from Phase 1 — do NOT re-fetch
Codacy/DeepSource comments, they only update after push). Include the same items from the
Step 3.3 prompt (both the Verification scope block and the Cross-cutting analysis 5 items).

**Failure handling:** If a fresh sub-agent dispatch fails (Task tool error, ring droid
unavailable), do NOT count as zero findings. Ask the user via `AskUser` whether to
retry the round or stop (status `DISPATCH_FAILED_ABORTED` if user stops).

When the loop exits (any status), proceed to Phase 11 (integration tests).

---

### Phase 11: Integration Tests (before push)

**Before pushing**, run integration tests. These are slow and expensive, so they
run ONCE here — not during the fix/convergence cycle. Run quietly —
see AGENTS.md Protocol: Quiet Command Execution:

```bash
_optimus_quiet_run "make-test-integration" make test-integration   # Optional target — SKIP if missing
```

| Test Type | Command | If target exists | If target missing |
|-----------|---------|-----------------|-------------------|
| Integration | `_optimus_quiet_run "make-test-integration" make test-integration` | **HARD BLOCK** if fails | SKIP |

**If integration tests fail:**
1. `_optimus_quiet_run` already printed the last 50 lines plus the log path —
   review them in place.
2. Ask via `AskUser`: "Integration tests are failing. What should I do?"
   - Fix the issue (dispatch ring droid)
   - Skip and push anyway (user will handle in CI)

---

### Phase 12: Push Commits

**HARD BLOCK:** Ask the user before pushing:

```
Fixes have been committed locally. Ready to push?
- Push now
- Skip (I'll push manually)
```

If approved:
```bash
git push
```

This triggers Codacy/DeepSource reanalysis automatically.

---
