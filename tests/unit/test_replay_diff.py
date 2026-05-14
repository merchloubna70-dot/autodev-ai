"""Unit tests for ReplayDiffFlow (autodev.flows.replay_diff_flow)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from autodev.flows.replay_diff_flow import ReplayDiff, ReplayDiffFlow

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_run(runs_dir: Path, run_id: str) -> Path:
    """Create a minimal run directory skeleton under *runs_dir*."""
    run_dir = runs_dir / run_id
    for sub in ("input", "product", "architecture", "planning", "execution",
                "quality", "verification", "delivery"):
        (run_dir / sub).mkdir(parents=True, exist_ok=True)
    return run_dir


def _write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _make_flow(tmp_path: Path) -> tuple[ReplayDiffFlow, Path]:
    state_dir = ".dev-factory"
    (tmp_path / state_dir / "runs").mkdir(parents=True, exist_ok=True)
    flow = ReplayDiffFlow(state_dir=state_dir)
    return flow, tmp_path


# ---------------------------------------------------------------------------
# Test 1 — same run-id × 2 = empty diff
# ---------------------------------------------------------------------------


def test_same_run_id_produces_empty_diff(tmp_path: Path) -> None:
    """Diffing a run against itself must return is_empty=True."""
    flow, repo = _make_flow(tmp_path)
    runs_dir = repo / ".dev-factory" / "runs"

    run_dir = _make_run(runs_dir, "run-AAA")
    _write_json(run_dir / "product" / "prd.json", {"product_name": "TestProduct", "overview": "hello"})
    _write_json(run_dir / "planning" / "milestones.json", [{"milestone_id": "M1"}])

    result = flow.diff("run-AAA", "run-AAA", repo_path=str(repo))

    assert isinstance(result, ReplayDiff)
    assert result.is_empty is True
    assert result.stage_diffs == []
    assert result.executor_changes == []


# ---------------------------------------------------------------------------
# Test 2 — different brief appears in diff
# ---------------------------------------------------------------------------


def test_different_brief_appears_in_diff(tmp_path: Path) -> None:
    """When product/prd.json differs, the diff includes a replace op."""
    flow, repo = _make_flow(tmp_path)
    runs_dir = repo / ".dev-factory" / "runs"

    dir_a = _make_run(runs_dir, "run-A01")
    dir_b = _make_run(runs_dir, "run-B01")

    _write_json(dir_a / "product" / "prd.json", {"product_name": "Alpha", "overview": "first brief"})
    _write_json(dir_b / "product" / "prd.json", {"product_name": "Beta", "overview": "second brief"})

    result = flow.diff("run-A01", "run-B01", repo_path=str(repo))

    assert not result.is_empty
    # Find the product stage diff
    product_diffs = [sd for sd in result.stage_diffs if sd.stage == "product"]
    assert len(product_diffs) >= 1, "Expected at least one product-stage diff"

    # The prd.json diff should contain a replace op for product_name
    prd_diff = next(sd for sd in product_diffs if "prd.json" in sd.artifact)
    paths_changed = {op.path for op in prd_diff.ops}
    assert "/product_name" in paths_changed, f"Expected /product_name in {paths_changed}"


# ---------------------------------------------------------------------------
# Test 3 — missing run-id raises clean FileNotFoundError
# ---------------------------------------------------------------------------


def test_missing_run_id_raises_error(tmp_path: Path) -> None:
    """A run-id that does not exist on disk raises FileNotFoundError."""
    flow, repo = _make_flow(tmp_path)
    runs_dir = repo / ".dev-factory" / "runs"

    # Only create run-A; leave run-B absent
    _make_run(runs_dir, "run-exists")

    with pytest.raises(FileNotFoundError, match="run-ghost"):
        flow.diff("run-exists", "run-ghost", repo_path=str(repo))

    with pytest.raises(FileNotFoundError, match="run-ghost"):
        flow.diff("run-ghost", "run-exists", repo_path=str(repo))


# ---------------------------------------------------------------------------
# Test 4 — executor-choice change is highlighted
# ---------------------------------------------------------------------------


def test_executor_choice_change_highlighted(tmp_path: Path) -> None:
    """When executor choices differ, executor_changes is populated."""
    flow, repo = _make_flow(tmp_path)
    runs_dir = repo / ".dev-factory" / "runs"

    dir_a = _make_run(runs_dir, "run-E01")
    dir_b = _make_run(runs_dir, "run-E02")

    # Simulate execution_calls.jsonl logs with different executor choices
    calls_a = [
        json.dumps({"task_id": "T-1", "executor": "codex"}),
        json.dumps({"task_id": "T-2", "executor": "claude_code"}),
    ]
    calls_b = [
        json.dumps({"task_id": "T-1", "executor": "claude_code"}),   # changed
        json.dumps({"task_id": "T-2", "executor": "claude_code"}),   # same
    ]
    (dir_a / "execution" / "execution_calls.jsonl").write_text(
        "\n".join(calls_a), encoding="utf-8"
    )
    (dir_b / "execution" / "execution_calls.jsonl").write_text(
        "\n".join(calls_b), encoding="utf-8"
    )

    result = flow.diff("run-E01", "run-E02", repo_path=str(repo))

    assert len(result.executor_changes) == 1, f"Expected 1 change, got {result.executor_changes}"
    change = result.executor_changes[0]
    assert change.task_id == "T-1"
    assert change.executor_a == "codex"
    assert change.executor_b == "claude_code"


# ---------------------------------------------------------------------------
# Test 5 — cost diff is populated when router_metrics.json present in both
# ---------------------------------------------------------------------------


def test_cost_diff_populated_when_metrics_present(tmp_path: Path) -> None:
    """cost_diff is filled when both runs have execution/router_metrics.json."""
    flow, repo = _make_flow(tmp_path)
    runs_dir = repo / ".dev-factory" / "runs"

    dir_a = _make_run(runs_dir, "run-C01")
    dir_b = _make_run(runs_dir, "run-C02")

    _write_json(dir_a / "execution" / "router_metrics.json", {"total_estimated_cost_cents": 12.5})
    _write_json(dir_b / "execution" / "router_metrics.json", {"total_estimated_cost_cents": 15.0})

    result = flow.diff("run-C01", "run-C02", repo_path=str(repo))

    assert result.cost_diff is not None
    assert result.cost_diff.cost_cents_a == pytest.approx(12.5)
    assert result.cost_diff.cost_cents_b == pytest.approx(15.0)
    assert result.cost_diff.delta_cents == pytest.approx(2.5)


# ---------------------------------------------------------------------------
# Test 6 — cost diff is None when metrics absent
# ---------------------------------------------------------------------------


def test_cost_diff_absent_when_no_metrics(tmp_path: Path) -> None:
    """cost_diff is None when router_metrics.json is missing from either run."""
    flow, repo = _make_flow(tmp_path)
    runs_dir = repo / ".dev-factory" / "runs"

    _make_run(runs_dir, "run-N01")
    _make_run(runs_dir, "run-N02")
    # Intentionally do NOT write router_metrics.json to either run

    result = flow.diff("run-N01", "run-N02", repo_path=str(repo))
    assert result.cost_diff is None


# ---------------------------------------------------------------------------
# Test 7 — to_dict produces JSON-serialisable output
# ---------------------------------------------------------------------------


def test_to_dict_is_json_serialisable(tmp_path: Path) -> None:
    """ReplayDiff.to_dict() must be serialisable via json.dumps."""
    flow, repo = _make_flow(tmp_path)
    runs_dir = repo / ".dev-factory" / "runs"

    dir_a = _make_run(runs_dir, "run-D01")
    dir_b = _make_run(runs_dir, "run-D02")

    _write_json(dir_a / "product" / "prd.json", {"x": 1})
    _write_json(dir_b / "product" / "prd.json", {"x": 2})
    _write_json(dir_a / "execution" / "router_metrics.json", {"total_estimated_cost_cents": 5.0})
    _write_json(dir_b / "execution" / "router_metrics.json", {"total_estimated_cost_cents": 7.0})

    result = flow.diff("run-D01", "run-D02", repo_path=str(repo))
    serialised = json.dumps(result.to_dict())  # must not raise
    parsed = json.loads(serialised)
    assert parsed["run_id_a"] == "run-D01"
    assert parsed["run_id_b"] == "run-D02"
    assert isinstance(parsed["stage_diffs"], list)
