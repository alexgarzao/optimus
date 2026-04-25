#!/usr/bin/env python3
"""Integration tests for sync-user-plugins.sh using mock commands.

After the refactor to Claude Code's NATIVE plugin system, Claude Code support
no longer copies SKILL.md files. It instead drives `claude plugin install/
update/uninstall` against the user-scope plugin store. The tests here mock
both the `droid` and `claude` binaries and assert the script's command
choreography, summary lines, and failure isolation.
"""

import json
import os
import shlex
import shutil
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parent.parent / "sync" / "scripts" / "sync-user-plugins.sh"
BASH = shutil.which("bash")
if BASH is None:
    pytest.skip("bash not found", allow_module_level=True)

DEFAULT_OPTIMUS_REPO_URL = "https://github.com/alexgarzao/optimus"


# ─── Mock binary helpers ─────────────────────────────────────────────────────

def _create_mock_bin(tmp_path: Path, name: str, script: str) -> None:
    """Create a mock executable in tmp_path/bin/."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    mock = bin_dir / name
    mock.write_text(f"#!/usr/bin/env bash\n{script}\n")
    mock.chmod(0o755)


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


def _claude_script(log: Path,
                   installed_plugins: list[dict] | None = None,
                   install_exit: int = 0,
                   update_exit: int = 0,
                   uninstall_exit: int = 0,
                   marketplace_update_exit: int = 0) -> str:
    """Return a bash mock for the `claude` binary.

    The mock supports the four subcommands the sync script invokes:
      - `claude plugin marketplace update <name>`
      - `claude plugin list --json`
      - `claude plugin install <id> --scope user`
      - `claude plugin update <id>`
      - `claude plugin uninstall <id>`

    `installed_plugins` is a list of dicts that will be returned as the JSON
    array from `claude plugin list --json`. Each dict should at minimum carry
    the `id` key in the `<plugin>@<marketplace>` form (matches the real schema
    observed in Claude Code 2.1.x).
    """
    json_out = json.dumps(installed_plugins or [])
    log_q = shlex.quote(str(log))
    return f"""
echo "$@" >> {log_q}
case "$1 $2" in
  "plugin list")
    if [ "$3" = "--json" ]; then
      cat <<'JSONEOF'
{json_out}
JSONEOF
      exit 0
    fi
    exit 0
    ;;
  "plugin install") exit {install_exit} ;;
  "plugin update") exit {update_exit} ;;
  "plugin uninstall") exit {uninstall_exit} ;;
  "plugin marketplace")
    if [ "$3" = "update" ]; then exit {marketplace_update_exit}; fi
    exit 0
    ;;
