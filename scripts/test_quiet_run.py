"""Tests for the _optimus_quiet_run bash helper and its adoption across skills.

The helper is defined in AGENTS.md Protocol: Quiet Command Execution and
auto-inlined into every consumer skill by scripts/inline-protocols.py.
These tests cover:
  1. Helper behavior (success, failure, exit codes, sanitization, edge cases)
  2. AGENTS.md protocol existence + canonical structure
  3. Adopter consistency (the 5 verification skills MUST wrap make commands)
  4. Coverage Measurement protocol updates (thresholds + helper wrapping)
  5. Gitignore inclusion of .optimus/logs/
"""

import re
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
AGENTS_MD = REPO_ROOT / "AGENTS.md"


def _helper_adopters_from_agents_md() -> list[str]:
    """Derive the adopter list from AGENTS.md so it can't drift silently.

    Source of truth: the `**Referenced by:**` line of Protocol: Quiet Command Execution.
    """
    section = _extract_protocol_section("Protocol: Quiet Command Execution")
    m = re.search(r"\*\*Referenced by:\*\*\s*([^\n]+)", section)
    if not m:
        raise RuntimeError("Cannot find 'Referenced by' line in Protocol: Quiet Command Execution")
    raw = m.group(1)
    # Strip parenthetical context like "(for `make test`, ...)" before splitting.
    raw = re.sub(r"\([^)]*\)", "", raw)
    return [a.strip() for a in raw.split(",") if a.strip()]


# HELPER_ADOPTERS is computed at module load time after _extract_protocol_section
# is defined below — see end of file for the actual binding via globals().


def _has_bash() -> bool:
    return shutil.which("bash") is not None


def _read_skill(plugin: str) -> str:
    paths = list(REPO_ROOT.glob(f"{plugin}/skills/*/SKILL.md"))
    if not paths:
        raise FileNotFoundError(f"No SKILL.md found for plugin '{plugin}'")
    return paths[0].read_text()


def _extract_protocol_section(title: str) -> str:
    """Extract the body of a `### Protocol: <title>` section in AGENTS.md."""
    content = AGENTS_MD.read_text()
    marker = f"### {title}"
    idx = content.find(marker)
    if idx == -1:
        raise RuntimeError(f"Section '{title}' not found in AGENTS.md")
    next_idx = content.find("\n### ", idx + len(marker))
    return content[idx:next_idx] if next_idx != -1 else content[idx:]


def _extract_helper_bash() -> str:
    """Extract the bash block that defines `_optimus_quiet_run()`.

    Content-based extraction (NOT positional) so that future contributors can
    add introductory examples without breaking every helper test with cryptic
    `bash: _optimus_quiet_run: command not found` errors.
    """
    section = _extract_protocol_section("Protocol: Quiet Command Execution")
    blocks = re.findall(r"```bash\n(.*?)\n```", section, re.DOTALL)
    for b in blocks:
        if "_optimus_quiet_run()" in b:
            return b
    raise RuntimeError(
        "Helper definition block (function `_optimus_quiet_run()`) not found "
        "in Protocol: Quiet Command Execution"
    )


