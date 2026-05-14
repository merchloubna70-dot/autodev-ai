"""Tests for SelfMcpAgent.

All tests operate in FACTORY_FORCE_MOCK=1 mode or via injected mock clients,
so no subprocess is ever spawned.
"""
from __future__ import annotations

import os
from typing import Any
from unittest.mock import MagicMock

import pytest

os.environ.setdefault("FACTORY_FORCE_MOCK", "1")

from autodev.adapters.self_mcp_client import SelfMcpClient  # noqa: E402
from autodev.agents.self_mcp_agent import SelfMcpAgent, SelfMcpResult  # noqa: E402

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_client(
    call_tool_return: dict[str, Any] | None = None,
    list_tools_return: list[dict[str, Any]] | None = None,
) -> MagicMock:
    """Build a mock SelfMcpClient that returns controlled values."""
    client = MagicMock(spec=SelfMcpClient)
    client.call_tool.return_value = call_tool_return or {
        "tool_name": "autodev_scan",
        "success": True,
        "response_text": '{"files": ["a.py", "b.py"]}',
        "error": None,
        "duration_ms": 42,
        "mock_used": True,
    }
    client.list_tools.return_value = list_tools_return or [
        {"name": "autodev_scan", "description": "Scan dir"},
        {"name": "autodev_list_runs", "description": "List runs"},
    ]
    return client


# ---------------------------------------------------------------------------
# Test 1: Agent can call a tool via mock client
# ---------------------------------------------------------------------------


class TestSelfMcpAgentCallViaClient:
    """Verify that SelfMcpAgent properly delegates to the client."""

    def test_run_delegates_to_client_call_tool(self) -> None:
        mock_client = _make_mock_client()
        agent = SelfMcpAgent(client=mock_client)

        result = agent.run(
            question="What files exist?",
            tool_name="autodev_scan",
            tool_args={"path": "."},
        )

        mock_client.call_tool.assert_called_once_with("autodev_scan", {"path": "."})
        assert isinstance(result, SelfMcpResult)

    def test_list_tools_delegates_to_client(self) -> None:
        mock_client = _make_mock_client()
        agent = SelfMcpAgent(client=mock_client)

        tools = agent.list_tools()

        mock_client.list_tools.assert_called_once()
        assert len(tools) == 2

    def test_run_for_roundtable_returns_string(self) -> None:
        # Use a mock client that returns the tool name we pass in
        call_return = {
            "tool_name": "autodev_list_runs",
            "success": True,
            "response_text": "[]",
            "error": None,
            "duration_ms": 5,
            "mock_used": True,
        }
        mock_client = _make_mock_client(call_tool_return=call_return)
        agent = SelfMcpAgent(client=mock_client)

        text = agent.run_for_roundtable(
            question="List runs",
            tool_name="autodev_list_runs",
            tool_args={},
        )

        assert isinstance(text, str)
        assert "autodev_list_runs" in text


# ---------------------------------------------------------------------------
# Test 2: Agent returns structured result
# ---------------------------------------------------------------------------


class TestSelfMcpAgentStructuredResult:
    """Verify SelfMcpResult has the expected fields and values."""

    def test_result_fields_populated(self) -> None:
        call_return = {
            "tool_name": "autodev_scan",
            "success": True,
            "response_text": '{"ok": true}',
            "error": None,
            "duration_ms": 99,
            "mock_used": False,
        }
        mock_client = _make_mock_client(call_tool_return=call_return)
        agent = SelfMcpAgent(client=mock_client)

        result = agent.run(
            question="Run a scan",
            tool_name="autodev_scan",
            tool_args={"path": "/tmp"},
        )

        assert result.tool_name == "autodev_scan"
        assert result.success is True
        assert result.response_text == '{"ok": true}'
        assert result.error is None
        assert result.duration_ms == 99
        assert result.mock_used is False
        assert result.question == "Run a scan"

    def test_roundtable_text_includes_key_info(self) -> None:
        call_return = {
            "tool_name": "autodev_scan",
            "success": True,
            "response_text": "scan output",
            "error": None,
            "duration_ms": 5,
            "mock_used": True,
        }
        mock_client = _make_mock_client(call_tool_return=call_return)
        agent = SelfMcpAgent(client=mock_client)

        result = agent.run(question="Scan the project", tool_name="autodev_scan")
        text = result.as_roundtable_text()

        assert "autodev_scan" in text
        assert "OK" in text
        assert "scan output" in text
        assert "Scan the project" in text

    def test_result_contains_question_field(self) -> None:
        mock_client = _make_mock_client()
        agent = SelfMcpAgent(client=mock_client)
        result = agent.run(question="Why?", tool_name="autodev_list_runs")
        assert result.question == "Why?"

    def test_default_tool_args_is_empty_dict(self) -> None:
        """When tool_args is omitted, an empty dict is passed to the client."""
        mock_client = _make_mock_client()
        agent = SelfMcpAgent(client=mock_client)
        agent.run(question="q", tool_name="autodev_list_runs")
        mock_client.call_tool.assert_called_once_with("autodev_list_runs", None)


