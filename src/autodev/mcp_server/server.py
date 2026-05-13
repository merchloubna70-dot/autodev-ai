"""MCPServer — pure-stdlib stdio JSON-RPC 2.0 MCP server.

Implements: initialize, ping, tools/list, tools/call.
Logs to stderr only; stdout is reserved for JSON-RPC protocol messages.
"""
from __future__ import annotations

import json
import sys
import time
from typing import Any

from .tools import get_tools

PROTOCOL_VERSION = "2024-11-05"
SERVER_INFO = {"name": "autodev", "version": "1.0.0"}


def _write(obj: dict[str, Any]) -> None:
    """Write a single JSON-RPC message to stdout followed by newline."""
    line = json.dumps(obj, separators=(",", ":"))
    sys.stdout.write(line + "\n")
    sys.stdout.flush()


def _log(msg: str) -> None:
    """Log to stderr; never to stdout."""
    print(f"[autodev-mcp] {msg}", file=sys.stderr, flush=True)


def _error_response(req_id: Any, code: int, message: str) -> dict[str, Any]:
    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "error": {"code": code, "message": message},
    }


def _ok_response(req_id: Any, result: Any) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": req_id, "result": result}


class MCPServer:
    """Stdio JSON-RPC 2.0 MCP server.

    Call ``run()`` to block reading lines from stdin and dispatching requests.
    """

    def __init__(self) -> None:
        self._tools = {t.name: t for t in get_tools()}
        self._start_time = time.monotonic()

    # ------------------------------------------------------------------
    # Request dispatch
    # ------------------------------------------------------------------

    def _handle(self, raw: str) -> dict[str, Any] | None:
        """Parse and dispatch one JSON-RPC line.  Returns None for notifications."""
        try:
            req = json.loads(raw)
        except json.JSONDecodeError as exc:
            return _error_response(None, -32700, f"Parse error: {exc}")

        req_id = req.get("id")
        method = req.get("method", "")
        params = req.get("params") or {}

        # Notifications have no id — handle and return None
        is_notification = "id" not in req

        if method == "initialize":
            result = {
                "protocolVersion": PROTOCOL_VERSION,
                "serverInfo": SERVER_INFO,
                "capabilities": {"tools": {}},
            }
            if is_notification:
                return None
            return _ok_response(req_id, result)

        if method == "ping":
            if is_notification:
                return None
            return _ok_response(req_id, {})

        if method == "tools/list":
            tools_list = [
                {
                    "name": t.name,
                    "description": t.description,
                    "inputSchema": t.input_schema,
                }
                for t in self._tools.values()
            ]
            if is_notification:
                return None
            return _ok_response(req_id, {"tools": tools_list})

        if method == "tools/call":
            if is_notification:
                return None
            name = params.get("name", "")
            arguments = params.get("arguments") or {}
            tool = self._tools.get(name)
            if tool is None:
                return _error_response(req_id, -32601, f"Unknown tool: {name!r}")
            t0 = time.monotonic()
            try:
                handler_result = tool.handler(arguments)
                duration_ms = int((time.monotonic() - t0) * 1000)
                _log(f"tools/call {name} ok ({duration_ms}ms)")
                if isinstance(handler_result, str):
                    content = [{"type": "text", "text": handler_result}]
                else:
                    content = [{"type": "text", "text": json.dumps(handler_result, default=str)}]
                return _ok_response(req_id, {"content": content, "isError": False})
            except Exception as exc:
                duration_ms = int((time.monotonic() - t0) * 1000)
                _log(f"tools/call {name} error ({duration_ms}ms): {exc}")
                return _ok_response(
                    req_id,
                    {"content": [{"type": "text", "text": str(exc)}], "isError": True},
                )

        # Unknown method
        if is_notification:
            return None
        return _error_response(req_id, -32601, f"Method not found: {method!r}")

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    def run(self) -> None:
        """Block-read from stdin; write responses to stdout."""
        _log("autodev MCP server ready")
        print("autodev MCP server ready", file=sys.stderr, flush=True)
        for raw in sys.stdin:
            raw = raw.strip()
            if not raw:
                continue
            response = self._handle(raw)
            if response is not None:
                _write(response)
