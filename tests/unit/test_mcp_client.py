"""Tests for MCPToolClient — all run in FACTORY_FORCE_MOCK=1 mode."""
from __future__ import annotations

import os

os.environ.setdefault("FACTORY_FORCE_MOCK", "1")

# Import directly from submodule to avoid __init__ chain side-effects
from autodev.adapters.mcp_client import MCPToolClient


class TestMCPClientMock:
    """Tests using the deterministic mock path (FACTORY_FORCE_MOCK=1)."""

    def setup_method(self) -> None:
        os.environ["FACTORY_FORCE_MOCK"] = "1"
        self.client = MCPToolClient(command="npx", args=["@modelcontextprotocol/server-everything"])

    def test_list_tools_returns_list(self) -> None:
        tools = self.client.list_tools()
        assert isinstance(tools, list)
        assert len(tools) > 0

    def test_list_tools_have_name_field(self) -> None:
        tools = self.client.list_tools()
        for tool in tools:
            assert "name" in tool

    def test_call_tool_returns_structured_dict(self) -> None:
        result = self.client.call_tool("echo", {"message": "hello"})
        assert isinstance(result, dict)
        assert "tool_name" in result
        assert "success" in result
        assert "response_text" in result

    def test_call_tool_mock_used_flag(self) -> None:
        result = self.client.call_tool("list_files", {"path": "."})
        assert result["mock_used"] is True
        assert result["success"] is True

    def test_call_tool_response_is_deterministic(self) -> None:
        r1 = self.client.call_tool("echo", {"x": 1})
        r2 = self.client.call_tool("echo", {"x": 1})
        assert r1["response_text"] == r2["response_text"]


class TestMCPClientBinaryMissing:
    """When binary is not on PATH and mock=0, still returns mock."""

    def setup_method(self) -> None:
        os.environ["FACTORY_FORCE_MOCK"] = "0"
        # Use a nonsense binary that definitely does not exist
        self.client = MCPToolClient(
            command="__nonexistent_mcp_server_xyz__",
            args=[],
            allowed_bins=frozenset({"__nonexistent_mcp_server_xyz__"}),
        )

    def teardown_method(self) -> None:
        os.environ["FACTORY_FORCE_MOCK"] = "1"

    def test_list_tools_falls_back_to_mock(self) -> None:
        tools = self.client.list_tools()
        assert isinstance(tools, list)
        assert len(tools) > 0

    def test_call_tool_falls_back_to_mock(self) -> None:
        result = self.client.call_tool("echo", {"msg": "hi"})
        assert isinstance(result, dict)
        assert result["success"] is True


class TestMCPClientDenyBin:
    """Binary not in allowlist -> fallback, no process spawned."""

    def setup_method(self) -> None:
        os.environ["FACTORY_FORCE_MOCK"] = "0"
        self.client = MCPToolClient(
            command="bash",  # bash is NOT in DEFAULT_ALLOWED_BINS
            args=["-c", "cat"],
        )

    def teardown_method(self) -> None:
        os.environ["FACTORY_FORCE_MOCK"] = "1"

    def test_denied_bin_list_tools_safe(self) -> None:
        tools = self.client.list_tools()
        assert isinstance(tools, list)

    def test_denied_bin_call_tool_safe(self) -> None:
        result = self.client.call_tool("cmd", {"arg": "val"})
        assert isinstance(result, dict)
