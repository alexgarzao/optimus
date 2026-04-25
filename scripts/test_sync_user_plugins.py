#!/usr/bin/env python3
"""Integration tests for sync-user-plugins.sh using mock commands."""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parent.parent / "sync" / "scripts" / "sync-user-plugins.sh"
BASH = shutil.which("bash")
if BASH is None:
    pytest.skip("bash not found", allow_module_level=True)


def _create_mock_bin(tmp_path: Path, name: str, script: str) -> None:
    """Create a mock executable in tmp_path/bin/."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    mock = bin_dir / name
    mock.write_text(f"#!/usr/bin/env bash\n{script}\n")
    mock.chmod(0o755)


def _create_marketplace(tmp_path: Path, plugins: list[str], name: str = "optimus") -> None:
    """Create a mock marketplace JSON file at the expected path."""
    mp_dir = tmp_path / "home" / ".factory" / "marketplaces" / name / ".factory-plugin"
    mp_dir.mkdir(parents=True)
    mp_file = mp_dir / "marketplace.json"
    entries = ", ".join(f'{{"name": "{p}"}}' for p in plugins)
    mp_file.write_text(f'{{"plugins": [{entries}]}}')


def _create_repo_cache(tmp_path: Path, plugins: list[str],
                       cache_dir: str | None = None) -> Path:
    """Create a mock optimus repo cache with SKILL.md files."""
    repo_dir = Path(cache_dir) if cache_dir else tmp_path / "home" / ".optimus" / "repo"
    # Create .git dir to mark it as a repo
    (repo_dir / ".git").mkdir(parents=True, exist_ok=True)
    # Create marketplace.json
    mp_dir = repo_dir / ".factory-plugin"
    mp_dir.mkdir(parents=True, exist_ok=True)
    entries = ", ".join(f'{{"name": "{p}"}}' for p in plugins)
    (mp_dir / "marketplace.json").write_text(f'{{"plugins": [{entries}]}}')
    # Create SKILL.md for each plugin
    for plugin in plugins:
        skill_dir = repo_dir / plugin / "skills" / f"optimus-{plugin}"
        skill_dir.mkdir(parents=True, exist_ok=True)
        (skill_dir / "SKILL.md").write_text(
            f"---\nname: optimus-{plugin}\n---\n# {plugin}\nContent for {plugin}.\n"
        )
    return repo_dir


def _create_claude_skill(tmp_path: Path, name: str,
                         content: str = "# placeholder") -> Path:
    """Create a skill directory in the mock Claude Code skills dir."""
    skills_dir = tmp_path / "home" / ".claude" / "skills" / "default"
    skill_dir = skills_dir / f"optimus-{name}"
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(content)
    return skill_dir


def _ensure_claude_dir(tmp_path: Path) -> Path:
    """Ensure ~/.claude/ directory exists in mock home."""
    claude_dir = tmp_path / "home" / ".claude"
    claude_dir.mkdir(parents=True, exist_ok=True)
    return claude_dir


def _path_without_droid() -> str:
    """Return system PATH with any directory containing a droid binary removed."""
    path_dirs = os.environ.get("PATH", "/usr/bin:/bin").split(":")
    filtered = [d for d in path_dirs if d and not (Path(d) / "droid").exists()]
    return ":".join(filtered) if filtered else "/usr/bin:/bin"


def _run_sync(tmp_path: Path, env_extra: dict[str, str] | None = None,
              restrict_path: bool = False,
              exclude_droid: bool = False,
              isolated: bool = False) -> subprocess.CompletedProcess:
    """Run the sync script with mocked PATH and HOME.

    Args:
        restrict_path: Only use tmp_path/bin as PATH (excludes ALL system binaries).
        exclude_droid: Remove droid from PATH but keep other system tools.
        isolated: Copy script to tmp_path so BASH_SOURCE doesn't resolve to the repo.
    """
    env = os.environ.copy()
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    if restrict_path:
        env["PATH"] = str(bin_dir)
    elif exclude_droid:
        env["PATH"] = f"{bin_dir}:{_path_without_droid()}"
    else:
        env["PATH"] = f"{bin_dir}:{env.get('PATH', '/usr/bin')}"
    env["HOME"] = str(tmp_path / "home")
    if env_extra:
        env.update(env_extra)

    script = SCRIPT
    if isolated:
        isolated_script = tmp_path / "isolated" / "sync-user-plugins.sh"
        isolated_script.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(SCRIPT, isolated_script)
        script = isolated_script

    return subprocess.run(
        [BASH, str(script)],
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
    )


def _droid_script(log: Path, list_output: str = "",
                  update_exit: int = 0, install_exit: int = 0,
                  uninstall_exit: int = 0) -> str:
    """Generate a droid mock script with configurable behavior."""
    return f"""
