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
                                     SKILL.md, body is the SKILL body with all
                                     `/optimus-<X>` references rewritten to
                                     `/optimus:<X>`.
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

import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MARKETPLACE_JSON = REPO_ROOT / ".factory-plugin" / "marketplace.json"
COMMANDS_DIR = REPO_ROOT / "commands"

# Matches `/optimus-<word>` slash-command references. The leading `/` is
# REQUIRED — bare mentions like `optimus-build` (used as skill names) must be
# left alone. The captured group `<X>` is preserved when rewriting to
# `/optimus:<X>`.
SLASH_REF_RE = re.compile(r"/optimus-([a-z][a-z0-9-]*)")


def rewrite_slash_refs(text: str) -> str:
    """Substitute `/optimus-<X>` with `/optimus:<X>` (slash-prefixed only)."""
    return SLASH_REF_RE.sub(r"/optimus:\1", text)


def parse_frontmatter(text: str) -> tuple[dict, str]:
    """Parse YAML-ish frontmatter at the start of a markdown file.

    Frontmatter is bounded by `---` lines at the very top. Returns
    `(frontmatter_dict, body)`. If no frontmatter, returns `({}, text)`.

    The script only needs `description`, so this implementation extracts
    that field directly with regex. SKILL.md frontmatter blocks contain
    structured fields (examples, trigger, skip_when, etc.) with mixed
    quoting that don't all parse cleanly under strict YAML; the regex
    approach side-steps those edge cases without losing fidelity for the
    one field we care about.

    Supports three `description:` forms observed in the codebase:
      1. quoted single line:   `description: "..."`
      2. unquoted single line: `description: ...`
      3. folded multiline:     `description: >\n  line1\n  line2\n  ...`
    """
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---\n", 4)
    if end == -1:
        return {}, text
    fm_block = text[4:end]
    body = text[end + len("\n---\n") :]

    data: dict[str, str] = {}
    desc = _extract_description(fm_block)
    if desc is not None:
        data["description"] = desc
    return data, body


def _extract_description(fm_block: str) -> str | None:
    """Pull the `description` field out of a frontmatter block, supporting
    the three forms documented in `parse_frontmatter`.
    """
    lines = fm_block.splitlines()
    for i, line in enumerate(lines):
        m = re.match(r"^description:\s*(.*)$", line)
        if not m:
            continue
        rest = m.group(1).strip()
        # Form 3: folded multiline (`>` or `|` indicator). Collect indented
        # continuation lines until a non-indented line appears.
        if rest in (">", "|", ">-", "|-", ">+", "|+"):
            chunks = []
            for cont in lines[i + 1 :]:
                if cont.strip() == "":
                    chunks.append("")
                    continue
                if cont.startswith((" ", "\t")):
                    chunks.append(cont.strip())
                else:
                    break
            return " ".join(c for c in chunks if c)
        # Forms 1 & 2: same line. Strip surrounding double-quotes if present.
        if len(rest) >= 2 and rest.startswith('"') and rest.endswith('"'):
            return rest[1:-1]
        return rest
    return None


def normalize_description(value: str) -> str:
    """Collapse whitespace so the description fits on a single frontmatter line.

    SKILL.md descriptions can be folded multiline strings (`description: >`).
    Claude command frontmatter expects a single-line value, so we squash all
    interior whitespace runs to one space and strip surrounding whitespace.
    """
    return re.sub(r"\s+", " ", value).strip()


def write_if_changed(path: Path, content: str) -> bool:
    """Write `content` to `path` only if the file would actually change.

    Returns True when the file was created or rewritten. This keeps the script
    idempotent: a second run produces zero filesystem mutations.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_text() == content:
        return False
    path.write_text(content)
    return True


def render_main_command(plugin: str) -> str:
    """Render the top-level `commands/<plugin>.md` file content.

    Reads the per-plugin SKILL.md, extracts the description, rewrites slash
    references in the body, and assembles a single file with single-line
    frontmatter.
    """
    skill_path = REPO_ROOT / plugin / "skills" / f"optimus-{plugin}" / "SKILL.md"
    if not skill_path.is_file():
        raise FileNotFoundError(f"SKILL.md not found: {skill_path}")
    raw = skill_path.read_text()
    fm, body = parse_frontmatter(raw)
    description = fm.get("description") or ""
    # Rewrite slash refs in the description too — it can mention sister
    # commands (e.g., `done` mentions `/optimus-pr-check` as a recommended
    # action when reviewers flag changes).
    description = normalize_description(rewrite_slash_refs(description))
    new_body = rewrite_slash_refs(body)
    # Body from the SKILL already starts with a newline run; ensure the file
    # ends with exactly one trailing newline.
    return f"---\ndescription: {description}\n---\n{new_body.rstrip()}\n"


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
    description = normalize_description(rewrite_slash_refs(description))
    new_body = rewrite_slash_refs(body)
    return f"---\ndescription: {description}\n---\n{new_body.rstrip()}\n"


def load_plugin_names() -> list[str]:
    """Return plugin names from the Droid marketplace (source of truth)."""
    if not MARKETPLACE_JSON.is_file():
        raise FileNotFoundError(f"Marketplace JSON not found: {MARKETPLACE_JSON}")
    data = json.loads(MARKETPLACE_JSON.read_text())
    plugins = data.get("plugins", [])
    return [p["name"] for p in plugins]


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
        alias_dir = REPO_ROOT / plugin / "commands"
        if alias_dir.is_dir():
            for alias_file in sorted(alias_dir.glob("*.md")):
                alias_content = render_alias_command(plugin, alias_file)
                alias_target = COMMANDS_DIR / alias_file.name
                write_if_changed(alias_target, alias_content)
                expected_files.add(alias_target.name)
                alias_count += 1

    # Remove orphaned files: anything in commands/ that this run did not
    # produce. Keeps the directory clean when a plugin is removed from the
    # marketplace.
    for existing in COMMANDS_DIR.glob("*.md"):
        if existing.name not in expected_files:
            existing.unlink()

    print(f"Generated {main_count} main commands and {alias_count} aliases.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
