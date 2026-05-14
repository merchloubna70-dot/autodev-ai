"""Tests for scripts/verify_release.sh."""
from __future__ import annotations

import os
import stat
import subprocess
from pathlib import Path


def _script_path() -> Path:
    """Return the absolute path to verify_release.sh."""
    # Walk up from this file to the repo root, then into scripts/
    here = Path(__file__).resolve()
    repo_root = here.parent.parent.parent
    return repo_root / "scripts" / "verify_release.sh"


def test_script_exists() -> None:
    """scripts/verify_release.sh must exist."""
    assert _script_path().exists(), f"Script not found: {_script_path()}"


def test_script_is_executable() -> None:
    """scripts/verify_release.sh must have the executable bit set."""
    path = _script_path()
    mode = os.stat(path).st_mode
    assert mode & stat.S_IXUSR, f"Script is not user-executable: {path} (mode={oct(mode)})"


def test_script_help_exits_zero() -> None:
    """verify_release.sh --help must exit 0 without requiring cosign."""
    path = _script_path()
    result = subprocess.run(
        ["bash", str(path), "--help"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0, (
        f"--help exited {result.returncode}\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )
    assert "Usage" in result.stdout or "verify_release" in result.stdout, (
        f"Expected usage text in stdout, got: {result.stdout!r}"
    )


def test_script_no_args_exits_2() -> None:
    """verify_release.sh with no arguments must exit 2 (usage error)."""
    path = _script_path()
    result = subprocess.run(
        ["bash", str(path)],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 2, (
        f"Expected exit 2 for no-args, got {result.returncode}"
    )
