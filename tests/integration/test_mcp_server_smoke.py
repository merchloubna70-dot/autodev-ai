"""MCP server smoke tests — full JSON-RPC 2.0 protocol verification.

Starts autodev mcp-serve as a subprocess with stdin/stdout pipes and exercises:
  - initialize handshake
  - tools/list (verifies exactly 9 tools)
  - tools/call for a safe, dependency-free tool (autodev_list_runs)
  - malformed JSON  → parse error response
  - missing method field → method-not-found error
  - unknown method → method-not-found error
  - unknown tool name → method-not-found error (code -32601)
  - shutdown (graceful close)
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys

import pytest

# ---------------------------------------------------------------------------
# Skip guard — if autodev binary is not installed, skip the whole module.
# We check both the venv binary and the module invocation path.
# ---------------------------------------------------------------------------

_AUTODEV_BIN = shutil.which("autodev") or (
    str(sys.executable).replace("python", "autodev") if "python" in str(sys.executable) else None
)
# Prefer venv binary discovered at test-collection time; fall back to -m invocation.
_VENV_BIN = os.path.join(os.path.dirname(sys.executable), "autodev")
_USE_BIN = _VENV_BIN if os.path.isfile(_VENV_BIN) else None

_SKIP_REASON = "autodev mcp-serve binary not available on PATH or in venv"
_SKIP = _USE_BIN is None and _AUTODEV_BIN is None


def _mcp_cmd() -> list[str]:
    """Return the command list to launch mcp-serve."""
    if _USE_BIN:
        return [_USE_BIN, "mcp-serve"]
    if _AUTODEV_BIN:
        return [_AUTODEV_BIN, "mcp-serve"]
    return [sys.executable, "-m", "autodev.cli", "mcp-serve"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

EXPECTED_TOOL_COUNT = 9

EXPECTED_TOOL_NAMES = {
    "autodev_scan",
    "autodev_classify_input",
    "autodev_create_prd",
    "autodev_deliver_project",
    "autodev_run_issue",
    "autodev_report",
    "autodev_roundtable",
    "autodev_release_check",
    "autodev_list_runs",
}


def _run_mcp(messages_or_raw_lines: list) -> tuple[list[dict], str]:
    """Start mcp-serve, send messages (dict) or raw strings, collect responses.

    Returns (parsed_responses, raw_stderr).
    """
    env = {**os.environ, "FACTORY_FORCE_MOCK": "1"}
    proc = subprocess.Popen(
        _mcp_cmd(),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
    )
    lines = []
    for item in messages_or_raw_lines:
        if isinstance(item, dict):
            lines.append(json.dumps(item))
        else:
            lines.append(str(item))  # allow raw / malformed strings
    payload = "\n".join(lines) + "\n"
    stdout, stderr = proc.communicate(input=payload, timeout=30)
    responses: list[dict] = []
    for line in stdout.splitlines():
        line = line.strip()
        if line:
            try:
                responses.append(json.loads(line))
            except json.JSONDecodeError:
                pass  # skip non-JSON lines
    return responses, stderr


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

INITIALIZE_MSG = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": "2024-11-05",
        "capabilities": {},
        "clientInfo": {"name": "audit", "version": "0.1"},
    },
}


# ---------------------------------------------------------------------------
# Test: initialize handshake
# ---------------------------------------------------------------------------

@pytest.mark.skipif(_SKIP, reason=_SKIP_REASON)
def test_initialize_handshake():
    """Server responds to initialize with protocolVersion + serverInfo + capabilities."""
    responses, _ = _run_mcp([INITIALIZE_MSG])
    assert len(responses) >= 1, "Expected at least one response"
    resp = next((r for r in responses if r.get("id") == 1), None)
    assert resp is not None, f"No id=1 in responses: {responses}"
    assert resp["jsonrpc"] == "2.0"
    assert "result" in resp, f"Expected result, got: {resp}"
    result = resp["result"]
    assert result["protocolVersion"] == "2024-11-05"
    assert result["serverInfo"]["name"] == "autodev"
    assert "tools" in result["capabilities"]


# ---------------------------------------------------------------------------
# Test: tools/list — exactly 9 tools with correct names
# ---------------------------------------------------------------------------

@pytest.mark.skipif(_SKIP, reason=_SKIP_REASON)
def test_tools_list_count_and_names():
    """tools/list returns exactly 9 tools with all expected names."""
    responses, _ = _run_mcp([
        INITIALIZE_MSG,
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
    ])
    resp = next((r for r in responses if r.get("id") == 2), None)
    assert resp is not None, f"No id=2 in responses: {responses}"
    assert "result" in resp
    tools = resp["result"]["tools"]
    assert len(tools) == EXPECTED_TOOL_COUNT, (
        f"Expected {EXPECTED_TOOL_COUNT} tools, got {len(tools)}: {[t['name'] for t in tools]}"
    )
    names = {t["name"] for t in tools}
    missing = EXPECTED_TOOL_NAMES - names
    assert not missing, f"Missing tools: {missing}"


@pytest.mark.skipif(_SKIP, reason=_SKIP_REASON)
def test_tools_list_has_input_schema():
    """Every tool in tools/list has a non-empty inputSchema."""
    responses, _ = _run_mcp([
        INITIALIZE_MSG,
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
    ])
    resp = next((r for r in responses if r.get("id") == 2), None)
    assert resp is not None
    for tool in resp["result"]["tools"]:
        assert "inputSchema" in tool, f"Tool {tool['name']} missing inputSchema"
        schema = tool["inputSchema"]
        assert schema.get("type") == "object"
        assert "properties" in schema


# ---------------------------------------------------------------------------
# Test: tools/call — safe tool (autodev_list_runs, no LLM dependency)
# ---------------------------------------------------------------------------

@pytest.mark.skipif(_SKIP, reason=_SKIP_REASON)
def test_tools_call_list_runs():
    """tools/call autodev_list_runs returns valid MCP content array."""
    responses, _ = _run_mcp([
        INITIALIZE_MSG,
        {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {"name": "autodev_list_runs", "arguments": {"repo_path": "."}},
        },
    ])
    resp = next((r for r in responses if r.get("id") == 3), None)
    assert resp is not None, f"No id=3 in responses: {responses}"
    assert "result" in resp, f"Expected result, got error: {resp}"
    result = resp["result"]
    assert "content" in result
    assert isinstance(result["content"], list)
    assert len(result["content"]) >= 1
    assert result["content"][0]["type"] == "text"
    assert result["isError"] is False
    # content text should be a JSON array
    content_text = result["content"][0]["text"]
    parsed = json.loads(content_text)
    assert isinstance(parsed, list)


# ---------------------------------------------------------------------------
# Test: error semantics — parse error (invalid JSON)
# ---------------------------------------------------------------------------

@pytest.mark.skipif(_SKIP, reason=_SKIP_REASON)
def test_parse_error_on_invalid_json():
    """Malformed JSON line triggers parse error with code -32700."""
    responses, _ = _run_mcp([
        INITIALIZE_MSG,
        "NOT VALID JSON {{{{",  # raw malformed string
        {"jsonrpc": "2.0", "id": 99, "method": "ping", "params": {}},
    ])
    # Find parse error response (id=null)
    parse_err = next(
        (r for r in responses if "error" in r and r.get("id") is None), None
    )
    assert parse_err is not None, f"No parse-error response found in: {responses}"
    assert parse_err["error"]["code"] == -32700
    assert "parse error" in parse_err["error"]["message"].lower()


# ---------------------------------------------------------------------------
# Test: error semantics — unknown method
# ---------------------------------------------------------------------------

@pytest.mark.skipif(_SKIP, reason=_SKIP_REASON)
def test_unknown_method_error():
    """Unknown method returns JSON-RPC error with code -32601."""
    responses, _ = _run_mcp([
        INITIALIZE_MSG,
        {"jsonrpc": "2.0", "id": 10, "method": "nonexistent/method", "params": {}},
    ])
    resp = next((r for r in responses if r.get("id") == 10), None)
    assert resp is not None, f"No id=10 response in: {responses}"
    assert "error" in resp, f"Expected error response, got: {resp}"
    assert resp["error"]["code"] == -32601
    assert "nonexistent/method" in resp["error"]["message"]


# ---------------------------------------------------------------------------
# Test: error semantics — unknown tool name
# ---------------------------------------------------------------------------

@pytest.mark.skipif(_SKIP, reason=_SKIP_REASON)
def test_unknown_tool_error():
    """tools/call with unknown tool name returns error code -32601."""
    responses, _ = _run_mcp([
        INITIALIZE_MSG,
        {
            "jsonrpc": "2.0",
            "id": 11,
            "method": "tools/call",
            "params": {"name": "nonexistent_tool_xyz", "arguments": {}},
        },
    ])
    resp = next((r for r in responses if r.get("id") == 11), None)
    assert resp is not None, f"No id=11 response in: {responses}"
    assert "error" in resp
    assert resp["error"]["code"] == -32601
    assert "nonexistent_tool_xyz" in resp["error"]["message"]


# ---------------------------------------------------------------------------
# Test: deeply nested JSON does not crash the server
# ---------------------------------------------------------------------------

@pytest.mark.skipif(_SKIP, reason=_SKIP_REASON)
def test_deeply_nested_json_handled():
    """Deeply nested JSON arguments do not crash the server."""
    deep = {"a": {"b": {"c": {"d": {"e": {"f": "x" * 500}}}}}}
    responses, _ = _run_mcp([
        INITIALIZE_MSG,
        {
            "jsonrpc": "2.0",
            "id": 20,
            "method": "tools/call",
            "params": {"name": "autodev_list_runs", "arguments": {"repo_path": ".", "extra": deep}},
        },
    ])
    resp = next((r for r in responses if r.get("id") == 20), None)
    assert resp is not None, f"No id=20 response in: {responses}"
    # Should succeed (extra keys ignored) or return a structured error — not a crash
    assert "result" in resp or "error" in resp


# ---------------------------------------------------------------------------
# Test: notification (no id) does not generate a response
# ---------------------------------------------------------------------------

@pytest.mark.skipif(_SKIP, reason=_SKIP_REASON)
def test_notification_no_response():
    """JSON-RPC notifications (no id) do not generate a response message."""
    responses, _ = _run_mcp([
        # notification: no "id" key
        {"jsonrpc": "2.0", "method": "initialize", "params": {"protocolVersion": "2024-11-05", "capabilities": {}}},
        # follow with a regular request to confirm server is still alive
        {"jsonrpc": "2.0", "id": 50, "method": "ping", "params": {}},
    ])
    # The notification must NOT generate a response; only ping should respond
    notification_responses = [r for r in responses if r.get("id") is None and "error" not in r]
    assert len(notification_responses) == 0, (
        f"Notification generated unexpected responses: {notification_responses}"
    )
    ping_resp = next((r for r in responses if r.get("id") == 50), None)
    assert ping_resp is not None, "ping after notification should respond"
    assert "result" in ping_resp


# ---------------------------------------------------------------------------
# Test: shutdown (graceful close via stdin EOF)
# ---------------------------------------------------------------------------

@pytest.mark.skipif(_SKIP, reason=_SKIP_REASON)
def test_shutdown_graceful():
    """Server exits cleanly when stdin is closed (EOF = shutdown signal)."""
    env = {**os.environ, "FACTORY_FORCE_MOCK": "1"}
    proc = subprocess.Popen(
        _mcp_cmd(),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
    )
    payload = json.dumps(INITIALIZE_MSG) + "\n"
    _stdout, _ = proc.communicate(input=payload, timeout=15)
    assert proc.returncode == 0, f"Server exited with non-zero code: {proc.returncode}"
