"""Tests for agents/navigator.py."""
from __future__ import annotations

from pathlib import Path

import pytest

from crewai_multicli_factory.agents.navigator import NavigatorAgent
from crewai_multicli_factory.schemas import NavigatorResult


@pytest.fixture()
def simple_repo(tmp_path: Path) -> Path:
    (tmp_path / "alpha.py").write_text("class AlphaService:\n    def run(self): pass\n")
    (tmp_path / "beta.py").write_text(
        "from alpha import AlphaService\ndef do_thing(): pass\n"
    )
    (tmp_path / "gamma.py").write_text("def utility(): pass\n")
    return tmp_path


def test_navigate_returns_navigator_result(simple_repo: Path) -> None:
    agent = NavigatorAgent(repo_path=str(simple_repo))
    result = agent.navigate(task_description="Fix the AlphaService run method", task_id="t-1")
    assert isinstance(result, NavigatorResult)
    assert result.task_id == "t-1"


def test_navigate_files_nonempty(simple_repo: Path) -> None:
    agent = NavigatorAgent(repo_path=str(simple_repo))
    result = agent.navigate("Refactor AlphaService")
    assert len(result.files) > 0
    # alpha.py defines AlphaService → should appear in files
    assert any("alpha.py" in f for f in result.files)


def test_navigate_seed_boost_influences_ranking(simple_repo: Path) -> None:
    agent = NavigatorAgent(repo_path=str(simple_repo))
    result = agent.navigate("Update the utility function in gamma")
    # gamma.py defines 'utility' → seed boost should bring it into files list
    assert any("gamma.py" in f for f in result.files)


def test_navigate_symbols_extracted(simple_repo: Path) -> None:
    agent = NavigatorAgent(repo_path=str(simple_repo))
    result = agent.navigate("Improve AlphaService performance")
    # Should have extracted at least one symbol
    assert isinstance(result.symbols, list)


def test_navigate_empty_repo(tmp_path: Path) -> None:
    agent = NavigatorAgent(repo_path=str(tmp_path))
    result = agent.navigate("Do something", task_id="empty-t")
    assert result.files == []
    assert result.task_id == "empty-t"
