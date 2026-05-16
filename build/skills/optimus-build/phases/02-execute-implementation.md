# Phase 2 (Execute Implementation): Subtask Loop + Post-Verification

Loaded by `SKILL.md` after Phase 1 completes. After context is loaded and all
questions are answered, execute the implementation.

## Step 2.1: Load Subtasks

Read all subtask `.md` files from the subtasks directory (derived from TaskSpec in
Step 1.7). Sort by filename (`subtask_001.md`, `subtask_002.md`, etc.).

If `PARALLEL-PLAN.md` exists in the subtasks directory, read it for informational
purposes (to understand implementation structure and dependencies between subtasks).
**NOTE:** All subtasks are executed sequentially with user checkpoints between each.
Future versions may support parallel execution.

**HARD BLOCK — Zero subtasks guard:**
If 0 subtask `.md` files are found (subtasks directory missing, empty, or contains
no `.md` files):
- **STOP**: "No subtask files found for T-XXX in `<subtasks_dir>`. Subtask breakdown
  is required for implementation. Run Ring pre-dev subtask creation first
  (`/pre-dev-subtask-creation`), or create subtask files manually."
- Do NOT proceed to Step 2.2.

Present the execution plan to the user:
```
Subtasks to implement (N total):
  1. subtask_001.md — [title from first heading]
  2. subtask_002.md — [title from first heading]
  ...
```

## Step 2.2: Execute Each Subtask via Ring Droid

**HARD BLOCK — Ring droid dispatch is MANDATORY for every subtask:**

The orchestrator (this agent) MUST NOT implement code directly — it MUST delegate
to a ring droid via `Task` tool for every single subtask, regardless of size or
complexity. The orchestrator's role is to manage the loop, run tests, and present
results — never to write production code.

**Anti-rationalization (excuses the agent MUST NOT use):**
- "I can implement this small subtask directly" — NO. Dispatch a ring droid.
- "The droid will take longer" — NO. Dispatch a ring droid.
- "I already know what to do" — NO. Dispatch a ring droid.
- "This is just a config change" — NO. Dispatch a ring droid.
- "There's only one subtask" — NO. Dispatch a ring droid.

For EACH subtask (sequentially, unless PARALLEL-PLAN.md allows parallel):

**0. Gather prior-subtask summaries (F12a — required before dispatch):**

Before dispatching `subtask_NNN`, collect short summaries of subtasks
`001..NNN-1` so the droid has full continuity context. Without this, the droid
for `subtask_002` does not know what `subtask_001` produced (file paths,
exported symbols, contract decisions) and can re-derive or contradict prior
work. Two complementary sources:

- **Session/state file:** if a post-subtask state file exists in
  `.optimus/sessions/` with a `completed_subtasks[]` array (filename + 1-line
  summary + key files/symbols), read it.
