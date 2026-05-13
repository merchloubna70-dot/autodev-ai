"""Unit tests for FourStagePlanner."""
from __future__ import annotations

import pytest

from crewai_multicli_factory.planners.four_stage_planner import FourStagePlanner, _MILESTONE_ID
from crewai_multicli_factory.schemas import Language, TaskType


@pytest.fixture()
def planner() -> FourStagePlanner:
    return FourStagePlanner()


@pytest.fixture()
def tasks(planner):
    return planner.plan(
        bug_description="NullPointerException in UserService.findById",
        repo_path="/tmp/repo",
        language="python",
    )


# ---------------------------------------------------------------------------
# Basic structure
# ---------------------------------------------------------------------------


def test_returns_exactly_four_tasks(tasks):
    assert len(tasks) == 4


def test_task_ids_in_order(tasks):
    expected = [
        "BUG-T1-REPRODUCE",
        "BUG-T2-LOCATE",
        "BUG-T3-PATCH",
        "BUG-T4-VERIFY",
    ]
    assert [t.task_id for t in tasks] == expected


def test_all_tasks_belong_to_mbug1(tasks):
    for t in tasks:
        assert t.milestone_id == _MILESTONE_ID


def test_task_types(tasks):
    t1, t2, t3, t4 = tasks
    assert t1.task_type == TaskType.TEST
    assert t2.task_type == TaskType.BUGFIX
    assert t3.task_type == TaskType.BUGFIX
    assert t4.task_type == TaskType.TEST


# ---------------------------------------------------------------------------
# Dependency chain
# ---------------------------------------------------------------------------


def test_t1_has_no_dependencies(tasks):
    assert tasks[0].dependencies == []


def test_t2_depends_on_t1(tasks):
    deps = tasks[1].dependencies
    assert len(deps) == 1
    assert deps[0].depends_on_task_id == "BUG-T1-REPRODUCE"


def test_t3_depends_on_t2(tasks):
    deps = tasks[2].dependencies
    assert len(deps) == 1
    assert deps[0].depends_on_task_id == "BUG-T2-LOCATE"


def test_t4_depends_on_t3(tasks):
    deps = tasks[3].dependencies
    assert len(deps) == 1
    assert deps[0].depends_on_task_id == "BUG-T3-PATCH"


# ---------------------------------------------------------------------------
# Templates referenced / prompts populated
# ---------------------------------------------------------------------------


def test_prompts_contain_bug_description(tasks):
    for t in tasks:
        assert "NullPointerException" in t.codex_prompt


def test_prompts_contain_repo_path(tasks):
    for t in tasks:
        assert "/tmp/repo" in t.codex_prompt


def test_prompts_contain_language(tasks):
    for t in tasks:
        assert "python" in t.codex_prompt.lower()


def test_claude_prompt_equals_codex_prompt(tasks):
    for t in tasks:
        assert t.claude_prompt == t.codex_prompt


# ---------------------------------------------------------------------------
# Language coercion
# ---------------------------------------------------------------------------


def test_language_string_coerced_to_enum(planner):
    tasks = planner.plan("bug", "/repo", language="rust")
    for t in tasks:
        assert t.language == Language.RUST


def test_unknown_language_string_falls_back(planner):
    tasks = planner.plan("bug", "/repo", language="cobol")
    for t in tasks:
        assert t.language == Language.UNKNOWN


def test_language_enum_accepted(planner):
    tasks = planner.plan("bug", "/repo", language=Language.TYPESCRIPT)
    for t in tasks:
        assert t.language == Language.TYPESCRIPT
