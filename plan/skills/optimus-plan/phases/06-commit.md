# Phase 6 (Commit): Commit Approved Changes

Loaded by `SKILL.md` after Phase 5 applies corrections. This was the original
"Phase 5: Commit Changes".

## Step 5.1: Commit Changes (if any modifications were made)

If any corrections were applied in Phase 5:
1. Run `git status` and `git diff` to review all changes
2. Check for sensitive data (secrets, keys, tokens) — if found, STOP and warn the user
3. Present the summary of changes and ask the user for commit approval via `AskUser`
4. If approved, stage all modified files and commit using the task's Tipo for the conventional commit prefix (Feature→`feat`, Fix→`fix`, Refactor→`refactor`, Chore→`chore`, Docs→`docs`, Test→`test`). Example: `feat(T-003): fix spec — [brief summary of corrections]`
5. Run `git status` to confirm the commit succeeded

If no corrections were applied (all findings skipped), skip this step.