esac
exit 0
"""


def _install_claude_mock(tmp_path: Path, log: Path | None = None,
                         installed_plugins: list[dict] | None = None,
                         install_exit: int = 0, update_exit: int = 0,
                         uninstall_exit: int = 0,
                         marketplace_update_exit: int = 0) -> Path:
    """Install a mock `claude` binary in tmp_path/bin/.

    Returns the log path so tests can introspect the issued commands. If `log`
    is not provided, defaults to tmp_path/'claude.log'.
    """
    log = log or (tmp_path / "claude.log")
    script = _claude_script(
        log=log,
        installed_plugins=installed_plugins,
        install_exit=install_exit,
        update_exit=update_exit,
        uninstall_exit=uninstall_exit,
        marketplace_update_exit=marketplace_update_exit,
    )
    _create_mock_bin(tmp_path, "claude", script)
    return log


# ─── Marketplace / cache builders ───────────────────────────────────────────

def _create_marketplace(tmp_path: Path, plugins: list[str], name: str = "optimus") -> None:
    """Create a Source 1 (Droid) marketplace JSON file. Bare plugin names."""
    mp_dir = tmp_path / "home" / ".factory" / "marketplaces" / name / ".factory-plugin"
    mp_dir.mkdir(parents=True)
    mp_file = mp_dir / "marketplace.json"
    entries = ", ".join(f'{{"name": "{p}"}}' for p in plugins)
    mp_file.write_text(f'{{"plugins": [{entries}]}}')


def _create_claude_marketplace_cache(tmp_path: Path, plugins: list[str],
                                     name: str = "optimus") -> Path:
    """Create a Source 2 (Claude Code) marketplace cache.

    Plugin entries use the PREFIXED `optimus-<name>` form, matching the real
    `.claude-plugin/marketplace.json` schema. The script strips the prefix.
    Returns the path to marketplace.json so tests can pass it via
    CLAUDE_MARKETPLACE_FILE.
    """
    mp_dir = tmp_path / "home" / ".claude" / "plugins" / "marketplaces" / name / ".claude-plugin"
    mp_dir.mkdir(parents=True)
    mp_file = mp_dir / "marketplace.json"
    payload = {
        "name": name,
        "owner": {"name": "Test", "email": "test@example.com"},
        "metadata": {"description": "test marketplace"},
        "plugins": [
            {"name": f"optimus-{p}", "source": f"./{p}", "version": "1.0.0",
             "description": f"plugin {p}"}
            for p in plugins
        ],
    }
    mp_file.write_text(json.dumps(payload))
    return mp_file


# ─── PATH helpers ────────────────────────────────────────────────────────────

def _path_without(*binaries: str) -> str:
    """Return system PATH with directories containing any named binary removed."""
    path_dirs = os.environ.get("PATH", "/usr/bin:/bin").split(":")
    filtered = []
    for d in path_dirs:
        if not d:
            continue
        if any((Path(d) / b).exists() for b in binaries):
            continue
        filtered.append(d)
    return ":".join(filtered) if filtered else "/usr/bin:/bin"


# ─── Test runner ─────────────────────────────────────────────────────────────

def _run_sync(tmp_path: Path, env_extra: dict[str, str] | None = None,
              restrict_path: bool = False,
              exclude_droid: bool = False,
              exclude_claude: bool = False,
              isolated: bool = False) -> subprocess.CompletedProcess:
    """Run the sync script with mocked PATH and HOME.

    Args:
        restrict_path: Use only tmp_path/bin as PATH (no system binaries).
        exclude_droid: Filter `droid` out of the system PATH.
        exclude_claude: Filter `claude` out of the system PATH.
        isolated: Copy script to tmp_path so BASH_SOURCE doesn't resolve to
            the optimus repo (defeats Source 3 fallback).
    """
    env = os.environ.copy()
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    if restrict_path:
        env["PATH"] = str(bin_dir)
    else:
        excluded: list[str] = []
        if exclude_droid:
            excluded.append("droid")
        if exclude_claude:
            excluded.append("claude")
        sys_path = _path_without(*excluded) if excluded else env.get("PATH", "/usr/bin")
        env["PATH"] = f"{bin_dir}:{sys_path}"
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


# ═══════════════════════════════════════════════════════════════════════════════
# Dependency / detection
# ═══════════════════════════════════════════════════════════════════════════════

class TestDependencyChecks:
    def test_fails_without_any_platform(self, tmp_path: Path) -> None:
        """Neither droid nor claude on PATH → error."""
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir(exist_ok=True)
        jq_path = shutil.which("jq")
        if jq_path:
            os.symlink(jq_path, bin_dir / "jq")
        else:
            (bin_dir / "jq").write_text("#!/bin/bash\necho jq\n")
            (bin_dir / "jq").chmod(0o755)
        result = _run_sync(tmp_path, restrict_path=True)
        assert result.returncode == 1
        assert "No supported platform found" in result.stderr

    def test_fails_without_jq(self, tmp_path: Path) -> None:
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


class TestPlatformDetection:
    def test_detects_claude_code_when_claude_binary_present(self, tmp_path: Path) -> None:
        """When `claude` is on PATH and Droid is not, Claude Code is detected."""
        _install_claude_mock(tmp_path)
        _create_claude_marketplace_cache(tmp_path, ["alpha"])
        result = _run_sync(tmp_path, exclude_droid=True, env_extra={
            "CLAUDE_MARKETPLACE_FILE": str(
                tmp_path / "home" / ".claude" / "plugins" / "marketplaces"
                / "optimus" / ".claude-plugin" / "marketplace.json"),
        })
        assert result.returncode == 0
        assert "Platforms:" in result.stdout
        assert "Claude Code" in result.stdout
        assert "── Claude Code ──" in result.stdout
        assert "── Droid (Factory) ──" not in result.stdout

    def test_skips_claude_code_when_claude_binary_missing(self, tmp_path: Path) -> None:
        """When `claude` is absent and droid present, only Droid runs."""
        log = tmp_path / "droid.log"
        _create_mock_bin(tmp_path, "droid", _droid_script(log))
        _create_marketplace(tmp_path, ["alpha"])
        result = _run_sync(tmp_path, exclude_claude=True)
        assert result.returncode == 0
        assert "── Droid (Factory) ──" in result.stdout
        assert "── Claude Code ──" not in result.stdout
        assert "install alpha@optimus" in log.read_text()


# ═══════════════════════════════════════════════════════════════════════════════
# Droid sync — unchanged behavior (smoke + edge cases)
# ═══════════════════════════════════════════════════════════════════════════════

class TestFirstTimeInstall:
    def test_installs_all_plugins_on_first_run(self, tmp_path: Path) -> None:
        log = tmp_path / "droid.log"
        _create_mock_bin(tmp_path, "droid", _droid_script(log))
        _create_marketplace(tmp_path, ["alpha", "beta"])
        result = _run_sync(tmp_path, exclude_claude=True)
        assert result.returncode == 0
        assert "Added: 2" in result.stdout
        assert "alpha ... OK" in result.stdout
        assert "beta ... OK" in result.stdout
        log_content = log.read_text()
        assert "alpha@optimus" in log_content
        assert "beta@optimus" in log_content


class TestUpdateWithExisting:
    def test_updates_existing_plugins(self, tmp_path: Path) -> None:
        log = tmp_path / "droid.log"
        _create_mock_bin(tmp_path, "droid", _droid_script(
            log, list_output="alpha@optimus  installed"))
        _create_marketplace(tmp_path, ["alpha"])
        result = _run_sync(tmp_path, exclude_claude=True)
        assert result.returncode == 0
        assert "Updated: 1" in result.stdout


class TestOrphanRemoval:
    def test_removes_orphaned_plugins(self, tmp_path: Path) -> None:
        log = tmp_path / "droid.log"
        _create_mock_bin(tmp_path, "droid", _droid_script(
            log, list_output="alpha@optimus  installed\norphan@optimus  installed"))
        _create_marketplace(tmp_path, ["alpha"])
        result = _run_sync(tmp_path, exclude_claude=True)
        assert result.returncode == 0
        assert "Removed: 1" in result.stdout
        log_content = log.read_text()
        assert "uninstall orphan@optimus" in log_content


class TestScopeConflict:
    def test_reinstalls_on_scope_conflict(self, tmp_path: Path) -> None:
        log = tmp_path / "droid.log"
        _create_mock_bin(tmp_path, "droid", _droid_script(
            log, list_output="alpha@optimus  installed", update_exit=1))
        _create_marketplace(tmp_path, ["alpha"])
        result = _run_sync(tmp_path, exclude_claude=True)
        assert result.returncode == 0
        assert "reinstalled" in result.stdout.lower()
        log_content = log.read_text()
        assert "uninstall alpha@optimus" in log_content
        assert "install alpha@optimus" in log_content


class TestMarketplaceOverride:
    def test_custom_marketplace_name(self, tmp_path: Path) -> None:
        log = tmp_path / "droid.log"
        _create_mock_bin(tmp_path, "droid", _droid_script(log))
        _create_marketplace(tmp_path, ["test"], name="custom")
        result = _run_sync(tmp_path, env_extra={"OPTIMUS_MARKETPLACE_NAME": "custom"},
                           exclude_claude=True)
        assert result.returncode == 0
        assert "Added: 1" in result.stdout


class TestErrorPaths:
    def test_fails_on_marketplace_not_found(self, tmp_path: Path) -> None:
        log = tmp_path / "droid.log"
        _create_mock_bin(tmp_path, "droid", _droid_script(log))
        (tmp_path / "home" / ".factory").mkdir(parents=True)
        # Use isolated=True so BASH_SOURCE doesn't resolve to the optimus repo.
        result = _run_sync(tmp_path, isolated=True, exclude_claude=True)
        assert result.returncode == 1
        assert "not found" in result.stderr.lower()

    def test_fails_on_empty_marketplace(self, tmp_path: Path) -> None:
        log = tmp_path / "droid.log"
        _create_mock_bin(tmp_path, "droid", _droid_script(log))
        mp_dir = tmp_path / "home" / ".factory" / "marketplaces" / "optimus" / ".factory-plugin"
        mp_dir.mkdir(parents=True)
        (mp_dir / "marketplace.json").write_text('{"plugins": []}')
        result = _run_sync(tmp_path, exclude_claude=True)
        assert result.returncode == 1
        assert "No plugins found" in result.stderr

    def test_exits_nonzero_on_persistent_failure(self, tmp_path: Path) -> None:
        log = tmp_path / "droid.log"
        _create_mock_bin(tmp_path, "droid", _droid_script(log, install_exit=1))
        _create_marketplace(tmp_path, ["failing"])
        result = _run_sync(tmp_path, exclude_claude=True)
        assert result.returncode == 1
        assert "Failed:" in result.stdout


class TestDroidTimeout:
    def test_rejects_zero_timeout(self, tmp_path: Path) -> None:
        log = tmp_path / "droid.log"
        _create_mock_bin(tmp_path, "droid", _droid_script(log))
        _create_marketplace(tmp_path, ["alpha"])
        result = _run_sync(tmp_path, env_extra={"OPTIMUS_DROID_TIMEOUT": "0"},
                           exclude_claude=True)
        assert result.returncode == 1
        assert "positive integer" in result.stderr

    def test_rejects_non_numeric_timeout(self, tmp_path: Path) -> None:
        log = tmp_path / "droid.log"
        _create_mock_bin(tmp_path, "droid", _droid_script(log))
        _create_marketplace(tmp_path, ["alpha"])
        result = _run_sync(tmp_path, env_extra={"OPTIMUS_DROID_TIMEOUT": "abc"},
                           exclude_claude=True)
        assert result.returncode == 1
        assert "positive integer" in result.stderr

    def test_rejects_negative_timeout(self, tmp_path: Path) -> None:
        log = tmp_path / "droid.log"
        _create_mock_bin(tmp_path, "droid", _droid_script(log))
        _create_marketplace(tmp_path, ["alpha"])
        result = _run_sync(tmp_path, env_extra={"OPTIMUS_DROID_TIMEOUT": "-5"},
                           exclude_claude=True)
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
        result = _run_sync(tmp_path, exclude_claude=True)
        assert result.returncode == 1
        assert "Added: 2" in result.stdout
        assert "Failed:" in result.stdout


class TestMarketplaceUpdateFailure:
    def test_continues_after_droid_marketplace_update_failure(self, tmp_path: Path) -> None:
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
        result = _run_sync(tmp_path, exclude_claude=True)
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
        env["PATH"] = f"{bin_dir}:{_path_without('claude')}"
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
        proc.communicate(timeout=10)
        assert proc.returncode == 130


class TestTimeoutWrapper:
    def test_uses_timeout_when_available(self, tmp_path: Path) -> None:
        log = tmp_path / "droid.log"
        timeout_log = tmp_path / "timeout.log"
        _create_mock_bin(tmp_path, "droid", _droid_script(log))
        _create_marketplace(tmp_path, ["alpha"])
        timeout_script = (
            f'echo "timeout called with: $@" >> "{timeout_log}"\n'
            'shift; exec "$@"\n'
        )
        _create_mock_bin(tmp_path, "timeout", timeout_script)
        result = _run_sync(tmp_path, exclude_claude=True)
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
        result = _run_sync(tmp_path, exclude_claude=True)
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
        result = _run_sync(tmp_path, exclude_claude=True)
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
        result = _run_sync(tmp_path, exclude_claude=True)
        assert result.returncode != 0


# ═══════════════════════════════════════════════════════════════════════════════
# Claude Code sync — native plugin install/update/uninstall
# ═══════════════════════════════════════════════════════════════════════════════

class TestClaudeCodeSync:
    def _claude_only_env(self, tmp_path: Path) -> dict[str, str]:
        return {
            "CLAUDE_MARKETPLACE_FILE": str(
                tmp_path / "home" / ".claude" / "plugins" / "marketplaces"
                / "optimus" / ".claude-plugin" / "marketplace.json"),
        }

    def test_installs_new_plugins_via_claude_install(self, tmp_path: Path) -> None:
        """`claude plugin install <name>@optimus --scope user` is called for every
        plugin from the marketplace when none are installed yet."""
        log = _install_claude_mock(tmp_path, installed_plugins=[])
        _create_claude_marketplace_cache(tmp_path, ["alpha", "beta"])
        result = _run_sync(tmp_path, exclude_droid=True,
                           env_extra=self._claude_only_env(tmp_path))
        assert result.returncode == 0
        assert "── Claude Code ──" in result.stdout
        assert "Added: 2" in result.stdout
        log_content = log.read_text()
        assert "plugin install optimus-alpha@optimus --scope user" in log_content
        assert "plugin install optimus-beta@optimus --scope user" in log_content

    def test_updates_existing_plugins_via_claude_update(self, tmp_path: Path) -> None:
        """When a plugin is already installed, the script issues `plugin update`."""
        installed = [
            {"id": "optimus-alpha@optimus", "version": "1.0.0", "scope": "user",
             "enabled": True},
        ]
        log = _install_claude_mock(tmp_path, installed_plugins=installed)
        _create_claude_marketplace_cache(tmp_path, ["alpha"])
        result = _run_sync(tmp_path, exclude_droid=True,
                           env_extra=self._claude_only_env(tmp_path))
        assert result.returncode == 0
        assert "Updated: 1" in result.stdout
        log_content = log.read_text()
        assert "plugin update optimus-alpha@optimus" in log_content
        assert "plugin install optimus-alpha@optimus" not in log_content

    def test_removes_orphans_via_claude_uninstall(self, tmp_path: Path) -> None:
        """Plugins installed but not in the marketplace are uninstalled."""
        installed = [
            {"id": "optimus-alpha@optimus", "version": "1.0.0", "scope": "user",
             "enabled": True},
            {"id": "optimus-orphan@optimus", "version": "1.0.0", "scope": "user",
             "enabled": True},
        ]
        log = _install_claude_mock(tmp_path, installed_plugins=installed)
        _create_claude_marketplace_cache(tmp_path, ["alpha"])
        result = _run_sync(tmp_path, exclude_droid=True,
                           env_extra=self._claude_only_env(tmp_path))
        assert result.returncode == 0
        assert "Removed: 1" in result.stdout
        log_content = log.read_text()
        assert "plugin uninstall optimus-orphan@optimus" in log_content

    def test_install_failure_increments_failed_count(self, tmp_path: Path) -> None:
        """When `claude plugin install` exits non-zero, summary shows Failed > 0."""
        log = _install_claude_mock(tmp_path, installed_plugins=[], install_exit=1)
        _create_claude_marketplace_cache(tmp_path, ["alpha"])
        result = _run_sync(tmp_path, exclude_droid=True,
                           env_extra=self._claude_only_env(tmp_path))
        assert result.returncode == 1
        assert "Claude Code — Added: 0" in result.stdout
        assert "Failed: 1" in result.stdout
        assert "+ alpha ... FAIL" in result.stdout
        # Install was still attempted (logged) before failing.
        assert "plugin install optimus-alpha@optimus" in log.read_text()

    def test_update_failure_increments_failed_count(self, tmp_path: Path) -> None:
        """A failing `claude plugin update` is reported as FAIL."""
        installed = [
            {"id": "optimus-alpha@optimus", "version": "1.0.0", "scope": "user",
             "enabled": True},
        ]
        _install_claude_mock(tmp_path, installed_plugins=installed, update_exit=1)
        _create_claude_marketplace_cache(tmp_path, ["alpha"])
        result = _run_sync(tmp_path, exclude_droid=True,
                           env_extra=self._claude_only_env(tmp_path))
        assert result.returncode == 1
        assert "Failed: 1" in result.stdout
        assert "* alpha ... FAIL" in result.stdout

    def test_uninstall_failure_increments_failed_count(self, tmp_path: Path) -> None:
        """A failing `claude plugin uninstall` is reported as FAIL."""
        installed = [
            {"id": "optimus-orphan@optimus", "version": "1.0.0", "scope": "user",
             "enabled": True},
        ]
        _install_claude_mock(tmp_path, installed_plugins=installed, uninstall_exit=1)
        _create_claude_marketplace_cache(tmp_path, ["alpha"])
        result = _run_sync(tmp_path, exclude_droid=True,
                           env_extra=self._claude_only_env(tmp_path))
        # alpha installs OK, orphan uninstall FAILs → exit 1.
        assert result.returncode == 1
        assert "Added: 1" in result.stdout
        assert "Failed: 1" in result.stdout
        assert "- orphan ... FAIL" in result.stdout

    def test_marketplace_update_failure_warns_but_continues(self, tmp_path: Path) -> None:
        """If `claude plugin marketplace update` fails, the script warns and continues
        using the cached marketplace JSON."""
        log = _install_claude_mock(tmp_path, installed_plugins=[],
                                    marketplace_update_exit=1)
        _create_claude_marketplace_cache(tmp_path, ["alpha"])
        result = _run_sync(tmp_path, exclude_droid=True,
                           env_extra=self._claude_only_env(tmp_path))
        assert result.returncode == 0
        assert "Could not update Claude Code marketplace" in result.stderr
        assert "Added: 1" in result.stdout
        # Install was still attempted using the cached marketplace.
        assert "plugin install optimus-alpha@optimus" in log.read_text()

    def test_summary_uses_added_updated_removed_failed_format(self, tmp_path: Path) -> None:
        """Claude Code summary line matches Droid's format (no `Unchanged` field)."""
        installed = [
            {"id": "optimus-alpha@optimus", "version": "1.0.0", "scope": "user",
             "enabled": True},
            {"id": "optimus-orphan@optimus", "version": "1.0.0", "scope": "user",
             "enabled": True},
        ]
        _install_claude_mock(tmp_path, installed_plugins=installed)
        _create_claude_marketplace_cache(tmp_path, ["alpha", "beta"])
        result = _run_sync(tmp_path, exclude_droid=True,
                           env_extra=self._claude_only_env(tmp_path))
        assert result.returncode == 0
        assert "Claude Code — Added: 1 | Updated: 1 | Removed: 1 | Failed: 0" in result.stdout
        assert "Unchanged" not in result.stdout

    def test_filters_non_optimus_marketplace_plugins(self, tmp_path: Path) -> None:
        """Plugins from other marketplaces (not @optimus) are ignored."""
        installed = [
            {"id": "optimus-alpha@optimus", "version": "1.0.0", "scope": "user"},
            {"id": "ring:reviewer@ring", "version": "2.0.0", "scope": "user"},
            {"id": "vendor-tool@other", "version": "1.0.0", "scope": "user"},
        ]
        log = _install_claude_mock(tmp_path, installed_plugins=installed)
        _create_claude_marketplace_cache(tmp_path, ["alpha"])
        result = _run_sync(tmp_path, exclude_droid=True,
                           env_extra=self._claude_only_env(tmp_path))
        assert result.returncode == 0
        # alpha is updated (already installed under @optimus), no orphan removal,
        # other-marketplace plugins are NOT touched.
        assert "Updated: 1" in result.stdout
        assert "Removed: 0" in result.stdout
        log_content = log.read_text()
        assert "plugin uninstall ring" not in log_content
        assert "plugin uninstall vendor" not in log_content


