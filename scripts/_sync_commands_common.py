"""Shared helpers for the per-platform command generators.

Two generators consume this module:

  - `sync-claude-commands.py` writes `commands/<name>.md` (Claude Code surface).
    Slash references in the rewritten bodies are namespaced (`/optimus:X`).

  - `sync-opencode-commands.py` writes `commands/opencode/<name>.md` (OpenCode
    surface). OpenCode does not have plugin-level namespacing in its
    documented behavior, so commands use the bare `optimus-<X>` prefix.

The shared functions handle frontmatter parsing, slash-reference rewriting,
description normalization, idempotent writes, and marketplace enumeration.
Per-target rendering differences live in the consumer scripts.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MARKETPLACE_JSON = REPO_ROOT / ".factory-plugin" / "marketplace.json"

# Matches `/optimus-<word>` slash-command references. The leading `/` is
# REQUIRED — bare mentions like `optimus-build` (used as skill names) must be
# left alone. The captured group `<X>` is preserved when rewriting.
SLASH_REF_RE = re.compile(r"/optimus-([a-z][a-z0-9-]*)")


def rewrite_slash_refs_to_namespaced(text: str) -> str:
    """Substitute `/optimus-<X>` with `/optimus:<X>` (Claude form)."""
    return SLASH_REF_RE.sub(r"/optimus:\1", text)


def parse_frontmatter(text: str) -> tuple[dict, str]:
    """Parse YAML-ish frontmatter at the start of a markdown file.

    Frontmatter is bounded by `---` lines at the very top. Returns
    `(frontmatter_dict, body)`. If no frontmatter, returns `({}, text)`.

    Only the `description` field is extracted (via regex) — see
    `_extract_description` for the supported forms.
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
    """Pull the `description` field out of a frontmatter block.

    Supports three forms observed in the codebase:
      1. quoted single line:   `description: "..."`
      2. unquoted single line: `description: ...`
      3. folded multiline:     `description: >\n  line1\n  line2\n  ...`
    """
    lines = fm_block.splitlines()
    for i, line in enumerate(lines):
        m = re.match(r"^description:\s*(.*)$", line)
        if not m:
            continue
        rest = m.group(1).strip()
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
        if len(rest) >= 2 and rest.startswith('"') and rest.endswith('"'):
            return rest[1:-1]
        return rest
    return None


def normalize_description(value: str) -> str:
    """Collapse whitespace so the description fits on a single frontmatter line."""
    return re.sub(r"\s+", " ", value).strip()


def write_if_changed(path: Path, content: str) -> bool:
    """Write `content` to `path` only if the file would actually change.

    Keeps generators idempotent: a second run produces zero filesystem mutations.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_text() == content:
        return False
    path.write_text(content)
    return True


def load_plugin_names() -> list[str]:
    """Return plugin names from the Droid marketplace (source of truth)."""
    if not MARKETPLACE_JSON.is_file():
        raise FileNotFoundError(f"Marketplace JSON not found: {MARKETPLACE_JSON}")
    data = json.loads(MARKETPLACE_JSON.read_text())
    plugins = data.get("plugins", [])
    return [p["name"] for p in plugins]


def load_skill_description(plugin: str) -> str:
    """Return the normalized description from `<plugin>/skills/optimus-<plugin>/SKILL.md`."""
    skill_path = REPO_ROOT / plugin / "skills" / f"optimus-{plugin}" / "SKILL.md"
    if not skill_path.is_file():
        raise FileNotFoundError(f"SKILL.md not found: {skill_path}")
    raw = skill_path.read_text()
    fm, _ = parse_frontmatter(raw)
    return fm.get("description") or ""


def per_plugin_alias_files() -> list[tuple[str, Path]]:
    """Enumerate `<plugin>/commands/<alias>.md` files across all plugins.

    Returns list of `(plugin_name, alias_path)` tuples. The plugin name is
    derived from the source path (`<plugin>/commands/<alias>.md`) so callers
    can rewrite the alias body to point at the matching main command.
    """
    out: list[tuple[str, Path]] = []
    for cmd_file in sorted(REPO_ROOT.glob("*/commands/*.md")):
        plugin_name = cmd_file.parent.parent.name
        out.append((plugin_name, cmd_file))
    return out
