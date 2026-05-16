# Rules — Anti-Patterns and Guardrails for optimus-coderabbit-review

**Load this file BEFORE deviating from the happy path, when the user asks to
skip a finding, or when you encounter an ambiguous instruction.** Claude should
consult this file proactively; smaller models can run the happy path without it
but MUST load it when a deviation is requested.

## Core Rules

- All findings are investigated, one at a time, in severity order (CRITICAL > HIGH > MEDIUM > LOW)
- BEFORE presenting each finding: deep research is MANDATORY — project patterns, architectural decisions, existing codebase, task focus, user/consumer use cases, UX impact, API best practices, engineering best practices, language-specific idioms. Option A must be the correct approach backed by research evidence, regardless of effort
- No changes without prior user approval — the user ALWAYS decides the approach
- Ignored findings are recorded but not fixed
- Use review agents (Phase 4 Step 4.1) for logic changes; use codebase exploration for context investigation
- Prioritize correctness over convenience
- If a fix involves logic changes (flow, conditions, behavior), mention explicitly
- Follow project coding standards (PROJECT_RULES.md or equivalent)
- After each fix, update the todo list to maintain progress visibility
- TDD cycle is mandatory for every approved fix — no exceptions
- Do NOT proceed to the next finding until all tests pass or the failure is classified
- Maximum 3 retry attempts per test failure
- Maximum 1 skipped test per fix, with documented justification
- The agent NEVER decides whether a finding should be fixed or skipped — the USER always decides
- ALL findings (CRITICAL, HIGH, MEDIUM, and LOW) MUST be presented to the user for decision
- The agent may recommend an option, but MUST wait for user approval via AskUser before proceeding
- Do NOT auto-skip, auto-dismiss, or auto-resolve any finding regardless of severity
