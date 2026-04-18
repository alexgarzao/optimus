# Codacy Review

Fetches Codacy PR issues via API, categorizes them, identifies false positives from misconfigured rules, evaluates genuine findings against the code, and presents results interactively with recommended actions.

---

## Phase 0: Obtain PR and Codacy Context

### Step 0.1: Identify PR

If no PR number was provided, detect from the current branch:

```bash
gh pr view --json number,url,headRefName --jq '.number' 2>/dev/null
```

If no PR is found, ask the user with `AskUser`.

### Step 0.2: Obtain Codacy API Token

The skill needs a Codacy API token. Check for it in this order:

1. Environment variable `CODACY_API_TOKEN`
2. Ask the user with `AskUser`:
   ```
   Codacy API token is needed to fetch PR issues. You can generate one at:
   app.codacy.com > Account > Access Management > API tokens
   ```

Store the token for use in subsequent API calls.

### Step 0.3: Identify Repository

Extract the GitHub owner and repository name:

```bash
gh repo view --json owner,name --jq '"\(.owner.login)/\(.name)"'
```

Store as `OWNER` and `REPO`.

---

## Phase 1: Fetch Codacy PR Issues

### Step 1.1: Fetch Issues via API

Use the Codacy API v3 to fetch all issues for the PR. Paginate if needed (cursor-based).

```bash
curl -s -H "api-token: ${CODACY_API_TOKEN}" \
  "https://app.codacy.com/api/v3/analysis/organizations/gh/${OWNER}/repositories/${REPO}/pull-requests/${PR_NUMBER}/issues?limit=100"
```

If the response includes a `pagination.cursor`, fetch the next page:

```bash
curl -s -H "api-token: ${CODACY_API_TOKEN}" \
  "https://app.codacy.com/api/v3/analysis/organizations/gh/${OWNER}/repositories/${REPO}/pull-requests/${PR_NUMBER}/issues?limit=100&cursor=${CURSOR}"
```

Repeat until no cursor is returned.

### Step 1.2: Parse and Group Issues

For each issue, extract:
- `filePath` — affected file
- `lineNumber` — line in the file
- `message` — issue description
- `patternInfo.id` — rule identifier (e.g., `ESLint8_es-x_no-arrow-functions`)
- `patternInfo.category` — category (ErrorProne, Compatibility, Performance, Security, BestPractice)
- `patternInfo.level` — severity (High, Medium, Warning, Error)
- `toolInfo.name` — tool that found it (ESLint, Biome, Opengrep, etc.)
- `deltaType` — Added or Fixed

**Only process issues with `deltaType: "Added"`** (new issues introduced by the PR).

Group issues by `patternInfo.id` to identify patterns:

```
Pattern: ESLint8_es-x_no-arrow-functions
  Tool: ESLint | Category: Compatibility | Level: High
  Count: 12 | Files: [file1.ts, file2.ts]
  Message: "ES2015 arrow function expressions are forbidden."
```

---

## Phase 2: Classify Issues

For each unique pattern, classify it into one of these categories:

### Category 1: False Positive — Misconfigured Rule

Rules that are technically correct but irrelevant for the project's stack. Common indicators:

| Indicator | Examples |
|-----------|----------|
| ES5 compatibility rules in a modern JS/TS project | `es-x/no-arrow-functions`, `es-x/no-destructuring`, `es-x/no-modules`, `es-x/no-template-literals`, `es-x/no-async-functions`, `es-x/no-block-scoped-variables`, `es-x/no-default-parameters` |
| Framework-specific rules for wrong framework | `@lwc/*` (Lightning Web Components) in a React project, `flowtype/*` in a TypeScript project |
| Functional programming rules in imperative code | `fp/no-nil`, `fp/no-mutation` |
| Monorepo false positives | `noUndeclaredDependencies` when package.json is in a subdirectory |
| React-specific props in React project | `noReactSpecificProps` flagging `className` |
| Credential detection on field names | `hashicorp-tf-password` on form field names like "password-input" |
| Import resolution failures | `import/no-unresolved`, `n/no-missing-import` on path aliases (`@/lib/utils`) |

**To classify:** Read the project's `package.json`, `tsconfig.json`, or equivalent to determine the actual stack. Compare against the rule's purpose. If the rule assumes a different stack/era, it's a false positive.

