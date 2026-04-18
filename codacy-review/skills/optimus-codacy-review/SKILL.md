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

## Phase 3: Present Overview

Present a summary table to the user:

```markdown
## Codacy Review: PR #<number> — <total> issues analyzed

### Summary
| Category | Count | Action |
|----------|-------|--------|
| False Positive (misconfigured rules) | X | Recommend disabling rules |
| Genuine Finding | Y | Review one-by-one |
| Informational (low priority) | Z | Skip or defer |

### False Positives — Misconfigured Rules
| # | Pattern | Tool | Count | Reason |
|---|---------|------|-------|--------|
| 1 | es-x/no-arrow-functions | ESLint | 12 | ES5 rule, project uses ES2022+ |
| 2 | ... | ... | ... | ... |

### Genuine Findings
| # | Severity | File:Line | Pattern | Message |
|---|----------|-----------|---------|---------|
| 1 | High | file.go:42 | sql-injection | SQL concat detected |
| 2 | ... | ... | ... | ... |

### Informational
| # | Pattern | Tool | Count | Message |
|---|---------|------|-------|---------|
| 1 | jsx-no-bind | ESLint | 2 | Arrow function in JSX prop |
```

---

## Phase 4: Interactive Finding-by-Finding Resolution

Process only **Genuine Findings**, one at a time, in severity order (Error > High > Medium > Warning).

For each finding:

### Step 4.1: Read the Affected Code

Read the file and surrounding context (±10 lines around the flagged line) to understand the issue in context.

### Step 4.2: Present Analysis

```markdown
## Finding X of N — [SEVERITY] | <pattern>

**File:** <file>:<line>
**Tool:** <tool> | **Category:** <category>
**Message:** <message>

**Code:**
<code snippet with context>

**Analysis:**
<Explain whether the issue is real in this context, what the impact is, and what the fix would be>

**Recommendation:**
- Option A: <fix description>
- Option B: Skip (explain why it's acceptable)
```

### Step 4.3: Collect Decision

Use `AskUser` to get the user's decision. **BLOCKING** — do not advance until decided.

Record: finding ID, decision (fix/skip/defer), chosen option.

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

## Phase 6: Apply Fixes

For each approved genuine finding fix:

1. Read the full file
2. Apply the fix
3. Run lint to verify
4. Commit with descriptive message referencing the finding
5. Record the commit SHA

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

### Issues Analyzed: <total>
| Category | Count | Outcome |
|----------|-------|---------|
| False Positive | X | Rules disabled / .codacy.yml updated |
| Genuine — Fixed | Y | Commits applied |
| Genuine — Skipped | Z | User decision |
| Informational | W | Skipped |

### Fixes Applied
| # | File | Pattern | Commit |
|---|------|---------|--------|

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