CMD="$1 $2"
case "$CMD" in
  "plugin marketplace") exit 0 ;;
  "plugin list") {f'echo "{list_output}"' if list_output else 'echo ""'} ;;
  "plugin update") echo "update $3" >> "{log}"; exit {update_exit} ;;
  "plugin uninstall") echo "uninstall $3" >> "{log}"; exit {uninstall_exit} ;;
  "plugin install") echo "install $3" >> "{log}"; exit {install_exit} ;;
  *) echo "unknown: $@" >> "{log}" ;;
esac
"""


# ═══════════════════════════════════════════════════════════════════════════════
# Existing Droid-only tests (adapted for dual-platform)
# ═══════════════════════════════════════════════════════════════════════════════

class TestDependencyChecks:
    def test_fails_without_any_platform(self, tmp_path: Path):
        """Neither droid nor ~/.claude/ → error."""
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir(exist_ok=True)
        jq_path = shutil.which("jq")
        if jq_path:
            os.symlink(jq_path, bin_dir / "jq")
        else:
            (bin_dir / "jq").write_text("#!/bin/bash\necho jq\n")
            (bin_dir / "jq").chmod(0o755)
        # No droid, no .claude dir
        result = _run_sync(tmp_path, restrict_path=True)
        assert result.returncode == 1
        assert "No supported platform found" in result.stderr

    def test_fails_without_jq(self, tmp_path: Path):
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir(exist_ok=True)
        droid_path = shutil.which("droid")
        if droid_path:
            os.symlink(droid_path, bin_dir / "droid")
        else:
            (bin_dir / "droid").write_text("#!/bin/bash\nexit 0\n")
            (bin_dir / "droid").chmod(0o755)
        result = _run_sync(tmp_path, restrict_path=True)
        assert result.returncode == 1
        assert "jq is required" in result.stderr


class TestFirstTimeInstall:
    def test_installs_all_plugins_on_first_run(self, tmp_path: Path):
        log = tmp_path / "droid.log"
        _create_mock_bin(tmp_path, "droid", _droid_script(log))
        _create_marketplace(tmp_path, ["alpha", "beta"])
        result = _run_sync(tmp_path)
        assert result.returncode == 0
        assert "Added: 2" in result.stdout
        assert "alpha ... OK" in result.stdout
        assert "beta ... OK" in result.stdout
        log_content = log.read_text()
        assert "alpha@optimus" in log_content
        assert "beta@optimus" in log_content


class TestUpdateWithExisting:
    def test_updates_existing_plugins(self, tmp_path: Path):
        log = tmp_path / "droid.log"
        _create_mock_bin(tmp_path, "droid", _droid_script(
            log, list_output="alpha@optimus  installed"))
        _create_marketplace(tmp_path, ["alpha"])
        result = _run_sync(tmp_path)
        assert result.returncode == 0
        assert "Updated: 1" in result.stdout


class TestOrphanRemoval:
    def test_removes_orphaned_plugins(self, tmp_path: Path):
        log = tmp_path / "droid.log"
        _create_mock_bin(tmp_path, "droid", _droid_script(
            log, list_output="alpha@optimus  installed\norphan@optimus  installed"))
        _create_marketplace(tmp_path, ["alpha"])
        result = _run_sync(tmp_path)
        assert result.returncode == 0
        assert "Removed: 1" in result.stdout
        log_content = log.read_text()
        assert "uninstall orphan@optimus" in log_content


class TestScopeConflict:
    def test_reinstalls_on_scope_conflict(self, tmp_path: Path):
        log = tmp_path / "droid.log"
        _create_mock_bin(tmp_path, "droid", _droid_script(
            log, list_output="alpha@optimus  installed", update_exit=1))
        _create_marketplace(tmp_path, ["alpha"])
        result = _run_sync(tmp_path)
        assert result.returncode == 0
        assert "reinstalled" in result.stdout.lower()
        log_content = log.read_text()
        assert "uninstall alpha@optimus" in log_content
        assert "install alpha@optimus" in log_content


class TestMarketplaceOverride:
    def test_custom_marketplace_name(self, tmp_path: Path):
        log = tmp_path / "droid.log"
        _create_mock_bin(tmp_path, "droid", _droid_script(log))
        _create_marketplace(tmp_path, ["test"], name="custom")
        result = _run_sync(tmp_path, {"OPTIMUS_MARKETPLACE_NAME": "custom"})
        assert result.returncode == 0
        assert "Added: 1" in result.stdout


class TestErrorPaths:
    def test_fails_on_marketplace_not_found(self, tmp_path: Path):
        log = tmp_path / "droid.log"
        _create_mock_bin(tmp_path, "droid", _droid_script(log))
        (tmp_path / "home" / ".factory").mkdir(parents=True)
        # Use isolated=True so BASH_SOURCE doesn't resolve to the optimus repo,
        # and set OPTIMUS_CACHE_DIR to a nonexistent path to prevent Source 2 fallback.
        result = _run_sync(tmp_path, isolated=True, env_extra={
            "OPTIMUS_CACHE_DIR": str(tmp_path / "nonexistent"),
        })
        assert result.returncode == 1
        assert "not found" in result.stderr.lower()

    def test_fails_on_empty_marketplace(self, tmp_path: Path):
        log = tmp_path / "droid.log"
        _create_mock_bin(tmp_path, "droid", _droid_script(log))
        mp_dir = tmp_path / "home" / ".factory" / "marketplaces" / "optimus" / ".factory-plugin"
        mp_dir.mkdir(parents=True)
        (mp_dir / "marketplace.json").write_text('{"plugins": []}')
        result = _run_sync(tmp_path)
        assert result.returncode == 1
        assert "No plugins found" in result.stderr

    def test_exits_nonzero_on_persistent_failure(self, tmp_path: Path):
        log = tmp_path / "droid.log"
        _create_mock_bin(tmp_path, "droid", _droid_script(log, install_exit=1))
        _create_marketplace(tmp_path, ["failing"])
        result = _run_sync(tmp_path)
        assert result.returncode == 1
        assert "Failed:" in result.stdout


class TestDroidTimeout:
    def test_rejects_zero_timeout(self, tmp_path: Path) -> None:
        log = tmp_path / "droid.log"
        _create_mock_bin(tmp_path, "droid", _droid_script(log))
        _create_marketplace(tmp_path, ["alpha"])
        result = _run_sync(tmp_path, {"OPTIMUS_DROID_TIMEOUT": "0"})
        assert result.returncode == 1
        assert "positive integer" in result.stderr

    def test_rejects_non_numeric_timeout(self, tmp_path: Path) -> None:
        log = tmp_path / "droid.log"
        _create_mock_bin(tmp_path, "droid", _droid_script(log))
        _create_marketplace(tmp_path, ["alpha"])
        result = _run_sync(tmp_path, {"OPTIMUS_DROID_TIMEOUT": "abc"})
        assert result.returncode == 1
        assert "positive integer" in result.stderr

    def test_rejects_negative_timeout(self, tmp_path: Path) -> None:
        log = tmp_path / "droid.log"
        _create_mock_bin(tmp_path, "droid", _droid_script(log))
        _create_marketplace(tmp_path, ["alpha"])
        result = _run_sync(tmp_path, {"OPTIMUS_DROID_TIMEOUT": "-5"})
        assert result.returncode == 1
        assert "positive integer" in result.stderr


class TestMixedResults:
    def test_mixed_success_and_failure_in_install(self, tmp_path: Path) -> None:
        log = tmp_path / "droid.log"
        script = f"""
