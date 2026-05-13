#!/bin/bash
# UserPromptSubmit hook for /optimus:* slash commands.
#
# Why this exists
# ---------------
# Claude Code's Skill-tool injection contract promises that when a user fires
# a slash command (e.g. /optimus:plan T-99), the harness wraps the relevant
# SKILL.md body in a <command-name> tag so the model can read the protocol.
# Empirically, current Claude Code builds inject only the tag's name — never
# the body — so the model has no protocol context for the skill and the
# canonical iTerm2 badge + tab-color setter inside the SKILL.md never runs.
#
# This hook is a deterministic workaround. On every UserPromptSubmit it:
#
#   1. Inspects the raw prompt. If it doesn't begin with /optimus:<name>,
#      exits 0 silently (zero overhead for unrelated prompts).
#
#   2. Emits an iTerm2 badge (OSC 1337 SetBadgeFormat) and tab color
#      (OSC 6 SetColors) directly to the controlling TTY. The PPID chain
#      is walked up to 8 levels because Claude Code spawns the hook from
#      an intermediate shim whose own TTY is "?" — the real iTerm2 ttys
#      is one or two hops up. Stage → color mapping matches the canonical
#      mapping inside the SKILL.md files (PLAN=blue, BUILD=green,
#      REVIEW=yellow, DONE=gray, RESUME/BATCH=purple).
#
#   3. Streams the corresponding SKILL.md to stdout. Claude Code captures
#      stdout from UserPromptSubmit hooks and surfaces it to the model as
#      additional context for the turn. Files larger than ~50 KB are
#      persisted to a tool-results file and only a 2 KB preview reaches
#      the model — large skills (plan, review, pr-check) therefore arrive
#      truncated. The badge still lands regardless of truncation because
#      it is emitted by this shell process, not the model.
#
# Failure mode policy: always exit 0. Blocking the user's prompt because
# of a missing TTY or a stat() race would be worse than a missing badge.
#
# Optional debug: set OPTIMUS_HOOK_DEBUG=1 in the environment to log
# every invocation to ~/.cache/optimus/skill-loader.log.

set -u
set -o pipefail

# ---------------------------------------------------------------------------
# Optional debug logging
# ---------------------------------------------------------------------------
LOG=""
if [ -n "${OPTIMUS_HOOK_DEBUG:-}" ]; then
  LOG="${XDG_CACHE_HOME:-$HOME/.cache}/optimus/skill-loader.log"
  mkdir -p "$(dirname "$LOG")" 2>/dev/null || LOG=""
fi
log() { [ -n "$LOG" ] && echo "$@" >> "$LOG" 2>/dev/null || true; }

log "=== $(date -Iseconds) PID=$$ PPID=$PPID ==="
log "env LC_TERMINAL=${LC_TERMINAL:-<unset>} TERM_PROGRAM=${TERM_PROGRAM:-<unset>} CLAUDE_PLUGIN_ROOT=${CLAUDE_PLUGIN_ROOT:-<unset>}"

# ---------------------------------------------------------------------------
# Parse stdin: extract the user prompt
# ---------------------------------------------------------------------------
# Claude Code passes a JSON envelope on stdin. The documented field name
# is `user_prompt` but real payloads use `prompt`. Try both for forward
# compatibility, and fall back to `userInput` for older builds.
input="$(cat || true)"
log "--- raw stdin ---"; log "$input"; log "--- end raw stdin ---"

prompt="$(printf '%s' "$input" | jq -r '.prompt // .user_prompt // .userInput // empty' 2>/dev/null || true)"
cwd_from_stdin="$(printf '%s' "$input" | jq -r '.cwd // empty' 2>/dev/null || true)"
log "extracted prompt=$prompt"
log "extracted cwd=$cwd_from_stdin"

# Match /optimus:<name> [<first-arg>] at start of prompt.
# BASH_REMATCH[1] = skill name (or alias the user typed)
# BASH_REMATCH[3] = first whitespace-separated arg (task ID, PR number, ...) or empty
if ! [[ "$prompt" =~ ^/optimus:([a-zA-Z0-9_-]+)([[:space:]]+([^[:space:]]+))? ]]; then
  exit 0
fi
cmd="${BASH_REMATCH[1]}"
task_arg="${BASH_REMATCH[3]:-}"

# ---------------------------------------------------------------------------
# Resolve alias → canonical skill folder name
# ---------------------------------------------------------------------------
# Aliases listed in /optimus:help. Keeping the mapping inline avoids a
# manifest read on every prompt.
case "$cmd" in
  hp)  skill_name=help ;;
  cr)  skill_name=coderabbit-review ;;
  qr)  skill_name=quick-report ;;
  dn)  skill_name=done ;;
  rs)  skill_name=resolve ;;
  dr)  skill_name=deep-review ;;
  im)  skill_name=import ;;
  rv)  skill_name=review ;;
  rsm) skill_name=resume ;;
  t)   skill_name=tasks ;;
  bd)  skill_name=build ;;
  sy)  skill_name=sync ;;
  ddr) skill_name=deep-doc-review ;;
  prc) skill_name=pr-check ;;
  rp)  skill_name=report ;;
  sp)  skill_name=plan ;;
  bt)  skill_name=batch ;;
  *)   skill_name="$cmd" ;;
