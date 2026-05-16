# Phase 4: Consolidate and Present

Loaded by `SKILL.md` after Phase 3 returns agent results. Consolidate, deduplicate, sort by severity, and present the overview table.

After ALL agents return:

1. **Merge** all findings into a single list
2. **Deduplicate** — if multiple agents flag the same issue (same file + same concern), keep one entry and note which agents agreed
3. **Enrich** — for each finding, add:
   - Which validation phase it belongs to (Spec Compliance, Coding Standards, Security, Test Coverage, etc.)
   - Cross-references to the exact rule/spec it violates
4. **Sort** by severity: CRITICAL > HIGH > MEDIUM > LOW
5. **Assign** sequential IDs (F1, F2, F3...)

### Severity Classification

| Severity | Criteria | Examples |
|----------|----------|---------|
| **CRITICAL** | Spec violation, security vulnerability, data loss risk, auth bypass | Missing acceptance criterion, injection vulnerability, hardcoded secret, broken business rule |
| **HIGH** | Missing test from spec, coding standards violation, broken accessibility, missing validation | Test ID not implemented, standards violation, no error handling, missing ARIA labels |
| **MEDIUM** | Code quality concern, pattern inconsistency, maintainability issue, missing edge case test | Duplication between files, inconsistent naming, missing boundary test, no loading state |
| **LOW** | Polish, minor style issue, optional improvement | Redundant style rule, verbose comment, slightly suboptimal approach |

---

### Phase 5: Present Overview Table

Show the user the full picture before diving into individual findings:

```markdown
### Post-Task Validation: T-XXX — X findings across Y agents

| # | Severity | Category | File | Summary | Agents |
|---|----------|----------|------|---------|--------|
| F1 | CRITICAL | Security | auth.go | ... | Security |
| F2 | HIGH | Spec Compliance | page.tsx | ... | Spec, Frontend |
| F3 | MEDIUM | Code Quality | layout.tsx | ... | Code, Cross-file |

### Agent Verdicts
| Agent | Verdict | Issues |
|-------|---------|--------|
| Code Quality | PASS/FAIL | 0C 2H 3M 1L |
| Business Logic | PASS/FAIL | ... |
| Security | PASS/FAIL | ... |
| QA Analyst | PASS/FAIL | ... |
| Frontend/Backend | PASS/FAIL | ... |
| Cross-File | PASS/FAIL | ... |
| Spec Compliance | PASS/FAIL | ... |

Spec compliance: X/Y acceptance criteria verified
Test coverage: X/Y test IDs implemented
Security verdict: PASS / FAIL
```

---
