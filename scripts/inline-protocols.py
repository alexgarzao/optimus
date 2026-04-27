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
# Max file size (5 MB) — prevents hanging on bloated or corrupted inputs.
MAX_FILE_SIZE = 5 * 1024 * 1024

# Substring used to detect the format-validation protocol heading. Anchored to a
# single source of truth so that future heading renames update the matcher in
# exactly one place. A regression test parses live AGENTS.md and asserts that
# at least one heading contains this token.
VALIDATION_PROTOCOL_TOKEN = "optimus-tasks.md Validation"
MAIN_WORKTREE_PROTOCOL_KEY = "Protocol: Resolve Main Worktree Path"

# Module-level compiled patterns.
HEADING_RE = re.compile(r'^(?:#{2,3})\s+(.+)$')
PROTOCOL_RE = re.compile(r'AGENTS\.md Protocol:\s*([^\n"]+)')
COMMON_PATTERN_RE = re.compile(r'AGENTS\.md\s*"Common Patterns\s*>\s*([^"]+)"')
FINDING_PRESENTATION_RE = re.compile(r'AGENTS\.md\s*"Finding Presentation"')
SENTENCE_BOUNDARY_RE = re.compile(r'\.\s+(?=[A-Z])')
TRAILING_CONTEXT_RE = re.compile(r',\s+(?:with |followed )|;\s|\*\*')
PAREN_SUFFIX_RE = re.compile(r'\s*\([^)]*\)\s*$')


def parse_agents_md() -> dict[str, str]:
    """Parse AGENTS.md into named sections keyed by heading text."""
    if not AGENTS_MD.exists():
        print(f"ERROR: {AGENTS_MD} not found. Run from repo root.", file=sys.stderr)
        sys.exit(1)
    # Guard against bloated AGENTS.md.
    if AGENTS_MD.stat().st_size > MAX_FILE_SIZE:
        print(
            f"ERROR: {AGENTS_MD} exceeds {MAX_FILE_SIZE} bytes — aborting.",
            file=sys.stderr,
        )
        sys.exit(1)
    lines = AGENTS_MD.read_text().splitlines()
    sections: dict[str, str] = {}
    seen: set[str] = set()
    current_key = None
    current_lines: list[str] = []

    def _flush(key: str, body_lines: list[str]) -> None:
        # Warn on duplicate headings — last one wins, which can silently
        # hide a misnamed protocol if two sections share a title. Track via
        # `seen` (not `sections`) so the warning fires on the SECOND
        # occurrence, not the third.
        if key in seen:
            print(
                f"  WARNING: Duplicate heading '{key}' — later "
                "definition wins",
                file=sys.stderr,
            )
        seen.add(key)
        sections[key] = "\n".join(body_lines)

    for line in lines:
        heading_match = HEADING_RE.match(line)
        if heading_match:
            title = heading_match.group(1).strip()
            if current_key:
                _flush(current_key, current_lines)
            current_key = title
            current_lines = [line]
        elif current_key:
            current_lines.append(line)

    if current_key:
        _flush(current_key, current_lines)

    return sections


def extract_refs_from_content(content: str) -> set[str]:
    """Extract all AGENTS.md references from SKILL.md content (body only, not inlined block).

    Heuristic chain (intentional, in order):
      1. Match the literal phrase ``AGENTS.md Protocol: <name>`` via PROTOCOL_RE.
      2. Trim trailing prose at the first sentence boundary
         (``. `` followed by uppercase) — cuts off "...Validation. Use stage=...".
      3. Trim remaining trailing context (comma+with/followed clauses, bold
         markers, semicolons) — cuts off "...Validation, with X" / "**Note**".
      4. Strip terminal punctuation `.):` to normalize "...Validation):" cases.

    This chain is fragile but currently functional: it relies on prose authors
    NOT putting ":" or "**" inside the Protocol name itself, which is true
    today. The structured alternative would be to require a dedicated form
    such as ``<protocol-ref name="X" />`` in SKILL bodies; deferred until the
    heuristic actually misfires.
    """
    content = strip_existing_inline(content)
    refs: set[str] = set()

    # Protocol references: "see AGENTS.md Protocol: X"
    for m in PROTOCOL_RE.finditer(content):
        name = m.group(1).strip()
        # Split at sentence boundary (". " followed by uppercase letter) to remove
        # trailing sentences like ". Use stage=..." or ". Also load:"
        name = SENTENCE_BOUNDARY_RE.split(name)[0].strip()
        # Clean remaining trailing context (comma clauses, bold markers, semicolons)
        name = TRAILING_CONTEXT_RE.split(name)[0].strip()
        name = name.rstrip('.):')
        # Skip empty names (can happen if a reference was e.g. "Protocol: ***").
        if not name:
            continue
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
    """Test convenience: tests pass Path objects. Production code calls
    extract_refs_from_content(raw_content) directly to avoid the extra
    read_text() round-trip."""
    return extract_refs_from_content(skill_path.read_text())


