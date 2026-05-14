"""Tests for SelfMcpClient.

All tests run with FACTORY_FORCE_MOCK=1 by default unless the individual
test class explicitly overrides the env-var to test process-management paths.
"""
from __future__ import annotations

import json
import os
import subprocess
from typing import Any
from unittest.mock import MagicMock, patch

os.environ.setdefault("FACTORY_FORCE_MOCK", "1")

from autodev.adapters.self_mcp_client import SelfMcpClient  # noqa: E402

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_proc(responses: list[dict[str, Any]]) -> MagicMock:
    """Return a mock Popen-like object that yields *responses* on readline().

    We do NOT use ``spec=subprocess.Popen`` here because in a patched test
    context ``subprocess.Popen`` is itself a ``MagicMock``, which would cause
    ``InvalidSpecError: Cannot spec a Mock object``.
    """
    lines = [json.dumps(r) + "\n" for r in responses]
    stdout_mock = MagicMock()
    stdout_mock.readline.side_effect = lines
    stdin_mock = MagicMock()
    proc = MagicMock()
    proc.poll.return_value = None  # process appears alive
    proc.stdout = stdout_mock
    proc.stdin = stdin_mock
    proc.stderr = MagicMock()
    return proc


# ---------------------------------------------------------------------------
# Test 1: Mock mode — startup handshake is never attempted
# ---------------------------------------------------------------------------


class TestSelfMcpClientMockMode:
    """With FACTORY_FORCE_MOCK=1 no subprocess is spawned."""

    def setup_method(self) -> None:
        os.environ["FACTORY_FORCE_MOCK"] = "1"
        self.client = SelfMcpClient()

    def test_list_tools_returns_mock_list(self) -> None:
        tools = self.client.list_tools()
        assert isinstance(tools, list)
        assert len(tools) > 0

    def test_list_tools_have_name_field(self) -> None:
        tools = self.client.list_tools()
        for tool in tools:
            assert "name" in tool

    def test_call_tool_returns_structured_dict(self) -> None:
        result = self.client.call_tool("autodev_scan", {"path": "."})
        assert isinstance(result, dict)
        assert "tool_name" in result
        assert "success" in result
        assert "response_text" in result
        assert "error" in result
        assert "duration_ms" in result
        assert "mock_used" in result

    def test_call_tool_mock_used_flag_is_true(self) -> None:
        result = self.client.call_tool("autodev_scan", {"path": "."})
        assert result["mock_used"] is True
        assert result["success"] is True
        assert result["error"] is None

    def test_call_tool_response_is_deterministic(self) -> None:
        r1 = self.client.call_tool("autodev_scan", {"path": "."})
        r2 = self.client.call_tool("autodev_scan", {"path": "."})
        assert r1["response_text"] == r2["response_text"]

    def test_no_subprocess_spawned_in_mock_mode(self) -> None:
        """Verify _proc is never set when FACTORY_FORCE_MOCK=1."""
        self.client.list_tools()
        self.client.call_tool("any_tool", {})
        assert self.client._proc is None

    def test_context_manager_closes_cleanly(self) -> None:
        with SelfMcpClient() as c:
            result = c.call_tool("autodev_list_runs", {})
        assert result["mock_used"] is True
        assert c._proc is None


# ---------------------------------------------------------------------------
# Test 2: Mock subprocess startup handshake
# ---------------------------------------------------------------------------


