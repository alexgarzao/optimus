# Phase 2: Classify, Filter, and Summarize

Loaded after Phase 1. Classify tasks by status, filter by active version, summarize version progress.

Classify each task into one of these categories:

### Done
Status is `DONE`.

### Cancelled
Status is `Cancelado`. These tasks were abandoned and will not be implemented.
Show in a separate section — do NOT count them in progress calculations.

### Active
Status is anything other than `Pendente`, `DONE`, or `Cancelado`:
- `Validando Spec` (plan running)
- `Em Andamento` (build running)
- `Validando Impl` (check running)

### Ready to Start
Status is `Pendente` AND all dependencies are `DONE` (or no dependencies).

### Blocked
Status is `Pendente` AND at least one dependency is NOT `DONE` or is `Cancelado`.
Record which dependencies are blocking (note if a blocker is `Cancelado` — the dependency
should be removed or replaced).

---

### Phase 4: Version Filtering

### Step 4.1: Determine Version Scope

Resolve the effective scope in this order — see AGENTS.md Protocol: Default Scope Resolution.

1. **Invocation wins.** If the user specified a scope in the invocation (e.g.,
   "report ativa", "report all", "report v2", "report upcoming"), use that scope
   directly. Skip sub-steps 2-4.

   **Force-ask keywords:** If the invocation contains `ask` or `menu` (e.g.,
   "report ask", "report menu"), skip sub-step 2 and go straight to the AskUser prompt
   (sub-step 3). Use this to override a saved default and optionally overwrite it.

2. **Config fallback.** If `.optimus/config.json` has a `defaultScope` key, use it
   without prompting. Validate the value (`ativa`, `upcoming`, `all`, or an existing
   version name). If invalid, warn and fall through to sub-step 3.

3. **Ask user.** Via `AskUser`:

   ```
   Which version scope do you want to see?
   ```
   Options:
   - **Ativa** — only tasks from the active version (<active_version_name>)
   - **Upcoming** — active + planned versions (Ativa, Próxima, Planejada — excludes Backlog and Concluída)
   - **All** — all tasks across all versions
   - **Specific version** — pick one version by name

   If the user selects **Specific version**, follow up with `AskUser` listing available
   version names as options.

4. **Offer to persist (only when sub-step 3 ran).** After the user picks a scope, ask:

   ```
   Save "<chosen_scope>" as the default in .optimus/config.json?
   You can still override per-invocation (e.g., "report all") or use
   "report ask" to be prompted again.
   ```
   Options:
   - **Save as default** — write `defaultScope` to `.optimus/config.json`
   - **Just this time** — do not persist

   **Exception to the read-only rule:** writing `defaultScope` to `.optimus/config.json`
   is the ONLY side-effect this skill is allowed to perform, and only when the user
   explicitly chooses "Save as default".

### Step 4.2: Apply Filter

**Scope mapping:**

| Scope | Versions included |
|-------|-------------------|
| `ativa` | Only the version with Status `Ativa` |
| `upcoming` | Versions with Status `Ativa`, `Próxima`, or `Planejada` |
| `all` | All versions |
| `<version_name>` | Only the named version |

**When filtering:**
- All subsequent phases (dependency graph, parallelization, dashboard tables) only include
  tasks from the selected version(s)
- Cross-version dependencies are shown as external references (e.g., "depends on T-001 [MVP, DONE]")

---

### Phase 5: Version Progress Summary

Compute progress for each version, regardless of filtering.
**Cancelled tasks are excluded from progress calculations** — they do not count toward
the total, done, active, or pending numbers. Progress = Done / (Total - Cancelled).
**If (Total - Cancelled) == 0** (all tasks cancelled or no tasks exist), show progress as
"N/A — all tasks cancelled" instead of computing a division.

```
┌──────────────────────────────────────────────────────────────┐
│ VERSION PROGRESS                                              │
├─────────┬────────┬──────┬────────┬─────────┬──────────┬──────┤
│ Version │ Status │ Done │ Active │ Pending │ Canceld. │ Prog │
├─────────┼────────┼──────┼────────┼─────────┼──────────┼──────┤
│ MVP     │ Ativa  │ 5    │ 2      │ 4       │ 1        │ 45%  │
│ v2      │ Próxima│ 0    │ 0      │ 6       │ 0        │ 0%   │
│ Futuro  │ Backlog│ 0    │ 0      │ 3       │ 0        │ 0%   │
└─────────┴────────┴──────┴────────┴─────────┴──────────┴──────┘
```

This section is ALWAYS shown (even when filtering by a specific version) to give the
user the full project overview.

---