def _run_helper(tmp_path: Path, snippet: str):
    """Run the helper definition + a snippet under bash, return (rc, stdout, stderr)."""
    helper = _extract_helper_bash()
    probe = f"{helper}\n{snippet}\n"
    result = subprocess.run(
        ["bash", "-c", probe],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode, result.stdout, result.stderr


# Derive adopter list from AGENTS.md "Referenced by" — single source of truth.
# Computed after _extract_protocol_section is in scope.
HELPER_ADOPTERS = _helper_adopters_from_agents_md()


# ---------------------------------------------------------------------------
# 1. Helper behavior (HARD BLOCK if any of these fail).
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not _has_bash(), reason="bash required")
class TestQuietRunHelper:
    """Direct execution of _optimus_quiet_run via bash -c."""

    def test_success_emits_pass_and_exits_zero(self, tmp_path: Path):
        rc, out, _ = _run_helper(tmp_path, '_optimus_quiet_run "ok" echo hi')
        assert rc == 0, f"expected exit 0, got {rc}; out={out}"
        assert out.startswith("PASS: ok "), f"unexpected output: {out}"
        assert "log: .optimus/logs/" in out
        log_files = list((tmp_path / ".optimus" / "logs").glob("*-ok-*.log"))
        assert len(log_files) == 1, f"expected 1 log file, got {len(log_files)}"
        assert "hi" in log_files[0].read_text()

    def test_failure_preserves_exit_code(self, tmp_path: Path):
        rc, out, _ = _run_helper(tmp_path, '_optimus_quiet_run "boom" sh -c "exit 7"')
        assert rc == 7, f"expected exit 7 (preserved), got {rc}"
        assert "FAIL: boom (exit=7" in out
        assert "--- last 50 lines ---" in out

    def test_empty_label_returns_2(self, tmp_path: Path):
        rc, _, err = _run_helper(tmp_path, '_optimus_quiet_run "" echo hi')
        assert rc == 2, f"expected exit 2 for empty label, got {rc}"
        assert "requires <label> and <command>" in err

    def test_missing_command_returns_2(self, tmp_path: Path):
        rc, _, err = _run_helper(tmp_path, '_optimus_quiet_run "label-only"')
        assert rc == 2, f"expected exit 2 for missing command, got {rc}"
        assert "requires <label> and <command>" in err

    def test_label_sanitization_special_chars(self, tmp_path: Path):
        rc, out, _ = _run_helper(
            tmp_path, '_optimus_quiet_run "weird/chars*here" echo ok'
        )
        assert rc == 0
        # The sanitized label must appear in the log path; '/' and '*' become '-'.
        assert "weird-chars-here-" in out, f"sanitization failed: {out}"

    def test_all_special_chars_falls_back_to_run(self, tmp_path: Path):
        rc, out, _ = _run_helper(tmp_path, '_optimus_quiet_run "///***???" echo ok')
        assert rc == 0
        assert "-run-" in out, f"expected fallback 'run' label, got: {out}"

    def test_creates_logs_dir(self, tmp_path: Path):
        _run_helper(tmp_path, '_optimus_quiet_run "x" echo ok')
        assert (tmp_path / ".optimus" / "logs").is_dir()

    def test_captures_stderr_too(self, tmp_path: Path):
        _run_helper(
            tmp_path, '_optimus_quiet_run "se" sh -c "echo to-err >&2"'
        )
        log = next((tmp_path / ".optimus" / "logs").glob("*-se-*.log"))
        assert "to-err" in log.read_text()

    def test_truncates_to_50_lines_on_failure(self, tmp_path: Path):
        # Escape $ so the outer bash does NOT expand $(seq ...) and $i — sh -c
        # must see the literal command-substitution and variable references.
        rc, out, _ = _run_helper(
            tmp_path,
            '_optimus_quiet_run "many" sh -c '
            '"for i in \\$(seq 1 200); do echo \\$i; done; exit 1"',
        )
        assert rc == 1, f"expected exit 1, got {rc}; out={out[:200]}"
        # Body between separator and end of stdout
        body = out.split("--- last 50 lines ---", 1)[1].strip().splitlines()
        # `cat -v` may add a trailing $ marker on the last line, but line count
        # should still be <= 50.
        assert len(body) <= 50, f"expected <=50 lines, got {len(body)}"

    def test_nonexistent_command_returns_127(self, tmp_path: Path):
        rc, out, _ = _run_helper(
            tmp_path, '_optimus_quiet_run "nx" /bin/no-such-command-here'
        )
        assert rc == 127, f"expected exit 127 for missing binary, got {rc}"
        assert "FAIL: nx (exit=127" in out

    def test_exit_code_works_with_if_chain(self, tmp_path: Path):
        """The whole point: `if _optimus_quiet_run ...; then` must short-circuit.

        Regression guard for the contract item: "Exit code preserved — Downstream
        `if _optimus_quiet_run ...; then ... fi` works the same as
        `if make test; then ... fi` would."
        """
        rc, out, _ = _run_helper(
            tmp_path,
            'if _optimus_quiet_run "p" true; then echo OK_TRUE; fi; '
            'if ! _optimus_quiet_run "f" false; then echo OK_FALSE; fi',
        )
        assert "OK_TRUE" in out, f"`if helper; then` did not short-circuit: {out}"
        assert "OK_FALSE" in out, f"`if !helper; then` did not short-circuit: {out}"

    def test_pid_suffix_creates_distinct_logs_for_separate_processes(self, tmp_path: Path):
        """Two SEPARATE bash processes (distinct PIDs) get distinct log files.

        This verifies the actual guarantee of the PID suffix: when two `bash -c`
        invocations run with the same label and timestamp, they produce two
        distinct log files (because the OS gives them distinct PIDs). It does
        NOT claim to prevent collisions for backgrounded subshells within ONE
        bash process — those share `$$` (only `$BASHPID` differs), which is a
        documented limitation of the helper.
        """
        helper = _extract_helper_bash()
        for _ in range(2):
            subprocess.run(
                ["bash", "-c", f"{helper}\n_optimus_quiet_run 'dup' echo A"],
                cwd=tmp_path,
                check=True,
                capture_output=True,
            )
        log_files = list((tmp_path / ".optimus" / "logs").glob("*-dup-*.log"))
        # On rare occasions both bash invocations get distinct PIDs but are
        # close enough to share a timestamp: still 2 distinct files because PID
        # differs. On extremely rare same-PID reuse, we'd have only 1 file —
        # but that is OS-level PID recycling, not a helper bug.
        assert len(log_files) >= 1, "expected at least 1 log file"
        contents = " ".join(p.read_text() for p in log_files)
        assert "A" in contents

    def test_umask_locks_log_to_owner_only(self, tmp_path: Path):
        """Log file must be owner-read/write only (mode 0600) to protect
        sensitive test output (credentials, internal stack traces) on
        multi-user systems."""
        _run_helper(tmp_path, '_optimus_quiet_run "perm" echo hi')
        log = next((tmp_path / ".optimus" / "logs").glob("*-perm-*.log"))
        mode = log.stat().st_mode & 0o777
        assert mode == 0o600, f"expected mode 0600 for log file, got {oct(mode)}"

    def test_failure_body_strips_terminal_escapes(self, tmp_path: Path):
        """Terminal escape sequences in failed-command output must NOT reach
        the agent's terminal raw — they must be neutralized via `cat -v`."""
        # Use printf inside sh -c with escaped backslash so the OUTER bash does
        # NOT interpret the escapes; sh's printf does.
        rc, out, _ = _run_helper(
            tmp_path,
            r'_optimus_quiet_run "esc" sh -c '
            r'"printf \"\\033]0;HACKED\\007payload\\n\"; exit 1"',
        )
        assert rc == 1
        body = out.split("--- last 50 lines ---", 1)[1]
        # The OSC sequence (ESC ] 0 ; ... BEL) must be NEUTRALIZED. cat -v
        # converts the actual ESC byte (0x1B) to the literal two-char "^[".
        assert "\x1b]0;HACKED" not in body, \
            "raw OSC escape sequence leaked through tail (cat -v missing or bypassed)"
        # Conversely, the caret-notation form ("^[" + "]0;HACKED" + "^G") must
        # appear, proving cat -v was applied.
        assert "^[]0;HACKED^G" in body, \
            "expected cat -v caret notation for ESC + BEL, got body: " + body[:200]


