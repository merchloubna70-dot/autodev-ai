"""Tests for LICENSE file existence and pyproject.toml / README license metadata."""
from __future__ import annotations

import sys
from pathlib import Path

if sys.version_info >= (3, 11):
    import tomllib
else:  # py3.10 compat
    import tomli as tomllib  # type: ignore[no-redef,import-not-found]

REPO_ROOT = Path(__file__).parent.parent.parent
LICENSE_FILE = REPO_ROOT / "LICENSE"
PYPROJECT = REPO_ROOT / "pyproject.toml"
README = REPO_ROOT / "README.md"


def test_license_file_exists() -> None:
    """LICENSE file must exist at repo root."""
    assert LICENSE_FILE.exists(), f"LICENSE file not found at {LICENSE_FILE}"


def test_license_text_contains_mit_grant() -> None:
    """LICENSE text must contain canonical MIT grant phrase."""
    text = LICENSE_FILE.read_text(encoding="utf-8")
    assert "Permission is hereby granted" in text or "MIT License" in text, (
        "LICENSE does not contain 'MIT License' or 'Permission is hereby granted'"
    )


def test_pyproject_license_is_mit() -> None:
    """pyproject.toml [project] must declare MIT license."""
    with PYPROJECT.open("rb") as f:
        data = tomllib.load(f)
    project = data.get("project", {})
    # Support both { text = "MIT" } and { file = "LICENSE" } forms
    lic = project.get("license", {})
    license_files = project.get("license-files", [])
    is_mit = (isinstance(lic, dict) and "MIT" in lic.get("text", "")) or (
        isinstance(lic, str) and "MIT" in lic
    )
    has_license_file = "LICENSE" in license_files
    assert is_mit or has_license_file, (
        f"pyproject.toml does not declare MIT license; got license={lic!r}, license-files={license_files!r}"
    )


def test_readme_mentions_mit() -> None:
    """README.md must mention MIT or link to LICENSE."""
    text = README.read_text(encoding="utf-8")
    assert "MIT" in text or "LICENSE" in text, (
        "README.md does not mention MIT or LICENSE"
    )
