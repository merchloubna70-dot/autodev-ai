"""autodev MCP server — exposes autodev flows as MCP tools over stdio JSON-RPC 2.0."""
from .server import MCPServer

__all__ = ["MCPServer"]
