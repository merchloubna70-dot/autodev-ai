"""Unit tests for StepRunner micro-file framework (BMAD-15).

≥6 tests covering: register/run/resume from step/skip-completed/topo order/persistence.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from autodev.flows.step_runner import Step, StepRegistry, StepRunner
from autodev.schemas import StepStatus

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_step(name: str, depends_on=None, side_effects=None):
    """Build a Step whose func appends name to ctx['trace']."""
    deps = depends_on or []

    def _func(ctx):
        ctx.setdefault("trace", []).append(name)
        if side_effects:
            side_effects(ctx)
        return f"done:{name}"

    return Step(name=name, description=f"step {name}", func=_func, depends_on=deps)


def _make_ctx(tmp_path: Path, run_id: str = "test-run") -> dict:
    """Build a minimal ctx dict that _CtxStepRunner can resolve."""
    # Use a fake run object with base_dir and run_id attrs
    class _FakeRun:
        pass

    fake = _FakeRun()
    fake.base_dir = str(tmp_path)
    fake.run_id = run_id
    return {"run": fake}


class _CtxRunner(StepRunner):
    """Override _steps_dir to resolve from ctx['run'] (mirrors _CtxStepRunner)."""

    @staticmethod
    def _steps_dir(ctx) -> Path:
        run = ctx.get("run")
        if run is None:
            return Path(".dev-factory/runs/unknown/steps")
        # Real RunState: .root
        root = getattr(run, "root", None)
        if root is not None:
            return Path(root) / "steps"
        # Test fakes: base_dir + run_id
        base = getattr(run, "base_dir", ".dev-factory")
        rid = getattr(run, "run_id", "unknown")
        return Path(str(base)) / "runs" / str(rid) / "steps"


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_register_and_list():
    """StepRegistry stores and lists registered steps."""
    reg = StepRegistry("test")
    s1 = _make_step("a")
    s2 = _make_step("b")
    reg.register(s1)
    reg.register(s2)
    names = [s.name for s in reg.list_steps()]
    assert "a" in names and "b" in names


def test_find_step():
    """find() returns the step by name; raises KeyError for unknown."""
    reg = StepRegistry("find_test")
    step = _make_step("foo")
    reg.register(step)
    assert reg.find("foo") is step
    with pytest.raises(KeyError):
        reg.find("not_there")


def test_topological_order_respects_deps():
    """Steps appear after their declared dependencies."""
    reg = StepRegistry("topo")
    reg.register(_make_step("a"))
    reg.register(_make_step("b", depends_on=["a"]))
    reg.register(_make_step("c", depends_on=["b"]))
    ordered = [s.name for s in reg.topological_order()]
    assert ordered.index("a") < ordered.index("b")
    assert ordered.index("b") < ordered.index("c")


def test_run_executes_all_steps(tmp_path):
    """StepRunner.run() calls every step and records COMPLETED status."""
    reg = StepRegistry("run_test")
    reg.register(_make_step("x"))
    reg.register(_make_step("y", depends_on=["x"]))

    ctx = _make_ctx(tmp_path)
    runner = _CtxRunner()
    records = runner.run(reg, ctx)

    assert records["x"].status == StepStatus.COMPLETED
    assert records["y"].status == StepStatus.COMPLETED
    assert ctx["trace"] == ["x", "y"]


def test_persistence_writes_json(tmp_path):
    """Each step status is persisted to a JSON file."""
    reg = StepRegistry("persist_test")
    reg.register(_make_step("p1"))
    reg.register(_make_step("p2", depends_on=["p1"]))

    ctx = _make_ctx(tmp_path, run_id="persist-run")
    runner = _CtxRunner()
    runner.run(reg, ctx)

    steps_dir = tmp_path / "runs" / "persist-run" / "steps"
    p1_file = steps_dir / "p1.json"
    p2_file = steps_dir / "p2.json"
    assert p1_file.exists()
    assert p2_file.exists()
    data = json.loads(p1_file.read_text())
    assert data["status"] == "completed"
    assert data["step_name"] == "p1"


def test_resume_from_step_skips_earlier(tmp_path):
    """from_step causes earlier steps to be skipped (not re-executed)."""
    reg = StepRegistry("resume_test")
    reg.register(_make_step("s1"))
    reg.register(_make_step("s2", depends_on=["s1"]))
    reg.register(_make_step("s3", depends_on=["s2"]))

    ctx = _make_ctx(tmp_path, run_id="resume-run")
    runner = _CtxRunner()
    records = runner.run(reg, ctx, from_step="s3")

    # s1 and s2 are before from_step and should be skipped
    assert records["s1"].status == StepStatus.SKIPPED
    assert records["s2"].status == StepStatus.SKIPPED
    # s3 should execute
    assert records["s3"].status == StepStatus.COMPLETED
    # trace should only contain s3
    assert ctx.get("trace", []) == ["s3"]


def test_skip_already_completed_before_from_step(tmp_path):
    """Steps before from_step that have COMPLETED status on disk are preserved.

    When from_step=c2, steps before c2 (i.e. c1) are NOT re-executed.
    Their existing COMPLETED record is loaded from disk and returned as-is.
    """
    reg = StepRegistry("skip_completed")
    reg.register(_make_step("c1"))
    reg.register(_make_step("c2", depends_on=["c1"]))

    ctx = _make_ctx(tmp_path, run_id="skip-completed-run")
    runner = _CtxRunner()

    # First run: complete all steps
    runner.run(reg, ctx)
    assert ctx["trace"] == ["c1", "c2"]

    # Second run: from c2, c1 should NOT be re-executed (trace has no c1)
    ctx2 = _make_ctx(tmp_path, run_id="skip-completed-run")
    records2 = runner.run(reg, ctx2, from_step="c2")

    # c1 before from_step -> preserved from disk as COMPLETED (not re-run)
    assert records2["c1"].status == StepStatus.COMPLETED
    # c2 at from_step -> re-executed
    assert records2["c2"].status == StepStatus.COMPLETED
    # Only c2 ran in this invocation (c1 was NOT re-executed)
    assert ctx2.get("trace", []) == ["c2"]


def test_failed_step_records_error(tmp_path):
    """A step that raises records FAILED status with error_type."""

    def _bad(ctx):
        raise RuntimeError("deliberate failure")

    reg = StepRegistry("fail_test")
    reg.register(Step(name="bad_step", description="fails", func=_bad))

    ctx = _make_ctx(tmp_path, run_id="fail-run")
    runner = _CtxRunner()
    with pytest.raises(RuntimeError):
        runner.run(reg, ctx)

    steps_dir = tmp_path / "runs" / "fail-run" / "steps"
    data = json.loads((steps_dir / "bad_step.json").read_text())
    assert data["status"] == "failed"
    assert data["error_type"] == "RuntimeError"
