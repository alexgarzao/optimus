# Phase 6: Respond to Every Comment + Final Summary

Loaded by `SKILL.md` after push. Reply to every Codacy/DeepSource/CodeRabbit/human comment thread with commit SHA (fix applied) or concrete won't-fix reason. Inline suppression tags for Codacy/DeepSource. Final readiness verdict. On completion, clear iTerm2 marker.

### Phase 13: Respond to ALL PR Comments

This phase has THREE sub-flows with independent mode gates:

| Sub-flow | Runs when | Purpose |
|---|---|---|
| **Step 13.0 — Outdated thread cleanup** | `REVIEW_MODE` ∈ {`findings`, `diff`} | Auto-reply + resolve every thread in `outdated_threads` (collected at Step 1.3.1). Pure hygiene — independent of agent verdicts. Required for CodeRabbit / approval-gate compliance, which withhold approval while ANY thread (including outdated ones) is unresolved. |
| **Steps 13.1-13.4 + 13.6 — Verdict-driven replies + summary** | `REVIEW_MODE = findings` only | Reply per agent verdict (AGREE / CONTEST / ALREADY-FIXED) on `active_threads`, then resolve. Step 13.6 renders the per-thread reply summary. Skipped in diff mode because agents performed a fresh review and never produced verdicts on existing comments. |
| **Step 13.5 — Hide fully-resolved reviews** | `REVIEW_MODE` ∈ {`findings`, `diff`} | Minimize bot-authored review summaries (CodeRabbit, DeepSource, Codacy, etc.) whose threads are all resolved AND contain only bot-authored content. Hygiene — independent of verdicts. Runs after thread mutations are complete (after 13.4 in `findings` mode, after 13.0 in `diff` mode). |

**Mode behavior at a glance:**
- `findings` → Step 13.0 → Steps 13.1-13.4 → Step 13.5 → Step 13.6 renders.
- `diff` → Step 13.0 → Step 13.2 (refresh thread map only) → Step 13.5. Steps 13.1, 13.3, 13.4, 13.6 active-threads table are SKIPPED. Phase 14 renders a warning that existing active comments remain unaddressed.
- `none` → user already exited at Step 1.8; Phase 13 is unreachable.

**HARD BLOCK (when running):** Every thread in scope MUST receive a reply AND be resolved. Phase 14 verifies zero unresolved threads remain.

<a id="step-cleanup-outdated-threads"></a>
### Step 13.0: Auto-resolve outdated threads (runs in `findings` and `diff` modes)

For EACH thread in `outdated_threads` collected at Step 1.3.1 where `is_resolved` is `false` (skip already-resolved ones):

1. **Reply** with this exact body (use the source's reply method from the thread's `reply_method` field; see Cases A and B below for the API choice):

   ```
   Outdated — this thread references code that was modified in subsequent commits and is no longer relevant to the current diff. Auto-resolved by /optimus-pr-check.
   ```

2. **Resolve** via GraphQL `resolveReviewThread` mutation (always GraphQL for resolve, regardless of source).

3. **Confirm** `isResolved: true` in the response.

4. **Deduplication note:** if the same finding re-surfaces in CodeRabbit's `♻️ Duplicate comments` section (Step 1.3.1.5), that re-surfaced finding is a SEPARATE entity in `active_threads` and goes through the normal verdict flow in Steps 13.1-13.6. The outdated thread auto-reply does NOT conflict — they're different surfaces of the related finding (one stale, one re-asserted).

5. **Idempotency:** before posting, check whether the agent already replied with the "Outdated — this thread references code that was modified..." string in this thread. If yes, skip the reply and proceed directly to resolve (handles re-runs after a crash between reply and resolve).

After processing all outdated threads, log: `"Auto-resolved M outdated threads in Step 13.0."`

**HARD BLOCK (Steps 13.1-13.6, findings mode only):** When REVIEW_MODE=findings, every active PR comment thread MUST receive a verdict-driven reply via the steps below — regardless of whether any fixes were applied. Step 13.0 above runs independently of this gate.

### Step 13.1: Response Rules (uniform for ALL sources)

**IMPORTANT:** Use the `{finding_id} → {commit_sha}` mapping from Phase 8.

**Case 1 — Fix applied (ANY source: Codacy, DeepSource, CodeRabbit, human):**
```
Fixed in <commit_sha>.

<brief description of what was done>
```

