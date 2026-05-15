# OpenCode platform support

Optimus supports three runtimes: Droid (Factory), Claude Code, and
[OpenCode](https://opencode.ai). This document covers what's specific to
the OpenCode layer — how install works without a plugin marketplace,
what to expect at the slash-command level, and the known gaps relative
to the other two platforms.

## Install

OpenCode does not provide a plugin marketplace or `opencode plugin install`
flow analogous to Droid or Claude Code. Distribution is filesystem-based.

1. Clone the Optimus repository:

   ```bash
   git clone https://github.com/alexgarzao/optimus ~/optimus
   ```

2. Run the sync skill from inside that clone, or via Make:

   ```bash
   cd ~/optimus
   make sync-plugins
   ```

   The sync script auto-detects OpenCode (`command -v opencode`) and creates
   symlinks under `~/.config/opencode/` back to the repo:

   ```
   ~/.config/opencode/skills/optimus-<plugin>/   → <repo>/<plugin>/skills/optimus-<plugin>/
   ~/.config/opencode/commands/optimus-<cmd>.md  → <repo>/commands/opencode/optimus-<cmd>.md
   ```

3. Reopen OpenCode. The 17 commands surface as `/optimus-<command>` and
   their short aliases as `/optimus-<alias>` (e.g. `/optimus-plan`,
   `/optimus-sp`).

The OpenCode config directory can be overridden via
`OPENCODE_CONFIG_DIR=<path>` when running the sync script. The default
follows the XDG Base Directory spec — `${XDG_CONFIG_HOME:-$HOME/.config}/opencode`.

## Staying up to date

Two paths work:

- **Edits in the clone** are visible to OpenCode immediately (symlinks),
  no re-sync needed.
- **`git pull` upstream** also propagates instantly through the symlinks.
  Re-run `/optimus-sync` only when:
  - The repo added new commands or removed old ones (link set changed).
  - Some commands' filenames changed (rename).

## Why bare names instead of `/optimus:<command>` namespacing

OpenCode's documented behavior maps a filename to a slash command
(`commands/test.md` → `/test`). Subdirectory namespacing is not
documented. Optimus uses flat filenames prefixed with `optimus-` so the
commands are clearly attributable to Optimus and don't collide with the
user's other commands. The resulting invocation form
(`/optimus-<command>`) mirrors the Droid convention rather than the
Claude Code `/optimus:<command>` form.

If OpenCode adds explicit `name:`-frontmatter or subdir-namespacing
support in a way that maps `commands/optimus/plan.md` to `/optimus:plan`,
this generator can be updated to produce that layout instead.

## Known limitations

| Gap | Detail |
|-----|--------|
| No marketplace | There is no `opencode plugin install` flow. Distribution is symlink-based. Users must clone the repo. |
| No `optimus:` namespace | Commands use bare names with an `optimus-` prefix (`/optimus-plan`), matching the Droid convention rather than the Claude Code namespaced form. |
| No iTerm2 hook | The Claude Code-only `optimus-skill-loader.sh` hook (badge, tab color, subtitle per stage) is not ported. Stages run normally but without per-tab visual feedback. Tracking issue: future port to an OpenCode plugin using the `tui.prompt.append` event. |
| Ring is a prerequisite | Optimus skills dispatch Ring (`ring:*`) agents. Optimus does not install or symlink Ring artifacts — users must have Ring functioning in their OpenCode runtime independently (typically via their own clone of the Ring repo or other distribution mechanism). |

## Conflict handling

If OpenCode is reading from `~/.config/opencode/skills/` or `commands/`
and the sync target path already contains a real file (not a symlink),
the sync logs a `FAIL` for that entry and **does not overwrite the user's
file**. Resolve manually by moving the conflicting file out of the way
and re-running `/optimus-sync`.

OpenCode may also read from `~/.claude/skills/` natively (per its
[skills docs](https://opencode.ai/docs/skills/)). If a user has Optimus
installed via Claude Code and additionally syncs OpenCode, both
mechanisms expose the same skills — no functional conflict but the user
may see duplicate entries in skill auto-discovery.

## Verifying install

After `/optimus-sync`, confirm the symlinks landed correctly:

```bash
ls -la ~/.config/opencode/skills/ | grep optimus-
ls -la ~/.config/opencode/commands/ | grep optimus-
```

Each entry should be a symlink (`->`) pointing back into the cloned
Optimus repo. Open OpenCode and type `/` — the autocomplete should list
`/optimus-plan`, `/optimus-build`, `/optimus-help`, and so on.

## Uninstall

```bash
find ~/.config/opencode/skills -maxdepth 1 -name 'optimus-*' -delete
find ~/.config/opencode/commands -maxdepth 1 -name 'optimus-*.md' -delete
```

Or remove the cloned repo directory and re-run `/optimus-sync` — the
orphan sweep removes broken symlinks automatically when the source
disappears.
