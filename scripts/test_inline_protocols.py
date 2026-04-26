#!/usr/bin/env python3
"""Tests for inline-protocols.py."""

import importlib.util
import re
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
        p = self._write_skill(tmp_path, "AGENTS.md Protocol: Session State. Use stage=review.")
        refs = ip.extract_refs_from_skill(p)
        assert "Protocol: Session State" in refs

    def test_protocol_with_comma_clause(self, tmp_path: Path):
        p = self._write_skill(tmp_path, "AGENTS.md Protocol: PR Title Validation, with the addition that X.")
        refs = ip.extract_refs_from_skill(p)
        assert "Protocol: PR Title Validation" in refs

    def test_protocol_with_dots_in_name(self, tmp_path: Path):
        p = self._write_skill(tmp_path, "see AGENTS.md Protocol: optimus-tasks.md Validation.")
        refs = ip.extract_refs_from_skill(p)
        assert "Protocol: optimus-tasks.md Validation" in refs

    def test_common_pattern_ref(self, tmp_path: Path):
        p = self._write_skill(tmp_path, 'AGENTS.md "Common Patterns > Convergence Loop"')
        refs = ip.extract_refs_from_skill(p)
        assert "Common: Convergence Loop" in refs

    def test_finding_presentation_ref(self, tmp_path: Path):
        p = self._write_skill(tmp_path, 'AGENTS.md "Finding Presentation"')
        refs = ip.extract_refs_from_skill(p)
        assert "Common: Finding Presentation" in refs

    def test_protocol_with_semicolon_trailing(self, tmp_path: Path):
        p = self._write_skill(tmp_path, "AGENTS.md Protocol: Session State; also do X.")
        refs = ip.extract_refs_from_skill(p)
        assert "Protocol: Session State" in refs

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
        assert ip._normalize_key("optimus-tasks.md Validation (HARD BLOCK)") == "optimus-tasks.md validation"

    def test_no_parens(self):
        assert ip._normalize_key("Push Commits") == "push commits"

    def test_empty(self):
        assert ip._normalize_key("") == ""


# --- match_ref_to_section ---

class TestMatchRefToSection:
    SECTIONS = {
        "Protocol: State Management": "...",
        "Protocol: optimus-tasks.md Validation (HARD BLOCK)": "...",
        "Protocol: TaskSpec Resolution": "...",
        "Protocol: Push Commits (optional)": "...",
        "Protocol: Convergence Loop (Full Roster Model — Opt-In, Gated)": "...",
        "Finding Presentation (Unified Model)": "...",
    }

    def test_exact_match(self):
        assert ip.match_ref_to_section("Protocol: State Management", self.SECTIONS) == "Protocol: State Management"

    def test_match_ignores_parenthetical(self):
        assert ip.match_ref_to_section("Protocol: optimus-tasks.md Validation", self.SECTIONS) == "Protocol: optimus-tasks.md Validation (HARD BLOCK)"

    def test_no_ambiguous_match(self):
        result = ip.match_ref_to_section("Protocol: TaskSpec Resolution", self.SECTIONS)
        assert result == "Protocol: TaskSpec Resolution"

    def test_common_match(self):
        result = ip.match_ref_to_section(
            "Common: Protocol: Convergence Loop (Full Roster Model — Opt-In, Gated)",
            self.SECTIONS,
        )
        assert result == "Protocol: Convergence Loop (Full Roster Model — Opt-In, Gated)"

    def test_no_match(self):
        assert ip.match_ref_to_section("Protocol: Nonexistent", self.SECTIONS) is None

    def test_startswith_does_not_overmatch(self):
        sections = {
            "Protocol: Task": "...",
            "Protocol: TaskSpec Resolution": "...",
        }
        result = ip.match_ref_to_section("Protocol: Task", sections)
        assert result == "Protocol: Task"

    def test_convergence_loop_resolves_against_live_agents_md(self):
        """Regression guard: the live AGENTS.md heading must resolve via the parser.

        Catches the failure mode where AGENTS.md heading drifts (e.g., adding/removing
        'Protocol:' prefix) and SKILL.md references stop resolving. This is a higher-
        fidelity check than the synthetic SECTIONS fixture above.
        """
        agents_md = Path(__file__).parent.parent / "AGENTS.md"
        sections = _parse_real_agents_md(agents_md)
        # The reference text emitted by extract_refs for SKILL.md content
        # `AGENTS.md "Common Patterns > Protocol: Convergence Loop (Full Roster Model — Opt-In, Gated)"`
        ref = "Common: Protocol: Convergence Loop (Full Roster Model — Opt-In, Gated)"
        result = ip.match_ref_to_section(ref, sections)
        assert result is not None, (
            f"Live AGENTS.md heading did not resolve for ref {ref!r}. "
            "Parser, heading, or match logic drifted."
        )
        assert "Convergence Loop" in result

    def test_validation_protocol_token_matches_live_heading(self):
        """Regression guard for VALIDATION_PROTOCOL_TOKEN constant.

        The needs_format substring matcher in inline-protocols.py uses the
        VALIDATION_PROTOCOL_TOKEN constant to detect the format-validation
        protocol heading. If the heading is renamed in AGENTS.md, this test
        flags the drift before propagation silently breaks foundational
        injection (Rename, Resolve Tasks Git Scope).
        """
        agents_md = Path(__file__).parent.parent / "AGENTS.md"
        sections = _parse_real_agents_md(agents_md)
        matching = [k for k in sections if ip.VALIDATION_PROTOCOL_TOKEN in k]
        assert matching, (
            f"VALIDATION_PROTOCOL_TOKEN ({ip.VALIDATION_PROTOCOL_TOKEN!r}) "
            "matches no heading in live AGENTS.md. The token in "
            "inline-protocols.py drifted from the actual heading text."
        )