# ---------------------------------------------------------------------------
# 2. AGENTS.md protocol existence + canonical structure.
# ---------------------------------------------------------------------------


class TestQuietRunProtocolDoc:
    def test_protocol_section_exists(self):
        content = AGENTS_MD.read_text()
        assert "### Protocol: Quiet Command Execution" in content, (
            "AGENTS.md missing Protocol: Quiet Command Execution section"
        )

    def test_helper_function_defined(self):
        section = _extract_protocol_section("Protocol: Quiet Command Execution")
        assert "_optimus_quiet_run()" in section, (
            "Protocol: Quiet Command Execution must define _optimus_quiet_run()"
        )

    def test_contract_clauses_present(self):
        section = _extract_protocol_section("Protocol: Quiet Command Execution")
        for phrase in (
            "Success path (exit 0)",
            "Failure path (exit != 0)",
            "Exit code preserved",
            "Log retention",
            "Reserved exit codes",
        ):
            assert phrase in section, f"Protocol missing contract clause: {phrase}"

    def test_canonical_reference_string_present(self):
        """Skills reference this protocol by an exact phrase."""
        content = AGENTS_MD.read_text()
        assert "AGENTS.md Protocol: Quiet Command Execution" in content


# ---------------------------------------------------------------------------
# 3. Adopter consistency.
# ---------------------------------------------------------------------------


