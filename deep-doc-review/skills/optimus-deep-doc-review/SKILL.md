---
name: optimus-deep-doc-review
description: "Deep review of project documentation. Finds errors, inconsistencies, gaps, missing data, and improvements. Presents findings in a compact table and resolves one by one with user approval. Does not make automatic changes."
trigger: >
  - When user requests project documentation review
  - Before starting implementation based on docs (validate doc quality)
  - After significant changes to reference docs (PRD, TRD, API design, etc.)
skip_when: >
  - Code review (use optimus-deep-review or optimus-check instead)
  - Docs do not exist yet (create them first)
  - Reviewing a single simple file (do it directly without the skill)
prerequisite: >
  - Project has documentation to review
  - Docs are accessible in the repository
NOT_skip_when: >
  - "Docs were already reviewed" -- Docs evolve and accumulate inconsistencies over time.
  - "There are only a few docs" -- Even a few docs can have contradictions between them.
  - "Only one doc changed" -- A change in one doc can create inconsistencies with others.
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
    - optimus-plan
    - optimus-check
  differentiation:
    - name: optimus-plan
      difference: >
        optimus-plan validates a task spec against reference docs.
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

## Phase 1: Discover and Load Docs

### Step 1.1: Identify Docs to Review

If the user specified files, use those. Otherwise, discover automatically:

1. Search for project reference docs: `docs/`, `docs/pre-dev/`, or equivalent
2. Include: PRD, TRD, API design, data model, task specs, coding standards, dependency map, README, CHANGELOG
3. Exclude: generated files, node_modules, build artifacts, binary files

Present the list of discovered docs to the user before proceeding. If there are many (>15), ask whether to review all or select a subset.

### Step 1.2: Read All Docs

Read the full content of each identified doc. Build a mental map of:
- Entities and fields defined in each doc
- Endpoints and API contracts
- Business rules
- Technical decisions
- Dependencies between docs

---

## Phase 2: Parallel Agent Dispatch

Dispatch specialist agents via `Task` tool to analyze the docs from different perspectives.
Each agent receives file paths and can navigate the project autonomously.

**Ring droids are REQUIRED** — verify ring droids — see AGENTS.md Protocol: Ring Droid Requirement Check. If the core review droids are not installed, **STOP** and inform the user:
```
Required ring droids are not installed. Install them before running this skill:
  - ring-tw-team-docs-reviewer
  - ring-default-business-logic-reviewer
  - ring-default-code-reviewer
```

**Droids to dispatch:**
1. `ring-tw-team-docs-reviewer` — documentation quality, structure, completeness, voice, tone, accuracy
2. `ring-default-business-logic-reviewer` — business rules consistency across docs, spec traceability, data integrity definitions, edge case coverage
3. `ring-default-code-reviewer` — technical accuracy, architectural consistency, implementability, feasibility of described patterns

**Dispatch at least 2 agents in parallel:**

| # | Agent | Focus |
|---|-------|-------|
| 1 | **Documentation quality** | Structure, completeness, clarity, voice, tone |
| 2 | **Cross-doc consistency** | Contradictions between docs, missing references, entity/field mismatches |

**Agent prompt template:**
```
Goal: Documentation review — [your domain]

Context:
  - Project root: <absolute path to project worktree>
  - Docs to review: [list of doc file paths] (READ each file)
  - Reference docs dir: <TASKS_DIR>/ (explore for related docs)
  - Project rules: AGENTS.md, PROJECT_RULES.md, docs/PROJECT_RULES.md (READ all that exist)
  - Codebase: available for cross-referencing docs against implementation

IMPORTANT: You have access to Read, Grep, and Glob tools. USE THEM to:
  - Read docs at the paths above
  - Cross-reference documentation claims against actual code implementation
  - Verify that referenced files, functions, endpoints, and configs actually exist
  - Find inconsistencies between docs and codebase
  - Discover related documentation not explicitly listed

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

Cross-cutting analysis (MANDATORY for all agents):
  1. Do the docs accurately reflect the current state of the codebase? (search code to verify)
  2. What's MISSING from the docs that a developer would need to implement or maintain this?
  3. Are acceptance criteria testable and measurable? (not vague like "works correctly")
  4. Would a new developer be able to implement this without asking questions?
  5. Are error scenarios, edge cases, and rollback strategies documented?
```

Merge agent findings with the orchestrator's own analysis in Phase 3.

---

## Phase 3: Analysis and Cross-Referencing

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

## Phase 4: Present Overview

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

## Phase 5: Interactive Resolution (one by one)

**=== MANDATORY — Progress Tracking (NEVER SKIP) ===**

**BEFORE presenting the first finding, you MUST:**
1. Count the TOTAL number of findings (N)
2. Display the total prominently: `"### Total findings to review: N"`

**For EVERY finding presented, you MUST:**
1. Include `"Finding X of N"` in the header
2. X starts at 1 and increments sequentially
3. N is the total announced above and NEVER changes mid-review

Present each finding individually, in severity order (CRITICAL first).

For EACH finding:

### 1. Deep Research Before Presenting (MANDATORY)

**BEFORE presenting any finding to the user, research it silently.** Do not show the
research process — present only the conclusions.

**Research checklist:**
1. **Verify accuracy against codebase:** If the doc references code, check that the code matches
2. **Check precedent in other docs:** Is this pattern used consistently elsewhere?
3. **Assess implementation impact:** Would this error cause a developer to build the wrong thing?
4. **Cross-reference sources:** Does the fix align with the project's source-of-truth hierarchy?
5. **Evaluate completeness:** Is there additional context the user needs to make a decision?

