#!/usr/bin/env bash
# optimus-state-read.sh
#
# Read .optimus/state.json for a single task and emit a structured JSON
# response. Replaces the ~6-line `jq -r --arg id ...` snippet repeated across
# build/plan/done/review SKILL.md files.
#
# Why a script: state.json access is one of the most-duplicated patterns
# across skills. Centralizing here gives a single error-handling contract
# (file missing, malformed JSON, MAIN_WORKTREE unset) and a stable JSON
# output shape that small models can read reliably.
#
# Source of truth for the state.json schema: AGENTS.md Protocol "Valid Status
# Values" and "Operational State". When the schema changes, update both.
#
# Usage:
#   MAIN_WORKTREE=/path/to/repo optimus-state-read.sh <TASK_ID>
#   optimus-state-read.sh --explain    # print JSON schema
#
# Output (stdout, always JSON):
#   ok + exists: {"status":"ok","error":null,"data":{"task_id":"T-003",
#                  "exists":true,"task_status":"Em Andamento",
#                  "branch":"feat/...","updated_at":"2025-..."}}
#   ok + not in state.json (implicit Pendente):
#                {"status":"ok","error":null,"data":{"task_id":"T-003",
#                  "exists":false,"task_status":"Pendente",
#                  "branch":"","updated_at":""}}
#   error:       {"status":"error","error":{"code":"...","message":"...",
#                  "hint":"..."},"data":null}
#
# Exit codes: 0 ok (including implicit Pendente), 1 task lookup failed
# in a recoverable way (e.g., MAIN_WORKTREE not set), 2 infra (jq missing,
# state.json malformed), 3 usage error.

set -u

emit_error() {
  local code="$1" message="$2" hint="$3"
  printf '{"status":"error","error":{"code":"%s","message":"%s","hint":"%s"},"data":null}\n' \
    "$code" "$message" "$hint"
}

cmd_explain() {
  cat <<'EOF'
{
  "schema_version": "1",
  "script": "optimus-state-read.sh",
  "args": ["TASK_ID"],
  "env": {"MAIN_WORKTREE": "absolute path to main repo worktree (required)"},
  "output_schema": {
    "status": "ok | error",
    "error": "null | {code,message,hint}",
    "data": {
      "task_id": "string (T-NNN)",
      "exists": "boolean (true if entry present in state.json)",
      "task_status": "string (Pendente|Validando Spec|Em Andamento|Validando Impl|DONE|Cancelado)",
      "branch": "string (empty when exists=false)",
      "updated_at": "ISO8601 string (empty when exists=false)"
    }
  },
  "exit_codes": {"0": "ok (including implicit Pendente)", "1": "recoverable lookup error", "2": "infra error", "3": "usage error"}
}
EOF
}

cmd_read() {
  local task_id="${1:-}"
  if [ -z "$task_id" ]; then
    emit_error "usage" "missing TASK_ID argument" "call as: optimus-state-read.sh <TASK_ID>"
    return 3
  fi

  if [ -z "${MAIN_WORKTREE:-}" ]; then
    emit_error "main_worktree_unset" "MAIN_WORKTREE env var not set" "resolve via 'git worktree list --porcelain' before calling this script"
    return 1
  fi

  local state_file="${MAIN_WORKTREE}/.optimus/state.json"
  if [ ! -f "$state_file" ]; then
    # state.json missing means no tasks have run yet — task is implicit Pendente.
    printf '{"status":"ok","error":null,"data":{"task_id":"%s","exists":false,"task_status":"Pendente","branch":"","updated_at":""}}\n' \
      "$task_id"
    return 0
  fi

  if ! command -v jq >/dev/null 2>&1; then
    emit_error "jq_missing" "jq is required but not installed" "brew install jq (macOS) or apt install jq (Linux)"
    return 2
  fi

  # Validate JSON parses first; jq returns 5 on parse error.
  if ! jq empty "$state_file" 2>/dev/null; then
    emit_error "state_malformed" "state.json is not valid JSON" "inspect ${state_file} manually or restore from backup"
    return 2
  fi

  local raw
  raw=$(jq -c --arg id "$task_id" '.[$id] // null' "$state_file")
  if [ "$raw" = "null" ]; then
    printf '{"status":"ok","error":null,"data":{"task_id":"%s","exists":false,"task_status":"Pendente","branch":"","updated_at":""}}\n' \
      "$task_id"
    return 0
  fi

  # Compose response. Status/branch/updated_at default to empty strings if absent.
  jq -nc --arg id "$task_id" --argjson entry "$raw" '
    {
      status: "ok",
      error: null,
      data: {
        task_id: $id,
        exists: true,
        task_status: ($entry.status // "Pendente"),
        branch: ($entry.branch // ""),
        updated_at: ($entry.updated_at // "")
      }
    }
  '
}

main() {
  case "${1:-}" in
    --explain|explain) cmd_explain ;;
    -h|--help|"")
      cat <<'EOF'
usage: MAIN_WORKTREE=/repo optimus-state-read.sh <TASK_ID>

Reads .optimus/state.json (under MAIN_WORKTREE) and emits the task's
operational state as JSON. A task with no entry is implicitly Pendente.

Subcommands:
  --explain     Print JSON schema describing this script.
  --help        Show this help text.
EOF
      ;;
    *) cmd_read "$@" ;;
  esac
}

main "$@"
