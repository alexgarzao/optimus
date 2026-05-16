# Phase 3: Interactive Finding-by-Finding Resolution (collect decisions only)

Loaded after Phase 2. Walk each finding via AskUser, collect decisions. HARD BLOCK on Tell-me-more — deep research mandatory before each finding.

**BEFORE presenting the first finding:** Announce total findings count prominently: `"### Total findings to review: N"`

**If N==1, skip any confirmation prompt** — present the single finding directly with header `(1/1) ...`. The user already chose to review by invoking the skill.

Process ONE finding at a time, in severity order (CRITICAL first, LOW last). Collect ALL decisions first — do NOT apply any fix during this phase.

For EACH finding, present with `"(X/N)"` progress prefix in the header, including the origin tag:
- Regular: `## (X/N) — [SEVERITY] | CodeRabbit | Category`
- Duplicate: `## (X/N) — [SEVERITY] | CodeRabbit — DUPLICATE | Category`
- Outside diff: `## (X/N) — [SEVERITY] | CodeRabbit — OUTSIDE PR DIFF | Category`

### 1. Deep Research Before Presenting (MANDATORY)

**BEFORE presenting any finding to the user, you MUST research it deeply.** This research
is done SILENTLY — do not show the research process. Present only the conclusions.

**Research checklist (ALL items, every finding):**

1. **Project patterns:** Read the affected file(s) fully, understand the patterns used, check how similar cases are handled elsewhere in the codebase
2. **Architectural decisions:** Review project rules (AGENTS.md, PROJECT_RULES.md, etc.) and architecture docs. Understand WHY the project is structured this way
3. **Existing codebase:** Search for precedent — if the codebase already does the same thing in other places, that context changes the finding's weight
4. **Current task focus:** Is this finding within the scope of the changes being reviewed? Flag tangential findings as such
5. **User/consumer use cases:** Who consumes this code — end users, other services, internal modules? Trace impact to real user scenarios
6. **UX impact:** For user-facing changes, evaluate usability, accessibility, error messaging, and workflows
7. **API best practices:** REST conventions, error handling, idempotency, status codes, pagination, versioning, backward compatibility
8. **Engineering best practices:** SOLID principles, DRY, separation of concerns, error handling, resilience, observability, testability
9. **Language-specific best practices:** Use `WebSearch` to research idioms for the specific language (Go, TypeScript, etc.) — official style guides, linter rules, community patterns
10. **Correctness over convenience:** Always recommend the correct approach, regardless of effort
11. **Production resilience:** Would this code survive production conditions? Consider: timeouts on external calls, retry with backoff, circuit breakers, graceful degradation, resource cleanup, graceful shutdown, and behavior under load
12. **Data integrity and privacy:** Are transaction boundaries correct? Could partial writes occur? Is PII properly handled (not logged, masked in responses)? LGPD/GDPR compliance?

**After research, form your recommendation:** Option A MUST be the approach you believe is correct based on all the research above, backed by evidence.

### 2. Description

- What was found (problem identified)
- Relevant current code with context
- Severity classification (CRITICAL/HIGH/MEDIUM/LOW) with justification

### 3. Impact Analysis (four lenses)

Evaluate the finding through all four perspectives to help the user make an informed decision:

- **User (UX):** How does this affect the end user? Usability degradation, confusion, broken workflow, accessibility issue? Would the user notice? Would it block their work?
- **Task focus:** Does this finding relate to the changes being reviewed? Is it within scope, or a tangential concern that should be a separate effort?
- **Project focus:** Is this MVP-critical, or gold-plating? Does ignoring it now create rework later? Does it conflict with the project's priorities?
- **Engineering quality:** Does this hurt maintainability, testability, reliability, or codebase consistency? What is the technical debt cost of skipping it?

### 4. Proposed Solutions (2-3 options)

**Option A MUST be your researched recommendation** — always prefer correctness over convenience.

For each option:

```
**Option A: [name] (RECOMMENDED)**
[Concrete steps — what to do, which files to change, what code to write]
- Why recommended: [reference to research — best practice, project pattern, official docs]
- Impact: UX / Task focus / Project focus / Engineering quality
- Effort: low / medium / high / very high
- Estimated time: < 5 min / 5-15 min / 15-60 min / 1-4h / > 4h

**Option B: [name]**
[Alternative approach]
- Impact: UX / Task focus / Project focus / Engineering quality
- Effort: low / medium / high / very high
- Estimated time: < 5 min / 5-15 min / 15-60 min / 1-4h / > 4h
```

### 5. Wait for User Decision

**AskUser `[topic]` format:** Format: `(X/N) F#-Category`.
Example: `[topic] (8/12) F8-DeadCode`.

Use `AskUser` tool. **BLOCKING**: Do NOT proceed to the next finding until the user decides.
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

The user may:
- Accept one of the proposed options (e.g., "A", "B")
- Select "Tell me more" for deeper analysis
- Resolve differently (user describes approach)
- Ignore this issue (proceed without fixing)

Record the decision internally. Do NOT apply any fix yet — all fixes are applied in Phase 4.

**Same-nature grouping:** applied automatically per AGENTS.md "Finding Presentation" item 3.

---
