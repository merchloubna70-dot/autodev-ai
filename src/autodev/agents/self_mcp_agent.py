"""SelfMcpAgent — invoke autodev-x tools via the MCP protocol.

This agent wraps ``SelfMcpClient`` to provide the "use my own tools"
participant for a roundtable discussion.  Given a question and a tool
name, it calls the tool via the local MCP server and returns a
structured result.

Usage::

    agent = SelfMcpAgent()
    result = agent.run(question="What files exist?", tool_name="autodev_scan",
                       tool_args={"path": "."})
    print(result.tool_name, result.success, result.response_text)

Roundtable integration:
    Pass ``SelfMcpAgent`` as a participant when you want one roundtable
    slot to use autodev-x's own MCP tools rather than an external LLM.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..adapters.self_mcp_client import SelfMcpClient


@dataclass
class SelfMcpResult:
    """Structured result from a ``SelfMcpAgent.run()`` call."""

    tool_name: str
    success: bool
    response_text: str
    error: str | None
    duration_ms: int
    mock_used: bool
    question: str = ""
    extra: dict[str, Any] = field(default_factory=dict)

    def as_roundtable_text(self) -> str:
        """Return a human-readable summary suitable for roundtable synthesis."""
        status = "OK" if self.success else "ERROR"
        lines = [
            f"[SelfMcpAgent] tool={self.tool_name} status={status}",
        ]
        if self.question:
            lines.append(f"Question: {self.question}")
        if self.response_text:
            lines.append(f"Response: {self.response_text}")
        if self.error:
            lines.append(f"Error: {self.error}")
        lines.append(f"duration_ms={self.duration_ms} mock={self.mock_used}")
        return "\n".join(lines)


class SelfMcpAgent:
    """Agent that invokes autodev-x tools via its own MCP server.

    This enables a reflective loop: tools can be called by other tools
    through the MCP protocol, which is the same interface external
    clients (e.g. Claude Desktop) use.

    Parameters
    ----------
    client:
        Optional pre-constructed ``SelfMcpClient``.  When omitted a new
        client is created with default parameters.  The agent does NOT
        take ownership of an externally supplied client (it will not
        close it on ``close()``).
    """

    def __init__(self, client: SelfMcpClient | None = None) -> None:
        self._external_client = client is not None
        self._client: SelfMcpClient = client if client is not None else SelfMcpClient()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def close(self) -> None:
        """Close the underlying client if it was created internally."""
        if not self._external_client:
            self._client.close()

    def __enter__(self) -> SelfMcpAgent:
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def list_tools(self) -> list[dict[str, Any]]:
        """Return the list of tools available on the MCP server."""
        return self._client.list_tools()

    def run(
        self,
        *,
        question: str,
        tool_name: str,
        tool_args: dict[str, Any] | None = None,
    ) -> SelfMcpResult:
        """Invoke *tool_name* with *tool_args* and return a ``SelfMcpResult``.

        Parameters
        ----------
        question:
            Human-readable description of what the caller wants to know.
            Stored in the result for traceability but not sent to the server.
        tool_name:
            The MCP tool to call (e.g. ``"autodev_scan"``).
        tool_args:
            Arguments forwarded to the tool.  Defaults to an empty dict.
        """
        raw = self._client.call_tool(tool_name, tool_args)
        return SelfMcpResult(
            tool_name=raw["tool_name"],
            success=raw["success"],
            response_text=raw.get("response_text", ""),
            error=raw.get("error"),
            duration_ms=raw.get("duration_ms", 0),
            mock_used=raw.get("mock_used", False),
            question=question,
        )

    def run_for_roundtable(
        self,
        *,
        question: str,
        tool_name: str,
        tool_args: dict[str, Any] | None = None,
    ) -> str:
        """Convenience wrapper: call ``run()`` and return roundtable-ready text."""
        result = self.run(
            question=question,
            tool_name=tool_name,
            tool_args=tool_args,
        )
        return result.as_roundtable_text()