# ═══════════════════════════════════════════════════════════════════════════════
# Dual-platform sync (both droid + claude installed)
# ═══════════════════════════════════════════════════════════════════════════════

class TestDualPlatformSync:
    def _claude_marketplace_env(self, tmp_path: Path) -> dict[str, str]:
        return {
            "CLAUDE_MARKETPLACE_FILE": str(
                tmp_path / "home" / ".claude" / "plugins" / "marketplaces"
                / "optimus" / ".claude-plugin" / "marketplace.json"),
        }

    def test_syncs_both_platforms_simultaneously(self, tmp_path: Path) -> None:
        droid_log = tmp_path / "droid.log"
        _create_mock_bin(tmp_path, "droid", _droid_script(droid_log))
        _create_marketplace(tmp_path, ["alpha", "beta"])
        claude_log = _install_claude_mock(tmp_path, installed_plugins=[])
        result = _run_sync(tmp_path)
        assert result.returncode == 0
        assert "── Droid (Factory) ──" in result.stdout
        assert "── Claude Code ──" in result.stdout
        # Droid installed both via the Source 1 (droid) marketplace.
        assert "install alpha@optimus" in droid_log.read_text()
        assert "install beta@optimus" in droid_log.read_text()
        # Claude installed both via the same EXPECTED list (bare names → prefixed).
        claude_content = claude_log.read_text()
        assert "plugin install optimus-alpha@optimus --scope user" in claude_content
        assert "plugin install optimus-beta@optimus --scope user" in claude_content

    def test_droid_only_when_no_claude_binary(self, tmp_path: Path) -> None:
        log = tmp_path / "droid.log"
        _create_mock_bin(tmp_path, "droid", _droid_script(log))
        _create_marketplace(tmp_path, ["alpha"])
        result = _run_sync(tmp_path, exclude_claude=True)
        assert result.returncode == 0
        assert "── Droid (Factory) ──" in result.stdout
        assert "── Claude Code ──" not in result.stdout

    def test_claude_only_when_no_droid_binary(self, tmp_path: Path) -> None:
        log = _install_claude_mock(tmp_path, installed_plugins=[])
        _create_claude_marketplace_cache(tmp_path, ["alpha"])
        result = _run_sync(tmp_path, exclude_droid=True,
                           env_extra=self._claude_marketplace_env(tmp_path))
        assert result.returncode == 0
        assert "── Droid (Factory) ──" not in result.stdout
        assert "── Claude Code ──" in result.stdout
        assert "plugin install optimus-alpha@optimus --scope user" in log.read_text()

    def test_droid_failure_doesnt_block_claude(self, tmp_path: Path) -> None:
        """If Droid sync fails, Claude Code sync still runs to completion."""
        droid_log = tmp_path / "droid.log"
        _create_mock_bin(tmp_path, "droid", _droid_script(droid_log, install_exit=1))
        _create_marketplace(tmp_path, ["alpha"])
        claude_log = _install_claude_mock(tmp_path, installed_plugins=[])
        result = _run_sync(tmp_path)
        # Aggregated failure (droid failed) but both sections ran.
        assert result.returncode == 1
        assert "── Droid (Factory) ──" in result.stdout
        assert "── Claude Code ──" in result.stdout
        # Claude install was attempted.
        assert "plugin install optimus-alpha@optimus --scope user" in claude_log.read_text()
        # Claude's added count must be 1 (not blocked by droid failure).
        assert "Claude Code — Added: 1" in result.stdout

    def test_claude_failure_doesnt_block_droid(self, tmp_path: Path) -> None:
        """If Claude Code sync fails, Droid sync still completes installs."""
        droid_log = tmp_path / "droid.log"
        _create_mock_bin(tmp_path, "droid", _droid_script(droid_log))
        _create_marketplace(tmp_path, ["alpha"])
        # Claude install fails for every call.
        _install_claude_mock(tmp_path, installed_plugins=[], install_exit=1)
        result = _run_sync(tmp_path)
        assert result.returncode == 1
        assert "── Droid (Factory) ──" in result.stdout
        assert "── Claude Code ──" in result.stdout
        # Droid still completed its install.
        assert "install alpha@optimus" in droid_log.read_text()
        # And Claude reported a failure.
        assert "Claude Code — Added: 0" in result.stdout
        assert "Failed: 1" in result.stdout

    def test_both_marketplace_updates_attempted(self, tmp_path: Path) -> None:
        """When both platforms are present, both marketplace-refresh calls happen."""
        droid_log = tmp_path / "droid.log"
        _create_mock_bin(tmp_path, "droid", _droid_script(droid_log))
        _create_marketplace(tmp_path, ["alpha"])
        claude_log = _install_claude_mock(tmp_path, installed_plugins=[])
        result = _run_sync(tmp_path)
        assert result.returncode == 0
        assert "Updating Droid marketplace..." in result.stdout
        assert "Updating Claude Code marketplace..." in result.stdout
        # Claude marketplace update is logged with `plugin marketplace update optimus`.
        assert "plugin marketplace update optimus" in claude_log.read_text()


