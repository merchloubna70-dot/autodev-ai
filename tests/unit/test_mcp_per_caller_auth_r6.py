"""R6 — Per-caller identity + scope-based authorization for MCP server.

Tests:
1. IdentityRegistry round-trip (load from JSON, lookup by token, missing token returns None)
2. CallerIdentity.has_scope() / is_expired()
3. Scope check: tool with required scope, caller with/without scope (allowed vs denied)
4. Audit log records caller_id for every invocation
5. Backward compat: when AUTODEV_MCP_IDENTITIES unset, legacy single-token mode still works
6. Apply-mode now requires BOTH mcp:apply scope AND env AND request flag (triple gate)
7. Expired identity returns None from authenticate()
8. Registry mode: missing / invalid token → -32001 Unauthorized
9. Scope enforcement: caller without tool scope → -32002 Forbidden
10. Legacy mode (no token env var) passes all requests through with legacy_shared_token
"""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _sha256(token: str) -> str:
    digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def _write_registry(tmp_path: Path, entries: dict) -> Path:
    """Write a JSON registry file and return its path."""
    p = tmp_path / "identities.json"
    p.write_text(json.dumps(entries), encoding="utf-8")
    return p


def _make_server_clean():
    """Instantiate MCPServer with a clean environment (no AUTODEV_MCP_IDENTITIES)."""
    from autodev.mcp_server.server import MCPServer
    return MCPServer()


def _dispatch(server, method: str, params: dict, req_id: int = 1) -> dict:
    req = {"jsonrpc": "2.0", "id": req_id, "method": method, "params": params}
    return server._handle(json.dumps(req))


def _tools_call(server, tool_name: str, arguments: dict, bearer: str | None = None, req_id: int = 1) -> dict:
    params: dict[str, Any] = {"name": tool_name, "arguments": arguments}
    if bearer is not None:
        params["_meta"] = {"authorization": f"Bearer {bearer}"}
    return _dispatch(server, "tools/call", params, req_id)


# ---------------------------------------------------------------------------
# 1. CallerIdentity unit tests
# ---------------------------------------------------------------------------

class TestCallerIdentity:
    def test_has_scope_positive(self):
        from autodev.mcp_server.identity import CallerIdentity
        ci = CallerIdentity(caller_id="bot", display_name="Bot", scopes=["mcp:read", "mcp:write"])
        assert ci.has_scope("mcp:read") is True
        assert ci.has_scope("mcp:write") is True

    def test_has_scope_negative(self):
        from autodev.mcp_server.identity import CallerIdentity
        ci = CallerIdentity(caller_id="bot", display_name="Bot", scopes=["mcp:read"])
        assert ci.has_scope("mcp:apply") is False

    def test_not_expired_when_no_expiry(self):
        from autodev.mcp_server.identity import CallerIdentity
        ci = CallerIdentity(caller_id="x", display_name="X", scopes=[], expires_at=None)
        assert ci.is_expired() is False

    def test_not_expired_when_future(self):
        from autodev.mcp_server.identity import CallerIdentity
        future = datetime.now(tz=timezone.utc) + timedelta(hours=1)
        ci = CallerIdentity(caller_id="x", display_name="X", scopes=[], expires_at=future)
        assert ci.is_expired() is False

    def test_expired_when_past(self):
        from autodev.mcp_server.identity import CallerIdentity
        past = datetime.now(tz=timezone.utc) - timedelta(seconds=1)
        ci = CallerIdentity(caller_id="x", display_name="X", scopes=[], expires_at=past)
        assert ci.is_expired() is True


# ---------------------------------------------------------------------------
# 2. IdentityRegistry round-trip
# ---------------------------------------------------------------------------

