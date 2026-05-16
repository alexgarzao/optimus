#!/usr/bin/env bash
# optimus-task-gate.sh
#
# Validate that a task is in an expected state.json status. Replaces the
# repeated "read state.json + compare to expected list + emit blocking
# message" snippets that appear in plan/build/review/done SKILL.md.
#
# Composes on top of optimus-state-read.sh (calls it internally).
#
# Usage:
#   MAIN_WORKTREE=/repo optimus-task-gate.sh <TASK_ID> --expected="Validando Spec|Em Andamento"
#   optimus-task-gate.sh --explain
#
# Output (stdout, always JSON):
#   {"status":"ok","error":null,"data":{
#     "task_id":"T-003",
#     "current_status":"Em Andamento",
#     "expected_one_of":["Validando Spec","Em Andamento"],
#     "passes":true,
#     "reason":""
#   }}
#
# A failing gate is NOT a script error — `status` stays "ok", `passes` is
# false, `reason` carries the human-readable explanation. The caller
# (skill) decides whether to HARD BLOCK or prompt the user.
#
# Genuine script errors (missing args, MAIN_WORKTREE unset, jq missing)
# emit {"status":"error",...} and exit non-zero.

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

emit_error() {
  local code="$1" message="$2" hint="$3"
  printf '{"status":"error","error":{"code":"%s","message":"%s","hint":"%s"},"data":null}\n' \
    "$code" "$message" "$hint"
}

cmd_explain() {
  cat <<'EOF'
{
  "schema_version": "1",
  "script": "optimus-task-gate.sh",
  "args": ["TASK_ID", "--expected=<STATUS|STATUS|...>"],
  "env": {"MAIN_WORKTREE": "absolute path to main repo worktree (required)"},
  "expected_format": "pipe-separated list of valid status values: Pendente|Validando Spec|Em Andamento|Validando Impl|DONE|Cancelado",
  "output_schema": {
    "status": "ok | error",
    "error": "null | {code,message,hint}",
    "data": {
      "task_id": "string",
      "current_status": "string",
      "expected_one_of": "array<string>",
      "passes": "boolean",
      "reason": "string (empty when passes=true)"
    }
  },
  "exit_codes": {"0": "ok regardless of passes value", "1": "recoverable", "2": "infra", "3": "usage"},
  "note": "A failing gate is reported via data.passes=false, NOT via status=error. status=error is reserved for script-level failures."
}
EOF
}

cmd_check() {
  local task_id=""
  local expected=""

  while [ "$#" -gt 0 ]; do
    case "$1" in
      --expected=*) expected="${1#--expected=}" ;;
      --expected)
        shift
        expected="${1:-}"
        ;;
      --*)
        emit_error "usage" "unknown flag: $1" "see optimus-task-gate.sh --help"
        return 3
        ;;
      *)
        if [ -z "$task_id" ]; then
          task_id="$1"
        else
          emit_error "usage" "unexpected positional arg: $1" "only one TASK_ID is accepted"
          return 3
        fi
        ;;
    esac
    shift
  done

  if [ -z "$task_id" ]; then
    emit_error "usage" "missing TASK_ID argument" "call as: optimus-task-gate.sh <TASK_ID> --expected=\"...\""
    return 3
  fi
  if [ -z "$expected" ]; then
    emit_error "usage" "missing --expected flag" "example: --expected=\"Validando Spec|Em Andamento\""
    return 3
  fi

  local state_json
  state_json=$("${SCRIPT_DIR}/optimus-state-read.sh" "$task_id")
  local rc=$?
  if [ "$rc" -ne 0 ]; then
    # Bubble up state-read's error verbatim so the caller sees the original
    # code/message/hint instead of a re-wrapped one.
    printf '%s\n' "$state_json"
    return "$rc"
  fi

  if ! command -v jq >/dev/null 2>&1; then
    emit_error "jq_missing" "jq is required but not installed" "brew install jq (macOS) or apt install jq (Linux)"
    return 2
  fi

  local current
  current=$(printf '%s' "$state_json" | jq -r '.data.task_status')

  # Split expected on '|' into a JSON array for the output, and check membership.
  local passes="false" reason=""
  # shellcheck disable=SC2206
  local IFS='|'
  local -a expected_arr=($expected)
  IFS=$' \t\n'
  for s in "${expected_arr[@]}"; do
    if [ "$current" = "$s" ]; then
      passes="true"
      break
    fi
  done

  if [ "$passes" = "false" ]; then
    reason="Task ${task_id} has status '${current}', expected one of: ${expected}"
  fi

  # Re-build expected_one_of as proper JSON array via jq.
  local expected_json
  expected_json=$(printf '%s\n' "${expected_arr[@]}" | jq -R . | jq -sc .)

  jq -nc \
    --arg id "$task_id" \
    --arg current "$current" \
    --argjson expected "$expected_json" \
    --argjson passes "$passes" \
    --arg reason "$reason" '
    {
      status: "ok",
      error: null,
      data: {
        task_id: $id,
        current_status: $current,
        expected_one_of: $expected,
        passes: $passes,
        reason: $reason
      }
    }
  '
}

main() {
  case "${1:-}" in
    --explain|explain) cmd_explain ;;
    -h|--help|"")
      cat <<'EOF'
usage: MAIN_WORKTREE=/repo optimus-task-gate.sh <TASK_ID> --expected="STATUS|STATUS|..."

Validates that the task's current state.json status matches one of the
expected values. Returns data.passes=true/false; a failing gate is NOT a
script error.

Valid status values:
  Pendente, "Validando Spec", "Em Andamento", "Validando Impl", DONE, Cancelado

Subcommands:
  --explain     Print JSON schema describing this script.
  --help        Show this help text.

Example:
  MAIN_WORKTREE=/repo optimus-task-gate.sh T-003 \
    --expected="Validando Spec|Em Andamento"
EOF
      ;;
    *) cmd_check "$@" ;;
  esac
}

main "$@"
