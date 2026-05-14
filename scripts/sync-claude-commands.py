#!/usr/bin/env python3
"""
Generates the top-level Claude Code commands directory from per-plugin SKILLs.

Background: Optimus ships a SINGLE Claude Code plugin (`optimus`) whose source
is the repo root. Claude Code discovers commands at `<plugin-source>/commands/`
and exposes each one as `/optimus:<command>` thanks to the namespace prefix.
Per-plugin SKILL.md bodies still live under `<plugin>/skills/optimus-<plugin>/`
(shared with the Droid layer), so this script flattens them into a single
`commands/` directory at the repo root.

For every plugin entry in `.factory-plugin/marketplace.json` (the source of
truth for the plugin list) the script emits:

  - `commands/<plugin>.md`          main command — frontmatter description from
                                     SKILL.md, body is a thin Skill-tool
                                     delegator that invokes `optimus:<plugin>`.
  - `commands/<alias>.md`           when `<plugin>/commands/<alias>.md` exists
                                     in the per-plugin layout. The body
                                     becomes `/optimus:<plugin> $ARGUMENTS`.

The Droid layer is NOT touched. Run after editing a SKILL.md or alias body so
the Claude commands stay in sync. The script is idempotent — running it twice
produces no diff. Tests in `scripts/test_skill_consistency.py` (class
`TestClaudeCommandsSync`) enforce that this script was run before commit.

Usage: python3 scripts/sync-claude-commands.py
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
    rewrite_slash_refs_to_namespaced,
    write_if_changed,
)

COMMANDS_DIR = REPO_ROOT / "commands"


def render_main_command(plugin: str) -> str:
    """Render the top-level `commands/<plugin>.md` file content as a thin wrapper.

    The slash command surface for Claude Code is a thin delegator: instead of
    duplicating the entire SKILL.md body (which historically grew each
    `commands/<plugin>.md` to ~600+ lines and totalled ~11K lines repo-wide),
    this emits a 5-line stub that asks Claude to invoke the matching skill
    via the Skill tool. The skill description (taken from the SKILL.md
    frontmatter) is preserved so `/help` and the slash-command picker still
    surface the same one-liner.

    The skill itself (`optimus-<plugin>`) is auto-registered by the harness
    from `<plugin>/skills/optimus-<plugin>/SKILL.md` and contains the actual
    workflow. The Skill tool loads it on demand when Claude invokes it.
    """
    description = load_skill_description(plugin)
    # Rewrite slash refs in the description too — it can mention sister
    # commands (e.g., `done` mentions `/optimus-pr-check` as a recommended
    # action when reviewers flag changes).
    description = normalize_description(rewrite_slash_refs_to_namespaced(description))
    return (
        f"---\n"
        f"description: {description}\n"
        f"---\n"
        f"\n"
        f"Invoke the `optimus:{plugin}` skill via the Skill tool. "
        f"Arguments: $ARGUMENTS\n"
    )


def render_alias_command(plugin: str, alias_path: Path) -> str:
    """Render an alias `commands/<alias>.md` file content.

    Reads the source alias file from `<plugin>/commands/<alias>.md`, rewrites
    slash references in BOTH the frontmatter description (so it points at
    `/optimus:<plugin>`) and the body (`/optimus-<plugin> $ARGUMENTS` →
    `/optimus:<plugin> $ARGUMENTS`).
    """
    raw = alias_path.read_text()
    fm, body = parse_frontmatter(raw)
    description = fm.get("description") or ""
    description = normalize_description(rewrite_slash_refs_to_namespaced(description))
    new_body = rewrite_slash_refs_to_namespaced(body)
    return f"---\ndescription: {description}\n---\n{new_body.rstrip()}\n"


def main() -> int:
    plugin_names = load_plugin_names()
    if not plugin_names:
        print("ERROR: marketplace.json has no plugins", file=sys.stderr)
        return 1

    COMMANDS_DIR.mkdir(parents=True, exist_ok=True)
    expected_files: set[str] = set()
    main_count = 0
    alias_count = 0

    for plugin in plugin_names:
        # Main command
        main_content = render_main_command(plugin)
        main_target = COMMANDS_DIR / f"{plugin}.md"
        write_if_changed(main_target, main_content)
        expected_files.add(main_target.name)
        main_count += 1

    # Alias commands (zero or more per plugin)
    for plugin_name, alias_file in per_plugin_alias_files():
        alias_content = render_alias_command(plugin_name, alias_file)
        alias_target = COMMANDS_DIR / alias_file.name
        write_if_changed(alias_target, alias_content)
        expected_files.add(alias_target.name)
        alias_count += 1

    # Remove orphaned files at the repo-root level only — DO NOT recurse into
    # subdirectories (the OpenCode generator owns `commands/opencode/`).
    for existing in COMMANDS_DIR.glob("*.md"):
        if existing.name not in expected_files:
            existing.unlink()

    print(f"Generated {main_count} main commands and {alias_count} aliases.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