# ---------------------------------------------------------------------------
# Test 3: Agent handles tool errors gracefully
# ---------------------------------------------------------------------------


class TestSelfMcpAgentErrorHandling:
    """Verify that tool-level errors produce success=False results, not exceptions."""

    def test_tool_error_returns_failure_result(self) -> None:
        error_return = {
            "tool_name": "bad_tool",
            "success": False,
            "response_text": "",
            "error": "Tool not found: bad_tool",
            "duration_ms": 3,
            "mock_used": False,
        }
        mock_client = _make_mock_client(call_tool_return=error_return)
        agent = SelfMcpAgent(client=mock_client)

        result = agent.run(question="call broken tool", tool_name="bad_tool")

        assert result.success is False
        assert result.error == "Tool not found: bad_tool"
        assert result.response_text == ""

    def test_tool_error_roundtable_text_shows_error_status(self) -> None:
        error_return = {
            "tool_name": "bad_tool",
            "success": False,
            "response_text": "",
            "error": "Internal server error",
            "duration_ms": 1,
            "mock_used": False,
        }
        mock_client = _make_mock_client(call_tool_return=error_return)
        agent = SelfMcpAgent(client=mock_client)

        result = agent.run(question="test", tool_name="bad_tool")
        text = result.as_roundtable_text()

        assert "ERROR" in text
        assert "Internal server error" in text

    def test_client_exception_propagates_as_error(self) -> None:
        """If SelfMcpClient.call_tool raises, the exception should propagate."""
        mock_client = _make_mock_client()
        mock_client.call_tool.side_effect = RuntimeError("connection lost")
        agent = SelfMcpAgent(client=mock_client)

        with pytest.raises(RuntimeError, match="connection lost"):
            agent.run(question="q", tool_name="autodev_scan")

    def test_agent_does_not_close_external_client(self) -> None:
        """Externally supplied clients are not closed by the agent."""
        mock_client = _make_mock_client()
        agent = SelfMcpAgent(client=mock_client)
        agent.close()
        mock_client.close.assert_not_called()

    def test_agent_closes_internal_client_on_close(self) -> None:
        """Internally created clients are closed when the agent is closed."""
        os.environ["FACTORY_FORCE_MOCK"] = "1"
        agent = SelfMcpAgent()
        # Patch the internally created client to track close()
        internal_client_mock = MagicMock(spec=SelfMcpClient)
        agent._client = internal_client_mock
        agent._external_client = False

        agent.close()
        internal_client_mock.close.assert_called_once()

    def test_mock_mode_end_to_end(self) -> None:
        """Full smoke-test with FACTORY_FORCE_MOCK=1 — no mocking needed."""
        os.environ["FACTORY_FORCE_MOCK"] = "1"
        agent = SelfMcpAgent()  # uses real SelfMcpClient in mock mode
        result = agent.run(
            question="List all tools",
            tool_name="autodev_scan",
            tool_args={"path": "."},
        )
        assert result.mock_used is True
        assert result.success is True
        assert result.tool_name == "autodev_scan"
        agent.close()
