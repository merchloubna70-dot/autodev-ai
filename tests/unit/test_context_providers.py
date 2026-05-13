"""Tests for context_providers — one test per provider."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from autodev.context_providers import (
    BaseContextProvider,
    FileTreeContextProvider,
    GitDiffContextProvider,
    RepoMapContextProvider,
    SearchContextProvider,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def py_repo(tmp_path: Path) -> Path:
    """Small Python repo used by multiple provider tests."""
    (tmp_path / "main.py").write_text(
        "def main():\n    print('hello')\n\nif __name__ == '__main__':\n    main()\n"
    )
    (tmp_path / "utils.py").write_text(
        "from main import main\ndef helper(): pass\n"
    )
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "module.py").write_text("class SubModule:\n    pass\n")
    return tmp_path


# ---------------------------------------------------------------------------
# BaseContextProvider is abstract
# ---------------------------------------------------------------------------


def test_base_provider_is_abstract() -> None:
    with pytest.raises(TypeError):
        BaseContextProvider()  # type: ignore[abstract]


# ---------------------------------------------------------------------------
# FileTreeContextProvider
# ---------------------------------------------------------------------------


def test_file_tree_provider_returns_markdown(py_repo: Path) -> None:
    provider = FileTreeContextProvider(repo_path=str(py_repo))
    output = provider.provide("some task")
    assert "```" in output
    assert "main.py" in output


def test_file_tree_provider_depth_limit(py_repo: Path) -> None:
    # With depth=1, the sub/ directory contents should not be listed
    provider = FileTreeContextProvider(repo_path=str(py_repo), max_depth=1)
    output = provider.provide("task")
    assert "sub/" in output  # directory itself visible
    # module.py is 2 levels deep → should be absent
    assert "module.py" not in output


def test_file_tree_nonexistent_repo() -> None:
    provider = FileTreeContextProvider(repo_path="/nonexistent/path/xyz")
    output = provider.provide("task")
    assert "not a directory" in output or "<!--" in output


# ---------------------------------------------------------------------------
# SearchContextProvider
# ---------------------------------------------------------------------------


def test_search_provider_finds_symbol(py_repo: Path) -> None:
    provider = SearchContextProvider(repo_path=str(py_repo))
    # Task starts with CamelCase → SearchContextProvider picks it as pattern
    output = provider.provide("SubModule helper")
    # "SubModule" is in sub/module.py; should appear in output
    assert "SubModule" in output or "module.py" in output


def test_search_provider_no_results(py_repo: Path) -> None:
    provider = SearchContextProvider(repo_path=str(py_repo))
    output = provider.provide("xyzzy_nonexistent_zork_blorple")
    assert "no results" in output.lower() or "<!--" in output


def test_search_provider_returns_string(py_repo: Path) -> None:
    provider = SearchContextProvider(repo_path=str(py_repo))
    result = provider.provide("SubModule class")
    assert isinstance(result, str)


# ---------------------------------------------------------------------------
# RepoMapContextProvider
# ---------------------------------------------------------------------------


def test_repo_map_provider_returns_table(py_repo: Path) -> None:
    provider = RepoMapContextProvider(repo_path=str(py_repo), token_budget=512)
    output = provider.provide("Improve SubModule")
    # Should be a Markdown table or comment
    assert isinstance(output, str)
    assert len(output) > 0


def test_repo_map_provider_seed_boost(py_repo: Path) -> None:
    provider = RepoMapContextProvider(repo_path=str(py_repo))
    output = provider.provide("Fix the SubModule class in the sub module")
    # sub/module.py defines SubModule — should appear in the table
    assert "module.py" in output or "SubModule" in output


# ---------------------------------------------------------------------------
# GitDiffContextProvider
# ---------------------------------------------------------------------------


def test_git_diff_provider_no_git(tmp_path: Path) -> None:
    """Non-git directory: should return a comment, not raise."""
    provider = GitDiffContextProvider(repo_path=str(tmp_path))
    output = provider.provide("any task")
    assert isinstance(output, str)
    assert "<!--" in output


def test_git_diff_provider_returns_string_on_error() -> None:
    """Even if repo_path is garbage, must return string."""
    provider = GitDiffContextProvider(repo_path="/totally/invalid/path/abc123")
    output = provider.provide("task")
    assert isinstance(output, str)
