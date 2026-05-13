"""Tests for scale-adaptive MilestonePlanner and TaskPlanner."""
from __future__ import annotations

import pytest

from autodev.planners.milestone_planner import MilestonePlanner
from autodev.planners.task_planner import TaskPlanner
from autodev.schemas import (
    ArchitectureSpec,
    Language,
    Scale,
    TaskType,
)


def _arch() -> ArchitectureSpec:
    return ArchitectureSpec(title="Test", overview="test arch")


def _langs(n: int = 1) -> list[Language]:
    all_langs = [Language.PYTHON, Language.TYPESCRIPT, Language.RUST]
    return all_langs[:n]


class TestMilestonePlannerScaleNone:
    """scale=None must reproduce exact current 6-milestone behavior (backward compat)."""

    def test_default_six_milestones(self):
        planner = MilestonePlanner()
        milestones = planner.plan(architecture=_arch(), languages=_langs())
        assert len(milestones) == 6

    def test_milestone_ids_are_m0_to_m5(self):
        planner = MilestonePlanner()
        milestones = planner.plan(architecture=_arch(), languages=_langs())
        ids = [m.milestone_id for m in milestones]
        assert ids == ["M0", "M1", "M2", "M3", "M4", "M5"]


class TestMilestonePlannerBugFix:
    """bug-fix scale => only M2."""

    def test_bug_fix_only_m2(self):
        planner = MilestonePlanner()
        milestones = planner.plan(architecture=_arch(), languages=_langs(), scale=Scale.BUG_FIX)
        ids = [m.milestone_id for m in milestones]
        assert ids == ["M2"]

    def test_bug_fix_no_m0_m1(self):
        planner = MilestonePlanner()
        milestones = planner.plan(architecture=_arch(), languages=_langs(), scale=Scale.BUG_FIX)
        ids = [m.milestone_id for m in milestones]
        assert "M0" not in ids
        assert "M1" not in ids

    def test_bug_fix_single_milestone(self):
        planner = MilestonePlanner()
        milestones = planner.plan(architecture=_arch(), languages=_langs(), scale=Scale.BUG_FIX)
        assert len(milestones) == 1

    def test_bug_fix_m2_no_dependencies(self):
        planner = MilestonePlanner()
        milestones = planner.plan(architecture=_arch(), languages=_langs(), scale=Scale.BUG_FIX)
        # M2 is first; should have no dependencies
        assert milestones[0].dependencies == []


class TestMilestonePlannerSmall:
    """small scale => all milestones except M3."""

    def test_small_skips_m3(self):
        planner = MilestonePlanner()
        milestones = planner.plan(architecture=_arch(), languages=_langs(), scale=Scale.SMALL)
        ids = [m.milestone_id for m in milestones]
        assert "M3" not in ids

    def test_small_has_m0_m1_m2_m4_m5(self):
        planner = MilestonePlanner()
        milestones = planner.plan(architecture=_arch(), languages=_langs(), scale=Scale.SMALL)
        ids = [m.milestone_id for m in milestones]
        for expected in ["M0", "M1", "M2", "M4", "M5"]:
            assert expected in ids

    def test_small_five_milestones(self):
        planner = MilestonePlanner()
        milestones = planner.plan(architecture=_arch(), languages=_langs(), scale=Scale.SMALL)
        assert len(milestones) == 5


class TestMilestonePlannerMedium:
    """medium scale => exact same 6-milestone default."""

    def test_medium_six_milestones(self):
        planner = MilestonePlanner()
        milestones = planner.plan(architecture=_arch(), languages=_langs(), scale=Scale.MEDIUM)
        assert len(milestones) == 6

    def test_medium_includes_m3(self):
        planner = MilestonePlanner()
        milestones = planner.plan(architecture=_arch(), languages=_langs(), scale=Scale.MEDIUM)
        ids = [m.milestone_id for m in milestones]
        assert "M3" in ids


