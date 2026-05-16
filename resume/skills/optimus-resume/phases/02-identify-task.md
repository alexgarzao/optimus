# Phase 2: Identify Task

Loaded after Phase 1. Resolve the task ID (user-provided or auto-detected from state.json), parse metadata from optimus-tasks.md, reject terminal statuses, run informational dependency check.

### Step 2.1: Task ID Provided

If the user supplied an argument as the task ID, set `TASK_ID` to that value.

**Validate format (HARD BLOCK):**

```bash
if [ -z "$TASK_ID" ]; then
  echo "ERROR: TASK_ID is empty."
  # STOP
fi
if ! [[ "$TASK_ID" =~ ^T-[0-9]+$ ]]; then
  echo "ERROR: Malformed TASK_ID '$TASK_ID' — expected format T-NNN (e.g., T-001, T-042)."
  # STOP
fi
```

Verify the task exists in optimus-tasks.md:

```bash
grep -E "^\| ${TASK_ID} \|" "$TASKS_FILE" >/dev/null
```

If no match → **STOP**: `"Task ${TASK_ID} not found in optimus-tasks.md. Run /optimus-report to see available tasks."`

### Step 2.2: Auto-Detect (no ID provided)

Filter for a concrete non-terminal status (whitelist — prevents malformed `null`/missing
status entries from surfacing as resumable tasks). Order by `updated_at` descending
(most recent first) for stable UX.

```bash
if [ -z "$STATE_JSON" ]; then
  echo "ERROR: No state.json found and no task ID provided. Run /optimus-report to see the project status."
  # STOP
fi
IN_PROGRESS=$(printf '%s' "$STATE_JSON" | jq -r '
  to_entries
  | map(select(
      .value.status == "Validando Spec"
      or .value.status == "Em Andamento"
      or .value.status == "Validando Impl"
    ))
  | sort_by(.value.updated_at // "")
  | reverse
  | .[]
  | "\(.key)\t\(.value.status)\t\(.value.branch // "")\t\(.value.updated_at // "")"
')
```

- **If 0 tasks** → **STOP**: `"No in-progress tasks found. Run /optimus-report to see the project status, or /optimus-plan T-XXX to start a new task."`
- **If exactly 1 task** → use that ID as `TASK_ID` (no AskUser — resume does not change status, so there is no expanded-confirmation requirement).
- **If N tasks** → present via `AskUser` with one option per task (`T-XXX — <title> (<status>, updated <relative-time>)`) plus **Cancel**. Do NOT offer Resume/Start fresh/Continue.

<a id="step-read-task-metadata"></a>
### Step 2.3: Read Task Metadata (HARD BLOCK)

Extract task metadata from optimus-tasks.md. The agent MUST execute the bash snippet literally;
prose-level "capture TASK_TITLE…" is not sufficient because downstream steps consume the
vars directly.

```bash
# optimus-tasks.md columns by pipe index: | 1=<blank> | 2=ID | 3=Title | 4=Tipo | 5=Depends | 6=Priority | 7=Version | 8=Estimate | 9=TaskSpec | 10=<blank> |
TASK_ROW=$(awk -F'|' -v id="$TASK_ID" '
  { gsub(/^ +| +$/,"",$2) }
  $2 == id { print; exit }
' "$TASKS_FILE")

if [ -z "$TASK_ROW" ]; then
  echo "ERROR: Could not read row for $TASK_ID from $TASKS_FILE."
  # STOP
fi

_trim() { printf '%s' "$1" | sed -E 's/^[[:space:]]+//; s/[[:space:]]+$//'; }
TASK_TITLE=$(_trim   "$(printf '%s' "$TASK_ROW" | awk -F'|' '{print $3}')")
TASK_TIPO=$(_trim    "$(printf '%s' "$TASK_ROW" | awk -F'|' '{print $4}')")
TASK_DEPENDS=$(_trim "$(printf '%s' "$TASK_ROW" | awk -F'|' '{print $5}')")
TASK_VERSION=$(_trim "$(printf '%s' "$TASK_ROW" | awk -F'|' '{print $7}')")

for v in TASK_TITLE TASK_TIPO TASK_DEPENDS TASK_VERSION; do
  eval "val=\${$v}"
  if [ -z "$val" ]; then
    echo "ERROR: $v is empty for $TASK_ID (could not parse optimus-tasks.md row)."
    # STOP
  fi
done
```

Read operational state from the cached `STATE_JSON` (integrity already validated in
Step 1.4; no re-validation here):

```bash
if [ -n "$STATE_JSON" ]; then
  TASK_STATUS=$(printf '%s' "$STATE_JSON" | jq -r --arg id "$TASK_ID" '.[$id].status // "Pendente"')
  TASK_BRANCH=$(printf '%s' "$STATE_JSON" | jq -r --arg id "$TASK_ID" '.[$id].branch // ""')
else
  TASK_STATUS="Pendente"
  TASK_BRANCH=""
fi
```

### Step 2.4: Refuse Terminal Statuses

- If `TASK_STATUS` is `DONE` → **STOP**: `"Task ${TASK_ID} is already DONE. Nothing to resume. To reopen, use /optimus-tasks."`
- If `TASK_STATUS` is `Cancelado` → **STOP**: `"Task ${TASK_ID} is Cancelado. Reopen via /optimus-tasks before resuming."`

### Step 2.5: Dependency Check (informational)

To avoid recommending a next stage that the delegate would immediately refuse (Rule 6 in
AGENTS.md Task Lifecycle), compute whether all `TASK_DEPENDS` are `DONE`. This does NOT
block resume itself — the user may still want to inspect the workspace — but it constrains
the Phase 5 options.

Step 2.3 guarantees `TASK_DEPENDS` is non-empty (either `-` or a comma-separated list of
`T-NNN`), so a bare `[ -z "$TASK_DEPENDS" ]` here would indicate a contract violation.

```bash
BLOCKING_DEPS=""
if [ -z "$TASK_DEPENDS" ]; then
  echo "ERROR: TASK_DEPENDS empty after Step 2.3 — contract violation."
  # STOP
fi
if [ "$TASK_DEPENDS" != "-" ]; then
  # Build a JSON array of dep IDs (trimmed). Single jq pass resolves all statuses.
  DEPS_JSON=$(printf '%s' "$TASK_DEPENDS" | jq -Rc '
    split(",") | map(gsub("^\\s+|\\s+$"; "")) | map(select(length > 0))
  ')
  BLOCKING_DEPS=$(printf '%s' "${STATE_JSON:-{}}" | jq -r --argjson deps "$DEPS_JSON" '
    [ $deps[] as $d
      | { id: $d, status: (.[$d].status // "Pendente") }
      | select(.status != "DONE")
      | "\(.id) (\(.status))"
    ] | join(", ")
  ')
fi
```

If `BLOCKING_DEPS` is non-empty, Phase 5 will **replace** the stage options with
`Skip` + `Run /optimus-report` and surface a warning in the Phase 4 summary
(see Step 4.2).

---