CMD="$1 $2"
case "$CMD" in
  "plugin marketplace") exit 0 ;;
  "plugin list") echo "" ;;
  "plugin install")
    if echo "$3" | grep -q "fail"; then
      echo "install $3" >> "{log}"; exit 1
    else
      echo "install $3" >> "{log}"; exit 0
    fi ;;
  *) echo "unknown: $@" >> "{log}" ;;
esac
"""
        _create_mock_bin(tmp_path, "droid", script)
        _create_marketplace(tmp_path, ["good", "fail-plugin", "also-good"])
        result = _run_sync(tmp_path)
        assert result.returncode == 1
        assert "Added: 2" in result.stdout
        assert "Failed:" in result.stdout


class TestMarketplaceUpdateFailure:
    def test_continues_after_marketplace_update_failure(self, tmp_path: Path) -> None:
        log = tmp_path / "droid.log"
        script = f"""
CMD="$1 $2"
case "$CMD" in
  "plugin marketplace") exit 1 ;;
  "plugin list") echo "" ;;
  "plugin install") echo "install $3" >> "{log}"; exit 0 ;;
  *) echo "unknown: $@" >> "{log}" ;;
esac
"""
        _create_mock_bin(tmp_path, "droid", script)
        _create_marketplace(tmp_path, ["alpha"])
        result = _run_sync(tmp_path)
        assert result.returncode == 0
        assert "Could not update marketplace" in result.stderr
        assert "Added: 1" in result.stdout


class TestSignalHandling:
    def test_trap_on_sigterm(self, tmp_path: Path) -> None:
        log = tmp_path / "droid.log"
        script = f"""