### Category 2: Genuine Finding — Worth Reviewing

Issues that identify real problems relevant to the project:

| Type | Examples |
|------|----------|
| Security | SQL injection, hardcoded credentials (real ones, not field names) |
| Performance | Unnecessary re-renders, missing memoization (in hot paths) |
| Correctness | Type errors, null safety, logic errors |
| Best practice | Missing error handling, unsafe patterns |

### Category 3: Informational — Low Priority

Issues that are technically valid but have negligible impact:

| Type | Examples |
|------|----------|
| Style preferences | `jsx-no-bind` on simple event handlers, namespace imports |
| Minor optimizations | Tree-shaking concerns on small components |
| Complexity metrics | High complexity in third-party code or node_modules |

---

## Phase 2.5: Agent Validation of Genuine Findings

After classification, dispatch specialist agents in parallel to validate or contest the genuine findings. This prevents blindly accepting Codacy's assessment — agents read the actual code and determine if each finding is real, a false positive in context, or misclassified in severity.

### Step 2.5.1: Load Project Context

1. **Identify stack:** Check for `go.mod`, `package.json`, `Makefile`, `Cargo.toml`, etc.
2. **Identify test commands:** Look in `Makefile`, `package.json` scripts, or CI config for lint, unit test, integration test, and E2E test commands
3. **Identify coding standards:** Look for `PROJECT_RULES.md`, linter configs, or equivalent

Store discovered commands:
```
LINT_CMD=<discovered lint command>
TEST_UNIT_CMD=<discovered unit test command>
TEST_INTEGRATION_CMD=<discovered integration test command>
```

### Step 2.5.2: Read Changed Files

Read the full content of every file that has at least one genuine finding. Agents need full file context, not just the flagged line.

### Step 2.5.3: Dispatch Agents

Dispatch ALL applicable agents simultaneously via `Task` tool. Each agent receives the full content of every affected file plus ALL genuine findings from Phase 2.

**Agent selection priority:**

1. **Ring review droids (preferred when available):**
   - `ring-default-code-reviewer` → Code quality, architecture, patterns
   - `ring-default-business-logic-reviewer` → Domain correctness, edge cases
   - `ring-default-security-reviewer` → Vulnerabilities, OWASP, input validation
   - `ring-default-ring-test-reviewer` → Test coverage gaps, test quality
   - `ring-default-ring-nil-safety-reviewer` → Nil/null pointer risks, unsafe dereferences
   - `ring-default-ring-consequences-reviewer` → Ripple effects beyond changed files
   - `ring-default-ring-dead-code-reviewer` → Orphaned code from changes
2. **Other available specialist droids**
3. **Worker droid with domain instructions** — as fallback

| Domain | When to Dispatch | Preferred Ring Droid |
|--------|-----------------|---------------------|
| **Code Quality** | Always | `ring-default-code-reviewer` |
| **Business Logic** | Always | `ring-default-business-logic-reviewer` |
| **Security** | Always | `ring-default-security-reviewer` |
| **Test Quality** | Always | `ring-default-ring-test-reviewer` |
| **Nil/Null Safety** | Always (if droid available) | `ring-default-ring-nil-safety-reviewer` |
| **Ripple Effects** | Always (if droid available) | `ring-default-ring-consequences-reviewer` |
| **Dead Code** | Always (if droid available) | `ring-default-ring-dead-code-reviewer` |

**Agent prompt MUST include:**

```
Goal: Validate Codacy findings for PR #<number>

Codacy Genuine Findings to evaluate:
[paste all genuine findings with file, line, pattern, message]

Changed files (full content):
[paste full content of each affected file]

Coding standards: [paste relevant sections]

Your job:
  1. For EACH Codacy finding, read the actual code in context and determine:
     - AGREE: The finding is valid and should be fixed
     - CONTEST: The finding is incorrect or irrelevant in context (explain why)
     - RECLASSIFY: The finding is valid but the severity is wrong (state correct severity)
  2. Report NEW findings not covered by Codacy — issues in the same files
     that Codacy missed but are relevant to your domain

Required output format:
  ## Codacy Finding Evaluation
  For each finding:
  - Finding: <pattern> at <file>:<line>
  - Verdict: AGREE / CONTEST / RECLASSIFY
  - Justification: <why>
  - Corrected severity (if RECLASSIFY): <new severity>

  ## New Findings (not from Codacy)
  For each:
  - Severity: CRITICAL / HIGH / MEDIUM / LOW
  - File and line
  - Problem and recommendation
```