class TestQuietRunAdoption:
    """The 5 verification skills MUST wrap make commands in _optimus_quiet_run."""

    BARE_VERIFY_RE = re.compile(
        r"^(make\s+(lint|test|test-coverage|test-integration|test-integration-coverage))\b"
    )

    def test_no_bare_verification_in_skill_bodies(self):
        violations = []
        for skill in HELPER_ADOPTERS:
            content = _read_skill(skill)
            body = content.split("<!-- INLINE-PROTOCOLS:START -->", 1)[0]
            in_code_block = False
            for i, line in enumerate(body.splitlines(), 1):
                stripped = line.strip()
                if stripped.startswith("```"):
                    in_code_block = not in_code_block
                    continue
                if not in_code_block:
                    continue
                if stripped.startswith("#"):
                    continue
                if self.BARE_VERIFY_RE.match(stripped):
                    violations.append(f"{skill}/SKILL.md:{i}: {stripped}")
        assert violations == [], (
            "Bare make commands found in skill bodies (must use _optimus_quiet_run):\n"
            + "\n".join(f"  - {v}" for v in violations)
        )

    def test_helper_inlined_into_consumer_skills(self):
        missing = []
        for skill in HELPER_ADOPTERS:
            content = _read_skill(skill)
            if "_optimus_quiet_run()" not in content:
                missing.append(skill)
        assert missing == [], (
            "Skills declared as Quiet Command Execution adopters but missing "
            "_optimus_quiet_run() helper body (run inline-protocols.py):\n"
            + "\n".join(f"  - {m}" for m in missing)
        )

    def test_referenced_by_field_lists_all_adopters(self):
        section = _extract_protocol_section("Protocol: Quiet Command Execution")
        ref_match = re.search(r"\*\*Referenced by:\*\*\s*([^\n]+)", section)
        assert ref_match, "Referenced by field missing"
        ref_text = ref_match.group(1)
        for adopter in HELPER_ADOPTERS:
            assert adopter in ref_text, (
                f"Protocol Referenced by field missing adopter '{adopter}': {ref_text}"
            )

    def test_no_silent_adopter_drift(self):
        """Catch silent drift: if a NEW skill body uses _optimus_quiet_run on
        make commands, it must be listed in the Quiet Command Execution
        Referenced-by line.

        Previously, HELPER_ADOPTERS was a hardcoded list — adding a 6th
        adopter to a SKILL.md without updating the list would have left the
        new adopter unenforced. Now HELPER_ADOPTERS is derived from the
        Referenced-by line itself, and this test catches drift in the OTHER
        direction: any skill body invoking `_optimus_quiet_run "make-...`
        must appear in the derived list.
        """
        wrap_pattern = re.compile(r'_optimus_quiet_run\s+["\']?make-')
        actual_adopters = []
        for path in REPO_ROOT.glob("*/skills/*/SKILL.md"):
            content = path.read_text()
            body = content.split("<!-- INLINE-PROTOCOLS:START -->", 1)[0]
            if wrap_pattern.search(body):
                # Extract plugin name from path: <plugin>/skills/optimus-<plugin>/SKILL.md
                plugin = path.parts[-4]
                actual_adopters.append(plugin)
        # Initialize Directory's "Referenced by" mentions stage agents
        # collectively as "all stage agents (1-4) for session files" rather
        # than enumerating them. The Quiet Command Execution Referenced-by
        # line, by contrast, lists every direct caller. Compare to that one.
        derived = set(HELPER_ADOPTERS)
        # Some entries in Referenced by are not skill plugins (e.g., trailing
        # prose). Filter the derived set to entries that match an actual plugin
        # directory (a sibling of `skills/`).
        plugin_dirs = {p.parent.name for p in REPO_ROOT.glob("*/skills")}
        derived_plugins = {a for a in derived if a in plugin_dirs}
        missing = set(actual_adopters) - derived_plugins
        assert not missing, (
            f"Skills using _optimus_quiet_run on make commands but missing from "
            f"Quiet Command Execution Referenced-by: {sorted(missing)}"
        )


