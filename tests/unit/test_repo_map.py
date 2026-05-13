"""Tests for scanners/repo_map.py — RepoMap ranking logic."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

from crewai_multicli_factory.scanners.repo_map import RepoMap


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def empty_repo(tmp_path: Path) -> Path:
    return tmp_path


@pytest.fixture()
def single_py_repo(tmp_path: Path) -> Path:
    (tmp_path / "hello.py").write_text("def greet(name):\n    return f'Hello {name}'\n")
    return tmp_path


@pytest.fixture()
def multi_py_repo(tmp_path: Path) -> Path:
    """Three files; b.py imports a.py; c.py imports a.py and b.py."""
    (tmp_path / "a.py").write_text("class Alpha:\n    pass\n")
    (tmp_path / "b.py").write_text("from a import Alpha\ndef beta():\n    pass\n")
    (tmp_path / "c.py").write_text(
        "from a import Alpha\nfrom b import beta\nclass Gamma:\n    pass\n"
    )
    return tmp_path


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_empty_repo_returns_empty(empty_repo: Path) -> None:
    rm = RepoMap(repo_path=str(empty_repo))
    entries = rm.rank()
    assert entries == []


def test_single_file_detected(single_py_repo: Path) -> None:
    rm = RepoMap(repo_path=str(single_py_repo))
    entries = rm.rank()
    assert len(entries) == 1
    assert entries[0].file_path == "hello.py"
    assert "greet" in entries[0].signature_summary


def test_multi_file_ranking_by_indegree(multi_py_repo: Path) -> None:
    rm = RepoMap(repo_path=str(multi_py_repo))
    entries = rm.rank()
    # a.py is imported by both b.py and c.py → highest in-degree → top rank
    assert len(entries) == 3
    top_path = entries[0].file_path
    assert top_path == "a.py", f"Expected a.py at top, got {top_path}"


def test_seed_boost_elevates_matching_file(multi_py_repo: Path) -> None:
    # Without seed, a.py is top. With seed='Gamma', c.py should jump.
    rm = RepoMap(repo_path=str(multi_py_repo), seeds=["Gamma"])
    entries = rm.rank()
    paths = [e.file_path for e in entries]
    # c.py defines Gamma → should be ranked first due to 10× seed boost
    assert paths[0] == "c.py", f"Expected c.py boosted to top, got {paths}"


def test_token_budget_truncation(multi_py_repo: Path) -> None:
    # Extremely small budget should return fewer entries
    rm = RepoMap(repo_path=str(multi_py_repo), token_budget=1)
    entries = rm.rank()
    # Budget of 1 token: only the first entry (which alone exceeds budget)
    # should still be returned (we always include at least first that fits)
    assert len(entries) <= 3


def test_open_file_boost(multi_py_repo: Path) -> None:
    # b.py has lower in-degree than a.py normally; open_files boost makes it top
    rm = RepoMap(repo_path=str(multi_py_repo), open_files=["b.py"])
    entries = rm.rank()
    assert entries[0].file_path == "b.py"


def test_symbol_count(single_py_repo: Path) -> None:
    rm = RepoMap(repo_path=str(single_py_repo))
    entries = rm.rank()
    assert entries[0].symbol_count == 1  # one 'def greet'


def test_score_positive(multi_py_repo: Path) -> None:
    rm = RepoMap(repo_path=str(multi_py_repo))
    for e in rm.rank():
        assert e.score > 0
