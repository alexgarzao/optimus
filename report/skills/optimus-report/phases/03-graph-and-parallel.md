# Phase 3: Dependency Graph and Parallelization

Loaded after Phase 2. Compute the dependency graph and identify parallelization opportunities (tasks that could run concurrently).

Build a directed acyclic graph (DAG) from the Depends column.

For the ASCII art graph:
- Use `✓` for done tasks
- Use `⚙` for active tasks
- Use `◇` for ready-to-start tasks
- Use `⊘` for blocked tasks
- Use `✗` for cancelled tasks
- Use `─►` for dependency arrows
- Use `┬`, `├`, `└` for branching

Example:
```
T-001 ✓ ─┬─► T-002 ✓ ─┬─► T-004 ◇
          │             │
          ├─► T-003 ◇   ├─► T-005 ⚙
          │             │
          └─► T-006 ◇   └─► T-008 ◇

T-007 ⚙ ────► T-009 ⊘ ────► T-010 ⊘

Legend: ✓=Done ⚙=Active ◇=Ready ⊘=Blocked ✗=Cancelled
```

For trees with depth > 3 levels, simplify by showing only the critical path and noting "N more tasks omitted".

---

### Phase 7: Identify Parallelization Opportunities

### Currently Parallelizable
Tasks that are `Pendente` with all dependencies `DONE`. These can ALL start right now, in parallel.

### Next Wave
For each active task, identify which blocked tasks it would unlock when completed.
Group by: "After T-XXX completes, these unlock: ..."

---