- **Git history (always available):** since the task started (find the
  branch's first commit on `$TASK_BRANCH`), enumerate subtask commits:
  ```bash
  git log --oneline --grep='subtask_' "$(git merge-base HEAD origin/main)"..HEAD
  ```
  For each commit, derive the subtask number from the message and a 1-line
  summary of files touched (`git show --stat --format= <sha>`).

Compose a list of entries shaped like:

```
- subtask_001.md — Added `internal/auth/jwt.go` (SignToken, VerifyToken); updated config schema with `jwt.secret`.
- subtask_002.md — Added `internal/auth/middleware.go` (RequireAuth); updated router to apply it on /api/*.
```

Pass this list as the **Previously completed subtasks** context block in the
dispatch prompt below. For `subtask_001` the list is empty (and the prompt
section says "(none — this is the first subtask)").

**1. Dispatch the stack-appropriate ring droid** via `Task` tool:

| Stack | Ring Droid |
|-------|-----------|
| Go | `ring:backend-engineer-golang` |
| TypeScript/Node.js | `ring:backend-engineer-typescript` |
| React/Next.js | `ring:frontend-engineer` |
| Tests only | `ring:qa-analyst` |

**2. The droid prompt MUST include:**
- The subtask file content (full implementation steps + code examples from Ring pre-dev)
- The task spec objective and acceptance criteria
- Project rules and coding standards (from Step 1.6)
- Codebase patterns discovered in Step 1.8
- File paths for the droid to navigate (Read/Grep/Glob enabled)
- Answers to questions from Step 1.9
- **Previously completed subtasks:** populated by the orchestrator from prior
  subtask state (Step 0 above). For each completed subtask: `subtask_NNN.md`
  filename + 1-line summary of files created/modified + relevant exported
  symbols/contracts. For `subtask_001`, this section reads `(none — this is
  the first subtask)`. The droid uses this to avoid re-creating files,
  re-exporting symbols, or contradicting earlier contract decisions.
- Instruction: "Implement this subtask following TDD (RED-GREEN-REFACTOR).
  Write failing test first, then minimal implementation, then refactor."

**3. After the droid returns:**

a. Run unit tests quietly — see AGENTS.md Protocol: Quiet Command Execution:
```bash
_optimus_quiet_run "make-test" make test
```
The agent sees only a PASS/FAIL verdict; the full test log lives in
`.optimus/logs/` if needed for diagnosis.

b. **If tests fail (max 3 attempts per subtask):**
   1. **Logic bug** — dispatch the same ring droid with failure output and instruction:
      "Test failed after your implementation: <output>. Diagnose and fix." Re-run tests.
   2. **Flaky test** — re-execute at least 3 times in a clean environment to confirm
      flakiness. Maximum 1 test skipped per subtask. Document explicit justification
      (error message, flakiness evidence) and tag with `pending-test-fix`.
   3. **External dependency** — pause and wait for restoration.
   If tests fail after 3 attempts, ask user via `AskUser`:
   "Unit tests failing after subtask X (3 attempts). Skip and continue, or stop?"
c. If tests pass → present a summary of what changed (files created/modified, tests added)

**4. MANDATORY USER CHECKPOINT:**

**HARD BLOCK:** After EVERY subtask, the agent MUST ask the user before proceeding.
The agent MUST NOT silently stop. The agent MUST NOT silently continue. The agent
MUST NOT batch multiple subtasks without checkpoints.

Ask via `AskUser`:
```
[topic] (X/N) Subtask-X
[question] Subtask X/N complete: [one-line summary of what was done].
  Unit tests: PASS (Y tests). Ready to proceed?
[option] Continue to subtask X+1
[option] Review changes first (git diff)
[option] Stop here — I'll resume later
```

- If **Continue** → proceed to next subtask (loop back to step 1)
- If **Review changes** → run `git diff` and present, then re-ask
- If **Stop** → present partial progress summary and stop

**If this is the LAST subtask** → proceed to Step 2.3 instead of asking to continue.

## Step 2.3: Post-Implementation Verification

After ALL subtasks are complete:

1. **Run lint quietly** — see AGENTS.md Protocol: Quiet Command Execution:
   ```bash
   _optimus_quiet_run "make-lint" make lint   # MANDATORY (first run of this stage)
   ```
   If lint fails, fix formatting.

   Unit tests already passed after the last subtask (Step 2.2 loop) — no need to re-run here.

2. **Measure coverage** — see AGENTS.md Protocol: Coverage Measurement. Coverage
   commands are wrapped in `_optimus_quiet_run` by the protocol.

3. **Run integration tests (only if integration coverage was SKIPped):**
   If item 2 measured integration coverage via `make test-integration-coverage`,
   integration tests already ran — skip this step (no-op).
   Otherwise (coverage target missing, marked SKIP in item 2), run quietly:
   ```bash
   _optimus_quiet_run "make-test-integration" make test-integration   # Optional fallback — SKIP if missing
   ```
   If the target does not exist, mark as SKIP. If it fails, the helper prints
   the last 50 lines of the log automatically — then ask user via `AskUser`:
   "Integration tests failing. Fix or defer to check?"

4. **Dispatch code review and spec compliance droids** in parallel via `Task` tool:
   - `ring:code-reviewer`
   - `ring:business-logic-reviewer`
   - `ring:security-reviewer`
   - `ring:test-reviewer`
   - `ring:nil-safety-reviewer`
   - `ring:consequences-reviewer`
   - `ring:dead-code-reviewer`
   - `ring:qa-analyst`

   Each droid receives all files changed by this task + project rules + task spec.
   Include per-droid quality checklists — see AGENTS.md Protocol: Per-Droid Quality Checklists.

   **Each review droid prompt MUST include this verification-scope block verbatim:**

   ```
   Verification scope (MANDATORY):
     Static analysis (lint, vet, format) and tests (unit, integration, coverage)
     have already been run by the orchestrator. Results are in this prompt or in
     the log files referenced under .optimus/logs/.
     - Do NOT run verification commands yourself. Forbidden: `go test`, `npm test`,
       `npm run test`, `pytest`, `make test`, `make lint`, `make test-coverage`,
       `make test-integration`, `golangci-lint`, `go vet`, `goimports`, `gofmt`,
       `prettier`, `eslint`, `tsc`, or any equivalent.
     - If you need test/coverage details, Read the log files referenced in this
       prompt — do not regenerate them.
     - Use Read, Grep, and Glob to inspect source files. Reserve Bash for read-only
       git inspection (`git log`, `git blame`, `git diff`) when needed.
   ```

   **Spec Compliance agent** (`ring:qa-analyst`) must additionally (beyond the protocol):
   1. List every acceptance criterion from the Ring source (via `TaskSpec` column) and mark PASS/FAIL/PARTIAL
   2. List every test ID and verify a corresponding test exists
   3. If the task has API endpoints, verify request/response format matches API contracts
   4. If the task has DB changes, verify column types/constraints match the data model

5. **Consolidate review findings:** merge, deduplicate, sort by severity.

6. **Present findings interactively** — one at a time, severity order, collect decisions
   (same pattern as AGENTS.md "Common Patterns > Finding Presentation").

7. **Apply approved fixes** — for each approved fix, apply directly (simple) or dispatch
   ring droid (complex). Run unit tests after each fix.

8. **Convergence loop (Optional — Gated):** Execute the opt-in convergence loop — see
   AGENTS.md "Common Patterns > Protocol: Convergence Loop (Full Roster Model — Opt-In, Gated)".
   Round 1 already happened in Step 2.3 item 4 (parallel review dispatch). THIS step
   only handles rounds 2 through 5. Present the **entry gate** before round 2 (`Run round 2` / `Skip
   convergence loop`); present the **per-round gate** before rounds 3, 4, 5. If a
   dispatched round produces ZERO new findings, declare convergence and exit silently.
   Dispatch the same 8 review droids in each round. Record the final loop status
   (`CONVERGED` / `USER_STOPPED` / `SKIPPED` / `HARD_LIMIT` / `DISPATCH_FAILED_ABORTED`)
   for the Final Summary. **Failure handling (build-specific carve-out):** Long
   multi-subtask builds make a deep-Phase-2.3 blocking prompt disruptive. For `build`
   specifically, when a dispatched agent slot fails (Task tool error, ring droid
   unavailable), the orchestrator MAY treat the failed slot as "zero new findings for
   that slot" and continue silently with a warning printed to the user — diverging
   from the protocol's default behavior of asking. The user is informed via the Final
   Summary which slots were skipped and why. If multiple slots fail in the same round,
   the orchestrator falls back to the protocol default and asks `AskUser` whether to
   retry or stop (status `DISPATCH_FAILED_ABORTED`). Other skills that consume this
   protocol use the default behavior (ask immediately on first failure).
