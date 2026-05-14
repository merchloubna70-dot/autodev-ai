"""Unit tests for MilestoneFlow (HIGH-COV-01 / HIGH-ORPHAN-01).

All tests are deterministic and require no real codex/claude binaries.
MilestoneFlow.run() calls RunState.load() then ImplementerAgent.run_milestone().
We mock at the ImplementerAgent layer so the router is never invoked.
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from autodev.config import FactoryConfig
from autodev.flows.milestone_flow import MilestoneFlow, MilestoneFlowInput
from autodev.schemas import (
    DeliveryTask,
    ExecutionBackend,
    ExecutionResult,
    ImplementationResult,
    Language,
    Milestone,
    MilestonePlan,
    PipelineMode,
    TaskType,
)
from autodev.state import RunState

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_run(tmp_path: Path, milestone_id: str = "M1") -> RunState:
    """Create a minimal RunState with one milestone and one task persisted."""
    run = RunState(repo_path=str(tmp_path))
    task = DeliveryTask(
        task_id="T1",
        milestone_id=milestone_id,
        title="Write hello",
        description="Print hello",
        language=Language.PYTHON,
        task_type=TaskType.FEATURE,
    )
    milestone = Milestone(
        milestone_id=milestone_id,
        title="Milestone One",
        objective="Deliver feature X",
        task_ids=["T1"],
    )
    run.state.milestone_plan = MilestonePlan(milestones=[milestone], tasks=[task])
    run.state.languages = [Language.PYTHON]
    run.save()
    return run


def _ok_impl_result(milestone_id: str = "M1") -> ImplementationResult:
    exec_res = ExecutionResult(
        task_id="T1",
        milestone_id=milestone_id,
        backend=ExecutionBackend.MOCK_CODEX,
        success=True,
        mock_used=True,
    )
    return ImplementationResult(
        milestone_id=milestone_id,
        task_results=[exec_res],
        success=True,
        mock_used=True,
    )


def _fail_impl_result(milestone_id: str = "M1") -> ImplementationResult:
    exec_res = ExecutionResult(
        task_id="T1",
        milestone_id=milestone_id,
        backend=ExecutionBackend.MOCK_CODEX,
        success=False,
        mock_used=True,
        error_type="mock_forced_failure",
    )
    return ImplementationResult(
        milestone_id=milestone_id,
        task_results=[exec_res],
        success=False,
        mock_used=True,
        failed_task_ids=["T1"],
    )


# ---------------------------------------------------------------------------
# Test 1 — initialization
# ---------------------------------------------------------------------------


def test_milestone_flow_initialization() -> None:
    """MilestoneFlow can be constructed with no arguments."""
    flow = MilestoneFlow()
    assert flow.config is not None
    assert isinstance(flow.config, FactoryConfig)


def test_milestone_flow_initialization_custom_config() -> None:
    """MilestoneFlow accepts a custom FactoryConfig."""
    cfg = FactoryConfig(allow_mock_executor=True)
    flow = MilestoneFlow(config=cfg)
    assert flow.config is cfg


# ---------------------------------------------------------------------------
# Test 2 — happy path with mock executor
# ---------------------------------------------------------------------------


def test_milestone_flow_happy_path_mock(tmp_path: Path) -> None:
    """Single milestone with mock executor returns ImplementationResult.success=True."""
    run = _make_run(tmp_path, "M1")
    flow = MilestoneFlow()
    inp = MilestoneFlowInput(
        run_id=run.run_id,
        milestone_id="M1",
        repo_path=str(tmp_path),
        mode=PipelineMode.DRY_RUN,
        allow_mock=True,
    )
    ok_result = _ok_impl_result("M1")

    with patch(
        "autodev.flows.milestone_flow.ImplementerAgent.run_milestone",
        return_value=ok_result,
    ):
        result = flow.run(inp)

    assert result.success is True
    assert result.milestone_id == "M1"


# ---------------------------------------------------------------------------
# Test 3 — failure path
# ---------------------------------------------------------------------------


def test_milestone_flow_failure_path(tmp_path: Path) -> None:
    """When executor returns a failed result the flow surfaces failure=True."""
    run = _make_run(tmp_path, "M1")
    flow = MilestoneFlow()
    inp = MilestoneFlowInput(
        run_id=run.run_id,
        milestone_id="M1",
        repo_path=str(tmp_path),
        mode=PipelineMode.DRY_RUN,
        allow_mock=True,
    )
    fail_result = _fail_impl_result("M1")

    with patch(
        "autodev.flows.milestone_flow.ImplementerAgent.run_milestone",
        return_value=fail_result,
    ):
        result = flow.run(inp)

    assert result.success is False
    assert "T1" in result.failed_task_ids


# ---------------------------------------------------------------------------
# Test 4 — report artifact written to disk
# ---------------------------------------------------------------------------


def test_milestone_flow_report_artifact(tmp_path: Path) -> None:
    """MilestoneFlow.run() writes execution/milestone_<id>_results.json via run.save_json()."""
    run = _make_run(tmp_path, "M1")
    flow = MilestoneFlow()
    inp = MilestoneFlowInput(
        run_id=run.run_id,
        milestone_id="M1",
        repo_path=str(tmp_path),
        allow_mock=True,
    )
    ok_result = _ok_impl_result("M1")

    # We also need run.save_json to actually be called by run_milestone; since we mock
    # run_milestone at the agent level, we verify the flow saves the aggregate result.
    with patch(
        "autodev.flows.milestone_flow.ImplementerAgent.run_milestone",
        return_value=ok_result,
    ):
        flow.run(inp)

    # The flow appends result to run.state.implementation_results and saves.
    saved_state_file = (
        Path(tmp_path) / ".dev-factory" / "runs" / run.run_id / "run_state.json"
    )
    assert saved_state_file.exists(), "run_state.json must be saved"
    data = json.loads(saved_state_file.read_text())
    impl_results = data.get("implementation_results", [])
    assert any(r["milestone_id"] == "M1" for r in impl_results), (
        "implementation_results must include M1"
    )


# ---------------------------------------------------------------------------
# Test 5 — empty milestone list (no tasks for milestone_id) returns success
# ---------------------------------------------------------------------------


def test_milestone_flow_empty_milestone_list(tmp_path: Path) -> None:
    """When a milestone has no tasks the implementer returns success=True immediately.

    ImplementerAgent.run_milestone returns ImplementationResult(success=True) when
    milestone_tasks is empty. We verify MilestoneFlow surfaces this correctly.
    """
    run = _make_run(tmp_path, "M1")
    # Use a milestone_id that has no tasks in the plan -> implementer returns empty success
    empty_result = ImplementationResult(milestone_id="M_EMPTY", success=True)
    flow = MilestoneFlow()
    inp = MilestoneFlowInput(
        run_id=run.run_id,
        milestone_id="M_EMPTY",
        repo_path=str(tmp_path),
        allow_mock=True,
    )

    with patch(
        "autodev.flows.milestone_flow.ImplementerAgent.run_milestone",
        return_value=empty_result,
    ):
        result = flow.run(inp)

    assert result.success is True
    assert result.milestone_id == "M_EMPTY"
    assert result.task_results == []


# ---------------------------------------------------------------------------
# Test 6 — skip-M0 / architecture milestone collapses
# ---------------------------------------------------------------------------


def test_milestone_flow_skip_m0_collapse(tmp_path: Path) -> None:
    """Architecture milestone M0 with no tasks returns ImplementationResult(success=True).

    ImplementerAgent.run_milestone returns early with success=True when there are no
    tasks matching the milestone_id. This test verifies MilestoneFlow correctly
    propagates that result (skip / collapse behavior).
    """
    run = RunState(repo_path=str(tmp_path))
    # M0 is the architecture milestone — add it to the plan with no tasks
    arch_milestone = Milestone(
        milestone_id="M0",
        title="Architecture",
        objective="Design the system",
        task_ids=[],  # no tasks → collapses
    )
    feature_task = DeliveryTask(
        task_id="T1",
        milestone_id="M1",
        title="Implement feature",
        description="Feature work",
        language=Language.PYTHON,
        task_type=TaskType.FEATURE,
    )
    run.state.milestone_plan = MilestonePlan(
        milestones=[arch_milestone],
        tasks=[feature_task],  # task belongs to M1, not M0
    )
    run.state.languages = [Language.PYTHON]
    run.save()

    flow = MilestoneFlow()
    inp = MilestoneFlowInput(
        run_id=run.run_id,
        milestone_id="M0",
        repo_path=str(tmp_path),
        allow_mock=True,
    )
    # run_milestone returns success=True immediately for empty task list
    collapsed = ImplementationResult(milestone_id="M0", success=True)

    with patch(
        "autodev.flows.milestone_flow.ImplementerAgent.run_milestone",
        return_value=collapsed,
    ):
        result = flow.run(inp)

    assert result.success is True
    assert result.milestone_id == "M0"
    assert result.task_results == [], "architecture milestone must collapse to no task results"


# ---------------------------------------------------------------------------
# Test 7 — run() raises RuntimeError when milestone_plan is absent
# ---------------------------------------------------------------------------


def test_milestone_flow_raises_when_no_plan(tmp_path: Path) -> None:
    """MilestoneFlow.run() raises RuntimeError when the run has no milestone_plan."""
    run = RunState(repo_path=str(tmp_path))
    # Leave run.state.milestone_plan as None (default)
    run.save()

    flow = MilestoneFlow()
    inp = MilestoneFlowInput(
        run_id=run.run_id,
        milestone_id="M1",
        repo_path=str(tmp_path),
        allow_mock=True,
    )
    with pytest.raises(RuntimeError, match="no milestone_plan"):
        flow.run(inp)
