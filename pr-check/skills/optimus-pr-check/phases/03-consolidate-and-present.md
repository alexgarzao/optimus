# Phase 3: Consolidate, Present, and Resolve Findings

Loaded by `SKILL.md` after agents return. Consolidate with source attribution, dedupe, present overview, walk through each finding interactively via AskUser. HARD BLOCK on Tell-me-more.

### Phase 4: Consolidation

After ALL agents return:

1. **Merge** all new findings into a single list
2. **Merge** all comment evaluations into a single list
3. **Deduplicate** — if multiple agents flag the same issue, keep one entry noting which agents agreed
4. **Cross-reference** — for existing comments, note agreement/disagreement between agents and the original source
5. **Classify false positives** — for Codacy/DeepSource findings that agents contest as misconfigured rules (e.g., ES5 rules in modern project, framework-specific rules for wrong framework), separate into "False Positive — Misconfigured Rule" category
6. **Sort** by severity: CRITICAL > HIGH > MEDIUM > LOW
7. **Assign** sequential IDs (F1, F2, F3...)

**Mode gate:** Steps 2 and 4 are SKIPPED when `REVIEW_MODE=diff` (no
AGREE/CONTEST verdicts produced; nothing to merge or cross-reference).

### Source Attribution

Each finding MUST include its source(s):

| Source Type | Label |
|-------------|-------|
| New finding from agent review | `[Agent: <agent-name>]` |
| CI check failure | `[CI: <check-name>]` |
| Codacy finding validated by agent | `[Codacy + Agent: <agent-name>]` |
| DeepSource finding validated by agent | `[DeepSource + Agent: <agent-name>]` |
| CodeRabbit comment validated by agent | `[CodeRabbit + Agent: <agent-name>]` |
| CodeRabbit duplicate comment | `[CodeRabbit — DUPLICATE + Agent: <agent-name>]` |
| CodeRabbit outside-diff comment | `[CodeRabbit — OUTSIDE PR DIFF + Agent: <agent-name>]` |
| Human review comment validated by agent | `[Reviewer: <username> + Agent: <agent-name>]` |
| Existing comment contested by agent | `[Contested: <source> vs Agent: <agent-name>]` |

---

### Phase 5: Present Overview

```markdown
### PR Review: #<number> — X findings

### CI Status
- Codacy: <conclusion> (<N> annotations)
- DeepSource: <analyzer statuses>
- Other checks: X passing, Y failing

### False Positives — Misconfigured Rules (Codacy/DeepSource)
| # | Source | Pattern/Title | Count | Reason |
|---|--------|--------------|-------|--------|

### Genuine Findings (validated by agents)
| # | Severity | File | Summary | Source | Agent(s) |
|---|----------|------|---------|--------|----------|

[Mode gate: the "Contested Comments" and "Agent Verdicts" tables below are
rendered ONLY when `REVIEW_MODE=findings`. In `diff` mode, render only "False
Positives", "Genuine Findings", and "Summary" sections — replace the "Agent
Verdicts" line with a single line: "Agents performed fresh diff review
(REVIEW_MODE=diff). No verdicts on existing comments."]

### Contested Comments
| # | Original Source | Summary | Contesting Agent | Reason |
|---|----------------|---------|-----------------|--------|

### Agent Verdicts
| Agent | Evaluated | Agree | Contest | New |
|-------|-----------|-------|---------|-----|

### Summary
- New findings: X | Validated comments: X | Contested: X | False positives: X
```

---

### Phase 6: Finding Presentation and Resolution

Findings are presented ONE AT A TIME, decisions collected for ALL, then fixes applied ALL AT ONCE at the end.

**=== MANDATORY — Progress Tracking (NEVER SKIP) ===**

**BEFORE presenting the first finding, you MUST:**
1. Count the TOTAL number of findings (N) — sum of genuine findings, validated comments, contested comments, and new agent findings
2. Display the total prominently: `"### Total findings to review: N"`
3. **Skip confirmation when N==1:** Present the single finding directly with header `(1/1) ...`. Do NOT ask "Review 1 finding?" or similar — the user already chose to review.
4. This total MUST be visible to the user BEFORE any finding is presented

**For EVERY finding presented, you MUST:**
1. Include `"(X/N)"` progress prefix in the header — this is NOT optional
2. X starts at 1 and increments sequentially
3. N is the total announced above and NEVER changes mid-review
4. If you present a finding WITHOUT "(X/N)" progress prefix in the header, you are violating this rule — STOP and correct it

**The user MUST always know:**
- How many findings exist in total (N)
- Which finding they are currently reviewing (X)
- How many remain (N - X)

