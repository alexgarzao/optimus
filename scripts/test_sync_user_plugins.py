#!/usr/bin/env python3
"""Integration tests for sync-user-plugins.sh using mock commands."""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parent.parent / "help" / "scripts" / "sync-user-plugins.sh"
BASH = shutil.which("bash") or "/bin/bash"


def _create_mock_bin(tmp_path: Path, name: str, script: str) -> Path:
    """Create a mock executable in tmp_path/bin/."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    mock = bin_dir / name
    mock.write_text(f"#!/usr/bin/env bash\n{script}\n")
    mock.chmod(0o755)
    return bin_dir


def _create_marketplace(tmp_path: Path, plugins: list[str], name: str = "optimus") -> Path:
    """Create a mock marketplace JSON file at the expected path."""
    mp_dir = tmp_path / "home" / ".factory" / "marketplaces" / name / ".factory-plugin"
    mp_dir.mkdir(parents=True)
    mp_file = mp_dir / "marketplace.json"
    entries = ", ".join(f'{{"name": "{p}"}}' for p in plugins)
    mp_file.write_text(f'{{"plugins": [{entries}]}}')
    return mp_file


def _run_sync(tmp_path: Path, env_extra: dict[str, str] | None = None,
              restrict_path: bool = False) -> subprocess.CompletedProcess:
    """Run the sync script with mocked PATH and HOME."""
    env = os.environ.copy()
    bin_dir = tmp_path / "bin"
    if restrict_path:
        env["PATH"] = str(bin_dir)
    else:
        env["PATH"] = f"{bin_dir}:{env.get('PATH', '/usr/bin')}"
    env["HOME"] = str(tmp_path / "home")
    if env_extra:
        env.update(env_extra)
    return subprocess.run(
        [BASH, str(SCRIPT)],
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


class TestDependencyChecks:
    def test_fails_without_droid(self, tmp_path: Path):
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
        assert "droid CLI is required" in result.stdout

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
        assert "jq is required" in result.stdout


class TestFirstTimeInstall:
    def test_installs_all_plugins_on_first_run(self, tmp_path: Path):
        log = tmp_path / "droid.log"
        _create_mock_bin(tmp_path, "droid", _droid_script(log))
        _create_marketplace(tmp_path, ["alpha", "beta"])
        result = _run_sync(tmp_path)
        assert result.returncode == 0
        assert "Added:   2" in result.stdout
        assert "(1/2)" in result.stdout
        assert "(2/2)" in result.stdout
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
        assert "scope conflict" in result.stdout.lower()
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
        assert "Added:   1" in result.stdout


class TestErrorPaths:
    def test_fails_on_marketplace_not_found(self, tmp_path: Path):
        log = tmp_path / "droid.log"
        _create_mock_bin(tmp_path, "droid", _droid_script(log))
        (tmp_path / "home" / ".factory").mkdir(parents=True)
        result = _run_sync(tmp_path)
        assert result.returncode == 1
        assert "not found" in result.stdout.lower()

    def test_fails_on_empty_marketplace(self, tmp_path: Path):
        log = tmp_path / "droid.log"
        _create_mock_bin(tmp_path, "droid", _droid_script(log))
        mp_dir = tmp_path / "home" / ".factory" / "marketplaces" / "optimus" / ".factory-plugin"
        mp_dir.mkdir(parents=True)
        (mp_dir / "marketplace.json").write_text('{"plugins": []}')
        result = _run_sync(tmp_path)
        assert result.returncode == 1
        assert "No plugins found" in result.stdout

    def test_exits_nonzero_on_persistent_failure(self, tmp_path: Path):
        log = tmp_path / "droid.log"
        _create_mock_bin(tmp_path, "droid", _droid_script(log, install_exit=1))
        _create_marketplace(tmp_path, ["failing"])
        result = _run_sync(tmp_path)
        assert result.returncode == 1
        assert "Failed:" in result.stdout
