#!/usr/bin/env python3
"""
Generates the OpenCode commands directory from per-plugin SKILLs.

Background: OpenCode (sst/opencode) does not provide a marketplace or per-
plugin namespacing in the documented behavior. Slash commands are
discovered as flat filenames under `~/.config/opencode/commands/` (or the
project-level `.opencode/commands/`). To avoid colliding with the user's
other commands we prefix every Optimus command with `optimus-` — so the
17 stages and their aliases surface as `/optimus-plan`, `/optimus-sp`,
`/optimus-build`, etc. (the bare form, mirroring the Droid invocation
convention).

For every plugin entry in `.factory-plugin/marketplace.json` (the source of
truth for the plugin list) the script emits:

  - `commands/opencode/optimus-<plugin>.md`     main command — frontmatter
                                                 description from SKILL.md,
                                                 body invokes the
                                                 `optimus-<plugin>` skill
                                                 directly (skill name in the
                                                 SKILL.md frontmatter).
  - `commands/opencode/optimus-<alias>.md`      alias — same body, frontmatter
                                                 description from the
                                                 per-plugin alias source.

Body convention: rather than chaining `/optimus-X $ARGUMENTS` redirects
(which would require slash commands inside slash commands), each command
file — main and alias — invokes the underlying skill directly. This works
because OpenCode's skill discovery walks `~/.config/opencode/skills/` (and
`.claude/skills/`) and finds the skill by its frontmatter `name`.

The Claude / Droid surfaces are NOT touched. Run after editing a SKILL.md
or alias body so the OpenCode commands stay in sync. The script is
idempotent — running it twice produces no diff. Tests in
`scripts/test_skill_consistency.py` (class `TestOpenCodeCommandsSync`)
enforce that this script was run before commit.

Usage: python3 scripts/sync-opencode-commands.py
"""
from __future__ import annotations

import sys
from pathlib import Path

from _sync_commands_common import (
    REPO_ROOT,
    load_plugin_names,
    load_skill_description,
    normalize_description,
    parse_frontmatter,
    per_plugin_alias_files,
    write_if_changed,
)

OPENCODE_COMMANDS_DIR = REPO_ROOT / "commands" / "opencode"


def render_main_command(plugin: str) -> str:
    """Render `commands/opencode/optimus-<plugin>.md` as a thin skill invoker.

    OpenCode skill discovery uses the frontmatter `name` field as the
    lookup key. Each Optimus skill is named `optimus-<plugin>` in its
    SKILL.md frontmatter, so we reference it by that exact identifier.

    Slash references in the description are left unrewritten — they already
    use the `/optimus-<X>` form which matches the OpenCode bare-name
    invocation surface (`/optimus-plan`, `/optimus-build`, ...).
    """
    description = normalize_description(load_skill_description(plugin))
    return (
        f"---\n"
        f"description: {description}\n"
        f"---\n"
        f"\n"
        f"Invoke the `optimus-{plugin}` skill. Arguments: $ARGUMENTS\n"
    )


def render_alias_command(plugin: str, alias_path: Path) -> str:
    """Render `commands/opencode/optimus-<alias>.md` for an alias.

    Reads the source alias file from `<plugin>/commands/<alias>.md`. We
    keep the description as-is (it already references `/optimus-<plugin>`,
    matching the OpenCode bare-name form) and replace the body with a
    direct skill invocation — avoiding command-chaining inside OpenCode.
    """
    raw = alias_path.read_text()
    fm, _ = parse_frontmatter(raw)
    description = normalize_description(fm.get("description") or "")
    return (
        f"---\n"
        f"description: {description}\n"
        f"---\n"
        f"\n"
        f"Invoke the `optimus-{plugin}` skill. Arguments: $ARGUMENTS\n"
    )


def main() -> int:
    plugin_names = load_plugin_names()
    if not plugin_names:
        print("ERROR: marketplace.json has no plugins", file=sys.stderr)
        return 1

    OPENCODE_COMMANDS_DIR.mkdir(parents=True, exist_ok=True)
    expected_files: set[str] = set()
    main_count = 0
    alias_count = 0

    for plugin in plugin_names:
        main_content = render_main_command(plugin)
        main_target = OPENCODE_COMMANDS_DIR / f"optimus-{plugin}.md"
        write_if_changed(main_target, main_content)
        expected_files.add(main_target.name)
        main_count += 1

    for plugin_name, alias_file in per_plugin_alias_files():
        alias_content = render_alias_command(plugin_name, alias_file)
        # alias_file.stem is e.g. "sp" — the OpenCode filename prefixes it
        # with `optimus-` so the resulting slash command is `/optimus-sp`.
        alias_target = OPENCODE_COMMANDS_DIR / f"optimus-{alias_file.stem}.md"
        write_if_changed(alias_target, alias_content)
        expected_files.add(alias_target.name)
        alias_count += 1

    # Remove orphaned files this run did not produce.
    for existing in OPENCODE_COMMANDS_DIR.glob("*.md"):
        if existing.name not in expected_files:
            existing.unlink()

    print(
        f"Generated {main_count} main commands and {alias_count} aliases "
        f"under {OPENCODE_COMMANDS_DIR.relative_to(REPO_ROOT)}/."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
