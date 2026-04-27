#!/usr/bin/env python3
"""Tests for inline-protocols.py."""

import importlib.util
import re
from pathlib import Path

import pytest

_IP_PATH = Path(__file__).parent / "inline-protocols.py"
spec = importlib.util.spec_from_file_location("inline_protocols", _IP_PATH)
assert spec is not None, f"Cannot load spec for {_IP_PATH}"
assert spec.loader is not None, f"Spec loader is None for {_IP_PATH}"
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

    def test_startswith_prefers_longest_match_with_warning(
        self, capsys: pytest.CaptureFixture[str]
    ):
        """F3.3a: When 2+ keys share the same prefix, prefer the LONGEST match
        (most specific) and emit a WARNING to stderr about the ambiguity.

        Without this guard, the resolver returned the first key in dict-iteration
        order — fragile and silently mis-routed refs.
        """
        # Use a prefix `Foo` that matches both `Foo` and `Foo Bar Resolution`.
        # The reference `Protocol: Foo` should resolve to the LONGER key
        # because the resolver collects all startswith candidates and picks
        # the longest, with a stderr warning.
        sections = {
            "Protocol: Foo Bar Resolution": "long",
            "Protocol: Foo Bar": "medium",
        }
        # Ref `Protocol: Foo Ba` matches BOTH startswith targets;
        # the longest one (Foo Bar Resolution) must win.
        result = ip.match_ref_to_section("Protocol: Foo Ba", sections)
        assert result == "Protocol: Foo Bar Resolution"
        captured = capsys.readouterr()
        assert "WARNING" in captured.err
        assert "ambiguous ref" in captured.err
        assert "Protocol: Foo Bar Resolution" in captured.err
        assert "Protocol: Foo Bar" in captured.err

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

    def test_missing_end_marker_returns_unchanged(self, capsys: pytest.CaptureFixture[str]):
        content = f"Before\n{ip.MARKER_START}\nOrphaned"
        result = ip.strip_existing_inline(content)
        assert result == content
        captured = capsys.readouterr()
        assert "WARNING" in captured.err
        assert "MARKER_START found but MARKER_END missing" in captured.err


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
        captured = capsys.readouterr()
        assert "WARNING: unmatched ref" in captured.err

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
        # F9-3: Use monkeypatch instead of chmod 0o000, which is bypassed when
        # tests run as root (e.g., in CI containers). Forcing PermissionError
        # via Path.read_text is deterministic across user contexts.
        agents = tmp_path / "AGENTS.md"
        agents.write_text("## Protocol: X\nContent\n")
        monkeypatch.setattr(ip, "AGENTS_MD", agents)
        monkeypatch.setattr(ip, "REPO_ROOT", tmp_path)

        skill_dir = tmp_path / "err" / "skills" / "optimus-err"
        skill_dir.mkdir(parents=True)
        skill = skill_dir / "SKILL.md"
        skill.write_text("see AGENTS.md Protocol: X.\n")

        original_read_text = Path.read_text

        def fake_read_text(self, *args, **kwargs):
            if self.name == "SKILL.md":
                raise PermissionError("simulated permission denied")
            return original_read_text(self, *args, **kwargs)

        monkeypatch.setattr(Path, "read_text", fake_read_text)

        ip.inline_protocols()
        captured = capsys.readouterr()
        output = captured.out + captured.err
        assert "ERROR" in output and "skipping" in output.lower()

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
    def test_duplicate_heading_keeps_last(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]):
        agents = tmp_path / "AGENTS.md"
        agents.write_text("## Same\nFirst content\n## Same\nSecond content\n")
        monkeypatch.setattr(ip, "AGENTS_MD", agents)
        sections = ip.parse_agents_md()
        assert "Second content" in sections["Same"]
        assert "First content" not in sections["Same"]
        captured = capsys.readouterr()
        assert "WARNING" in captured.err
        assert "Duplicate heading" in captured.err

    def test_duplicate_heading_warns_on_second_occurrence(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ):
        """Regression guard: warning must fire on the SECOND duplicate, not the third.

        With the bug fixed, exactly two `## Dup` headings produce a WARNING.
        """
        agents = tmp_path / "AGENTS.md"
        agents.write_text("## Dup\nA\n## Dup\nB\n")
        monkeypatch.setattr(ip, "AGENTS_MD", agents)
        sections = ip.parse_agents_md()
        assert "Dup" in sections
        captured = capsys.readouterr()
        assert "WARNING" in captured.err
        assert "Duplicate heading" in captured.err
        assert "'Dup'" in captured.err

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
        # F9-3: Use monkeypatch instead of chmod 0o555 on the parent dir, which
        # is bypassed when tests run as root. Forcing OSError on Path.write_text
        # for the atomic-write tmp sibling is deterministic across user contexts.
        agents = tmp_path / "AGENTS.md"
        agents.write_text("## Protocol: Y\nContent Y\n")
        monkeypatch.setattr(ip, "AGENTS_MD", agents)
        monkeypatch.setattr(ip, "REPO_ROOT", tmp_path)

        skill_dir = tmp_path / "wr" / "skills" / "optimus-wr"
        skill_dir.mkdir(parents=True)
        skill = skill_dir / "SKILL.md"
        skill.write_text("see AGENTS.md Protocol: Y.\n")

        original_write_text = Path.write_text

        def fake_write_text(self, *args, **kwargs):
            # F3.3c: atomic write writes to a `<name>.tmp` sibling first, then
            # uses tmp.replace(skill_path). Trip on the .tmp sibling so the
            # OSError fires inside the production atomic-write try block.
            if self.name == "SKILL.md.tmp":
                raise OSError("simulated write failure")
            return original_write_text(self, *args, **kwargs)

        monkeypatch.setattr(Path, "write_text", fake_write_text)

        ip.inline_protocols()
        captured = capsys.readouterr()
        output = captured.out + captured.err
        assert "ERROR" in output or "Failed to write" in output


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


