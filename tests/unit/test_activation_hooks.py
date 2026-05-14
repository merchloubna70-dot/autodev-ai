"""BMAD-16: Tests for ActivatableAgent activation hooks."""
from __future__ import annotations

import pytest

from autodev.agents._activation import ActivatableAgent, ActivationContext
from autodev.schemas import ActivationResult


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


class _SimpleAgent(ActivatableAgent):
    """Minimal agent with a .run() method for testing."""

    call_log: list[str]

    def __init__(self) -> None:
        self.call_log = []
        # Use instance-level lists so tests don't share state
        self.activation_steps_prepend = []
        self.activation_steps_append = []

    def run(self, **kwargs: object) -> str:
        self.call_log.append("run")
        return "run-ok"


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_prepend_runs_before_run() -> None:
    """Prepend hooks must execute before .run() is called."""
    order: list[str] = []

    def pre(ctx: ActivationContext) -> None:
        order.append("prepend")

    agent = _SimpleAgent()
    agent.activation_steps_prepend = [pre]

    # monkey-patch run to record order
    original_run = agent.run

    def patched_run(**kw: object) -> str:
        order.append("run")
        return original_run(**kw)

    agent.run = patched_run  # type: ignore[method-assign]

    result = agent.activate()
    assert order.index("prepend") < order.index("run")
    assert result.success is True
    assert "pre" in result.prepend_steps_run[0]


def test_append_runs_after_run() -> None:
    """Append hooks must execute after .run() returns."""
    order: list[str] = []

    agent = _SimpleAgent()

    original_run = agent.run

    def patched_run(**kw: object) -> str:
        order.append("run")
        return original_run(**kw)

    agent.run = patched_run  # type: ignore[method-assign]

    def post(ctx: ActivationContext) -> None:
        order.append("append")

    agent.activation_steps_append = [post]

    result = agent.activate()
    assert order.index("run") < order.index("append")
    assert "post" in result.append_steps_run[0]


def test_activation_result_captures_timing() -> None:
    """ActivationResult.duration_ms must be non-negative."""
    agent = _SimpleAgent()
    result = agent.activate()
    assert isinstance(result, ActivationResult)
    assert result.duration_ms >= 0


def test_hook_failure_returns_success_false_no_raise() -> None:
    """A failing prepend hook must set success=False but not raise."""
    def bad_hook(ctx: ActivationContext) -> None:
        raise RuntimeError("hook error")

    agent = _SimpleAgent()
    agent.activation_steps_prepend = [bad_hook]

    result = agent.activate()
    assert result.success is False
    assert any("hook error" in e for e in result.errors)


def test_multiple_prepend_hooks_run_in_order() -> None:
    """Multiple prepend hooks must run in registration order."""
    order: list[int] = []

    def h1(ctx: ActivationContext) -> None:
        order.append(1)

    def h2(ctx: ActivationContext) -> None:
        order.append(2)

    def h3(ctx: ActivationContext) -> None:
        order.append(3)

    agent = _SimpleAgent()
    agent.activation_steps_prepend = [h1, h2, h3]

    result = agent.activate()
    assert order == [1, 2, 3]
    assert result.success is True
    assert len(result.prepend_steps_run) == 3


def test_activation_result_has_agent_name() -> None:
    """ActivationResult.agent_name should reflect the class."""
    agent = _SimpleAgent()
    result = agent.activate()
    assert result.agent_name  # non-empty string


def test_append_hook_failure_does_not_swallow_run_result() -> None:
    """Even if an append hook fails, the run result summary should be recorded."""
    def bad_append(ctx: ActivationContext) -> None:
        raise ValueError("append boom")

    agent = _SimpleAgent()
    agent.activation_steps_append = [bad_append]
    result = agent.activate()
    # run itself succeeded, so result_summary should be populated
    assert "run-ok" in result.result_summary
    # but success is False due to append error
    assert result.success is False
