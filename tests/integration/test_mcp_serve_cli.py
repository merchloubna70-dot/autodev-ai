"""Integration tests: autodev mcp-serve subprocess over stdio."""
from __future__ import annotations

import json
import os
import subprocess
import sys


def _run_mcp(messages: list[dict]) -> list[dict]:
    """Start `autodev mcp-serve`, send messages, collect responses."""
    env = {**os.environ, "FACTORY_FORCE_MOCK": "1"}
    proc = subprocess.Popen(
        [sys.executable, "-m", "autodev.cli", "mcp-serve"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
    )
    # Write all messages at once then close stdin
    payload = "\n".join(json.dumps(m) for m in messages) + "\n"
    stdout, _stderr = proc.communicate(input=payload, timeout=30)
    responses = []
    for line in stdout.splitlines():
        line = line.strip()
        if line:
            try:
                responses.append(json.loads(line))
            except json.JSONDecodeError:
                pass  # skip non-JSON stderr lines that leaked
    return responses


def test_mcp_serve_initialize():
    """autodev mcp-serve responds correctly to initialize."""
    responses = _run_mcp([
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {"protocolVersion": "2024-11-05", "capabilities": {}},
        }
    ])
    assert len(responses) >= 1
    resp = responses[0]
    assert resp["jsonrpc"] == "2.0"
    assert resp["id"] == 1
    assert resp["result"]["protocolVersion"] == "2024-11-05"


def test_mcp_serve_tools_list():
    """autodev mcp-serve returns ≥9 tools from tools/list."""
    responses = _run_mcp([
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {"protocolVersion": "2024-11-05", "capabilities": {}},
        },
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {},
        },
    ])
    # Find the tools/list response (id == 2)
    tools_resp = next((r for r in responses if r.get("id") == 2), None)
    assert tools_resp is not None, f"No id=2 response in: {responses}"
    tools = tools_resp["result"]["tools"]
    assert len(tools) >= 9
    names = {t["name"] for t in tools}
    assert "autodev_scan" in names
    assert "autodev_roundtable" in names
    assert "autodev_list_runs" in names