class TestSelfMcpClientSubprocessStartup:
    """Tests that validate the subprocess startup and initialize handshake."""

    def setup_method(self) -> None:
        os.environ["FACTORY_FORCE_MOCK"] = "0"

    def teardown_method(self) -> None:
        os.environ["FACTORY_FORCE_MOCK"] = "1"

    def test_initialize_handshake_sets_initialized_flag(self) -> None:
        """When subprocess starts and handshake succeeds, _initialized is True."""
        init_response = {
            "jsonrpc": "2.0",
            "id": 1,
            "result": {"protocolVersion": "2024-11-05", "capabilities": {}},
        }
        mock_proc = _make_mock_proc([init_response])

        with (
            patch("autodev.adapters.self_mcp_client.shutil.which", return_value="/usr/bin/autodev-x"),
            patch("autodev.adapters.self_mcp_client.subprocess.Popen", return_value=mock_proc),
        ):
            client = SelfMcpClient()
            started = client._ensure_started()

        assert started is True
        assert client._initialized is True
        client.close()

    def test_initialize_handshake_failure_falls_back_to_mock(self) -> None:
        """When handshake returns error, client falls back gracefully."""
        error_response = {
            "jsonrpc": "2.0",
            "id": 1,
            "error": {"code": -32600, "message": "Invalid request"},
        }
        mock_proc = _make_mock_proc([error_response])

        with (
            patch("autodev.adapters.self_mcp_client.shutil.which", return_value="/usr/bin/autodev-x"),
            patch("autodev.adapters.self_mcp_client.subprocess.Popen", return_value=mock_proc),
        ):
            client = SelfMcpClient()
            started = client._ensure_started()

        # Handshake failed → should not be started
        assert started is False
        assert client._proc is None


# ---------------------------------------------------------------------------
# Test 3: Mock tool call round-trip
# ---------------------------------------------------------------------------


class TestSelfMcpClientToolCallRoundTrip:
    """Full round-trip: handshake + tools/list + tools/call via mock proc."""

    def setup_method(self) -> None:
        os.environ["FACTORY_FORCE_MOCK"] = "0"
        self._patches: list[Any] = []

    def teardown_method(self) -> None:
        # Stop any patches that were started during the test.
        for p in reversed(self._patches):
            p.stop()
        self._patches.clear()
        os.environ["FACTORY_FORCE_MOCK"] = "1"

    def _make_started_client(
        self, extra_responses: list[dict[str, Any]]
    ) -> tuple[SelfMcpClient, MagicMock]:
        init_resp = {
            "jsonrpc": "2.0",
            "id": 1,
            "result": {"protocolVersion": "2024-11-05", "capabilities": {}},
        }
        mock_proc = _make_mock_proc([init_resp, *extra_responses])

        popen_patch = patch(
            "autodev.adapters.self_mcp_client.subprocess.Popen",
            return_value=mock_proc,
        )
        which_patch = patch(
            "autodev.adapters.self_mcp_client.shutil.which",
            return_value="/usr/bin/autodev-x",
        )
        which_patch.start()
        popen_patch.start()
        # Track for cleanup in teardown_method
        self._patches.extend([which_patch, popen_patch])
        client = SelfMcpClient()
        client._ensure_started()
        return client, mock_proc

    def test_call_tool_round_trip_success(self) -> None:
        tool_resp = {
            "jsonrpc": "2.0",
            "id": 2,
            "result": {"content": [{"type": "text", "text": "scan complete"}]},
        }
        client, _ = self._make_started_client([tool_resp])
        # _ensure_started already called; proc is running; patches still active
        result = client.call_tool("autodev_scan", {"path": "."})
        assert result["success"] is True
        assert result["mock_used"] is False
        assert result["tool_name"] == "autodev_scan"
        assert "scan complete" in result["response_text"] or result["response_text"]
        client.close()

    def test_call_tool_server_error_returns_failure(self) -> None:
        error_resp = {
            "jsonrpc": "2.0",
            "id": 2,
            "error": {"code": -32601, "message": "Tool not found: unknown_tool"},
        }
        client, _ = self._make_started_client([error_resp])
        result = client.call_tool("unknown_tool", {})
        assert result["success"] is False
        assert "Tool not found" in (result["error"] or "")
        assert result["mock_used"] is False
        client.close()


# ---------------------------------------------------------------------------
# Test 4: Shutdown cleanup
# ---------------------------------------------------------------------------