# ---------------------------------------------------------------------------
# 4. Coverage Measurement protocol updates.
# ---------------------------------------------------------------------------


class TestCoverageMeasurementProtocol:
    def test_thresholds_present(self):
        c = AGENTS_MD.read_text()
        assert "Unit tests | 85%" in c, "Unit threshold 85% missing"
        assert "Integration tests | 70%" in c, "Integration threshold 70% missing"

    def test_examples_use_quiet_run(self):
        section = _extract_protocol_section("Protocol: Coverage Measurement")
        # Every coverage example must wrap the command in _optimus_quiet_run.
        for label in ("make-test-coverage",):
            assert f'_optimus_quiet_run "{label}"' in section, (
                f"Coverage example missing _optimus_quiet_run wrapper for {label}"
            )

    @pytest.mark.skipif(not _has_bash(), reason="bash required for syntax check")
    def test_examples_are_valid_bash(self):
        section = _extract_protocol_section("Protocol: Coverage Measurement")
        for i, m in enumerate(re.finditer(r"```bash\n(.*?)\n```", section, re.DOTALL)):
            snippet = m.group(1)
            result = subprocess.run(
                ["bash", "-n"], input=snippet, text=True, capture_output=True
            )
            assert result.returncode == 0, (
                f"Coverage Measurement bash block #{i} has syntax errors:\n"
                f"{snippet}\n---\n{result.stderr}"
            )


# ---------------------------------------------------------------------------
# 5. Gitignore propagation.
# ---------------------------------------------------------------------------


class TestLogsDirGitignored:
    def test_logs_dir_in_initialize_protocol_block(self):
        section = _extract_protocol_section("Protocol: Initialize .optimus Directory")
        assert ".optimus/logs/" in section, (
            "Protocol: Initialize .optimus Directory must include .optimus/logs/ in gitignore block"
        )
        assert "mkdir -p .optimus/sessions .optimus/reports .optimus/logs" in section, (
            "Initialize protocol must mkdir .optimus/logs alongside sessions/reports"
        )

    def test_session_state_protocol_mkdir_includes_logs(self):
        """Session State inline mkdir must stay in sync with Initialize Directory.

        Drift was previously possible because Session State had its own inline
        `mkdir -p .optimus/sessions .optimus/reports` that lagged behind the full
        Initialize protocol. Now both must include `.optimus/logs`.
        """
        section = _extract_protocol_section("Protocol: Session State")
        assert "mkdir -p .optimus/sessions .optimus/reports .optimus/logs" in section, (
            "Protocol: Session State mkdir must match Initialize .optimus Directory "
            "(include .optimus/logs to prevent doc drift)"
        )

    def test_prune_logic_present_in_both_protocols(self):
        """The auto-prune logic must live in BOTH Initialize Directory AND
        Session State so that:
          - admin/standalone skills (which call Initialize Directory but not
            Session State) get prune coverage, AND
          - stage agents (which call Session State but not Initialize Directory)
            get prune coverage.

        Both prune sites are idempotent — running both is a harmless no-op on
        clean directories. Removing prune from either site silently breaks
        coverage for one class of skill.
        """
        for proto_title in ("Protocol: Initialize .optimus Directory", "Protocol: Session State"):
            section = _extract_protocol_section(proto_title)
            assert "find .optimus/logs -type f -name '*.log' -mtime +30 -delete" in section, (
                f"{proto_title} missing age-based prune (find -mtime +30 -delete)"
            )
            assert "tail -n +501" in section, (
                f"{proto_title} missing count-cap prune (tail -n +501)"
            )

    def test_quiet_command_execution_contract_references_both_prune_sites(self):
        """The Quiet Command Execution contract clause #4 (Log retention) must
        reference BOTH prune sites — not just one — to avoid the documentation
        drift that round-3 caught (clause referenced only Initialize Directory
        while implementation was in Session State only)."""
        section = _extract_protocol_section("Protocol: Quiet Command Execution")
        # The contract should mention both protocols by name in the retention clause.
        assert "Protocol: Initialize .optimus Directory" in section, (
            "Quiet Command Execution contract must reference Initialize Directory as a prune site"
        )
        assert "Protocol: Session State" in section, (
            "Quiet Command Execution contract must reference Session State as a prune site"
        )
