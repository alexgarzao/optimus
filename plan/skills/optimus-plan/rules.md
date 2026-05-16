# Rules — Anti-Patterns and Guardrails for optimus-plan

**Load this file BEFORE deviating from the happy path, when the user asks to skip a
phase, or when you encounter an ambiguous instruction.** Claude should consult this
file proactively; smaller models can run the happy path without it but MUST load it
when a deviation is requested.

## Core Rules

- Do NOT generate code — this is analysis only
- Do NOT assume — if something is ambiguous, flag it
- ALWAYS check both happy path AND error paths
- Prioritize findings: contradictions > missing specs > test gaps > observability gaps > DoD issues > ambiguities
- Reference exact file locations when citing docs
- Test Coverage Gaps (Dimension 5) is MANDATORY and MUST enumerate gaps for ALL three test types plus cross-cutting scenarios
- Observability Gaps (Dimension 7) is MANDATORY. Check existing codebase logging patterns and verify new components follow them
- ALWAYS use the two-phase flow: Phase 4 presents summary then walks through each finding one at a time. Phase 5 applies all approved corrections at once
- If corrections were applied, ask the user for commit approval — do NOT commit without explicit approval
- Every finding must reference a specific doc section or standard — "I would do it differently" is not a valid finding
- BEFORE presenting each finding: deep research is MANDATORY — project patterns, architectural decisions, existing codebase, task focus, user/consumer use cases, UX impact, API best practices, engineering best practices, language-specific idioms. Option A must be the correct approach backed by research evidence, regardless of effort
- The agent NEVER decides whether a finding should be fixed or skipped — the USER always decides
- ALL findings (CRITICAL, HIGH, MEDIUM, and LOW) MUST be presented to the user for decision
- The agent may recommend an option, but MUST wait for user approval via AskUser before proceeding
- Do NOT auto-skip, auto-dismiss, or auto-resolve any finding regardless of severity
- **Re-run guard:** After the convergence loop exits, execute the Re-run Guard protocol
  (Phase 8) instead of unconditionally suggesting the next stage. The next stage is only
  suggested when the analysis produces 0 findings. See AGENTS.md Protocol: Re-run Guard.

## Dry-Run Mode

Follow AGENTS.md Protocol: Dry-Run Mode. The canonical rules apply uniformly
to plan/build/review/done — see the inlined Protocol: Dry-Run Mode block in
`SKILL.md` Shared Protocols section.

**Stage-1 (plan) specifics:**
- The "no workspace creation" rule means skip Phase 1 Step 1.0.5 (status reservation
  AND workspace creation).
- The "no stats" rule means skip Phase 1 Step 1.0.7 (Increment Stage Stats).
- The "no commit/push/re-run" rule means skip Phases 5, 6, 8, and 9.
- The "skip convergence rounds 2+" rule means stop after Phase 7 round 1.
