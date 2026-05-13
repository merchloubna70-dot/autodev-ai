"""Tests for budget-aware routing in ExecutorRouter (Agent D)."""
from autodev.config import FactoryConfig
from autodev.executors.base_executor import BaseExecutor
from autodev.executors.executor_router import ExecutorRouter
from autodev.executors.mock_codex_executor import MockCodexExecutor
from autodev.executors.mock_claude_executor import MockClaudeExecutor
from autodev.schemas import (
    BudgetHint,
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
        repo_path="/tmp/_budget_test",
        prompt="test prompt " * 20,
        task_type=task_type,
        risk_level=RiskLevel.LOW,
        language=Language.PYTHON,
        backend=ExecutionBackend.AUTO,
        allowed_files=["a", "b", "c", "d", "e", "f", "g", "h"],  # many files -> normally Claude
    )
    base.update(kwargs)
    return ExecutionRequest(**base)


def test_no_budget_feature_with_many_files_routes_to_claude():
    """Without budget hint, many files pushes FEATURE to Claude (baseline)."""
    router = _mock_router()
    decision = router.decide(_req(task_type=TaskType.FEATURE))
    assert decision.selected_backend in (ExecutionBackend.CLAUDE_CODE, ExecutionBackend.MOCK_CLAUDE)


def test_prefer_cheaper_biases_feature_to_codex():
    """With prefer_cheaper_backend=True, FEATURE routes to CODEX/MOCK_CODEX."""
    router = _mock_router()
    router.set_budget(BudgetHint(prefer_cheaper_backend=True))
    decision = router.decide(_req(task_type=TaskType.FEATURE, task_id="F1"))
    assert decision.selected_backend in (ExecutionBackend.CODEX, ExecutionBackend.MOCK_CODEX)


def test_prefer_cheaper_biases_integration_to_codex():
    """With prefer_cheaper_backend=True, INTEGRATION routes to CODEX/MOCK_CODEX."""
    router = _mock_router()
    router.set_budget(BudgetHint(prefer_cheaper_backend=True))
    decision = router.decide(_req(task_type=TaskType.INTEGRATION, task_id="I1"))
    assert decision.selected_backend in (ExecutionBackend.CODEX, ExecutionBackend.MOCK_CODEX)


def test_prefer_cheaper_biases_refactor_to_codex():
    """With prefer_cheaper_backend=True, REFACTOR routes to CODEX/MOCK_CODEX."""
    router = _mock_router()
    router.set_budget(BudgetHint(prefer_cheaper_backend=True))
    decision = router.decide(_req(task_type=TaskType.REFACTOR, task_id="R1"))
    assert decision.selected_backend in (ExecutionBackend.CODEX, ExecutionBackend.MOCK_CODEX)


def test_architecture_not_affected_by_budget():
    """ARCHITECTURE always routes to Claude regardless of budget hint."""
    router = _mock_router()
    router.set_budget(BudgetHint(prefer_cheaper_backend=True))
    decision = router.decide(_req(task_type=TaskType.ARCHITECTURE, task_id="A1"))
    assert decision.selected_backend in (ExecutionBackend.CLAUDE_CODE, ExecutionBackend.MOCK_CLAUDE)


def test_security_not_affected_by_budget():
    """SECURITY always routes to Claude regardless of budget hint."""
    router = _mock_router()
    router.set_budget(BudgetHint(prefer_cheaper_backend=True))
    decision = router.decide(_req(task_type=TaskType.SECURITY, task_id="SEC1"))
    assert decision.selected_backend in (ExecutionBackend.CLAUDE_CODE, ExecutionBackend.MOCK_CLAUDE)


def test_release_not_affected_by_budget():
    """RELEASE always routes to Claude regardless of budget hint."""
    router = _mock_router()
    router.set_budget(BudgetHint(prefer_cheaper_backend=True))
    decision = router.decide(_req(task_type=TaskType.RELEASE, task_id="REL1"))
    assert decision.selected_backend in (ExecutionBackend.CLAUDE_CODE, ExecutionBackend.MOCK_CLAUDE)


def test_docs_not_affected_by_budget():
    """DOCS always routes to Claude regardless of budget hint."""
    router = _mock_router()
    router.set_budget(BudgetHint(prefer_cheaper_backend=True))
    decision = router.decide(_req(task_type=TaskType.DOCS, task_id="D1"))
    assert decision.selected_backend in (ExecutionBackend.CLAUDE_CODE, ExecutionBackend.MOCK_CLAUDE)


def test_budget_exhausted_biases_feature_to_codex():
    """When remaining budget < avg call cost (1 cent), FEATURE biases to Codex."""
    router = _mock_router()
    # Set a max budget of 0.5 cents — smaller than avg cost (1 cent)
    router.set_budget(BudgetHint(max_cost_cents=0.5))
    decision = router.decide(_req(task_type=TaskType.FEATURE, task_id="F1"))
    assert decision.selected_backend in (ExecutionBackend.CODEX, ExecutionBackend.MOCK_CODEX)


def test_set_budget_updates_router_budget():
    router = _mock_router()
    hint = BudgetHint(prefer_cheaper_backend=True, max_cost_cents=10.0)
    router.set_budget(hint)
    assert router.budget.prefer_cheaper_backend is True
    assert router.budget.max_cost_cents == 10.0
