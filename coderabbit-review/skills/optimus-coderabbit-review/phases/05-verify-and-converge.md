# Phase 5: Verify, Converge, and Push

Loaded after Phase 4. Coverage verification, optional convergence loop (rounds 2-5), integration tests, optional push to remote.

After all findings have been processed through the TDD cycle:

### Step 5.1: Lint + Coverage Measurement

**Run lint ONCE** after all fixes are applied, using the resolved command from
Step 1.3, wrapped in `_optimus_quiet_run` — see AGENTS.md Protocol: Quiet
Command Execution:
```bash
_optimus_quiet_run "make-lint" make lint
```
If lint fails, fix formatting issues and re-run.

**Measure unit test coverage:**

Measure coverage — see AGENTS.md Protocol: Coverage Measurement.

If coverage is below threshold, flag as findings.

**NOTE:** Integration tests run only before push or when user invokes directly.

### Step 5.2: Test Scenario Gap Analysis

Dispatch a test gap analyzer — see AGENTS.md Protocol: Test Gap Analyzer Dispatch.

**HIGH priority gaps** are presented as findings for user decision (fix now or defer).

---

### Phase 6: Convergence Loop (Optional — Gated)

Execute the opt-in convergence loop — see AGENTS.md "Common Patterns > Protocol: Convergence Loop (Full Roster Model — Opt-In, Gated)".

**Behavioral contract for THIS phase:**
- "Round 1" maps to the aggregate of Phase 4 Step 4.1 per-fix Secondary Agent Validation
  dispatches (this skill is fix-driven; the agent roster is dispatched per fix, not as
  a single primary review pass). THIS phase (rounds 2 through 5) re-dispatches the same
  roster ONCE over the full diff to catch issues missed during the per-fix passes.
- Present the **entry gate** before round 2 (`Run round 2` / `Skip convergence loop`).
- Present the **per-round gate** before rounds 3, 4, 5 (`Continue` / `Stop here`).
- If a dispatched round produces ZERO new findings, declare convergence and exit
  silently — DO NOT ask the user whether to run another round.
- Record the final loop status (`CONVERGED` / `USER_STOPPED` / `SKIPPED` /
  `HARD_LIMIT` / `DISPATCH_FAILED_ABORTED`) for the Final Summary.

**Stage-specific scope for convergence rounds 2+:**
Dispatch the **same agent roster** used in Phase 4 Step 4.1 (all 7 review droids). Each
agent receives file paths and project rules (re-read fresh from disk). Do NOT include the
findings ledger in agent prompts — the orchestrator handles dedup using strict matching
(same file + same line range ±5 + same category).

Additionally, one agent in the roster should re-run CodeRabbit CLI
(`coderabbit review --prompt-only --base <base-branch> --plain`) to get fresh static
analysis. The other agents review the code from their specialist domains.

**Failure handling:** If a dispatched agent slot fails (Task tool error, ring droid
unavailable), do NOT count as zero findings. Ask the user via `AskUser` whether to
retry the round or stop (status `DISPATCH_FAILED_ABORTED` if user stops).

When the loop exits (any status), proceed to Phase 7 (integration tests).

---

### Phase 7: Integration Tests (before push)

**After the convergence loop exits**, run integration tests. These are slow and
expensive, so they run ONCE here — not during the fix/convergence cycle. Run
quietly — see AGENTS.md Protocol: Quiet Command Execution:

```bash
_optimus_quiet_run "make-test-integration" make test-integration   # Optional target — SKIP if missing
```

| Test Type | Command | If target exists | If missing |
|-----------|---------|-----------------|------------|
| Integration | `_optimus_quiet_run "make-test-integration" make test-integration` | **HARD BLOCK** if fails | SKIP |

**If integration tests fail:**
1. `_optimus_quiet_run` already printed the last 50 lines plus the log path —
   review them in place.
2. Ask via `AskUser`: "Integration tests are failing. What should I do?"
   - Fix the issue (dispatch ring droid)
   - Skip and proceed to summary (user will handle later)

**If all pass (or targets don't exist):** proceed to Phase 8 (Push) or Phase 9 (Final Summary).

---

### Phase 8: Push Commits (optional)

Offer to push commits — see AGENTS.md Protocol: Push Commits.

---