class TestMilestonePlannerEnterprise:
    """enterprise scale => 8 milestones with M3.5 and M3.6."""

    def test_enterprise_eight_milestones(self):
        planner = MilestonePlanner()
        milestones = planner.plan(architecture=_arch(), languages=_langs(), scale=Scale.ENTERPRISE)
        assert len(milestones) == 8

    def test_enterprise_has_m35_m36(self):
        planner = MilestonePlanner()
        milestones = planner.plan(architecture=_arch(), languages=_langs(), scale=Scale.ENTERPRISE)
        ids = [m.milestone_id for m in milestones]
        assert "M3.5" in ids
        assert "M3.6" in ids

    def test_enterprise_m35_after_m3(self):
        planner = MilestonePlanner()
        milestones = planner.plan(architecture=_arch(), languages=_langs(), scale=Scale.ENTERPRISE)
        ids = [m.milestone_id for m in milestones]
        m3_pos = ids.index("M3")
        m35_pos = ids.index("M3.5")
        assert m35_pos == m3_pos + 1

    def test_enterprise_m36_before_m4(self):
        planner = MilestonePlanner()
        milestones = planner.plan(architecture=_arch(), languages=_langs(), scale=Scale.ENTERPRISE)
        ids = [m.milestone_id for m in milestones]
        m36_pos = ids.index("M3.6")
        m4_pos = ids.index("M4")
        assert m36_pos == m4_pos - 1


class TestTaskPlannerBugFix:
    """TaskPlanner bug-fix scale => single FEATURE task on M2."""

    def test_bug_fix_single_task(self):
        mplanner = MilestonePlanner()
        milestones = mplanner.plan(architecture=_arch(), languages=_langs(), scale=Scale.BUG_FIX)
        tplanner = TaskPlanner()
        tasks = tplanner.plan(milestones=milestones, architecture=_arch(), languages=_langs(), scale=Scale.BUG_FIX)
        assert len(tasks) == 1

    def test_bug_fix_task_type_is_feature(self):
        mplanner = MilestonePlanner()
        milestones = mplanner.plan(architecture=_arch(), languages=_langs(), scale=Scale.BUG_FIX)
        tplanner = TaskPlanner()
        tasks = tplanner.plan(milestones=milestones, architecture=_arch(), languages=_langs(), scale=Scale.BUG_FIX)
        assert tasks[0].task_type == TaskType.FEATURE

    def test_bug_fix_task_targets_cli_py(self):
        mplanner = MilestonePlanner()
        milestones = mplanner.plan(architecture=_arch(), languages=_langs(), scale=Scale.BUG_FIX)
        tplanner = TaskPlanner()
        tasks = tplanner.plan(
            milestones=milestones, architecture=_arch(), languages=_langs(),
            scale=Scale.BUG_FIX, product_name="my-app",
        )
        assert any("cli.py" in f for f in tasks[0].target_files)


class TestTaskPlannerEnterprise:
    """Enterprise scale includes tasks for M3.5 and M3.6."""

    def test_enterprise_has_m35_m36_tasks(self):
        mplanner = MilestonePlanner()
        milestones = mplanner.plan(architecture=_arch(), languages=_langs(), scale=Scale.ENTERPRISE)
        tplanner = TaskPlanner()
        tasks = tplanner.plan(milestones=milestones, architecture=_arch(), languages=_langs(), scale=Scale.ENTERPRISE)
        milestone_ids = {t.milestone_id for t in tasks}
        assert "M3.5" in milestone_ids
        assert "M3.6" in milestone_ids

    def test_enterprise_no_new_task_types(self):
        """Enterprise tasks reuse FEATURE type (no new TaskType required)."""
        mplanner = MilestonePlanner()
        milestones = mplanner.plan(architecture=_arch(), languages=_langs(), scale=Scale.ENTERPRISE)
        tplanner = TaskPlanner()
        tasks = tplanner.plan(milestones=milestones, architecture=_arch(), languages=_langs(), scale=Scale.ENTERPRISE)
        m35_tasks = [t for t in tasks if t.milestone_id == "M3.5"]
        m36_tasks = [t for t in tasks if t.milestone_id == "M3.6"]
        assert all(t.task_type == TaskType.FEATURE for t in m35_tasks)
        assert all(t.task_type == TaskType.FEATURE for t in m36_tasks)


class TestTaskPlannerBackwardCompat:
    """scale=None must not change existing task counts (backward compat)."""

    def test_none_scale_medium_task_count(self):
        mplanner = MilestonePlanner()
        milestones_none = mplanner.plan(architecture=_arch(), languages=_langs(), scale=None)
        milestones_med = mplanner.plan(architecture=_arch(), languages=_langs(), scale=Scale.MEDIUM)
        tplanner = TaskPlanner()
        tasks_none = tplanner.plan(milestones=milestones_none, architecture=_arch(), languages=_langs(), scale=None)
        tasks_med = tplanner.plan(milestones=milestones_med, architecture=_arch(), languages=_langs(), scale=Scale.MEDIUM)
        assert len(tasks_none) == len(tasks_med)
