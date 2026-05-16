# Phase 4 (Present Findings): Summary, Walk-Through, Decision Collection

Loaded by `SKILL.md` after Phase 3 dispatches the validation agents. This was
the original "Phase 3: Present and Resolve Findings".

## Step 3.1: Present Summary, then Walk Through Each Finding

1. **Announce total findings count:** Display `"### Total findings to review: N"` prominently before presenting the first finding
2. **Skip confirmation when N==1:** Present the single finding directly with header `(1/1) ...`. Do NOT ask "Review 1 finding?" or similar — the user already chose to review.
3. **Present the summary report** (tables from `templates/output-format.md`) for bird's-eye view
4. **Then present findings ONE AT A TIME** in priority order: contradictions > missing specs > test gaps > observability > DoD > ambiguities

**For EACH finding**, present with `"(X/N)"` progress prefix in the header.

### Deep Research Before Presenting (MANDATORY)

Execute deep research before presenting each finding — see AGENTS.md "Common Patterns > Deep Research Before Presenting". All 12 checklist items apply.

### Present the Finding

- **Problem:** Clear description, referencing exact doc locations
- **Why it matters:** Impact analysis through four lenses:
  - **UX:** How does this affect the end user?
  - **Task focus:** Within task scope or tangential?
  - **Project focus:** MVP-critical or gold-plating?
  - **Engineering quality:** Maintainability, testability, reliability impact

### Proposed Solutions (2-3 options)

Present 2-3 options using the format from AGENTS.md "Common Patterns > Finding Option Format".

### Collect Decision

   **AskUser `[topic]` format:** Format: `(X/N) F#-Category`.
   Example: `[topic] (8/12) F8-DeadCode`.

5. Use `AskUser` tool. **BLOCKING**: Do NOT advance to the next finding until the user decides.
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

6. **HARD BLOCK — IMMEDIATE RESPONSE RULE:** If the user selects "Tell me more" or responds
   with free text: **STOP IMMEDIATELY.** Do NOT continue to the next finding. Research and
   answer RIGHT NOW. Only after the user is satisfied, re-present the SAME finding's options.
   **NEVER defer to the end of the findings loop.**

   **Anti-rationalization (excuses the agent MUST NOT use):**
   - "I'll address all questions after presenting the remaining findings" — NO
   - "Let me continue with the next finding and come back to this" — NO
   - "I'll research this after the findings loop" — NO
   - "This is noted, moving to the next finding" — NO
7. **Track all decisions** internally. Do NOT apply any fix yet — all fixes are applied in Phase 5.