CMD="$1 $2"
case "$CMD" in
  "plugin marketplace") exit 0 ;;
  "plugin list") echo "" ;;
  "plugin install") sleep 30; echo "install $3" >> "{log}"; exit 0 ;;
  *) echo "unknown: $@" >> "{log}" ;;
esac
"""
        _create_mock_bin(tmp_path, "droid", script)
        _create_marketplace(tmp_path, ["slow-plugin"])
        env = os.environ.copy()
        bin_dir = tmp_path / "bin"
        env["PATH"] = f"{bin_dir}:{env.get('PATH', '/usr/bin')}"
        env["HOME"] = str(tmp_path / "home")
        import signal
        import time
        proc = subprocess.Popen(
            [BASH, str(SCRIPT)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
            start_new_session=True,
        )
        time.sleep(2)
        os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
        stdout, stderr = proc.communicate(timeout=10)
        assert proc.returncode == 130


class TestTimeoutWrapper:
    def test_uses_timeout_when_available(self, tmp_path: Path) -> None:
        log = tmp_path / "droid.log"
        timeout_log = tmp_path / "timeout.log"
        _create_mock_bin(tmp_path, "droid", _droid_script(log))
        _create_marketplace(tmp_path, ["alpha"])
        timeout_script = f'#!/usr/bin/env bash\necho "timeout called with: $@" >> "{timeout_log}"\nshift; exec "$@"\n'
        _create_mock_bin(tmp_path, "timeout", timeout_script)
        result = _run_sync(tmp_path)
        assert result.returncode == 0
        assert timeout_log.exists()
        assert "timeout called with" in timeout_log.read_text()


class TestSerialRetry:
    def test_retries_transient_update_before_reinstall(self, tmp_path: Path) -> None:
        log = tmp_path / "droid.log"
        state_dir = tmp_path / "state"
        state_dir.mkdir()
        script = f"""
CMD="$1 $2"
case "$CMD" in
  "plugin marketplace") exit 0 ;;
  "plugin list") echo "alpha@optimus  installed" ;;
  "plugin update")
    count_file="{state_dir}/update.count"
    count=$(cat "$count_file" 2>/dev/null || echo 0)
    count=$((count + 1))
    echo "$count" > "$count_file"
    echo "update $3 #$count" >> "{log}"
    if [ "$count" -eq 1 ]; then exit 1; fi
    exit 0 ;;
  "plugin uninstall") echo "uninstall $3" >> "{log}"; exit 0 ;;
  "plugin install") echo "install $3" >> "{log}"; exit 0 ;;
  *) echo "unknown: $@" >> "{log}" ;;
