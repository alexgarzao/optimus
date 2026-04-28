#!/usr/bin/env python3
"""
Inlines referenced AGENTS.md protocols into each SKILL.md.

Problem: AGENTS.md lives at repo root but plugins are installed individually.
Skills reference "see AGENTS.md Protocol: X" but agents can't find AGENTS.md.

Solution: Append only the referenced protocols/patterns to each SKILL.md,
making each plugin self-contained.

Phases 1-9 of issue #34 (inline-protocol bloat reduction):
Protocols may carry one of two inline-mode markers immediately under their
heading:

  * `<!-- inline-mode: summarize -->` — emit a 5-10 line stub (the
    protocol's `**Summary:**` subsection) in consumer SKILLs instead of
    the full body.
  * `<!-- inline-mode: omit -->` (Phase 9) — emit NOTHING in consumer
    SKILLs (no body, no stub, no header). Consumer SKILLs reference the
    protocol via body code (`see AGENTS.md Protocol: X`); the agent
    reads AGENTS.md on demand. Most aggressive token-reduction mode.

Pass `--no-summarize` to fall back to full-body inlining for ALL marked
protocols (both summarize and omit). Pass `--no-omit` for selective
testing that disables only omit mode.

Usage:
    python3 scripts/inline-protocols.py             # honor markers (default)
    python3 scripts/inline-protocols.py --no-summarize  # full body for all
    python3 scripts/inline-protocols.py --no-omit       # treat omit as full body
    python3 scripts/inline-protocols.py --stats-only
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
AGENTS_MD = REPO_ROOT / "AGENTS.md"
MARKER_START = "<!-- INLINE-PROTOCOLS:START -->"
MARKER_END = "<!-- INLINE-PROTOCOLS:END -->"
SUMMARIZE_MARKER = "<!-- inline-mode: summarize -->"
OMIT_MARKER = "<!-- inline-mode: omit -->"
# Regex matching either marker on a line by itself (used by parser + tests).
INLINE_MODE_MARKER_RE = re.compile(
    r'^\s*<!--\s*inline-mode:\s*(summarize|omit)\s*-->\s*$'
)
SUMMARY_PREFIX = "**Summary:**"
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
H2_OR_H3_RE = re.compile(r'^#{2,3}\s+')
PROTOCOL_RE = re.compile(r'AGENTS\.md Protocol:\s*([^\n"]+)')
COMMON_PATTERN_RE = re.compile(r'AGENTS\.md\s*"Common Patterns\s*>\s*([^"]+)"')
FINDING_PRESENTATION_RE = re.compile(r'AGENTS\.md\s*"Finding Presentation"')
SENTENCE_BOUNDARY_RE = re.compile(r'\.\s+(?=[A-Z])')
TRAILING_CONTEXT_RE = re.compile(r',\s+(?:with |followed )|;\s|\*\*')
PAREN_SUFFIX_RE = re.compile(r'\s*\([^)]*\)\s*$')


def _extract_summary(body: str) -> str | None:
    """Extract the `**Summary:** ...` block from a protocol body.

    Returns the prose between `**Summary:**` and the next blank-line-followed-by
    a structural marker (bold heading, `**Referenced by:**`, fenced code block,
    or H2/H3 heading). The summary is normalized to start with `**Summary:**`
    so consumers can render it unchanged. Returns None if no summary is found.
    """
    lines = body.splitlines()
    start_idx = None
    for i, line in enumerate(lines):
        if line.lstrip().startswith(SUMMARY_PREFIX):
            start_idx = i
            break
    if start_idx is None:
        return None

    end_idx = len(lines)
    # Walk forward until we hit a blank line followed by a new structural
    # element (bold prose marker like `**Foo:**`, fenced code, or another
    # H2/H3). We tolerate a single blank line inside the summary itself when
    # the next non-blank line continues plain prose.
    i = start_idx + 1
    while i < len(lines):
        stripped = lines[i].lstrip()
        if not stripped:
            # blank — peek next non-blank line
            j = i + 1
            while j < len(lines) and not lines[j].lstrip():
                j += 1
            if j >= len(lines):
                end_idx = i
                break
            nxt = lines[j].lstrip()
            if (
                nxt.startswith("**")
                or nxt.startswith("```")
                or H2_OR_H3_RE.match(lines[j])
            ):
                end_idx = i
                break
            # otherwise continue — summary spans the blank
            i = j + 1
            continue
        if H2_OR_H3_RE.match(lines[i]):
            end_idx = i
            break
        i += 1

    summary = "\n".join(lines[start_idx:end_idx]).rstrip()
    return summary or None


def parse_agents_md() -> tuple[dict[str, str], dict[str, str], dict[str, str]]:
    """Parse AGENTS.md into named sections keyed by heading text.

    Returns a `(sections, summaries, modes)` triple:
      * `sections[heading] = full body` for every H2/H3 heading.
      * `summaries[heading] = summary text` only for protocols carrying
        either inline-mode marker AND a `**Summary:**` block. Summaries
        remain available for omit-mode protocols too — they preserve the
        documentation depth in AGENTS.md and let a future revert to
        summarize mode work without a content rewrite.
      * `modes[heading] = "summarize" | "omit"` only for protocols that
        carry one of the markers. Headings with no marker are absent from
        this dict (consumers default to full-body inlining).
    """
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
    summaries: dict[str, str] = {}
    modes: dict[str, str] = {}
    seen: set[str] = set()
    current_key = None
    current_lines: list[str] = []

    def _detect_mode(body_lines: list[str]) -> str | None:
        """Return 'summarize' / 'omit' / None for a protocol body.

        Match on the regex (line-anchored) so prose mentions in backticks
        or inline code don't count — that prevents the meta-doc in
        `## Editing Rules` from marking itself.
        """
        for line in body_lines:
            m = INLINE_MODE_MARKER_RE.match(line)
            if m:
                return m.group(1)
        return None

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
        body = "\n".join(body_lines)
        sections[key] = body
        mode = _detect_mode(body_lines)
        if mode is not None:
            modes[key] = mode
            # Summaries are still extracted for both summarize and omit
            # modes — omit mode doesn't need the summary at runtime, but
            # extracting it preserves the source-of-truth structure and
            # makes a future revert to summarize mode trivially safe.
            summary = _extract_summary(body)
            if summary is None:
                # Missing summary is only a hard problem for summarize
                # mode (where the stub IS the summary). For omit mode it
                # is benign — emit a softer notice so authors know the
                # documentation block is missing without forcing fallback.
                if mode == "summarize":
                    print(
                        f"  WARNING: '{key}' carries {SUMMARIZE_MARKER} but "
                        "no **Summary:** subsection found — falling back to "
                        "full-body inlining for this protocol",
                        file=sys.stderr,
                    )
            else:
                summaries[key] = summary

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

    return sections, summaries, modes


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


def _build_summary_stub(key: str, summary: str) -> str:
    """Render the inlined stub for a summarize-marked protocol."""
    lines: list[str] = []
    lines.append(f"### {key} (summarized)")
    lines.append("")
    lines.append(
        f"> **Summary inlined here. Full recipe at "
        f"`AGENTS.md -> {key}`.**"
    )
    lines.append("")
    lines.append(summary)
    return "\n".join(lines)


def inline_protocols(
    *,
    summarize: bool = True,
    omit: bool = True,
    stats_only: bool = False,
) -> dict | None:
    """Main: inline referenced protocols into each SKILL.md.

    Parameters
    ----------
    summarize:
        When True (default), protocols carrying `<!-- inline-mode: summarize -->`
        propagate as their `**Summary:**` stub instead of the full body. When
        False, summarize-marked protocols inline the full body. Disabling
        summarize ALSO forces omit-marked protocols to full body — `summarize`
        is the master switch (legacy semantics preserved for `--no-summarize`).
    omit:
        When True (default), protocols carrying `<!-- inline-mode: omit -->`
        emit nothing in consumer SKILLs (no body, no stub, no header). When
        False, omit-marked protocols fall back to the next-most-aggressive
        mode that's enabled — summarize stub if `summarize=True`, otherwise
        full body. Useful for diagnostic runs that want to see what the stub
        would have looked like without globally reverting omit mode.
    stats_only:
        When True, no files are written. Returns a stats dict for callers
        (e.g., `make inline-stats`) to render a table.
    """
    sections, summaries, modes = parse_agents_md()
    print(f"Parsed {len(sections)} sections from AGENTS.md", file=sys.stderr)
    if modes:
        summarize_keys = sorted(k for k, m in modes.items() if m == "summarize")
        omit_keys = sorted(k for k, m in modes.items() if m == "omit")
        print(
            f"  {len(modes)} carry inline-mode markers: "
            f"{len(summarize_keys)} summarize, {len(omit_keys)} omit",
            file=sys.stderr,
        )
        if summarize_keys:
            print(f"    summarize: {summarize_keys}", file=sys.stderr)
        if omit_keys:
            print(f"    omit: {omit_keys}", file=sys.stderr)

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
    print(f"Found {len(skill_files)} SKILL.md files\n", file=sys.stderr)

    # Stats accumulators for `--stats-only` mode.
    per_skill: list[dict] = []
    protocol_consumers: dict[str, list[str]] = {}
    protocol_lines: dict[str, int] = {}
    pre_summarize_total = 0
    post_summarize_total = 0

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
        # (and drift risk if one copy diverges). _optimus_sanitize and
        # _optimus_set_title are checked as future-regression guards —
        # _optimus_sanitize was removed in F2 and _optimus_set_title was
        # replaced by _optimus_mark_session / _optimus_clear_session.
        body_function_guards = (
            "_optimus_quiet_run() {",
            "_optimus_mark_session() {",
            "_optimus_clear_session() {",
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

        # Track which protocols got summarized vs full-bodied vs omitted
        # for this skill, plus the lines saved (for both stats and the
        # per-skill log line below).
        summarized_count = 0
        full_count = 0
        omitted_count = 0
        lines_saved = 0

        def _resolve_mode(key: str) -> str:
            """Determine effective mode for a protocol given current flags.

            Returns 'omit' / 'summarize' / 'full'. Marker-less protocols
            always resolve to 'full'. The flags `summarize` and `omit`
            cascade: if the requested mode is disabled, fall back to the
            next-most-aggressive mode that IS enabled.
            """
            mode = modes.get(key)
            if mode == "omit":
                if omit:
                    return "omit"
                # Omit disabled — fall through to summarize if enabled.
                if summarize and key in summaries:
                    return "summarize"
                return "full"
            if mode == "summarize":
                if summarize and key in summaries:
                    return "summarize"
                return "full"
            return "full"

        def _emit(key: str, full_text: str) -> None:
            """Append summary stub, full body, or nothing for `key`."""
            nonlocal summarized_count, full_count, omitted_count, lines_saved
            effective = _resolve_mode(key)
            if effective == "omit":
                # Phase 9: emit absolutely nothing for this protocol — no
                # heading, no stub, no body. Consumer SKILLs reference it
                # via body code; the agent reads AGENTS.md on demand.
                omitted_count += 1
                full_lines = full_text.count("\n") + 1 if full_text else 0
                lines_saved += full_lines
                return
            if effective == "summarize":
                stub = _build_summary_stub(key, summaries[key])
                inline_parts.append(stub)
                summarized_count += 1
                full_lines = full_text.count("\n") + 1
                stub_lines = stub.count("\n") + 1
                lines_saved += max(full_lines - stub_lines, 0)
            else:
                inline_parts.append(full_text)
                full_count += 1
            inline_parts.append("")

        # Add foundational context first
        for key, text in extra.items():
            if key not in sections_to_inline:
                _emit(key, text)

        # Add referenced protocols/patterns
        for key, text in sections_to_inline.items():
            _emit(key, text)

        inline_parts.append(MARKER_END)

        new_content = content + "\n".join(inline_parts) + "\n"

        # Update accumulators that are needed by both write and stats-only paths.
        # `inlined_keys` is the union of sections_to_inline + extra (foundational).
        inlined_keys = set(sections_to_inline) | {
            k for k in extra if k not in sections_to_inline
        }
        for key in inlined_keys:
            protocol_consumers.setdefault(key, []).append(plugin_name)
            full_text = sections_to_inline.get(key) or extra.get(key) or ""
            protocol_lines.setdefault(
                key, full_text.count("\n") + 1 if full_text else 0
            )
        # Per-skill stats: count lines in inlined block (full vs stub).
        inlined_block_lines = sum(part.count("\n") + 1 for part in inline_parts)
        skill_total_lines = new_content.count("\n") + 1
        body_lines = content.count("\n") + 1
        per_skill.append({
            "plugin": plugin_name,
            "total": skill_total_lines,
            "inlined": inlined_block_lines,
            "body": body_lines,
            "summarized": summarized_count,
            "full": full_count,
            "omitted": omitted_count,
            "lines_saved": lines_saved,
        })
        # The "before summarize" estimate sums full-body line counts for ALL
        # inlined keys; "after" sums summary lines for keys with a summary,
        # zero for omitted keys, and full lines for the rest (= what the
        # skill currently emits with current flags).
        for key in inlined_keys:
            full_text = sections_to_inline.get(key) or extra.get(key) or ""
            full_len = full_text.count("\n") + 1 if full_text else 0
            pre_summarize_total += full_len
            mode = modes.get(key)
            if mode == "omit" and omit:
                # Omit emits zero lines for this protocol.
                continue
            if mode == "omit" and not omit and summarize and key in summaries:
                stub_text = _build_summary_stub(key, summaries[key])
                post_summarize_total += stub_text.count("\n") + 1
                continue
            if mode == "summarize" and summarize and key in summaries:
                stub_text = _build_summary_stub(key, summaries[key])
                post_summarize_total += stub_text.count("\n") + 1
            else:
                post_summarize_total += full_len

        # F14e: Skip the write when the inlined output is byte-identical to
        # what's already on disk. Keeps mtime stable on no-op runs, which
        # matters for incremental tooling (Make, watchers) and avoids
        # spurious git diffs. The matched/unmatched accounting is still
        # printed below so reviewers see the full picture.
        if new_content == raw_content:
            if not stats_only:
                print(
                    f"  {plugin_name}: no changes (already up to date) "
                    f"({len(refs)} refs, {len(unmatched)} unmatched)"
                )
                if unmatched:
                    for u in unmatched:
                        print(f"    WARNING: unmatched ref: {u}", file=sys.stderr)
            continue

        # In stats-only mode, never write. Still log per-skill summary so
        # callers can verify the dry-run path is producing sensible numbers.
        if stats_only:
            print(
                f"  [stats-only] {plugin_name}: would inline "
                f"{len(sections_to_inline)} protocols "
                f"({omitted_count} omitted, {summarized_count} summarized, "
                f"{full_count} full) + {len(extra)} foundational, "
                f"{lines_saved} lines saved"
            )
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
        print(
            f"  {plugin_name}: inlined {len(sections_to_inline)} protocols "
            f"({omitted_count} omitted, {summarized_count} summarized, "
            f"{full_count} full) + {len(extra)} foundational, "
            f"{lines_saved} lines saved ({len(refs)} refs, "
            f"{len(unmatched)} unmatched)"
        )
        if unmatched:
            for u in unmatched:
                print(f"    WARNING: unmatched ref: {u}", file=sys.stderr)

    if stats_only:
        _render_stats(per_skill, protocol_consumers, protocol_lines,
                      pre_summarize_total, post_summarize_total,
                      summarize, omit)
        return {
            "per_skill": per_skill,
            "protocol_consumers": protocol_consumers,
            "protocol_lines": protocol_lines,
            "pre_summarize_total": pre_summarize_total,
            "post_summarize_total": post_summarize_total,
            "modes": modes,
        }

    print(f"\nDone. Inlined protocols into {total_inlined} SKILL.md files.")
    return None


def _render_stats(
    per_skill: list[dict],
    protocol_consumers: dict[str, list[str]],
    protocol_lines: dict[str, int],
    pre_summarize_total: int,
    post_summarize_total: int,
    summarize: bool,
    omit: bool,
) -> None:
    """Pretty-print the stats table to stdout (for `make inline-stats`)."""
    print()
    print("Per-skill inlining stats")
    print("-" * 88)
    header = (
        f"{'Skill':<24} {'Total LOC':>10} {'Inlined LOC':>12} "
        f"{'Body LOC':>10} {'Inline %':>9} {'Full':>5} {'Sum':>5} {'Omit':>5}"
    )
    print(header)
    print("-" * 88)
    for row in sorted(per_skill, key=lambda r: -r["inlined"]):
        pct = (row["inlined"] / row["total"] * 100) if row["total"] else 0
        print(
            f"{row['plugin']:<24} {row['total']:>10} "
            f"{row['inlined']:>12} {row['body']:>10} {pct:>8.0f}% "
            f"{row.get('full', 0):>5} {row.get('summarized', 0):>5} "
            f"{row.get('omitted', 0):>5}"
        )
    print()
    print("Duplication summary (by protocol)")
    print("-" * 72)
    print(f"{'Protocol':<48} {'Consumers':>10} {'Lines/copy':>11}")
    print("-" * 72)
    rows = []
    for key, consumers in protocol_consumers.items():
        rows.append((key, len(consumers), protocol_lines.get(key, 0)))
    for key, n, lines in sorted(rows, key=lambda r: -(r[1] * r[2])):
        total = n * lines
        label = key
        if len(label) > 47:
            label = label[:44] + "..."
        print(f"{label:<48} {n:>10} {lines:>11}  (total {total})")
    print()
    print("Estimated total inlined LOC")
    print("-" * 72)
    print(
        f"  Before any mode  : {pre_summarize_total} LOC across "
        f"{len(per_skill)} SKILLs (full-body baseline)"
    )
    flag_label = (
        "summarize+omit" if (summarize and omit)
        else "summarize-only" if summarize
        else "omit-only" if omit
        else "disabled"
    )
    if pre_summarize_total and (summarize or omit):
        delta = pre_summarize_total - post_summarize_total
        pct = delta / pre_summarize_total * 100
        print(
            f"  After {flag_label:<14}: {post_summarize_total} LOC "
            f"(-{delta} LOC, -{pct:.0f}%)"
        )
    else:
        print(
            "  All inline-mode markers disabled — using full-body inlining"
        )
    # Per-mode breakdown (Phase 9).
    full_total = sum(r.get("full", 0) for r in per_skill)
    sum_total = sum(r.get("summarized", 0) for r in per_skill)
    omit_total = sum(r.get("omitted", 0) for r in per_skill)
    print()
    print("Per-mode protocol counts (across all SKILLs)")
    print("-" * 72)
    print(f"  Full-body inlined : {full_total}")
    print(f"  Summarized stubs  : {sum_total}")
    print(f"  Omitted entirely  : {omit_total}")


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Inline AGENTS.md protocols into each SKILL.md."
    )
    parser.add_argument(
        "--no-summarize",
        action="store_true",
        help=(
            "Disable BOTH summarize and omit modes. Protocols carrying "
            f"{SUMMARIZE_MARKER!r} or {OMIT_MARKER!r} will inline their "
            "full body. Useful for diagnostic or full-rebuild runs."
        ),
    )
    parser.add_argument(
        "--no-omit",
        action="store_true",
        help=(
            f"Disable omit mode only. Protocols carrying {OMIT_MARKER!r} "
            "fall back to summarize mode (if marked) or full body. Lets "
            "diagnostic runs see the would-have-been stub without "
            "globally reverting omit mode."
        ),
    )
    parser.add_argument(
        "--stats-only",
        action="store_true",
        help=(
            "Don't write any files. Print a per-skill / per-protocol table "
            "and a before/after estimate to stdout, including per-mode "
            "counts (full / summarize / omit)."
        ),
    )
    return parser.parse_args(argv)


if __name__ == "__main__":
    args = _parse_args()
    # `--no-summarize` is the master switch: it forces full-body inlining
    # for every marked protocol (legacy semantics from Phases 1-8 preserved).
    summarize = not args.no_summarize
    omit = summarize and not args.no_omit
    inline_protocols(
        summarize=summarize,
        omit=omit,
        stats_only=args.stats_only,
    )
