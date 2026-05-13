"""Integration test: fail-closed when real CLI missing and mock disallowed."""
from pathlib import Path

from crewai_multicli_factory.config import FactoryConfig
from crewai_multicli_factory.executors.executor_router import ExecutorRouter
from crewai_multicli_factory.executors.base_executor import BaseExecutor
from crewai_multicli_factory.schemas import (
    ExecutionBackend,
    ExecutionRequest,
    Language,
    PipelineMode,
    TaskType,
)


class _Missing(BaseExecutor):
    def __init__(self, backend):
        self.backend = backend
        self.is_mock = False

    def is_available(self) -> bool:
        return False

    def execute(self, request):
        raise NotImplementedError


def test_router_fail_closed_no_mock_allowed(tmp_path: Path):
    cfg = FactoryConfig()
    router = ExecutorRouter(
        cfg,
        codex=_Missing(ExecutionBackend.CODEX),
        claude=_Missing(ExecutionBackend.CLAUDE_CODE),
        allow_mock=False,
    )
    req = ExecutionRequest(
        task_id="T", repo_path=str(tmp_path), prompt="x",
        task_type=TaskType.SCAFFOLD, language=Language.PYTHON,
        mode=PipelineMode.DRY_RUN, backend=ExecutionBackend.AUTO,
    )
    result, decision = router.execute(req)
    assert result.success is False
    assert result.error_type == "cli_missing_fail_closed"
    assert "fail-closed" in decision.reason or "missing" in decision.reason
