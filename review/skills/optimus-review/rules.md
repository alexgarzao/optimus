# Rules — Anti-Patterns and Guardrails for optimus-review

**Load this file BEFORE deviating from the happy path, when the user asks to
skip a finding, or when you encounter an ambiguous instruction.** Claude
should consult this file proactively; smaller models can run the happy path
without it but MUST load it when a deviation is requested.

## Agent Dispatch
- ALWAYS dispatch agents for: Code Quality, Business Logic, Security, QA, Cross-File Consistency, Spec Compliance
- Dispatch Frontend/Backend specialists based on task scope (Phase 1 Step 1.4)
- Each agent receives file paths and can navigate the codebase autonomously via Read/Grep/Glob tools
- Agents run in PARALLEL — do not wait for one before dispatching another
- Ring droids are required — do not proceed without them

## Scope
- Validate ONLY the files changed by this task — do not audit the entire codebase
- Do not suggest refactoring of pre-existing code unless the task introduced a regression
- Flag pre-existing issues as "pre-existing, not from this task" and do not count them as findings

## Objectivity
- Every finding must reference a specific rule (coding standards section, task spec line, or named best practice)
- "I would do it differently" is NOT a valid finding — it must violate a documented standard or create a measurable risk
- Subjective style preferences are LOW severity at most
- BEFORE presenting each finding: deep research is MANDATORY — project patterns, architectural decisions, existing codebase, task focus, user/consumer use cases, UX impact, API best practices, engineering best practices, language-specific idioms. Option A must be the correct approach backed by research evidence, regardless of effort

## Prioritization
- Security vulnerabilities and spec violations are always CRITICAL/HIGH regardless of effort to fix
- Code style issues that don't affect correctness are LOW
- Missing tests for happy paths are HIGH; missing tests for extreme edge cases are MEDIUM

## Test Gap Cross-Reference
When agents identify a missing test (from QA analyst, spec compliance, or any other agent):
1. **Search future tasks** in the tasks file to check if the test is planned for a later task
2. **If planned in a future task (T-XXX):**
   - Include in the finding: "This test is planned in T-XXX: [task title]"
   - Provide your opinion on timing: should it be created now or deferred? Consider whether the current task introduced the code path being tested, and whether deferring creates a risk window (untested code in production between tasks)
   - During interactive resolution (Phase 5), ask via `AskUser`: "Test for [scenario] is planned for T-XXX. I recommend [creating now / deferring] because [reason]. Do you want to anticipate this test?"
3. **If NOT planned in any future task:**
   - Flag as a standard finding — recommend adding the test now
4. Do NOT silently downgrade test gap severity because a future task covers it — the user decides whether to anticipate or defer

## No False Positives
- If you're unsure whether something is a violation, check the existing codebase for precedent
- If the codebase already does the same thing elsewhere without issue, it's not a finding
- If the spec is ambiguous and the implementation is reasonable, flag as LOW (not HIGH)

## User Authority Over Decisions
- The agent NEVER decides whether a finding should be fixed or skipped — the USER always decides
- ALL findings (CRITICAL, HIGH, MEDIUM, and LOW) MUST be presented to the user for decision
- The agent may recommend an option, but MUST wait for user approval via AskUser before proceeding
- Do NOT auto-skip, auto-dismiss, or auto-resolve any finding regardless of severity
- Do NOT group LOW findings and decide they "don't need attention" — present them individually
- Within a dispatched round, present every finding regardless of severity. Whether to run another round is gated by user prompt.

## Communication
- Be specific: "line 42 of file.tsx uses X, but coding standards section Y requires Z"
- Be constructive: always provide a concrete fix, not just criticism
- Be honest about effort: don't say "trivial" for something that requires refactoring multiple files
- **Re-run guard:** After the convergence loop exits, execute the Re-run Guard protocol
  (Phase 7 in the new layout — see `phases/07-finalize.md`) instead of unconditionally
  suggesting the next stage. The next stage is only suggested when the analysis produces 0
  findings. See AGENTS.md Protocol: Re-run Guard.

## Dry-Run Mode

Follow AGENTS.md Protocol: Dry-Run Mode. The canonical rules apply uniformly
to plan/build/review/done — see the inlined Protocol: Dry-Run Mode block in
`SKILL.md` Shared Protocols section.

**Stage-3 (review) specifics:**
- The "no status change" rule means skip the status update in Phase 1 Step 1.0.8.
- The "no stats" rule means skip Phase 1 Step 1.0.9 (Increment Stage Stats).
- The "no fix application" rule means skip Phase 6 (apply fixes) entirely.
- The "skip convergence rounds 2+" rule means stop after Phase 7 round 1.
- Present a summary showing: total findings, severity breakdown, estimated
  fix effort.
