"""Tests for ConventionLoader — offline, no network, no shell."""
from __future__ import annotations

from autodev.adapters.convention_loader import ConventionLoader


def test_no_convention_files(tmp_path):
    """Returns empty RepoConventions when no convention files exist."""
    loader = ConventionLoader()
    result = loader.load(tmp_path)
    assert result.sources == []
    assert result.body == ""
    assert result.char_count == 0
    assert result.truncated is False


def test_agents_md_only(tmp_path):
    """Reads AGENTS.md and includes it with a header."""
    agents_md = tmp_path / "AGENTS.md"
    agents_md.write_text("# Agent rules\nDo not foo.", encoding="utf-8")

    loader = ConventionLoader()
    result = loader.load(tmp_path)

    assert "AGENTS.md" in result.sources
    assert "## from AGENTS.md" in result.body
    assert "Do not foo." in result.body
    assert result.char_count > 0
    assert result.truncated is False


def test_mixed_files(tmp_path):
    """Reads both AGENTS.md and CLAUDE.md; concatenates with headers."""
    (tmp_path / "AGENTS.md").write_text("agents content", encoding="utf-8")
    (tmp_path / "CLAUDE.md").write_text("claude content", encoding="utf-8")
    # Also add a .cursor/rules/*.mdc file
    cursor_dir = tmp_path / ".cursor" / "rules"
    cursor_dir.mkdir(parents=True)
    (cursor_dir / "style.mdc").write_text("style rules", encoding="utf-8")

    loader = ConventionLoader()
    result = loader.load(tmp_path)

    assert "AGENTS.md" in result.sources
    assert "CLAUDE.md" in result.sources
    assert ".cursor/rules/style.mdc" in result.sources
    assert "agents content" in result.body
    assert "claude content" in result.body
    assert "style rules" in result.body
    assert result.truncated is False


def test_truncation_when_over_budget(tmp_path):
    """Body is truncated when combined content exceeds char_budget."""
    large_text = "x" * 5000
    (tmp_path / "AGENTS.md").write_text(large_text, encoding="utf-8")
    (tmp_path / "CLAUDE.md").write_text("should not appear fully", encoding="utf-8")

    loader = ConventionLoader(char_budget=200)
    result = loader.load(tmp_path)

    assert result.truncated is True
    assert result.char_count <= 200 + len("[...truncated]") + 20  # some slack for header
    # The body should not exceed the budget significantly
    assert len(result.body) < 300


def test_cursorrules_file(tmp_path):
    """.cursorrules (no extension) is included."""
    (tmp_path / ".cursorrules").write_text("cursorrules content", encoding="utf-8")

    loader = ConventionLoader()
    result = loader.load(tmp_path)

    assert ".cursorrules" in result.sources
    assert "cursorrules content" in result.body
