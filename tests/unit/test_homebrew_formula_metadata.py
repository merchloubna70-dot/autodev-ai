"""Tests for Homebrew formula metadata correctness (BLOCKER-PKG-01, BLOCKER-PKG-02, BLOCKER-PKG-03)."""
import plistlib
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
FORMULA_PATH = REPO_ROOT / "packaging" / "homebrew" / "Formula" / "autodev-ai.rb"
PLIST_PATH = REPO_ROOT / "packaging" / "desktop" / "autodev-ai.app" / "Contents" / "Info.plist"

STALE_SHA256 = "744375fb1fcc6b6e02b9f6b53322999dd8486d2cdd666dd1eddb4239847a52da"


def _formula_text() -> str:
    return FORMULA_PATH.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# BLOCKER-PKG-01 / BLOCKER-PKG-02: Homebrew formula
# ---------------------------------------------------------------------------

def test_formula_file_exists():
    """Formula file must be present at its canonical path."""
    assert FORMULA_PATH.exists(), f"Formula not found at {FORMULA_PATH}"


def test_formula_homepage_uses_correct_org():
    """homepage must reference the correct GitHub org (merchloubna70-dot, not stale macworkers)."""
    text = _formula_text()
    preamble = text.split("  resource ")[0]
    homepage_match = re.search(r'^\s*homepage\s+"([^"]+)"', preamble, re.MULTILINE)
    assert homepage_match, "No homepage line found in formula preamble"
    value = homepage_match.group(1)
    assert "macworkers/autodev-ai" not in value, f"stale 'macworkers' org: {value!r}"
    assert "merchloubna70-dot" in value, f"expected 'merchloubna70-dot' org: {value!r}"


def test_formula_url_points_at_canonical_source():
    """Top-level url must point at either canonical PyPI (post-publish) or merchloubna70-dot GitHub Release (pre-publish)."""
    text = _formula_text()
    preamble = text.split("  resource ")[0]
    url_match = re.search(r'^\s*url\s+"([^"]+)"', preamble, re.MULTILINE)
    assert url_match, "No top-level url in formula preamble"
    value = url_match.group(1)
    assert "macworkers/autodev-ai" not in value, f"stale 'macworkers' org: {value!r}"
    # Post-publish: PyPI canonical; OR pre-publish: GitHub Release under correct org
    is_pypi = "files.pythonhosted.org" in value
    is_gh_release = "merchloubna70-dot/autodev-ai/releases" in value
    assert is_pypi or is_gh_release, (
        f"url must be canonical PyPI (post-publish) or merchloubna70-dot GitHub Release (pre-publish), got {value!r}"
    )


def test_formula_version_matches_pyproject_alpha_series():
    """Formula version must be in the 0.1.0a* series (matches pyproject.toml). Post-publish allows 0.1.0a2."""
    text = _formula_text()
    preamble = text.split("  resource ")[0]
    version_match = re.search(r'^\s*version\s+"([^"]+)"', preamble, re.MULTILINE)
    assert version_match, "No version line in formula preamble"
    actual = version_match.group(1)
    assert re.match(r"^0\.1\.0a\d+$", actual), (
        f"Formula version {actual!r} not in 0.1.0a* series — must match pyproject.toml current"
    )


def test_formula_sha256_is_not_stale():
    """Stale sha256 from placeholder 0.1.0 tarball must be removed."""
    text = _formula_text()
    # Find the main formula sha256 (first occurrence, before any resource blocks)
    first_sha = re.search(r'^\s*sha256\s+"([^"]+)"', text, re.MULTILINE)
    assert first_sha is not None, "No sha256 found in formula"
    actual = first_sha.group(1)
    assert actual != STALE_SHA256, (
        f"BLOCKER-PKG-02: stale sha256 {STALE_SHA256!r} still present; "
        "must be replaced with a placeholder or real PyPI hash"
    )


def test_formula_license_is_mit():
    """Formula must declare MIT license."""
    text = _formula_text()
    match = re.search(r'^\s*license\s+"([^"]+)"', text, re.MULTILINE)
    assert match is not None, "No license line found in formula"
    assert match.group(1) == "MIT", (
        f"Expected license 'MIT', got {match.group(1)!r}"
    )


def test_formula_provenance_comment_present():
    """Formula must carry a leading comment about its state: either pre-publish BLOCKED warning
    OR post-publish backfilled provenance note (R4.5 backfill from real PyPI 0.1.0a2)."""
    text = _formula_text()
    has_pre_publish_warning = "pending PyPI publish" in text or "BLOCKED for publish" in text
    has_post_publish_backfill = "Backfilled" in text and "PyPI" in text
    assert has_pre_publish_warning or has_post_publish_backfill, (
        "Formula must have either a pre-publish BLOCKED comment OR a "
        "post-publish backfill provenance note documenting state"
    )


def test_formula_sha256_placeholder_is_explicit():
    """When PyPI publish has not happened, sha256 must be a recognisable placeholder."""
    text = _formula_text()
    first_sha = re.search(r'^\s*sha256\s+"([^"]+)"', text, re.MULTILINE)
    assert first_sha is not None, "No sha256 found"
    actual = first_sha.group(1)
    # Either it is the explicit placeholder string or a 64-hex real hash
    is_placeholder = "REPLACE_WITH" in actual or "TODO" in actual or len(actual) == 0
    is_hex64 = bool(re.fullmatch(r'[0-9a-f]{64}', actual))
    assert is_placeholder or is_hex64, (
        f"sha256 {actual!r} is neither a recognisable placeholder nor a valid sha256"
    )


# ---------------------------------------------------------------------------
# BLOCKER-PKG-03: macOS .app Info.plist version
# ---------------------------------------------------------------------------

def test_plist_short_version_is_0_1_0a1():
    """CFBundleShortVersionString must be updated to 0.1.0a1."""
    assert PLIST_PATH.exists(), f"Info.plist not found at {PLIST_PATH}"
    with PLIST_PATH.open("rb") as f:
        data = plistlib.load(f)
    assert data.get("CFBundleShortVersionString") == "0.1.0a1", (
        f"BLOCKER-PKG-03: CFBundleShortVersionString is "
        f"{data.get('CFBundleShortVersionString')!r}, expected '0.1.0a1'"
    )


def test_plist_bundle_version_is_0_1_0a1():
    """CFBundleVersion must be updated to 0.1.0a1."""
    with PLIST_PATH.open("rb") as f:
        data = plistlib.load(f)
    assert data.get("CFBundleVersion") == "0.1.0a1", (
        f"BLOCKER-PKG-03: CFBundleVersion is "
        f"{data.get('CFBundleVersion')!r}, expected '0.1.0a1'"
    )


def test_plist_other_keys_intact():
    """Other Info.plist keys must remain untouched."""
    with PLIST_PATH.open("rb") as f:
        data = plistlib.load(f)
    assert data.get("CFBundleIdentifier") == "com.macworkers.autodev-ai"
    assert data.get("CFBundleExecutable") == "launcher"
    assert data.get("CFBundlePackageType") == "APPL"
