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


DEFAULT_OPTIMUS_REPO_URL = "https://github.com/alexgarzao/optimus"


def _create_repo_cache(tmp_path: Path, plugins: list[str],
                       cache_dir: str | None = None,
                       origin_url: str = DEFAULT_OPTIMUS_REPO_URL,
                       install_git_mock: bool = True) -> Path:
    """Create a mock optimus repo cache with SKILL.md files.

    Writes a minimal but functional .git/ dir (config + HEAD + objects/refs)
    so real `git -C config --get remote.origin.url` returns the configured URL.
    F26 (post bash refactor) verifies origin URL before using cache.

    install_git_mock=True (default) installs a default mock `git` in tmp_path/bin
    that handles config/fetch/reset as no-ops returning the right URL — preventing
    real network calls. Set install_git_mock=False if a test wants to provide its
    own git mock.
    """
    repo_dir = Path(cache_dir) if cache_dir else tmp_path / "home" / ".optimus" / "repo"
    git_dir = repo_dir / ".git"
    git_dir.mkdir(parents=True, exist_ok=True)
    # Minimum files for git to recognize this as a valid repo.
    (git_dir / "config").write_text(
        '[core]\n\trepositoryformatversion = 0\n\tfilemode = true\n\tbare = false\n'
        f'[remote "origin"]\n\turl = {origin_url}\n\tfetch = +refs/heads/*:refs/remotes/origin/*\n'
    )
    (git_dir / "HEAD").write_text("ref: refs/heads/main\n")
    (git_dir / "objects").mkdir(exist_ok=True)
    (git_dir / "refs" / "heads").mkdir(parents=True, exist_ok=True)
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
    # Install default git mock so the script's `git fetch` doesn't go to network,
    # and `git config --get remote.origin.url` returns the configured origin.
    # Skipped if the test already wrote one or explicitly opts out.
    if install_git_mock:
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir(exist_ok=True)
        git_mock = bin_dir / "git"
        if not git_mock.exists():
            # The script invokes git with `-C <path>` prefix for repo ops
            # (e.g. `git -C $repo_dir config --get remote.origin.url`).
            # Strip leading "-C <path>" so we can dispatch on the real subcommand.
            git_mock.write_text(
                "#!/usr/bin/env bash\n"
                'if [ "$1" = "-C" ]; then shift 2; fi\n'
                'case "$1" in\n'
                f'  config) echo "{origin_url}"; exit 0 ;;\n'
                "  fetch|reset|clone) exit 0 ;;\n"
                "esac\n"
                "exit 0\n"
            )
            git_mock.chmod(0o755)
    return repo_dir


