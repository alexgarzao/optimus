#!/usr/bin/env bash
# optimus-mark-session.sh
#
# Canonical iTerm2 session marker for Optimus stage skills. Wraps the two
# focus-independent visual signals — iTerm2 Badge (OSC 1337) + Tab Color
# (OSC 6) — so SKILL.md files reference one script instead of inlining
# ~60 lines of bash 5× across the stage skills.
#
# Source of truth for the algorithm: AGENTS.md Protocol "Terminal Identification".
# When the protocol changes, update both this file and AGENTS.md in lockstep.
#
# Usage:
#   optimus-mark-session.sh mark <STAGE> <TASK_ID> <TITLE>
#     STAGE in: PLAN | BUILD | REVIEW | DONE | RESUME | BATCH
#     Example: optimus-mark-session.sh mark BUILD T-003 "User Auth JWT"
#
#   optimus-mark-session.sh clear
#     Restores default badge + tab color at stage completion.
#
# Behavior outside iTerm2/macOS or when the parent TTY cannot be resolved
# (Docker, CI, divorced sessions): silent no-op, exit 0. Never fails the
# caller — the badge is informational and must not block the stage flow.

set -u

_optimus_resolve_tty() {
  # Walks up the parent process chain (4 levels) looking for a controlling
  # TTY. The Execute/Bash tool runs `bash -c` without a controlling TTY, so
  # we resolve the user's shell TTY via ps and write escape sequences there.
  local pid="$PPID" target_tty=""
  for _ in 1 2 3 4; do
    { [ -z "$pid" ] || [ "$pid" = "1" ]; } && break
    target_tty=$(ps -o tty= -p "$pid" 2>/dev/null | tr -d ' ')
    case "$target_tty" in
      ""|"?"|"??") pid=$(ps -o ppid= -p "$pid" 2>/dev/null | tr -d ' '); target_tty="" ;;
      *) break ;;
    esac
  done
  printf '%s' "$target_tty"
}

_optimus_emit() {
  local target_tty="$1" payload="$2"
  if [ -n "$target_tty" ] && [ -w "/dev/$target_tty" ]; then
    printf '%s' "$payload" > "/dev/$target_tty" 2>/dev/null || printf '%s' "$payload"
  else
    printf '%s' "$payload"
  fi
}

_optimus_in_iterm2() {
  [ "${LC_TERMINAL:-}" = "iTerm2" ] || [ "${TERM_PROGRAM:-}" = "iTerm.app" ]
}

cmd_mark() {
  local stage="${1:-}" task_id="${2:-}" title="${3:-}"
  if [ -z "$stage" ] || [ -z "$task_id" ]; then
    echo "usage: optimus-mark-session.sh mark <STAGE> <TASK_ID> [TITLE]" >&2
    return 2
  fi
  _optimus_in_iterm2 || return 0

  local target_tty
  target_tty=$(_optimus_resolve_tty)

  local badge_b64
  badge_b64=$(printf '%s %s\n%s' "$stage" "$task_id" "$title" | base64 | tr -d '\n')
  _optimus_emit "$target_tty" "$(printf '\e]1337;SetBadgeFormat=%s\a' "$badge_b64")"

  local r g b
  case "$stage" in
    PLAN)   r=66;  g=135; b=245 ;;  # blue
    BUILD)  r=34;  g=197; b=94  ;;  # green
    REVIEW) r=234; g=179; b=8   ;;  # yellow
    DONE)   r=148; g=163; b=184 ;;  # gray
    *)      r=168; g=85;  b=247 ;;  # purple (RESUME/BATCH/other)
  esac
  _optimus_emit "$target_tty" "$(printf '\e]6;1;bg;red;brightness;%d\a\e]6;1;bg;green;brightness;%d\a\e]6;1;bg;blue;brightness;%d\a' "$r" "$g" "$b")"
}

cmd_clear() {
  _optimus_in_iterm2 || return 0
  local target_tty
  target_tty=$(_optimus_resolve_tty)
  _optimus_emit "$target_tty" "$(printf '\e]1337;SetBadgeFormat=\a')"
  _optimus_emit "$target_tty" "$(printf '\e]6;1;bg;*;default\a')"
}

cmd_explain() {
  cat <<'EOF'
{
  "schema_version": "1",
  "script": "optimus-mark-session.sh",
  "subcommands": {
    "mark":  {"args": ["STAGE", "TASK_ID", "TITLE?"], "side_effect": "writes OSC 1337 + OSC 6 escape sequences to parent shell TTY"},
    "clear": {"args": [],                              "side_effect": "resets badge and tab color to terminal defaults"}
  },
  "stages": ["PLAN", "BUILD", "REVIEW", "DONE", "RESUME", "BATCH"],
  "no_op_when": ["LC_TERMINAL != iTerm2 && TERM_PROGRAM != iTerm.app", "parent TTY cannot be resolved"],
  "exit_codes": {"0": "ok (including silent no-op)", "2": "usage error"}
}
EOF
}

main() {
  local sub="${1:-}"
  shift || true
  case "$sub" in
    mark)    cmd_mark "$@" ;;
    clear)   cmd_clear "$@" ;;
    --explain|explain) cmd_explain ;;
    ""|-h|--help)
      cat <<'EOF'
usage: optimus-mark-session.sh <subcommand> [args]

Subcommands:
  mark <STAGE> <TASK_ID> [TITLE]   Set iTerm2 badge + tab color for stage.
  clear                            Reset badge and tab color.
  --explain                        Print JSON schema describing this script.

STAGE in: PLAN | BUILD | REVIEW | DONE | RESUME | BATCH
Outside iTerm2/macOS this is a silent no-op.
EOF
      ;;
    *)
      echo "optimus-mark-session.sh: unknown subcommand '$sub'" >&2
      return 2
      ;;
  esac
}

main "$@"
