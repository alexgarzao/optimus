---
name: optimus-deep-doc-review
description: >
  Deep review of project documentation. Finds errors, inconsistencies,
  gaps, missing data, and improvements. Presents findings in a compact table
  and resolves one by one with user approval. Does not make automatic changes.
trigger: >
  - When user requests project documentation review
  - Before starting implementation based on docs (validate doc quality)
  - After significant changes to reference docs (PRD, TRD, API design, etc.)
skip_when: >
  - Code review (use optimus-deep-review or optimus-cycle-impl-review-stage-3 instead)
  - Docs do not exist yet (create them first)
  - Reviewing a single simple file (do it directly without the skill)
prerequisite: >
  - Project has documentation to review
  - Docs are accessible in the repository
NOT_skip_when: >
  - "Docs were already reviewed" → Docs evolve and accumulate inconsistencies over time.
  - "There are only a few docs" → Even a few docs can have contradictions between them.
  - "Only one doc changed" → A change in one doc can create inconsistencies with others.
examples:
  - name: Review all project docs
    invocation: "Review the project docs"
    expected_flow: >
      1. Discover existing docs
      2. Read all docs
      3. Cross-reference information between docs
      4. Generate findings table
      5. Present one by one, apply approved corrections
      6. Final summary
  - name: Review specific docs
    invocation: "Review docs/pre-dev/api-design.md and docs/pre-dev/data-model.md"
    expected_flow: >
      1. Read the specified docs
      2. Cross-reference information between them
      3. Generate table and resolve findings
related:
  complementary:
    - optimus-cycle-spec-stage-1
    - optimus-cycle-impl-review-stage-3
  differentiation:
    - name: optimus-cycle-spec-stage-1
      difference: >
        optimus-cycle-spec-stage-1 validates a task spec against reference docs.
        optimus-deep-doc-review reviews the docs themselves against each other,
        independent of any task.
verification:
  manual:
    - All findings presented to user
    - Approved corrections applied correctly
    - Final summary presented
---

# Deep Doc Review

Deep review of project documentation. Finds errors, inconsistencies, gaps, missing data, and improvements.

---

## Phase 0: Discover and Load Docs

### Step 0.1: Identify Docs to Review

If the user specified files, use those. Otherwise, discover automatically:

1. Search for project reference docs: `docs/`, `docs/pre-dev/`, or equivalent
2. Include: PRD, TRD, API design, data model, task specs, coding standards, dependency map, README, CHANGELOG
3. Exclude: generated files, node_modules, build artifacts, binary files

Present the list of discovered docs to the user before proceeding. If there are many (>15), ask whether to review all or select a subset.

### Step 0.2: Read All Docs

Read the full content of each identified doc. Build a mental map of:
- Entities and fields defined in each doc
- Endpoints and API contracts
- Business rules
- Technical decisions
- Dependencies between docs

---

## Phase 0.5: Parallel Agent Dispatch

Dispatch specialist agents via `Task` tool to analyze the docs from different perspectives.
Each agent receives the full content of all docs being reviewed.

**Agent selection priority:**
1. `ring-tw-team-docs-reviewer` — documentation quality, structure, completeness
2. `ring-default-business-logic-reviewer` — business rules consistency across docs
3. `ring-default-code-reviewer` — technical accuracy, architectural consistency
4. `worker` with domain instructions — fallback (always available)

**Dispatch at least 2 agents in parallel:**

| # | Agent | Focus |
|---|-------|-------|
| 1 | **Documentation quality** | Structure, completeness, clarity, voice, tone |
| 2 | **Cross-doc consistency** | Contradictions between docs, missing references, entity/field mismatches |

**Agent prompt template:**
```
Goal: Documentation review — [your domain]

Context:
  - Docs to review: [full content of each doc with filename header]

Your job:
  Review the documentation for issues in your domain. Report issues ONLY — do NOT fix anything.

Required output format:
  For each issue found, provide:
  - Type: ERROR / INCONSISTENCY / GAP / MISSING / IMPROVEMENT
  - Severity: CRITICAL / HIGH / MEDIUM / LOW
  - File(s): affected doc(s)
  - Problem: what is wrong
  - Suggested fix: concrete correction
  If no issues: "PASS — no issues in [domain]"
```

