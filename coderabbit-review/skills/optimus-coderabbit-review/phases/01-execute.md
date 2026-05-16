# Phase 1: Execute CodeRabbit

Loaded by SKILL.md first. Discover CodeRabbit config, run the CLI against the base branch, parse JSON output into a structured findings list.

### Step 1.1: Discover Configuration

1. **Find config file:** Look for `.coderabbit.yaml` in the project root
2. **Determine base branch:** Default to `origin/main`, or use user-specified branch
3. **Verify CLI:** Confirm `coderabbit` command is available

### Step 1.2: Run CodeRabbit

Check if the CodeRabbit CLI is available:

```bash
which coderabbit 2>/dev/null || which coderabbit-cli 2>/dev/null
```

**If CodeRabbit CLI is available:** Execute the CLI:

```bash
coderabbit review --prompt-only --base <base-branch> --plain --config <config-file>
```

Capture the full output for parsing.

**If CodeRabbit CLI is NOT available:** Inform the user and offer a fallback:

```
CodeRabbit CLI is not installed. To install it:
  npm install -g coderabbit

Alternatively, I can run a code review using specialist agents instead (same as /optimus-deep-review).
```

Ask via `AskUser`:
- **Install CodeRabbit** — show installation instructions and retry
- **Fall back to agent review** — proceed with a deep-review style agent dispatch (skip Phase 2 parsing, go directly to Phase 3 interactive resolution with parallel agent findings)
- **Cancel** — stop the review

If the user chooses the fallback, dispatch the same agents used by `optimus-deep-review`
(code quality, business logic, security, test quality, cross-file consistency) and follow
the same interactive resolution flow from Phase 3 onward.

### Step 1.3: Load Project Context

1. **Identify stack:** Check for `go.mod`, `package.json`, `Makefile`, `Cargo.toml`, etc.
2. **Verify Makefile targets (HARD BLOCK):** The project MUST have a `Makefile` with `lint` and `test` targets. If either is missing, **STOP**: "Project is missing required Makefile targets (`make lint`, `make test`). Add them before running coderabbit-review."
3. **Identify project rules and AI instructions (MANDATORY):** Execute project rules discovery — see AGENTS.md Protocol: Project Rules Discovery.
4. **Initialize .optimus directory (HARD BLOCK):** Execute Protocol: Initialize .optimus Directory — see AGENTS.md Protocol: Initialize .optimus Directory. This guarantees `.optimus/logs/` exists AND is gitignored before any `_optimus_quiet_run` call creates log files.

---
