# Phase 5: Resolve Findings (Interactive)

Loaded by `SKILL.md` after the overview is presented. Walk through each finding one at a time, collect user decisions via AskUser. HARD BLOCK on Tell-me-more rule.

**BEFORE presenting the first finding:** Announce total findings count prominently: `"### Total findings to review: N"`

**If N==1, skip any confirmation prompt** — present the single finding directly with header `(1/1) ...`. The user already chose to review by invoking the skill.

Process ONE finding at a time, starting from highest severity. Present ALL findings sequentially, collecting the user's decision for each. Do NOT apply any fix during this phase — only collect decisions.

For EACH finding, present with `"(X/N)"` progress prefix in the header:

### Deep Research Before Presenting (MANDATORY)
Execute deep research before presenting each finding — see AGENTS.md "Common Patterns > Deep Research Before Presenting". All 12 checklist items apply.

### Problem Description
- What is wrong (file, line, code snippet if relevant)
- Which rule/spec it violates (exact reference to coding standards section, task spec line, or named best practice)
- Which agent(s) flagged it
- Why it matters — what breaks, what risk it creates, what the user would experience

### Impact Analysis (four lenses)

Evaluate the finding through all four perspectives:

- **User (UX):** How does this affect the end user? Usability degradation, confusion, broken workflow, accessibility issue? Would the user notice? Would it block their work?
- **Task focus:** Does this finding relate to what the task was supposed to deliver? Is it within the task's scope, or is it a tangential concern that should be a separate task?
- **Project focus:** Is this MVP-critical, or gold-plating? Does ignoring it now create rework later? Does it conflict with the project's priorities?
- **Engineering quality:** Does this hurt maintainability, testability, reliability, or codebase consistency? What is the technical debt cost of skipping it?

### Proposed Solutions (2-3 options)

Present 2-3 options using the format from AGENTS.md "Common Patterns > Finding Option Format".

### Ask for Decision

**AskUser `[topic]` format:** Format: `(X/N) F#-Category`.
Example: `[topic] (8/12) F8-DeadCode`.

Use `AskUser` tool. **BLOCKING**: Do NOT advance to the next finding until the user decides.
**Every AskUser MUST include these options:**
- One option per proposed solution (Option A, Option B, Option C, etc.)
- Skip — no action
- Tell me more — if selected, STOP and answer immediately (do NOT continue to next finding)

**AskUser template (MANDATORY — follow this exact structure for every finding):**
```
1. [question] (X/N) SEVERITY — Finding title summary
[topic] (X/N) F#-Category
[option] Option A: recommended fix
[option] Option B: alternative approach
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

Internally record every decision: finding ID, chosen option (or "skip"), and rationale if provided. Do NOT apply any fix yet — all fixes are applied in Phase 7.

**Same-nature grouping:** applied automatically per AGENTS.md "Finding Presentation" item 3.

---
