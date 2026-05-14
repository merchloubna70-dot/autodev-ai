"""SelfMcpClient — spawn autodev-x mcp-serve as a subprocess and communicate via JSON-RPC.

This client enables the reflective loop: an autodev-x agent can invoke tools
exposed by autodev-x's own MCP server.  The subprocess is started lazily on
first use and cleaned up via ``close()`` (or context manager).

Mock mode (``FACTORY_FORCE_MOCK=1`` or binary missing) returns deterministic
responses without launching any process, keeping tests fast and hermetic.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from typing import Any

_SELF_BINARY = "autodev-x"
_MCP_SERVE_ARG = "mcp-serve"

# Deterministic mock tools returned in mock mode
_MOCK_TOOLS: list[dict[str, Any]] = [
    {
        "name": "autodev_scan",
        "description": "Scan a directory for project metadata.",
        "inputSchema": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]},
    },
    {
        "name": "autodev_list_runs",
        "description": "List recent pipeline runs.",
        "inputSchema": {"type": "object", "properties": {}, "required": []},
    },
]


def _force_mock() -> bool:
    return os.environ.get("FACTORY_FORCE_MOCK", "0") == "1"


class SelfMcpClient:
    """JSON-RPC-over-stdio client that talks to ``autodev-x mcp-serve``.

    Parameters
    ----------
    binary:
        Name (or absolute path) of the autodev-x binary.  Defaults to
        ``"autodev-x"`` which is resolved via PATH.
    startup_timeout:
        Seconds to wait for the subprocess to start and respond to the
        ``initialize`` handshake.  Defaults to 10.
    """

    def __init__(
        self,
        binary: str = _SELF_BINARY,
        startup_timeout: float = 10.0,
    ) -> None:
        self._binary = binary
        self._startup_timeout = startup_timeout
        self._proc: subprocess.Popen[str] | None = None
        self._request_id = 0
        self._initialized = False

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _next_id(self) -> int:
        self._request_id += 1
        return self._request_id

    def _send_request(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        """Write a JSON-RPC request to stdin, read the response from stdout."""
        if self._proc is None or self._proc.poll() is not None:
            raise RuntimeError("SelfMcpClient: subprocess is not running")
        request: dict[str, Any] = {
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": method,
            "params": params,
        }
        line = json.dumps(request) + "\n"
        assert self._proc.stdin is not None
        self._proc.stdin.write(line)
        self._proc.stdin.flush()
        assert self._proc.stdout is not None
        raw = self._proc.stdout.readline()
        if not raw:
            raise RuntimeError("SelfMcpClient: subprocess closed stdout unexpectedly")
        return json.loads(raw)  # type: ignore[no-any-return]

    def _resolve_binary(self) -> str | None:
        """Return the absolute path to the binary, or None if not found."""
        return shutil.which(self._binary)

    def _do_initialize_handshake(self) -> None:
        """Perform MCP ``initialize`` → ``notifications/initialized`` handshake."""
        resp = self._send_request(
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "self-mcp-client", "version": "1.0.0"},
            },
        )
        if "error" in resp:
            raise RuntimeError(
                f"SelfMcpClient: initialize failed: {resp['error']}"
            )
        # Send the initialized notification (id=None per JSON-RPC notification)
        notif = json.dumps(
            {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}}
        ) + "\n"
        assert self._proc is not None and self._proc.stdin is not None
        self._proc.stdin.write(notif)
        self._proc.stdin.flush()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def _ensure_started(self) -> bool:
        """Start the subprocess if needed.  Returns False when in mock mode."""
        if _force_mock():
            return False
        if self._proc is not None and self._proc.poll() is None:
            return True

        binary_path = self._resolve_binary()
        if binary_path is None:
            return False  # binary not found → fall back to mock

        try:
            self._proc = subprocess.Popen(
                [binary_path, _MCP_SERVE_ARG],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
        except (FileNotFoundError, PermissionError):
            self._proc = None
            return False

        # Wait briefly for the process to actually start
        deadline = time.monotonic() + self._startup_timeout
        while time.monotonic() < deadline:
            if self._proc.poll() is not None:
                self._proc = None
                return False  # process died immediately
            break  # process is running

        # Perform MCP handshake
        try:
            self._do_initialize_handshake()
            self._initialized = True
        except Exception:
            self.close()
            return False

        return True

    def close(self) -> None:
        """Terminate the subprocess cleanly."""
        if self._proc is not None and self._proc.poll() is None:
            if self._proc.stdin:
                try:
                    self._proc.stdin.close()
                except OSError:
                    pass
            self._proc.terminate()
            try:
                self._proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._proc.kill()
        self._proc = None
        self._initialized = False

    def __enter__(self) -> SelfMcpClient:
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def list_tools(self) -> list[dict[str, Any]]:
        """Return the list of tools exposed by the MCP server.

        Falls back to a deterministic mock list when mock mode is active
        or the binary is unavailable.
        """
        if not self._ensure_started():
            return list(_MOCK_TOOLS)
        try:
            resp = self._send_request("tools/list", {})
            return resp.get("result", {}).get("tools", [])
        except Exception:
            return list(_MOCK_TOOLS)

    def call_tool(
        self, name: str, arguments: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Invoke a named tool and return a structured result dict.

        The returned dict always contains:
        - ``tool_name``   (str)
        - ``success``     (bool)
        - ``response_text`` (str)
        - ``error``       (str | None)
        - ``duration_ms`` (int)
        - ``mock_used``   (bool)

        In mock mode a deterministic response is returned without
        launching any subprocess.  If the server returns an error, the
        dict has ``success=False`` and ``error`` set.
        """
        args = arguments or {}

        if not self._ensure_started():
            return {
                "tool_name": name,
                "success": True,
                "response_text": (
                    f"mock:{name}({json.dumps(args, sort_keys=True)})"
                ),
                "error": None,
                "duration_ms": 0,
                "mock_used": True,
            }

        t0 = time.monotonic()
        try:
            resp = self._send_request(
                "tools/call", {"name": name, "arguments": args}
            )
            duration_ms = int((time.monotonic() - t0) * 1000)

            if "error" in resp:
                error_obj = resp["error"]
                error_msg = (
                    error_obj.get("message", str(error_obj))
                    if isinstance(error_obj, dict)
                    else str(error_obj)
                )
                return {
                    "tool_name": name,
                    "success": False,
                    "response_text": "",
                    "error": error_msg,
                    "duration_ms": duration_ms,
                    "mock_used": False,
                }

            content = resp.get("result", {})
            text = json.dumps(content) if not isinstance(content, str) else content
            return {
                "tool_name": name,
                "success": True,
                "response_text": text,
                "error": None,
                "duration_ms": duration_ms,
                "mock_used": False,
            }
        except Exception as exc:
            duration_ms = int((time.monotonic() - t0) * 1000)
            return {
                "tool_name": name,
                "success": False,
                "response_text": "",
                "error": str(exc),
                "duration_ms": duration_ms,
                "mock_used": False,
            }