Merge agent findings with the orchestrator's own analysis in Phase 1.

---

## Phase 1: Analysis and Cross-Referencing

### Issue Types

| Type | Description |
|------|-------------|
| ERROR | Factually incorrect information |
| INCONSISTENCY | Contradiction between two or more docs |
| GAP | Expected information that is absent |
| MISSING | Referenced data that does not exist in any doc |
| IMPROVEMENT | Opportunity for clarity, organization, or completeness |

### Severity

| Severity | Criteria |
|----------|----------|
| CRITICAL | Blocks implementation — developer cannot proceed without resolving |
| HIGH | Causes bugs or significant confusion during implementation |
| MEDIUM | Affects doc quality but does not block implementation |
| LOW | Cosmetic — formatting, typos, organization |

### What to Analyze

For each doc, verify:
1. **Internal consistency** — does the doc contradict itself?
2. **Cross-doc consistency** — does the doc contradict other docs?
3. **Completeness** — are expected sections missing?
4. **Valid references** — do referenced entities, fields, and endpoints exist in the corresponding docs?
5. **Clarity** — can a developer implement without needing to ask questions?
6. **Currency** — is the information outdated compared to the existing code?

---

## Phase 2: Present Overview

Present the full findings table for a bird's-eye view:

```markdown
## Deep Doc Review — X findings across Y docs

| # | Type | Severity | File(s) | Problem | Suggested Fix | Tradeoff | Recommendation |
|---|------|----------|---------|---------|---------------|----------|----------------|
| 1 | INCONSISTENCY | CRITICAL | api-design.md, data-model.md | Field X defined as VARCHAR(50) in data-model but string with no limit in API design | Align to VARCHAR(100) in both | Changing limit may affect validation | Fix both docs |
| 2 | GAP | HIGH | tasks.md | Task T-008 does not define Testing Strategy | Add section with unit + integration tests | Additional writing effort | Add before implementation |
| ... | ... | ... | ... | ... | ... | ... | ... |

### Summary by Severity
- CRITICAL: X
- HIGH: X
- MEDIUM: X
- LOW: X
```

---

## Phase 3: Interactive Resolution (one by one)

Present each finding individually, in severity order (CRITICAL first).

For EACH finding:

### 1. Show the Item

Display the number, type, severity, affected file(s), problem description, suggested fix, and tradeoff.

### 2. Ask the User

Use `AskUser` with contextual options:
- Fix as suggested
- Fix with adjustment (user specifies)
- Skip this item

**BLOCKING**: Do NOT advance to the next item until the user decides.

### 3. Apply (if approved)

If the user chose to fix:
1. Apply the correction immediately
2. Confirm it was applied
3. Only then advance to the next item

### Rules
- Never present more than one item at a time
- Never apply corrections without explicit approval
- Internally record each decision (fixed, skipped, adjusted)

---

## Phase 4: Final Summary

After processing all findings:

```markdown
## Deep Doc Review — Summary

### Fixed (X findings)
| # | Type | File(s) | Fix Applied |
|---|------|---------|-------------|
| 1 | INCONSISTENCY | api-design.md, data-model.md | Aligned to VARCHAR(100) |

### Skipped (X findings)
| # | Type | File(s) | Reason |
|---|------|---------|--------|
| 5 | IMPROVEMENT | trd.md | User: cosmetic, not a priority |

### Statistics
- Total findings: X
- Fixed: X
- Skipped: X
- Docs modified: [list]
```

**Do NOT commit automatically.** Present the summary and wait for the user to decide whether to commit.

---

## Rules

- Do NOT generate code — this skill is for documentation only
- Do NOT assume — if something is ambiguous, classify it as GAP or MISSING
- ALWAYS cross-reference information between docs — intra-doc findings are useful, but inter-doc findings are more valuable
- Prioritize: CRITICAL > HIGH > MEDIUM > LOW
- Reference exact locations (file, section, line when possible)
- Tradeoffs must be honest — do not minimize the cost of a correction
- If a doc references existing code, verify that the code matches the doc
