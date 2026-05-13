"""Tests for ExecutorRouter cost/latency telemetry (Agent D)."""
from autodev.config import FactoryConfig
from autodev.executors.base_executor import BaseExecutor
from autodev.executors.executor_router import ExecutorRouter
from autodev.executors.mock_codex_executor import MockCodexExecutor
from autodev.executors.mock_claude_executor import MockClaudeExecutor
from autodev.schemas import (
    ExecutionBackend,
    ExecutionRequest,
    Language,
    RiskLevel,
    TaskType,
)


class _FakeAvailable(BaseExecutor):
    def __init__(self, backend: ExecutionBackend, available: bool = True):
        self.backend = backend
        self.is_mock = False
        self._available = available

    def is_available(self) -> bool:
        return self._available

    def execute(self, request):  # pragma: no cover
        raise NotImplementedError


def _mock_router():
    """Router backed entirely by mock executors (both real CLIs absent)."""
    cfg = FactoryConfig()
    return ExecutorRouter(
        cfg,
        codex=_FakeAvailable(ExecutionBackend.CODEX, available=False),
        claude=_FakeAvailable(ExecutionBackend.CLAUDE_CODE, available=False),
        mock_codex=MockCodexExecutor(),
        mock_claude=MockClaudeExecutor(),
        allow_mock=True,
    )


def _req(task_type=TaskType.FEATURE, **kwargs):
    base = dict(
        task_id="T1",
        repo_path="/tmp/_metrics_test",
        prompt="x" * 400,
        task_type=task_type,
        risk_level=RiskLevel.LOW,
        language=Language.PYTHON,
        backend=ExecutionBackend.AUTO,
    )
    base.update(kwargs)
    return ExecutionRequest(**base)


def test_metrics_start_empty():
    router = _mock_router()
    assert router.metrics.total_calls == 0
    assert router.metrics.samples == []


def test_single_execute_increments_total_calls():
    router = _mock_router()
    req = _req(task_type=TaskType.SCAFFOLD)
    router.execute(req)
    assert router.metrics.total_calls == 1
    assert len(router.metrics.samples) == 1


def test_multiple_executes_accumulate():
    router = _mock_router()
    for i, tt in enumerate([TaskType.SCAFFOLD, TaskType.TEST, TaskType.FEATURE], 1):
        router.execute(_req(task_type=tt, task_id=f"T{i}"))
    assert router.metrics.total_calls == 3
    assert len(router.metrics.samples) == 3


def test_by_backend_reflects_routes():
    router = _mock_router()
    # SCAFFOLD -> CODEX -> MOCK_CODEX (real CLI absent)
    router.execute(_req(task_type=TaskType.SCAFFOLD, task_id="S1"))
    # ARCHITECTURE -> CLAUDE -> MOCK_CLAUDE (real CLI absent)
    router.execute(_req(task_type=TaskType.ARCHITECTURE, task_id="A1"))
    router.execute(_req(task_type=TaskType.SCAFFOLD, task_id="S2"))
    by = router.metrics.by_backend
    assert by.get("mock_codex", 0) >= 2
    assert by.get("mock_claude", 0) >= 1


def test_estimated_tokens_positive_for_nonempty_prompt():
    router = _mock_router()
    req = _req(task_type=TaskType.SCAFFOLD, prompt="hello world " * 50)
    router.execute(req)
    sample = router.metrics.samples[0]
    assert sample.estimated_tokens > 0


def test_mock_backends_have_zero_cost():
    router = _mock_router()
    router.execute(_req(task_type=TaskType.SCAFFOLD, task_id="S1"))
    router.execute(_req(task_type=TaskType.ARCHITECTURE, task_id="A1"))
    for sample in router.metrics.samples:
        assert sample.estimated_cost_cents == 0.0
    assert router.metrics.total_estimated_cost_cents == 0.0


def test_mock_call_count_tracks_mock_used():
    router = _mock_router()
    router.execute(_req(task_type=TaskType.SCAFFOLD, task_id="S1"))
    router.execute(_req(task_type=TaskType.ARCHITECTURE, task_id="A1"))
    assert router.metrics.mock_call_count == 2


def test_success_count_increments():
    router = _mock_router()
    router.execute(_req(task_type=TaskType.SCAFFOLD, task_id="S1"))
    assert router.metrics.success_count == 1
    assert router.metrics.failure_count == 0


def test_export_metrics_returns_dict():
    router = _mock_router()
    router.execute(_req(task_type=TaskType.TEST, task_id="T1"))
    exported = router.export_metrics()
    assert isinstance(exported, dict)
    assert "total_calls" in exported
    assert exported["total_calls"] == 1
    assert "samples" in exported
    assert len(exported["samples"]) == 1
