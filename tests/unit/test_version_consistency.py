"""Tests for version string consistency across pyproject.toml, __init__.py and CLI."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

if sys.version_info >= (3, 11):
    import tomllib
else:  # py3.10 compat
    import tomli as tomllib  # type: ignore[no-redef,import-not-found]

REPO_ROOT = Path(__file__).parent.parent.parent
PYPROJECT = REPO_ROOT / "pyproject.toml"
INIT_PY = REPO_ROOT / "src" / "autodev" / "__init__.py"


def _pyproject_version() -> str:
    with PYPROJECT.open("rb") as f:
        data = tomllib.load(f)
    return data["project"]["version"]


def test_pyproject_version_starts_with_010() -> None:
    """pyproject.toml version must start with 0.1.0."""
    v = _pyproject_version()
    assert v.startswith("0.1.0"), f"Expected version starting with '0.1.0', got {v!r}"


def test_init_py_defines_version() -> None:
    """src/autodev/__init__.py must define __version__."""
    source = INIT_PY.read_text(encoding="utf-8")
    assert "__version__" in source, "__version__ not found in __init__.py"


def test_package_version_matches_metadata() -> None:
    """__version__ from the package must equal importlib.metadata version."""
    from importlib.metadata import version as _v

    import autodev

    metadata_ver = _v("autodev-ai")
    assert autodev.__version__ == metadata_ver, (
        f"autodev.__version__ {autodev.__version__!r} != metadata {metadata_ver!r}"
    )


def test_autodev_version_cli_output() -> None:
    """autodev --version must output the current version string."""
    result = subprocess.run(
        [sys.executable, "-m", "autodev.cli", "--version"],
        capture_output=True,
        text=True,
    )
    import autodev

    assert autodev.__version__ in result.stdout, (
        f"version {autodev.__version__!r} not in CLI output: {result.stdout!r}"
    )


def test_python_m_autodev_cli_version() -> None:
    """python -m autodev.cli --version must output the current version string."""
    result = subprocess.run(
        [sys.executable, "-m", "autodev.cli", "--version"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"CLI exited with {result.returncode}: {result.stderr}"
    from importlib.metadata import version as _v

    v = _v("autodev-ai")
    assert v in result.stdout, f"version {v!r} not in output: {result.stdout!r}"
