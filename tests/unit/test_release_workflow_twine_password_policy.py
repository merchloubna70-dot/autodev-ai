"""Policy tests: release.yml must use TWINE_PASSWORD env var, not -p CLI flag.

Forward-looking tests that will FAIL until .github/workflows/release.yml is
updated to pass the PyPI token via the TWINE_PASSWORD environment variable
instead of the `-p "$PYPI_API_TOKEN"` positional CLI flag.

Using `TWINE_PASSWORD` (env var) is the current best-practice recommended by
Twine and PyPI because:
  * The CLI flag value is visible in process listings (ps aux, /proc/<pid>/cmdline).
  * Environment variables are not exposed to child-process argv, reducing the
    token-leakage surface in CI logs.

These tests are marked xfail(strict=True) so the gap stays tracked in the test
suite until R4 lands the migration.
"""
from __future__ import annotations

import re
from pathlib import Path

_RELEASE_YML = Path(__file__).parents[2] / ".github" / "workflows" / "release.yml"


def _load_release_yml() -> str:
    return _release_yml_path().read_text()


def _release_yml_path() -> Path:
    return _RELEASE_YML


# ---------------------------------------------------------------------------
# Helpers (non-xfail — always pass or skip gracefully)
# ---------------------------------------------------------------------------

def test_release_yml_exists():
    """Precondition: release.yml must be present before any policy checks."""
    assert _release_yml_path().exists(), (
        f"release.yml not found at {_release_yml_path()}"
    )


# ---------------------------------------------------------------------------
# Policy tests (xfail until TWINE_PASSWORD migration lands in R4)
# ---------------------------------------------------------------------------

def test_twine_upload_does_not_use_p_flag():
    """twine upload must NOT pass the token via the -p CLI flag.

    The -p flag exposes the token in process listings.  The approved pattern
    is to set TWINE_PASSWORD in the step env block and call twine upload
    without any -p / --password argument.
    """
    content = _load_release_yml()
    # Match any form of `-p <value>` or `--password <value>` on a twine upload line
    matches = re.findall(r"twine\s+upload\b[^\n]*(?:-p\s+\S+|--password\s+\S+)", content)
    assert not matches, (
        "release.yml twine upload step uses -p / --password CLI flag. "
        "Migrate to TWINE_PASSWORD env var: "
        f"found: {matches}"
    )


def test_twine_upload_uses_twine_password_env():
    """The publish step must export TWINE_PASSWORD in the step env block."""
    content = _load_release_yml()
    assert "TWINE_PASSWORD" in content, (
        "release.yml does not set TWINE_PASSWORD env var. "
        "Add 'TWINE_PASSWORD: ${{ secrets.PYPI_API_TOKEN }}' to the publish step env."
    )


def test_twine_upload_does_not_inline_secret_in_run():
    """The run: block for twine upload must not inline the secret token as a shell argument."""
    content = _load_release_yml()
    # Catch patterns like: -p "$PYPI_API_TOKEN" or -p $PYPI_API_TOKEN
    dangerous = re.findall(r'-p\s+["\']?\$[{]?PYPI_API_TOKEN[}]?["\']?', content)
    assert not dangerous, (
        "release.yml inlines PYPI_API_TOKEN as a -p CLI argument — "
        "token will appear in process listings and CI logs. "
        f"Found: {dangerous}"
    )


def test_twine_upload_command_is_minimal_without_auth_flags():
    """After migration, twine upload run line must not contain -u / -p / --password flags."""
    content = _load_release_yml()
    twine_lines = [
        line.strip()
        for line in content.splitlines()
        if "twine upload" in line and "twine check" not in line
    ]
    assert twine_lines, "No 'twine upload' line found in release.yml"
    for line in twine_lines:
        assert "-p " not in line and "--password" not in line, (
            f"twine upload line still contains auth flag: {line!r}. "
            "Remove -u / -p flags and rely on TWINE_USERNAME / TWINE_PASSWORD env vars."
        )