esac
"""
        _create_mock_bin(tmp_path, "droid", script)
        _create_marketplace(tmp_path, ["alpha"])
        result = _run_sync(tmp_path)
        assert result.returncode == 0
        assert "Retrying failed plugin operations serially" in result.stdout
        assert "Updated: 1" in result.stdout
        log_content = log.read_text()
        assert "update alpha@optimus #1" in log_content
        assert "update alpha@optimus #2" in log_content
        assert "uninstall alpha@optimus" not in log_content
        assert "install alpha@optimus" not in log_content

    def test_retries_transient_install_serially(self, tmp_path: Path) -> None:
        log = tmp_path / "droid.log"
        state_dir = tmp_path / "state"
        state_dir.mkdir()
        script = f"""
CMD="$1 $2"
case "$CMD" in
  "plugin marketplace") exit 0 ;;
  "plugin list") echo "" ;;
  "plugin install")
    count_file="{state_dir}/install.count"
    count=$(cat "$count_file" 2>/dev/null || echo 0)
    count=$((count + 1))
    echo "$count" > "$count_file"
    echo "install $3 #$count" >> "{log}"
    if [ "$count" -eq 1 ]; then exit 1; fi
    exit 0 ;;
  *) echo "unknown: $@" >> "{log}" ;;
esac
"""
        _create_mock_bin(tmp_path, "droid", script)
        _create_marketplace(tmp_path, ["alpha"])
        result = _run_sync(tmp_path)
        assert result.returncode == 0
        assert "Retrying failed plugin operations serially" in result.stdout
        assert "Added: 1" in result.stdout
        log_content = log.read_text()
        assert "install alpha@optimus #1" in log_content
        assert "install alpha@optimus #2" in log_content


class TestMalformedMarketplace:
    def test_fails_on_malformed_json(self, tmp_path: Path) -> None:
        log = tmp_path / "droid.log"
        _create_mock_bin(tmp_path, "droid", _droid_script(log))
        mp_dir = tmp_path / "home" / ".factory" / "marketplaces" / "optimus" / ".factory-plugin"
        mp_dir.mkdir(parents=True)
        (mp_dir / "marketplace.json").write_text("{invalid json")
        result = _run_sync(tmp_path)
        assert result.returncode != 0


# ═══════════════════════════════════════════════════════════════════════════════
# Claude Code detection tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestClaudeCodeDetection:
    def test_detects_claude_code_when_dir_exists(self, tmp_path: Path) -> None:
        """When ~/.claude/ exists and no droid, runs Claude Code sync."""
        _ensure_claude_dir(tmp_path)
        repo_dir = _create_repo_cache(tmp_path, ["alpha"])
        skills_dir = tmp_path / "home" / ".claude" / "skills" / "default"
        result = _run_sync(tmp_path, env_extra={
            "OPTIMUS_CACHE_DIR": str(repo_dir),
            "CLAUDE_SKILLS_DIR": str(skills_dir),
        }, exclude_droid=True)
        assert result.returncode == 0
        assert "── Claude Code ──" in result.stdout
        assert "── Droid (Factory) ──" not in result.stdout

    def test_skips_claude_code_when_no_dir(self, tmp_path: Path) -> None:
        """When ~/.claude/ doesn't exist but droid is available, only Droid runs."""
        log = tmp_path / "droid.log"
        _create_mock_bin(tmp_path, "droid", _droid_script(log))
        _create_marketplace(tmp_path, ["alpha"])
        # Don't create .claude dir
        result = _run_sync(tmp_path)
        assert result.returncode == 0
        assert "Droid" in result.stdout
        # Claude Code section should not appear
        assert "── Claude Code ──" not in result.stdout


