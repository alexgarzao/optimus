#!/usr/bin/env python3
"""
Inlines referenced AGENTS.md protocols into each SKILL.md.

Problem: AGENTS.md lives at repo root but plugins are installed individually.
Skills reference "see AGENTS.md Protocol: X" but agents can't find AGENTS.md.

Solution: Append only the referenced protocols/patterns to each SKILL.md,
making each plugin self-contained.

Usage: python3 scripts/inline-protocols.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
AGENTS_MD = REPO_ROOT / "AGENTS.md"
MARKER_START = "<!-- INLINE-PROTOCOLS:START -->"
MARKER_END = "<!-- INLINE-PROTOCOLS:END -->"
HEADING_RE = re.compile(r'^(?:#{2,3})\s+(.+)$')
PROTOCOL_RE = re.compile(r'AGENTS\.md Protocol:\s*([^\n"]+)')
COMMON_PATTERN_RE = re.compile(r'AGENTS\.md\s*"Common Patterns\s*>\s*([^"]+)"')
FINDING_PRESENTATION_RE = re.compile(r'AGENTS\.md\s*"Finding Presentation"')

def parse_agents_md() -> dict[str, str]:
    """Parse AGENTS.md into named sections keyed by heading text."""
    if not AGENTS_MD.exists():
        print(f"ERROR: {AGENTS_MD} not found. Run from repo root.")
        sys.exit(1)
    lines = AGENTS_MD.read_text().splitlines()
    sections = {}
    current_key = None
    current_lines = []

    for line in lines:
        heading_match = HEADING_RE.match(line)
        if heading_match:
            title = heading_match.group(1).strip()
            if current_key:
                sections[current_key] = "\n".join(current_lines)
            current_key = title
            current_lines = [line]
        elif current_key:
            current_lines.append(line)

    if current_key:
        sections[current_key] = "\n".join(current_lines)

    return sections


def extract_refs_from_content(content: str) -> set[str]:
    """Extract all AGENTS.md references from SKILL.md content (body only, not inlined block)."""
    content = strip_existing_inline(content)
    refs: set[str] = set()

    # Protocol references: "see AGENTS.md Protocol: X"
    for m in PROTOCOL_RE.finditer(content):
        name = m.group(1).strip()
        # Split at sentence boundary (". " followed by uppercase letter) to remove
        # trailing sentences like ". Use stage=..." or ". Also load:"
        name = re.split(r'\.\s+(?=[A-Z])', name)[0].strip()
        # Clean remaining trailing context (comma clauses, bold markers, semicolons)
        name = re.split(r',\s+(?:with |followed )|;\s|\*\*', name)[0].strip()
        name = name.rstrip('.):')
        refs.add(f"Protocol: {name}")

    # Common pattern references: 'AGENTS.md "Common Patterns > X"'
    for m in COMMON_PATTERN_RE.finditer(content):
        name = m.group(1).strip().rstrip('.')
        refs.add(f"Common: {name}")

    # Finding Presentation references
    for m in FINDING_PRESENTATION_RE.finditer(content):
        refs.add("Common: Finding Presentation")

    return refs


def extract_refs_from_skill(skill_path: Path) -> set[str]:
    """Extract all AGENTS.md references from a SKILL.md file."""
    return extract_refs_from_content(skill_path.read_text())


def _normalize_key(key: str) -> str:
    """Strip parenthetical suffixes like (HARD BLOCK), (optional) for matching."""
    return re.sub(r'\s*\([^)]*\)\s*$', '', key).strip().lower()


def match_ref_to_section(ref: str, sections: dict[str, str]) -> str | None:
    """Match a reference name to a section key in AGENTS.md."""
    if ref.startswith("Protocol: "):
        proto_name = ref[len("Protocol: "):]
        proto_lower = proto_name.lower()
        # Try exact match (ignoring parenthetical suffixes)
        for key in sections:
            if key.startswith("Protocol: "):
                key_base = _normalize_key(key[len("Protocol: "):])
                if key_base == proto_lower:
                    return key
        # Try startswith match for partial names
        for key in sections:
            if key.startswith("Protocol: "):
                key_base = _normalize_key(key[len("Protocol: "):])
                if key_base.startswith(proto_lower):
                    return key
    elif ref.startswith("Common: "):
        pattern_name = ref[len("Common: "):]
        pattern_normalized = _normalize_key(pattern_name)
        # Try exact match first (both sides normalized)
        for key in sections:
            if _normalize_key(key) == pattern_normalized:
                return key
        # Try startswith match
        for key in sections:
            if _normalize_key(key).startswith(pattern_normalized):
                return key
    return None


def strip_existing_inline(content: str) -> str:
    """Remove previously inlined protocols section, preserving content after end marker."""
    start_idx = content.find(MARKER_START)
    if start_idx == -1:
        return content
    end_idx = content.find(MARKER_END)
    if end_idx == -1:
        print("  WARNING: MARKER_START found but MARKER_END missing — skipping strip to avoid data loss")
        return content
    after = content[end_idx + len(MARKER_END):]
    return content[:start_idx].rstrip() + after


def inline_protocols() -> None:
    """Main: inline referenced protocols into each SKILL.md."""
    sections = parse_agents_md()
    print(f"Parsed {len(sections)} sections from AGENTS.md")

    # Also include some foundational sections that provide context
    # for protocol references (e.g., State Management references state.json format)
    foundational = {}
    for key in ["File Location", "Valid Status Values (stored in state.json)",
                 "Task Spec Resolution", "Format Validation",
                 "Protocol: Resolve Main Worktree Path"]:
        if key in sections:
            foundational[key] = sections[key]

    # Find all SKILL.md files
    skill_files = sorted(REPO_ROOT.glob("*/skills/*/SKILL.md"))
    print(f"Found {len(skill_files)} SKILL.md files\n")

    total_inlined = 0

    for skill_path in skill_files:
        plugin_name = skill_path.parts[-4]  # e.g., "plan" from plan/skills/optimus-plan/SKILL.md
        try:
            raw_content = skill_path.read_text()
        except (OSError, UnicodeDecodeError) as e:
            print(f"  ERROR: {skill_path}: {e} — skipping")
            continue

        refs = extract_refs_from_content(raw_content)

        if not refs:
            print(f"  {plugin_name}: no AGENTS.md refs, skipping")
            continue

        # Match refs to sections
        matched: dict[str, str] = {}
        unmatched: list[str] = []
        for ref in sorted(refs):
            key = match_ref_to_section(ref, sections)
            if key:
                matched[ref] = key
            else:
                unmatched.append(ref)

        # Collect the sections to inline (deduplicated, ordered)
        sections_to_inline: dict[str, str] = {}
        for ref, key in sorted(matched.items(), key=lambda x: x[1]):
            if key not in sections_to_inline:
                sections_to_inline[key] = sections[key]

        # Also check if State Management is referenced -> include foundational state.json docs
        needs_state = any("State Management" in k for k in sections_to_inline)
        needs_taskspec = any("TaskSpec" in k for k in sections_to_inline)
        needs_format = any("tasks.md Validation" in k for k in sections_to_inline)
        # Any protocol that touches .optimus/ gitignored files needs the main-worktree
        # resolver. Include it whenever State Management, Session State, Increment Stage
        # Stats, or Initialize .optimus Directory is inlined.
        needs_worktree_resolver = any(
            any(trigger in k for trigger in (
                "State Management",
                "Session State",
                "Increment Stage Stats",
                "Initialize .optimus Directory",
            ))
            for k in sections_to_inline
        )

        extra: dict[str, str] = {}
        if needs_state and "File Location" in foundational:
            extra["File Location"] = foundational["File Location"]
        if needs_state and "Valid Status Values (stored in state.json)" in foundational:
            extra["Valid Status Values (stored in state.json)"] = foundational["Valid Status Values (stored in state.json)"]
        if needs_taskspec and "Task Spec Resolution" in foundational:
            extra["Task Spec Resolution"] = foundational["Task Spec Resolution"]
        if needs_format and "Format Validation" in foundational:
            extra["Format Validation"] = foundational["Format Validation"]
        if needs_worktree_resolver and "Protocol: Resolve Main Worktree Path" in foundational:
            # Do not duplicate if already explicitly referenced by the skill.
            if not any("Resolve Main Worktree Path" in k for k in sections_to_inline):
                extra["Protocol: Resolve Main Worktree Path"] = foundational["Protocol: Resolve Main Worktree Path"]

        content = strip_existing_inline(raw_content).rstrip() + "\n"

        inline_parts = []
        inline_parts.append(f"\n{MARKER_START}")
        inline_parts.append("## Shared Protocols (from AGENTS.md)")
        inline_parts.append("")
        inline_parts.append("The following protocols are referenced by this skill. They are")
        inline_parts.append("extracted from the Optimus AGENTS.md to make this plugin self-contained.")
        inline_parts.append("")

        # Add foundational context first
        for key, text in extra.items():
            if key not in sections_to_inline:
                inline_parts.append(text)
                inline_parts.append("")

        # Add referenced protocols/patterns
        for key, text in sections_to_inline.items():
            inline_parts.append(text)
            inline_parts.append("")

        inline_parts.append(MARKER_END)

        new_content = content + "\n".join(inline_parts) + "\n"
        try:
            skill_path.write_text(new_content)
        except OSError as e:
            print(f"  ERROR: Failed to write {skill_path}: {e}")
            continue

        total_inlined += 1
        print(f"  {plugin_name}: inlined {len(sections_to_inline)} protocols + {len(extra)} foundational ({len(refs)} refs, {len(unmatched)} unmatched)")
        if unmatched:
            for u in unmatched:
                print(f"    WARNING: unmatched ref: {u}")

    print(f"\nDone. Inlined protocols into {total_inlined} SKILL.md files.")


if __name__ == "__main__":
    inline_protocols()
