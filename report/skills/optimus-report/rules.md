# Rules — Anti-Patterns and Guardrails for optimus-report

**Load this file BEFORE deviating from the happy path, when the user asks to
write to a project file, or when you encounter an ambiguous instruction.**

Report is a near-read-only dashboard. The rules below define the narrow
write-allowlist and the non-negotiable read-only stance for everything else.

## Core Rules

- **NEVER modify project files** — this agent is strictly read-only with two allow-listed
  exceptions: (a) exports to `.optimus/reports/` (gitignored), and (b) writing
  `defaultScope` to `.optimus/config.json` when the user opts in (see Phase 4 Step 4.1, sub-step 4).
- **NEVER change task status** — only report current state.
- **NEVER invoke other stage agents** — only recommend.
- Present the full dashboard even if there's only 1 task.
- If optimus-tasks.md has no table or invalid format, suggest running `/optimus-import` to convert it to the standard format.
- If optimus-tasks.md does not exist, suggest running `/optimus-import` to create one from existing task files.
- Always show the dependency graph, even for small projects — it reveals parallelization opportunities.
