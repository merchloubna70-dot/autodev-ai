"""Tests for LocalShellTransport, MockTransport, and A2AClient."""
from __future__ import annotations

import pytest

from autodev.adapters.a2a.client import A2AClient
from autodev.adapters.a2a.transports.local_shell import LocalShellTransport
from autodev.adapters.a2a.transports.mock import MockTransport
from autodev.schemas import (
    A2AMessage,
    A2APart,
    A2ATask,
    A2ATaskStatus,
    AgentCard,
)


def _make_task(prompt: str, task_id: str = "t-1", context_id: str = "ctx-1") -> A2ATask:
    msg = A2AMessage(
        message_id="m-1",
        role="user",
        parts=[A2APart(kind="text", text=prompt)],
        task_id=task_id,
        context_id=context_id,
    )
    return A2ATask(id=task_id, context_id=context_id, history=[msg])


def _make_card(name: str = "test-agent", system_prompt: str | None = None, model_hint: str | None = "sonnet") -> AgentCard:
    return AgentCard(
        name=name,
        transport="local-shell",
        model_hint=model_hint,
        system_prompt=system_prompt,
    )


# --------------------------------------------------------------------------
# LocalShellTransport with FACTORY_FORCE_MOCK=1
# --------------------------------------------------------------------------

def test_force_mock_returns_mock_local_shell_prefix(monkeypatch):
    monkeypatch.setenv("FACTORY_FORCE_MOCK", "1")
    transport = LocalShellTransport()
    card = _make_card("architect")
    task = _make_task("Review this PR")
    result = transport.send_task(card, task)
    assert result.status == A2ATaskStatus.COMPLETED
    # Find the agent response in history
    agent_msgs = [m for m in result.history if m.role == "agent"]
    assert len(agent_msgs) == 1
    text = agent_msgs[0].parts[0].text
    assert text is not None
    assert "[MOCK-LOCAL-SHELL:architect]" in text


def test_force_mock_deterministic_same_input(monkeypatch):
    monkeypatch.setenv("FACTORY_FORCE_MOCK", "1")
    transport = LocalShellTransport()
    card = _make_card("security")
    task1 = _make_task("Check for SQL injection")
    task2 = _make_task("Check for SQL injection")
    r1 = transport.send_task(card, task1)
    r2 = transport.send_task(card, task2)
    text1 = next(m for m in r1.history if m.role == "agent").parts[0].text
    text2 = next(m for m in r2.history if m.role == "agent").parts[0].text
    assert text1 == text2


def test_force_mock_different_inputs_differ(monkeypatch):
    monkeypatch.setenv("FACTORY_FORCE_MOCK", "1")
    transport = LocalShellTransport()
    card = _make_card("security")
    r1 = transport.send_task(card, _make_task("prompt A"))
    r2 = transport.send_task(card, _make_task("prompt B"))
    text1 = next(m for m in r1.history if m.role == "agent").parts[0].text
    text2 = next(m for m in r2.history if m.role == "agent").parts[0].text
    assert text1 != text2


def test_force_mock_different_card_names_differ(monkeypatch):
    monkeypatch.setenv("FACTORY_FORCE_MOCK", "1")
    transport = LocalShellTransport()
    same_prompt = "Analyze this code"
    r1 = transport.send_task(_make_card("architect"), _make_task(same_prompt))
    r2 = transport.send_task(_make_card("security"), _make_task(same_prompt))
    text1 = next(m for m in r1.history if m.role == "agent").parts[0].text
    text2 = next(m for m in r2.history if m.role == "agent").parts[0].text
    assert text1 != text2


def test_force_mock_task_has_artifact(monkeypatch):
    monkeypatch.setenv("FACTORY_FORCE_MOCK", "1")
    transport = LocalShellTransport()
    card = _make_card("style")
    task = _make_task("Check style")
    result = transport.send_task(card, task)
    assert len(result.artifacts) >= 1
    assert result.artifacts[-1].kind == "text"
    assert "[MOCK-LOCAL-SHELL:style]" in result.artifacts[-1].text


def test_force_mock_reads_card_system_prompt(monkeypatch):
    """Transport picks up card.system_prompt (mock path just encodes card name)."""
    monkeypatch.setenv("FACTORY_FORCE_MOCK", "1")
    transport = LocalShellTransport()
    card = AgentCard(
        name="custom-agent",
        transport="local-shell",
        model_hint="haiku",
        system_prompt="You are a haiku writer. Write only haiku.",
    )
    task = _make_task("Write something")
    result = transport.send_task(card, task)
    # The mock response is keyed on card.name — confirms system_prompt card was used
    agent_msg = next(m for m in result.history if m.role == "agent")
    assert "[MOCK-LOCAL-SHELL:custom-agent]" in agent_msg.parts[0].text


# --------------------------------------------------------------------------
# Failed shell — returns FAILED status (no exception raised)
# --------------------------------------------------------------------------

