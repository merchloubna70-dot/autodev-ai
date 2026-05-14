"""Tests for ExecutorRouter routing decisions and fail-closed behavior."""
from autodev.config import FactoryConfig
from autodev.executors.base_executor import BaseExecutor
from autodev.executors.executor_router import ExecutorRouter
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

    def execute(self, request):  # pragma: no cover - not used in decide
        raise NotImplementedError


def _router(*, codex_ok=True, claude_ok=True, allow_mock=True):
    cfg = FactoryConfig()
    return ExecutorRouter(
        cfg,
        codex=_FakeAvailable(ExecutionBackend.CODEX, codex_ok),
        claude=_FakeAvailable(ExecutionBackend.CLAUDE_CODE, claude_ok),
        allow_mock=allow_mock,
    )


def _req(**overrides):
    base = dict(
        task_id="T1", repo_path="/tmp/_router_test", prompt="p", task_type=TaskType.FEATURE,
        risk_level=RiskLevel.LOW, language=Language.PYTHON, backend=ExecutionBackend.AUTO,
    )
    base.update(overrides)
    return ExecutionRequest(**base)


def test_scaffold_goes_to_codex():
    d = _router().decide(_req(task_type=TaskType.SCAFFOLD))
    assert d.selected_backend == ExecutionBackend.CODEX


def test_test_task_goes_to_codex():
    d = _router().decide(_req(task_type=TaskType.TEST))
    assert d.selected_backend == ExecutionBackend.CODEX


def test_architecture_goes_to_claude():
    d = _router().decide(_req(task_type=TaskType.ARCHITECTURE))
    assert d.selected_backend == ExecutionBackend.CLAUDE_CODE


def test_high_risk_refactor_goes_to_claude():
    d = _router().decide(_req(task_type=TaskType.REFACTOR, risk_level=RiskLevel.HIGH))
    assert d.selected_backend == ExecutionBackend.CLAUDE_CODE


def test_cross_language_integration_goes_to_claude():
    d = _router().decide(_req(task_type=TaskType.INTEGRATION), cross_language=True)
    assert d.selected_backend == ExecutionBackend.CLAUDE_CODE


def test_single_language_integration_goes_to_codex():
    d = _router().decide(_req(task_type=TaskType.INTEGRATION), cross_language=False)
    assert d.selected_backend == ExecutionBackend.CODEX


def test_explicit_codex_respected():
    d = _router().decide(_req(backend=ExecutionBackend.CODEX, task_type=TaskType.REFACTOR))
    assert d.selected_backend == ExecutionBackend.CODEX


def test_explicit_claude_respected():
    d = _router().decide(_req(backend=ExecutionBackend.CLAUDE_CODE, task_type=TaskType.SCAFFOLD))
    assert d.selected_backend == ExecutionBackend.CLAUDE_CODE


def test_falls_back_to_mock_codex_when_missing():
    d = _router(codex_ok=False).decide(_req(task_type=TaskType.SCAFFOLD))
    assert d.selected_backend == ExecutionBackend.MOCK_CODEX
    assert d.fallback_used and d.mock_used


def test_falls_back_to_mock_claude_when_missing():
    d = _router(claude_ok=False).decide(_req(task_type=TaskType.ARCHITECTURE))
    assert d.selected_backend == ExecutionBackend.MOCK_CLAUDE
    assert d.fallback_used and d.mock_used


def test_fail_closed_when_mock_disallowed():
    r = _router(codex_ok=False, allow_mock=False)
    r.decide(_req(task_type=TaskType.SCAFFOLD))
    # decide() keeps the preferred backend; execute() must fail-closed.
    result, _ = r.execute(_req(task_type=TaskType.SCAFFOLD))
    assert result.success is False
    assert result.error_type == "cli_missing_fail_closed"


def test_many_files_pushes_feature_to_claude():
    req = _req(task_type=TaskType.FEATURE, risk_level=RiskLevel.LOW)
    req.allowed_files = ["a", "b", "c", "d", "e", "f", "g"]
    d = _router().decide(req)
    assert d.selected_backend == ExecutionBackend.CLAUDE_CODE