class TestIdentityRegistry:
    def test_load_and_lookup_valid_token(self, tmp_path):
        from autodev.mcp_server.identity import IdentityRegistry
        token = "super-secret-abc123"
        reg_path = _write_registry(tmp_path, {
            "ci-bot": {
                "display_name": "CI Bot",
                "scopes": ["mcp:read", "mcp:write"],
                "hashed_token": _sha256(token),
            }
        })
        reg = IdentityRegistry(reg_path)
        identity = reg.authenticate(token)
        assert identity is not None
        assert identity.caller_id == "ci-bot"
        assert identity.display_name == "CI Bot"
        assert "mcp:read" in identity.scopes
        assert "mcp:write" in identity.scopes

    def test_missing_token_returns_none(self, tmp_path):
        from autodev.mcp_server.identity import IdentityRegistry
        reg_path = _write_registry(tmp_path, {
            "ci-bot": {
                "scopes": ["mcp:read"],
                "hashed_token": _sha256("valid-token"),
            }
        })
        reg = IdentityRegistry(reg_path)
        assert reg.authenticate("wrong-token") is None

    def test_expired_token_returns_none(self, tmp_path):
        from autodev.mcp_server.identity import IdentityRegistry
        token = "expiring-token"
        past = (datetime.now(tz=timezone.utc) - timedelta(hours=1)).isoformat()
        reg_path = _write_registry(tmp_path, {
            "expired-bot": {
                "scopes": ["mcp:read"],
                "hashed_token": _sha256(token),
                "expires_at": past,
            }
        })
        reg = IdentityRegistry(reg_path)
        assert reg.authenticate(token) is None

    def test_non_expired_token_returns_identity(self, tmp_path):
        from autodev.mcp_server.identity import IdentityRegistry
        token = "valid-future-token"
        future = (datetime.now(tz=timezone.utc) + timedelta(hours=24)).isoformat()
        reg_path = _write_registry(tmp_path, {
            "future-bot": {
                "scopes": ["mcp:read"],
                "hashed_token": _sha256(token),
                "expires_at": future,
            }
        })
        reg = IdentityRegistry(reg_path)
        identity = reg.authenticate(token)
        assert identity is not None
        assert identity.caller_id == "future-bot"

    def test_multiple_callers(self, tmp_path):
        from autodev.mcp_server.identity import IdentityRegistry
        token_a, token_b = "token-a", "token-b"
        reg_path = _write_registry(tmp_path, {
            "caller-a": {"scopes": ["mcp:read"], "hashed_token": _sha256(token_a)},
            "caller-b": {"scopes": ["mcp:apply"], "hashed_token": _sha256(token_b)},
        })
        reg = IdentityRegistry(reg_path)
        assert reg.authenticate(token_a).caller_id == "caller-a"
        assert reg.authenticate(token_b).caller_id == "caller-b"

    def test_len(self, tmp_path):
        from autodev.mcp_server.identity import IdentityRegistry
        reg_path = _write_registry(tmp_path, {
            "a": {"scopes": [], "hashed_token": _sha256("ta")},
            "b": {"scopes": [], "hashed_token": _sha256("tb")},
        })
        reg = IdentityRegistry(reg_path)
        assert len(reg) == 2

    def test_hash_token_helper(self):
        from autodev.mcp_server.identity import _hash_token
        h = _hash_token("hello")
        assert h.startswith("sha256:")
        assert len(h) == 7 + 64  # "sha256:" + 64 hex chars


# ---------------------------------------------------------------------------
# 3. requires_scope decorator
# ---------------------------------------------------------------------------

class TestRequiresScope:
    def test_no_caller_raises(self):
        from autodev.mcp_server.identity import requires_scope, set_current_caller
        set_current_caller(None)

        @requires_scope("mcp:read")
        def fn():
            return "ok"

        with pytest.raises(PermissionError, match="No authenticated caller"):
            fn()

    def test_caller_with_scope_passes(self):
        from autodev.mcp_server.identity import CallerIdentity, requires_scope, set_current_caller
        ci = CallerIdentity(caller_id="x", display_name="X", scopes=["mcp:read"])
        set_current_caller(ci)

        @requires_scope("mcp:read")
        def fn():
            return "ok"

        assert fn() == "ok"
        set_current_caller(None)

    def test_caller_without_scope_raises(self):
        from autodev.mcp_server.identity import CallerIdentity, requires_scope, set_current_caller
        ci = CallerIdentity(caller_id="read-only", display_name="R", scopes=["mcp:read"])
        set_current_caller(ci)

        @requires_scope("mcp:apply")
        def fn():
            return "ok"

        with pytest.raises(PermissionError, match="lacks required scope"):
            fn()
        set_current_caller(None)