# ═══════════════════════════════════════════════════════════════════════════════
# Marketplace source resolution
# ═══════════════════════════════════════════════════════════════════════════════

class TestSourceResolution:
    def test_resolves_from_droid_cache_source_1(self, tmp_path: Path) -> None:
        """Source 1 (~/.factory/marketplaces/.../marketplace.json) takes priority."""
        log = tmp_path / "droid.log"
        _create_mock_bin(tmp_path, "droid", _droid_script(log))
        _create_marketplace(tmp_path, ["fromsrc1"])
        result = _run_sync(tmp_path, exclude_claude=True)
        assert result.returncode == 0
        assert "install fromsrc1@optimus" in log.read_text()

    def test_resolves_from_claude_marketplace_cache_source_2(self, tmp_path: Path) -> None:
        """Source 2 (CLAUDE_MARKETPLACE_FILE) is used when Source 1 is absent.

        Names from this source are PREFIXED (`optimus-foo`) — the script must
        strip the prefix before exposing them as the EXPECTED bare list.
        """
        _install_claude_mock(tmp_path, installed_plugins=[])
        # No droid binary, no Source 1.
        mp_path = _create_claude_marketplace_cache(tmp_path, ["fromsrc2"])
        # isolated=True so Source 3 cannot satisfy from the optimus repo root.
        result = _run_sync(tmp_path, exclude_droid=True, isolated=True,
                           env_extra={"CLAUDE_MARKETPLACE_FILE": str(mp_path)})
        assert result.returncode == 0
        # Bare name reaches Claude Code with the optimus- prefix re-attached.
        assert "+ fromsrc2 ... OK" in result.stdout

    def test_resolves_from_repo_factory_plugin_source_3(self, tmp_path: Path) -> None:
        """Source 3 (in-repo .factory-plugin/marketplace.json) is the fallback when
        Source 1 and Source 2 are both absent."""
        log = tmp_path / "droid.log"
        _create_mock_bin(tmp_path, "droid", _droid_script(log))
        # Build a fake repo layout that exposes Source 3.
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
        env = os.environ.copy()
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir(exist_ok=True)
        env["PATH"] = f"{bin_dir}:{_path_without('claude')}"
        env["HOME"] = str(tmp_path / "home")
        result = subprocess.run(
            [BASH, str(fake_repo / "sync" / "scripts" / "sync-user-plugins.sh")],
            capture_output=True,
            text=True,
            env=env,
            timeout=30,
        )
        assert result.returncode == 0, f"stderr: {result.stderr}\nstdout: {result.stdout}"
        assert "Added: 1" in result.stdout
        assert "install fromsrc3@optimus" in log.read_text()

    def test_resolves_from_repo_claude_plugin_fallback(self, tmp_path: Path) -> None:
        """Source 3 fallback: in-repo `.claude-plugin/marketplace.json` is consulted
        when `.factory-plugin/marketplace.json` is absent. Names use the prefixed
        form and must be stripped to bare."""
        _install_claude_mock(tmp_path, installed_plugins=[])
        fake_repo = tmp_path / "fake_repo"
        (fake_repo / "sync" / "scripts").mkdir(parents=True)
        (fake_repo / ".claude-plugin").mkdir(parents=True)
        shutil.copy2(SCRIPT, fake_repo / "sync" / "scripts" / "sync-user-plugins.sh")
        (fake_repo / "AGENTS.md").write_text("# AGENTS")
        (fake_repo / ".claude-plugin" / "marketplace.json").write_text(json.dumps({
            "name": "optimus",
            "owner": {"name": "T", "email": "t@e"},
            "metadata": {"description": "x"},
            "plugins": [{"name": "optimus-fallback", "source": "./fallback",
                         "version": "1.0.0", "description": "x"}],
        }))
        # No Source 1 (no droid). No Source 2 (no CLAUDE_MARKETPLACE_FILE).
        env = os.environ.copy()
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir(exist_ok=True)
        env["PATH"] = f"{bin_dir}:{_path_without('droid', 'claude')}"
        env["HOME"] = str(tmp_path / "home")
        result = subprocess.run(
            [BASH, str(fake_repo / "sync" / "scripts" / "sync-user-plugins.sh")],
            capture_output=True,
            text=True,
            env=env,
            timeout=30,
        )
        assert result.returncode == 0, f"stderr: {result.stderr}\nstdout: {result.stdout}"
        # Stripped to bare 'fallback' on the EXPECTED list, then re-prefixed for
        # the Claude Code install command.
        assert "+ fallback ... OK" in result.stdout

    def test_empty_marketplace_via_source_2_fails(self, tmp_path: Path) -> None:
        """F38 analog: Source 1 missing, Source 2 is the only available source but
        the marketplace plugin list is empty → exit 1 with 'No plugins found'."""
        _install_claude_mock(tmp_path, installed_plugins=[])
        mp_path = _create_claude_marketplace_cache(tmp_path, [])
        # isolated=True so Source 3 inside the optimus repo doesn't accidentally satisfy.
        result = _run_sync(tmp_path, exclude_droid=True, isolated=True,
                           env_extra={"CLAUDE_MARKETPLACE_FILE": str(mp_path)})
        assert result.returncode == 1
        assert "No plugins found" in result.stderr


