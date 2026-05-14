"""
Tests for Homebrew publish-time blocker separation.

These tests verify that:
  - The formula is HONESTLY blocked (placeholder sha256 + explicit BLOCKED comment)
  - The PUBLISH_CHECKLIST.md exists and is adequately detailed
  - Formula metadata (URL host, version) is correct

Passing these tests means the blocker is RECORDED and HONEST.
It does NOT mean Homebrew is ready to publish.
"""

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
FORMULA_PATH = REPO_ROOT / "packaging" / "homebrew" / "Formula" / "autodev-ai.rb"
CHECKLIST_PATH = REPO_ROOT / "packaging" / "homebrew" / "PUBLISH_CHECKLIST.md"


@pytest.fixture(scope="module")
def formula_text() -> str:
    return FORMULA_PATH.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def checklist_text() -> str:
    return CHECKLIST_PATH.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Test 1: formula sha256 is still a TODO/placeholder (formula is BLOCKED)
# ---------------------------------------------------------------------------
def test_formula_sha256_is_placeholder(formula_text: str) -> None:
    """sha256 must remain a placeholder — formula must NOT be published yet."""
    # Accept either the old long placeholder or the new shorter conventional one
    placeholder_pattern = re.compile(
        r'sha256\s+"(TODO_PUBLISH_SHA256|REPLACE_WITH_PYPI_0_1_0A1_SDIST_SHA256_AT_PUBLISH_TIME)"'
    )
    match = placeholder_pattern.search(formula_text)
    assert match is not None, (
        "Formula sha256 must still be a placeholder (TODO_PUBLISH_SHA256 or equivalent). "
        "If it has been replaced with a real hash the Homebrew publish workflow should run "
        "PUBLISH_CHECKLIST.md steps in full before this test is removed."
    )


# ---------------------------------------------------------------------------
# Test 2: formula has explicit BLOCKED leading comment
# ---------------------------------------------------------------------------
def test_formula_has_blocked_comment(formula_text: str) -> None:
    """Formula header must contain the explicit BLOCKED publish comment."""
    assert "BLOCKED for publish" in formula_text, (
        "Formula must contain the comment: "
        "'This formula is BLOCKED for publish until PyPI 0.1.0a1 is live and sha256 is computed from PyPI metadata.'"
    )


# ---------------------------------------------------------------------------
# Test 3: PUBLISH_CHECKLIST.md exists and contains at least 5 numbered steps
# ---------------------------------------------------------------------------
def test_publish_checklist_exists_and_has_five_steps(checklist_text: str) -> None:
    """PUBLISH_CHECKLIST.md must exist and list at least 5 numbered steps."""
    # Count lines that start a numbered step (e.g. "1. ", "2. " …)
    numbered_steps = re.findall(r"^\s*\d+\.\s+\S", checklist_text, re.MULTILINE)
    assert len(numbered_steps) >= 5, (
        f"PUBLISH_CHECKLIST.md must list at least 5 numbered steps; found {len(numbered_steps)}."
    )


# ---------------------------------------------------------------------------
# Test 4: formula URL points at merchloubna70-dot (not macworkers)
# ---------------------------------------------------------------------------
def test_formula_url_points_at_correct_github_user(formula_text: str) -> None:
    """Formula URL must reference the 'merchloubna70-dot' GitHub account, not 'macworkers'."""
    url_line_match = re.search(r'^\s*url\s+"([^"]+)"', formula_text, re.MULTILINE)
    assert url_line_match is not None, "Formula must contain a url field."
    url_value = url_line_match.group(1)
    assert "macworkers" not in url_value, (
        f"Formula url must not reference 'macworkers'; got: {url_value}"
    )
    assert "merchloubna70-dot" in url_value, (
        f"Formula url must reference 'merchloubna70-dot'; got: {url_value}"
    )


# ---------------------------------------------------------------------------
# Test 5: formula version is 0.1.0a1
# ---------------------------------------------------------------------------
def test_formula_version_is_0_1_0a1(formula_text: str) -> None:
    """Formula version must be exactly 0.1.0a1."""
    version_match = re.search(r'^\s*version\s+"([^"]+)"', formula_text, re.MULTILINE)
    assert version_match is not None, "Formula must contain a version field."
    assert version_match.group(1) == "0.1.0a1", (
        f"Formula version must be '0.1.0a1'; got: '{version_match.group(1)}'"
    )


# ---------------------------------------------------------------------------
# Test 6 (bonus): PUBLISH_CHECKLIST.md references the pypi-sdist-url / sha256sum step
# ---------------------------------------------------------------------------
def test_publish_checklist_mentions_sha256sum(checklist_text: str) -> None:
    """PUBLISH_CHECKLIST.md must include a sha256sum computation step."""
    assert "sha256sum" in checklist_text, (
        "PUBLISH_CHECKLIST.md must describe computing the sha256 via sha256sum."
    )


# ---------------------------------------------------------------------------
# Test 7 (bonus): formula still has the original STATUS leading comment
# ---------------------------------------------------------------------------
def test_formula_has_status_pending_comment(formula_text: str) -> None:
    """Formula must retain the 'STATUS: pending PyPI publish' leading comment."""
    assert "STATUS: pending PyPI publish" in formula_text, (
        "Formula must retain the 'STATUS: pending PyPI publish' leading comment."
    )