# ---------------------------------------------------------------------------
# 4. Audit log includes caller_id
# ---------------------------------------------------------------------------

class TestAuditLogCallerId:
    def test_audit_log_has_caller_id_per_caller_mode(self, tmp_path):
        from autodev.mcp_server.identity import CallerIdentity, set_current_caller
        from autodev.mcp_server.tools import _write_audit_log

        ci = CallerIdentity(caller_id="test-agent", display_name="Test", scopes=["mcp:read"])
        set_current_caller(ci)

        log_file = tmp_path / "audit.log"
        with patch.dict(os.environ, {"AUTODEV_MCP_AUDIT_LOG": str(log_file)}):
            _write_audit_log("autodev_scan", {"repo_path": "/tmp/x"}, "/tmp/x", "allowed")

        set_current_caller(None)
        lines = log_file.read_text().strip().splitlines()
        assert len(lines) == 1
        entry = json.loads(lines[0])
        assert entry["caller_id"] == "test-agent"
        assert entry["tool"] == "autodev_scan"
        assert entry["decision"] == "allowed"

    def test_audit_log_has_legacy_caller_id(self, tmp_path):
        from autodev.mcp_server.identity import LEGACY_CALLER_ID, set_current_caller
        from autodev.mcp_server.tools import _write_audit_log

        set_current_caller(None)  # simulate legacy / no context

        log_file = tmp_path / "audit_legacy.log"
        with patch.dict(os.environ, {"AUTODEV_MCP_AUDIT_LOG": str(log_file)}):
            _write_audit_log("autodev_scan", {"repo_path": "/tmp/y"}, "/tmp/y", "allowed")

        lines = log_file.read_text().strip().splitlines()
        entry = json.loads(lines[0])
        assert entry["caller_id"] == LEGACY_CALLER_ID


# ---------------------------------------------------------------------------
# 5. Backward compat: legacy single-token mode still works
# ---------------------------------------------------------------------------

class TestLegacyMode:
    def test_no_identities_env_no_a2a_token_passes(self):
        """No AUTODEV_MCP_IDENTITIES + no A2A token = open/stdio trust, any call works."""
        env = {k: v for k, v in os.environ.items()
               if k not in ("AUTODEV_MCP_IDENTITIES", "AUTODEV_A2A_TOKEN")}
        with patch.dict(os.environ, env, clear=True):
            server = _make_server_clean()
        # initialize and ping should always work
        resp = _dispatch(server, "initialize", {})
        assert "result" in resp

    def test_legacy_token_accepted(self):
        """AUTODEV_A2A_TOKEN set, correct token in request → accepted."""
        env = {k: v for k, v in os.environ.items()
               if k not in ("AUTODEV_MCP_IDENTITIES", "AUTODEV_A2A_TOKEN")}
        env["AUTODEV_A2A_TOKEN"] = "my-legacy-secret"
        with patch.dict(os.environ, env, clear=True):
            server = _make_server_clean()
        # Provide correct token in tools/list
        params: dict[str, Any] = {"_meta": {"authorization": "Bearer my-legacy-secret"}}
        resp = _dispatch(server, "tools/list", params)
        assert "result" in resp

    def test_legacy_token_rejected_when_wrong(self):
        """AUTODEV_A2A_TOKEN set, wrong token in request → -32001."""
        env = {k: v for k, v in os.environ.items()
               if k not in ("AUTODEV_MCP_IDENTITIES", "AUTODEV_A2A_TOKEN")}
        env["AUTODEV_A2A_TOKEN"] = "my-legacy-secret"
        with patch.dict(os.environ, env, clear=True):
            server = _make_server_clean()
        params: dict[str, Any] = {"_meta": {"authorization": "Bearer wrong-token"}}
        resp = _dispatch(server, "tools/list", params)
        assert resp["error"]["code"] == -32001

    def test_legacy_token_rejected_when_missing(self):
        """AUTODEV_A2A_TOKEN set, no token in request → -32001."""
        env = {k: v for k, v in os.environ.items()
               if k not in ("AUTODEV_MCP_IDENTITIES", "AUTODEV_A2A_TOKEN")}
        env["AUTODEV_A2A_TOKEN"] = "my-legacy-secret"
        with patch.dict(os.environ, env, clear=True):
            server = _make_server_clean()
        resp = _dispatch(server, "tools/list", {})
        assert resp["error"]["code"] == -32001


