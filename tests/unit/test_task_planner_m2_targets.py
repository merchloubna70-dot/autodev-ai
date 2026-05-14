"""Tests for TaskPlanner M2 feature task target files and layout nudge."""
from __future__ import annotations

from autodev.planners.task_planner import TaskPlanner
from autodev.schemas import ArchitectureSpec, Language, Milestone


def _make_milestones() -> list[Milestone]:
    return [
        Milestone(
            milestone_id="M2",
            title="Feature",
            objective="Feature milestone",
            acceptance_criteria=["impl done"],
            task_ids=[],
        )
    ]


def _arch() -> ArchitectureSpec:
    return ArchitectureSpec(title="test", overview="test arch")


# 1) M2 feature task with product_name="mdlines" has correct allowed_files
def test_m2_allowed_files_with_product_name():
    planner = TaskPlanner()
    tasks = planner.plan(
        milestones=_make_milestones(),
        architecture=_arch(),
        languages=[Language.PYTHON],
        product_name="mdlines",
    )
    m2_tasks = [t for t in tasks if t.milestone_id == "M2"]
    assert len(m2_tasks) == 1
    task = m2_tasks[0]
    assert "src/mdlines/core.py" in task.allowed_files
    assert "src/mdlines/cli.py" in task.allowed_files
    assert "src/mdlines/core.py" in task.target_files
    assert "src/mdlines/cli.py" in task.target_files


# 2) M2 task description contains layout nudge
def test_m2_description_contains_layout_nudge():
    planner = TaskPlanner()
    tasks = planner.plan(
        milestones=_make_milestones(),
        architecture=_arch(),
        languages=[Language.PYTHON],
        product_name="mdlines",
    )
    m2_tasks = [t for t in tasks if t.milestone_id == "M2"]
    assert len(m2_tasks) == 1
    desc = m2_tasks[0].description
    assert "Do NOT modify pyproject.toml" in desc
    assert "do NOT write code into src/__init__.py" in desc


# 3) When product_name is None, M2 task uses empty target (backward compat)
def test_m2_no_product_name_empty_target():
    planner = TaskPlanner()
    tasks = planner.plan(
        milestones=_make_milestones(),
        architecture=_arch(),
        languages=[Language.PYTHON],
        product_name=None,
    )
    m2_tasks = [t for t in tasks if t.milestone_id == "M2"]
    assert len(m2_tasks) == 1
    task = m2_tasks[0]
    assert task.allowed_files == []
    assert task.target_files == []


# 4) Hyphenated product_name produces correct slug in target paths
def test_m2_hyphenated_product_name_slug():
    planner = TaskPlanner()
    tasks = planner.plan(
        milestones=_make_milestones(),
        architecture=_arch(),
        languages=[Language.PYTHON],
        product_name="my-tool",
    )
    m2_tasks = [t for t in tasks if t.milestone_id == "M2"]
    task = m2_tasks[0]
    assert "src/my_tool/core.py" in task.allowed_files
    assert "src/my_tool/cli.py" in task.allowed_files


# 5) Non-Python M2 task (Rust) does NOT get the layout nudge even with product_name
def test_m2_rust_no_layout_nudge():
    planner = TaskPlanner()
    tasks = planner.plan(
        milestones=_make_milestones(),
        architecture=_arch(),
        languages=[Language.RUST],
        product_name="mylib",
    )
    m2_tasks = [t for t in tasks if t.milestone_id == "M2"]
    assert len(m2_tasks) == 1
    desc = m2_tasks[0].description
    assert "Do NOT modify pyproject.toml" not in desc
