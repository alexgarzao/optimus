# Phase 2: Triage

Loaded after Phase 1. Categorize findings by severity, deduplicate, present overview table.

### Step 2.1: Parse Findings

**Parse CodeRabbit review body — see AGENTS.md Protocol: Parse CodeRabbit Review Body.**

The shared protocol is the single source of truth for the deterministic
parsing algorithm consumed by both `coderabbit-review` and `pr-check`. It
covers: per-section parse (regular inline / duplicate / outside-diff),
per-finding fix-block extraction (`Minimal fix` / `Suggested refactor`), AI
prompt capture, severity mapping, count-parity HARD BLOCK, aggregate
cross-validation, and origin tagging.

The three origin tags surfaced by the protocol:

1. **Regular findings** — inline suggestions about code within the diff. `origin: inline`.
2. **Duplicate comments** — findings CodeRabbit already reported in previous reviews that remain unresolved. `origin: duplicate`.
3. **Outside diff range comments** — suggestions about code OUTSIDE the reviewed diff. `origin: outside-diff`.

Categorize ALL findings (regardless of origin) by severity:

| Severity | Criteria |
|----------|----------|
| **CRITICAL** | Security vulnerability, data loss risk, auth bypass, broken business rule |
| **HIGH** | Missing validation, broken error handling, incorrect logic, missing tests for critical paths |
| **MEDIUM** | Code quality concern, pattern inconsistency, maintainability issue, missing edge case coverage |
| **LOW** | Polish, style, formatting, minor improvements |

### Step 2.2: Present Overview Table

```markdown
### CodeRabbit Review — X findings

| # | Severity | Origin | File | Line | Summary |
|---|----------|--------|------|------|---------|
| 1 | CRITICAL | inline | auth.go | 42 | ... |
| 2 | HIGH | DUPLICATE | handler.go | 88 | (reported in previous review) ... |
| 3 | MEDIUM | OUTSIDE PR DIFF | config.go | 15 | (outside this PR's changes) ... |

### Summary by Severity
- CRITICAL: X
- HIGH: X
- MEDIUM: X
- LOW: X

### Summary by Origin
- Inline (within diff): X
- Duplicate (from previous reviews): X
- Outside PR diff: X
```

---