def _normalize_key(key: str) -> str:
    """Strip parenthetical suffixes like (HARD BLOCK), (optional) for matching."""
    return PAREN_SUFFIX_RE.sub('', key).strip().lower()


def _pick_longest_with_warning(
    ref: str, candidates: list[str]
) -> str | None:
    """Pick the longest candidate from a startswith match list.

    When 2+ keys match the same prefix, prefer the LONGEST match (most specific),
    and warn to stderr about the ambiguity so the drift is visible.
    """
    if not candidates:
        return None
    if len(candidates) == 1:
        return candidates[0]
    # Sort by length DESC, then lexicographically for deterministic tie-break.
    ordered = sorted(candidates, key=lambda k: (-len(k), k))
    chosen = ordered[0]
    losers = ordered[1:]
    for loser in losers:
        print(
            f"  WARNING: ambiguous ref {ref!r} resolved to {chosen!r} "
            f"over {loser!r}",
            file=sys.stderr,
        )
    return chosen


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
        # Try startswith match for partial names — collect ALL candidates
        # and prefer the LONGEST match. Warn on ambiguity.
        candidates: list[str] = []
        for key in sections:
            if key.startswith("Protocol: "):
                key_base = _normalize_key(key[len("Protocol: "):])
                if key_base.startswith(proto_lower):
                    candidates.append(key)
        return _pick_longest_with_warning(ref, candidates)
    elif ref.startswith("Common: "):
        pattern_name = ref[len("Common: "):]
        pattern_normalized = _normalize_key(pattern_name)
        # Try exact match first (both sides normalized)
        for key in sections:
            if _normalize_key(key) == pattern_normalized:
                return key
        # Try startswith match — collect ALL candidates and prefer LONGEST.
        candidates = []
        for key in sections:
            if _normalize_key(key).startswith(pattern_normalized):
                candidates.append(key)
        return _pick_longest_with_warning(ref, candidates)
    return None