esac

# Resolve SKILL.md path. Inside an installed Claude Code plugin, the source
# lives at ${CLAUDE_PLUGIN_ROOT}/<skill>/skills/optimus-<skill>/SKILL.md. If
# CLAUDE_PLUGIN_ROOT is not set (e.g. script invoked manually for debug),
# fall back to the user-installed copy under ~/.claude/skills/default/.
if [ -n "${CLAUDE_PLUGIN_ROOT:-}" ] && [ -f "${CLAUDE_PLUGIN_ROOT}/${skill_name}/skills/optimus-${skill_name}/SKILL.md" ]; then
  skill_md="${CLAUDE_PLUGIN_ROOT}/${skill_name}/skills/optimus-${skill_name}/SKILL.md"
elif [ -f "$HOME/.claude/skills/default/optimus-${skill_name}/SKILL.md" ]; then
  skill_md="$HOME/.claude/skills/default/optimus-${skill_name}/SKILL.md"
else
  log "SKILL.md not found for $skill_name"
  exit 0
fi

# ---------------------------------------------------------------------------
# Lifecycle gate: /optimus:done requires status "Validando Impl"
# ---------------------------------------------------------------------------
# Prevents the user from skipping /optimus:review after build. Reads
# ${MAIN_WORKTREE}/.optimus/state.json — resolved via git common-dir so
# the check works from inside a linked worktree too. Bypassable by
# passing --force anywhere after the task ID:
#   /optimus:done T-99 --force
#
# Permissive on missing infrastructure (no git, no state.json, no
# task_arg, no jq) so we never block users in non-optimus projects.
if [ "$skill_name" = "done" ] && [ -n "$task_arg" ] && ! [[ " $prompt " == *" --force "* ]]; then
  # Resolve main worktree. --git-common-dir is the canonical .git path
  # shared by all linked worktrees; its parent is the main worktree.
  # git returns a path that is relative to the directory passed via -C
  # (or to PWD if no -C). Normalize against the hook's stdin cwd so we
  # don't accidentally land in the cwd of the bash process itself.
  base_cwd="${cwd_from_stdin:-$PWD}"
  git_dir_raw="$(cd "$base_cwd" 2>/dev/null && git rev-parse --git-common-dir 2>/dev/null || true)"
  if [ -n "$git_dir_raw" ]; then
    case "$git_dir_raw" in
      /*) git_dir="$git_dir_raw" ;;
      *)  git_dir="${base_cwd}/${git_dir_raw}" ;;
    esac
    main_worktree="$(dirname "$git_dir")"
    state_file="${main_worktree}/.optimus/state.json"
    log "gate: state_file=$state_file"

    if [ -f "$state_file" ] && command -v jq >/dev/null 2>&1; then
      status="$(jq -r --arg id "$task_arg" '.[$id].status // "Pendente"' "$state_file" 2>/dev/null || echo "")"
      log "gate: task=$task_arg status=$status"

      if [ "$status" != "Validando Impl" ]; then
        case "$status" in
          "Pendente"|"")    reason="task has not started yet (no entry in state.json — implicit Pendente)" ;;
          "Validando Spec") reason="task is still in planning (/optimus:plan output not yet built)" ;;
          "Em Andamento")   reason="task was built but never reviewed — RUN /optimus:review ${task_arg} FIRST" ;;
          "DONE")           reason="task is already DONE (use /optimus:resume ${task_arg} to reopen)" ;;
          "Cancelado")      reason="task was cancelled" ;;
          *)                reason="task is in an unexpected status: ${status}" ;;
        esac
        {
          echo "BLOCKED: /optimus:done ${task_arg} requires status 'Validando Impl'."
          echo "Current status: ${status:-<none>}"
          echo "Reason: ${reason}"
          echo "Override with: /optimus:done ${task_arg} --force"
        } >&2
        log "gate: BLOCKED status=$status reason=$reason"
        exit 2
      fi
    fi
  fi
fi

# ---------------------------------------------------------------------------
# Step 1: deterministic stub badge
# ---------------------------------------------------------------------------
# Only stage-bearing skills (task lifecycle) receive a badge. Admin/info
# skills (help, tasks, report, sync, import, resolve, quick-report) leave
# the badge alone because they don't represent a focused work session.
case "$skill_name" in
  plan)                                            stage=PLAN ;;
  build)                                           stage=BUILD ;;
  review|deep-review|coderabbit-review|pr-check)   stage=REVIEW ;;
  done)                                            stage=DONE ;;
  resume)                                          stage=RESUME ;;
  batch)                                           stage=BATCH ;;
  *)                                               stage="" ;;
esac

log "stage=$stage skill_name=$skill_name cmd=$cmd task_arg=$task_arg"

if [ -n "$stage" ]; then
  # Find a writable TTY by walking up the parent-process chain. The hook's
  # immediate parent is a Claude Code shim with tty=? (not user-attached);
  # one or two hops up we hit the iTerm2 ttysNNN that owns the visible
  # terminal. 8 levels is comfortably more than ever needed in practice.
  pid="$PPID"
  target_tty=""
  for _ in 1 2 3 4 5 6 7 8; do
    if [ -z "$pid" ] || [ "$pid" = "1" ]; then break; fi
    target_tty="$(ps -o tty= -p "$pid" 2>/dev/null | tr -d ' ')"
    log "  walk pid=$pid tty=$target_tty"
    case "$target_tty" in
      ""|"?"|"??")
        pid="$(ps -o ppid= -p "$pid" 2>/dev/null | tr -d ' ')"
        target_tty=""
        ;;
      *) break ;;
    esac
  done
  log "resolved target_tty=$target_tty writable=$([ -w "/dev/$target_tty" ] && echo yes || echo no)"

  if [ -n "$target_tty" ] && [ -w "/dev/$target_tty" ]; then
    # Badge label preserves the user's typed form (alias or full name).
    # Line 1: OPTIMUS:<CMD-UPPER>, Line 2: first arg or "loading…"
    cmd_upper="$(printf '%s' "$cmd" | tr '[:lower:]' '[:upper:]')"
    badge_line2="${task_arg:-loading…}"
    badge_b64="$(printf 'OPTIMUS:%s\n%s' "$cmd_upper" "$badge_line2" | base64 | tr -d '\n')"
    printf '\e]1337;SetBadgeFormat=%s\a' "$badge_b64" > "/dev/$target_tty" 2>/dev/null || true

    # Title text: single-line "OPTIMUS:<CMD> <ARG>" (omit trailing space
    # when no arg). Emitted on two channels because iTerm2 surfaces them
    # differently:
    #
    #   1. OSC 1337;SetTabName  — user-set name; shows in the tab strip
    #      and survives shell prompt redraws (precmd in oh-my-zsh themes
    #      doesn't write here).
    #
    #   2. OSC 0  — icon + window title; this is the channel iTerm2 uses
    #      to compute the per-session title bar (the strip above each
    #      pane that normally shows "caffeinate (claude)" or similar
    #      auto-detected job names). SetTabName alone does NOT override
    #      the session title bar — OSC 0 does.
    if [ -n "$task_arg" ]; then
      title_text="OPTIMUS:${cmd_upper} ${task_arg}"
    else
      title_text="OPTIMUS:${cmd_upper}"
    fi
    title_b64="$(printf '%s' "$title_text" | base64 | tr -d '\n')"
    printf '\e]1337;SetTabName=%s\a' "$title_b64" > "/dev/$target_tty" 2>/dev/null || true
    printf '\e]0;%s\a' "$title_text" > "/dev/$target_tty" 2>/dev/null || true

    # SetUserVar exposes the title content as \(user.optimus) so iTerm2
    # profiles configured with a custom Title format like
    #   \(user.optimus)
    # can render the stage + task ID. SetUserVar values must be base64.
    # The variable persists across the session and is empty until a
    # /optimus:* prompt fires the hook.
    optimus_var_b64="$(printf '%s' "$title_text" | base64 | tr -d '\n')"
    printf '\e]1337;SetUserVar=optimus=%s\a' "$optimus_var_b64" > "/dev/$target_tty" 2>/dev/null || true

    # Tab color: stage → RGB. Matches the canonical mapping inside the
    # SKILL.md files so the stub and the final mark_session call agree.
    case "$stage" in
      PLAN)   r=66;  g=135; b=245 ;;
      BUILD)  r=34;  g=197; b=94  ;;
      REVIEW) r=234; g=179; b=8   ;;
      DONE)   r=148; g=163; b=184 ;;
      *)      r=168; g=85;  b=247 ;;
    esac
    printf '\e]6;1;bg;red;brightness;%d\a\e]6;1;bg;green;brightness;%d\a\e]6;1;bg;blue;brightness;%d\a' \
      "$r" "$g" "$b" > "/dev/$target_tty" 2>/dev/null || true
    log "  badge emitted to /dev/$target_tty"
  fi
fi

# ---------------------------------------------------------------------------
# Step 2: inject SKILL.md into the model's context
# ---------------------------------------------------------------------------
printf '%s\n' "<optimus-skill-loader>"
printf 'Auto-loaded /optimus:%s → %s\n' "$cmd" "$skill_md"
printf 'Reason: the Skill tool in this harness build does not expand SKILL.md\n'
printf 'into <command-name> context, so this hook injects it manually.\n\n'
cat "$skill_md"
printf '\n%s\n' "</optimus-skill-loader>"
exit 0