# --- F3.3d: Symlink-write defense ---

class TestSymlinkWrite:
    def test_refuses_to_write_through_symlink(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ):
        """F3.3d: A SKILL.md that is a symlink must NOT be overwritten.

        Defense-in-depth: a malicious commit could replace SKILL.md with a
        symlink to ~/.bashrc and we'd otherwise clobber the target.
        """
        agents = tmp_path / "AGENTS.md"
        agents.write_text("## Protocol: Sym\nSym content\n")
        monkeypatch.setattr(ip, "AGENTS_MD", agents)
        monkeypatch.setattr(ip, "REPO_ROOT", tmp_path)

        # Create the real target file outside the SKILL path
        target = tmp_path / "real_target.md"
        target.write_text("ORIGINAL TARGET CONTENT — must not be overwritten\n")

        # Create the SKILL dir + symlink-as-SKILL.md
        skill_dir = tmp_path / "linked" / "skills" / "optimus-linked"
        skill_dir.mkdir(parents=True)
        skill = skill_dir / "SKILL.md"
        # Stage refs by writing through the symlink target, then convert to symlink
        target.write_text("see AGENTS.md Protocol: Sym.\n")
        skill.symlink_to(target)

        ip.inline_protocols()
        captured = capsys.readouterr()
        assert "ERROR" in captured.err
        assert "refusing to write through symlink" in captured.err
        # Target must remain unchanged.
        assert target.read_text() == "see AGENTS.md Protocol: Sym.\n"
        # MARKER_START must NOT appear in target (proves no write happened).
        assert ip.MARKER_START not in target.read_text()


# --- F3.3e: Body-level paste detection ---

