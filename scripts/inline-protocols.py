#!/usr/bin/env python3
"""
Inlines referenced AGENTS.md protocols into each SKILL.md.

Problem: AGENTS.md lives at repo root but plugins are installed individually.
Skills reference "see AGENTS.md Protocol: X" but agents can't find AGENTS.md.

Solution: Append only the referenced protocols/patterns to each SKILL.md,
making each plugin self-contained.

Usage: python3 scripts/inline-protocols.py
"""

import re
import os
from pathlib import Path
from collections import defaultdict

REPO_ROOT = Path(__file__).parent.parent
AGENTS_MD = REPO_ROOT / "AGENTS.md"
MARKER_START = "<!-- INLINE-PROTOCOLS:START -->"
MARKER_END = "<!-- INLINE-PROTOCOLS:END -->"

# Sections that are general context (not protocols) but referenced by skills
GENERAL_SECTIONS = {
    "tasks.md Format",
    "Task Lifecycle",
    "Dry-Run Mode (all stages)",
    "Verification Command Configuration",
}


def parse_agents_md():
    """Parse AGENTS.md into named sections keyed by heading text."""
    lines = AGENTS_MD.read_text().splitlines()
    sections = {}
    current_key = None
    current_lines = []
    current_level = 0

    for line in lines:
        heading_match = re.match(r'^(#{2,3})\s+(.+)$', line)
        if heading_match:
            level = len(heading_match.group(1))
            title = heading_match.group(2).strip()
            if current_key:
                sections[current_key] = "\n".join(current_lines)
            current_key = title
            current_lines = [line]
            current_level = level
        elif current_key:
            current_lines.append(line)

    if current_key:
        sections[current_key] = "\n".join(current_lines)

    return sections


def extract_refs_from_skill(skill_path):
    """Extract all AGENTS.md references from a SKILL.md file."""
    content = skill_path.read_text()
    refs = set()

    # Protocol references: "see AGENTS.md Protocol: X"
    for m in re.finditer(r'AGENTS\.md Protocol:\s*([^.\n"]+)', content):
        name = m.group(1).strip().rstrip('.')
        # Clean trailing context like "Use counter=..." or "If invalid..."
        name = re.split(r'\.\s|;\s|\*\*|Use |If |Check |Also |Load |,\s', name)[0].strip()
        name = name.rstrip('):')
        refs.add(f"Protocol: {name}")

    # Common pattern references: 'AGENTS.md "Common Patterns > X"'
    for m in re.finditer(r'AGENTS\.md\s*"Common Patterns\s*>\s*([^"]+)"', content):
        name = m.group(1).strip().rstrip('.')
        refs.add(f"Common: {name}")

    # Finding Presentation references
    for m in re.finditer(r'AGENTS\.md\s*"Finding Presentation"', content):
        refs.add("Common: Finding Presentation")

    return refs


def match_ref_to_section(ref, sections):
    """Match a reference name to a section key in AGENTS.md."""
    if ref.startswith("Protocol: "):
        proto_name = ref[len("Protocol: "):]
        # Try exact match first
        for key in sections:
            if key.startswith("Protocol: ") and proto_name.lower() in key.lower():
                return key
        # Try without "Protocol: " prefix
        for key in sections:
            if proto_name.lower() in key.lower():
                return key
    elif ref.startswith("Common: "):
        pattern_name = ref[len("Common: "):]
        for key in sections:
            if pattern_name.lower() in key.lower():
                return key
    return None


def strip_existing_inline(content):
    """Remove previously inlined protocols section."""
    start_idx = content.find(MARKER_START)
    if start_idx == -1:
        return content
    end_idx = content.find(MARKER_END)
    if end_idx == -1:
        return content[:start_idx].rstrip()
    return content[:start_idx].rstrip()


def inline_protocols():
    """Main: inline referenced protocols into each SKILL.md."""
    sections = parse_agents_md()
    print(f"Parsed {len(sections)} sections from AGENTS.md")

    # Also include some foundational sections that provide context
    # for protocol references (e.g., State Management references state.json format)
    foundational = {}
    for key in ["File Location", "Valid Status Values (stored in state.json)",
                 "Task Spec Resolution", "Format Validation",
                 "Dependency Rules", "Version Management",
                 "Valid Tipo Values", "Column Specification"]:
        if key in sections:
            foundational[key] = sections[key]

    # Find all SKILL.md files
    skill_files = sorted(REPO_ROOT.glob("*/skills/*/SKILL.md"))
    print(f"Found {len(skill_files)} SKILL.md files\n")

    total_inlined = 0

    for skill_path in skill_files:
        plugin_name = skill_path.parts[-4]  # e.g., "plan" from plan/skills/optimus-plan/SKILL.md
        refs = extract_refs_from_skill(skill_path)

        if not refs:
            print(f"  {plugin_name}: no AGENTS.md refs, skipping")
            continue

        # Match refs to sections
        matched = {}
        unmatched = []
        for ref in sorted(refs):
            key = match_ref_to_section(ref, sections)
            if key:
                matched[ref] = key
            else:
                unmatched.append(ref)

        # Collect the sections to inline (deduplicated, ordered)
        sections_to_inline = {}
        for ref, key in sorted(matched.items(), key=lambda x: x[1]):
            if key not in sections_to_inline:
                sections_to_inline[key] = sections[key]

        # Also check if State Management is referenced -> include foundational state.json docs
        needs_state = any("State Management" in k for k in sections_to_inline)
        needs_taskspec = any("TaskSpec" in k for k in sections_to_inline)
        needs_format = any("tasks.md Validation" in k for k in sections_to_inline)

        extra = {}
        if needs_state and "File Location" in foundational:
            extra["File Location"] = foundational["File Location"]
        if needs_state and "Valid Status Values (stored in state.json)" in foundational:
            extra["Valid Status Values (stored in state.json)"] = foundational["Valid Status Values (stored in state.json)"]
        if needs_taskspec and "Task Spec Resolution" in foundational:
            extra["Task Spec Resolution"] = foundational["Task Spec Resolution"]
        if needs_format and "Format Validation" in foundational:
            extra["Format Validation"] = foundational["Format Validation"]

        # Build the inline block
        content = skill_path.read_text()
        content = strip_existing_inline(content)

        inline_parts = []
        inline_parts.append(f"\n\n{MARKER_START}")
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
        skill_path.write_text(new_content)

        total_inlined += 1
        print(f"  {plugin_name}: inlined {len(sections_to_inline)} protocols + {len(extra)} foundational ({len(refs)} refs, {len(unmatched)} unmatched)")
        if unmatched:
            for u in unmatched:
                print(f"    WARNING: unmatched ref: {u}")

    print(f"\nDone. Inlined protocols into {total_inlined} SKILL.md files.")


if __name__ == "__main__":
    inline_protocols()
