# Verify Code

## Description

Two-phase code verification supporting Go, TypeScript, Python, and generic (Makefile) projects. Phase 1 runs static analysis and unit tests in parallel. Phase 2 runs integration and E2E tests sequentially. Presents an executive summary with a MERGE_READY or NEEDS_FIX verdict.

## Variables

None — automatically detects Makefile targets.

## Skill

See the full installable version at [`verify/skills/optimus-verify-code/SKILL.md`](../../verify/skills/optimus-verify-code/SKILL.md).

## Example

```
/optimus-verify-code — runs all checks and presents a summary with verdict.
```
