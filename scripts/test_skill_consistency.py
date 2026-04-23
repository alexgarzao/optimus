#!/usr/bin/env python3
"""Tests for cross-file consistency rules in SKILL.md and AGENTS.md."""

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
AGENTS_MD = REPO_ROOT / "AGENTS.md"


def _all_skill_files():
    return sorted(REPO_ROOT.glob("*/skills/*/SKILL.md"))


def _all_doc_files():
    files = [AGENTS_MD] + _all_skill_files()
    return [f for f in files if f.exists()]


# --- AskUser topic format must include (X/N) progress prefix ---

TOPIC_FORMAT_RE = re.compile(
    r"AskUser.*\[topic\].*format.*Format:\s*`([^`]+)`", re.IGNORECASE
)
TOPIC_EXAMPLE_RE = re.compile(
    r"Example:\s*`\[topic\]\s+([^`]+)`"
)
PROGRESS_PREFIX_RE = re.compile(r"\(X/N\)")
PROGRESS_EXAMPLE_RE = re.compile(r"\(\d+/\d+\)")


class TestAskUserTopicProgress:
    """Every AskUser [topic] format definition must include (X/N) progress prefix."""

    def _collect_violations(self, pattern, check_re, label):
        violations = []
        for filepath in _all_doc_files():
            text = filepath.read_text()
            for i, line in enumerate(text.splitlines(), 1):
                m = pattern.search(line)
                if m and not check_re.search(m.group(1)):
                    rel = filepath.relative_to(REPO_ROOT)
                    violations.append(f"{rel}:{i}: {label} missing in: {m.group(1)}")
        return violations

    def test_topic_format_has_progress_prefix(self):
        """All 'AskUser [topic] format: `...`' lines must contain (X/N)."""
        violations = self._collect_violations(
            TOPIC_FORMAT_RE, PROGRESS_PREFIX_RE, "(X/N)"
        )
        assert violations == [], (
            "AskUser topic format lines missing (X/N) prefix:\n"
            + "\n".join(f"  - {v}" for v in violations)
        )

    def test_topic_example_has_progress_prefix(self):
        """All 'Example: `[topic] ...`' lines for findings must contain (N/N) pattern."""
        violations = []
        for filepath in _all_doc_files():
            text = filepath.read_text()
            lines = text.splitlines()
            for i, line in enumerate(lines, 1):
                m = TOPIC_EXAMPLE_RE.search(line)
                if not m:
                    continue
                value = m.group(1)
                # Only check finding-related examples (contain F followed by digit)
                if not re.search(r"F\d", value):
                    continue
                if not PROGRESS_EXAMPLE_RE.search(value):
                    rel = filepath.relative_to(REPO_ROOT)
                    violations.append(f"{rel}:{i}: concrete (N/N) missing in: {value}")
        assert violations == [], (
            "AskUser topic example lines missing progress prefix:\n"
            + "\n".join(f"  - {v}" for v in violations)
        )

    def test_at_least_one_format_found(self):
        """Sanity: ensure the patterns actually match something."""
        count = 0
        for filepath in _all_doc_files():
            text = filepath.read_text()
            count += len(TOPIC_FORMAT_RE.findall(text))
        assert count >= 7, (
            f"Expected at least 7 AskUser topic format definitions, found {count}. "
            "Pattern may need updating."
        )
