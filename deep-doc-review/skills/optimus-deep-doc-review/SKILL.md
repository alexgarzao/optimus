---
name: optimus-deep-doc-review
description: "Deep review of project documentation. Finds errors, inconsistencies, gaps, missing data, and improvements. Presents findings in a compact table and resolves one by one with user approval. Does not make automatic changes."
trigger: >
  - When user requests project documentation review
  - Before starting implementation based on docs (validate doc quality)
  - After significant changes to reference docs (PRD, TRD, API design, etc.)
skip_when: >
  - Code review (use optimus-deep-review or optimus-review instead)
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
    - optimus-review
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
    - Convergence loop run, skipped, or stopped (status recorded)
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
| 2 | GAP | HIGH | optimus-tasks.md | Task T-008 does not define Testing Strategy | Add section with unit + integration tests | Additional writing effort | Add before implementation |
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
1. Include `"(X/N)"` progress prefix in the header
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

`## (X/N) — [TYPE] [SEVERITY] | [File(s)]`

Display the type, severity, affected file(s), problem description, suggested fix, and tradeoff.

### 3. Ask the User

**AskUser `[topic]` format:** Format: `(X/N) F#-Category`.
Example: `[topic] (8/12) F8-DeadCode`.

Use `AskUser` with contextual options:
- Fix as suggested
- Fix with adjustment (user specifies)
- Skip this item
- Tell me more — if selected, STOP and answer immediately (do NOT continue to next finding)

**AskUser template (MANDATORY — follow this exact structure for every finding):**
```
1. [question] (X/N) SEVERITY — Finding title summary
[topic] (X/N) F#-Category
[option] Fix as suggested
[option] Fix with adjustment
[option] Skip
[option] Tell me more
```

**BLOCKING**: Do NOT advance to the next item until the user decides.

**HARD BLOCK — IMMEDIATE RESPONSE RULE:** If the user selects "Tell me more" or responds
with free text: **STOP IMMEDIATELY.** Do NOT continue to the next finding. Research and
answer RIGHT NOW. Only after the user is satisfied, re-present the SAME finding's options.
**NEVER defer to the end of the findings loop.**

**Anti-rationalization (excuses the agent MUST NOT use):**
- "I'll address all questions after presenting the remaining findings" — NO
- "Let me continue with the next finding and come back to this" — NO
- "I'll research this after the findings loop" — NO
- "This is noted, moving to the next finding" — NO

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

## Phase 6: Convergence Loop (Optional — Gated)

Execute the opt-in convergence loop — see AGENTS.md "Common Patterns > Protocol: Convergence Loop (Full Roster Model — Opt-In, Gated)".

**Behavioral contract for THIS phase:**
- Round 1 already ran in Phase 2. THIS phase only handles rounds 2 through 5.
- Present the **entry gate** before round 2 (`Run round 2` / `Skip convergence loop`).
- Present the **per-round gate** before rounds 3, 4, 5 (`Continue` / `Stop here`).
- If a dispatched round produces ZERO new findings, declare convergence and exit
  silently — DO NOT ask the user whether to run another round.
- Record the final loop status (`CONVERGED` / `USER_STOPPED` / `SKIPPED` /
  `HARD_LIMIT` / `DISPATCH_FAILED_ABORTED`) for the Final Summary.

**Stage-specific scope for convergence rounds 2+:**
Dispatch the **same 3 droids** from Phase 2 (docs-reviewer, business-logic-reviewer,
code-reviewer). Each agent receives file paths to all docs being reviewed and project
rules (re-read fresh from disk). Do NOT include the findings ledger in agent prompts —
the orchestrator handles dedup using strict matching (same file + same line range ±5 +
same category).

**Failure handling:** If a dispatched agent slot fails (Task tool error, ring droid
unavailable), do NOT count as zero findings. Ask the user via `AskUser` whether to
retry the round or stop (status `DISPATCH_FAILED_ABORTED` if user stops).

When the loop exits (any status), proceed to Phase 7 (Final Summary).

---

## Phase 7: Final Summary

After the convergence loop exits and all findings are processed:

```markdown
## Deep Doc Review — Summary

### Convergence
- Rounds dispatched (round 1 + convergence rounds): X
- Status: CONVERGED | USER_STOPPED | SKIPPED | HARD_LIMIT | DISPATCH_FAILED_ABORTED

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

### Protocol: Convergence Loop (Full Roster Model — Opt-In, Gated)
Applies to: plan, review, pr-check, coderabbit-review, deep-review, deep-doc-review, build

Round 1 (the skill's primary agent dispatch) is MANDATORY and uses the per-skill
default ring roster. Convergence rounds 2+ are OPTIONAL and gated behind explicit
user prompts. Convergence detection (zero new findings) exits the loop silently
without offering further rounds.

- **Round 1:** Orchestrator dispatches the per-skill default roster of specialist
  ring droids in parallel (with full session context). This round is NOT counted
  as a "convergence round" — it is the skill's primary review pass.
- **Rounds 2-5 (each gated by user prompt):** The **same agent roster** as round 1
  is dispatched in parallel via `Task` tool, each with zero prior context. Each
  agent reads all files fresh from disk.
- **Sub-agents do NOT receive the findings ledger.** Dedup is performed entirely
  by the orchestrator after agents return, using **strict matching**: same file +
  same line range (±5 lines) + same category. "Description similarity" is NOT
  sufficient for dedup — the file, location, and category must all match.
- LOW severity findings are NOT a reason to skip presentation — ALL findings are
  presented to the user.

**Entry gate (before round 2 — MANDATORY):** After round 1 completes (decisions
collected, fixes applied), ask via `AskUser`:
```
1. [question] Round 1 produced N findings (X fixed, Y skipped). Run convergence
   round 2 (re-dispatches the same roster with clean context)?
[topic] Convergence-Entry
[option] Run round 2
[option] Skip convergence loop
```
- "Skip convergence loop" → exit with status `SKIPPED`.
- "Run round 2" → dispatch round 2.

**Per-round gate (before rounds 3, 4, 5 — MANDATORY):** After each round 2+
completes (findings presented, fixes applied), before dispatching the next round:
```
1. [question] Round N-1 produced M new findings. Run round N?
[topic] Convergence-RoundN
[option] Continue (run round N)
[option] Stop here
```
- "Stop here" → exit with status `USER_STOPPED`.
- "Continue" → dispatch round N.

**Convergence detection (after each dispatched round — DO NOT ASK):** If a
dispatched round returns ZERO new findings (using the strict matching rules
above), the orchestrator MUST:
1. Print: `Convergence reached at round N: zero new findings.`
2. Exit immediately with status `CONVERGED`.
3. NEVER offer to run another round — the user is informed, not asked.

**Hard limit:** Round 5 is the maximum. After round 5 completes (with new
findings present), exit with status `HARD_LIMIT` without asking.

**Dispatch failure (default):** If a `Task` dispatch fails entirely (transport error,
ring droid unavailable, etc.), do NOT count as zero findings (would falsely
mark `CONVERGED`). Ask via `AskUser`:
```
1. [question] Round N dispatch failed: <error>. Retry, or stop here?
[topic] Convergence-DispatchFail
[option] Retry round N
[option] Stop here
```
- "Retry round N" → re-dispatch.
- "Stop here" → exit with status `DISPATCH_FAILED_ABORTED`.

**Dispatch failure (build-specific carve-out):** `build` runs the convergence loop
deep inside Phase 2.3 of a potentially hours-long multi-subtask implementation. A
blocking prompt at this point is disruptive. `build` therefore MAY treat a single
failed slot as "zero new findings for that slot" and continue silently with a
printed warning. The user is informed via the Final Summary. If multiple slots
fail in the same round, `build` falls back to the default behavior (ask immediately).
This carve-out applies ONLY to `build`; all other skills use the default.

**Exit statuses (recorded for the Final Summary):**

| Status | Trigger |
|--------|---------|
| `CONVERGED` | A dispatched round returned zero new findings |
| `USER_STOPPED` | User chose "Stop here" at a per-round gate (before rounds 3, 4, or 5) |
| `SKIPPED` | User chose "Skip convergence loop" at the entry gate |
| `HARD_LIMIT` | Round 5 completed with new findings still present |
| `DISPATCH_FAILED_ABORTED` | Dispatch failure followed by user choosing to stop |

**Why full roster, not a single agent:** A single generalist agent structurally cannot
replicate the coverage of 8-10 domain specialists. The security-reviewer catches injection
risks a code-reviewer won't. The nil-safety-reviewer catches empty guards a QA analyst won't.
Dispatching a single agent in rounds 2+ creates false convergence — the agent declares
"zero new findings" because it lacks the domain depth, not because the code is clean.


### Protocol: Ring Droid Requirement Check

**Referenced by:** review, deep-doc-review, coderabbit-review, plan, build

Before dispatching ring droids, verify the required droids are available. If any required
droid is not installed, **STOP** and list missing droids.

**Core review droids** (required by review, pr-check, deep-review, coderabbit-review):
- `ring-default-code-reviewer`
- `ring-default-business-logic-reviewer`
- `ring-default-security-reviewer`
- `ring-default-ring-test-reviewer`

**Extended review droids** (required by review, pr-check, deep-review, coderabbit-review):
- `ring-default-ring-nil-safety-reviewer`
- `ring-default-ring-consequences-reviewer`
- `ring-default-ring-dead-code-reviewer`

**QA droids** (required by review, deep-review, build):
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