# ═══════════════════════════════════════════════════════════════════════════════
# Claude Code sync tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestClaudeCodeSync:
    def test_installs_new_skills(self, tmp_path: Path) -> None:
        """First-time install copies SKILL.md files to skills dir."""
        _ensure_claude_dir(tmp_path)
        repo_dir = _create_repo_cache(tmp_path, ["alpha", "beta"])
        skills_dir = tmp_path / "home" / ".claude" / "skills" / "default"
        result = _run_sync(tmp_path, env_extra={
            "OPTIMUS_CACHE_DIR": str(repo_dir),
            "CLAUDE_SKILLS_DIR": str(skills_dir),
        }, exclude_droid=True)
        assert result.returncode == 0
        assert "Added: 2" in result.stdout
        assert (skills_dir / "optimus-alpha" / "SKILL.md").exists()
        assert (skills_dir / "optimus-beta" / "SKILL.md").exists()

    def test_updates_changed_skills(self, tmp_path: Path) -> None:
        """When source SKILL.md differs, it gets updated."""
        _ensure_claude_dir(tmp_path)
        repo_dir = _create_repo_cache(tmp_path, ["alpha"])
        skills_dir = tmp_path / "home" / ".claude" / "skills" / "default"
        # Create existing skill with different content
        skill_dir = skills_dir / "optimus-alpha"
        skill_dir.mkdir(parents=True, exist_ok=True)
        (skill_dir / "SKILL.md").write_text("old content")
        result = _run_sync(tmp_path, env_extra={
            "OPTIMUS_CACHE_DIR": str(repo_dir),
            "CLAUDE_SKILLS_DIR": str(skills_dir),
        }, exclude_droid=True)
        assert result.returncode == 0
        assert "Updated: 1" in result.stdout
        assert "alpha" in (skill_dir / "SKILL.md").read_text()

    def test_skips_unchanged_skills(self, tmp_path: Path) -> None:
        """When source SKILL.md is identical, skip with 'unchanged'."""
        _ensure_claude_dir(tmp_path)
        repo_dir = _create_repo_cache(tmp_path, ["alpha"])
        skills_dir = tmp_path / "home" / ".claude" / "skills" / "default"
        # Copy the exact same content
        src_content = (repo_dir / "alpha" / "skills" / "optimus-alpha" / "SKILL.md").read_text()
        skill_dir = skills_dir / "optimus-alpha"
        skill_dir.mkdir(parents=True, exist_ok=True)
        (skill_dir / "SKILL.md").write_text(src_content)
        result = _run_sync(tmp_path, env_extra={
            "OPTIMUS_CACHE_DIR": str(repo_dir),
            "CLAUDE_SKILLS_DIR": str(skills_dir),
        }, exclude_droid=True)
        assert result.returncode == 0
        assert "unchanged" in result.stdout.lower()
        assert "Unchanged: 1" in result.stdout

    def test_removes_orphaned_skills(self, tmp_path: Path) -> None:
        """Skills in dir but not in marketplace get removed."""
        _ensure_claude_dir(tmp_path)
        repo_dir = _create_repo_cache(tmp_path, ["alpha"])
        skills_dir = tmp_path / "home" / ".claude" / "skills" / "default"
        # Create orphaned skill
        orphan_dir = skills_dir / "optimus-orphan"
        orphan_dir.mkdir(parents=True, exist_ok=True)
        (orphan_dir / "SKILL.md").write_text("orphan")
        result = _run_sync(tmp_path, env_extra={
            "OPTIMUS_CACHE_DIR": str(repo_dir),
            "CLAUDE_SKILLS_DIR": str(skills_dir),
        }, exclude_droid=True)
        assert result.returncode == 0
        assert "Removed: 1" in result.stdout
        assert not orphan_dir.exists()

    def test_never_removes_non_optimus_skills(self, tmp_path: Path) -> None:
        """Skills without optimus- prefix must NEVER be touched."""
        _ensure_claude_dir(tmp_path)
        repo_dir = _create_repo_cache(tmp_path, ["alpha"])
        skills_dir = tmp_path / "home" / ".claude" / "skills" / "default"
        # Create non-optimus skills that must survive
        for name in ["ring:code-reviewer", "my-custom-skill", "other-tool"]:
            safe_dir = skills_dir / name
            safe_dir.mkdir(parents=True, exist_ok=True)
            (safe_dir / "SKILL.md").write_text(f"safe: {name}")
        result = _run_sync(tmp_path, env_extra={
            "OPTIMUS_CACHE_DIR": str(repo_dir),
            "CLAUDE_SKILLS_DIR": str(skills_dir),
        }, exclude_droid=True)
        assert result.returncode == 0
        # All non-optimus skills must still exist
        for name in ["ring:code-reviewer", "my-custom-skill", "other-tool"]:
            assert (skills_dir / name / "SKILL.md").exists(), f"{name} was incorrectly removed!"

    def test_source_not_found_reports_fail(self, tmp_path: Path) -> None:
        """When SKILL.md doesn't exist in repo cache, report FAIL."""
        _ensure_claude_dir(tmp_path)
        repo_dir = _create_repo_cache(tmp_path, ["alpha"])
        skills_dir = tmp_path / "home" / ".claude" / "skills" / "default"
        # Remove the SKILL.md from cache to simulate missing source
        (repo_dir / "alpha" / "skills" / "optimus-alpha" / "SKILL.md").unlink()
        result = _run_sync(tmp_path, env_extra={
            "OPTIMUS_CACHE_DIR": str(repo_dir),
            "CLAUDE_SKILLS_DIR": str(skills_dir),
        }, exclude_droid=True)
        assert result.returncode == 1
        assert "source not found" in result.stdout.lower()