### 2. Show the Item

`## Finding X of N — [TYPE] [SEVERITY] | [File(s)]`

Display the type, severity, affected file(s), problem description, suggested fix, and tradeoff.

### 3. Ask the User

Use `AskUser` with contextual options:
- Fix as suggested
- Fix with adjustment (user specifies)
- Skip this item
- Tell me more

**BLOCKING**: Do NOT advance to the next item until the user decides.

**IMMEDIATE RESPONSE RULE:** If the user selects "Tell me more" or responds with free text
(a question, disagreement, or request for clarification) instead of a decision:
**STOP IMMEDIATELY.** Do NOT continue to the next finding. Do NOT batch the response.
Research the user's concern RIGHT NOW using `WebSearch`, codebase analysis, or both.
Provide a thorough answer with evidence. Only AFTER the user is satisfied, re-present the
options and ask for their decision again. **NEVER defer to the end of the findings loop.**

### 4. Apply (if approved)

If the user chose to fix:
1. Apply the correction immediately
2. Confirm it was applied
3. Only then advance to the next item

### Rules
- Never present more than one item at a time
- Never apply corrections without explicit approval
- Internally record each decision (fixed, skipped, adjusted)

---

## Phase 6: Convergence Loop (MANDATORY)

Execute the convergence loop — see AGENTS.md "Common Patterns > Convergence Loop".

**Stage-specific scope for convergence rounds 2+:**
Dispatch the **same 3 droids** from Phase 2 (docs-reviewer, business-logic-reviewer,
code-reviewer). Each agent receives file paths to all docs being reviewed and project
rules (re-read fresh from disk). Do NOT include the findings ledger in agent prompts —
the orchestrator handles dedup using strict matching (same file + same line range ±5 +
same category).

**Failure handling:** If any agent dispatch fails, treat that agent's slot as "zero findings"
for that round but warn the user. Do NOT fail the entire review.

When the loop exits, proceed to Phase 7 (Final Summary).

---

## Phase 7: Final Summary

After the convergence loop exits and all findings are processed:

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

<!-- INLINE-PROTOCOLS:START -->
## Shared Protocols (from AGENTS.md)

The following protocols are referenced by this skill. They are
extracted from the Optimus AGENTS.md to make this plugin self-contained.

### Convergence Loop (Full Roster Model)
Applies to: plan, check, pr-check, coderabbit-review, deep-review, deep-doc-review

The convergence loop eliminates false convergence by dispatching the **same agent roster**
as round 1 in every subsequent round:
- **Round 1:** Orchestrator dispatches all specialist agents in parallel (with full session context)
- **Rounds 2-5:** The **same agent roster** as round 1 is dispatched in parallel via `Task`
  tool, each with zero prior context. Each agent reads all files fresh from disk.
- **Round 2 is MANDATORY** — the "zero new findings" stop condition only applies from round 3 onward
- **Sub-agents do NOT receive the findings ledger.** Dedup is performed entirely by the
  orchestrator after agents return, using **strict matching**: same file + same line range
  (±5 lines) + same category. "Description similarity" is NOT sufficient for dedup — the
  file, location, and category must all match.
- Stop only when: zero new findings (round 3+), round 5 reached, or user explicitly stops
- LOW severity findings are NOT a reason to stop — ALL findings are presented to the user

**Why full roster, not a single agent:** A single generalist agent structurally cannot
replicate the coverage of 8-10 domain specialists. The security-reviewer catches injection
risks a code-reviewer won't. The nil-safety-reviewer catches empty guards a QA analyst won't.
Dispatching a single agent in rounds 2+ creates false convergence — the agent declares
"zero new findings" because it lacks the domain depth, not because the code is clean.


### Protocol: Ring Droid Requirement Check

**Referenced by:** check, pr-check, deep-review, deep-doc-review, coderabbit-review, plan (build delegates droid dispatch to dev-cycle)

Before dispatching ring droids, verify the required droids are available. If any required
droid is not installed, **STOP** and list missing droids.

**Core review droids** (required by check, pr-check, deep-review, coderabbit-review):
- `ring-default-code-reviewer`
- `ring-default-business-logic-reviewer`
- `ring-default-security-reviewer`
- `ring-default-ring-test-reviewer`

**Extended review droids** (required by check, pr-check, deep-review, coderabbit-review):
- `ring-default-ring-nil-safety-reviewer`
- `ring-default-ring-consequences-reviewer`
- `ring-default-ring-dead-code-reviewer`

**QA droids** (required by check, deep-review):
- `ring-dev-team-qa-analyst`

**Documentation droids** (required by deep-doc-review):
- `ring-tw-team-docs-reviewer`
- `ring-default-business-logic-reviewer`
- `ring-default-code-reviewer`

**Implementation droids** (required by build):
- `ring-dev-team-backend-engineer-golang` (Go)
- `ring-dev-team-backend-engineer-typescript` (TypeScript)
- `ring-dev-team-frontend-engineer` (React/Next.js)

**Spec validation droids** (required by plan):
- `ring-default-business-logic-reviewer`
- `ring-default-security-reviewer`
- `ring-dev-team-qa-analyst`
- `ring-default-code-reviewer`

Skills reference this as: "Verify ring droids — see AGENTS.md Protocol: Ring Droid Requirement Check."


<!-- INLINE-PROTOCOLS:END -->
