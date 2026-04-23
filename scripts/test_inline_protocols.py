#!/usr/bin/env python3
"""Tests for inline-protocols.py."""

import importlib.util
import tempfile
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location(
    "inline_protocols",
    Path(__file__).parent / "inline-protocols.py",
)
ip = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ip)


# --- parse_agents_md ---

class TestParseAgentsMd:
    def test_parses_h2_and_h3_sections(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        agents = tmp_path / "AGENTS.md"
        agents.write_text("## Section A\nContent A\n### Section B\nContent B\n")
        monkeypatch.setattr(ip, "AGENTS_MD", agents)
        sections = ip.parse_agents_md()
        assert "Section A" in sections
        assert "Section B" in sections
        assert "Content A" in sections["Section A"]
        assert "Content B" in sections["Section B"]

    def test_ignores_h1_and_h4(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        agents = tmp_path / "AGENTS.md"
        agents.write_text("# H1\nIgnored\n## H2\nKept\n#### H4\nAlso kept in H2\n")
        monkeypatch.setattr(ip, "AGENTS_MD", agents)
        sections = ip.parse_agents_md()
        assert "H1" not in sections
        assert "H4" not in sections
        assert "H2" in sections
        assert "Also kept in H2" in sections["H2"]

    def test_empty_file(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        agents = tmp_path / "AGENTS.md"
        agents.write_text("")
        monkeypatch.setattr(ip, "AGENTS_MD", agents)
        assert ip.parse_agents_md() == {}

    def test_missing_file_exits(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setattr(ip, "AGENTS_MD", tmp_path / "nonexistent.md")
        with pytest.raises(SystemExit):
            ip.parse_agents_md()


# --- extract_refs_from_skill ---

class TestExtractRefsFromSkill:
    def _write_skill(self, tmp_path: Path, content: str) -> Path:
        p = tmp_path / "SKILL.md"
        p.write_text(content)
        return p

    def test_protocol_ref(self, tmp_path: Path):
        p = self._write_skill(tmp_path, "see AGENTS.md Protocol: State Management.")
        refs = ip.extract_refs_from_skill(p)
        assert "Protocol: State Management" in refs

    def test_protocol_with_trailing_sentence(self, tmp_path: Path):
        p = self._write_skill(tmp_path, "AGENTS.md Protocol: Session State. Use stage=check.")
        refs = ip.extract_refs_from_skill(p)
        assert "Protocol: Session State" in refs

    def test_protocol_with_comma_clause(self, tmp_path: Path):
        p = self._write_skill(tmp_path, "AGENTS.md Protocol: PR Title Validation, with the addition that X.")
        refs = ip.extract_refs_from_skill(p)
        assert "Protocol: PR Title Validation" in refs

    def test_protocol_with_dots_in_name(self, tmp_path: Path):
        p = self._write_skill(tmp_path, "see AGENTS.md Protocol: tasks.md Validation.")
        refs = ip.extract_refs_from_skill(p)
        assert "Protocol: tasks.md Validation" in refs

    def test_common_pattern_ref(self, tmp_path: Path):
        p = self._write_skill(tmp_path, 'AGENTS.md "Common Patterns > Convergence Loop"')
        refs = ip.extract_refs_from_skill(p)
        assert "Common: Convergence Loop" in refs

    def test_finding_presentation_ref(self, tmp_path: Path):
        p = self._write_skill(tmp_path, 'AGENTS.md "Finding Presentation"')
        refs = ip.extract_refs_from_skill(p)
        assert "Common: Finding Presentation" in refs

    def test_no_refs(self, tmp_path: Path):
        p = self._write_skill(tmp_path, "No references here.")
        assert ip.extract_refs_from_skill(p) == set()

    def test_excludes_refs_from_inlined_block(self, tmp_path: Path):
        content = (
            "Body ref: AGENTS.md Protocol: Push Commits.\n"
            f"{ip.MARKER_START}\n"
            "Inlined: AGENTS.md Protocol: Should Not Match.\n"
            f"{ip.MARKER_END}\n"
        )
        p = self._write_skill(tmp_path, content)
        refs = ip.extract_refs_from_skill(p)
        assert "Protocol: Push Commits" in refs
        assert "Protocol: Should Not Match" not in refs


# --- _normalize_key ---

class TestNormalizeKey:
    def test_strips_trailing_parens(self):
        assert ip._normalize_key("tasks.md Validation (HARD BLOCK)") == "tasks.md validation"

    def test_no_parens(self):
        assert ip._normalize_key("Push Commits") == "push commits"

    def test_empty(self):
        assert ip._normalize_key("") == ""


# --- match_ref_to_section ---

class TestMatchRefToSection:
    SECTIONS = {
        "Protocol: State Management": "...",
        "Protocol: tasks.md Validation (HARD BLOCK)": "...",
        "Protocol: TaskSpec Resolution": "...",
        "Protocol: Push Commits (optional)": "...",
        "Convergence Loop (Full Roster Model)": "...",
        "Finding Presentation (Unified Model)": "...",
    }

    def test_exact_match(self):
        assert ip.match_ref_to_section("Protocol: State Management", self.SECTIONS) == "Protocol: State Management"

    def test_match_ignores_parenthetical(self):
        assert ip.match_ref_to_section("Protocol: tasks.md Validation", self.SECTIONS) == "Protocol: tasks.md Validation (HARD BLOCK)"

    def test_no_ambiguous_match(self):
        result = ip.match_ref_to_section("Protocol: TaskSpec Resolution", self.SECTIONS)
        assert result == "Protocol: TaskSpec Resolution"

    def test_common_match(self):
        result = ip.match_ref_to_section("Common: Convergence Loop", self.SECTIONS)
        assert result == "Convergence Loop (Full Roster Model)"

    def test_no_match(self):
        assert ip.match_ref_to_section("Protocol: Nonexistent", self.SECTIONS) is None


# --- strip_existing_inline ---

class TestStripExistingInline:
    def test_no_markers(self):
        assert ip.strip_existing_inline("Hello world") == "Hello world"

    def test_removes_inline_block(self):
        content = f"Before\n{ip.MARKER_START}\nInlined\n{ip.MARKER_END}\nAfter"
        result = ip.strip_existing_inline(content)
        assert "Before" in result
        assert "Inlined" not in result
        assert "After" in result

    def test_preserves_content_after_end(self):
        content = f"Before\n{ip.MARKER_START}\nX\n{ip.MARKER_END}\nTrailing"
        result = ip.strip_existing_inline(content)
        assert "Trailing" in result

    def test_missing_end_marker_returns_unchanged(self):
        content = f"Before\n{ip.MARKER_START}\nOrphaned"
        result = ip.strip_existing_inline(content)
        assert result == content


# --- idempotency integration test ---

class TestIdempotency:
    def test_double_run_produces_same_output(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        agents = tmp_path / "AGENTS.md"
        agents.write_text("## Protocol: Example\nExample content\n")
        monkeypatch.setattr(ip, "AGENTS_MD", agents)
        monkeypatch.setattr(ip, "REPO_ROOT", tmp_path)

        skill_dir = tmp_path / "myplugin" / "skills" / "optimus-myplugin"
        skill_dir.mkdir(parents=True)
        skill = skill_dir / "SKILL.md"
        skill.write_text("Body: see AGENTS.md Protocol: Example.\n")

        ip.inline_protocols()
        content_after_first = skill.read_text()

        ip.inline_protocols()
        content_after_second = skill.read_text()

        assert content_after_first == content_after_second