# ═══════════════════════════════════════════════════════════════════════════════
# Plugin name validation
# ═══════════════════════════════════════════════════════════════════════════════

class TestPluginNameValidation:
    def test_rejects_plugin_name_with_path_traversal(self, tmp_path: Path) -> None:
        log = tmp_path / "droid.log"
        _create_mock_bin(tmp_path, "droid", _droid_script(log))
        mp_dir = tmp_path / "home" / ".factory" / "marketplaces" / "optimus" / ".factory-plugin"
        mp_dir.mkdir(parents=True)
        (mp_dir / "marketplace.json").write_text(
            '{"plugins": [{"name": "../../../etc"}]}'
        )
        result = _run_sync(tmp_path, exclude_claude=True)
        assert result.returncode == 1
        assert "Invalid plugin name" in result.stderr

    def test_rejects_plugin_name_with_uppercase(self, tmp_path: Path) -> None:
        log = tmp_path / "droid.log"
        _create_mock_bin(tmp_path, "droid", _droid_script(log))
        mp_dir = tmp_path / "home" / ".factory" / "marketplaces" / "optimus" / ".factory-plugin"
        mp_dir.mkdir(parents=True)
        (mp_dir / "marketplace.json").write_text(
            '{"plugins": [{"name": "MyPlugin"}]}'
        )
        result = _run_sync(tmp_path, exclude_claude=True)
        assert result.returncode == 1
        assert "Invalid plugin name" in result.stderr

    def test_rejects_plugin_name_with_leading_dash(self, tmp_path: Path) -> None:
        log = tmp_path / "droid.log"
        _create_mock_bin(tmp_path, "droid", _droid_script(log))
        mp_dir = tmp_path / "home" / ".factory" / "marketplaces" / "optimus" / ".factory-plugin"
        mp_dir.mkdir(parents=True)
        (mp_dir / "marketplace.json").write_text(
            '{"plugins": [{"name": "-evil"}]}'
        )
        result = _run_sync(tmp_path, exclude_claude=True)
        assert result.returncode == 1
        assert "Invalid plugin name" in result.stderr

    def test_accepts_valid_plugin_names(self, tmp_path: Path) -> None:
        log = tmp_path / "droid.log"
        _create_mock_bin(tmp_path, "droid", _droid_script(log))
        valid_names = ["plan", "build-2", "optimus_helper", "abc", "x1"]
        _create_marketplace(tmp_path, valid_names)
        result = _run_sync(tmp_path, exclude_claude=True)
        assert result.returncode == 0
        assert "Invalid plugin name" not in result.stderr
        for name in valid_names:
            assert f"+ {name} ... OK" in result.stdout