**Case 2 — Won't fix (ANY source: Codacy, DeepSource, CodeRabbit, human):**
```
Won't fix: <concrete reason why this doesn't apply>
```

**Case 2a — Won't fix + suppression (Codacy/DeepSource only):**
```
Won't fix: <reason>. Suppressed in <suppression_commit_sha>.
```

**Case 3 — Deferred:**
```
Deferred to <destination>: <brief reason>
```

**Case 4 — Contested:**
```
Contested: <agent's reasoning for why the comment is incorrect>
```

**Case 5 — Already fixed:**
```
Already addressed in a previous commit.
```

**Case 6 — Question/clarification (human reviewers):**
```
<direct answer referencing specific code/files>
```

### Step 13.2: Refresh Thread Map

Re-fetch the thread map from Step 1.3.1 to get the latest state (threads may have been resolved by pushes or other activity):

**HARD BLOCK — keep in lockstep with Step 1.3.1:** the `comments` selection below MUST mirror Step 1.3.1's selection, including `pullRequestReview { id author { login } }`. If you drop that field, Step 13.5 loses its `review_node_id` grouping key and will incorrectly classify every review as "no threads attached" → minimize everything indiscriminately.

```bash
gh api graphql -f query='
  query {
    repository(owner: "<owner>", name: "<repo>") {
      pullRequest(number: <number>) {
        reviewThreads(first: 100) {
          nodes {
            id
            isResolved
            isOutdated
            path
            line
            comments(first: 10) {
              nodes {
                databaseId
                author { login }
                body
                pullRequestReview { id author { login } }
              }
            }
          }
        }
      }
    }
  }
'
```