def _ensure_claude_dir(tmp_path: Path) -> Path:
    """Ensure ~/.claude/skills/ directory exists in mock home.

    Per F49, Claude Code detection requires ~/.claude/skills/ (not just ~/.claude/).
    """
    claude_skills = tmp_path / "home" / ".claude" / "skills"
    claude_skills.mkdir(parents=True, exist_ok=True)
    return claude_skills.parent


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
        assert "Could not update Droid marketplace" in result.stderr
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
        """When ~/.claude/skills/ doesn't exist but droid is available, only Droid runs."""
        log = tmp_path / "droid.log"
        _create_mock_bin(tmp_path, "droid", _droid_script(log))
        _create_marketplace(tmp_path, ["alpha"])
        # Don't create .claude/skills/ dir (F49 detection requires it).
        result = _run_sync(tmp_path)
        assert result.returncode == 0
        # F32: assert exact section header AND that Droid actually installed something.
        assert "── Droid (Factory) ──" in result.stdout
        # Claude Code section should not appear
        assert "── Claude Code ──" not in result.stdout
        log_content = log.read_text()
        assert "install alpha@optimus" in log_content


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
        # F11: existing installs need the .optimus-managed marker so update path runs.
        (skill_dir / ".optimus-managed").touch()
        result = _run_sync(tmp_path, env_extra={
            "OPTIMUS_CACHE_DIR": str(repo_dir),
            "CLAUDE_SKILLS_DIR": str(skills_dir),
        }, exclude_droid=True)
        assert result.returncode == 0
        assert "Updated: 1" in result.stdout
        assert "alpha" in (skill_dir / "SKILL.md").read_text()

    def test_skips_unchanged_skills(self, tmp_path: Path) -> None:
        """When source SKILL.md is identical, skip with 'unchanged' and don't touch the file."""
        _ensure_claude_dir(tmp_path)
        repo_dir = _create_repo_cache(tmp_path, ["alpha"])
        skills_dir = tmp_path / "home" / ".claude" / "skills" / "default"
        # Copy the exact same content
        src_content = (repo_dir / "alpha" / "skills" / "optimus-alpha" / "SKILL.md").read_text()
        skill_dir = skills_dir / "optimus-alpha"
        skill_dir.mkdir(parents=True, exist_ok=True)
        dest = skill_dir / "SKILL.md"
        dest.write_text(src_content)
        # F11: existing installs need the .optimus-managed marker.
        (skill_dir / ".optimus-managed").touch()
        # F14: capture mtime to verify the unchanged path doesn't rewrite the file.
        mtime_before = dest.stat().st_mtime_ns
        result = _run_sync(tmp_path, env_extra={
            "OPTIMUS_CACHE_DIR": str(repo_dir),
            "CLAUDE_SKILLS_DIR": str(skills_dir),
        }, exclude_droid=True)
        assert result.returncode == 0
        assert "unchanged" in result.stdout.lower()
        assert "Unchanged: 1" in result.stdout
        assert dest.stat().st_mtime_ns == mtime_before

    def test_removes_orphaned_skills(self, tmp_path: Path) -> None:
        """Skills in dir but not in marketplace get removed (when marker present)."""
        _ensure_claude_dir(tmp_path)
        repo_dir = _create_repo_cache(tmp_path, ["alpha"])
        skills_dir = tmp_path / "home" / ".claude" / "skills" / "default"
        # Create orphaned skill with .optimus-managed marker (F11)
        orphan_dir = skills_dir / "optimus-orphan"
        orphan_dir.mkdir(parents=True, exist_ok=True)
        (orphan_dir / "SKILL.md").write_text("orphan")
        (orphan_dir / ".optimus-managed").touch()
        result = _run_sync(tmp_path, env_extra={
            "OPTIMUS_CACHE_DIR": str(repo_dir),
            "CLAUDE_SKILLS_DIR": str(skills_dir),
        }, exclude_droid=True)
        assert result.returncode == 0
        assert "Removed: 1" in result.stdout
        assert not orphan_dir.exists()

    def test_skips_orphan_without_marker(self, tmp_path: Path) -> None:
        """F11: orphan dirs lacking .optimus-managed are skipped (user-created safety)."""
        _ensure_claude_dir(tmp_path)
        repo_dir = _create_repo_cache(tmp_path, ["alpha"])
        skills_dir = tmp_path / "home" / ".claude" / "skills" / "default"
        # Orphan WITHOUT marker — should be left alone.
        orphan_dir = skills_dir / "optimus-orphan"
        orphan_dir.mkdir(parents=True, exist_ok=True)
        (orphan_dir / "SKILL.md").write_text("user-created")
        result = _run_sync(tmp_path, env_extra={
            "OPTIMUS_CACHE_DIR": str(repo_dir),
            "CLAUDE_SKILLS_DIR": str(skills_dir),
        }, exclude_droid=True)
        assert result.returncode == 0
        assert "Removed: 0" in result.stdout
        assert "skipped" in result.stdout.lower()
        assert ".optimus-managed marker" in result.stdout
        assert orphan_dir.exists()
        assert (orphan_dir / "SKILL.md").read_text() == "user-created"

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
        """When cache dir exists with .git, uses it without cloning, and EXPECTED comes from it."""
        _ensure_claude_dir(tmp_path)
        # Cache holds a single plugin "alpha-from-cache" — the expected list must come from here.
        # Default git mock from _create_repo_cache handles config/fetch/reset as no-ops.
        repo_dir = _create_repo_cache(tmp_path, ["alpha-from-cache"])
        skills_dir = tmp_path / "home" / ".claude" / "skills" / "default"
        result = _run_sync(tmp_path, env_extra={
            "OPTIMUS_CACHE_DIR": str(repo_dir),
            "CLAUDE_SKILLS_DIR": str(skills_dir),
        }, exclude_droid=True)
        assert result.returncode == 0
        assert "Updating repo cache" in result.stdout
        # F33: post-condition — EXPECTED was sourced from the cache.
        assert (skills_dir / "optimus-alpha-from-cache" / "SKILL.md").exists()
        assert "alpha-from-cache" in result.stdout

    def test_clones_when_no_cache(self, tmp_path: Path) -> None:
        """When no cache exists, attempts to clone with exact expected arguments."""
        _ensure_claude_dir(tmp_path)
        cache_dir = tmp_path / "home" / ".optimus" / "repo"
        skills_dir = tmp_path / "home" / ".claude" / "skills" / "default"
        git_log = tmp_path / "git.log"
        # Mock git clone to create the repo cache.
        # F57: use a heredoc so the SKILL.md actually contains literal newlines.
        # F34: log every git invocation so we can assert exact clone args.
        git_script = f"""
echo "$@" >> "{git_log}"
if [ "$1" = "clone" ]; then
  # Args: clone --depth 1 <url> <dest>
  dest="${{!#}}"
  mkdir -p "$dest/.git"
  mkdir -p "$dest/.factory-plugin"
  echo '{{"plugins": [{{"name": "alpha"}}]}}' > "$dest/.factory-plugin/marketplace.json"
  mkdir -p "$dest/alpha/skills/optimus-alpha"
  cat > "$dest/alpha/skills/optimus-alpha/SKILL.md" <<'EOF'
---
name: optimus-alpha
---
# alpha
EOF
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
        # F34: verify exact clone arguments.
        log_content = git_log.read_text()
        expected_clone = f"clone --depth 1 {DEFAULT_OPTIMUS_REPO_URL} {cache_dir}"
        assert expected_clone in log_content, (
            f"Expected '{expected_clone}' in git log, got:\n{log_content}"
        )

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
        # F5: strict assertions — both the warning and the skip line must appear.
        assert "Could not clone repo" in result.stderr
        assert "(skipped)" in result.stdout
        assert result.returncode in (0, 1)


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
        """Without droid CLI, only Claude Code sync runs and installs skills."""
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
        # F35: confirm files were actually installed.
        assert (skills_dir / "optimus-alpha" / "SKILL.md").exists()

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

    def test_claude_failure_doesnt_block_droid(self, tmp_path: Path) -> None:
        """F3: If Claude Code sync fails, Droid sync still completes installs.

        Symmetric to test_droid_failure_doesnt_block_claude.
        Claude Code is set up to fail at SKILL.md copy (source missing in cache),
        so it reports FAIL — but Droid path must still run end-to-end.
        """
        log = tmp_path / "droid.log"
        _create_mock_bin(tmp_path, "droid", _droid_script(log))
        _create_marketplace(tmp_path, ["alpha"])
        _ensure_claude_dir(tmp_path)
        # Set up repo cache that has marketplace but is missing SKILL.md → Claude fails.
        repo_dir = _create_repo_cache(tmp_path, ["alpha"])
        (repo_dir / "alpha" / "skills" / "optimus-alpha" / "SKILL.md").unlink()
        skills_dir = tmp_path / "home" / ".claude" / "skills" / "default"
        result = _run_sync(tmp_path, env_extra={
            "OPTIMUS_CACHE_DIR": str(repo_dir),
            "CLAUDE_SKILLS_DIR": str(skills_dir),
        })
        # Aggregated failure expected (Claude failed)
        assert result.returncode == 1
        assert "── Droid (Factory) ──" in result.stdout
        assert "── Claude Code ──" in result.stdout
        # Droid must have completed its install.
        log_content = log.read_text()
        assert "install alpha@optimus" in log_content
        # And Claude must have reported the source-not-found failure.
        assert "source not found" in result.stdout.lower()


# ═══════════════════════════════════════════════════════════════════════════════
# README contract (F4)
# ═══════════════════════════════════════════════════════════════════════════════

class TestREADMEContract:
    def test_bootstrap_oneliner_paths_exist(self) -> None:
        """README bootstrap one-liner relies on these paths existing in the repo."""
        repo_root = Path(__file__).resolve().parent.parent
        skill_path = repo_root / "sync" / "skills" / "optimus-sync" / "SKILL.md"
        assert skill_path.exists(), f"Missing: {skill_path}"
        skill_md = skill_path.read_text()
        assert "name: optimus-sync" in skill_md  # frontmatter sanity
        # The bootstrap also relies on the sync script.
        assert (repo_root / "sync" / "scripts" / "sync-user-plugins.sh").exists()


# ═══════════════════════════════════════════════════════════════════════════════
# Plugin name validation (F6)
# ═══════════════════════════════════════════════════════════════════════════════

class TestPluginNameValidation:
    def test_rejects_plugin_name_with_path_traversal(self, tmp_path: Path) -> None:
        """Marketplace.json with a name containing '..' must error and not write any files."""
        log = tmp_path / "droid.log"
        _create_mock_bin(tmp_path, "droid", _droid_script(log))
        # Hand-craft a marketplace.json with a malicious name.
        mp_dir = tmp_path / "home" / ".factory" / "marketplaces" / "optimus" / ".factory-plugin"
        mp_dir.mkdir(parents=True)
        (mp_dir / "marketplace.json").write_text(
            '{"plugins": [{"name": "../../../etc"}]}'
        )
        # Ensure target path doesn't exist before sync.
        skills_dir = tmp_path / "home" / ".claude" / "skills" / "default"
        result = _run_sync(tmp_path)
        assert result.returncode == 1
        assert "Invalid plugin name" in result.stderr
        # No directory should have been created at the malicious location.
        assert not (skills_dir / "optimus-../../../etc").exists()
        assert not (tmp_path / "home" / ".claude" / "skills" / "etc").exists()

    def test_rejects_plugin_name_with_uppercase(self, tmp_path: Path) -> None:
        """Names like 'MyPlugin' should be rejected by the regex."""
        log = tmp_path / "droid.log"
        _create_mock_bin(tmp_path, "droid", _droid_script(log))
        mp_dir = tmp_path / "home" / ".factory" / "marketplaces" / "optimus" / ".factory-plugin"
        mp_dir.mkdir(parents=True)
        (mp_dir / "marketplace.json").write_text(
            '{"plugins": [{"name": "MyPlugin"}]}'
        )
        result = _run_sync(tmp_path)
        assert result.returncode == 1
        assert "Invalid plugin name" in result.stderr

    def test_rejects_plugin_name_with_leading_dash(self, tmp_path: Path) -> None:
        """Names starting with '-' should be rejected (must start with [a-z0-9])."""
        log = tmp_path / "droid.log"
        _create_mock_bin(tmp_path, "droid", _droid_script(log))
        mp_dir = tmp_path / "home" / ".factory" / "marketplaces" / "optimus" / ".factory-plugin"
        mp_dir.mkdir(parents=True)
        (mp_dir / "marketplace.json").write_text(
            '{"plugins": [{"name": "-evil"}]}'
        )
        result = _run_sync(tmp_path)
        assert result.returncode == 1
        assert "Invalid plugin name" in result.stderr

    def test_accepts_valid_plugin_names(self, tmp_path: Path) -> None:
        """Names matching ^[a-z0-9][a-z0-9_-]*$ are accepted."""
        log = tmp_path / "droid.log"
        _create_mock_bin(tmp_path, "droid", _droid_script(log))
        # All valid: lowercase start, contain digits, underscores, hyphens.
        valid_names = ["plan", "build-2", "optimus_helper", "abc", "x1"]
        _create_marketplace(tmp_path, valid_names)
        result = _run_sync(tmp_path)
        assert result.returncode == 0
        assert "Invalid plugin name" not in result.stderr
        for name in valid_names:
            assert f"+ {name} ... OK" in result.stdout


# ═══════════════════════════════════════════════════════════════════════════════
# Repo cache edge cases (F16)
# ═══════════════════════════════════════════════════════════════════════════════

class TestRepoCacheEdgeCases:
    def test_repo_cache_corrupt_no_git(self, tmp_path: Path) -> None:
        """F16: cache dir exists but lacks .git/ → script tries to clone, fails clearly.

        `git clone` will not clone into a non-empty existing directory. Verify the
        failure surfaces as a clear warning rather than a silent crash.
        """
        _ensure_claude_dir(tmp_path)
        cache_dir = tmp_path / "home" / ".optimus" / "repo"
        cache_dir.mkdir(parents=True)
        # Populate without a .git/ directory — simulates a corrupted/manual cache.
        (cache_dir / "stray.txt").write_text("not a git repo")
        skills_dir = tmp_path / "home" / ".claude" / "skills" / "default"
        # Mock git clone to fail (mimics real `git clone` into non-empty dir).
        _create_mock_bin(tmp_path, "git", 'if [ "$1" = "clone" ]; then exit 128; fi; exit 0')
        result = _run_sync(tmp_path, env_extra={
            "OPTIMUS_CACHE_DIR": str(cache_dir),
            "CLAUDE_SKILLS_DIR": str(skills_dir),
        }, exclude_droid=True)
        # Graceful: warns and skips Claude Code; exit code may be 0 (Claude skipped, no failures).
        assert "Could not clone repo" in result.stderr
        assert "Cloning repo cache" in result.stdout
        assert "(skipped)" in result.stdout


# ═══════════════════════════════════════════════════════════════════════════════
# Source 3 marketplace resolution (F17 / F28)
# ═══════════════════════════════════════════════════════════════════════════════

class TestSourceResolution:
    def test_resolve_expected_uses_source_3(self, tmp_path: Path) -> None:
        """F17/F28: when Source 1 and Source 2 are absent, fall back to repo root.

        Source 3 requires AGENTS.md AND sync/scripts/sync-user-plugins.sh at repo_root.
        We simulate this by copying the script into a fake repo with stub AGENTS.md
        and a marketplace.json at repo_root/.factory-plugin/marketplace.json.
        """
        log = tmp_path / "droid.log"
        _create_mock_bin(tmp_path, "droid", _droid_script(log))
        # Build a fake repo layout.
        fake_repo = tmp_path / "fake_repo"
        (fake_repo / "sync" / "scripts").mkdir(parents=True)
        (fake_repo / ".factory-plugin").mkdir(parents=True)
        shutil.copy2(SCRIPT, fake_repo / "sync" / "scripts" / "sync-user-plugins.sh")
        (fake_repo / "AGENTS.md").write_text("# AGENTS")
        (fake_repo / ".factory-plugin" / "marketplace.json").write_text(
            '{"plugins": [{"name": "fromsrc3"}]}'
        )
        # Source 1: empty .factory cache (dir exists but no marketplace.json).
        (tmp_path / "home" / ".factory").mkdir(parents=True)
        # Source 2: nonexistent OPTIMUS_CACHE_DIR.
        env = os.environ.copy()
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir(exist_ok=True)
        env["PATH"] = f"{bin_dir}:{env.get('PATH', '/usr/bin')}"
        env["HOME"] = str(tmp_path / "home")
        env["OPTIMUS_CACHE_DIR"] = str(tmp_path / "nonexistent")
        result = subprocess.run(
            [BASH, str(fake_repo / "sync" / "scripts" / "sync-user-plugins.sh")],
            capture_output=True,
            text=True,
            env=env,
            timeout=30,
        )
        assert result.returncode == 0, f"stderr: {result.stderr}\nstdout: {result.stdout}"
        assert "Added: 1" in result.stdout
        log_content = log.read_text()
        assert "install fromsrc3@optimus" in log_content


# ═══════════════════════════════════════════════════════════════════════════════
# Symlink safety on orphan removal (F18)
# ═══════════════════════════════════════════════════════════════════════════════

class TestSymlinkSafety:
    def test_symlinked_orphan_removal_safe(self, tmp_path: Path) -> None:
        """F18: a symlink in the skills dir must NEVER cause the script to delete the target.

        The current bash `find -type d` does NOT follow symlinks, so symlinked entries
        are not detected as "installed" and are not candidates for orphan removal.
        That's the safety guarantee: the symlink target stays untouched regardless.
        F7 (rm -f before cp) is the install-side defense; this asserts the orphan-side
        property: even if a symlink with .optimus-managed is present, the target survives.
        """
        _ensure_claude_dir(tmp_path)
        repo_dir = _create_repo_cache(tmp_path, ["alpha"])
        skills_dir = tmp_path / "home" / ".claude" / "skills" / "default"
        skills_dir.mkdir(parents=True, exist_ok=True)
        # Create a sensitive directory elsewhere with content + the .optimus-managed
        # marker (so even if the script were to follow the symlink, it would still
        # see the marker and could choose to delete — we want to verify it doesn't).
        sensitive = tmp_path / "sensitive_data"
        sensitive.mkdir()
        (sensitive / "secret.txt").write_text("must-survive")
        (sensitive / ".optimus-managed").touch()
        orphan_link = skills_dir / "optimus-foo"
        orphan_link.symlink_to(sensitive)
        result = _run_sync(tmp_path, env_extra={
            "OPTIMUS_CACHE_DIR": str(repo_dir),
            "CLAUDE_SKILLS_DIR": str(skills_dir),
        }, exclude_droid=True)
        assert result.returncode == 0
        # The target directory and its contents must be intact (primary safety property).
        assert sensitive.exists()
        assert (sensitive / "secret.txt").exists()
        assert (sensitive / "secret.txt").read_text() == "must-survive"


# ═══════════════════════════════════════════════════════════════════════════════
# Update-path failure when source not found (F36)
# ═══════════════════════════════════════════════════════════════════════════════

class TestUpdatePathFailures:
    def test_source_not_found_reports_fail_in_update(self, tmp_path: Path) -> None:
        """F36: plugin already installed, but missing from cache → FAIL in update path."""
        _ensure_claude_dir(tmp_path)
        repo_dir = _create_repo_cache(tmp_path, ["alpha"])
        skills_dir = tmp_path / "home" / ".claude" / "skills" / "default"
        # Pre-install alpha locally with marker (simulates prior sync).
        skill_dir = skills_dir / "optimus-alpha"
        skill_dir.mkdir(parents=True, exist_ok=True)
        (skill_dir / "SKILL.md").write_text("previously installed")
        (skill_dir / ".optimus-managed").touch()
        # Now remove SKILL.md from cache → update path must report FAIL.
        (repo_dir / "alpha" / "skills" / "optimus-alpha" / "SKILL.md").unlink()
        result = _run_sync(tmp_path, env_extra={
            "OPTIMUS_CACHE_DIR": str(repo_dir),
            "CLAUDE_SKILLS_DIR": str(skills_dir),
        }, exclude_droid=True)
        assert result.returncode == 1
        # The * marker indicates update path (not + which is install).
        assert "* alpha ... FAIL (source not found)" in result.stdout
        assert "Failed: 1" in result.stdout


# ═══════════════════════════════════════════════════════════════════════════════
# Stale cache via fetch failure (F37)
# ═══════════════════════════════════════════════════════════════════════════════

class TestStaleCache:
    def test_warns_on_fetch_failure_existing_cache(self, tmp_path: Path) -> None:
        """F37: existing valid cache + git fetch fails → cache marked stale, sync proceeds."""
        _ensure_claude_dir(tmp_path)
        # install_git_mock=False so we can install our own that fails on fetch.
        repo_dir = _create_repo_cache(tmp_path, ["alpha"], install_git_mock=False)
        skills_dir = tmp_path / "home" / ".claude" / "skills" / "default"
        # Mock git: handle `-C path` prefix, emit origin URL on config, fail on fetch.
        git_script = f"""
