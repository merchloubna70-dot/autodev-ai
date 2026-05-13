"""Unit tests for DependencyPlanner wave logic (Bug8 regression suite)."""
from __future__ import annotations

import pytest

from autodev.planners.dependency_planner import DependencyPlanner
from autodev.schemas import DeliveryTask, RiskLevel, TaskDependency


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _task(
    tid: str,
    *,
    allowed_files: list[str] | None = None,
    target_files: list[str] | None = None,
    risk_level: RiskLevel = RiskLevel.LOW,
    deps: list[str] | None = None,
) -> DeliveryTask:
    return DeliveryTask(
        task_id=tid,
        milestone_id="m1",
        title=tid,
        description=tid,
        allowed_files=allowed_files or [],
        target_files=target_files or [],
        risk_level=risk_level,
        dependencies=[TaskDependency(depends_on_task_id=d) for d in (deps or [])],
    )


planner = DependencyPlanner()


# ---------------------------------------------------------------------------
# Test 1: Two FEATURE tasks with disjoint files + low risk → SAME wave
# ---------------------------------------------------------------------------


def test_disjoint_files_same_wave():
    tasks = [
        _task("T1", allowed_files=["src/a.py"]),
        _task("T2", allowed_files=["src/b.py"]),
    ]
    waves = planner.waves(tasks)
    # Both tasks should appear in the first (and only) wave
    assert len(waves) == 1
    assert set(waves[0]) == {"T1", "T2"}


# ---------------------------------------------------------------------------
# Test 2: Overlapping allowed_files → serialized into separate waves
# ---------------------------------------------------------------------------


def test_overlapping_files_serialized():
    tasks = [
        _task("T1", allowed_files=["pyproject.toml"]),
        _task("T2", allowed_files=["pyproject.toml"]),
    ]
    waves = planner.waves(tasks)
    assert len(waves) == 2
    # T1 must precede T2 (or T2 T1 in reverse, order from topological sort)
    flat = [t for w in waves for t in w]
    assert flat.index("T1") < flat.index("T2")


# ---------------------------------------------------------------------------
# Test 3: T1 dep T2, T2 dep T3 → 3 waves of width 1
# ---------------------------------------------------------------------------


def test_explicit_dep_chain_three_waves():
    tasks = [
        _task("T3"),
        _task("T2", deps=["T3"]),
        _task("T1", deps=["T2"]),
    ]
    waves = planner.waves(tasks)
    assert len(waves) == 3
    for w in waves:
        assert len(w) == 1
    flat = [w[0] for w in waves]
    assert flat == ["T3", "T2", "T1"]


# ---------------------------------------------------------------------------
# Test 4: Two HIGH risk tasks → serialized (sanity)
# ---------------------------------------------------------------------------


def test_high_risk_serialized():
    tasks = [
        _task("H1", risk_level=RiskLevel.HIGH),
        _task("H2", risk_level=RiskLevel.HIGH),
    ]
    waves = planner.waves(tasks)
    assert len(waves) == 2
    flat = [w[0] for w in waves]
    assert flat == ["H1", "H2"]


# ---------------------------------------------------------------------------
# Test 5: Two LOW risk tasks with empty allowed_files → SAME wave
#         (regression test for empty-key bug)
# ---------------------------------------------------------------------------


def test_empty_allowed_files_not_serialized():
    tasks = [
        _task("L1", allowed_files=[]),
        _task("L2", allowed_files=[]),
    ]
    waves = planner.waves(tasks)
    # Must NOT be serialized due to empty key — both in same wave
    assert len(waves) == 1
    assert set(waves[0]) == {"L1", "L2"}


# ---------------------------------------------------------------------------
# Test 6: explain_waves returns non-empty reasons map AND correct stats keys
# ---------------------------------------------------------------------------


def test_explain_waves_structure():
    tasks = [
        _task("A", allowed_files=["pyproject.toml"]),
        _task("B", allowed_files=["pyproject.toml"]),
        _task("C", allowed_files=["README.md"]),
    ]
    explanation = planner.explain_waves(tasks)
    assert explanation.waves  # non-empty
    assert explanation.reasons  # non-empty reasons map
    # All task IDs must appear in reasons
    for t in tasks:
        assert t.task_id in explanation.reasons
    # Stats must contain required keys
    assert "num_waves" in explanation.stats
    assert "max_width" in explanation.stats
    assert "avg_width" in explanation.stats
    assert "single_task_waves" in explanation.stats
    # B is blocked by A due to same-file conflict
    b_reasons = explanation.reasons.get("B", [])
    assert any("blocked-by-A" in r for r in b_reasons)
