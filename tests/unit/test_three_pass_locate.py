"""Unit tests for the 3-pass LOCATE sub-decomposition in FourStagePlanner (W5)."""
from __future__ import annotations

from autodev.planners.four_stage_planner import (
    FourStagePlanner,
)
from autodev.schemas import TaskType

_BUG = "NullPointerException in auth module"
_REPO = "/tmp/myrepo"


class TestDefaultBehaviorPreserved:
    """Without three_pass_locate, the planner should behave identically to before."""

    def test_default_returns_four_tasks(self):
        planner = FourStagePlanner()
        tasks = planner.plan(_BUG, _REPO)
        assert len(tasks) == 4

    def test_default_task_ids(self):
        planner = FourStagePlanner()
        tasks = planner.plan(_BUG, _REPO)
        ids = [t.task_id for t in tasks]
        assert ids == ["BUG-T1-REPRODUCE", "BUG-T2-LOCATE", "BUG-T3-PATCH", "BUG-T4-VERIFY"]

    def test_default_chain_dependencies(self):
        """Each task after T1 must depend on its immediate predecessor."""
        planner = FourStagePlanner()
        tasks = planner.plan(_BUG, _REPO)
        assert tasks[0].dependencies == []
        assert tasks[1].dependencies[0].depends_on_task_id == "BUG-T1-REPRODUCE"
        assert tasks[2].dependencies[0].depends_on_task_id == "BUG-T2-LOCATE"
        assert tasks[3].dependencies[0].depends_on_task_id == "BUG-T3-PATCH"

    def test_explicit_false_returns_four_tasks(self):
        planner = FourStagePlanner(three_pass_locate=False)
        tasks = planner.plan(_BUG, _REPO)
        assert len(tasks) == 4


class TestThreePassLocateEnabled:
    """With three_pass_locate=True, LOCATE expands to T2A, T2B, T2C."""

    def test_three_pass_returns_six_tasks(self):
        planner = FourStagePlanner(three_pass_locate=True)
        tasks = planner.plan(_BUG, _REPO)
        assert len(tasks) == 6

    def test_three_pass_task_ids_include_sub_tasks(self):
        planner = FourStagePlanner(three_pass_locate=True)
        tasks = planner.plan(_BUG, _REPO)
        ids = [t.task_id for t in tasks]
        assert "BUG-T2-LOCATE" not in ids
        assert "BUG-T2A-REPO-TREE" in ids
        assert "BUG-T2B-SKELETON" in ids
        assert "BUG-T2C-LINE-RANGE" in ids

    def test_three_pass_sub_tasks_are_chained(self):
        """T2A depends on T1; T2B depends on T2A; T2C depends on T2B."""
        planner = FourStagePlanner(three_pass_locate=True)
        tasks = planner.plan(_BUG, _REPO)
        task_map = {t.task_id: t for t in tasks}
        t2a = task_map["BUG-T2A-REPO-TREE"]
        t2b = task_map["BUG-T2B-SKELETON"]
        t2c = task_map["BUG-T2C-LINE-RANGE"]
        assert t2a.dependencies[0].depends_on_task_id == "BUG-T1-REPRODUCE"
        assert t2b.dependencies[0].depends_on_task_id == "BUG-T2A-REPO-TREE"
        assert t2c.dependencies[0].depends_on_task_id == "BUG-T2B-SKELETON"

    def test_patch_depends_on_last_locate_sub_task(self):
        """BUG-T3-PATCH must depend on BUG-T2C-LINE-RANGE, not BUG-T2-LOCATE."""
        planner = FourStagePlanner(three_pass_locate=True)
        tasks = planner.plan(_BUG, _REPO)
        task_map = {t.task_id: t for t in tasks}
        t3 = task_map["BUG-T3-PATCH"]
        assert t3.dependencies[0].depends_on_task_id == "BUG-T2C-LINE-RANGE"

    def test_verify_depends_on_patch(self):
        planner = FourStagePlanner(three_pass_locate=True)
        tasks = planner.plan(_BUG, _REPO)
        task_map = {t.task_id: t for t in tasks}
        t4 = task_map["BUG-T4-VERIFY"]
        assert t4.dependencies[0].depends_on_task_id == "BUG-T3-PATCH"

    def test_three_pass_sub_tasks_are_bugfix_type(self):
        planner = FourStagePlanner(three_pass_locate=True)
        tasks = planner.plan(_BUG, _REPO)
        sub_ids = {"BUG-T2A-REPO-TREE", "BUG-T2B-SKELETON", "BUG-T2C-LINE-RANGE"}
        for t in tasks:
            if t.task_id in sub_ids:
                assert t.task_type == TaskType.BUGFIX

    def test_language_propagated_to_sub_tasks(self):
        planner = FourStagePlanner(three_pass_locate=True)
        tasks = planner.plan(_BUG, _REPO, language="python")
        sub_ids = {"BUG-T2A-REPO-TREE", "BUG-T2B-SKELETON", "BUG-T2C-LINE-RANGE"}
        from autodev.schemas import Language
        for t in tasks:
            if t.task_id in sub_ids:
                assert t.language == Language.PYTHON