if [ "$1" = "-C" ]; then shift 2; fi
case "$1" in
  config) echo "{DEFAULT_OPTIMUS_REPO_URL}"; exit 0 ;;
  fetch) exit 1 ;;
  reset) exit 0 ;;
esac
exit 0
"""
        _create_mock_bin(tmp_path, "git", git_script)
        result = _run_sync(tmp_path, env_extra={
            "OPTIMUS_CACHE_DIR": str(repo_dir),
            "CLAUDE_SKILLS_DIR": str(skills_dir),
        }, exclude_droid=True)
        # Sync still proceeds using cached marketplace.
        assert result.returncode == 0
        assert "Could not fetch latest" in result.stderr
        assert "(cache: stale)" in result.stdout
        # Confirms cached EXPECTED was used.
        assert (skills_dir / "optimus-alpha" / "SKILL.md").exists()


# ═══════════════════════════════════════════════════════════════════════════════
# Empty marketplace via Source 2 (F38)
# ═══════════════════════════════════════════════════════════════════════════════

class TestEmptyMarketplaceSource2:
    def test_fails_on_empty_marketplace_via_source_2(self, tmp_path: Path) -> None:
        """F38: Source 1 missing, Source 2 (repo cache) empty → exit 1 with 'No plugins found'."""
        _ensure_claude_dir(tmp_path)
        # Source 2: repo cache with empty marketplace. Default git mock handles
        # config/fetch/reset as no-ops returning the right URL.
        repo_dir = _create_repo_cache(tmp_path, [])
        skills_dir = tmp_path / "home" / ".claude" / "skills" / "default"
        # isolated=True so Source 3 (running from inside repo) can't accidentally satisfy.
        result = _run_sync(tmp_path, env_extra={
            "OPTIMUS_CACHE_DIR": str(repo_dir),
            "CLAUDE_SKILLS_DIR": str(skills_dir),
        }, exclude_droid=True, isolated=True)
        assert result.returncode == 1
        assert "No plugins found" in result.stderr
