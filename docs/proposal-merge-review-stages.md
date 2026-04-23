# Proposal: Merge "Validando Impl" and "Revisando PR" into a single stage

## Status
Proposed

## Context

The current Optimus pipeline has 5 active stages:

```
Pendente → Validando Spec → Em Andamento → Validando Impl → [Revisando PR] → DONE
           (plan)            (build)        (check)          (pr-check)       (done)
```

- **Validando Impl (check):** Automated post-implementation validation — spec compliance,
  coding standards, test coverage, production readiness. Runs *before* a PR is opened.
- **Revisando PR (pr-check):** PR-based code review — CodeRabbit, Codacy, DeepSource,
  human reviewers. Runs *after* a PR is opened.

Both stages are review/validation activities that happen sequentially after implementation
is complete. The `pr-check` stage is already marked as optional in the current design
(`done` accepts both `Validando Impl` and `Revisando PR`).

## Proposal

Merge both stages into a single **"Em Revisao"** stage:

```
Pendente → Validando Spec → Em Andamento → Em Revisao → DONE
           (plan)            (build)        (review)     (done)
```

The merged `review` skill would:
1. First run automated validation (current `check` logic)
2. Then run PR review (current `pr-check` logic), if a PR exists
3. Both sub-phases happen within the same pipeline stage

## Tradeoffs

### What we gain

| Benefit | Detail |
|---------|--------|
| **Simpler mental model** | 3 active stages instead of 4. Easier to explain and track. |
| **Less state overhead** | Fewer transitions, fewer state.json updates, fewer hooks. |
| **Single concept** | "I'm done coding, now it's being reviewed" is one phase for the task owner. |
| **Reduced ceremony** | No need to decide whether to run check, pr-check, or both. |
| **Already optional** | pr-check is already optional — `done` accepts `Validando Impl`. Merging formalizes this. |

### What we lose

| Loss | Detail | Mitigation |
|------|--------|------------|
| **Granular visibility** | Can't distinguish "running automated checks" from "waiting for human reviewer" at the pipeline level. | The merged skill can log sub-phase progress internally. |
| **Independent metrics** | Can't measure cycle time for validation vs review separately. | Metrics can be collected within the skill without needing separate pipeline states. |
| **Explicit gate** | Lose the explicit "pass automated checks before opening PR" gate. | The merged skill enforces this internally — it runs check first, only proceeds to PR review if it passes. |

### When to keep them separate

For **larger teams** where different people are responsible for validation vs review,
or where PR review queues are a significant bottleneck worth measuring independently,
keeping separate stages provides better visibility. This proposal is optimized for
**small teams and AI-assisted workflows** where the same entity (developer or AI agent)
handles both phases.

## Impact Analysis

### Files requiring changes

| File | Change type |
|------|-------------|
| `AGENTS.md` | Pipeline definition, transition table, status mappings |
| `README.md` | Pipeline overview |
| `check/skills/optimus-check/SKILL.md` | Absorb pr-check logic, rename status to `Em Revisao` |
| `pr-check/skills/optimus-pr-check/SKILL.md` | Remove or redirect to merged skill |
| `done/skills/optimus-done/SKILL.md` | Accept `Em Revisao` instead of `Validando Impl`/`Revisando PR` |
| `build/skills/optimus-build/SKILL.md` | Update status validation list |
| `plan/skills/optimus-plan/SKILL.md` | Update status validation list |
| `tasks/skills/optimus-tasks/SKILL.md` | Update advance/demote tables, mid-pipeline warning |
| `batch/skills/optimus-batch/SKILL.md` | Update stage table (merge stages 3-4) |
| `quick-report/skills/optimus-quick-report/SKILL.md` | Update stage progress bar (4 stages instead of 5) |
| `report/skills/optimus-report/SKILL.md` | Update status listings and examples |
| `import/skills/optimus-import/SKILL.md` | Update status mapping table |
| `help/skills/optimus-help/SKILL.md` | Update pipeline diagram |
| `docs/future-improvements.md` | Update status list |

### New pipeline states

| Status | Stage | Skill |
|--------|-------|-------|
| `Pendente` | - | - |
| `Validando Spec` | 1/4 | plan |
| `Em Andamento` | 2/4 | build |
| `Em Revisao` | 3/4 | review |
| `DONE` | 4/4 | done |
| `Cancelado` | - | tasks (cancel) |

### New transition table

| Agent | Expects status | Changes to | Re-execution? |
|-------|---------------|------------|---------------|
| plan | `Pendente` or `Validando Spec` | `Validando Spec` | Yes |
| build | `Validando Spec` or `Em Andamento` | `Em Andamento` | Yes |
| review | `Em Andamento` or `Em Revisao` | `Em Revisao` | Yes |
| done | `Em Revisao` | `DONE` | No |

### Quick report stage progress (new)

| Status | Stage | Filled chars |
|--------|-------|-------------|
| `Validando Spec` | 1/4 | 1 |
| `Em Andamento` | 2/4 | 2 |
| `Em Revisao` | 3/4 | 3 |

### Backward compatibility

- **state.json:** Existing tasks with status `Validando Impl` or `Revisando PR` should
  be treated as `Em Revisao` during migration. A one-time migration script or manual
  update is needed for in-flight tasks.
- **pr-check skill:** Can be kept as an alias that redirects to the merged `review` skill,
  or removed entirely with a deprecation notice.

## Decision

Pending team review.
