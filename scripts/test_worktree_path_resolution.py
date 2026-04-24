#!/usr/bin/env python3
"""Regression tests for worktree path resolution of .optimus/ operational files.

These tests guard against the "T-037 state drift" incident: gitignored files
inside `.optimus/` (state.json, stats.json, sessions/, reports/) MUST always
be resolved against the main worktree — never the current working directory.

A skill running from a linked worktree that uses `".optimus/state.json"` as a
relative path will write into that linked worktree's isolated copy. When the
worktree is later removed (e.g., during task closure), the write is silently
lost and the main worktree's state.json is left stale.

See AGENTS.md "Protocol: Resolve Main Worktree Path" for the fix.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
AGENTS_MD = REPO_ROOT / "AGENTS.md"

# Regex matching bash variable assignments to a relative .optimus/... path.
# Matches patterns like:
#   STATE_FILE=".optimus/state.json"
#   STATS_FILE=".optimus/stats.json"
#   SESSION_FILE=".optimus/sessions/session-foo.json"
# Does NOT match escape-sequence examples (ignored via contextual filtering below).
RELATIVE_ASSIGN_RE = re.compile(
    r'^\s*(?P<name>[A-Z_]+)="\.optimus/(?P<tail>(?:state\.json|stats\.json|sessions|reports)[^"]*)"',
    re.MULTILINE,
)

# Lines that are documentation-only examples and should be exempted.
# The Protocol: Resolve Main Worktree Path section explicitly shows the WRONG
# pattern as a contrastive example. We allow exempted occurrences to stay.
ALLOWED_EXAMPLE_TAGS = [
    "# WRONG",
    "`STATE_FILE=\".optimus/state.json\"` created",
]


def _all_doc_files():
    yield AGENTS_MD
    yield from sorted(REPO_ROOT.glob("*/skills/*/SKILL.md"))


def _is_allowed_example(context_line: str) -> bool:
    """Lines inside the WRONG-example block are allowed."""
    return any(tag in context_line for tag in ALLOWED_EXAMPLE_TAGS)


class TestWorktreePathResolution:
    """AGENTS.md and SKILL.md must not contain relative .optimus/ paths
    (except inside the documented WRONG-example block)."""

    def test_no_relative_optimus_assignments(self):
        violations: list[str] = []
        for filepath in _all_doc_files():
            if not filepath.exists():
                continue
            text = filepath.read_text()
            for match in RELATIVE_ASSIGN_RE.finditer(text):
                # Find the line containing this match
                line_start = text.rfind("\n", 0, match.start()) + 1
                line_end = text.find("\n", match.end())
                if line_end == -1:
                    line_end = len(text)
                line = text[line_start:line_end]
                # Skip documented "WRONG" example blocks
                if _is_allowed_example(line):
                    continue
                line_no = text.count("\n", 0, match.start()) + 1
                rel = filepath.relative_to(REPO_ROOT)
                violations.append(f"{rel}:{line_no}: {line.strip()}")
        assert violations == [], (
            "Relative .optimus/ paths found (must resolve against main worktree — "
            "see AGENTS.md Protocol: Resolve Main Worktree Path):\n"
            + "\n".join(f"  - {v}" for v in violations)
        )

    def test_resolve_main_worktree_protocol_exists(self):
        """AGENTS.md must define the Resolve Main Worktree Path protocol."""
        text = AGENTS_MD.read_text()
        assert "### Protocol: Resolve Main Worktree Path" in text, (
            "Protocol: Resolve Main Worktree Path must exist in AGENTS.md"
        )
        # Protocol must explain the `git worktree list --porcelain` recipe
        assert "git worktree list --porcelain" in text, (
            "Protocol must document the `git worktree list --porcelain` recipe"
        )

    def test_state_touching_skills_inline_worktree_protocol(self):
        """Every SKILL.md that inlines State Management, Session State,
        Increment Stage Stats, or Initialize .optimus Directory must also
        inline Protocol: Resolve Main Worktree Path (since those protocols
        depend on it)."""
        state_protocols = (
            "Protocol: State Management",
            "Protocol: Session State",
            "Protocol: Increment Stage Stats",
            "Protocol: Initialize .optimus Directory",
        )
        violations: list[str] = []
        for filepath in sorted(REPO_ROOT.glob("*/skills/*/SKILL.md")):
            text = filepath.read_text()
            touches_state = any(f"### {p}" in text for p in state_protocols)
            if not touches_state:
                continue
            has_resolver = "### Protocol: Resolve Main Worktree Path" in text
            if not has_resolver:
                rel = filepath.relative_to(REPO_ROOT)
                violations.append(str(rel))
        assert violations == [], (
            "Skills that inline State Management/Session State/Increment Stage Stats/"
            "Initialize .optimus Directory must also inline Protocol: Resolve Main "
            "Worktree Path. Run `python3 scripts/inline-protocols.py` to regenerate:\n"
            + "\n".join(f"  - {v}" for v in violations)
        )
