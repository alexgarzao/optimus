# Phase 5: Velocity and Stage Stats

Loaded after Phase 4. Velocity history metrics (completed-in-last-N-days), stage execution stats (plan/build/review/done run counters from stats.json).

After the dashboard, compute velocity metrics from `state.json` timestamps. These provide
trend data that a static snapshot (Phase 8) cannot show.

**NOTE:** Status lives in `.optimus/state.json` (gitignored), not in git commits.
Velocity is derived from the `updated_at` timestamps of tasks with status `DONE`.

### Step 9.1: Compute Task Completion History

Read `.optimus/state.json` and extract all tasks with status `DONE`:

```bash
# Resolve main worktree so .optimus/* paths are not isolated to a linked worktree.
# All .optimus/* state lives in the main worktree; linked worktrees do not propagate it.
MAIN_WORKTREE="$(git worktree list --porcelain 2>/dev/null | awk '/^worktree / {print $2; exit}')"
if [ -z "$MAIN_WORKTREE" ]; then
  echo "ERROR: Cannot determine main worktree — not in a git repository." >&2
  exit 1
fi

STATE_FILE="${MAIN_WORKTREE}/.optimus/state.json"
if [ -f "$STATE_FILE" ] && jq empty "$STATE_FILE" 2>/dev/null; then
  jq -r 'to_entries[] | select(.value.status == "DONE") | "\(.key) \(.value.updated_at)"' "$STATE_FILE"
fi
```

For each completed task, extract: task ID and completion date (from `updated_at`).
Group completions by week (last 4 weeks) for the velocity chart.

**If state.json is missing or has no DONE tasks**, show:
```
Velocity: No completed tasks found in state.json. Complete a task to start tracking.
```

### Step 9.2: Present Velocity Dashboard

```
┌─────────────────────────────────────────────────┐
│ VELOCITY (last 4 weeks)                          │
├─────────────────────────────────────────────────┤
│ Tasks completed:                                 │
│   Week -4: ██░░░░░░░░ 2                         │
│   Week -3: ████░░░░░░ 4                         │
│   Week -2: ███░░░░░░░ 3                         │
│   Week -1: █████░░░░░ 5                         │
│                                                  │
│ Average: 3.5 tasks/week                          │
│ Trend: ↑ accelerating                            │
│                                                  │
│ At current pace:                                 │
│   Remaining tasks (active version): N            │
│   Estimated completion: ~X weeks                 │
└─────────────────────────────────────────────────┘
```

### Step 9.3: Average Time Per Stage

If enough data exists (3+ completed tasks with `updated_at` timestamps in state.json),
compute approximate stage durations by comparing `updated_at` values of tasks that
progressed through multiple stages. If `stats.json` has `last_plan` and `last_review`
timestamps, use those for more precise stage duration estimates.

Present as:
```
Average time per stage (from N completed tasks):
  Validando Spec:  ~2h
  Em Andamento:    ~1.5 days
  Validando Impl:  ~3h
  Close:           ~15min
```

---

### Phase 9.4: Stage Execution Stats (Churn Metrics)

Read `.optimus/stats.json` to display stage execution counters. If the file does not
exist, skip this phase silently.

### Step 9.4.1: Load Stats

```bash
# MAIN_WORKTREE was resolved earlier (Step 9.1); reuse it. If somehow unset,
# resolve again to keep this block independent.
if [ -z "${MAIN_WORKTREE:-}" ]; then
  MAIN_WORKTREE="$(git worktree list --porcelain 2>/dev/null | awk '/^worktree / {print $2; exit}')"
  if [ -z "$MAIN_WORKTREE" ]; then
    echo "ERROR: Cannot determine main worktree — not in a git repository." >&2
    exit 1
  fi
fi

STATS_FILE="${MAIN_WORKTREE}/.optimus/stats.json"
if [ -f "$STATS_FILE" ]; then
  if jq empty "$STATS_FILE" 2>/dev/null; then
    cat "$STATS_FILE"
  else
    echo "WARNING: stats.json is corrupted. Skipping churn metrics."
  fi
fi
```

### Step 9.4.2: Present Churn Dashboard

Only show this section if stats.json exists AND has at least one task entry.

**Highlight tasks with above-average churn** — tasks where `plan_runs > avg_plan_runs`
or `review_runs > avg_review_runs` are flagged as high-churn.

```
┌─────────────────────────────────────────────────┐
│ STAGE EXECUTION STATS                            │
├─────────────────────────────────────────────────┤
│ Average plan runs:  1.5 per task                 │
│ Average review runs: 2.0 per task                │
│                                                  │
│ High-churn tasks:                                │
│   T-003: plan ×4, review ×3  ← spec issues?     │
│   T-007: plan ×1, review ×5  ← review cycles?   │
│                                                  │
│ All tasks:                                       │
│   T-001: plan ×1, review ×1                      │
│   T-002: plan ×2, review ×2                      │
│   T-003: plan ×4, review ×3  ⚠                  │
│   T-007: plan ×1, review ×5  ⚠                  │
└─────────────────────────────────────────────────┘
```

**If only 1-2 tasks exist**, skip the averages and high-churn section — just show the
per-task counts.

---