# ═══════════════════════════════════════════════════════════════════════════════
# Claude Code repo cache tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestClaudeCodeRepoCache:
    def test_uses_existing_cache(self, tmp_path: Path) -> None:
        """When cache dir exists with .git, uses it without cloning."""
        _ensure_claude_dir(tmp_path)
        repo_dir = _create_repo_cache(tmp_path, ["alpha"])
        # Mock git to avoid actual network calls
        _create_mock_bin(tmp_path, "git", 'exit 0')
        skills_dir = tmp_path / "home" / ".claude" / "skills" / "default"
        result = _run_sync(tmp_path, env_extra={
            "OPTIMUS_CACHE_DIR": str(repo_dir),
            "CLAUDE_SKILLS_DIR": str(skills_dir),
        }, exclude_droid=True)
        assert result.returncode == 0
        assert "Updating repo cache" in result.stdout

    def test_clones_when_no_cache(self, tmp_path: Path) -> None:
        """When no cache exists, attempts to clone."""
        _ensure_claude_dir(tmp_path)
        cache_dir = tmp_path / "home" / ".optimus" / "repo"
        skills_dir = tmp_path / "home" / ".claude" / "skills" / "default"
        # Mock git clone to create the repo cache
        git_script = f"""
if [ "$1" = "clone" ]; then
  mkdir -p "{cache_dir}/.git"
  mkdir -p "{cache_dir}/.factory-plugin"
  echo '{{"plugins": [{{"name": "alpha"}}]}}' > "{cache_dir}/.factory-plugin/marketplace.json"
  mkdir -p "{cache_dir}/alpha/skills/optimus-alpha"
  echo "---\\nname: optimus-alpha\\n---\\n# alpha" > "{cache_dir}/alpha/skills/optimus-alpha/SKILL.md"
  exit 0
fi
exit 0
"""
        _create_mock_bin(tmp_path, "git", git_script)
        result = _run_sync(tmp_path, env_extra={
            "OPTIMUS_CACHE_DIR": str(cache_dir),
            "CLAUDE_SKILLS_DIR": str(skills_dir),
        }, exclude_droid=True)
        assert result.returncode == 0
        assert "Cloning repo cache" in result.stdout

    def test_warns_on_clone_failure(self, tmp_path: Path) -> None:
        """When clone fails, warn and skip Claude Code sync gracefully."""
        _ensure_claude_dir(tmp_path)
        cache_dir = tmp_path / "home" / ".optimus" / "repo"
        skills_dir = tmp_path / "home" / ".claude" / "skills" / "default"
        # Mock git that always fails
        _create_mock_bin(tmp_path, "git", 'exit 1')
        result = _run_sync(tmp_path, env_extra={
            "OPTIMUS_CACHE_DIR": str(cache_dir),
            "CLAUDE_SKILLS_DIR": str(skills_dir),
        }, exclude_droid=True)
        # Should not crash — graceful skip
        assert "Could not clone repo" in result.stderr or "skipped" in result.stdout.lower()


