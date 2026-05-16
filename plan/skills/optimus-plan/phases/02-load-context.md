# Phase 2 (Load Context): Discover Stack, Load Docs, Build Doc Brief

Loaded by `SKILL.md` after Phase 1 setup completes. Covers Steps 1.1, 1.2, 0.5,
and 1.3 of the original Phase 1 — project structure discovery, document loading,
Doc Brief caching, and existing-code verification.

## Step 1.1: Discover Project Structure

Before loading docs, discover the project's structure:

1. **Identify stack:** Check for `go.mod`, `package.json`, `Makefile`, `Cargo.toml`, etc.
2. **Identify test commands:** Look in `Makefile`, `package.json` scripts, or CI config for lint, test, and integration test commands. These are needed for DoD validation.
3. **Identify project rules and AI instructions (MANDATORY):** Execute project rules discovery — see AGENTS.md Protocol: Project Rules Discovery.

4. **Identify reference docs:** Look for task specs, API design, data model, architecture docs, business requirements, and dependency maps.
5. **Identify doc hierarchy:** Determine the source-of-truth ordering for conflicting docs (typically: project rules/AI instructions > API design > data model > architecture > business requirements > task specs).

## Step 1.2: Load Documents

Resolve TaskSpec — see AGENTS.md Protocol: TaskSpec Resolution. Load the Ring pre-dev
task spec for objective, acceptance criteria, API contracts, and data model.

Ring pre-dev artifacts are the primary specification source.

## Step 0.5: Build Doc Brief (HARD BLOCK on TaskSpec resolution)

Build (or reuse) the per-task Doc Brief — see AGENTS.md Protocol: Doc Brief Cache.

- If `.optimus/sessions/T-XXX/doc-brief.md` exists and `task_spec_hash` matches `git hash-object <current-task-spec>`: REUSE.
- Otherwise: generate the brief now per the protocol. The orchestrator (not a sub-agent) reads PRD, TRD, API, and data-model once, extracts only the sections relevant to T-XXX (mentions of the task ID, AC keywords, listed endpoints/entities/modules), and writes the result to `.optimus/sessions/T-XXX/doc-brief.md`.
- For plan, the `## Relevant Coding Standards / Protocols` section MUST include only these protocols: `Per-Droid Quality Checklists`, `Deep Research Before Presenting`, `Convergence Loop`, `Re-run Guard`.

The Doc Brief is the primary context passed inline to all downstream sub-agent dispatches in Phase 3 (validation). Do NOT instruct sub-agents to read PRD/TRD/API/data-model directly unless the Doc Brief is explicitly insufficient for a finding.

## Step 1.3: Verify Existing Code

Check the codebase for:
- Are dependencies (required tasks) actually implemented?
- Do shared packages/interfaces referenced exist?
- Does the DB schema match the data model doc?
- Are there existing patterns to follow?

## Validation Dimensions (reference)

Before entering Phase 3 execution, ensure you know the 8 validation dimensions you
must cover — Read `templates/validation-dimensions.md` for the full checklist.
The dimensions are referenced directly from Phase 3 steps.
