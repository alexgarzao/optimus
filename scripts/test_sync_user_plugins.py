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
        """When `claude` is on PATH and Droid is not, Claude Code is detected.

        F9-1: Banner-only assertion was insufficient — a regression that
        announced the platform but skipped the install loop would slip past.
        Strengthened with log-file evidence proving the install machinery
        ran (the mock `claude` binary records every invocation).
        """
        claude_log = _install_claude_mock(tmp_path)
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
        # F9-1: Prove the install loop actually ran — banner alone is not
        # sufficient evidence that the platform was exercised.
        assert claude_log.exists(), "claude mock log not created — install loop never invoked claude"
        log_content = claude_log.read_text()
        assert "plugin list" in log_content, (
            f"claude `plugin list` not invoked; install loop did not run. log={log_content!r}"
        )

    def test_skips_claude_code_when_claude_binary_missing(self, tmp_path: Path) -> None:
        """When `claude` is absent and droid present, only Droid runs.

        F9-1: The log-file assertion (`install alpha@optimus`) already proves
        the Droid install loop ran — kept and clarified.
        """
        log = tmp_path / "droid.log"
        _create_mock_bin(tmp_path, "droid", _droid_script(log))
        _create_marketplace(tmp_path, ["alpha"])
        result = _run_sync(tmp_path, exclude_claude=True)
        assert result.returncode == 0
        assert "── Droid (Factory) ──" in result.stdout
        assert "── Claude Code ──" not in result.stdout
        # F9-1: log-file evidence — confirms install loop entered, not just the banner.
        assert log.exists(), "droid mock log not created — install loop never invoked droid"
        log_content = log.read_text()
        assert "install alpha@optimus" in log_content, (
            f"droid install loop did not run. log={log_content!r}"
        )


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


