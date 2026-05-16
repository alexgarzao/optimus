# Phase 4: Rule Configuration + Apply Fixes

Loaded by `SKILL.md` after resolution. Recommend Codacy/DeepSource rule configuration where applicable, then apply ALL approved fixes with TDD cycle (RED-GREEN-REFACTOR), one commit per fix.

### Phase 7: Recommend Rule Configuration (Codacy/DeepSource)

If false positives were identified, present configuration recommendations:

### For Codacy false positives:

```markdown
**Via .codacy.yml:**
  exclude_paths:
    - "<path>"

**Via Codacy UI:** app.codacy.com > Repository > Code Patterns > disable pattern
```

### For DeepSource false positives:

```markdown
**Via .deepsource.toml:**
  exclude_patterns = ["<path>"]

**Via inline suppression:** // skipcq: <issue-code>
**Via DeepSource Dashboard:** app.deepsource.com > suppress issue
```

Ask the user whether to apply config changes. If approved, edit the config files.

---

### Phase 8: Apply All Approved Fixes with TDD Cycle

**IMPORTANT:** This phase runs ONCE, after ALL findings have been presented and ALL decisions collected in Phase 6. No fix is applied during Phase 6.

### Step 8.1: Pre-Apply Summary

```markdown
### Fixes to Apply (X of Y findings)

| # | Finding | Source | Decision | Files |
|---|---------|--------|----------|-------|
| F1 | [summary] | [Codacy + Agent] | Fix (Option A) | file1.go |
| F3 | [summary] | [Agent: Security] | Fix (Option B) | auth.go |

### Skipped (Z findings)
| # | Finding | Source | Reason |
|---|---------|--------|--------|

### Deferred (W findings)
| # | Finding | Source | Destination |
|---|---------|--------|-------------|
```

### Step 8.2: Classify and Apply Each Fix

For each approved fix, classify its complexity and apply accordingly — see AGENTS.md
"Common Patterns > Fix Implementation (Complexity-Based Dispatch)".

**Complexity classification (per finding):**

| Complexity | Criteria | Action |
|------------|----------|--------|
| **CodeRabbit-as-is** | User selected `Apply CodeRabbit's suggested fix as-is` in Phase 6, AND the finding has a non-empty `FIX_DIFF` | Apply `FIX_DIFF` verbatim with Edit tool, then run unit tests |
| **Simple** | Review agent provided exact fix, single file, localized change, obvious resolution (typo, missing nil guard, import, rename, dead code removal) | Apply directly with Edit tool |
| **Complex** | Multiple files, new logic, architectural impact, new test scenarios, security-sensitive, uncertain resolution | Dispatch ring droid with TDD cycle |
| **Uncertain** | Cannot confidently classify | Treat as complex → dispatch ring droid |

**CodeRabbit-as-is fix flow:**
1. Apply `FIX_DIFF` verbatim using Edit/MultiEdit. Treat the diff as authoritative — do NOT re-derive from agent recommendation.
2. Run unit tests to verify no regression.
3. If tests fail → revert the diff and escalate to ring droid dispatch (Complex flow), informing the user that CodeRabbit's diff did not pass tests as-applied. Record the failure in the per-finding audit trail.

**Relationship to coderabbit-review (intentional divergence):** This as-is path
is unique to `pr-check` and intentionally absent from `coderabbit-review`.
`coderabbit-review` always applies CodeRabbit findings via TDD (RED-GREEN-REFACTOR)
because that skill is for the case where the user wants to deeply understand
and re-implement each suggestion. `pr-check` accepts the trade-off of merging
CodeRabbit's exact patches (even nitpicks) because the goal here is unblocking
PR review, not author understanding. If you want as-is application, stay on
`pr-check`; if you want TDD-driven re-implementation, switch to
`coderabbit-review`. See coderabbit-review/SKILL.md Phase 4 for the mirror note.

**Simple fix flow:**
1. Apply the fix directly using Edit/MultiEdit tools
2. Run unit tests to verify no regression
3. If tests fail → revert the change and escalate to ring droid dispatch

**Complex fix flow:**
1. Dispatch the stack-appropriate ring droid via `Task` tool with TDD cycle (RED-GREEN-REFACTOR)
2. Documentation fixes use ring-tw-team droids without TDD

**Droid selection (complex fixes only):**
- Go → `ring-dev-team-backend-engineer-golang`
- TypeScript → `ring-dev-team-backend-engineer-typescript`
- React/Next.js → `ring-dev-team-frontend-engineer`
- Tests → `ring-dev-team-qa-analyst`
- Docs → `ring-tw-team-functional-writer`, `ring-tw-team-api-writer`

### Step 8.3: Handle Test Failures (max 3 attempts)

1. **Logic bug** → Return to RED, adjust test/fix
2. **Flaky test** → Re-execute at least 3 times in a clean environment to confirm
   flakiness. Maximum 1 test skipped per fix. Document explicit justification
   (error message, flakiness evidence) and tag with `pending-test-fix`
3. **External dependency** → Pause and wait for restoration

### Step 8.4: Commit Each Fix

After each successful TDD cycle:

1. Stage ONLY the files changed by this fix
2. Commit with descriptive message:
   ```bash
   COMMIT_MSG_FILE=$(mktemp)
   printf 'fix: <concise description>\n\nAddresses review finding F<N> [<source>]' > "$COMMIT_MSG_FILE"
   git commit -F "$COMMIT_MSG_FILE"
   rm -f "$COMMIT_MSG_FILE"
   ```
3. Record `{finding_id} → {commit_sha}` mapping

### Step 8.4.1: Final Lint Check

**After ALL fixes are committed**, run lint once using the resolved command from
Step 3.1, wrapped in `_optimus_quiet_run` — see AGENTS.md Protocol: Quiet
Command Execution:
```bash
_optimus_quiet_run "make-lint" make lint
```
If lint fails, fix formatting issues, amend the last commit or create a `chore: fix lint` commit.

### Step 8.5: Suppress Won't-Fix Findings (Codacy/DeepSource)

For each **skipped/discarded** finding from Codacy or DeepSource, add inline suppression:

**Codacy findings:**
Codacy has NO inline suppression syntax of its own. It uses the underlying linter's mechanism. You MUST identify which linter Codacy is running (check the Codacy annotation or `.codacy.yml`) and use that linter's suppression:
- **Biome** (JS/TS): `// biome-ignore lint/<category>/<rule>: <reason>` on the line BEFORE the flagged code
- **ESLint** (JS/TS): `// eslint-disable-next-line <rule>` on the line BEFORE
- **golangci-lint** (Go): `//nolint:<linter>` on the same line
- **Pylint** (Python): `# pylint: disable=<rule>` on the same line

**IMPORTANT:** `codacy:ignore` does NOT exist. Never use it.

**DeepSource findings:**
Add `// skipcq: <shortcode>` comment on the line above the flagged code (e.g., `// skipcq: JS-C1003`).

Commit all suppressions together:
```bash
COMMIT_MSG_FILE=$(mktemp)
printf 'chore: suppress won'\''t-fix static analysis findings\n\nCodacy: X findings suppressed (via <linter> inline suppression)\nDeepSource: Y findings suppressed (skipcq)' > "$COMMIT_MSG_FILE"
git commit -F "$COMMIT_MSG_FILE"
rm -f "$COMMIT_MSG_FILE"
```

Record the suppression commit SHA for use in Phase 13.

---