### Step 6.1: Present Findings One at a Time (collect decisions only)

Present ALL findings sequentially, one after another, collecting the user's decision for each. Do NOT apply any fix during this phase — only collect decisions.

For EACH finding:

#### Finding Header

`## (X/N) F# — [SEVERITY] | [Source] | [Category]`

Example: `## (1/12) F1 — [HIGH] | Codacy + Agent | Security`
Example: `## (5/12) F5 — [MEDIUM] | DeepSource + Agent | Anti-pattern`
Example: `## (8/12) F8 — [MEDIUM] | CodeRabbit — DUPLICATE + Agent | Error handling`
Example: `## (10/12) F10 — [LOW] | CodeRabbit — OUTSIDE PR DIFF + Agent | Naming`
Example: `## (12/12) F12 — [LOW] | CodeRabbit + Agent | Style`

#### Deep Research Before Presenting (MANDATORY)

Execute deep research before presenting each finding — see AGENTS.md "Common Patterns > Deep Research Before Presenting". All 12 checklist items apply.

#### Deep Technical Analysis

**Problem description:**
- Clear description with code snippet
- For validated comments: show original comment and agent's validation
- For contested comments: show both the original and agent's contestation

**CodeRabbit's original suggestion (CodeRabbit-sourced findings only):**

Render this block ONLY when the finding's source is CodeRabbit AND at least one of `FIX_LABEL`, `FIX_DIFF`, or `AI_PROMPT` is non-empty. Render only the sub-fields that are populated; omit absent sub-fields silently. If all three are empty, omit the entire block.

- *Fix style:* `<FIX_LABEL>` *(e.g., `Minimal fix` or `Suggested refactor`)*
- *Suggested change:*
  ```diff
  <FIX_DIFF>
  ```
- *CodeRabbit-curated AI agent prompt:*
  > <AI_PROMPT>

Rationale: this gives the user full visibility into what CodeRabbit proposed before they pick from `Proposed Solutions`. The agent-validated options below remain the primary recommendation; the CodeRabbit block is supplementary context.

**Impact analysis (four lenses):**
- **UX:** End-user impact — errors, data loss, broken workflows
- **Task focus:** Within PR scope or tangential?
- **Project focus:** MVP-critical or gold-plating?
- **Engineering quality:** Maintainability, testability, reliability, consistency

#### Proposed Solutions

Present 2-3 options using the format from AGENTS.md "Common Patterns > Finding Option Format".

#### Collect Decision

**AskUser `[topic]` format:** Format: `(X/N) F#-Category`.
Example: `[topic] (8/12) F8-DeadCode`.

Use `AskUser`. **BLOCKING** — do not advance until decided.
**Every AskUser MUST include these options:**
- One option per proposed solution (Option A, Option B, Option C, etc.)
- **Apply CodeRabbit's suggested fix as-is** — *only* when the finding is CodeRabbit-sourced AND `FIX_DIFF` is non-empty. Selecting this option causes Phase 8 (Step 8.2) to apply `FIX_DIFF` verbatim, bypassing the agent-recommended options. Omit this option entirely when `FIX_DIFF` is empty (no CodeRabbit fix to apply) or when the finding is not CodeRabbit-sourced.
- Skip — no action
- Tell me more — if selected, STOP and answer immediately (do NOT continue to next finding)

**AskUser template (MANDATORY — follow this exact structure for every finding):**
```
1. [question] (X/N) SEVERITY — Finding title summary
[topic] (X/N) F#-Category
[option] Option A: recommended fix
[option] Option B: alternative approach
[option] Apply CodeRabbit's suggested fix as-is   ← include ONLY for CodeRabbit findings with non-empty FIX_DIFF
[option] Skip
[option] Tell me more
```

**HARD BLOCK — IMMEDIATE RESPONSE RULE:** If the user selects "Tell me more" or responds
with free text: **STOP IMMEDIATELY.** Do NOT continue to the next finding. Research and
answer RIGHT NOW. Only after the user is satisfied, re-present the SAME finding's options.
**NEVER defer to the end of the findings loop.**

**Anti-rationalization (excuses the agent MUST NOT use):**
- "I'll address all questions after presenting the remaining findings" — NO
- "Let me continue with the next finding and come back to this" — NO
- "I'll research this after the findings loop" — NO
- "This is noted, moving to the next finding" — NO

Record: finding ID, source(s), decision (fix/skip/defer), chosen option. Do NOT apply any fix yet.

**Same-nature grouping:** applied automatically per AGENTS.md "Finding Presentation" item 3.

---
