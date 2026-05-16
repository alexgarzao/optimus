# Phase 4: Present Dashboard

Loaded after Phase 3. Render the full dashboard: version progress, active tasks, ready/blocked queues, dependency graph, parallelization opportunities, churn metrics.

Present the full dashboard using the format below. Use the `<json-render>` format when available for richer display, otherwise use the ASCII art format.

### ASCII Art Format

```
╔══════════════════════════════════════════════════════╗
║                  PROJECT STATUS                      ║
╠══════════════════════════════════════════════════════╣
║  Total: NN  │  Done: NN  │  Active: NN  │  Pending: NN  │  Cancelled: NN  ║
╚══════════════════════════════════════════════════════╝

Progress: ████████░░░░░░░░░░░░ XX% (done / (total - cancelled))

┌──────────────────────────────────────────────────────────┐
│ ACTIVE TASKS                                              │
├────────┬──────────────────────┬──────────┬────────────────┤
│ ID     │ Title                │ Version  │ Status         │
├────────┼──────────────────────┼──────────┼────────────────┤
│ T-005  │ User registration    │ MVP      │ Em Andamento   │
│ T-007  │ Login page           │ MVP      │ Validando Impl │
└────────┴──────────────────────┴──────────┴────────────────┘

┌──────────────────────────────────────────────────────────┐
│ READY TO START (dependencies satisfied)                   │
├────────┬──────────────────────┬──────────┬────────────────┤
│ ID     │ Title                │ Version  │ Priority       │
├────────┼──────────────────────┼──────────┼────────────────┤
│ T-006  │ Password reset       │ v2       │ Alta           │
│ T-008  │ E2E auth tests       │ MVP      │ Media          │
└────────┴──────────────────────┴──────────┴────────────────┘

┌──────────────────────────────────────────────────────────┐
│ BLOCKED (waiting for dependencies)                        │
├────────┬──────────────────────┬──────────┬────────────────┤
│ ID     │ Title                │ Version  │ Blocked by     │
├────────┼──────────────────────┼──────────┼────────────────┤
│ T-009  │ Admin dashboard      │ MVP      │ T-007          │
│ T-010  │ Role management      │ v2       │ T-009          │
└────────┴──────────────────────┴──────────┴────────────────┘

┌─────────────────────────────────────────────────┐
│ DEPENDENCY GRAPH                                 │
├─────────────────────────────────────────────────┤
│                                                  │
│  [insert computed graph here]                    │
│                                                  │
│  Legend: ✓=Done ⚙=Active ◇=Ready                 │
│          ⊘=Blocked ✗=Cancelled                   │
└─────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────┐
│ PARALLELIZATION OPPORTUNITIES                    │
├─────────────────────────────────────────────────┤
│ Can start RIGHT NOW (in parallel):               │
│                                                  │
│  ┌─ T-006: Password reset          [Alta]        │
│  ├─ T-008: E2E auth tests          [Media]       │
│  └─ T-003: Login page              [Alta]        │
│                                                  │
│ After T-007 completes, also unlock:              │
│  └─ T-009: Admin dashboard         [Alta]        │
│                                                  │
│ After T-009 completes, also unlock:              │
│  └─ T-010: Role management         [Media]       │
└─────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────┐
│ COMPLETED                                        │
├────────┬──────────────────────────────────────────┤
│ T-001  │ Setup auth module                        │
│ T-002  │ User registration API                    │
└────────┴──────────────────────────────────────────┘

┌─────────────────────────────────────────────────┐
│ CANCELLED                                        │
├────────┬──────────────────────────────────────────┤
│ T-011  │ Legacy migration script                  │
└────────┴──────────────────────────────────────────┘
```

### Estimate Summary

If any tasks have Estimate values (non-`-`), show an estimate breakdown by status:

```
┌─────────────────────────────────────────────────┐
│ ESTIMATE BREAKDOWN                               │
├──────────┬────────────────────────────────────────┤
│ Status   │ Estimates                              │
├──────────┼────────────────────────────────────────┤
│ Active   │ 2S, 1M, 1L                            │
│ Ready    │ 1M, 2L                                 │
│ Blocked  │ 1S, 1XL                                │
│ Done     │ 3S, 2M, 1L                            │
└──────────┴────────────────────────────────────────┘
```

If no tasks have Estimate values, skip this section.

### json-render Format

Also generate a `<json-render>` dashboard with these components:
- **Heading**: "Project Status"
- **ProgressBar**: overall completion (done / (total - cancelled))
- **Metric**: Total, Done, Active, Pending, Cancelled counts
- **Table**: Active tasks (columns: ID, Title, Version, Status)
- **Table**: Ready to start (columns: ID, Title, Version, Priority)
- **Table**: Blocked (columns: ID, Title, Version, Blocked by)
- **List**: Parallelization opportunities
- **StatusLine**: one per active task (success=done, info=active, warning=blocked, error=failed)

Present BOTH formats: the ASCII art first (always readable), then the json-render (for rich terminal).

---
