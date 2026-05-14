"""
Integration test: python -m autodev.release_readiness_gate works from a wheel install.

Builds dist/autodev_x-*.whl (if not present), installs it into a fresh temp venv,
then runs `python -m autodev.release_readiness_gate` from that venv to confirm the
gate ships inside the wheel and exits 0.

This verifies the R5 fix: the implementation no longer uses a path-relative shim
that breaks in non-editable installs.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration

REPO_ROOT = Path(__file__).resolve().parents[2]
DIST_DIR = REPO_ROOT / "dist"


def _find_or_build_wheel() -> Path | None:
    """Return the first *.whl in dist/, building with `python -m build` if absent."""
    wheels = sorted(DIST_DIR.glob("autodev_x-*.whl"))
    if wheels:
        return wheels[-1]  # newest

    # Try to build — this may take ~30 s but only happens once per CI run.
    result = subprocess.run(
        [sys.executable, "-m", "build", "--wheel", "--outdir", str(DIST_DIR)],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=120,
    )
    if result.returncode != 0:
        return None  # caller will skip

    wheels = sorted(DIST_DIR.glob("autodev_x-*.whl"))
    return wheels[-1] if wheels else None


@pytest.fixture(scope="module")
def installed_venv_python():
    """
    Build the wheel (or reuse an existing one), install it into a fresh temp venv,
    and yield the path to that venv's python executable.

    Cleans up the venv after the test module finishes.
    """
    wheel = _find_or_build_wheel()
    if wheel is None:
        pytest.skip(
            "Could not find or build a wheel for autodev-x — "
            "run `python -m build` first or ensure `build` is installed."
        )

    tmp = tempfile.mkdtemp(prefix="autodev-wheel-gate-venv-")
    venv_dir = Path(tmp)
    try:
        # Create a fresh venv using the same python that runs the tests.
        create = subprocess.run(
            [sys.executable, "-m", "venv", str(venv_dir)],
            capture_output=True,
            text=True,
            check=False,
        )
        assert create.returncode == 0, (
            f"venv creation failed:\n{create.stdout}\n{create.stderr}"
        )

        venv_python = str(venv_dir / "bin" / "python")

        # Install the wheel (and its dependencies).
        install = subprocess.run(
            [venv_python, "-m", "pip", "install", "--quiet", str(wheel)],
            capture_output=True,
            text=True,
            check=False,
        )
        assert install.returncode == 0, (
            f"pip install failed:\n{install.stdout}\n{install.stderr}"
        )

        yield venv_python

    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_gate_module_exits_0_from_wheel_install(installed_venv_python, tmp_path):
    """
    `python -m autodev.release_readiness_gate` must exit 0 when invoked from a
    wheel-installed venv (no --strict, gate just reports).
    """
    out_json = str(tmp_path / "gate_wheel_test.json")
    result = subprocess.run(
        [
            installed_venv_python,
            "-m", "autodev.release_readiness_gate",
            "--repo-path", str(REPO_ROOT),
            "--output", out_json,
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )
    assert result.returncode == 0, (
        f"`python -m autodev.release_readiness_gate` exited {result.returncode}\n"
        f"stdout:\n{result.stdout[-2000:]}\nstderr:\n{result.stderr[-500:]}"
    )


def test_gate_produces_valid_json_from_wheel_install(installed_venv_python, tmp_path):
    """
    The output JSON written by the wheel-installed gate must be valid and contain
    the expected top-level keys.
    """
    out_json = tmp_path / "gate_wheel_output.json"
    subprocess.run(
        [
            installed_venv_python,
            "-m", "autodev.release_readiness_gate",
            "--repo-path", str(REPO_ROOT),
            "--output", str(out_json),
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )
    assert out_json.exists(), "Gate did not write the output JSON file"
    data = json.loads(out_json.read_text(encoding="utf-8"))
    for key in ("gate", "ran_at", "overall", "checks", "strict_pass", "summary"):
        assert key in data, f"Missing key in gate output: {key}"
    assert data["gate"] == "release_readiness"


def test_gate_runs_36_checks_from_wheel_install(installed_venv_python, tmp_path):
    """
    The wheel-installed gate must run all 36 checks (12 BASE + 12 R2 + 12 R3).
    """
    out_json = tmp_path / "gate_wheel_36checks.json"
    subprocess.run(
        [
            installed_venv_python,
            "-m", "autodev.release_readiness_gate",
            "--repo-path", str(REPO_ROOT),
            "--output", str(out_json),
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )
    assert out_json.exists(), "Gate did not write the output JSON file"
    data = json.loads(out_json.read_text(encoding="utf-8"))
    assert len(data["checks"]) == 36, (
        f"Expected 36 checks but got {len(data['checks'])}: "
        f"{[c['name'] for c in data['checks']]}"
    )
