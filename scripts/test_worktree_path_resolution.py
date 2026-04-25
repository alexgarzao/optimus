#!/usr/bin/env python3
"""Regression tests for the worktree-isolation fix.

Bug context: `.optimus/state.json`, `.optimus/stats.json`, `.optimus/sessions/`,
`.optimus/reports/`, and checkpoint markers are gitignored. Git does NOT
propagate ignored files across linked worktrees. Skills that resolve these
paths against `$PWD` (relative path) write to the worktree's isolated copy
when run from a linked worktree. When the worktree is later removed (e.g.,
by `/optimus-done` cleanup), the writes are lost — silent data loss.

Real incident: T-037 in `plugin-br-payments` had wrong status forever,
blocking 3 dependent tasks.

The fix introduces `Protocol: Resolve Main Worktree Path` and prefixes all
`.optimus/` paths with `${MAIN_WORKTREE}` (resolved via
`git worktree list --porcelain`).

These tests fail if any relative `.optimus/` path reappears in AGENTS.md or
any SKILL.md (except inside the documented `# WRONG` example block of the
resolver protocol itself).
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
AGENTS_MD = REPO_ROOT / "AGENTS.md"


def _read(path: Path) -> str:
    return path.read_text()


def _all_skill_files() -> list[Path]:
    return sorted(REPO_ROOT.glob("*/skills/*/SKILL.md"))


def _strip_inlined_block(content: str) -> str:
    """Return only the body region of a SKILL.md (above INLINE-PROTOCOLS:START)."""
    return content.split("<!-- INLINE-PROTOCOLS:START -->", 1)[0]


def _strip_wrong_example_block(content: str) -> str:
    """Strip the documented `# WRONG (resolves against PWD...)` example block
    from AGENTS.md so the regression detector doesn't flag the intentional
    counter-example inside Protocol: Resolve Main Worktree Path.

    The block is a fenced bash code block that starts with the `# WRONG` comment.
    """
    # The WRONG example is inside a single fenced bash block. Find the comment
    # and strip from the comment's line through the next ``` on its own line.
    lines = content.splitlines()
    out_lines: list[str] = []
    skip = False
    for line in lines:
        if not skip and "# WRONG (resolves against PWD" in line:
            skip = True
            continue
        if skip:
            # Skip until we hit a closing ``` (end of fenced block).
            if line.strip() == "```":
                skip = False
            continue
        out_lines.append(line)
    return "\n".join(out_lines)


# --- Patterns ---

# Bare path assignments (LHS is the variable, RHS starts with .optimus/...)
RELATIVE_PATH_ASSIGN_RE = re.compile(
    r'^\s*(STATE_FILE|STATS_FILE|SESSION_FILE|FETCH_MARKER|REPORT_FILE|REPORT_DIR|CONFIG_FILE)\s*=\s*"\.optimus/',
    re.MULTILINE,
)

# Bare mkdir / rm / find on .optimus paths (excluding gitignore patterns,
# which are project-rooted by convention and stay as-is).
RELATIVE_OPTIMUS_BASH_RE = re.compile(
    r'(?:mkdir\s+-p\s+|find\s+|ls\s+(?:-1t\s+)?|cat\s+|rm\s+-f\s+)(?:"\s*)?\.optimus/'
)

# Migration / rename checkpoint markers as bare paths.
RELATIVE_CHECKPOINT_RE = re.compile(
    r'(?:>|<|\[\s*-f|\bcat)\s*\.optimus/\.(?:migration|rename|last-tasks)'
)


class TestAgentsMdMainWorktreeResolver:
    """AGENTS.md must define and use Protocol: Resolve Main Worktree Path."""

    def test_resolver_protocol_exists(self):
        content = _read(AGENTS_MD)
        assert "### Protocol: Resolve Main Worktree Path" in content, (
            "AGENTS.md must define `### Protocol: Resolve Main Worktree Path` — "
            "this is the canonical recipe for resolving .optimus/ paths against "
            "the main worktree (fixes worktree-isolation data loss)."
        )

    def test_resolver_uses_git_worktree_list_porcelain(self):
        content = _read(AGENTS_MD)
        assert "git worktree list --porcelain" in content, (
            "Resolver protocol must use `git worktree list --porcelain` "
            "(machine-readable, stable across git versions). The first "
            "`worktree` line is always the main worktree."
        )

    def test_resolver_documents_wrong_pattern(self):
        content = _read(AGENTS_MD)
        assert "# WRONG" in content and "PWD" in content, (
            "Resolver protocol must include a `# WRONG (resolves against PWD...)` "
            "example showing the broken pattern, so future contributors don't "
            "accidentally regress to relative paths."
        )

    def test_no_relative_optimus_state_paths_outside_wrong_block(self):
        """AGENTS.md must NOT have any STATE_FILE/STATS_FILE/SESSION_FILE/etc.
        relative-path assignment outside the documented WRONG example."""
        content = _strip_wrong_example_block(_read(AGENTS_MD))
        violations = []
        for m in RELATIVE_PATH_ASSIGN_RE.finditer(content):
            line_no = content[: m.start()].count("\n") + 1
            violations.append(f"AGENTS.md:{line_no}: {m.group(0).strip()}")
        assert violations == [], (
            "Found relative .optimus/ path assignments in AGENTS.md (outside "
            "the documented WRONG example block):\n"
            + "\n".join(f"  - {v}" for v in violations)
            + "\n\nFix: prefix with ${MAIN_WORKTREE}/, e.g. "
            'STATE_FILE="${MAIN_WORKTREE}/.optimus/state.json"'
        )

    def test_no_relative_optimus_bash_outside_wrong_block(self):
        """No bare `mkdir -p .optimus/...` / `find .optimus/...` / etc. in
        AGENTS.md outside the documented WRONG example. Gitignore-pattern lines
        (which are project-rooted by convention) are excluded by the regex."""
        content = _strip_wrong_example_block(_read(AGENTS_MD))
        violations = []
        for m in RELATIVE_OPTIMUS_BASH_RE.finditer(content):
            line_no = content[: m.start()].count("\n") + 1
            ctx = content.splitlines()[line_no - 1].strip()
            # Skip gitignore-pattern blocks (where .optimus/ appears as
            # part of a `printf '...' >> .gitignore` heredoc-style payload).
            if ".gitignore" in ctx or "printf" in ctx:
                continue
            violations.append(f"AGENTS.md:{line_no}: {ctx}")
        assert violations == [], (
            "Found relative .optimus/ bash usage in AGENTS.md:\n"
            + "\n".join(f"  - {v}" for v in violations)
        )


class TestSkillBodiesUseMainWorktreePrefix:
    """Every SKILL.md body must prefix .optimus/ paths with ${MAIN_WORKTREE}/.

    Inlined blocks (between INLINE-PROTOCOLS:START/END) are auto-regenerated
    from AGENTS.md and are checked separately by AGENTS.md tests above.
    """

    def test_no_relative_state_paths_in_skill_bodies(self):
        violations = []
        for skill_path in _all_skill_files():
            body = _strip_inlined_block(_read(skill_path))
            for m in RELATIVE_PATH_ASSIGN_RE.finditer(body):
                line_no = body[: m.start()].count("\n") + 1
                rel = skill_path.relative_to(REPO_ROOT)
                violations.append(f"{rel}:{line_no}: {m.group(0).strip()}")
        assert violations == [], (
            "Found relative .optimus/ path assignments in SKILL.md bodies. "
            "These will write to the worktree's isolated copy when the skill "
            "runs from a linked worktree, causing silent data loss:\n"
            + "\n".join(f"  - {v}" for v in violations)
            + "\n\nFix: use ${MAIN_WORKTREE}/.optimus/... after invoking "
            "AGENTS.md Protocol: Resolve Main Worktree Path."
        )

    def test_no_relative_checkpoint_markers_in_skill_bodies(self):
        violations = []
        for skill_path in _all_skill_files():
            body = _strip_inlined_block(_read(skill_path))
            for m in RELATIVE_CHECKPOINT_RE.finditer(body):
                line_no = body[: m.start()].count("\n") + 1
                rel = skill_path.relative_to(REPO_ROOT)
                violations.append(f"{rel}:{line_no}: {m.group(0).strip()}")
        assert violations == [], (
            "Found relative .optimus/.{migration,rename,last-tasks} "
            "checkpoint markers in SKILL.md bodies. Same data-loss risk as "
            "state.json:\n"
            + "\n".join(f"  - {v}" for v in violations)
        )


class TestInlineProtocolsInjectsMainWorktree:
    """The propagation script must inject Protocol: Resolve Main Worktree Path
    as a foundational dependency for any skill that touches .optimus/ files."""

    def test_state_touching_skills_have_main_worktree_inlined(self):
        """Skills that inline State Management / Session State / Stats /
        Initialize .optimus / Migrate / Rename must also inline the main
        worktree resolver."""
        triggers = (
            "### Protocol: State Management",
            "### Protocol: Session State",
            "### Protocol: Increment Stage Stats",
            "### Protocol: Initialize .optimus Directory",
            "### Protocol: Migrate tasks.md to tasksDir",
            "### Protocol: Rename tasks.md to optimus-tasks.md",
            "### Protocol: Divergence Warning",
        )
        resolver_heading = "### Protocol: Resolve Main Worktree Path"
        violations = []
        for skill_path in _all_skill_files():
            content = _read(skill_path)
            inlined_start = content.find("<!-- INLINE-PROTOCOLS:START -->")
            if inlined_start == -1:
                continue  # skill has no inlined block (e.g., help, sync)
            inlined = content[inlined_start:]
            triggered = [t for t in triggers if t in inlined]
            if triggered and resolver_heading not in inlined:
                rel = skill_path.relative_to(REPO_ROOT)
                violations.append(
                    f"{rel}: inlines {triggered} but missing {resolver_heading!r}"
                )
        assert violations == [], (
            "Skills inlining state-touching protocols are missing the "
            "main-worktree resolver. Re-run "
            "`python3 scripts/inline-protocols.py` after editing AGENTS.md:\n"
            + "\n".join(f"  - {v}" for v in violations)
        )