def strip_existing_inline(content: str) -> str:
    """Remove previously inlined protocols section, preserving content after end marker."""
    start_idx = content.find(MARKER_START)
    if start_idx == -1:
        return content
    end_idx = content.find(MARKER_END)
    if end_idx == -1:
        print(
            "  WARNING: MARKER_START found but MARKER_END missing — "
            "skipping strip to avoid data loss",
            file=sys.stderr,
        )
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
                 "Protocol: Resolve Tasks Git Scope",
                 MAIN_WORKTREE_PROTOCOL_KEY]:
        if key in sections:
            foundational[key] = sections[key]

    # Find all SKILL.md files
    skill_files = sorted(REPO_ROOT.glob("*/skills/*/SKILL.md"))
    print(f"Found {len(skill_files)} SKILL.md files\n")

    total_inlined = 0

    for skill_path in skill_files:
        plugin_name = skill_path.parts[-4]  # e.g., "plan" from plan/skills/optimus-plan/SKILL.md
        try:
            if skill_path.stat().st_size > MAX_FILE_SIZE:
                print(
                    f"  WARNING: {skill_path} exceeds {MAX_FILE_SIZE} bytes — skipping",
                    file=sys.stderr,
                )
                continue
            raw_content = skill_path.read_text()
        except (OSError, UnicodeDecodeError) as e:
            print(f"  ERROR: {skill_path}: {e} — skipping", file=sys.stderr)
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

        # F3.3i: Detect ref-alias collisions — when 2+ refs map to the same
        # section key, surface it via INFO so reviewers can decide if the
        # aliasing is intentional or if a SKILL.md uses inconsistent phrasing.
        key_to_refs: dict[str, list[str]] = {}
        for ref, key in matched.items():
            key_to_refs.setdefault(key, []).append(ref)
        for key, alias_refs in key_to_refs.items():
            if len(alias_refs) > 1:
                print(
                    f"  INFO: {plugin_name}: ref alias collapsed: "
                    f"{sorted(alias_refs)} all -> {key!r}",
                    file=sys.stderr,
                )

        # Collect the sections to inline (deduplicated, ordered)
        sections_to_inline: dict[str, str] = {}
        for ref, key in sorted(matched.items(), key=lambda x: x[1]):
            if key not in sections_to_inline:
                sections_to_inline[key] = sections[key]

        # Also check if State Management is referenced -> include foundational state.json docs
        needs_state = any("State Management" in k for k in sections_to_inline)
        needs_taskspec = any("TaskSpec" in k for k in sections_to_inline)
        needs_format = any(VALIDATION_PROTOCOL_TOKEN in k for k in sections_to_inline)
        # Any protocol that touches .optimus/ operational files needs the
        # main-worktree resolver. Detected by: explicit reference, or by
        # transitive use via State Management / Session State / Stage Stats /
        # Initialize .optimus Directory.
        needs_main_worktree = (
            any("Resolve Main Worktree Path" in k for k in sections_to_inline)
            or needs_state
            or any("Session State" in k for k in sections_to_inline)
            or any("Increment Stage Stats" in k for k in sections_to_inline)
            or any("Initialize .optimus Directory" in k for k in sections_to_inline)
            or any("Divergence Warning" in k for k in sections_to_inline)
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

        # optimus-tasks.md Validation depends on Resolve Tasks Git Scope (which
        # defines TASKS_DIR/TASKS_FILE/TASKS_GIT_SCOPE/tasks_git). Auto-inject
        # the scope protocol when a skill references only Validation.
        if needs_format:
            if "Protocol: Resolve Tasks Git Scope" in foundational and \
               "Protocol: Resolve Tasks Git Scope" not in sections_to_inline:
                extra["Protocol: Resolve Tasks Git Scope"] = foundational["Protocol: Resolve Tasks Git Scope"]

        # Auto-inject Resolve Main Worktree Path into any skill that touches
        # .optimus/ operational files. The bug it fixes (worktree isolation)
        # affects every skill that reads/writes state.json, stats.json,
        # sessions, or reports.
        if needs_main_worktree and MAIN_WORKTREE_PROTOCOL_KEY in foundational \
                and MAIN_WORKTREE_PROTOCOL_KEY not in sections_to_inline:
            extra[MAIN_WORKTREE_PROTOCOL_KEY] = foundational[MAIN_WORKTREE_PROTOCOL_KEY]

        body_only = strip_existing_inline(raw_content)

        # F3.3e: Detect manual paste of inlined helper functions in the body.
        # The inliner appends these as part of shared protocols; if a SKILL
        # body also defines them, output ends up with duplicate definitions
        # (and drift risk if one copy diverges). _optimus_sanitize is checked
        # as a future-regression guard — it was removed in F2.
        body_function_guards = (
            "_optimus_quiet_run() {",
            "_optimus_set_title() {",
            "_optimus_sanitize() {",
        )
        for fn_marker in body_function_guards:
            if fn_marker in body_only:
                fn_name = fn_marker.split("()", 1)[0]
                print(
                    f"  WARNING: {plugin_name}: body contains manual definition "
                    f"of {fn_name}() — should use inlined protocol",
                    file=sys.stderr,
                )

        content = body_only.rstrip() + "\n"

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

        # F14e: Skip the write when the inlined output is byte-identical to
        # what's already on disk. Keeps mtime stable on no-op runs, which
        # matters for incremental tooling (Make, watchers) and avoids
        # spurious git diffs. The matched/unmatched accounting is still
        # printed below so reviewers see the full picture.
        if new_content == raw_content:
            print(
                f"  {plugin_name}: no changes (already up to date) "
                f"({len(refs)} refs, {len(unmatched)} unmatched)"
            )
            if unmatched:
                for u in unmatched:
                    print(f"    WARNING: unmatched ref: {u}", file=sys.stderr)
            continue

        # F3.3d: Refuse to write through a symlink. Defense-in-depth against
        # a malicious commit that replaces SKILL.md with a symlink to e.g.
        # ~/.bashrc — the inliner would otherwise overwrite the target.
        if skill_path.is_symlink():
            print(
                f"  ERROR: refusing to write through symlink: {skill_path}",
                file=sys.stderr,
            )
            continue

        # F3.3c: Atomic write. A direct write_text() interrupted mid-write
        # leaves the file truncated without MARKER_END; on the next run
        # strip_existing_inline silently degrades. Write to a temp sibling
        # and atomically replace.
        tmp = skill_path.with_suffix(skill_path.suffix + ".tmp")
        try:
            tmp.write_text(new_content)
            tmp.replace(skill_path)
        except OSError as e:
            print(f"  ERROR: Failed to write {skill_path}: {e}", file=sys.stderr)
            # Best-effort cleanup of the temp file if it was created.
            try:
                if tmp.exists():
                    tmp.unlink()
            except OSError:
                pass
            continue

        total_inlined += 1
        print(f"  {plugin_name}: inlined {len(sections_to_inline)} protocols + {len(extra)} foundational ({len(refs)} refs, {len(unmatched)} unmatched)")
        if unmatched:
            for u in unmatched:
                print(f"    WARNING: unmatched ref: {u}", file=sys.stderr)

    print(f"\nDone. Inlined protocols into {total_inlined} SKILL.md files.")


if __name__ == "__main__":
    inline_protocols()