class TestBodyLevelInlineGuard:
    def _setup(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, body: str):
        agents = tmp_path / "AGENTS.md"
        agents.write_text("## Protocol: Echo\nEcho content\n")
        monkeypatch.setattr(ip, "AGENTS_MD", agents)
        monkeypatch.setattr(ip, "REPO_ROOT", tmp_path)
        skill_dir = tmp_path / "echo" / "skills" / "optimus-echo"
        skill_dir.mkdir(parents=True)
        skill = skill_dir / "SKILL.md"
        skill.write_text(body)
        return skill

    def test_warns_on_quiet_run_in_body(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ):
        body = (
            "see AGENTS.md Protocol: Echo.\n"
            "```bash\n"
            "_optimus_quiet_run() {\n"
            "  echo manual\n"
            "}\n"
            "```\n"
        )
        self._setup(tmp_path, monkeypatch, body)
        ip.inline_protocols()
        captured = capsys.readouterr()
        assert "WARNING" in captured.err
        assert "_optimus_quiet_run" in captured.err
        assert "manual definition" in captured.err

    def test_warns_on_set_title_in_body(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ):
        body = (
            "see AGENTS.md Protocol: Echo.\n"
            "_optimus_set_title() {\n"
            "  printf '\\033]0;%s\\007' \"$1\"\n"
            "}\n"
        )
        self._setup(tmp_path, monkeypatch, body)
        ip.inline_protocols()
        captured = capsys.readouterr()
        assert "WARNING" in captured.err
        assert "_optimus_set_title" in captured.err

    def test_warns_on_sanitize_regression(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ):
        # _optimus_sanitize was removed in F2; this is a future regression guard.
        body = (
            "see AGENTS.md Protocol: Echo.\n"
            "_optimus_sanitize() {\n"
            "  echo regression\n"
            "}\n"
        )
        self._setup(tmp_path, monkeypatch, body)
        ip.inline_protocols()
        captured = capsys.readouterr()
        assert "WARNING" in captured.err
        assert "_optimus_sanitize" in captured.err


# --- F3.3f: Canonical reference phrasing in skills ---

class TestCanonicalReferencePhrasing:
    """Scan every SKILL.md and assert AGENTS.md Protocol: refs use canonical form."""

    def test_no_unanchored_protocol_references(self):
        """F3.3f: Every `AGENTS.md Protocol:` mention in a SKILL body must
        either follow canonical phrasing or live in a code/quote block.

        Canonical form: `AGENTS.md Protocol: <Heading>` (the regex anchor
        used by the inliner). Deviations (e.g. `AGENTS.md "Protocol: X"`)
        cause silent unmatched refs.
        """
        repo_root = Path(__file__).parent.parent
        skill_files = sorted(repo_root.glob("*/skills/*/SKILL.md"))
        assert skill_files, "No SKILL.md files found — fixture broken"

        offenders: list[str] = []
        # Canonical: literally "AGENTS.md Protocol: <Heading>"
        # The inliner regex is PROTOCOL_RE = r'AGENTS\.md Protocol:\s*([^\n"]+)'
        canonical_re = re.compile(r'AGENTS\.md\s+Protocol:\s*[^\n"]+')
        # Suspicious: an unanchored mention of `Protocol:` adjacent to AGENTS.md
        # but not matching the canonical form. Examples we'd flag:
        #   `AGENTS.md "Protocol: X"`           (quoted)
        #   `AGENTS.md\nProtocol: X`            (newline-separated)
        suspicious_re = re.compile(r'AGENTS\.md["\s]+Protocol:')

        for skill in skill_files:
            content = skill.read_text()
            # Strip out the inlined block — those refs are not authoritative.
            content = ip.strip_existing_inline(content)
            # Strip fenced code blocks and block-quotes to avoid false positives.
            content_no_fences = re.sub(r"```[\s\S]*?```", "", content)
            content_no_quotes = "\n".join(
                line for line in content_no_fences.splitlines()
                if not line.lstrip().startswith(">")
            )
            for m in suspicious_re.finditer(content_no_quotes):
                # Verify it's not actually canonical (the canonical form
                # also matches the suspicious regex if there's a single space).
                snippet = content_no_quotes[m.start(): m.start() + 80]
                # Canonical form has exactly one space and no quote between
                # `AGENTS.md` and `Protocol:`.
                head = snippet[: snippet.index("Protocol:")]
                # Strip "AGENTS.md" prefix.
                between = head[len("AGENTS.md"):]
                # Canonical: " " (one space). Anything else (multiple
                # whitespace, quotes, newlines) is non-canonical.
                if between != " ":
                    offenders.append(f"{skill}: {snippet!r}")

        # Cross-check: for every canonical mention we found, drop into the
        # offender list only if the previous regex did not catch it. (The
        # canonical regex is a sanity check and not used for offender output.)
        _ = canonical_re  # kept for future tightening; not used to fail here.

        assert not offenders, (
            "Non-canonical AGENTS.md Protocol references found:\n"
            + "\n".join(offenders)
        )


