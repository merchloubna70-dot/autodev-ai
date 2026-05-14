"""MCPServer — pure-stdlib stdio JSON-RPC 2.0 MCP server.

Implements: initialize, ping, tools/list, tools/call.
Logs to stderr only; stdout is reserved for JSON-RPC protocol messages.

Auth modes:
- Legacy (AUTODEV_MCP_IDENTITIES unset): single shared AUTODEV_A2A_TOKEN or
  no auth (stdio).  caller_id = "legacy_shared_token" in audit logs.
- Per-caller (AUTODEV_MCP_IDENTITIES = path): each request must carry a valid
  Bearer token that maps to a CallerIdentity in the registry.  Missing/invalid
  token → -32001 Unauthorized.  Missing scope → -32002 Forbidden.
"""
from __future__ import annotations

import json
import os
import sys
import time
from typing import Any

from .identity import (
    CallerIdentity,
    IdentityRegistry,
    _make_legacy_identity,
    load_registry_from_env,
    set_current_caller,
)
from .tools import TOOL_SCOPES, get_tools

PROTOCOL_VERSION = "2024-11-05"
SERVER_INFO = {"name": "autodev-x", "version": "1.0.0"}

# JSON Schema type → Python types mapping for basic type checking
_SCHEMA_TYPE_MAP: dict[str, tuple[type, ...]] = {
    "string": (str,),
    "number": (int, float),
    "integer": (int,),
    "boolean": (bool,),
    "array": (list,),
    "object": (dict,),
    "null": (type(None),),
}


def _validate_required_params(
    schema: dict[str, Any],
    args: dict[str, Any],
    tool_name: str,
) -> str | None:
    """Validate required fields and basic types against a JSON Schema object.

    Strategy:
    - REJECT missing required fields → return error detail string
    - REJECT wrong type for required fields → return error detail string
    - IGNORE unknown extra args (pass through to handler)

    Returns None if valid, or an error message string if invalid.
    """
    if schema.get("type") != "object":
        return None  # nothing to validate for non-object schemas

    required: list[str] = schema.get("required", [])
    properties: dict[str, Any] = schema.get("properties", {})

    missing = [field for field in required if field not in args]
    if missing:
        return (
            f"Tool {tool_name!r} missing required param(s): {missing}. "
            f"Required: {required}"
        )

    # Type-check required fields that are present
    type_errors: list[str] = []
    for field in required:
        if field not in args:
            continue  # already caught above
        prop_schema = properties.get(field, {})
        expected_type = prop_schema.get("type")
        if expected_type is None:
            continue  # no type declared — skip
        allowed_python_types = _SCHEMA_TYPE_MAP.get(expected_type)
        if allowed_python_types is None:
            continue  # unknown schema type — skip
        value = args[field]
        # Special case: bool is a subclass of int in Python; treat bool strictly
        if expected_type in ("integer", "number") and isinstance(value, bool):
            type_errors.append(
                f"Field {field!r}: expected {expected_type}, got bool"
            )
        elif not isinstance(value, allowed_python_types):
            actual = type(value).__name__
            type_errors.append(
                f"Field {field!r}: expected {expected_type}, got {actual}"
            )

    if type_errors:
        return (
            f"Tool {tool_name!r} invalid param type(s): {'; '.join(type_errors)}"
        )

    return None


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


_ENV_A2A_TOKEN = "AUTODEV_A2A_TOKEN"


class MCPServer:
    """Stdio JSON-RPC 2.0 MCP server.

    Call ``run()`` to block reading lines from stdin and dispatching requests.
    """

    def __init__(self) -> None:
        self._tools = {t.name: t for t in get_tools()}
        self._start_time = time.monotonic()
        # Load identity registry (None = legacy mode)
        self._registry: IdentityRegistry | None = load_registry_from_env()
        # Legacy shared token (only used when registry is None)
        self._legacy_token: str | None = os.environ.get(_ENV_A2A_TOKEN)

    # ------------------------------------------------------------------
    # Authentication helpers
    # ------------------------------------------------------------------

    def _resolve_caller(self, req: dict[str, Any]) -> CallerIdentity | None:
        """Resolve the caller identity for *req*.

        Returns:
            CallerIdentity  — authenticated caller (legacy or per-caller)
            None            — authentication failed (should be rejected)

        In legacy mode (no registry):
            - If no AUTODEV_A2A_TOKEN is configured, accept all (stdio trust).
            - If AUTODEV_A2A_TOKEN is configured, require a matching Bearer token
              in params._meta.authorization or the top-level "authorization" key.
            - On success, return the legacy shared-token identity.

        In per-caller mode (registry loaded):
            - Extract Bearer token from params._meta.authorization.
            - Authenticate via registry.
            - Return None if token missing, invalid, or expired.
        """
        params = req.get("params") or {}
        meta = params.get("_meta") or {}
        auth_header: str | None = (
            meta.get("authorization")
            or params.get("authorization")
        )
        bearer_token: str | None = None
        if auth_header and auth_header.startswith("Bearer "):
            bearer_token = auth_header[len("Bearer "):]

        # ---- Per-caller registry mode ----
        if self._registry is not None:
            if not bearer_token:
                return None
            return self._registry.authenticate(bearer_token)

        # ---- Legacy mode ----
        if not self._legacy_token:
            # No token configured — open / stdio trust mode
            return _make_legacy_identity()
        if bearer_token and bearer_token == self._legacy_token:
            return _make_legacy_identity()
        if not bearer_token:
            # Legacy: no token required when env var not set (already handled above),
            # but if the env var IS set, we require a matching token.
            return None
        # Provided token doesn't match
        return None

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

        # ------------------------------------------------------------------
        # Authentication gate — applied to all methods except initialize/ping
        # (those are always allowed so the client can establish the session).
        # ------------------------------------------------------------------
        _auth_exempt = {"initialize", "ping"}
        caller: CallerIdentity | None = None
        if method not in _auth_exempt:
            caller = self._resolve_caller(req)
            if caller is None and (self._registry is not None or self._legacy_token):
                # Registry mode: always enforce. Legacy mode: enforce only when
                # a token is configured.
                if is_notification:
                    return None
                return _error_response(req_id, -32001, "Unauthorized: valid Bearer token required")
        if caller is None:
            # initialize/ping or open legacy mode — treat as legacy identity
            caller = _make_legacy_identity()

        # Set caller in context for the duration of this request
        set_current_caller(caller)

        try:
            return self._dispatch(req, req_id, method, params, is_notification, caller)
        finally:
            set_current_caller(None)

    def _dispatch(
        self,
        req: dict[str, Any],
        req_id: Any,
        method: str,
        params: dict[str, Any],
        is_notification: bool,
        caller: CallerIdentity,
    ) -> dict[str, Any] | None:
        """Inner dispatch after authentication is resolved."""

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

            # --- Scope enforcement (per-caller mode only when registry active) ---
            required_scope = TOOL_SCOPES.get(name)
            if required_scope is not None and self._registry is not None:
                if not caller.has_scope(required_scope):
                    return _error_response(
                        req_id,
                        -32002,
                        f"Forbidden: caller {caller.caller_id!r} lacks scope {required_scope!r} required by tool {name!r}",
                    )

            # --- Pre-dispatch JSON Schema validation ---
            schema_error = _validate_required_params(tool.input_schema, arguments, name)
            if schema_error is not None:
                return _error_response(req_id, -32602, schema_error)

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
