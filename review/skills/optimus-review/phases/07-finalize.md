# Phase 7: Finalize (Convergence, Re-run Guard, Integration, Summary, Push, PR)

Loaded by `SKILL.md` after fixes are applied. Covers convergence loop (rounds 2-5, opt-in), Re-run Guard, integration tests, validation summary, optional push, and optional PR creation. On completion, clears iTerm2 marker via `_optimus_clear_session() {
  [ "$LC_TERMINAL" = "iTerm2" ] || [ "$TERM_PROGRAM" = "iTerm.app" ] || return 0
  local pid="$PPID" target_tty=""
  for _ in 1 2 3 4; do
    [ -z "$pid" ] || [ "$pid" = "1" ] && break
    target_tty=$(ps -o tty= -p "$pid" 2>/dev/null | tr -d ' ')
    case "$target_tty" in
      ""|"?"|"??") pid=$(ps -o ppid= -p "$pid" 2>/dev/null | tr -d ' '); target_tty="" ;;
      *) break ;;
    esac
  done
  _optimus_emit_clear() {
    if [ -n "$target_tty" ] && [ -w "/dev/$target_tty" ]; then
      printf '%s' "$1" > "/dev/$target_tty" 2>/dev/null || printf '%s' "$1"
    else
      printf '%s' "$1"
    fi
  }
  _optimus_emit_clear "$(printf '\e]1337;SetBadgeFormat=\a')"
  _optimus_emit_clear "$(printf '\e]6;1;bg;*;default\a')"
}
_optimus_clear_session`.

Execute the opt-in convergence loop — see AGENTS.md "Common Patterns > Protocol: Convergence Loop (Full Roster Model — Opt-In, Gated)".

**Behavioral contract for THIS phase:**
- Round 1 already ran in Phase 3. THIS phase only handles rounds 2 through 5.
- Present the **entry gate** before round 2 (`Run round 2` / `Skip convergence loop`).
- Present the **per-round gate** before rounds 3, 4, 5 (`Continue` / `Stop here`).
- If a dispatched round produces ZERO new findings, declare convergence and exit
  silently — DO NOT ask the user whether to run another round.
- Record the final loop status (`CONVERGED` / `USER_STOPPED` / `SKIPPED` /
  `HARD_LIMIT` / `DISPATCH_FAILED_ABORTED`) for the Final Summary.

**Stage-specific scope for convergence rounds 2+:**
Dispatch the **same agent roster** from Phase 3 (all agents from the Agent Roster table).
Each agent receives the SAME compact context as round 1: the Doc Brief
(`.optimus/sessions/T-XXX/doc-brief.md`), changed file paths, and the round-1 findings
ledger. Do NOT instruct agents to "re-read fresh from disk" — that defeats the brief's
caching purpose. Agents may consult full pre-dev docs only if a finding requires verbatim
reference. The orchestrator handles dedup using strict matching (same file + same line
range ±5 + same category).

Include the same items from the Phase 3 prompt (both the Verification scope block and the Cross-cutting analysis 5 items).

**Failure handling:** If a fresh sub-agent dispatch fails (Task tool error, ring droid
unavailable), do NOT count as zero findings. Ask the user via `AskUser` whether to
retry the round or stop (status `DISPATCH_FAILED_ABORTED` if user stops).

When the loop exits (any status), proceed to Phase 9 (Re-run Guard).

---

### Phase 9: Re-run Guard

### Step 9.1: Evaluate Re-run or Advance

Execute re-run guard — see AGENTS.md Protocol: Re-run Guard.

- If the user chooses **Re-run with clean context**: go back to Step 1.1 (Discover Project
  Structure). Skip all prior setup steps (GitHub CLI check, optimus-tasks.md validation, workspace
  resolution, task identification, session state, status validation, divergence check).
  Increment stage stats before re-starting analysis. Apply the **Re-run reset semantics**: reset `convergence_status` to `null`; reset `phase` to the first re-executed phase; overwrite `started_at`; preserve `task_id`, `task_branch`, `created_at`. See AGENTS.md Protocol: Re-run Guard.
- If the user chooses **Advance** (or 0 findings): proceed to Phase 10 (integration tests).

---

### Phase 10: Integration Tests (before push)

**After the convergence loop exits**, run integration tests. These are slow and
expensive, so they run ONCE at the end — not during the fix/convergence cycle.

If Step 7.4 measured integration coverage via `make test-integration-coverage`,
integration tests already ran — skip this phase (no-op).
Otherwise (coverage target missing, marked SKIP in Step 7.4), run quietly — see
AGENTS.md Protocol: Quiet Command Execution:

```bash
_optimus_quiet_run "make-test-integration" make test-integration   # Optional fallback — SKIP if missing
```

| Test Type | Command | If target exists | If missing |
|-----------|---------|-----------------|------------|
| Integration | `_optimus_quiet_run "make-test-integration" make test-integration` | **HARD BLOCK** if fails | SKIP |

**If integration tests fail:**
1. `_optimus_quiet_run` already printed the last 50 lines plus the log path —
   review them in place.
2. Ask via `AskUser`: "Integration tests are failing. What should I do?"
   - Fix the issue (dispatch ring droid)
   - Skip and proceed to summary (user will handle later)

**If all pass (or targets don't exist):** proceed to the Validation Summary.

---

### Phase 11: Validation Summary

```markdown
### Post-Task Validation Summary: T-XXX

### Verdict: APPROVED / APPROVED WITH CAVEATS / NEEDS REWORK

### Convergence
- Rounds dispatched (round 1 + convergence rounds): X
- Status: CONVERGED | USER_STOPPED | SKIPPED | HARD_LIMIT | DISPATCH_FAILED_ABORTED

### Agent Results
| Agent | Verdict | Issues Found | Fixed | Skipped |
|-------|---------|-------------|-------|---------|
| Code Quality | PASS | 3 | 2 | 1 |
| Business Logic | PASS | 1 | 1 | 0 |
| Security | PASS | 0 | 0 | 0 |
| QA Analyst | PASS | 4 | 3 | 1 |

### Spec Compliance: X/Y acceptance criteria PASS
| Criterion | Status | Notes |
|-----------|--------|-------|
| AC-1 | PASS | |
| AC-2 | PASS | |

### Test Coverage: X/Y test IDs implemented
| Test ID | Status | File |
|---------|--------|------|
| U1 | PASS | ... |
| E1 | PASS | ... |

### Fixed (X findings)
| # | Finding | Agent(s) | Solution Applied |
|---|---------|----------|-----------------|
| F1 | ... | Security | Option A: ... |

### Skipped (X findings)
| # | Finding | Agent(s) | Reason |
|---|---------|----------|--------|
| F5 | ... | QA | User decision: out of scope |

### Verification
- Lint: PASS
- Unit tests: PASS (X tests)
- Integration tests: PASS / SKIPPED (Phase 10)

### Test Coverage
- Unit tests: XX.X% (threshold: 85%) — PASS / FAIL
- Integration tests: XX.X% (threshold: 70%) — PASS / FAIL / SKIP
- Untested functions: X (Y business logic, Z infrastructure)
```

---

### Phase 12: Push Commits (optional)
Offer to push commits — see AGENTS.md Protocol: Push Commits.

---

### Phase 13: Offer PR Creation

After the validation summary is presented and the verdict is APPROVED or APPROVED WITH CAVEATS,
offer to create a PR for the task.

### Step 13.1: Check if PR Already Exists

```bash
gh pr list --head "$(git branch --show-current)" --json number,state,url --jq '.[]'
```

- **If PR already exists (any state):** skip PR creation — inform the user: "PR #X already exists: <url>"
- **If no PR exists:** proceed to Step 13.2

### Step 13.2: Generate PR Title (Conventional Commits)

Derive the PR title from the task's **Tipo** column and title:

1. Read the Tipo for the task and map to the conventional commit prefix:
   - Feature→`feat`, Fix→`fix`, Refactor→`refactor`, Chore→`chore`, Docs→`docs`, Test→`test`
2. Use the task ID as scope
3. Use the task title as description (lowercase, imperative)

**Format:** `<type>(T-XXX): <description>`

**Example:** Task T-003 "User registration API" with Tipo "Feature" → `feat(T-003): add user registration API`

### Step 13.3: Offer to Create

Ask via `AskUser`:
```
Validation complete. Would you like to create a PR?
  Title: <generated title>
  Base: <default branch>
  Head: <current branch>
```
Options:
- **Create PR with this title**
- **Create PR with a different title** (user provides)
- **Skip** — I'll create it manually

If the user chooses to create:
```bash
gh pr create --title "<title>" --body "<auto-generated body>" --base "$DEFAULT_BRANCH" --assignee @me
```

The `--assignee @me` flag assigns the PR to the authenticated GitHub user automatically.

The body should include:
- Task ID and title
- Objective (from Ring source via `TaskSpec` column)
- Link to the task section in optimus-tasks.md

### Step 13.4: Confirm

If created, show: "PR #N created: <url> (assigned to you)"

**NOTE:** PR creation is optional — the user may prefer to create it manually with additional
context. The agent NEVER creates a PR without explicit user approval.

---
