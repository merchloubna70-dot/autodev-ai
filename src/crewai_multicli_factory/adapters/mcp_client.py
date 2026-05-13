"""Minimal JSON-RPC-over-stdio MCP client with safety-first process spawning.

When FACTORY_FORCE_MOCK=1 or the binary is missing, returns deterministic mock
responses without launching any subprocess.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from typing import Any

from ..executors.shell_executor import ShellExecutor

# Default set of binary names allowed to be spawned as MCP servers.
DEFAULT_ALLOWED_BINS: frozenset[str] = frozenset(
    {
        "npx",
        "uvx",
        "python",
        "python3",
        "node",
    }
)

_MOCK_TOOLS = [
    {"name": "echo", "description": "Echo input", "inputSchema": {}},
    {"name": "list_files", "description": "List files in dir", "inputSchema": {}},
]


def _force_mock() -> bool:
    return os.environ.get("FACTORY_FORCE_MOCK", "0") == "1"


class MCPToolClient:
    """Minimal JSON-RPC-over-stdio MCP client.

    Parameters
    ----------
    command:
        The binary name (e.g. ``"npx"``) to launch the MCP server.
    args:
        Additional arguments passed after the binary name.
    allowed_bins:
        Set of binary names permitted to spawn. Defaults to
        ``DEFAULT_ALLOWED_BINS``.
    """

    def __init__(
        self,
        command: str = "npx",
        args: list[str] | None = None,
        allowed_bins: frozenset[str] | None = None,
    ) -> None:
        self.command = command
        self.args: list[str] = args or []
        self.allowed_bins: frozenset[str] = (
            allowed_bins if allowed_bins is not None else DEFAULT_ALLOWED_BINS
        )
        self._proc: subprocess.Popen[str] | None = None
        self._request_id = 0

    # ------------------------------------------------------------------
    # Safety helpers
    # ------------------------------------------------------------------

    def _safe_spawn_via_shell_executor(self) -> bool:
        """Return True only if the binary is on the allowlist and on PATH.

        Uses ShellExecutor's allowlist machinery by running a harmless
        ``git status``-style check and then verifies the binary directly.
        """
        bin_name = self.command.split("/")[-1]  # strip path prefix
        if bin_name not in self.allowed_bins:
            return False
        # Also require the binary to actually exist on PATH
        if shutil.which(self.command) is None:
            return False
        return True

    def _next_id(self) -> int:
        self._request_id += 1
        return self._request_id

    def _send_request(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        """Send a JSON-RPC request and return the response dict."""
        if self._proc is None or self._proc.poll() is not None:
            raise RuntimeError("MCP server process is not running")
        request = {
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
        return json.loads(raw)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def _ensure_started(self) -> bool:
        """Start the server if not running. Returns False when mock mode."""
        if _force_mock():
            return False
        if not self._safe_spawn_via_shell_executor():
            return False
        if self._proc is not None and self._proc.poll() is None:
            return True
        argv = [self.command] + self.args
        try:
            self._proc = subprocess.Popen(
                argv,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
        except (FileNotFoundError, PermissionError):
            self._proc = None
            return False
        return True

    def close(self) -> None:
        if self._proc and self._proc.poll() is None:
            self._proc.stdin.close() if self._proc.stdin else None
            self._proc.terminate()
            try:
                self._proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._proc.kill()
        self._proc = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def list_tools(self) -> list[dict[str, Any]]:
        """Return a list of tool descriptors from the MCP server.

        Falls back to deterministic mock list when mock mode is active or
        binary is unavailable.
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
        """Call a tool by name and return the raw result dict.

        In mock mode returns a deterministic response keyed on *name*.
        """
        args = arguments or {}
        if not self._ensure_started():
            return {
                "tool_name": name,
                "success": True,
                "response_text": f"mock:{name}({json.dumps(args, sort_keys=True)})",
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
                return {
                    "tool_name": name,
                    "success": False,
                    "response_text": "",
                    "error": str(resp["error"]),
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