# ---------------------------------------------------------------------------
# 6. Per-caller registry mode
# ---------------------------------------------------------------------------

class TestRegistryMode:
    def _make_server_with_registry(self, reg_path: Path) -> Any:
        env = {k: v for k, v in os.environ.items()
               if k not in ("AUTODEV_MCP_IDENTITIES", "AUTODEV_A2A_TOKEN")}
        env["AUTODEV_MCP_IDENTITIES"] = str(reg_path)
        with patch.dict(os.environ, env, clear=True):
            from autodev.mcp_server.server import MCPServer
            return MCPServer()

    def test_valid_token_accepted(self, tmp_path):
        token = "valid-registry-token"
        reg_path = _write_registry(tmp_path, {
            "my-agent": {
                "scopes": ["mcp:read", "mcp:write"],
                "hashed_token": _sha256(token),
                "display_name": "My Agent",
            }
        })
        server = self._make_server_with_registry(reg_path)
        params: dict[str, Any] = {"_meta": {"authorization": f"Bearer {token}"}}
        resp = _dispatch(server, "tools/list", params)
        assert "result" in resp

    def test_missing_token_returns_unauthorized(self, tmp_path):
        reg_path = _write_registry(tmp_path, {
            "my-agent": {"scopes": ["mcp:read"], "hashed_token": _sha256("secret")}
        })
        server = self._make_server_with_registry(reg_path)
        resp = _dispatch(server, "tools/list", {})
        assert resp["error"]["code"] == -32001

    def test_invalid_token_returns_unauthorized(self, tmp_path):
        reg_path = _write_registry(tmp_path, {
            "my-agent": {"scopes": ["mcp:read"], "hashed_token": _sha256("secret")}
        })
        server = self._make_server_with_registry(reg_path)
        params: dict[str, Any] = {"_meta": {"authorization": "Bearer wrong"}}
        resp = _dispatch(server, "tools/list", params)
        assert resp["error"]["code"] == -32001

    def test_caller_without_scope_gets_forbidden(self, tmp_path):
        """Caller with only mcp:read trying to call a mcp:write tool → -32002."""
        token = "read-only-token"
        reg_path = _write_registry(tmp_path, {
            "read-only-agent": {
                "scopes": ["mcp:read"],
                "hashed_token": _sha256(token),
            }
        })
        server = self._make_server_with_registry(reg_path)
        # autodev_classify_input requires mcp:write
        with patch("autodev.mcp_server.tools._handle_classify_input", return_value={"ok": True}):
            resp = _tools_call(
                server,
                "autodev_classify_input",
                {"text": "hello"},
                bearer=token,
            )
        assert resp["error"]["code"] == -32002

    def test_caller_with_scope_passes(self, tmp_path):
        """Caller with mcp:write can call a mcp:write tool."""
        token = "write-token"
        reg_path = _write_registry(tmp_path, {
            "write-agent": {
                "scopes": ["mcp:read", "mcp:write"],
                "hashed_token": _sha256(token),
            }
        })
        server = self._make_server_with_registry(reg_path)
        with patch("autodev.mcp_server.tools._handle_classify_input", return_value={"ok": True}):
            resp = _tools_call(
                server,
                "autodev_classify_input",
                {"text": "hello"},
                bearer=token,
            )
        # Should NOT have a -32002 error; either result or isError from handler
        assert "error" not in resp or resp.get("error", {}).get("code") not in (-32001, -32002)