def test_failed_shell_returns_failed_status(monkeypatch):
    """When shell exits non-zero with no output, task should be FAILED."""
    monkeypatch.delenv("FACTORY_FORCE_MOCK", raising=False)
    transport = LocalShellTransport(binary="nonexistent-binary-xyz-404")
    # Ensure shutil.which returns None for fake binary
    card = _make_card("arch")
    task = _make_task("analyze")
    # Since binary doesn't exist, _should_mock returns True (shutil.which is None)
    # which means it'll return mock. Let's patch _should_mock to False and _run_claude to fail.
    import unittest.mock as mock
    with mock.patch.object(transport, "_should_mock", return_value=False):
        with mock.patch.object(transport, "_run_claude", return_value=(127, "")):
            result = transport.send_task(card, task)
    assert result.status == A2ATaskStatus.FAILED
    # No exception raised
    assert len(result.artifacts) >= 1


def test_no_exception_even_on_internal_error(monkeypatch):
    """send_task must never raise — errors go into task.status=FAILED."""
    monkeypatch.delenv("FACTORY_FORCE_MOCK", raising=False)
    transport = LocalShellTransport()
    import unittest.mock as mock
    with mock.patch.object(transport, "_should_mock", return_value=False):
        with mock.patch.object(transport, "_run_claude", side_effect=RuntimeError("boom")):
            # Should not raise
            try:
                transport.send_task(_make_card(), _make_task("test"))
                # Either FAILED or COMPLETED is acceptable; must not raise
            except Exception:
                pytest.fail("send_task raised an exception — it must not")


# --------------------------------------------------------------------------
# MockTransport — pure deterministic
# --------------------------------------------------------------------------

def test_mock_transport_pure(monkeypatch):
    monkeypatch.delenv("FACTORY_FORCE_MOCK", raising=False)
    transport = MockTransport()
    card = _make_card("pure-mock")
    task = _make_task("test prompt")
    result = transport.send_task(card, task)
    assert result.status == A2ATaskStatus.COMPLETED
    agent_msgs = [m for m in result.history if m.role == "agent"]
    assert len(agent_msgs) == 1
    assert "[MOCK:pure-mock]" in agent_msgs[0].parts[0].text


def test_mock_transport_deterministic(monkeypatch):
    transport = MockTransport()
    card = _make_card("det-agent")
    r1 = transport.send_task(card, _make_task("same prompt"))
    r2 = transport.send_task(card, _make_task("same prompt"))
    t1 = next(m for m in r1.history if m.role == "agent").parts[0].text
    t2 = next(m for m in r2.history if m.role == "agent").parts[0].text
    assert t1 == t2


def test_mock_transport_never_shells(monkeypatch):
    """MockTransport should not import or call subprocess."""
    import unittest.mock as mock
    transport = MockTransport()
    with mock.patch("subprocess.run", side_effect=AssertionError("subprocess.run called!")):
        result = transport.send_task(_make_card("no-shell"), _make_task("hello"))
    assert result.status == A2ATaskStatus.COMPLETED


# --------------------------------------------------------------------------
# A2AClient dispatch
# --------------------------------------------------------------------------

def test_a2a_client_dispatches_to_mock_transport(monkeypatch):
    monkeypatch.setenv("FACTORY_FORCE_MOCK", "1")
    client = A2AClient()
    card = AgentCard(name="mock-agent", transport="mock")
    task = _make_task("dispatch test")
    result = client.send(card, task)
    assert result.status == A2ATaskStatus.COMPLETED


def test_a2a_client_dispatches_to_local_shell(monkeypatch):
    monkeypatch.setenv("FACTORY_FORCE_MOCK", "1")
    client = A2AClient()
    card = AgentCard(name="local-agent", transport="local-shell", model_hint="sonnet")
    task = _make_task("local shell dispatch")
    result = client.send(card, task)
    assert result.status == A2ATaskStatus.COMPLETED
    agent_msgs = [m for m in result.history if m.role == "agent"]
    assert "[MOCK-LOCAL-SHELL:local-agent]" in agent_msgs[0].parts[0].text


def test_a2a_client_caches_transport_instances(monkeypatch):
    monkeypatch.setenv("FACTORY_FORCE_MOCK", "1")
    client = A2AClient()
    card = AgentCard(name="cached", transport="mock")
    task1 = _make_task("first")
    task2 = _make_task("second")
    client.send(card, task1)
    client.send(card, task2)
    # Same transport instance used both times
    assert "mock" in client._transport_cache


def test_a2a_client_unknown_transport_falls_back_to_mock(monkeypatch):
    monkeypatch.setenv("FACTORY_FORCE_MOCK", "1")
    client = A2AClient()
    card = AgentCard(name="fallback", transport="a2a-http-unimplemented")
    task = _make_task("fallback test")
    result = client.send(card, task)
    # Falls back to MockTransport — should succeed
    assert result.status == A2ATaskStatus.COMPLETED
