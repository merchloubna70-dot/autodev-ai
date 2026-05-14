"""
Integration smoke tests for the built wheel distribution.

Verifies that dist/autodev_x-0.1.0a1-py3-none-any.whl installs correctly
into a clean virtual environment and that the CLI reports the correct version.

These tests create a temporary venv, install the wheel, and invoke the CLI;
they may take up to ~30 seconds.

HIGH-DIST-01 closure tests.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
DIST_DIR = REPO_ROOT / "dist"
WHEEL_NAME = "autodev_x-0.1.0a1-py3-none-any.whl"
SDIST_NAME = "autodev_x-0.1.0a1.tar.gz"
WHEEL_PATH = DIST_DIR / WHEEL_NAME
SDIST_PATH = DIST_DIR / SDIST_NAME
EXPECTED_VERSION_STRING = "autodev-x 0.1.0a1"

pytestmark = pytest.mark.integration

# These tests are post-build smoke checks: they require `python -m build` to
# have been run first so dist/*.whl + dist/*.tar.gz exist. In CI default test
# job, no build is run, so we skip rather than fail. The release.yml workflow's
# publish job runs `python -m build` then `twine check` — the dedicated build
# verification path. These tests run if a developer ran `python -m build`
# locally OR if a CI job explicitly builds dist/ before pytest.
_DIST_PRESENT = WHEEL_PATH.exists() and SDIST_PATH.exists()
skip_if_no_dist = pytest.mark.skipif(
    not _DIST_PRESENT,
    reason="dist/*.whl + dist/*.tar.gz absent — run `python -m build` first",
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _python312() -> str | None:
    """Return the python3.12 executable path, or None if unavailable."""
    for candidate in ("python3.12", "python3.12"):
        found = shutil.which(candidate)
        if found:
            result = subprocess.run(
                [found, "--version"], capture_output=True, text=True, check=False
            )
            if result.returncode == 0 and "3.12" in result.stdout + result.stderr:
                return found
    return None


# ---------------------------------------------------------------------------
# Tests: artifact existence
# ---------------------------------------------------------------------------

@skip_if_no_dist
def test_wheel_file_exists():
    """dist/autodev_x-0.1.0a1-py3-none-any.whl must exist after build."""
    assert WHEEL_PATH.exists(), (
        f"Wheel not found at {WHEEL_PATH}. Run: python -m build"
    )


@skip_if_no_dist
def test_sdist_file_exists():
    """dist/autodev_x-0.1.0a1.tar.gz must exist after build."""
    assert SDIST_PATH.exists(), (
        f"Sdist not found at {SDIST_PATH}. Run: python -m build"
    )


# ---------------------------------------------------------------------------
# Tests: clean-venv installation
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def clean_venv():
    """
    Create a temporary virtual environment, install the wheel, yield the venv
    bin directory, then tear it down.

    Skips the entire module scope if python3.12 is unavailable.
    """
    py312 = _python312()
    if py312 is None:
        pytest.skip("python3.12 not found on PATH — skipping wheel-install smoke tests")

    if not WHEEL_PATH.exists():
        pytest.skip(f"Wheel not found at {WHEEL_PATH} — run 'python -m build' first")

    tmp = tempfile.mkdtemp(prefix="autodev-wheel-smoke-venv-")
    venv_dir = Path(tmp)
    try:
        # Create venv
        create = subprocess.run(
            [py312, "-m", "venv", str(venv_dir)],
            capture_output=True, text=True, check=False,
        )
        assert create.returncode == 0, (
            f"venv creation failed (exit {create.returncode}):\n"
            f"stdout: {create.stdout}\nstderr: {create.stderr}"
        )

        bin_dir = venv_dir / "bin"
        pip = str(bin_dir / "pip")

        # Install wheel (pip install upgrades pip silently first)
        install = subprocess.run(
            [pip, "install", "--quiet", str(WHEEL_PATH)],
            capture_output=True, text=True, check=False,
        )
        assert install.returncode == 0, (
            f"pip install wheel failed (exit {install.returncode}):\n"
            f"stdout: {install.stdout}\nstderr: {install.stderr}"
        )

        yield bin_dir

    finally:
        shutil.rmtree(tmp, ignore_errors=True)


@skip_if_no_dist
def test_wheel_installs_in_clean_venv(clean_venv):
    """
    Installing dist/autodev_x-0.1.0a1-py3-none-any.whl into a fresh
    python3.12 venv must exit 0.

    The fixture already asserts exit 0 on install; reaching this point means
    it succeeded.
    """
    assert clean_venv.exists(), "venv bin dir must exist after install"


@skip_if_no_dist
def test_wheel_autodev_help_works(clean_venv):
    """After wheel install, `autodev --help` must exit 0 and show 'Usage:'."""
    autodev_bin = str(clean_venv / "autodev")
    result = subprocess.run(
        [autodev_bin, "--help"],
        capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0, (
        f"`autodev --help` exited {result.returncode}\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )
    output = result.stdout + result.stderr
    assert "Usage:" in output, (
        f"Expected 'Usage:' in output but got:\n{output}"
    )


@skip_if_no_dist
def test_wheel_autodev_version_outputs_0_1_0a1(clean_venv):
    """
    `autodev --version` must output exactly 'autodev-x 0.1.0a1'
    (closes HIGH-DIST-01).
    """
    autodev_bin = str(clean_venv / "autodev")
    result = subprocess.run(
        [autodev_bin, "--version"],
        capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0, (
        f"`autodev --version` exited {result.returncode}\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )
    output = (result.stdout + result.stderr).strip()
    assert output == EXPECTED_VERSION_STRING, (
        f"Expected exact version string '{EXPECTED_VERSION_STRING}' but got: '{output}'"
    )


@skip_if_no_dist
def test_wheel_module_form_version_works(clean_venv):
    """
    `python -m autodev.cli --version` must also output 'autodev-x 0.1.0a1'.
    """
    python_bin = str(clean_venv / "python")
    result = subprocess.run(
        [python_bin, "-m", "autodev.cli", "--version"],
        capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0, (
        f"`python -m autodev.cli --version` exited {result.returncode}\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )
    output = (result.stdout + result.stderr).strip()
    assert output == EXPECTED_VERSION_STRING, (
        f"Expected exact version string '{EXPECTED_VERSION_STRING}' but got: '{output}'"
    )