class TestForceRefresh:
    """The Droid branch refreshes existing plugins via uninstall+install.

    Rationale: `droid plugin update` can be a no-op when marketplace.json's
    `version` field hasn't changed, even when the underlying source files
    have. Optimus ships SKILL changes without bumping the marketplace version
    on every PR, so update would leave users on stale cached SKILL.md.
    Mirrors the fix applied to the Claude branch in PR #44.
    """

    def test_existing_plugins_are_refreshed_via_uninstall_install(
        self, tmp_path: Path
    ) -> None:
        log = tmp_path / "droid.log"
        _create_mock_bin(tmp_path, "droid", _droid_script(
            log, list_output="alpha@optimus  installed"))
        _create_marketplace(tmp_path, ["alpha"])
        result = _run_sync(tmp_path, exclude_claude=True)
        assert result.returncode == 0
        # Output marker confirms refresh path was taken.
        assert "(refreshed)" in result.stdout.lower()
        log_content = log.read_text()
        # uninstall happens BEFORE install (force-refresh ordering).
        assert "uninstall alpha@optimus" in log_content
        assert "install alpha@optimus" in log_content
        assert log_content.find("uninstall alpha@optimus") < log_content.find(
            "install alpha@optimus"
        )
        # `update` is no longer used as the primary path.
        assert "update alpha@optimus" not in log_content


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
        # F9-2: Replace flaky time.sleep(2) with marker-file polling. The mock
        # droid touches READY_FILE before its inner sleep, so the test can wait
        # deterministically for the install loop to enter `sleep 30` rather than
        # guessing a wall-clock duration that breaks on slow CI.
        log = tmp_path / "droid.log"
        ready_file = tmp_path / "READY"
        script = f"""
CMD="$1 $2"
case "$CMD" in
  "plugin marketplace") exit 0 ;;
  "plugin list") echo "" ;;
  "plugin install") touch "$READY_FILE"; sleep 30; echo "install $3" >> "{log}"; exit 0 ;;
  *) echo "unknown: $@" >> "{log}" ;;
esac
"""
        _create_mock_bin(tmp_path, "droid", script)
        _create_marketplace(tmp_path, ["slow-plugin"])
        env = os.environ.copy()
        bin_dir = tmp_path / "bin"
        env["PATH"] = f"{bin_dir}:{_path_without('claude')}"
        env["HOME"] = str(tmp_path / "home")
        env["READY_FILE"] = str(ready_file)
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
        # Poll for the ready marker (5s cap) instead of sleeping a fixed
        # wall-clock duration — eliminates flakiness on slow CI.
        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline:
            if ready_file.exists():
                break
            time.sleep(0.05)
        else:
            proc.terminate()
            proc.communicate(timeout=10)
            pytest.fail("Mock droid did not reach READY marker within 5s")
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
    def test_retries_transient_install_failure_during_refresh(
        self, tmp_path: Path
    ) -> None:
        """When the parallel uninstall+install pass loses a race for a plugin
        already in INSTALLED, the serial retry runs the same uninstall+install
        sequence again. The plugin lands as Updated on success.
        """
        log = tmp_path / "droid.log"
        state_dir = tmp_path / "state"
        state_dir.mkdir()
        script = f"""
CMD="$1 $2"
case "$CMD" in
  "plugin marketplace") exit 0 ;;
  "plugin list") echo "alpha@optimus  installed" ;;
  "plugin uninstall") echo "uninstall $3" >> "{log}"; exit 0 ;;
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
        assert "Updated: 1" in result.stdout
        log_content = log.read_text()
        # First install attempt (parallel pass) failed; serial retry succeeded.
        assert "install alpha@optimus #1" in log_content
        assert "install alpha@optimus #2" in log_content
        # `update` is no longer part of the refresh path.
        assert "update alpha@optimus" not in log_content

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
    """Claude Code now installs a SINGLE `optimus@optimus` plugin regardless of
    how many bare-name skills the Droid marketplace lists. Pre-2.0 per-skill
    installs (`optimus-<name>@optimus`) are detected and uninstalled silently
    as legacy entries.
    """

    def _claude_only_env(self, tmp_path: Path) -> dict[str, str]:
        return {
            "CLAUDE_MARKETPLACE_FILE": str(
                tmp_path / "home" / ".claude" / "plugins" / "marketplaces"
                / "optimus" / ".claude-plugin" / "marketplace.json"),
        }

    def test_installs_single_optimus_plugin_when_none_installed(self, tmp_path: Path) -> None:
        """`claude plugin install optimus@optimus --scope user` runs ONCE — no
        per-skill installs — when nothing is installed yet, regardless of how
        many bare names the marketplace contains.
        """
        log = _install_claude_mock(tmp_path, installed_plugins=[])
        _create_claude_marketplace_cache(tmp_path, ["alpha", "beta"])
        result = _run_sync(tmp_path, exclude_droid=True,
                           env_extra=self._claude_only_env(tmp_path))
        assert result.returncode == 0
        assert "── Claude Code ──" in result.stdout
        assert "Added: 1" in result.stdout
        assert "+ optimus ... OK" in result.stdout
        log_content = log.read_text()
        assert "plugin install optimus@optimus --scope user" in log_content
        # No per-skill installs.
        assert "plugin install optimus-alpha@optimus" not in log_content
        assert "plugin install optimus-beta@optimus" not in log_content

    def test_updates_existing_optimus_plugin(self, tmp_path: Path) -> None:
        """When `optimus@optimus` is already installed, the script issues
        `plugin uninstall` + `plugin install` to force-refresh the cache.

        Rationale: `claude plugin update` is a no-op when marketplace.json's
        `version` field hasn't changed, even if the underlying source files
        have. Optimus ships SKILL changes without bumping the marketplace
        version on every PR, so update would leave users on stale cached
        SKILL.md. Uninstall + reinstall guarantees a fresh fetch.
        """
        installed = [
            {"id": "optimus@optimus", "version": "2.0.0", "scope": "user",
             "enabled": True},
        ]
        log = _install_claude_mock(tmp_path, installed_plugins=installed)
        _create_claude_marketplace_cache(tmp_path, ["alpha"])
        result = _run_sync(tmp_path, exclude_droid=True,
                           env_extra=self._claude_only_env(tmp_path))
        assert result.returncode == 0
        assert "Updated: 1" in result.stdout
        assert "* optimus ... OK (refreshed)" in result.stdout
        log_content = log.read_text()
        assert "plugin uninstall optimus@optimus" in log_content
        assert "plugin install optimus@optimus" in log_content
        # Confirm uninstall happens BEFORE install in the call order.
        assert log_content.find("plugin uninstall optimus@optimus") < log_content.find(
            "plugin install optimus@optimus"
        )
        # Update is no longer used for refresh.
        assert "plugin update optimus@optimus" not in log_content

    def test_uninstalls_legacy_per_skill_plugins(self, tmp_path: Path) -> None:
        """Pre-2.0 `optimus-<name>@optimus` installs are pruned as legacy.
        The single `optimus@optimus` plugin is installed in the same run."""
        installed = [
            {"id": "optimus-alpha@optimus", "version": "1.0.0", "scope": "user",
             "enabled": True},
            {"id": "optimus-beta@optimus", "version": "1.0.0", "scope": "user",
             "enabled": True},
        ]
        log = _install_claude_mock(tmp_path, installed_plugins=installed)
        _create_claude_marketplace_cache(tmp_path, ["alpha"])
        result = _run_sync(tmp_path, exclude_droid=True,
                           env_extra=self._claude_only_env(tmp_path))
        assert result.returncode == 0
        assert "Added: 1" in result.stdout, (
            "single optimus@optimus install should bump Added to 1"
        )
        assert "Removed: 2" in result.stdout
        assert "- optimus-alpha (legacy) ... OK" in result.stdout
        assert "- optimus-beta (legacy) ... OK" in result.stdout
        log_content = log.read_text()
        assert "plugin uninstall optimus-alpha@optimus" in log_content
        assert "plugin uninstall optimus-beta@optimus" in log_content
        assert "plugin install optimus@optimus --scope user" in log_content

    def test_install_failure_increments_failed_count(self, tmp_path: Path) -> None:
        """When `claude plugin install optimus@optimus` exits non-zero,
        summary shows Failed > 0 and the failing line has the `+ optimus ...
        FAIL` form."""
        log = _install_claude_mock(tmp_path, installed_plugins=[], install_exit=1)
        _create_claude_marketplace_cache(tmp_path, ["alpha"])
        result = _run_sync(tmp_path, exclude_droid=True,
                           env_extra=self._claude_only_env(tmp_path))
        assert result.returncode == 1
        assert "Claude Code — Added: 0" in result.stdout
        assert "Failed: 1" in result.stdout
        assert "+ optimus ... FAIL" in result.stdout
        # Install was still attempted (logged) before failing.
        assert "plugin install optimus@optimus" in log.read_text()

    def test_update_failure_increments_failed_count(self, tmp_path: Path) -> None:
        """A failing reinstall (during the force-refresh path) is reported as FAIL.

        The Claude branch refreshes via uninstall + install (see
        test_updates_existing_optimus_plugin). When the install half fails,
        the summary surfaces it as FAIL on the optimus line.
        """
        installed = [
            {"id": "optimus@optimus", "version": "2.0.0", "scope": "user",
             "enabled": True},
        ]
        _install_claude_mock(tmp_path, installed_plugins=installed, install_exit=1)
        _create_claude_marketplace_cache(tmp_path, ["alpha"])
        result = _run_sync(tmp_path, exclude_droid=True,
                           env_extra=self._claude_only_env(tmp_path))
        assert result.returncode == 1
        assert "Failed: 1" in result.stdout
        assert "* optimus ... FAIL (reinstall)" in result.stdout

    def test_uninstall_failure_increments_failed_count(self, tmp_path: Path) -> None:
        """A failing `claude plugin uninstall <legacy>@optimus` is reported as FAIL."""
        installed = [
            {"id": "optimus@optimus", "version": "2.0.0", "scope": "user",
             "enabled": True},
            {"id": "optimus-orphan@optimus", "version": "1.0.0", "scope": "user",
             "enabled": True},
        ]
        _install_claude_mock(tmp_path, installed_plugins=installed, uninstall_exit=1)
        _create_claude_marketplace_cache(tmp_path, ["alpha"])
        result = _run_sync(tmp_path, exclude_droid=True,
                           env_extra=self._claude_only_env(tmp_path))
        # optimus updates OK, legacy orphan uninstall FAILs → exit 1.
        assert result.returncode == 1
        assert "Updated: 1" in result.stdout
        assert "Failed: 1" in result.stdout
        assert "- optimus-orphan (legacy) ... FAIL" in result.stdout

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
        assert "plugin install optimus@optimus" in log.read_text()

    def test_summary_uses_added_updated_removed_failed_format(self, tmp_path: Path) -> None:
        """Claude Code summary line matches Droid's format (no `Unchanged` field)."""
        installed = [
            {"id": "optimus@optimus", "version": "2.0.0", "scope": "user",
             "enabled": True},
            {"id": "optimus-legacy@optimus", "version": "1.0.0", "scope": "user",
             "enabled": True},
        ]
        _install_claude_mock(tmp_path, installed_plugins=installed)
        _create_claude_marketplace_cache(tmp_path, ["alpha", "beta"])
        result = _run_sync(tmp_path, exclude_droid=True,
                           env_extra=self._claude_only_env(tmp_path))
        assert result.returncode == 0
        # optimus@optimus already installed -> Updated 1; one legacy entry pruned.
        assert "Claude Code — Added: 0 | Updated: 1 | Removed: 1 | Failed: 0" in result.stdout
        assert "Unchanged" not in result.stdout

    def test_filters_non_optimus_marketplace_plugins(self, tmp_path: Path) -> None:
        """Plugins from other marketplaces (not @optimus) are ignored even when
        installed alongside the optimus plugin."""
        installed = [
            {"id": "optimus@optimus", "version": "2.0.0", "scope": "user"},
            {"id": "ring:reviewer@ring", "version": "2.0.0", "scope": "user"},
            {"id": "vendor-tool@other", "version": "1.0.0", "scope": "user"},
        ]
        log = _install_claude_mock(tmp_path, installed_plugins=installed)
        _create_claude_marketplace_cache(tmp_path, ["alpha"])
        result = _run_sync(tmp_path, exclude_droid=True,
                           env_extra=self._claude_only_env(tmp_path))
        assert result.returncode == 0
        # optimus@optimus already present -> Updated; other marketplaces untouched.
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
        # Claude installed the SINGLE optimus plugin (not per-skill).
        claude_content = claude_log.read_text()
        assert "plugin install optimus@optimus --scope user" in claude_content
        assert "plugin install optimus-alpha@optimus" not in claude_content
        assert "plugin install optimus-beta@optimus" not in claude_content

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
        assert "plugin install optimus@optimus --scope user" in log.read_text()

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
        # Claude install of the single plugin was attempted.
        assert "plugin install optimus@optimus --scope user" in claude_log.read_text()
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
        """Source 2 (CLAUDE_MARKETPLACE_FILE) is used when Source 1 is absent
        and the resolver is exercised. The EXPECTED list is consumed by the
        Droid branch only, so the visible effect on a Claude-only run is the
        single `optimus@optimus` install — but the resolver still has to
        succeed (otherwise the script aborts before reaching the Claude branch).
        """
        _install_claude_mock(tmp_path, installed_plugins=[])
        # No droid binary, no Source 1.
        mp_path = _create_claude_marketplace_cache(tmp_path, ["fromsrc2"])
        # isolated=True so Source 3 cannot satisfy from the optimus repo root.
        result = _run_sync(tmp_path, exclude_droid=True, isolated=True,
                           env_extra={"CLAUDE_MARKETPLACE_FILE": str(mp_path)})
        assert result.returncode == 0
        # Single optimus plugin installed (proves the Source-2 resolver
        # succeeded — without it the script would abort with an error).
        assert "+ optimus ... OK" in result.stdout

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
        """Source 3 fallback: in-repo `.claude-plugin/marketplace.json` is
        consulted when `.factory-plugin/marketplace.json` is absent. The
        EXPECTED list is consumed by the Droid branch only — for a Claude-
        only run the visible effect is just the single `optimus@optimus`
        install, but the resolver must still succeed."""
        _install_claude_mock(tmp_path, installed_plugins=[])
        fake_repo = tmp_path / "fake_repo"
        (fake_repo / "sync" / "scripts").mkdir(parents=True)
        (fake_repo / ".claude-plugin").mkdir(parents=True)
        shutil.copy2(SCRIPT, fake_repo / "sync" / "scripts" / "sync-user-plugins.sh")
        (fake_repo / "AGENTS.md").write_text("# AGENTS")
        # The new Claude marketplace has a single `optimus` entry (no prefix).
        (fake_repo / ".claude-plugin" / "marketplace.json").write_text(json.dumps({
            "name": "optimus",
            "owner": {"name": "T", "email": "t@e"},
            "metadata": {"description": "x"},
            "plugins": [{"name": "optimus", "source": ".",
                         "version": "2.0.0", "description": "x"}],
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
        # Single optimus plugin installed (proves the Source-3 resolver
        # succeeded).
        assert "+ optimus ... OK" in result.stdout

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
# Claude timeout / retry / marketplace name validation (F4)
# ═══════════════════════════════════════════════════════════════════════════════

class TestClaudeTimeout:
    def test_claude_helper_uses_timeout(self) -> None:
        """`_claude()` must exist and reference OPTIMUS_CLAUDE_TIMEOUT (or its
        normalized CLAUDE_TIMEOUT constant)."""
        content = SCRIPT.read_text()
        assert "_claude()" in content, "missing _claude() helper"
        # Either the env var or the readonly that derives from it must appear
        # in the helper's vicinity.
        helper_idx = content.index("_claude()")
        snippet = content[helper_idx:helper_idx + 600]
        assert "CLAUDE_TIMEOUT" in snippet, (
            "_claude() should reference CLAUDE_TIMEOUT"
        )

    def test_claude_calls_route_through_helper(self) -> None:
        """No bare `claude plugin` call sites should remain outside the
        `_claude()` definition (comments and error-message hints excluded)."""
        # Strip comments and string literals before scanning.
        offending: list[str] = []
        for lineno, line in enumerate(SCRIPT.read_text().splitlines(), start=1):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            # Allow user-facing hint lines that emit `claude plugin marketplace add` to stderr.
            if "echo " in stripped:
                continue
            # Match standalone `claude plugin ...` invocations (not `_claude`,
            # not `claude_` substring inside another identifier).
            # The (?<![_A-Za-z]) lookbehind avoids matching `_claude plugin` and
            # the `b` boundary on the right side avoids `claude_xyz`.
            import re
            if re.search(r"(?<![_A-Za-z])claude\s+plugin\b", stripped):
                offending.append(f"{lineno}: {line}")
        assert not offending, (
            "Bare `claude plugin` call sites must route through `_claude`:\n"
            + "\n".join(offending)
        )

    def test_invalid_OPTIMUS_CLAUDE_TIMEOUT_rejected(self, tmp_path: Path) -> None:
        """Non-numeric OPTIMUS_CLAUDE_TIMEOUT should fail validation."""
        _install_claude_mock(tmp_path, installed_plugins=[])
        _create_claude_marketplace_cache(tmp_path, ["alpha"])
        result = _run_sync(tmp_path, exclude_droid=True, env_extra={
            "OPTIMUS_CLAUDE_TIMEOUT": "abc",
            "CLAUDE_MARKETPLACE_FILE": str(
                tmp_path / "home" / ".claude" / "plugins" / "marketplaces"
                / "optimus" / ".claude-plugin" / "marketplace.json"),
        })
        assert result.returncode == 1
        assert "OPTIMUS_CLAUDE_TIMEOUT" in result.stderr
        assert "positive integer" in result.stderr

    def test_zero_OPTIMUS_CLAUDE_TIMEOUT_rejected(self, tmp_path: Path) -> None:
        _install_claude_mock(tmp_path, installed_plugins=[])
        _create_claude_marketplace_cache(tmp_path, ["alpha"])
        result = _run_sync(tmp_path, exclude_droid=True, env_extra={
            "OPTIMUS_CLAUDE_TIMEOUT": "0",
            "CLAUDE_MARKETPLACE_FILE": str(
                tmp_path / "home" / ".claude" / "plugins" / "marketplaces"
                / "optimus" / ".claude-plugin" / "marketplace.json"),
        })
        assert result.returncode == 1
        assert "OPTIMUS_CLAUDE_TIMEOUT" in result.stderr


class TestClaudeRetry:
    def test_claude_retry_helper_present(self) -> None:
        """`_claude_retry_once()` helper must exist in the script."""
        content = SCRIPT.read_text()
        assert "_claude_retry_once()" in content, (
            "missing _claude_retry_once() helper"
        )

    def test_claude_install_retries_on_transient_failure(self, tmp_path: Path) -> None:
        """A claude plugin install that fails the first time then succeeds on
        the second attempt should still report success and log the retry."""
        log = tmp_path / "claude.log"
        state_dir = tmp_path / "state"
        state_dir.mkdir()
        # Mock claude that fails the first install attempt then succeeds.
        json_out = json.dumps([])
        log_q = shlex.quote(str(log))
        state_q = shlex.quote(str(state_dir))
        script = f"""
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
  "plugin install")
    count_file={state_q}/install.count
    count=$(cat "$count_file" 2>/dev/null || echo 0)
    count=$((count + 1))
    echo "$count" > "$count_file"
    if [ "$count" -eq 1 ]; then exit 1; fi
    exit 0
    ;;
  "plugin update") exit 0 ;;
  "plugin uninstall") exit 0 ;;
  "plugin marketplace") exit 0 ;;
esac
exit 0
"""
        _create_mock_bin(tmp_path, "claude", script)
        _create_claude_marketplace_cache(tmp_path, ["alpha"])
        result = _run_sync(tmp_path, exclude_droid=True, env_extra={
            "CLAUDE_MARKETPLACE_FILE": str(
                tmp_path / "home" / ".claude" / "plugins" / "marketplaces"
                / "optimus" / ".claude-plugin" / "marketplace.json"),
        })
        assert result.returncode == 0, (
            f"stderr={result.stderr}\nstdout={result.stdout}"
        )
        assert "+ optimus ... OK" in result.stdout
        assert "retrying once" in result.stderr
        # Two install attempts must be logged.
        log_content = log.read_text()
        # `plugin install optimus@optimus --scope user` fires twice.
        assert log_content.count("plugin install optimus@optimus --scope user") == 2


class TestMarketplaceNameValidation:
    def test_invalid_OPTIMUS_MARKETPLACE_NAME_rejected(self, tmp_path: Path) -> None:
        """Path-traversal-like marketplace names must be rejected."""
        log = tmp_path / "droid.log"
        _create_mock_bin(tmp_path, "droid", _droid_script(log))
        result = _run_sync(tmp_path, exclude_claude=True, env_extra={
            "OPTIMUS_MARKETPLACE_NAME": "../etc",
        })
        assert result.returncode == 1
        assert "OPTIMUS_MARKETPLACE_NAME" in result.stderr

    def test_uppercase_OPTIMUS_MARKETPLACE_NAME_rejected(self, tmp_path: Path) -> None:
        """Uppercase letters in marketplace names violate the contract."""
        log = tmp_path / "droid.log"
        _create_mock_bin(tmp_path, "droid", _droid_script(log))
        result = _run_sync(tmp_path, exclude_claude=True, env_extra={
            "OPTIMUS_MARKETPLACE_NAME": "Optimus",
        })
        assert result.returncode == 1
        assert "OPTIMUS_MARKETPLACE_NAME" in result.stderr


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


# ═══════════════════════════════════════════════════════════════════════════════
# F5 — Bash hygiene refactors
# ═══════════════════════════════════════════════════════════════════════════════
#
# The next three test classes exercise the F5 refactors directly, sourcing the
# shell helpers via a small `bash -c` wrapper that pulls in the same script
# under test (read into a temp file with the bottom main-body stripped).

# Helper to source the script's helper definitions only (everything above the
# main "=== Optimus Plugin Sync ===" banner). This avoids running the actual
# sync logic — we only want the function definitions in scope.
_HELPERS_HEADER_BOUNDARY = "echo \"=== Optimus Plugin Sync ===\""


def _helpers_only_script(tmp_path: Path) -> Path:
    """Write a copy of the sync script truncated just before the main body so
    only function/constant definitions are sourced. Required env (HOME,
    OPTIMUS_MARKETPLACE_NAME, etc.) is set by the caller.
    """
    full = SCRIPT.read_text()
    idx = full.index(_HELPERS_HEADER_BOUNDARY)
    helpers = full[:idx]
    # Trim the trailing comment delimiter line if present.
    helpers_path = tmp_path / "helpers.sh"
    helpers_path.write_text(helpers)
    return helpers_path


def _bash_eval(tmp_path: Path, snippet: str, env_extra: dict[str, str] | None = None,
               extra_path_dirs: list[Path] | None = None) -> subprocess.CompletedProcess:
    """Source the helpers and run an arbitrary bash snippet. Returns the
    CompletedProcess so tests can assert on stdout/stderr/returncode.

    Helpers run with HAS_DROID/HAS_CLAUDE_CODE detection guarded; we set HOME
    and PATH so the script's top-of-file validation succeeds (a `droid` mock
    is installed in tmp_path/bin so HAS_DROID=true).
    """
    helpers = _helpers_only_script(tmp_path)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    # Provide a no-op droid so HAS_DROID=true and validation passes.
    if not (bin_dir / "droid").exists():
        (bin_dir / "droid").write_text("#!/bin/bash\nexit 0\n")
        (bin_dir / "droid").chmod(0o755)
    # Provide jq if missing (system jq is fine; otherwise stub).
    if not shutil.which("jq") and not (bin_dir / "jq").exists():
        (bin_dir / "jq").write_text("#!/bin/bash\nexit 0\n")
        (bin_dir / "jq").chmod(0o755)
    env = os.environ.copy()
    extras = [str(bin_dir)]
    if extra_path_dirs:
        extras = [str(d) for d in extra_path_dirs] + extras
    env["PATH"] = ":".join([*extras, env.get("PATH", "/usr/bin:/bin")])
    env["HOME"] = str(tmp_path / "home")
    (tmp_path / "home").mkdir(exist_ok=True)
    if env_extra:
        env.update(env_extra)
    full_script = f"source {shlex.quote(str(helpers))}\n{snippet}\n"
    return subprocess.run(
        [BASH, "-c", full_script],
        capture_output=True,
        text=True,
        env=env,
        timeout=15,
    )


class TestComputeDiffsEval:
    """`_compute_diffs` prints three NAME=value lines to stdout that the caller
    consumes via `eval`. No globals are mutated."""

    def test_compute_diffs_outputs_three_kv_lines(self, tmp_path: Path) -> None:
        """Stdout should contain NEW_PLUGINS=, ORPHANED_PLUGINS=, EXISTING_PLUGINS=."""
        snippet = (
            'expected=$(printf "alpha\\nbeta\\ngamma")\n'
            'installed=$(printf "beta\\nzulu")\n'
            '_compute_diffs "$expected" "$installed"\n'
        )
        result = _bash_eval(tmp_path, snippet)
        assert result.returncode == 0, f"stderr: {result.stderr}"
        assert "NEW_PLUGINS=" in result.stdout
        assert "ORPHANED_PLUGINS=" in result.stdout
        assert "EXISTING_PLUGINS=" in result.stdout

    def test_compute_diffs_eval_works_in_caller(self, tmp_path: Path) -> None:
        """`eval "$(_compute_diffs ...)"` populates the three vars correctly."""
        snippet = (
            'expected=$(printf "alpha\\nbeta\\ngamma")\n'
            'installed=$(printf "beta\\nzulu")\n'
            'eval "$(_compute_diffs "$expected" "$installed")"\n'
            # Iterate each multiline var with a stable per-line tag so the
            # Python side can assert on grouped entries without parsing
            # bash quote escapes.
            'while IFS= read -r p; do [ -n "$p" ] && echo "NEW_ITEM=$p"; done <<< "$NEW_PLUGINS"\n'
            'while IFS= read -r p; do [ -n "$p" ] && echo "ORPH_ITEM=$p"; done <<< "$ORPHANED_PLUGINS"\n'
            'while IFS= read -r p; do [ -n "$p" ] && echo "EXIST_ITEM=$p"; done <<< "$EXISTING_PLUGINS"\n'
        )
        result = _bash_eval(tmp_path, snippet)
        assert result.returncode == 0, f"stderr: {result.stderr}"
        # alpha and gamma are NEW; zulu is ORPHANED; beta is EXISTING.
        assert "NEW_ITEM=alpha" in result.stdout
        assert "NEW_ITEM=gamma" in result.stdout
        assert "ORPH_ITEM=zulu" in result.stdout
        assert "EXIST_ITEM=beta" in result.stdout
        # Cross-bucket sanity.
        assert "NEW_ITEM=beta" not in result.stdout
        assert "ORPH_ITEM=alpha" not in result.stdout
        assert "EXIST_ITEM=zulu" not in result.stdout

    def test_compute_diffs_empty_expected_returns_error(self, tmp_path: Path) -> None:
        """An empty expected list is a programmer bug — error and non-zero exit."""
        snippet = (
            'set +e\n'
            '_compute_diffs "" "alpha"\n'
            'echo "rc=$?"\n'
        )
        result = _bash_eval(tmp_path, snippet)
        # Helper itself returns 1; the snippet captures the rc.
        assert "rc=1" in result.stdout
        assert "BUG: _compute_diffs called with empty expected list" in result.stderr

    def test_compute_diffs_empty_installed_marks_all_as_new(self, tmp_path: Path) -> None:
        """When installed="" — first-run case — every expected entry is NEW."""
        snippet = (
            'expected=$(printf "alpha\\nbeta")\n'
            'eval "$(_compute_diffs "$expected" "")"\n'
            # Use a delimiter so multiline values stay grouped; iterate via
            # bash to print one entry per line in a stable form.
            'while IFS= read -r p; do echo "NEW_ITEM=$p"; done <<< "$NEW_PLUGINS"\n'
            'echo "ORPH=[$ORPHANED_PLUGINS]"\n'
            'echo "EXIST=[$EXISTING_PLUGINS]"\n'
        )
        result = _bash_eval(tmp_path, snippet)
        assert result.returncode == 0, f"stderr: {result.stderr}"
        # Both expected entries must appear as NEW_ITEMs.
        assert "NEW_ITEM=alpha" in result.stdout
        assert "NEW_ITEM=beta" in result.stdout
        # ORPH and EXIST must be empty.
        assert "ORPH=[]" in result.stdout
        assert "EXIST=[]" in result.stdout


class TestReadResult:
    """`_read_result` returns the file's first line, or sentinels for missing/
    unreadable inputs."""

    def test_read_result_returns_token_for_existing_file(self, tmp_path: Path) -> None:
        target = tmp_path / "result"
        target.write_text("OK\n")
        snippet = f'_read_result {shlex.quote(str(target))}\n'
        result = _bash_eval(tmp_path, snippet)
        assert result.returncode == 0
        assert result.stdout.strip() == "OK"

    def test_read_result_returns_MISSING_for_nonexistent(self, tmp_path: Path) -> None:
        missing = tmp_path / "does_not_exist"
        snippet = f'_read_result {shlex.quote(str(missing))}\n'
        result = _bash_eval(tmp_path, snippet)
        assert result.returncode == 0
        assert result.stdout.strip() == "MISSING"

    def test_read_result_returns_empty_for_empty_file(self, tmp_path: Path) -> None:
        empty = tmp_path / "empty"
        empty.write_text("")
        snippet = f'_read_result {shlex.quote(str(empty))}\n'
        result = _bash_eval(tmp_path, snippet)
        assert result.returncode == 0
        # Empty file: read returns non-zero (EOF immediately) but file is
        # readable, so helper emits empty token.
        assert result.stdout.strip() == ""

    def test_read_result_uses_no_fork(self) -> None:
        """`_read_result` body must not invoke `cat` (no-fork hygiene)."""
        content = SCRIPT.read_text()
        # Find the function body between `_read_result()` definition and the
        # closing brace at column 0 ("\n}").
        idx = content.index("_read_result()")
        # Slice out roughly 800 characters of definition; sufficient for the
        # whole function body.
        body_window = content[idx:idx + 800]
        # The body should NOT contain `cat "$file"` or similar.
        assert "cat " not in body_window or 'cat "$file"' not in body_window, (
            "_read_result must use bash builtin `read`, not `cat`"
        )
        # Stronger assertion: literal "cat " must not appear in the helper.
        body_end = body_window.index("\n}")
        body = body_window[:body_end]
        assert "cat " not in body, (
            f"_read_result body must not invoke `cat`; got:\n{body}"
        )


class TestPluginListPipelineParsing:
    """The `_droid plugin list` pipeline collapses to a single awk that strips
    the `@MARKETPLACE_NAME` suffix and emits bare names."""

    def test_plugin_list_strips_marketplace_suffix(self, tmp_path: Path) -> None:
        """Feed mock `_droid plugin list` output with `@optimus` suffix; the
        Droid sync branch should see bare names in `installed`."""
        log = tmp_path / "droid.log"
        # `plugin list` emits @optimus rows plus a row from a different
        # marketplace that must be filtered out by the awk pipeline. (Header
        # rows starting with uppercase letters are also filtered, but the
        # mock keeps the row set tight to keep assertions deterministic.)
        list_output = (
            "alpha@optimus  installed\n"
            "beta@optimus  installed\n"
            "ringthing@ring  installed"
        )
        _create_mock_bin(tmp_path, "droid", _droid_script(
            log, list_output=list_output))
        # Marketplace expects only "alpha" — beta is orphaned, ringthing
        # ignored.
        _create_marketplace(tmp_path, ["alpha"])
        result = _run_sync(tmp_path, exclude_claude=True)
        assert result.returncode == 0, (
            f"stderr: {result.stderr}\nstdout: {result.stdout}"
        )
        # alpha is updated (it's in both expected and installed).
        assert "Updated: 1" in result.stdout
        # beta is removed (in installed but not in expected).
        assert "Removed: 1" in result.stdout
        # ringthing was filtered (different marketplace), so no removal for it.
        log_content = log.read_text()
        assert "uninstall ringthing" not in log_content
        assert "uninstall beta@optimus" in log_content
