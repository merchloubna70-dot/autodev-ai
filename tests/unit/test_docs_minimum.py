"""Minimum-presence tests for the R3 documentation deliverables.

Verifies that CHANGELOG.md, docs/configuration.md, and docs/troubleshooting.md
exist, are non-trivially populated, and that README.md links to all three.
"""
from __future__ import annotations

import re
from pathlib import Path

# ---------------------------------------------------------------------------
# Repo root — resolved relative to this file's location.
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).parent.parent.parent


# ---------------------------------------------------------------------------
# 1. CHANGELOG.md exists at repo root
# ---------------------------------------------------------------------------
def test_changelog_exists() -> None:
    changelog = REPO_ROOT / "CHANGELOG.md"
    assert changelog.exists(), f"CHANGELOG.md not found at {changelog}"


# ---------------------------------------------------------------------------
# 2. CHANGELOG.md mentions 0.1.0a1
# ---------------------------------------------------------------------------
def test_changelog_mentions_alpha_release() -> None:
    changelog = REPO_ROOT / "CHANGELOG.md"
    content = changelog.read_text(encoding="utf-8")
    assert "0.1.0a1" in content, (
        "CHANGELOG.md must reference the 0.1.0a1 pre-release version"
    )


# ---------------------------------------------------------------------------
# 3. docs/configuration.md exists and is non-empty (> 500 chars)
# ---------------------------------------------------------------------------
def test_configuration_doc_exists_and_nonempty() -> None:
    cfg_doc = REPO_ROOT / "docs" / "configuration.md"
    assert cfg_doc.exists(), f"docs/configuration.md not found at {cfg_doc}"
    content = cfg_doc.read_text(encoding="utf-8")
    assert len(content) > 500, (
        f"docs/configuration.md is suspiciously short ({len(content)} chars); "
        "expected > 500 chars"
    )


# ---------------------------------------------------------------------------
# 4. docs/troubleshooting.md exists and is non-empty (> 500 chars)
# ---------------------------------------------------------------------------
def test_troubleshooting_doc_exists_and_nonempty() -> None:
    ts_doc = REPO_ROOT / "docs" / "troubleshooting.md"
    assert ts_doc.exists(), f"docs/troubleshooting.md not found at {ts_doc}"
    content = ts_doc.read_text(encoding="utf-8")
    assert len(content) > 500, (
        f"docs/troubleshooting.md is suspiciously short ({len(content)} chars); "
        "expected > 500 chars"
    )


# ---------------------------------------------------------------------------
# 5. docs/configuration.md mentions FACTORY_FORCE_MOCK and FACTORY_LOG
# ---------------------------------------------------------------------------
def test_configuration_doc_mentions_key_env_vars() -> None:
    cfg_doc = REPO_ROOT / "docs" / "configuration.md"
    content = cfg_doc.read_text(encoding="utf-8")
    assert "FACTORY_FORCE_MOCK" in content, (
        "docs/configuration.md must document the FACTORY_FORCE_MOCK env var"
    )
    assert "FACTORY_LOG" in content, (
        "docs/configuration.md must document the FACTORY_LOG env var"
    )


# ---------------------------------------------------------------------------
# 6. README.md links to CHANGELOG, configuration.md, troubleshooting.md
# ---------------------------------------------------------------------------
def _extract_md_links(text: str) -> set[str]:
    """Return the set of link targets from Markdown link syntax [text](target)."""
    return set(re.findall(r"\[.*?\]\(([^)]+)\)", text))


def test_readme_links_to_new_docs() -> None:
    readme = REPO_ROOT / "README.md"
    content = readme.read_text(encoding="utf-8")
    links = _extract_md_links(content)

    missing: list[str] = []
    for expected in ("CHANGELOG.md", "docs/configuration.md", "docs/troubleshooting.md"):
        if not any(expected in link for link in links):
            missing.append(expected)

    assert not missing, (
        f"README.md is missing links to: {missing}\n"
        f"Found links: {sorted(links)}"
    )