def _parse_real_agents_md(path):
    """Minimal section parser used by the live regression test."""
    sections: dict[str, str] = {}
    current_key = None
    current_lines: list[str] = []
    for line in path.read_text().splitlines():
        m = re.match(r"^(?:#{2,3})\s+(.+)$", line)
        if m:
            if current_key:
                sections[current_key] = "\n".join(current_lines)
            current_key = m.group(1).strip()
            current_lines = []
        else:
            current_lines.append(line)
    if current_key:
        sections[current_key] = "\n".join(current_lines)
    return sections


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

    def test_skips_skill_without_refs(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]):
        agents = tmp_path / "AGENTS.md"
        agents.write_text("## Protocol: Example\nContent\n")
        monkeypatch.setattr(ip, "AGENTS_MD", agents)
        monkeypatch.setattr(ip, "REPO_ROOT", tmp_path)

        skill_dir = tmp_path / "noop" / "skills" / "optimus-noop"
        skill_dir.mkdir(parents=True)
        skill = skill_dir / "SKILL.md"
        skill.write_text("No references here.\n")

        ip.inline_protocols()
        assert "no AGENTS.md refs, skipping" in capsys.readouterr().out
        assert ip.MARKER_START not in skill.read_text()

    def test_warns_on_unmatched_refs(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]):
        agents = tmp_path / "AGENTS.md"
        agents.write_text("## Protocol: Real\nContent\n")
        monkeypatch.setattr(ip, "AGENTS_MD", agents)
        monkeypatch.setattr(ip, "REPO_ROOT", tmp_path)

        skill_dir = tmp_path / "bad" / "skills" / "optimus-bad"
        skill_dir.mkdir(parents=True)
        skill = skill_dir / "SKILL.md"
        skill.write_text("see AGENTS.md Protocol: Nonexistent.\n")

        ip.inline_protocols()
        assert "unmatched" in capsys.readouterr().out.lower()

    def test_includes_foundational_for_state_management(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        agents = tmp_path / "AGENTS.md"
        agents.write_text(
            "## File Location\nFile location content\n"
            "## Valid Status Values (stored in state.json)\nStatus values\n"
            "## Protocol: State Management\nState mgmt content\n"
        )
        monkeypatch.setattr(ip, "AGENTS_MD", agents)
        monkeypatch.setattr(ip, "REPO_ROOT", tmp_path)

        skill_dir = tmp_path / "st" / "skills" / "optimus-st"
        skill_dir.mkdir(parents=True)
        skill = skill_dir / "SKILL.md"
        skill.write_text("see AGENTS.md Protocol: State Management.\n")

        ip.inline_protocols()
        content = skill.read_text()
        assert "File location content" in content
        assert "Status values" in content
        assert "State mgmt content" in content

    def test_handles_read_error_gracefully(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]):
        agents = tmp_path / "AGENTS.md"
        agents.write_text("## Protocol: X\nContent\n")
        monkeypatch.setattr(ip, "AGENTS_MD", agents)
        monkeypatch.setattr(ip, "REPO_ROOT", tmp_path)

        skill_dir = tmp_path / "err" / "skills" / "optimus-err"
        skill_dir.mkdir(parents=True)
        skill = skill_dir / "SKILL.md"
        skill.write_text("see AGENTS.md Protocol: X.\n")
        skill.chmod(0o000)

        try:
            ip.inline_protocols()
            captured = capsys.readouterr()
            output = captured.out + captured.err
            assert "ERROR" in output and "skipping" in output.lower()
        finally:
            skill.chmod(0o644)

    def test_processes_multiple_skills(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        agents = tmp_path / "AGENTS.md"
        agents.write_text("## Protocol: Alpha\nAlpha content\n## Protocol: Beta\nBeta content\n")
        monkeypatch.setattr(ip, "AGENTS_MD", agents)
        monkeypatch.setattr(ip, "REPO_ROOT", tmp_path)

        for name, ref in [("aaa", "Alpha"), ("bbb", "Beta")]:
            d = tmp_path / name / "skills" / f"optimus-{name}"
            d.mkdir(parents=True)
            (d / "SKILL.md").write_text(f"see AGENTS.md Protocol: {ref}.\n")

        ip.inline_protocols()

        a = (tmp_path / "aaa" / "skills" / "optimus-aaa" / "SKILL.md").read_text()
        b = (tmp_path / "bbb" / "skills" / "optimus-bbb" / "SKILL.md").read_text()
        assert "Alpha content" in a
        assert "Beta content" not in a
        assert "Beta content" in b
        assert "Alpha content" not in b


# --- F3: Critical path tests ---

class TestCriticalPaths:
    def test_duplicate_heading_keeps_last(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        agents = tmp_path / "AGENTS.md"
        agents.write_text("## Same\nFirst content\n## Same\nSecond content\n")
        monkeypatch.setattr(ip, "AGENTS_MD", agents)
        sections = ip.parse_agents_md()
        assert "Second content" in sections["Same"]
        assert "First content" not in sections["Same"]

    def test_multiple_mixed_refs_in_single_file(self, tmp_path: Path):
        content = (
            "see AGENTS.md Protocol: State Management.\n"
            'also AGENTS.md "Common Patterns > Convergence Loop"\n'
            'and AGENTS.md "Finding Presentation"\n'
            "plus AGENTS.md Protocol: Push Commits.\n"
        )
        p = tmp_path / "SKILL.md"
        p.write_text(content)
        refs = ip.extract_refs_from_skill(p)
        assert len(refs) == 4
        assert "Protocol: State Management" in refs
        assert "Common: Convergence Loop" in refs
        assert "Common: Finding Presentation" in refs
        assert "Protocol: Push Commits" in refs

    def test_handles_write_error_gracefully(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]):
        agents = tmp_path / "AGENTS.md"
        agents.write_text("## Protocol: Y\nContent Y\n")
        monkeypatch.setattr(ip, "AGENTS_MD", agents)
        monkeypatch.setattr(ip, "REPO_ROOT", tmp_path)

        skill_dir = tmp_path / "wr" / "skills" / "optimus-wr"
        skill_dir.mkdir(parents=True)
        skill = skill_dir / "SKILL.md"
        skill.write_text("see AGENTS.md Protocol: Y.\n")
        skill.chmod(0o444)

        try:
            ip.inline_protocols()
            captured = capsys.readouterr()
            output = captured.out + captured.err
            assert "ERROR" in output or "Failed to write" in output
        finally:
            skill.chmod(0o644)


# --- F4: Edge case tests ---

class TestEdgeCases:
    def test_protocol_with_bold_trailing(self, tmp_path: Path):
        p = tmp_path / "SKILL.md"
        p.write_text("AGENTS.md Protocol: State Management**")
        refs = ip.extract_refs_from_skill(p)
        assert "Protocol: State Management" in refs

    def test_normalize_key_multiple_parens_strips_only_last(self):
        assert ip._normalize_key("X (A) (B)") == "x (a)"

    def test_strip_multiple_inline_blocks_strips_first(self):
        content = f"A\n{ip.MARKER_START}\nB\n{ip.MARKER_END}\nC\n{ip.MARKER_START}\nD\n{ip.MARKER_END}\nE"
        result = ip.strip_existing_inline(content)
        assert "A" in result
        assert "B" not in result
        assert "C" in result

    def test_heading_with_special_chars(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        agents = tmp_path / "AGENTS.md"
        agents.write_text("## Protocol: optimus-tasks.md Validation (HARD BLOCK)\nValidation content\n")
        monkeypatch.setattr(ip, "AGENTS_MD", agents)
        sections = ip.parse_agents_md()
        assert "Protocol: optimus-tasks.md Validation (HARD BLOCK)" in sections

    def test_protocol_with_trailing_paren(self, tmp_path: Path):
        p = tmp_path / "SKILL.md"
        p.write_text("AGENTS.md Protocol: Push Commits)")
        refs = ip.extract_refs_from_skill(p)
        assert "Protocol: Push Commits" in refs

    def test_unicode_heading(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        agents = tmp_path / "AGENTS.md"
        agents.write_text("## Protocol: Notifica\u00e7\u00e3o de Status\nContent\n")
        monkeypatch.setattr(ip, "AGENTS_MD", agents)
        sections = ip.parse_agents_md()
        assert "Protocol: Notifica\u00e7\u00e3o de Status" in sections

    def test_includes_foundational_for_taskspec(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        agents = tmp_path / "AGENTS.md"
        agents.write_text(
            "## Task Spec Resolution\nTaskSpec resolution content\n"
            "## Protocol: TaskSpec Resolution\nTaskSpec protocol content\n"
        )
        monkeypatch.setattr(ip, "AGENTS_MD", agents)
        monkeypatch.setattr(ip, "REPO_ROOT", tmp_path)

        skill_dir = tmp_path / "ts" / "skills" / "optimus-ts"
        skill_dir.mkdir(parents=True)
        skill = skill_dir / "SKILL.md"
        skill.write_text("see AGENTS.md Protocol: TaskSpec Resolution.\n")

        ip.inline_protocols()
        content = skill.read_text()
        assert "TaskSpec resolution content" in content
        assert "TaskSpec protocol content" in content

    def test_unicode_decode_error_gracefully(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]):
        agents = tmp_path / "AGENTS.md"
        agents.write_text("## Protocol: Z\nContent Z\n")
        monkeypatch.setattr(ip, "AGENTS_MD", agents)
        monkeypatch.setattr(ip, "REPO_ROOT", tmp_path)

        skill_dir = tmp_path / "uc" / "skills" / "optimus-uc"
        skill_dir.mkdir(parents=True)
        skill = skill_dir / "SKILL.md"
        skill.write_bytes(b'\xff\xfe see AGENTS.md Protocol: Z.\n')

        ip.inline_protocols()
        captured = capsys.readouterr()
        output = captured.out + captured.err
        assert "ERROR" in output and "skipping" in output.lower()
