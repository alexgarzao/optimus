# Future Improvements

Tracked improvements that are not yet prioritized for implementation.

---

## I6: Additional Test Coverage for optimus-tasks.md Relocation Feature

**Status:** Open
**Affects:** scripts/test_skill_consistency.py
**Priority:** Low

### Context

The optimus-tasks.md-to-tasksDir migration feature (commit ad0d8d7, hardened in subsequent
review) has integration tests in `TestMigrationAndScopeIntegration` covering:
scope detection (same-repo/separate-repo), non-git tasksDir rejection, dash-prefix
rejection, path traversal, migration detection. Additional scenarios are identified
as gaps:

1. **End-to-end migration flow** — given a real legacy .optimus/tasks.md, run the
   full migration bash and verify the final state (file location, git commits in
   correct repos, gitignore updated).
2. **Concurrent migration** — two shell processes running migration simultaneously
   on the same project (expected: one succeeds, the other aborts cleanly).
3. **Scale test** — optimus-tasks.md with 500+ rows; measure parsing time for `grep`/`awk`.
4. **Special characters in task titles** — pipes, emojis, unicode — verify table
   parsing does not break.
5. **Migration rollback on partial failure** — inject failures at steps 2-5; verify
   rollback code paths actually restore pre-migration state.

### Why Not Now

The current integration tests catch the most important regression risks (scope
detection, security boundaries). The remaining scenarios are rare in practice;
adding them requires simulating filesystem failures (harder to set up in CI).

---

## I1: Optimize Convergence Loop Token Cost

**Status:** Resolved (rounds 2+ are now opt-in — user controls cost via gates)
**Affects:** plan, review, build, pr-check, coderabbit-review, deep-review, deep-doc-review
**Priority:** Low

### Context

The convergence loop was changed from a **single-agent model** (1 generalist sub-agent
in rounds 2+) to a **full-roster model** (same 8-10 specialist agents dispatched in
parallel). This was done because the single-agent model caused **false convergence** —
the generalist lacked domain depth to find what specialists would, declaring "zero new
findings" not because the code was clean, but because it couldn't see the issues.

The full-roster model dispatches the same agent count in rounds 2+ as round 1, roughly
doubling the token cost per convergence round. This tradeoff was accepted: correctness
is more valuable than token savings.

A subsequent change (Convergence Loop opt-in / gated) made rounds 2+ entirely
**user-controlled**: an entry gate before round 2, per-round gates before rounds 3-5,
and silent exit on convergence detection. Users now decide round-by-round whether
the additional token cost is justified, addressing the cost concern at its source
without sacrificing correctness when the user opts in.

### Remaining Optimization Opportunities

The opt-in/gated model resolves items 3 (adaptive round 2) and 4 (scope-aware limits)
of the original list — both are now under explicit user control. The optimizations
below remain potential improvements that can further reduce cost WHEN the user opts
into a convergence round, WITHOUT reverting to the single-agent model:

1. **Delta-only rounds:** rounds 2+ receive only files modified by fixes (not all
   changed files). Each specialist still analyzes independently but with a smaller scope.
2. **Selective agent dispatch:** rounds 2+ dispatch only agents relevant to the domains
   where fixes were applied (e.g., if only security fixes were made, only dispatch
   security + consequences reviewers).
3. **Adaptive round 2:** [DONE — rounds 2+ are now opt-in regardless of fix application]
4. **Scope-aware limits:** [DONE — all skills now have rounds 2+ as opt-in via user gates]

### Decision Criteria (for items 1 & 2)

Implement remaining optimizations if:
- Token cost of full-roster convergence is > 3x the cost of single-pass
- An optimization (delta-only, selective dispatch) reduces cost by > 50% without
  increasing false convergence rate
- The optimization maintains the principle that each domain specialist reviews
  independently (never collapse back to a single generalist)

---

## I2: Weighted Version Progress by Task Estimate

**Status:** Open
**Affects:** report, quick-report
**Priority:** Low

### Context

After removing per-task Progresso checkboxes (PR #4), version progress is calculated
as a simple binary count: `Done / (Total - Cancelled)`. This means a version with
3 XL tasks DONE out of 10 S tasks pending shows 30% — even though the bulk of the
effort is already delivered.

### Idea

Weight each task's contribution to version progress by its Estimate column
(S=1, M=2, L=3, XL=5, or similar). Progress becomes:
`Sum(weight of DONE tasks) / Sum(weight of all non-cancelled tasks)`.

The Estimate column already exists in optimus-tasks.md and comes from Ring pre-dev, so
no extra data collection is needed.

### Analysis

**Arguments for:**
- Better reflects actual effort delivered, especially in versions with mixed-size tasks.
- Data already available — no user overhead.
- Simple to implement — a mapping table and a weighted sum.

**Arguments against:**
- Estimates are guesses. Weighting guesses with guesses adds false precision.
- Estimate is optional (can be `-`). Tasks without estimates need a fallback (default
  weight of 1? exclude from weighted calc?). Mixed presence makes the number unreliable.
- Free-text format (`S`, `M`, `L`, `XL`, `2h`, `1d`, `3d`) requires normalization.
  Non-standard values need heuristics or a strict allowlist.
- Harder to interpret at a glance. "50%" today means "5 of 10 tasks". "50% weighted"
  requires the user to remember the weighting scheme.
- The full task table in report already shows every task with its status and estimate —
  users who want effort-aware assessment can read it directly.

### Recommendation

**Do not implement.** The complexity-to-benefit ratio is unfavorable. Simple binary
counting is predictable, easy to understand, and does not depend on estimate quality.
Users needing finer granularity can inspect the task table directly.

If revisited in the future, consider:
1. Only activate weighted progress when ALL tasks have estimates (no `-` values).
2. Restrict Estimate to a fixed enum (`S`, `M`, `L`, `XL`) to avoid normalization issues.
3. Show both values: `50% (5/10 tasks) | 72% (weighted by estimate)` — let the user
   choose which to trust.

---

## I3: Translate All Portuguese to English

**Status:** Open
**Affects:** AGENTS.md, all SKILL.md files, README.md
**Priority:** Medium

### Problem

Status values (Pendente, Validando Spec, Em Andamento, Validando Impl,
Cancelado, Concluída), version statuses (Ativa, Próxima, Planejada, Backlog), priority
values (Alta, Media, Baixa), column headers (Tipo, Depends), and various labels are in
Portuguese. This creates a barrier for non-Portuguese-speaking users and contributors.

### Scope

1. Status values in AGENTS.md and all SKILL.md files
2. Version status values
3. Priority values
4. Column headers and labels
5. User-facing messages and AskUser prompts
6. state.json values (requires migration path for existing users)

### Considerations

- Requires a migration path for state.json (existing status values)
- optimus-tasks.md format marker may need versioning (v1 → v2)
- All protocol references to status names must be updated atomically
- Consider keeping Portuguese as an alias during transition period

---

## I5: Remove Revisando PR Migration Code

**Status:** Open (waiting for all projects to migrate)
**Affects:** AGENTS.md Protocol: State Management
**Priority:** Low

### Context

The `Revisando PR` status was removed from the pipeline. A one-time migration in
Protocol: State Management rewrites `Revisando PR` → `Validando Impl` on first read.

### When to Remove

Safe to remove when all projects using Optimus have run at least one stage agent
with this version (migration runs automatically on first state.json read).

### Action

Remove the "One-time migration" block from Protocol: State Management in AGENTS.md.


