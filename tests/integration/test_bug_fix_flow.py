"""Integration tests for BugFixFlow — run with mock executors, offline."""
from __future__ import annotations

import json
from pathlib import Path

from autodev.config import FactoryConfig
from autodev.flows.bug_fix_flow import BugFixFlow, BugFixInput
from autodev.schemas import Language, PipelineMode

FIX = Path(__file__).resolve().parents[1] / "fixtures"


def _make_repo(tmp_path: Path) -> Path:
    """Create a minimal repo-like directory for testing."""
    import shutil

    src = FIX / "python_project"
    dst = tmp_path / "python_project"
    shutil.copytree(src, dst)
    return dst


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _cfg(allow_mock: bool = True) -> FactoryConfig:
    cfg = FactoryConfig()
    cfg.allow_mock_executor = allow_mock
    return cfg


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_bug_fix_flow_creates_planning_tasks_json(tmp_path):
    """planning/tasks.json must exist and contain exactly 4 entries."""
    repo = _make_repo(tmp_path)
    cfg = _cfg()
    run = BugFixFlow(cfg).run(BugFixInput(
        bug_description="ValueError raised when input is empty string",
        repo_path=str(repo),
        languages=[Language.PYTHON],
        mode=PipelineMode.DRY_RUN,
        allow_mock=True,
    ))

    tasks_file = Path(run.repo_path) / ".dev-factory" / "runs" / run.run_id / "planning" / "tasks.json"
    assert tasks_file.exists(), "planning/tasks.json must be created"

    data = json.loads(tasks_file.read_text(encoding="utf-8"))
    assert isinstance(data, list), "tasks.json should be a JSON array"
    assert len(data) == 4, f"expected 4 tasks, got {len(data)}"


def test_bug_fix_flow_task_ids_in_order(tmp_path):
    repo = _make_repo(tmp_path)
    cfg = _cfg()
    run = BugFixFlow(cfg).run(BugFixInput(
        bug_description="IndexError on empty list",
        repo_path=str(repo),
        languages=[Language.PYTHON],
        mode=PipelineMode.DRY_RUN,
        allow_mock=True,
    ))

    tasks_file = Path(run.repo_path) / ".dev-factory" / "runs" / run.run_id / "planning" / "tasks.json"
    data = json.loads(tasks_file.read_text(encoding="utf-8"))
    task_ids = [t["task_id"] for t in data]
    assert task_ids == [
        "BUG-T1-REPRODUCE",
        "BUG-T2-LOCATE",
        "BUG-T3-PATCH",
        "BUG-T4-VERIFY",
    ]


def test_bug_fix_flow_four_execution_calls(tmp_path):
    """execution_calls.jsonl must have exactly 4 entries — one per stage."""
    repo = _make_repo(tmp_path)
    cfg = _cfg()
    run = BugFixFlow(cfg).run(BugFixInput(
        bug_description="KeyError on missing dict key",
        repo_path=str(repo),
        languages=[Language.PYTHON],
        mode=PipelineMode.DRY_RUN,
        allow_mock=True,
    ))

    calls_file = (
        Path(run.repo_path)
        / ".dev-factory"
        / "runs"
        / run.run_id
        / "execution"
        / "execution_calls.jsonl"
    )
    assert calls_file.exists(), "execution_calls.jsonl must be created"

    lines = [ln for ln in calls_file.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert len(lines) == 4, f"expected 4 execution call entries, got {len(lines)}"


def test_bug_fix_flow_mock_used(tmp_path):
    """With allow_mock=True the router must fall back to mock and record it."""
    repo = _make_repo(tmp_path)
    cfg = _cfg()
    run = BugFixFlow(cfg).run(BugFixInput(
        bug_description="AttributeError in model save()",
        repo_path=str(repo),
        languages=[Language.PYTHON],
        mode=PipelineMode.DRY_RUN,
        allow_mock=True,
    ))
    assert run.state.mock_execution_used is True


def test_bug_fix_flow_run_state_has_milestone_plan(tmp_path):
    """The persisted run state must contain a milestone_plan with MBUG-1."""
    repo = _make_repo(tmp_path)
    cfg = _cfg()
    run = BugFixFlow(cfg).run(BugFixInput(
        bug_description="TypeError: unsupported operand types",
        repo_path=str(repo),
        languages=[Language.PYTHON],
        mode=PipelineMode.DRY_RUN,
        allow_mock=True,
    ))
    plan = run.state.milestone_plan
    assert plan is not None
    milestone_ids = [m.milestone_id for m in plan.milestones]
    assert "MBUG-1" in milestone_ids
