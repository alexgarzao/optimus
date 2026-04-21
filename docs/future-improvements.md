# Future Improvements

Tracked improvements that are not yet prioritized for implementation.

---

## I1: Optimize Convergence Loop Token Cost

**Status:** Open
**Affects:** plan, check, pr-check, coderabbit-review
**Priority:** Medium

### Problem

Each round of the convergence loop dispatches a fresh sub-agent via `Task` that reads
ALL changed files from scratch and dispatches its own review agents. With round 2
mandatory and up to 5 rounds possible, the token cost is multiplicative.

Example for a PR with 20 files (~300 lines each) and 8 review agents:
- Round 1: orchestrator reads 20 files + dispatches 8 agents (each receives all 20 files)
- Round 2 (mandatory): fresh sub-agent reads 20 files again + dispatches its own agents
- Rounds 3-5: same, if new findings exist

Estimated cost per round: ~6,000-15,000 lines of code copied into agent prompts, times
8 agents. A full 5-round cycle could consume 5x the tokens of a single-pass review.

### Investigation Steps

1. **Measure real cost:** instrument a few real review sessions to measure tokens consumed
   per round and per agent. Compare single-pass vs full convergence cycle.
2. **Evaluate benefit:** track how many genuinely new findings are caught in rounds 2+
   vs round 1. If round 2 rarely finds new issues, the mandatory requirement may be
   too aggressive for some skills.
3. **Explore optimizations:**
   - **Delta-only rounds:** rounds 2+ receive only files modified by fixes (not all
     changed files). The fresh sub-agent still analyzes independently but with a
     smaller scope.
   - **Selective agent dispatch:** rounds 2+ dispatch only agents relevant to the
     domains where fixes were applied (e.g., if only security fixes were made, only
     dispatch security + consequences reviewers).
   - **Adaptive round 2:** make round 2 mandatory only when fixes were applied in
     round 1. If the user skipped all findings, round 2 is unlikely to find new issues.
   - **Scope-aware limits:** skills reviewing large scopes (deep-review on full codebase)
     could have round 2 as optional (ask user) instead of mandatory.
4. **Compare quality:** run the same PR through single-pass and convergence, compare
   finding quality and false convergence rate.

### Decision Criteria

Implement optimizations if:
- Round 2 finds genuinely new findings in < 20% of sessions
- Token cost of convergence is > 3x the cost of single-pass
- An optimization (delta-only, selective dispatch) reduces cost by > 50% without
  increasing false convergence rate

---

## I5: Evaluate Convergence Loop for deep-review

**Status:** Closed (implemented)
**Affects:** deep-review
**Priority:** N/A

**Resolution:** deep-review now includes a mandatory convergence loop (Phase 7) using
the fresh sub-agent model, same as cycle review skills. The loop uses round 2 mandatory
with up to 5 rounds total. Closed as implemented.
