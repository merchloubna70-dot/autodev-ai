"""
Tests for Homebrew publish-time blocker honesty (R3-F) — UPDATED FOR POST-PUBLISH STATE.

Two valid states are accepted (formula must be in EXACTLY ONE consistently):

  A. PRE-publish (initial state, before PyPI is live):
     - sha256 = placeholder (TODO_PUBLISH_SHA256 etc.)
     - "BLOCKED for publish" comment present
     - PUBLISH_CHECKLIST.md exists

  B. POST-publish (after R4.5 backfill, current state for 0.1.0a2+):
     - sha256 = real 64-char hex hash matching canonical PyPI
     - url points at files.pythonhosted.org
     - "Backfilled" provenance comment present
     - PUBLISH_CHECKLIST.md still exists for next bump

Tests verify the formula is in one consistent state, not the other.
"""

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
FORMULA_PATH = REPO_ROOT / "packaging" / "homebrew" / "Formula" / "autodev-x.rb"
CHECKLIST_PATH = REPO_ROOT / "packaging" / "homebrew" / "PUBLISH_CHECKLIST.md"


@pytest.fixture(scope="module")
def formula_text() -> str:
    return FORMULA_PATH.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def checklist_text() -> str:
    return CHECKLIST_PATH.read_text(encoding="utf-8")


def _preamble(text: str) -> str:
    """Return formula text up to (but not including) the first `resource` block."""
    return text.split("  resource ")[0]


def _top_level_sha256(text: str) -> str | None:
    m = re.search(r'^\s*sha256\s+"([^"]+)"', _preamble(text), re.MULTILINE)
    return m.group(1) if m else None


def _formula_state(text: str) -> str:
    """Classify the formula's publish state as 'pre_publish', 'post_publish', or 'ambiguous'."""
    sha = _top_level_sha256(text) or ""
    has_placeholder = ("TODO" in sha) or ("REPLACE_WITH" in sha)
    is_real_64hex = bool(re.fullmatch(r"[0-9a-f]{64}", sha))
    has_blocked = "BLOCKED for publish" in text
    if has_placeholder and has_blocked:
        return "pre_publish"
    if is_real_64hex and not has_placeholder:
        return "post_publish"
    return "ambiguous"


# ---------------------------------------------------------------------------
# Test 1: formula sha256 is internally consistent with its declared state
# ---------------------------------------------------------------------------
def test_formula_sha256_state_is_internally_consistent(formula_text: str) -> None:
    """Top-level sha256 must be either a recognized placeholder OR a 64-char hex hash,
    consistent with the formula's declared state."""
    state = _formula_state(formula_text)
    assert state != "ambiguous", (
        f"Formula is in an ambiguous state — sha256 is neither a recognized placeholder "
        f"nor a 64-hex real hash, OR placeholder+BLOCKED comment are inconsistent. "
        f"sha256={_top_level_sha256(formula_text)!r}"
    )


# ---------------------------------------------------------------------------
# Test 2: formula provenance comment is appropriate for its state
# ---------------------------------------------------------------------------
def test_formula_provenance_comment_matches_state(formula_text: str) -> None:
    """Pre-publish state needs 'BLOCKED for publish' comment; post-publish needs 'Backfilled' comment."""
    state = _formula_state(formula_text)
    if state == "pre_publish":
        assert "BLOCKED for publish" in formula_text, (
            "Pre-publish state requires 'BLOCKED for publish' leading comment"
        )
    elif state == "post_publish":
        assert "Backfilled" in formula_text and "PyPI" in formula_text, (
            "Post-publish state requires a 'Backfilled ... from real PyPI ...' provenance comment"
        )


# ---------------------------------------------------------------------------
# Test 3: PUBLISH_CHECKLIST.md exists and contains at least 5 numbered steps
# ---------------------------------------------------------------------------
def test_publish_checklist_exists_and_has_five_steps(checklist_text: str) -> None:
    """PUBLISH_CHECKLIST.md must exist (kept for next version bump even after first publish)."""
    numbered_steps = re.findall(r"^\s*\d+\.\s+\S", checklist_text, re.MULTILINE)
    assert len(numbered_steps) >= 5, (
        f"PUBLISH_CHECKLIST.md must list at least 5 numbered steps; found {len(numbered_steps)}."
    )


# ---------------------------------------------------------------------------
# Test 4: formula URL points at canonical source (PyPI or correct GitHub org)
# ---------------------------------------------------------------------------
def test_formula_url_points_at_correct_source(formula_text: str) -> None:
    """Formula URL must point at either canonical PyPI (post-publish) or correct merchloubna70-dot GitHub Release (pre-publish)."""
    url_match = re.search(r'^\s*url\s+"([^"]+)"', _preamble(formula_text), re.MULTILINE)
    assert url_match is not None, "Formula must contain a top-level url field."
    url_value = url_match.group(1)
    assert "macworkers" not in url_value, f"Formula url must NOT reference stale 'macworkers'; got: {url_value}"

    is_pypi = "files.pythonhosted.org" in url_value
    is_gh_release = "merchloubna70-dot/autodev-x/releases" in url_value
    assert is_pypi or is_gh_release, (
        f"Formula url must point at canonical PyPI OR merchloubna70-dot GitHub Release; got: {url_value}"
    )


# ---------------------------------------------------------------------------
# Test 5: formula version is in the 0.1.0a* alpha series
# ---------------------------------------------------------------------------
def test_formula_version_in_alpha_series(formula_text: str) -> None:
    """Formula version must be in the 0.1.0a* series (matching pyproject.toml current alpha)."""
    version_match = re.search(r'^\s*version\s+"([^"]+)"', _preamble(formula_text), re.MULTILINE)
    assert version_match is not None, "Formula must contain a version field."
    actual = version_match.group(1)
    assert re.match(r"^0\.1\.0a\d+$", actual), (
        f"Formula version must match 0.1.0a* pattern; got: {actual!r}"
    )


# ---------------------------------------------------------------------------
# Test 6: PUBLISH_CHECKLIST.md references the sha256 computation step
# ---------------------------------------------------------------------------
def test_publish_checklist_mentions_sha256_computation(checklist_text: str) -> None:
    """PUBLISH_CHECKLIST.md must describe how to compute the sha256."""
    assert "sha256sum" in checklist_text or "shasum" in checklist_text, (
        "PUBLISH_CHECKLIST.md must describe computing the sha256 (via sha256sum or shasum)."
    )


# ---------------------------------------------------------------------------
# Test 7: formula state is recognized (NOT ambiguous)
# ---------------------------------------------------------------------------
def test_formula_state_is_recognized(formula_text: str) -> None:
    """Formula must be in EITHER pre-publish OR post-publish state — not ambiguous."""
    state = _formula_state(formula_text)
    assert state in ("pre_publish", "post_publish"), (
        f"Formula is in ambiguous state — neither a clean pre-publish (placeholder + BLOCKED comment) "
        f"nor a clean post-publish (real 64-hex sha256 + backfill comment). state={state!r}"
    )