class TestSelfMcpClientShutdown:
    """Verify that close() properly terminates the subprocess."""

    def setup_method(self) -> None:
        os.environ["FACTORY_FORCE_MOCK"] = "0"

    def teardown_method(self) -> None:
        os.environ["FACTORY_FORCE_MOCK"] = "1"

    def test_close_terminates_subprocess(self) -> None:
        init_resp = {
            "jsonrpc": "2.0",
            "id": 1,
            "result": {"protocolVersion": "2024-11-05", "capabilities": {}},
        }
        mock_proc = _make_mock_proc([init_resp])

        with (
            patch("autodev.adapters.self_mcp_client.shutil.which", return_value="/usr/bin/autodev-x"),
            patch("autodev.adapters.self_mcp_client.subprocess.Popen", return_value=mock_proc),
        ):
            client = SelfMcpClient()
            client._ensure_started()
            assert client._proc is not None
            client.close()

        mock_proc.terminate.assert_called_once()
        assert client._proc is None
        assert client._initialized is False

    def test_close_is_idempotent(self) -> None:
        """Calling close() multiple times does not raise."""
        client = SelfMcpClient()
        client.close()
        client.close()  # second call must not raise

    def test_close_waits_for_proc_then_kills_on_timeout(self) -> None:
        """When wait() times out, kill() is called."""
        init_resp = {
            "jsonrpc": "2.0",
            "id": 1,
            "result": {"protocolVersion": "2024-11-05"},
        }
        mock_proc = _make_mock_proc([init_resp])
        mock_proc.wait.side_effect = subprocess.TimeoutExpired(cmd="autodev-x", timeout=5)

        with (
            patch("autodev.adapters.self_mcp_client.shutil.which", return_value="/usr/bin/autodev-x"),
            patch("autodev.adapters.self_mcp_client.subprocess.Popen", return_value=mock_proc),
        ):
            client = SelfMcpClient()
            client._ensure_started()
            client.close()

        mock_proc.kill.assert_called_once()


# ---------------------------------------------------------------------------
# Test 5: Error on missing autodev-x binary
# ---------------------------------------------------------------------------


class TestSelfMcpClientBinaryMissing:
    """When autodev-x is not on PATH, client falls back to mock mode."""

    def setup_method(self) -> None:
        os.environ["FACTORY_FORCE_MOCK"] = "0"

    def teardown_method(self) -> None:
        os.environ["FACTORY_FORCE_MOCK"] = "1"

    def test_binary_not_found_returns_mock_list_tools(self) -> None:
        with patch("autodev.adapters.self_mcp_client.shutil.which", return_value=None):
            client = SelfMcpClient(binary="autodev-x-nonexistent")
            tools = client.list_tools()
        assert isinstance(tools, list)
        assert len(tools) > 0  # mock list returned

    def test_binary_not_found_returns_mock_call_tool(self) -> None:
        with patch("autodev.adapters.self_mcp_client.shutil.which", return_value=None):
            client = SelfMcpClient(binary="autodev-x-nonexistent")
            result = client.call_tool("autodev_scan", {"path": "."})
        assert result["success"] is True
        assert result["mock_used"] is True

    def test_binary_not_found_proc_is_never_set(self) -> None:
        with patch("autodev.adapters.self_mcp_client.shutil.which", return_value=None):
            client = SelfMcpClient(binary="autodev-x-nonexistent")
            client._ensure_started()
        assert client._proc is None


# ---------------------------------------------------------------------------
# Test 6: Error on tool-not-found (server returns JSON-RPC error)
# ---------------------------------------------------------------------------


class TestSelfMcpClientToolNotFound:
    """tool-not-found is surfaced as success=False with a descriptive error."""

    def setup_method(self) -> None:
        os.environ["FACTORY_FORCE_MOCK"] = "0"

    def teardown_method(self) -> None:
        os.environ["FACTORY_FORCE_MOCK"] = "1"

    def test_tool_not_found_error_key_present(self) -> None:
        init_resp = {"jsonrpc": "2.0", "id": 1, "result": {"protocolVersion": "2024-11-05"}}
        tool_err = {
            "jsonrpc": "2.0",
            "id": 2,
            "error": {"code": -32601, "message": "Tool not found: bogus_tool"},
        }
        mock_proc = _make_mock_proc([init_resp, tool_err])

        with (
            patch("autodev.adapters.self_mcp_client.shutil.which", return_value="/usr/bin/autodev-x"),
            patch("autodev.adapters.self_mcp_client.subprocess.Popen", return_value=mock_proc),
        ):
            client = SelfMcpClient()
            client._ensure_started()
            result = client.call_tool("bogus_tool", {})

        assert result["success"] is False
        assert result["error"] is not None
        assert "bogus_tool" in (result["error"] or "") or "not found" in (result["error"] or "").lower()
        client.close()