# ---------------------------------------------------------------------------
# 7. Apply-mode triple gate
# ---------------------------------------------------------------------------

class TestApplyModeTripleGate:
    """Apply mode now requires THREE gates: mcp:apply scope + env + request flag."""

    def _make_server_with_registry(self, reg_path: Path) -> Any:
        env = {k: v for k, v in os.environ.items()
               if k not in ("AUTODEV_MCP_IDENTITIES", "AUTODEV_A2A_TOKEN",
                            "AUTODEV_MCP_ALLOW_APPLY")}
        env["AUTODEV_MCP_IDENTITIES"] = str(reg_path)
        with patch.dict(os.environ, env, clear=True):
            from autodev.mcp_server.server import MCPServer
            return MCPServer()

    def _make_server_legacy(self) -> Any:
        env = {k: v for k, v in os.environ.items()
               if k not in ("AUTODEV_MCP_IDENTITIES", "AUTODEV_A2A_TOKEN",
                            "AUTODEV_MCP_ALLOW_APPLY")}
        with patch.dict(os.environ, env, clear=True):
            from autodev.mcp_server.server import MCPServer
            return MCPServer()

    def test_scope_missing_blocks_apply(self, tmp_path):
        """Caller lacks mcp:apply scope → denied even with env + flag."""
        token = "no-apply-scope"
        reg_path = _write_registry(tmp_path, {
            "limited": {
                "scopes": ["mcp:read", "mcp:write"],  # no mcp:apply
                "hashed_token": _sha256(token),
            }
        })
        env = {k: v for k, v in os.environ.items()
               if k not in ("AUTODEV_MCP_IDENTITIES", "AUTODEV_A2A_TOKEN")}
        env["AUTODEV_MCP_IDENTITIES"] = str(reg_path)
        env["AUTODEV_MCP_ALLOW_APPLY"] = "1"

        from autodev.mcp_server.identity import CallerIdentity, set_current_caller
        from autodev.mcp_server.tools import _check_apply_mode_allowed

        ci = CallerIdentity(caller_id="limited", display_name="L", scopes=["mcp:read", "mcp:write"])
        set_current_caller(ci)
        try:
            result = _check_apply_mode_allowed(
                "autodev_deliver_project",
                {"allow_apply": True},
                "/tmp/r",
            )
        finally:
            set_current_caller(None)

        assert result is not None
        assert "mcp:apply" in result["content"][0]["text"]

    def test_env_missing_blocks_apply(self, tmp_path):
        """mcp:apply scope present + flag present, but env var not set → denied."""
        from autodev.mcp_server.identity import CallerIdentity, set_current_caller
        from autodev.mcp_server.tools import _check_apply_mode_allowed

        ci = CallerIdentity(caller_id="full-agent", display_name="F", scopes=["mcp:read", "mcp:write", "mcp:apply"])
        set_current_caller(ci)
        env = {k: v for k, v in os.environ.items() if k != "AUTODEV_MCP_ALLOW_APPLY"}
        # Ensure AUTODEV_MCP_ALLOW_APPLY is NOT set
        env.pop("AUTODEV_MCP_ALLOW_APPLY", None)
        try:
            with patch.dict(os.environ, env, clear=True):
                result = _check_apply_mode_allowed(
                    "autodev_deliver_project",
                    {"allow_apply": True},
                    "/tmp/r",
                )
        finally:
            set_current_caller(None)

        assert result is not None
        assert "AUTODEV_MCP_ALLOW_APPLY" in result["content"][0]["text"]

    def test_flag_missing_blocks_apply(self, tmp_path):
        """mcp:apply scope + env present, but allow_apply=False in args → denied."""
        from autodev.mcp_server.identity import CallerIdentity, set_current_caller
        from autodev.mcp_server.tools import _check_apply_mode_allowed

        ci = CallerIdentity(caller_id="full-agent", display_name="F", scopes=["mcp:read", "mcp:write", "mcp:apply"])
        set_current_caller(ci)
        try:
            with patch.dict(os.environ, {"AUTODEV_MCP_ALLOW_APPLY": "1"}):
                result = _check_apply_mode_allowed(
                    "autodev_deliver_project",
                    {"allow_apply": False},  # flag missing
                    "/tmp/r",
                )
        finally:
            set_current_caller(None)

        assert result is not None
        assert "allow_apply=true" in result["content"][0]["text"]

    def test_all_three_gates_pass(self, tmp_path):
        """mcp:apply scope + env + flag all present → None (allowed)."""
        from autodev.mcp_server.identity import CallerIdentity, set_current_caller
        from autodev.mcp_server.tools import _check_apply_mode_allowed

        ci = CallerIdentity(caller_id="full-agent", display_name="F", scopes=["mcp:read", "mcp:write", "mcp:apply"])
        set_current_caller(ci)
        try:
            with patch.dict(os.environ, {"AUTODEV_MCP_ALLOW_APPLY": "1"}):
                result = _check_apply_mode_allowed(
                    "autodev_deliver_project",
                    {"allow_apply": True},
                    "/tmp/r",
                )
        finally:
            set_current_caller(None)

        assert result is None  # None = allowed

    def test_legacy_mode_triple_gate_still_works(self, tmp_path):
        """In legacy mode, legacy_shared_token identity has all scopes → gates 2+3 still apply."""
        from autodev.mcp_server.identity import _make_legacy_identity, set_current_caller
        from autodev.mcp_server.tools import _check_apply_mode_allowed

        ci = _make_legacy_identity()
        set_current_caller(ci)
        try:
            # Gate 2 missing: flag=False
            with patch.dict(os.environ, {"AUTODEV_MCP_ALLOW_APPLY": "1"}):
                result = _check_apply_mode_allowed(
                    "autodev_deliver_project",
                    {"allow_apply": False},
                    "/tmp/r",
                )
        finally:
            set_current_caller(None)

        assert result is not None  # still denied (missing flag)

    def test_legacy_mode_all_gates_pass(self, tmp_path):
        """Legacy mode with all gates: scope (implicit) + env + flag → allowed."""
        from autodev.mcp_server.identity import _make_legacy_identity, set_current_caller
        from autodev.mcp_server.tools import _check_apply_mode_allowed

        ci = _make_legacy_identity()
        set_current_caller(ci)
        try:
            with patch.dict(os.environ, {"AUTODEV_MCP_ALLOW_APPLY": "1"}):
                result = _check_apply_mode_allowed(
                    "autodev_deliver_project",
                    {"allow_apply": True},
                    "/tmp/r",
                )
        finally:
            set_current_caller(None)

        assert result is None  # allowed


# ---------------------------------------------------------------------------
# 8. Tool scope table integrity
# ---------------------------------------------------------------------------

class TestToolScopeTable:
    def test_all_tools_have_scope_entry(self):
        from autodev.mcp_server.tools import TOOL_SCOPES, get_tools
        tools = get_tools()
        for tool in tools:
            assert tool.name in TOOL_SCOPES, (
                f"Tool {tool.name!r} has no entry in TOOL_SCOPES"
            )

    def test_scope_values_are_known(self):
        from autodev.mcp_server.identity import ALL_SCOPES
        from autodev.mcp_server.tools import TOOL_SCOPES
        for tool_name, scope in TOOL_SCOPES.items():
            assert scope in ALL_SCOPES, (
                f"Tool {tool_name!r} has unknown scope {scope!r}"
            )