Update the thread map with fresh `isResolved` status. Re-derive `review_node_id` and `review_author` from the refreshed first-comment `pullRequestReview` selection — do NOT carry forward the Step 1.3.1 values blindly, since deletions or edits between Step 1.3.1 and Step 13.2 can change the parent review attribution. Skip threads already resolved (their `is_resolved == true` rules them out of further mutation but they REMAIN in the thread map for Step 13.5's grouping).

### Step 13.3: Reply AND Resolve Each Thread (atomically)

**CRITICAL:** For EACH thread, reply and resolve in the SAME step. Never batch "all replies first, then all resolves". The pattern is: reply → resolve → confirm → next thread.

**Deduplication check (MANDATORY):** Before posting a reply to any thread, check if a reply
from the agent already exists in that thread (e.g., from a previous interrupted run). If a
reply with similar content already exists, skip posting and proceed directly to resolve.
This prevents duplicate replies when re-executing after a crash between reply and resolve.

**For each unresolved thread, use the correct reply method based on the source:**

#### Case A: Native app threads (DeepSource `deepsource-io`, Codacy `codacy-production`)

The REST API returns 404 for these threads. You MUST use GraphQL for both reply and resolve.

**1. Reply via GraphQL:**
```bash
gh api graphql -f query='
  mutation {
    addPullRequestReviewThreadReply(input: {
      pullRequestReviewThreadId: "<thread_node_id>",
      body: "<reply>"
    }) { comment { id } }
  }
'
```

**2. Resolve via GraphQL:**
```bash
gh api graphql -f query='
  mutation {
    resolveReviewThread(input: {threadId: "<thread_node_id>"}) {
      thread { isResolved }
    }
  }
'
```

**3. Confirm** `isResolved: true` in the response.

**Example — DeepSource native thread:**
```bash
# Thread from deepsource-io at backend/internal/handler/client.go:42
# thread_node_id = "PRRT_kwDORrzDks579CXg"

# Reply
gh api graphql -f query='
  mutation {
    addPullRequestReviewThreadReply(input: {
      pullRequestReviewThreadId: "PRRT_kwDORrzDks579CXg",
      body: "Fixed in abc1234. Replaced exported function returning unexported type."
    }) { comment { id } }
  }
'

# Resolve
gh api graphql -f query='
  mutation {
    resolveReviewThread(input: {threadId: "PRRT_kwDORrzDks579CXg"}) {
      thread { isResolved }
    }
  }
'
```

**Example — Codacy native thread:**
```bash
# Thread from codacy-production at frontend/src/app/page.tsx:15
# thread_node_id = "PRRT_kwDORrzDks57_ABC"

# Reply
gh api graphql -f query='
  mutation {
    addPullRequestReviewThreadReply(input: {
      pullRequestReviewThreadId: "PRRT_kwDORrzDks57_ABC",
      body: "Won'\''t fix: this is a convention in the project. Suppressed via biome-ignore."
    }) { comment { id } }
  }
'

# Resolve
gh api graphql -f query='
  mutation {
    resolveReviewThread(input: {threadId: "PRRT_kwDORrzDks57_ABC"}) {
      thread { isResolved }
    }
  }
'
```

#### Case B: Workflow and bot threads (`github-actions[bot]`, `coderabbitai[bot]`, humans)

Use REST API with `in_reply_to` for the reply, then GraphQL for resolve.

**1. Reply via REST:**
```bash
gh api repos/{owner}/{repo}/pulls/{number}/comments \
  --method POST -f body="<reply>" -F in_reply_to=<first_comment_database_id>
```

**2. Resolve via GraphQL:**
```bash
gh api graphql -f query='
  mutation {
    resolveReviewThread(input: {threadId: "<thread_node_id>"}) {
      thread { isResolved }
    }
  }
'
```

**3. Confirm** `isResolved: true` in the response.

**If REST returns 404** (can happen for some bot types), fall back to Case A (GraphQL for both reply and resolve).

#### Case C: General PR comments (non-inline)

```bash
gh pr comment <PR_NUMBER_OR_URL> --body "<reply>"
```

These don't have threads and cannot be resolved.

### Step 13.4: Verify Zero Unresolved Remain

After all threads are processed (BOTH the active threads from Steps 13.1-13.3 AND the outdated threads from Step 13.0), re-run the query from Step 13.2 and confirm ALL threads — including outdated ones — have `isResolved: true`. If any remain unresolved, reply and resolve them now. Do NOT proceed until zero unresolved threads remain.

**Why this includes outdated threads:** CodeRabbit and other approval gates inspect EVERY review thread on the PR, not just the ones agents acted on. Leaving outdated threads with `isResolved: false` blocks PR approval even though the underlying code was already fixed in subsequent commits. Step 13.0's auto-resolve hygiene is the entire reason this gate now passes.

### Step 13.5: Hide Fully-Resolved Reviews (runs in `findings` and `diff` modes)

**Goal:** collapse bot-authored review summaries (e.g. CodeRabbit's `<base_pr_url>#pullrequestreview-<id>` entries) once ALL their inline threads are resolved AND those threads contain only bot-authored content — mirroring what a human does manually by clicking "Resolve conversation" on a review summary. Without this step, CodeRabbit's review summary panels stay expanded on the PR forever even when every underlying thread is resolved, which is exactly what users complain about.

**HARD BLOCK — runs in BOTH modes:**
- `findings` mode: runs AFTER Step 13.4 confirms zero unresolved threads.
- `diff` mode: runs AFTER Step 13.0 (outdated cleanup) and Step 13.2 (refresh thread map) — there are no agent verdicts to act on, but minimization is hygiene independent of verdicts.

The Completion Checklist and Phase 14 summary verify Step 13.5 ran. Idempotency (Step 13.5.4) makes it safe to re-run.

**PR scope reminder:** Step 13.5 acts on the `<owner>/<repo>` resolved at Step 1.1 — do NOT enumerate reviews on a different repo. The PAT scope bounds reach, but a misconfigured invocation must not pivot to another repo's PR.

#### Step 13.5.1: Enumerate ALL reviews on the PR

**First page (no cursor):**
```bash
gh api graphql -f query='
  query {
    repository(owner: "<owner>", name: "<repo>") {
      pullRequest(number: <number>) {
        reviews(first: 100) {
          pageInfo { hasNextPage endCursor }
          nodes { id author { login } state body isMinimized }
        }
      }
    }
  }
'
```

**Subsequent pages — pass the `endCursor` from the previous response:**
```bash
gh api graphql -f query='
  query($cursor: String) {
    repository(owner: "<owner>", name: "<repo>") {
      pullRequest(number: <number>) {
        reviews(first: 100, after: $cursor) {
          pageInfo { hasNextPage endCursor }
          nodes { id author { login } state body isMinimized }
        }
      }
    }
  }
' -f cursor="<endCursor>"
```

Merge all pages into a single `reviews[]` list.

**`gh` parameter gotcha:** use `-f` for raw string variables (`String`, here for `cursor`) and `-F` for typed variables (`ID!`, used in Step 13.5.3). Mixing them silently fails — `-F id="..."` for a `String` variable will error; `-f id="..."` for an `ID!` variable passes a string where the schema expects an ID.

#### Step 13.5.2: Compute per-review eligibility (precedence-ranked decision)

Using the thread map from Step 13.2 (whose query mirrors Step 1.3.1's `pullRequestReview` selection — see HARD BLOCK in Step 13.2), evaluate each `review` in `reviews[]` in this **exact order**. The first rule that matches wins:

1. **If `review.state == "PENDING"`** → skip. Pending reviews aren't visible to other PR participants yet.
2. **If `review.isMinimized == true`** → skip (idempotency — already hidden).
3. **If `review.author.login` is NOT in the bot allowlist below** → skip. **Human-authored reviews are NEVER auto-minimized**, regardless of state, body, or thread resolution. Approvals especially must remain visible — they are a governance signal.
4. **Compute `threads_for_review`** = `[t for t in (active_threads ∪ outdated_threads) if t.review_node_id == review.id]`. **If `len(threads_for_review) == 0`** → skip. Reviews with zero inline threads include CodeRabbit summary-only reviews and reviews whose findings live in the body (Step 1.3.1.5's `♻️ Duplicate comments` and `⚠️ Outside diff range comments` sections); auto-hiding those would suppress findings the user has not yet triaged.
5. **If any thread in `threads_for_review` has `review_node_id == null` AND `is_resolved == false`** → log a warning (`"Skipped <review_url>: orphan unresolved thread <thread_node_id>"`) and skip this review. Orphan unresolved threads (e.g. deleted first comment, attachment to a commit instead of a review) are an unexpected state worth surfacing rather than silently hiding.
6. **If any comment inside any thread in `threads_for_review` has an author NOT in the bot allowlist** → skip. Bot threads that contain human replies must stay visible — minimization would collapse the human's content along with the bot's. Log: `"Skipped <review_url>: contains human replies in <N> thread(s)"`.
7. **If `all(t.is_resolved == true for t in threads_for_review)` is false** → skip. (Step 13.4 already guarantees this in `findings` mode; in `diff` mode, only Step 13.0 ran, so this rule is the actual gate.)
8. **Otherwise** → eligible. Add the review to `eligible_reviews[]`.

**Bot allowlist (exact login string match — entries fail closed if the actual login differs):**
- `coderabbitai[bot]`
- `deepsource-io`
- `codacy-production`
- `github-actions[bot]`
- `copilot-pull-request-reviewer[bot]` *(GitHub Copilot for PRs — verify against the current repo's actual login; the older `copilot` form does not match modern Copilot review accounts)*
- `github-advanced-security[bot]`

#### Step 13.5.3: Minimize each eligible review (atomically: act → confirm → next)

For EACH review in `eligible_reviews[]`, in order, do not batch:

```bash
gh api graphql -f query='
  mutation($id: ID!) {
    minimizeComment(input: {subjectId: $id, classifier: RESOLVED}) {
      minimizedComment { isMinimized }
    }
  }
' -F id="<review_node_id>"
```

Confirm `isMinimized: true` in the response before moving to the next review. If the mutation errors (permission, race), log the failure with the review URL and continue — do NOT abort the run; Step 13.4 already guaranteed thread resolution (in `findings` mode), which is the user-visible blocker. Hiding is hygiene.

**Example — CodeRabbit review (matching the user's reported surface):**
```bash
# review_node_id = "PRR_kwDOABCDEF4gXyZ_" (from Step 13.5.1, author=coderabbitai[bot])
# corresponds to <base_pr_url>#pullrequestreview-4192419317

gh api graphql -f query='
  mutation($id: ID!) {
    minimizeComment(input: {subjectId: $id, classifier: RESOLVED}) {
      minimizedComment { isMinimized }
    }
  }
' -F id="PRR_kwDOABCDEF4gXyZ_"
```

#### Step 13.5.4: Idempotency

`review.isMinimized == true` from Step 13.5.1 is the dedupe key (Step 13.5.2 rule 2 enforces it). Steady-state on a re-run is `"Hidden 0 fully-resolved reviews (already minimized: K)"`.

**Race window — accepted trade-off:** between Step 13.5.1 (read) and Step 13.5.3 (write), another actor could call `minimizeComment(R, classifier: SPAM | OFFENSIVE | OUTDATED)`. Our subsequent mutation overwrites the classifier to `RESOLVED`. We accept this: pr-check's authority on "this thread is resolved" is established by Step 13.4 (or by the bot author + Step 13.0 in `diff` mode), and treating `RESOLVED` as the safe default is preferable to leaving the review uncollapsed. If the spec is later extended with a moderation pathway, this rule needs revisiting.

#### Step 13.5.5: Log line (MANDATORY — surface to user)

After processing all eligible reviews, emit ONE log line with per-author counts and dedupe accounting:

```
Hidden K fully-resolved reviews (CodeRabbit: X, DeepSource: Y, Codacy: Z, other bots: W). Already-minimized (idempotent skip): I. Skipped — non-bot replies / orphan threads / unresolved threads / non-bot author: S.
```

This line surfaces in chat output to confirm the hide-on-resolve behavior actually ran. Phase 14 echoes K under "Sources Analyzed".

### Step 13.6: Reply Summary

**HARD BLOCK:** The Status column MUST show "Resolved" for every row (including outdated-cleanup rows). If any row shows "Replied" instead of "Resolved", go back and resolve it.

Render TWO tables. The "Active threads" table is omitted entirely in `diff` mode (no verdicts produced); the "Outdated threads" table is rendered in both `findings` and `diff` modes.

```markdown
### PR Comment Replies Posted

#### Active threads (verdict-driven — `findings` mode only)
| # | Thread | Source | Reply | Commit | Status |
|---|--------|--------|-------|--------|--------|
| 1 | file.go:42 | Codacy | Fixed | abc1234 | Resolved |
| 2 | file.go:88 | DeepSource | Won't fix: convention. Suppressed | def5678 | Resolved |
| 3 | file.go:15 | CodeRabbit | Fixed | ghi9012 | Resolved |
| 4 | file.go:22 | @reviewer | Won't fix: out of scope | — | Resolved |
| 5 | general | @reviewer | [answer] | — | Resolved |

#### Outdated threads (Step 13.0 hygiene — runs in `findings` and `diff` modes)
| # | Thread | Source | Reply | Status |
|---|--------|--------|-------|--------|
| 1 | file.go:120 | CodeRabbit | Outdated — code changed in subsequent commits | Resolved |
| 2 | file.go:88 | Codacy | Outdated — code changed in subsequent commits | Resolved |

#### Reviews hidden (Step 13.5 — render only when ≥1 review was hidden)

The Review URL column renders the full anchored URL (`<base_pr_url>#pullrequestreview-<id>`) so the audit row is clickable; siblings use bare paths because reviews — unlike threads — have no `file:line` anchor. Render `Threads` as `K/K resolved` for K≥1, or `0/0 (summary-only — skipped per rule 4)` for the rare cases where a future relaxation of rule 4 surfaces here.

| # | Review URL | Author | Threads | Status |
|---|------------|--------|---------|--------|
| 1 | <base_pr_url>#pullrequestreview-<id> | coderabbitai[bot] | 4/4 resolved | Hidden |
| 2 | <base_pr_url>#pullrequestreview-<id> | deepsource-io | 2/2 resolved | Hidden |
```

---

### Phase 14: Final Summary

**Always render the `REVIEW_MODE` selected in Step 1.8** (`findings` | `diff` | `none`)
and a warning if findings remain unaddressed. Pick the template by mode:

**Template — when `REVIEW_MODE=none` (user chose Do nothing in Step 1.8):**

```markdown
### PR Review Summary: #<number> — <title>

**Mode:** none (user opted out)
**findings_total:** <N>
[render the next line ONLY if M > 0:]
**Outdated threads observed (NOT cleaned, blocking CodeRabbit approval):** M — re-run pr-check with mode=findings or mode=diff to auto-resolve them via Step 13.0. None mode respects user opt-out from all PR mutation, so these were left untouched.
**Status:** Exited without dispatching agents. <N> findings remain
unaddressed. Re-run `/optimus-pr-check` later to handle them.
```

**Template — when `REVIEW_MODE=diff` (user chose fresh diff review):**

```markdown
### PR Review Summary: #<number> — <title>

**Mode:** diff (fresh review of changed files; existing comments NOT evaluated)
**findings_total (existing, unaddressed):** <N>
**New agent findings (this run):** <M>
**Outdated threads auto-resolved (Step 13.0): M** — pure hygiene; required for CodeRabbit / approval-gate compliance
**Reviews hidden (Step 13.5): K** (CodeRabbit: X, DeepSource: Y, Codacy: Z, other bots: W) — fully-resolved bot review summaries collapsed via `minimizeComment`

[render the next paragraph ONLY if findings_total > 0:]
⚠️ **<N> existing PR comments / CI failures were NOT addressed in this run.**
Phase 13 verdict-driven replies (Steps 13.1, 13.3, 13.4, 13.6 active-threads
table) were skipped because diff mode does not produce AGREE/CONTEST verdicts
on existing threads. Step 13.0 (outdated thread cleanup) and Step 13.5 (hide
fully-resolved reviews) ran normally — see counts above. To address the
existing N findings, re-run pr-check with `REVIEW_MODE=findings` (the default
when findings_total > 0).

[then render the standard tables for Fixed / Skipped / Deferred / CI Status /
Verification / Configuration Changes — same schema as findings mode, but
populated only with the new findings discovered in this run]
```

**Template — when `REVIEW_MODE=findings` (default path with findings_total > 0):**

Render the standard summary below.

```markdown
### PR Review Summary: #<number> — <title>

### Sources Analyzed
- CI checks: X failing (Y fixed, Z remaining)
- Codacy: X issues (Y fixed, Z suppressed)
- DeepSource: X issues (Y fixed, Z suppressed)
- CodeRabbit: X comments (Y validated, Z contested)
- Human reviewers: X comments (Y validated, Z contested)
- New agent findings: X
- **Outdated threads auto-resolved (Step 13.0): M** — pure hygiene; required for CodeRabbit / approval-gate compliance
- **Reviews hidden (Step 13.5): K** (CodeRabbit: X, DeepSource: Y, Codacy: Z, other bots: W) — fully-resolved review summaries collapsed via `minimizeComment`
  [render this aside ONLY when M is non-trivially large, e.g. M >= 10:]
  (NOTE: on the first pr-check run after this skill was upgraded, M may be unexpectedly large because previously-discarded outdated threads from prior runs accumulate on the PR. Subsequent runs will see steady-state values.)

### Convergence
- Rounds dispatched (round 1 + convergence rounds): X
- Status: CONVERGED | USER_STOPPED | SKIPPED | HARD_LIMIT | DISPATCH_FAILED_ABORTED

### Fixed (X findings)
| # | Source | File(s) | Commit |
|---|--------|---------|--------|

### Won't Fix — Suppressed (X findings)
| # | Source | File(s) | Reason | Suppression Commit |
|---|--------|---------|--------|--------------------|

### Skipped (X findings)
| # | Source | File(s) | Reason |
|---|--------|---------|--------|

### Deferred (X findings)
| # | Source | File(s) | Destination |
|---|--------|---------|-------------|

### CI Status
- Codacy: <conclusion> (<N> annotations)
- DeepSource: <analyzer statuses>
- Other: X passing, Y failing

### Verification
- Lint: PASS
- Unit tests: PASS (X tests) — Coverage: XX.X% (threshold: 85%)
- Integration tests: PASS/SKIPPED — Coverage: XX.X% (threshold: 70%) / SKIP

### Configuration Changes
| # | Tool | Change | Method |
|---|------|--------|--------|

### PR Readiness
- [ ] All CRITICAL/HIGH findings resolved (including CI failures)
- [ ] All CI checks passing (verified after fixes pushed)
- [ ] Codacy/DeepSource findings resolved or suppressed
- [ ] Changes align with PR description and linked issues
- [ ] Test coverage adequate

**Verdict:** READY FOR MERGE / NEEDS CHANGES
```

---

### Completion Checklist (MANDATORY — verify before ending)

- [ ] Total findings count (N) was announced before the first finding
- [ ] All findings presented with "(X/N)" progress prefix in EVERY header
- [ ] All decisions collected (fix / skip / defer for every finding)
- [ ] All approved fixes committed with TDD cycle (applied after all decisions collected)
- [ ] Won't-fix Codacy/DeepSource findings suppressed inline
- [ ] Push completed or explicitly skipped
- [ ] ALL comment threads replied AND resolved atomically (reply → resolve → next, never batch separately)
- [ ] Verification query confirms zero `isResolved: false` threads remain
- [ ] Fully-resolved reviews hidden via `minimizeComment` (runs in `findings` and `diff` modes) — Step 13.5.3 confirms `isMinimized: true` for every previously-eligible review, or `eligible_reviews[]` was empty (steady-state on a re-run)
- [ ] Reply summary presented — every row MUST show "Resolved" status
- [ ] Final summary with verdict presented

**STOP CONDITION:** You may ONLY end the review session after ALL items are checked.

