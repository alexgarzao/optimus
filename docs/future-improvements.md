# Future Improvements

Tracked improvements that are not yet prioritized for implementation.

---

## I1: Optimize Convergence Loop Token Cost

**Status:** Open
**Affects:** cycle-spec-stage-1, cycle-impl-review-stage-3, cycle-pr-review-stage-4, coderabbit-review
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

**Status:** Open
**Affects:** deep-review
**Priority:** Low

### Problem

The `deep-review` skill currently uses a single-pass model (no convergence loop), while
cycle review skills (stages 1, 3, 4, coderabbit-review) all have mandatory convergence
loops with fresh sub-agents.

The question is whether `deep-review` would benefit from a convergence loop. The tradeoff
is different from cycle skills because `deep-review` typically reviews larger scopes
(entire codebase or large directories, not just a task diff), making each round significantly
more expensive in tokens.

### Investigation Steps

1. **Measure false convergence rate:** run `deep-review` on several real codebases and
   track whether the single-pass misses issues that a second pass would catch.
2. **Estimate cost:** for a typical `deep-review` scope (20-50 files), calculate the
   token cost of adding a mandatory round 2 with fresh sub-agent.
3. **Compare with cycle skills:** in cycle review skills, what percentage of genuinely
   new findings come from round 2+? If the rate is low even for smaller scopes, it
   would be even lower for `deep-review`'s broader scope with more agents.
4. **Consider optional mode:** if convergence is added, it should likely be optional
   (ask the user) rather than mandatory, given the larger scope and cost.

### Decision Criteria

Add convergence loop to `deep-review` if:
- Single-pass misses genuinely important findings in > 30% of sessions
- The cost of round 2 is acceptable relative to the scope size
- An optional (user-prompted) convergence mode can be implemented without adding
  complexity to the base flow
