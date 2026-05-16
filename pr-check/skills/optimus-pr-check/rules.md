# Rules — Anti-Patterns and Guardrails for optimus-pr-check

**Load this file BEFORE deviating from the happy path, when the user requests a
dry-run, asks to skip a finding, or when you encounter an ambiguous
instruction.** Claude should consult this file proactively; smaller models can
run the happy path without it but MUST load it when a deviation is requested.

## Every Invocation Starts From Scratch

**HARD BLOCK:** Every time this skill is invoked, it MUST fetch ALL data fresh
from the PR. There is NO state carried over from previous invocations.

- Do NOT assume issues from a previous run are still resolved
- Do NOT skip fetching comments because "I already saw this PR"
- Do NOT say "issues were already resolved" without fetching and verifying RIGHT NOW
- New comments, new commits, new CI results may exist since the last run
- Always run Phase 1 completely: fetch metadata, fetch ALL threads, fetch CI checks, fetch changed files
- The PR may have changed entirely since the last time you looked at it

If you find yourself saying "these were already addressed" without having run
`gh api` commands in THIS session, you are violating this rule.

## Core Rules

- Fetch comments from ALL sources before starting: Codacy (`**Codacy**` prefix from `github-actions[bot]`), DeepSource (`**DeepSource**` prefix from `github-actions[bot]`), CodeRabbit (`coderabbitai[bot]`), and human reviewers
- Agents MUST evaluate ALL existing comments — validate, contest, or mark as already fixed
- Every finding must include source attribution
- Only review files changed in the PR
- ALWAYS announce total findings count (N) before presenting the first finding: `"### Total findings to review: N"`
- **When N==1, skip any gating prompt** — present the single finding directly with header `(1/1) ...`. Do not ask "Review 1 finding?" or similar.
- Present findings ONE AT A TIME in severity order, ALWAYS showing "(X/N)" progress prefix in EVERY finding header
- Collect ALL decisions first (Phase 3), then apply ALL approved fixes at once (Phase 4)
- Coverage verification runs ONLY after all fixes are applied; the convergence loop is opt-in (gated)
- No changes without user approval
- BEFORE presenting each finding: deep research is MANDATORY — project patterns, architectural decisions, existing codebase, task focus, user/consumer use cases, UX impact, API best practices, engineering best practices, language-specific idioms. Option A must be the correct approach backed by research evidence, regardless of effort
- If the user selects "Tell me more" or responds with free text: STOP, research and answer thoroughly RIGHT NOW — do NOT defer to the fix phase or continue to the next finding. NEVER batch responses.
- Ring droids are required for complex fixes and for review dispatch — do not proceed without them
- Simple fixes (obvious resolution provided by review agents) are applied directly; complex or uncertain fixes use ring droids with TDD cycle (RED-GREEN-REFACTOR)
- Each fix gets a separate commit regardless of whether it was applied directly or via ring droid
- For won't-fix Codacy findings: use the underlying linter's suppression syntax (e.g., `biome-ignore` for Biome, `eslint-disable-next-line` for ESLint, `//nolint` for Go). `codacy:ignore` does NOT exist.
- For won't-fix DeepSource findings: add `// skipcq: <shortcode>` inline and commit
- Response to ALL comments is uniform: commit SHA for fixes, concrete reason for won't-fix
- Do NOT merge the PR — only review and apply fixes
- Push triggers Codacy/DeepSource reanalysis automatically
- The agent NEVER decides whether a finding should be fixed or skipped — the USER always decides
- ALL findings (CRITICAL, HIGH, MEDIUM, and LOW) MUST be presented to the user for decision
- The agent may recommend an option, but MUST wait for user approval via AskUser before proceeding
- Do NOT auto-skip, auto-dismiss, or auto-resolve any finding regardless of severity

## Dry-Run Mode

If the user requests a dry-run (e.g., "dry-run pr-check", "preview PR review"):
- Fetch ALL PR data normally (Phase 1)
- Dispatch ALL review agents (Phase 2) and consolidate (Phase 3)
- Present ALL findings in Phase 3 (interactive resolution)
- **Do NOT apply fixes** — skip Phase 4 (TDD cycle)
- **Do NOT push anything** — skip Phase 5
- **Do NOT respond to PR comments** — skip Phase 6
- **Do NOT enter the convergence loop (rounds 2+)** — round 1 (primary review pass) is sufficient for preview
- Present results as informational with estimated fix effort