# --- F3.3h: MAX_FILE_SIZE boundary ---

class TestMaxFileSize:
    def test_oversized_agents_md_exits(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        agents = tmp_path / "AGENTS.md"
        agents.write_bytes(
            b"# header\n\n## Protocol: X\n\n" + b"x" * (5 * 1024 * 1024)
        )
        monkeypatch.setattr(ip, "AGENTS_MD", agents)
        with pytest.raises(SystemExit):
            ip.parse_agents_md()

    def test_oversized_skill_md_skipped_with_warning(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ):
        agents = tmp_path / "AGENTS.md"
        agents.write_text("## Protocol: Big\nBig content\n")
        monkeypatch.setattr(ip, "AGENTS_MD", agents)
        monkeypatch.setattr(ip, "REPO_ROOT", tmp_path)

        skill_dir = tmp_path / "big" / "skills" / "optimus-big"
        skill_dir.mkdir(parents=True)
        skill = skill_dir / "SKILL.md"
        # Write a payload that exceeds MAX_FILE_SIZE (5 MB).
        payload = b"see AGENTS.md Protocol: Big.\n" + b"x" * (5 * 1024 * 1024)
        skill.write_bytes(payload)

        ip.inline_protocols()
        captured = capsys.readouterr()
        assert "WARNING" in captured.err
        assert "exceeds" in captured.err
        assert "skipping" in captured.err
        # MARKER_START must NOT have been added (file was skipped).
        assert ip.MARKER_START not in skill.read_bytes().decode(
            "utf-8", errors="ignore"
        )


# --- F3.3i: Ref-alias collision INFO line ---

class TestRefAliasCollision:
    def test_emits_info_when_two_refs_collapse_to_one_key(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ):
        """F3.3i: When 2+ distinct refs map to the same section key, emit
        an INFO line so reviewers can decide if the aliasing is intentional.
        """
        agents = tmp_path / "AGENTS.md"
        # One heading. Two ways to reference it from the SKILL body:
        #   1. Exact: `Protocol: Foo Bar Resolution`
        #   2. Prefix that resolves via startswith: `Protocol: Foo Bar`
        # Both will map to `Protocol: Foo Bar Resolution`.
        agents.write_text("## Protocol: Foo Bar Resolution\nFoo content\n")
        monkeypatch.setattr(ip, "AGENTS_MD", agents)
        monkeypatch.setattr(ip, "REPO_ROOT", tmp_path)

        skill_dir = tmp_path / "alias" / "skills" / "optimus-alias"
        skill_dir.mkdir(parents=True)
        skill = skill_dir / "SKILL.md"
        skill.write_text(
            "see AGENTS.md Protocol: Foo Bar Resolution.\n"
            "also AGENTS.md Protocol: Foo Bar.\n"
        )

        ip.inline_protocols()
        captured = capsys.readouterr()
        assert "INFO" in captured.err
        assert "ref alias collapsed" in captured.err
        assert "Protocol: Foo Bar Resolution" in captured.err
