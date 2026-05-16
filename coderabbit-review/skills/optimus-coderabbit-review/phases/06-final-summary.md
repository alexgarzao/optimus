# Phase 6: Final Summary

Loaded after Phase 5. Present the structured summary of fixes applied / findings skipped / convergence status / next-step recommendation.

After all phases complete:

```markdown
### CodeRabbit Review — Summary

### Convergence
- Rounds dispatched (round 1 + convergence rounds): X
- Status: CONVERGED | USER_STOPPED | SKIPPED | HARD_LIMIT | DISPATCH_FAILED_ABORTED

### Fixed (X findings)
| # | Severity | File | Fix Applied | Tests Added | Round |
|---|----------|------|-------------|-------------|-------|

### Ignored (X findings)
| # | Severity | File | Reason | Round |
|---|----------|------|--------|-------|

### Pending (X findings)
| # | Severity | File | Blocker | Round |
|---|----------|------|---------|-------|

### Test Coverage
- Unit tests: XX.X% (threshold: 85%) — PASS / FAIL
- Integration tests: XX.X% (threshold: 70%) — PASS / FAIL / SKIP
- Untested functions: X (Y business logic, Z infrastructure)

### Test Results
- Unit tests: PASS (X tests)
- Lint: PASS
- Integration tests: not run (run before push or invoke directly)
- Skipped tests: X (with justification)

### Statistics
- Total findings: X (across Y rounds)
- Fixed: X
- Ignored: X
- Pending: X
- Files modified: [list]
```

**Do NOT commit automatically.** Present the summary and ask the user if they want to commit.

---