### Step 2.5.4: Merge Agent Results

After all agents return:
1. **Update genuine findings** with agent verdicts — if agents contest a finding, move it to "Contested by agents" category
2. **Reclassify** findings where agents disagree with Codacy's severity
3. **Add new findings** discovered by agents (not from Codacy) to the genuine findings list
4. **Deduplicate** if multiple agents flag the same new issue
5. **Sort** all genuine findings by severity: CRITICAL > HIGH > MEDIUM > LOW

---

## Phase 3: Present Overview

Present a summary table to the user:

```markdown
## Codacy Review: PR #<number> — <total> issues analyzed

### Summary
| Category | Count | Action |
|----------|-------|--------|
| False Positive (misconfigured rules) | X | Recommend disabling rules |
| Genuine Finding (Codacy + agents agree) | Y | Review one-by-one |
| Contested by agents | Z | Review — agents disagree with Codacy |
| New findings (agents only) | W | Review one-by-one |
| Informational (low priority) | V | Skip or defer |

### False Positives — Misconfigured Rules
| # | Pattern | Tool | Count | Reason |
|---|---------|------|-------|--------|
| 1 | es-x/no-arrow-functions | ESLint | 12 | ES5 rule, project uses ES2022+ |

### Genuine Findings (validated by agents)
| # | Severity | File:Line | Pattern | Source | Validating Agent(s) |
|---|----------|-----------|---------|--------|---------------------|
| 1 | High | file.go:42 | sql-injection | Codacy + Agent | Security |

### Contested Findings (agents disagree)
| # | Codacy Says | Agent Says | File:Line | Pattern | Contesting Agent |
|---|-------------|------------|-----------|---------|-----------------|
| 1 | High | Not an issue | ... | ... | Business Logic |

### New Findings (from agents, not Codacy)
| # | Severity | File:Line | Summary | Agent(s) |
|---|----------|-----------|---------|----------|
| 1 | HIGH | ... | ... | Nil Safety |

### Agent Verdicts
| Agent | Issues Evaluated | Agree | Contest | Reclassify | New Findings |
|-------|-----------------|-------|---------|------------|--------------|

### Informational
| # | Pattern | Tool | Count | Message |
|---|---------|------|-------|---------|
| 1 | jsx-no-bind | ESLint | 2 | Arrow function in JSX prop |
```

---

## Phase 4: Interactive Finding-by-Finding Resolution

Process **Genuine Findings**, **Contested Findings**, and **New Agent Findings**, one at a time, in severity order (CRITICAL > HIGH > MEDIUM > LOW).

For each finding:

### Step 4.1: Read the Affected Code

Read the file and surrounding context (±10 lines around the flagged line) to understand the issue in context.

### Step 4.2: Present Analysis

```markdown
## Finding X of N — [SEVERITY] | <pattern>

**File:** <file>:<line>
**Source:** <Codacy | Codacy + Agent(s) | Agent only | Contested: Codacy vs Agent>
**Tool:** <tool> | **Category:** <category>
**Message:** <message>

**Code:**
<code snippet with context>
```

### Step 4.3: Impact Analysis (four lenses)

Evaluate the finding through all four perspectives to help the user make an informed decision:

- **User (UX):** How does this affect the end user? Usability degradation, confusion, broken workflow, accessibility issue? Would the user notice? Would it block their work?
- **Task focus:** Does this finding relate to the changes in this PR? Is it within scope, or a tangential concern that should be a separate effort?
- **Project focus:** Is this MVP-critical, or gold-plating? Does ignoring it now create rework later? Does it conflict with the project's priorities?
- **Engineering quality:** Does this hurt maintainability, testability, reliability, or codebase consistency? What is the technical debt cost of skipping it?

For contested findings, present both Codacy's assessment and the agent's contestation with justification.

### Step 4.4: Proposed Solutions (2-3 options)

For each option, evaluate all four lenses:

```
**Option A: [name]**
[What to do — concrete steps, files to change]
- UX: [impact on the end user's experience]
- Task focus: [within scope / tangential]
- Project focus: [MVP-aligned / nice-to-have / out-of-scope]
- Engineering: [pros and cons — complexity, maintainability, test coverage, consistency]
- Effort: [trivial (< 5 min) / small (5-15 min) / moderate (15-60 min) / large (> 1h)]
```

For straightforward fixes with no ambiguity, state: "Direct fix, no tradeoffs."

### Step 4.5: Collect Decision

Use `AskUser` to get the user's decision. **BLOCKING** — do not advance until decided.

Record: finding ID, source(s), decision (fix/skip/defer), chosen option.

---

## Phase 5: Recommend Rule Configuration

After reviewing all findings, present recommendations for Codacy configuration:

### Step 5.1: Rules to Disable

For all false-positive patterns, generate the API calls or UI steps to disable them:

```markdown
### Recommended Rule Changes

**Via Codacy API** (if no coding standard conflict):
| # | Tool | Pattern | Action | API Call |
|---|------|---------|--------|---------|

**Via Codacy UI** (if coding standard blocks API):
1. Go to app.codacy.com > Repository > Code Patterns
2. Find tool: <tool>
3. Disable pattern: <pattern>

**Via .codacy.yml** (exclude paths):
Add to .codacy.yml:
  engines:
    <tool>:
      exclude_paths:
        - "<path>"
```

### Step 5.2: Apply Configuration Changes

Ask the user whether to apply the recommended changes:

```
Apply recommended Codacy configuration changes?
- Apply all via API (where possible)
- Apply only .codacy.yml changes
- Skip (I'll do it manually)
```

If approved, execute the API calls and/or edit `.codacy.yml`.

---

## Phase 6: Apply Fixes with TDD Cycle

For each approved fix (skipped for ignored/deferred findings):

### Step 6.1: TDD Cycle (mandatory)

For each approved fix:

1. **RED:** Write a failing test that exposes the problem (if one doesn't already exist for the scenario)
2. **GREEN:** Implement the minimal fix to make the test pass
3. **REFACTOR:** Improve if necessary without changing behavior
4. **RUN ALL TESTS:** Execute unit + integration tests using discovered commands

### Step 6.2: Handle Test Failures

If tests fail after implementing the fix (maximum 3 attempts):

1. **Classify the failure:**
   - **Logic bug** → Return to RED phase, adjust test/fix
   - **Flaky/environmental test** → Re-execute at least 3 times to confirm flakiness. Maximum 1 test skipped per fix. Document justification and tag with "pending-test-fix"
   - **Unavailable external dependency** → Pause and wait for restoration

2. **Do NOT proceed** to the next fix until all tests pass or the failure is classified and documented

### Step 6.3: Commit Each Fix

After each successful TDD cycle:

1. Run lint to verify formatting
2. Stage ONLY the files changed by this fix
3. Commit with descriptive message referencing the finding:
   ```bash
   git commit -m "fix: <concise description>

   Addresses Codacy finding: <pattern> at <file>:<line>"
   ```
4. Record the commit SHA for this fix

### Step 6.4: Batching Independent Fixes

For PRs with many findings, independent fixes (in different modules/files) may be grouped in a single TDD cycle, as long as all tests pass before proceeding to the next group.

---

## Phase 6.5: Coverage Verification and Test Gap Analysis

After all fixes have been applied through the TDD cycle:

### Step 6.5.1: Coverage Measurement

Measure test coverage for the changed files:

**Unit test coverage:**
```bash
go test -coverprofile=coverage-unit.out ./...
go tool cover -func=coverage-unit.out | tail -1
```

**Integration test coverage (if applicable):**
```bash
go test -tags=integration -coverprofile=coverage-integration.out ./...
go tool cover -func=coverage-integration.out | tail -1
```

**Untested functions:**
```bash
go tool cover -func=coverage-unit.out | grep "0.0%"
```

**Thresholds:**
- Unit tests: 85% minimum
- Integration tests: 70% minimum

If coverage is below threshold, flag as a finding:
- **HIGH** severity for unit test coverage below 85%
- **MEDIUM** severity for integration test coverage below 70%
- List untested business-logic functions as individual **HIGH** findings

**E2E tests:** If not configured, ask the user using `AskUser`:
"E2E tests are not configured. Should they be implemented, or skip for now?"

### Step 6.5.2: Test Scenario Gap Analysis

Dispatch an agent to identify missing test scenarios in the changed files.

**Dispatch a test gap analyzer** via `Task` tool. Use `ring-default-ring-test-reviewer`, `ring-dev-team-qa-analyst`, or `worker` (in that priority order).

The agent receives:
1. **Changed source files** — full content (non-test files only)
2. **Test files for changed source** — full content
3. **Coverage profile** — `go tool cover -func` output

```
Goal: Identify missing test scenarios in files changed during this review.

Context:
  - Source files changed: [full content]
  - Test files: [full content]
  - Coverage profile: [go tool cover -func output]

Your job:
  For each public function changed/added:
  1. Unit tests: check for happy path, error paths, edge cases, validation failures
  2. Integration tests: check for DB failure, timeout, retry, rollback scenarios
  3. Report what EXISTS and what is MISSING

Required output format:
  ## Unit Test Gaps
  | # | File | Function | Existing Scenarios | Missing Scenarios | Priority |
  |---|------|----------|--------------------|-------------------|----------|

  ## Integration Test Gaps
  | # | File | Function | Existing Scenarios | Missing Scenarios | Priority |
  |---|------|----------|--------------------|-------------------|----------|

  ## Summary
  - Functions analyzed: X
  - Fully covered: X | Partial: X | No tests: X
  - Missing scenarios: X HIGH, Y MEDIUM, Z LOW
```

**HIGH priority gaps** are presented as findings for user decision (fix now or defer).

---

## Phase 6.6: Convergence Loop (MANDATORY — automatic re-validation with escalating scrutiny)

After Phase 6.5 completes, the reviewer MUST automatically re-validate the updated code. This catches new issues introduced by the fixes just applied.

**CRITICAL — Escalating Scrutiny Per Round:**

The primary failure mode of convergence loops is that re-running the same analysis with the same depth produces the same results (minus already-seen findings), leading to false convergence. To prevent this, EACH round MUST escalate its level of scrutiny:

| Round | Scrutiny Level | Focus |
|-------|---------------|-------|
| **1** (initial) | Standard analysis | Normal Codacy + agent validation |
| **2** | Skeptical re-read | For each domain, ask: "What did I accept as correct in round 1 that I should question?" Re-read code function-by-function, branch-by-branch instead of scanning |
| **3** | Adversarial analysis | Actively try to break the code: invent edge cases, check nil/empty/zero inputs, concurrent requests, external service failures |
| **4** | Cross-cutting deep dive | Focus on interactions BETWEEN domains: does test coverage exercise security-sensitive paths? Do fixes from previous rounds introduce new consistency issues? |
| **5** | Final sweep | Review ALL previously skipped/deferred findings with fresh eyes — should any be reconsidered? Check cumulative changes for internal consistency |

**Re-run Codacy and re-dispatch agents with escalated prompts:**

```
This is re-validation round X of 5. In previous rounds, the following findings
were already identified and resolved:
[list of previous findings with resolutions]

Your job NOW is to look DEEPER — not repeat what was already found.
Specifically:
- Question assumptions: what did round 1 accept that might be wrong?
- Check interactions: do the fixes from previous rounds create new issues?
- Look for subtle issues: off-by-one errors, race conditions, missing error
  propagation, implicit type coercions, nil dereferences in rare paths
- Examine what was NOT flagged: absence of validation, missing constraints,
  undocumented behavior, untested error paths

Do NOT report findings that match any previously identified finding.
Only report genuinely NEW issues.
```

**Loop rules:**
- **Maximum rounds:** 5 (the initial run counts as round 1)
- **Progress indicator:** Show `"=== Re-validation round X of 5 (scrutiny: <level>) ==="` at the start of each re-run
- **Scope:** Re-run Codacy CLI, re-dispatch agents with escalated prompts, re-measure coverage. Do NOT re-load project context (Phase 0)
- **Finding deduplication:** Maintain a ledger of ALL findings from ALL previous rounds. Only present findings that are NEW — not already seen, resolved, or skipped. If a finding was skipped/discarded by the user in a prior round, do NOT re-present it
- **If new findings exist:** Present via Phase 4 (interactive resolution), fix via Phase 6 (TDD cycle), verify via Phase 6.5 (coverage), then loop again
- **Stop conditions (any one triggers exit):**
  1. Zero new findings in the current round (after escalated scrutiny — this is genuine convergence)
  2. Only LOW severity findings remain (ask user: "Only LOW findings remain. Stop validation?")
  3. Round 5 completed (hard limit)
  4. User explicitly requests to stop (via AskUser response)

**Round summary (show after each round):**

```markdown
### Round X of 5 (scrutiny: <level>) — Summary
- New findings this round: N (C critical, H high, M medium, L low)
- Cumulative: X total findings across Y rounds
- Fixed: A | Skipped: B | Deferred: C
- Status: CONVERGED / CONTINUING / HARD LIMIT REACHED
```

**When the loop exits**, proceed to Phase 7.

---

## Phase 7: Trigger Reanalysis

After all changes are committed and pushed, trigger Codacy reanalysis:

```bash
curl -s -X POST -H "api-token: ${CODACY_API_TOKEN}" \
  -H "Content-Type: application/json" \
  "https://app.codacy.com/api/v3/organizations/gh/${OWNER}/repositories/${REPO}/reanalyzeCommit" \
  -d "{\"commitUuid\": \"${HEAD_SHA}\"}"
```

---

## Phase 8: Final Summary

```markdown
## Codacy Review Summary: PR #<number>

### Convergence
- Rounds executed: X of 5
- Status: CONVERGED / HARD LIMIT REACHED

### Issues Analyzed: <total>
| Category | Count | Outcome |
|----------|-------|---------|
| False Positive (misconfigured rules) | X | Rules disabled / .codacy.yml updated |
| Genuine — Fixed (Codacy + agents agree) | Y | Commits applied |
| Genuine — Skipped | Z | User decision |
| Contested by agents — Fixed | W | Commits applied |
| Contested by agents — Skipped | V | User decision |
| New findings (agents only) — Fixed | U | Commits applied |
| Informational | T | Skipped |

### Agent Verdicts
| Agent | Issues Evaluated | Agree | Contest | Reclassify | New Findings |
|-------|-----------------|-------|---------|------------|--------------|

### Fixes Applied
| # | File | Pattern | Source | Commit | Round |
|---|------|---------|--------|--------|-------|

### Test Coverage
- Unit tests: XX.X% (threshold: 85%) — PASS / FAIL
- Integration tests: XX.X% (threshold: 70%) — PASS / FAIL
- Untested functions: X (Y business logic, Z infrastructure)
- E2E tests: Configured / Not configured

### Test Results
- Unit tests: PASS (X tests)
- Integration tests: PASS / SKIPPED
- E2E tests: PASS / SKIPPED
- Skipped tests: X (with justification)

### Configuration Changes
| # | Tool | Change | Method |
|---|------|--------|--------|

### Reanalysis
- Status: Triggered / Skipped
```

---

## Phase 9: Codacy CLI Local Analysis (Optional)

If the user requests local analysis or wants to verify before pushing:

### Step 9.1: Check CLI Installation

```bash
codacy-cli --version 2>/dev/null || codacy-cli-v2 --version 2>/dev/null
```

If not installed, suggest:
```bash
brew install codacy/homebrew-codacy-cli-v2/codacy-cli-v2
```

### Step 9.2: Initialize and Run

```bash
codacy-cli init --provider gh --organization ${OWNER} --repository ${REPO} --api-token ${CODACY_API_TOKEN}
codacy-cli install
codacy-cli analyze
```

### Step 9.3: Compare Results

Compare CLI results against the API results to identify any discrepancies.

---

## Rules

- Always fetch ALL pages of issues (handle pagination cursor)
- Only process `deltaType: "Added"` issues (new issues, not fixed ones)
- Read the project's stack files (package.json, tsconfig.json, go.mod) before classifying rules
- Never blindly accept Codacy's severity — validate against actual code context
- Present false positives separately from genuine findings
- Always recommend configuration fixes for false positives (don't just skip them)
- One finding at a time for genuine issues, severity order
- No changes without user approval
- Record commit SHAs for all fixes
- Trigger reanalysis after applying changes
- If API token is provided, warn user to revoke it after the session (security)
- If `gh` CLI is not available, inform user and suggest installation