# ═══════════════════════════════════════════════════════════════════════════════
# Custom OPTIMUS_REPO_URL surfacing
# ═══════════════════════════════════════════════════════════════════════════════

class TestCustomRepoURL:
    def test_announces_custom_repo_url(self, tmp_path: Path) -> None:
        log = tmp_path / "droid.log"
        _create_mock_bin(tmp_path, "droid", _droid_script(log))
        _create_marketplace(tmp_path, ["alpha"])
        result = _run_sync(tmp_path, exclude_claude=True, env_extra={
            "OPTIMUS_REPO_URL": "https://example.com/fork/optimus",
        })
        assert result.returncode == 0
        assert "Note: using custom OPTIMUS_REPO_URL=https://example.com/fork/optimus" in result.stdout

    def test_does_not_announce_default_repo_url(self, tmp_path: Path) -> None:
        log = tmp_path / "droid.log"
        _create_mock_bin(tmp_path, "droid", _droid_script(log))
        _create_marketplace(tmp_path, ["alpha"])
        result = _run_sync(tmp_path, exclude_claude=True)
        assert result.returncode == 0
        assert "Note: using custom OPTIMUS_REPO_URL" not in result.stdout


# ═══════════════════════════════════════════════════════════════════════════════
# Bootstrap path contract
# ═══════════════════════════════════════════════════════════════════════════════

class TestBootstrapContract:
    def test_bootstrap_paths_exist(self) -> None:
        """The bootstrap one-liner relies on a specific set of repo files.

        Post-refactor: the in-repo Claude Code marketplace
        (`.claude-plugin/marketplace.json`) is now part of the contract — Source
        3 falls back to it when Source 1 / 2 are missing.
        """
        repo_root = Path(__file__).resolve().parent.parent
        skill_path = repo_root / "sync" / "skills" / "optimus-sync" / "SKILL.md"
        assert skill_path.exists(), f"Missing: {skill_path}"
        skill_md = skill_path.read_text()
        assert "name: optimus-sync" in skill_md
        assert (repo_root / "sync" / "scripts" / "sync-user-plugins.sh").exists()
        # Both marketplace files must exist so dual-platform bootstrap works.
        assert (repo_root / ".claude-plugin" / "marketplace.json").exists()
        assert (repo_root / ".factory-plugin" / "marketplace.json").exists()