# ═══════════════════════════════════════════════════════════════════════════════
# Dual platform sync tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestDualPlatformSync:
    def test_syncs_both_platforms_simultaneously(self, tmp_path: Path) -> None:
        """When both droid and ~/.claude/ are available, sync both."""
        log = tmp_path / "droid.log"
        _create_mock_bin(tmp_path, "droid", _droid_script(log))
        _create_marketplace(tmp_path, ["alpha", "beta"])
        _ensure_claude_dir(tmp_path)
        repo_dir = _create_repo_cache(tmp_path, ["alpha", "beta"])
        skills_dir = tmp_path / "home" / ".claude" / "skills" / "default"
        result = _run_sync(tmp_path, {
            "OPTIMUS_CACHE_DIR": str(repo_dir),
            "CLAUDE_SKILLS_DIR": str(skills_dir),
        })
        assert result.returncode == 0
        # Both platform sections should appear
        assert "── Droid (Factory) ──" in result.stdout
        assert "── Claude Code ──" in result.stdout
        # Both should report success
        assert "Droid" in result.stdout
        assert "Claude Code" in result.stdout
        # Claude Code skills should be installed
        assert (skills_dir / "optimus-alpha" / "SKILL.md").exists()
        assert (skills_dir / "optimus-beta" / "SKILL.md").exists()

    def test_droid_only_when_no_claude_dir(self, tmp_path: Path) -> None:
        """Without ~/.claude/, only Droid sync runs."""
        log = tmp_path / "droid.log"
        _create_mock_bin(tmp_path, "droid", _droid_script(log))
        _create_marketplace(tmp_path, ["alpha"])
        result = _run_sync(tmp_path)
        assert result.returncode == 0
        assert "── Droid (Factory) ──" in result.stdout
        assert "── Claude Code ──" not in result.stdout

    def test_claude_only_when_no_droid(self, tmp_path: Path) -> None:
        """Without droid CLI, only Claude Code sync runs."""
        _ensure_claude_dir(tmp_path)
        repo_dir = _create_repo_cache(tmp_path, ["alpha"])
        skills_dir = tmp_path / "home" / ".claude" / "skills" / "default"
        result = _run_sync(tmp_path, env_extra={
            "OPTIMUS_CACHE_DIR": str(repo_dir),
            "CLAUDE_SKILLS_DIR": str(skills_dir),
        }, exclude_droid=True)
        assert result.returncode == 0
        assert "── Droid (Factory) ──" not in result.stdout
        assert "── Claude Code ──" in result.stdout

    def test_droid_failure_doesnt_block_claude(self, tmp_path: Path) -> None:
        """If Droid sync fails, Claude Code sync still runs."""
        log = tmp_path / "droid.log"
        _create_mock_bin(tmp_path, "droid", _droid_script(log, install_exit=1))
        _create_marketplace(tmp_path, ["alpha"])
        _ensure_claude_dir(tmp_path)
        repo_dir = _create_repo_cache(tmp_path, ["alpha"])
        skills_dir = tmp_path / "home" / ".claude" / "skills" / "default"
        result = _run_sync(tmp_path, env_extra={
            "OPTIMUS_CACHE_DIR": str(repo_dir),
            "CLAUDE_SKILLS_DIR": str(skills_dir),
        })
        # Overall should fail (droid failed) but Claude Code should succeed
        assert result.returncode == 1
        assert "── Droid (Factory) ──" in result.stdout
        assert "── Claude Code ──" in result.stdout
        # Claude Code skill should still be installed
        assert (skills_dir / "optimus-alpha" / "SKILL.md").exists()
