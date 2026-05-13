"""Unit tests for the autodev MCP server (stdio JSON-RPC 2.0)."""
from __future__ import annotations

import io
import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_server():
    """Return a fresh MCPServer instance."""
    from autodev.mcp_server.server import MCPServer
    return MCPServer()


def _dispatch(server, method: str, params: dict, req_id: int = 1) -> dict:
    """Call server._handle() with a well-formed JSON-RPC request string."""
    req = {"jsonrpc": "2.0", "id": req_id, "method": method, "params": params}
    return server._handle(json.dumps(req))


# ---------------------------------------------------------------------------
# Test 1: initialize handshake returns correct protocolVersion
# ---------------------------------------------------------------------------


def test_initialize_returns_protocol_version():
    srv = _make_server()
    resp = _dispatch(srv, "initialize", {"protocolVersion": "2024-11-05", "capabilities": {}})
    assert resp is not None
    assert resp["jsonrpc"] == "2.0"
    assert resp["id"] == 1
    result = resp["result"]
    assert result["protocolVersion"] == "2024-11-05"
    assert "serverInfo" in result
    assert result["serverInfo"]["name"] == "autodev"


# ---------------------------------------------------------------------------
# Test 2: tools/list returns ≥9 tools with valid JSON Schema
# ---------------------------------------------------------------------------


def test_tools_list_returns_nine_or_more_tools():
    srv = _make_server()
    resp = _dispatch(srv, "tools/list", {})
    assert resp is not None
    tools = resp["result"]["tools"]
    assert len(tools) >= 9
    for t in tools:
        assert "name" in t
        assert "description" in t
        schema = t["inputSchema"]
        assert schema.get("type") == "object"
        assert "properties" in schema


# ---------------------------------------------------------------------------
# Test 3: tools/call autodev_scan returns RepoScanResult-shaped JSON
# ---------------------------------------------------------------------------


def test_tools_call_scan_empty_repo(tmp_path):
    srv = _make_server()
    resp = _dispatch(srv, "tools/call", {"name": "autodev_scan", "arguments": {"repo_path": str(tmp_path)}})
    assert resp is not None
    assert not resp["result"]["isError"]
    content_text = resp["result"]["content"][0]["text"]
    data = json.loads(content_text)
    assert "repo_path" in data
    assert "is_empty" in data
    assert "detected_languages" in data


# ---------------------------------------------------------------------------
# Test 4: tools/call autodev_classify_input returns InputClassification
# ---------------------------------------------------------------------------


def test_tools_call_classify_input():
    srv = _make_server()
    resp = _dispatch(srv, "tools/call", {
        "name": "autodev_classify_input",
        "arguments": {"text": "Fix the login button not working in production"},
    })
    assert resp is not None
    assert not resp["result"]["isError"]
    content_text = resp["result"]["content"][0]["text"]
    data = json.loads(content_text)
    assert "input_type" in data
    assert "confidence" in data
    assert "suggested_flow" in data


# ---------------------------------------------------------------------------
# Test 5: tools/call autodev_roundtable with FACTORY_FORCE_MOCK=1
# ---------------------------------------------------------------------------


def test_tools_call_roundtable_mock():
    with patch.dict(os.environ, {"FACTORY_FORCE_MOCK": "1"}):
        srv = _make_server()
        resp = _dispatch(srv, "tools/call", {
            "name": "autodev_roundtable",
            "arguments": {
                "topic": "How to improve test coverage",
                "skills": ["testing", "architecture"],
                "max_participants": 2,
            },
        })
    assert resp is not None
    assert not resp["result"]["isError"]
    content_text = resp["result"]["content"][0]["text"]
    data = json.loads(content_text)
    assert "synth_text" in data
    assert "conversation" in data


# ---------------------------------------------------------------------------
# Test 6: Unknown tool name → JSON-RPC error response (not crash)
# ---------------------------------------------------------------------------


def test_unknown_tool_returns_error():
    srv = _make_server()
    resp = _dispatch(srv, "tools/call", {"name": "nonexistent_tool_xyz", "arguments": {}})
    assert resp is not None
    assert "error" in resp
    assert resp["error"]["code"] == -32601
    assert "nonexistent_tool_xyz" in resp["error"]["message"]


# ---------------------------------------------------------------------------
# Test 7: autodev_list_runs returns empty list for new dir
# ---------------------------------------------------------------------------


def test_list_runs_empty_repo(tmp_path):
    srv = _make_server()
    resp = _dispatch(srv, "tools/call", {
        "name": "autodev_list_runs",
        "arguments": {"repo_path": str(tmp_path)},
    })
    assert resp is not None
    assert not resp["result"]["isError"]
    content_text = resp["result"]["content"][0]["text"]
    data = json.loads(content_text)
    assert isinstance(data, list)
    assert data == []


# ---------------------------------------------------------------------------
# Test 8: MCPToolHandlerResult and MCPServerStatus schemas exist
# ---------------------------------------------------------------------------


def test_mcp_schemas_importable():
    from autodev.schemas import MCPToolHandlerResult, MCPServerStatus

    r = MCPToolHandlerResult(tool_name="autodev_scan", success=True, content_text="ok")
    assert r.tool_name == "autodev_scan"
    assert r.success is True

    s = MCPServerStatus(tools_count=9)
    assert s.protocol_version == "2024-11-05"
    assert s.tools_count == 9


# ---------------------------------------------------------------------------
# Test 9: ping returns empty result
# ---------------------------------------------------------------------------


def test_ping():
    srv = _make_server()
    resp = _dispatch(srv, "ping", {})
    assert resp is not None
    assert resp["result"] == {}


# ---------------------------------------------------------------------------
# Test 10: parse error for malformed JSON
# ---------------------------------------------------------------------------


def test_parse_error_on_bad_json():
    srv = _make_server()
    resp = srv._handle("{{not valid json")
    assert resp is not None
    assert "error" in resp
    assert resp["error"]["code"] == -32700
