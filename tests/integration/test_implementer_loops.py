"""Integration tests for ImplementerAgent W2 loops.

Tests architect_editor_split, post_edit_lint, and evaluator_optimizer_iters
using FACTORY_FORCE_MOCK=1 to stay fully offline.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from autodev.agents.implementer import ImplementerAgent
from autodev.schemas import (
    DeliveryTask,
    ExecutionBackend,
    Language,
    PipelineMode,
    RiskLevel,
    TaskType,
)
from autodev.state import RunState


@pytest.fixture(autouse=True)
def _force_mock(monkeypatch):
    monkeypatch.setenv("FACTORY_FORCE_MOCK", "1")


def _make_task(task_id: str = "T1", milestone_id: str = "M1") -> DeliveryTask:
    return DeliveryTask(
        task_id=task_id,
        milestone_id=milestone_id,
        title="Write hello world",
        description="Implement a hello world function in Python.",
        language=Language.PYTHON,
        task_type=TaskType.FEATURE,
        risk_level=RiskLevel.LOW,
        preferred_executor=ExecutionBackend.MOCK_CODEX,
        codex_prompt="Write hello world",
    )


@pytest.fixture()
def router():
    """Return a mock ExecutorRouter whose execute() returns a successful real result."""
    from autodev.executors.executor_router import RouterDecision
    from autodev.schemas import ExecutionResult, PipelineMode

    real_result = ExecutionResult(
        task_id="T1",
        milestone_id="M1",
        backend=ExecutionBackend.MOCK_CODEX,
        language=Language.PYTHON,
        command="mock-codex ...",
        exit_code=0,
        stdout="mock output",
        stderr="",
        success=True,
        mock_used=True,
        mode=PipelineMode.DRY_RUN,
    )

    decision = RouterDecision(
        selected_backend=ExecutionBackend.MOCK_CODEX,
        candidate_backends=[ExecutionBackend.MOCK_CODEX],
        reason="mock forced",
        fallback_used=False,
        mock_used=True,
    )

    r = MagicMock()
    r.execute.return_value = (real_result, decision)
    return r


@pytest.fixture()
def run(tmp_path):
    return RunState(repo_path=str(tmp_path))


class TestImplementerLoopsDefaults:
    def test_default_flags_off(self, router, run):
        """Default construction has all W2 flags off — run_milestone completes."""
        agent = ImplementerAgent(router=router)
        assert agent.architect_editor_split is False
        assert agent.post_edit_lint is False
        assert agent.evaluator_optimizer_iters == 0

    def test_run_milestone_no_loops(self, router, run):
        """With all flags off, run_milestone executes exactly once per task."""
        agent = ImplementerAgent(router=router)
        task = _make_task()
        result = agent.run_milestone(
            milestone_id="M1",
            tasks=[task],
            run=run,
            mode=PipelineMode.DRY_RUN,
            languages=[Language.PYTHON],
        )
        assert result.success
        assert router.execute.call_count == 1


class TestArchitectEditorSplit:
    def test_architect_plan_called(self, router, run):
        """With architect_editor_split=True, OpusConsultAgent.architect is consulted."""
        agent = ImplementerAgent(router=router, architect_editor_split=True)
        task = _make_task()

        with patch("autodev.agents.implementer.ImplementerAgent._architect_plan",
                   wraps=agent._architect_plan) as mock_plan:
            result = agent.run_milestone(
                milestone_id="M1",
                tasks=[task],
                run=run,
                mode=PipelineMode.DRY_RUN,
                languages=[Language.PYTHON],
            )
        assert result.success
        mock_plan.assert_called_once()

    def test_plan_context_injected_into_prompt(self, router, run):
        """Architect plan text is appended to the prompt sent to the router."""
        agent = ImplementerAgent(router=router, architect_editor_split=True)
        task = _make_task()

        with patch.object(agent, "_architect_plan", return_value="STEP1\nSTEP2"):
            agent.run_milestone(
                milestone_id="M1",
                tasks=[task],
                run=run,
                mode=PipelineMode.DRY_RUN,
                languages=[Language.PYTHON],
            )

        call_args = router.execute.call_args
        req = call_args[0][0]
        assert "STEP1" in req.prompt


class TestPostEditLint:
    def test_lint_gate_called_when_flag_on(self, router, run, tmp_path):
        """With post_edit_lint=True, _run_lint is invoked after execution."""
        agent = ImplementerAgent(router=router, post_edit_lint=True)
        task = _make_task()

        with patch.object(agent, "_run_lint", wraps=agent._run_lint) as mock_lint:
            result = agent.run_milestone(
                milestone_id="M1",
                tasks=[task],
                run=run,
                mode=PipelineMode.DRY_RUN,
                languages=[Language.PYTHON],
            )
        assert result.success
        mock_lint.assert_called()

    def test_lint_gate_not_called_when_flag_off(self, router, run):
        """With post_edit_lint=False (default), _run_lint is never called."""
        agent = ImplementerAgent(router=router, post_edit_lint=False)
        task = _make_task()

        with patch.object(agent, "_run_lint") as mock_lint:
            agent.run_milestone(
                milestone_id="M1",
                tasks=[task],
                run=run,
                mode=PipelineMode.DRY_RUN,
                languages=[Language.PYTHON],
            )
        mock_lint.assert_not_called()


class TestEvaluatorOptimizer:
    def test_critic_called_when_iters_set(self, router, run):
        """With evaluator_optimizer_iters=2, CriticAgent.evaluate is called."""
        agent = ImplementerAgent(router=router, evaluator_optimizer_iters=2)
        task = _make_task()

        critic_calls = []

        def fake_critic_loop(initial_result, **kwargs):
            critic_calls.append(initial_result)
            return initial_result

        with patch.object(agent, "_critic_loop", side_effect=fake_critic_loop):
            result = agent.run_milestone(
                milestone_id="M1",
                tasks=[task],
                run=run,
                mode=PipelineMode.DRY_RUN,
                languages=[Language.PYTHON],
            )
        assert result.success
        assert len(critic_calls) == 1  # called once per successful task

    def test_critic_not_called_when_iters_zero(self, router, run):
        """With evaluator_optimizer_iters=0, critic loop is never entered."""
        agent = ImplementerAgent(router=router, evaluator_optimizer_iters=0)
        task = _make_task()

        with patch.object(agent, "_critic_loop") as mock_critic:
            agent.run_milestone(
                milestone_id="M1",
                tasks=[task],
                run=run,
                mode=PipelineMode.DRY_RUN,
                languages=[Language.PYTHON],
            )
        mock_critic.assert_not_called()

    def test_critic_capped_at_max(self, router, run):
        """evaluator_optimizer_iters is capped at _MAX_CRITIC_ITERS=3."""
        agent = ImplementerAgent(router=router, evaluator_optimizer_iters=99)
        assert agent.evaluator_optimizer_iters == 3

    def test_all_flags_together(self, router, run):
        """All three flags can be enabled simultaneously without error."""
        agent = ImplementerAgent(
            router=router,
            architect_editor_split=True,
            post_edit_lint=True,
            evaluator_optimizer_iters=2,
        )
        task = _make_task()

        # Stub all sub-methods to avoid real filesystem/process calls
        with patch.object(agent, "_architect_plan", return_value="plan"), \
             patch.object(agent, "_run_lint") as mock_lint, \
             patch.object(agent, "_critic_loop", side_effect=lambda r, **kw: r):
            from autodev.schemas import LintGateResult
            mock_lint.return_value = LintGateResult(language="python", ok=True)
            result = agent.run_milestone(
                milestone_id="M1",
                tasks=[task],
                run=run,
                mode=PipelineMode.DRY_RUN,
                languages=[Language.PYTHON],
            )
        assert result.success
