# Optimus — Agent Instructions

This repository contains installable skill plugins for Droid (Factory) and Claude Code.
Every change to this repo is made by AI agents. This file is the primary context source
for any agent operating here.

## Repository Structure

```
optimus/
├── .factory-plugin/marketplace.json   # Plugin marketplace manifest
├── AGENTS.md                          # THIS FILE — read first
├── README.md                          # Public-facing docs
├── TEMPLATE.md                        # Template for catalog entries
├── catalog/                           # Skill reference cards (read-only docs)
│   ├── analysis/                      # Review/analysis skill cards
│   ├── coding/                        # Coding skill cards
│   ├── system/                        # Orchestration skill cards
│   └── writing/                       # Writing skill cards
├── pr-review/                         # Unified PR review orchestrator
├── pre-task-validator/                # Pre-implementation spec validator
├── post-task-validator/               # Post-implementation code validator
├── task-executor/                     # End-to-end task executor
├── deep-review/                       # Parallel code review (no PR context)
├── deep-doc-review/                   # Documentation review
├── coderabbit-review/                 # CodeRabbit CLI + TDD cycle
└── verify/                            # Automated verification (lint/test/build)
```

Each plugin follows the same layout:
```
<plugin>/
├── .factory-plugin/plugin.json        # Plugin manifest (name, description)
└── skills/optimus-<skill>/SKILL.md    # Full skill instructions with YAML frontmatter
```

## How Skills Work

A SKILL.md file is the complete instruction set for an agent. It contains:
- **YAML frontmatter**: name, description, trigger conditions, skip conditions, prerequisites, examples
- **Phases**: sequential steps the agent must follow
- **Rules**: constraints the agent must obey

When a user installs a plugin and invokes the skill, the SKILL.md content is injected
into the agent's context as instructions.

## Design Principles

### 1. User Authority Over Decisions
The agent NEVER decides whether a finding should be fixed or skipped. ALL findings
(CRITICAL, HIGH, MEDIUM, LOW) MUST be presented to the user for decision. The agent
recommends but the user decides.

### 2. No False Convergence
Convergence loops must use escalating scrutiny (5 rounds). Agents in re-validation
rounds should analyze from scratch — the orchestrator deduplicates, not the agent.
LOW severity is NOT a stop condition.

### 3. Atomic Thread Resolution
When replying to PR threads: reply → resolve → confirm per thread. Never batch
"all replies first, then all resolves".

### 4. Source-Aware Reply Methods
PR review threads from native GitHub Apps (deepsource-io, codacy-production) require
GraphQL for replies (REST returns 404). Workflow comments (github-actions[bot]) use REST.
Always classify threads by author login before replying.

### 5. CI Checks Are Findings
Any failing check shown by `gh pr checks` is a finding (HIGH severity). This includes
Codacy, DeepSource, Merge Gate — not just GitHub Actions workflows. The agent must not
rationalize these away.

## Editing Rules

### SKILL.md Files
- Preserve YAML frontmatter structure (---, name, description, trigger, skip_when, etc.)
- Keep phase numbering sequential (Phase 0, Phase 1, ...)
- Step numbering within phases: Step X.Y (e.g., Step 0.3, Step 8.2)
- Use `**HARD BLOCK:**` for steps the agent must never skip
- Use `**CRITICAL:**` for rules that override normal behavior
- Use `**IMPORTANT:**` for emphasis without hard blocking
- When adding anti-rationalization rules, list specific excuses the agent might use
- Include concrete command examples (bash blocks) — agents follow examples better than prose
- Always include example output showing what success/failure looks like

### marketplace.json
- Must list ALL plugins in the repo
- `source` paths are relative to repo root (e.g., `./pr-review`)
- Description should be concise (1-2 sentences)

### plugin.json
- Located at `<plugin>/.factory-plugin/plugin.json`
- Must match the marketplace.json entry

### README.md
- Keep the install instructions and skill table up to date
- Update when adding/removing plugins

## Plugin Lifecycle

### Adding a new plugin
1. Create directory: `<name>/skills/optimus-<name>/SKILL.md`
2. Create manifest: `<name>/.factory-plugin/plugin.json`
3. Add entry to `.factory-plugin/marketplace.json`
4. Update README.md table
5. Commit, push, then `droid plugin install <name>@optimus`

### Updating a plugin
1. Edit the SKILL.md
2. Commit, push
3. Run `droid plugin update <name>@optimus`

### Removing a plugin
1. Remove from marketplace.json
2. Remove directory
3. Update README.md
4. Commit, push
5. Run `droid plugin uninstall <name>@optimus`

## Project Rules Discovery (all skills)

Every skill that reviews, validates, or generates code MUST search for project rules
and AI instruction files before starting. The checklist (in priority order):

```
AGENTS.md                    # Primary agent instructions
CLAUDE.md                    # Claude-specific rules
DROIDS.md                    # Droid-specific rules
.cursorrules                 # Cursor-specific rules
PROJECT_RULES.md             # Coding standards (root or docs/)
docs/PROJECT_RULES.md
.editorconfig                # Editor formatting rules
docs/coding-standards.md     # Explicit coding conventions
docs/conventions.md
.github/CONTRIBUTING.md      # Contribution guidelines
CONTRIBUTING.md
.eslintrc*                   # Linter configs (implicit rules)
biome.json
.golangci.yml
.prettierrc*
```

If NONE exist, the agent must warn the user. If any are found, they become the
source of truth for coding standards and must be passed to every dispatched sub-agent.

## Common Patterns Across Skills

### Finding Presentation
All review/validation skills follow this pattern:
1. Collect findings from agents/tools
2. Consolidate and deduplicate
3. Present overview table with severity counts
4. Walk through findings one by one (AskUser for each decision)
5. Batch apply approved fixes
6. Present final summary

### Convergence Loop
Used by: post-task-validator, pre-task-validator, pr-review, coderabbit-review
- 5 rounds maximum (round 1 = initial analysis)
- Escalating scrutiny: standard → skeptical → adversarial → cross-cutting → final sweep
- Stop only when: zero new findings, round 5 reached, or user explicitly stops

### Agent Dispatch
Skills dispatch specialist droids in parallel via Task tool:
- Preferred: ring-default-* droids (code-reviewer, business-logic-reviewer, security-reviewer, etc.)
- Fallback: worker droid with domain-specific instructions

## Known Issues and Decisions

- `codacy:ignore` does NOT exist — use the underlying linter's syntax (biome-ignore, eslint-disable, //nolint)
- DeepSource `// skipcq: <shortcode>` is the inline suppression syntax
- Native app review threads (deepsource-io, codacy-production) cannot be replied to via REST API — use GraphQL `addPullRequestReviewThreadReply`
- Biome has a known bug with JSX comments for `biome-ignore` (#8980, #9469, #7473) — exclude test files from Codacy instead
