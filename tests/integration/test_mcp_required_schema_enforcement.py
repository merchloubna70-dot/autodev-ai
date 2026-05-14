"""Integration tests: MCP server enforces JSON Schema 'required' fields.

Strategy under test:
  - REJECT missing required params  → JSON-RPC error -32602 Invalid params
  - REJECT wrong type for required  → JSON-RPC error -32602 Invalid params
  - IGNORE unknown extra args       → tool dispatches normally (no -32602)

Tools covered (5):
  autodev_deliver_project  required: [repo_path, brief_text]
  autodev_run_issue        required: [repo_path, issue_text]
  autodev_scan             required: [repo_path]
  autodev_report           required: [repo_path, run_id]
  autodev_roundtable       required: [topic, skills]

Test count: >= 12 (3 patterns × 5 tools = 15 tests + 2 edge-case tests).
"""
from __future__ import annotations

import json
import os
from typing import Any
from unittest import mock

from autodev.mcp_server.server import MCPServer

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_server() -> MCPServer:
    return MCPServer()


def _dispatch(
    server: MCPServer,
    name: str,
    arguments: dict[str, Any],
    req_id: int = 1,
) -> dict[str, Any]:
    """Dispatch a tools/call request and return the full response dict."""
    req = {
        "jsonrpc": "2.0",
        "id": req_id,
        "method": "tools/call",
        "params": {"name": name, "arguments": arguments},
    }
    resp = server._handle(json.dumps(req))
    assert resp is not None, "Server returned None for a non-notification request"
    return resp


def _assert_invalid_params(resp: dict[str, Any], *, tool: str = "") -> None:
    """Assert resp is a JSON-RPC -32602 Invalid params error."""
    assert "error" in resp, (
        f"Expected JSON-RPC error for {tool!r}, got result: {resp.get('result')!r}"
    )
    code = resp["error"]["code"]
    assert code == -32602, (
        f"Expected -32602 Invalid params for {tool!r}, got {code}"
    )


def _assert_not_invalid_params(resp: dict[str, Any], *, tool: str = "") -> None:
    """Assert resp is NOT a -32602 error (extra unknown args should be ignored)."""
    if "error" in resp:
        code = resp["error"]["code"]
        assert code != -32602, (
            f"Tool {tool!r} unexpectedly returned -32602 for extra unknown args: "
            f"{resp['error']['message']!r}"
        )


# ---------------------------------------------------------------------------
# Pattern A: missing required param → -32602
# ---------------------------------------------------------------------------

class TestMissingRequiredParam:
    """Each tool called without its required params must return -32602."""

    def test_deliver_project_missing_repo_path(self):
        srv = _make_server()
        resp = _dispatch(srv, "autodev_deliver_project", {"brief_text": "Build a CLI"})
        _assert_invalid_params(resp, tool="autodev_deliver_project")

    def test_deliver_project_missing_brief_text(self):
        srv = _make_server()
        resp = _dispatch(srv, "autodev_deliver_project", {"repo_path": "/tmp/proj"})
        _assert_invalid_params(resp, tool="autodev_deliver_project")

    def test_deliver_project_missing_both_required(self):
        srv = _make_server()
        resp = _dispatch(srv, "autodev_deliver_project", {})
        _assert_invalid_params(resp, tool="autodev_deliver_project")

    def test_run_issue_missing_repo_path(self):
        srv = _make_server()
        resp = _dispatch(srv, "autodev_run_issue", {"issue_text": "Fix null pointer"})
        _assert_invalid_params(resp, tool="autodev_run_issue")

    def test_run_issue_missing_issue_text(self):
        srv = _make_server()
        resp = _dispatch(srv, "autodev_run_issue", {"repo_path": "/tmp/proj"})
        _assert_invalid_params(resp, tool="autodev_run_issue")

    def test_scan_missing_repo_path(self):
        srv = _make_server()
        resp = _dispatch(srv, "autodev_scan", {})
        _assert_invalid_params(resp, tool="autodev_scan")

    def test_report_missing_repo_path(self):
        srv = _make_server()
        resp = _dispatch(srv, "autodev_report", {"run_id": "run-123"})
        _assert_invalid_params(resp, tool="autodev_report")

    def test_report_missing_run_id(self):
        srv = _make_server()
        resp = _dispatch(srv, "autodev_report", {"repo_path": "/tmp/proj"})
        _assert_invalid_params(resp, tool="autodev_report")

    def test_roundtable_missing_topic(self):
        srv = _make_server()
        resp = _dispatch(srv, "autodev_roundtable", {"skills": ["architecture"]})
        _assert_invalid_params(resp, tool="autodev_roundtable")

    def test_roundtable_missing_skills(self):
        srv = _make_server()
        resp = _dispatch(srv, "autodev_roundtable", {"topic": "Review API design"})
        _assert_invalid_params(resp, tool="autodev_roundtable")

    def test_roundtable_missing_both(self):
        srv = _make_server()
        resp = _dispatch(srv, "autodev_roundtable", {})
        _assert_invalid_params(resp, tool="autodev_roundtable")


# ---------------------------------------------------------------------------
# Pattern B: all required + extra unknown arg → tool dispatches (no -32602)
# ---------------------------------------------------------------------------

class TestExtraUnknownArgsIgnored:
    """Extra unknown args must not trigger -32602; the tool should proceed normally."""

    def test_scan_extra_arg_not_rejected(self, tmp_path):
        """autodev_scan with repo_path + unknown extra arg does not return -32602."""
        srv = _make_server()
        # Point at a real temp directory so path_safety passes; patch the agent
        mock_result = mock.MagicMock()
        mock_result.model_dump_json.return_value = json.dumps({"language": "python"})
        with mock.patch(
            "autodev.agents.repo_explorer.RepoExplorerAgent.explore",
            return_value=mock_result,
        ):
            resp = _dispatch(srv, "autodev_scan", {
                "repo_path": str(tmp_path),
                "unknown_future_flag": True,
            })
        _assert_not_invalid_params(resp, tool="autodev_scan")

    def test_roundtable_extra_arg_not_rejected(self):
        """autodev_roundtable with required + unknown extra arg does not return -32602."""
        srv = _make_server()
        mock_conv = mock.MagicMock()
        mock_conv.messages = []
        mock_conv.model_dump.return_value = {}
        mock_msg = mock.MagicMock()
        mock_msg.parts = []
        with mock.patch(
            "autodev.agents.roundtable.RoundtableAgent.discuss_and_synthesize",
            return_value=(mock_conv, mock_msg),
        ):
            resp = _dispatch(srv, "autodev_roundtable", {
                "topic": "API security",
                "skills": ["security"],
                "extra_unknown_key": "value",
            })
        _assert_not_invalid_params(resp, tool="autodev_roundtable")

    def test_deliver_project_extra_arg_not_rejected(self, tmp_path):
        """autodev_deliver_project with required + unknown extra arg does not return -32602."""
        srv = _make_server()
        mock_run = mock.MagicMock()
        mock_run.run_id = "run-ignore-extra"
        mock_run.state.release_check = None
        with mock.patch(
            "autodev.flows.project_delivery_flow.ProjectDeliveryFlow.run",
            return_value=mock_run,
        ), mock.patch.dict(os.environ, {"FACTORY_FORCE_MOCK": "1"}):
            resp = _dispatch(srv, "autodev_deliver_project", {
                "repo_path": str(tmp_path),
                "brief_text": "hello world",
                "surprise_new_field": 99,
            })
        _assert_not_invalid_params(resp, tool="autodev_deliver_project")


# ---------------------------------------------------------------------------
# Pattern C: wrong type for required field → -32602
# ---------------------------------------------------------------------------

class TestWrongTypeForRequiredField:
    """Wrong type for a required field must return -32602."""

    def test_scan_repo_path_wrong_type_integer(self):
        """autodev_scan: repo_path must be string; passing int returns -32602."""
        srv = _make_server()
        resp = _dispatch(srv, "autodev_scan", {"repo_path": 42})
        _assert_invalid_params(resp, tool="autodev_scan")

    def test_scan_repo_path_wrong_type_bool(self):
        """autodev_scan: repo_path must be string; passing bool returns -32602."""
        srv = _make_server()
        resp = _dispatch(srv, "autodev_scan", {"repo_path": True})
        _assert_invalid_params(resp, tool="autodev_scan")

    def test_deliver_project_repo_path_wrong_type(self):
        """autodev_deliver_project: repo_path must be string; passing list returns -32602."""
        srv = _make_server()
        resp = _dispatch(srv, "autodev_deliver_project", {
            "repo_path": ["/tmp/proj"],
            "brief_text": "build it",
        })
        _assert_invalid_params(resp, tool="autodev_deliver_project")

    def test_deliver_project_brief_text_wrong_type(self):
        """autodev_deliver_project: brief_text must be string; passing dict returns -32602."""
        srv = _make_server()
        resp = _dispatch(srv, "autodev_deliver_project", {
            "repo_path": "/tmp/proj",
            "brief_text": {"summary": "build a CLI"},
        })
        _assert_invalid_params(resp, tool="autodev_deliver_project")

    def test_roundtable_topic_wrong_type(self):
        """autodev_roundtable: topic must be string; passing int returns -32602."""
        srv = _make_server()
        resp = _dispatch(srv, "autodev_roundtable", {
            "topic": 123,
            "skills": ["architecture"],
        })
        _assert_invalid_params(resp, tool="autodev_roundtable")

    def test_roundtable_skills_wrong_type(self):
        """autodev_roundtable: skills must be array; passing string returns -32602."""
        srv = _make_server()
        resp = _dispatch(srv, "autodev_roundtable", {
            "topic": "design",
            "skills": "architecture",  # should be a list
        })
        _assert_invalid_params(resp, tool="autodev_roundtable")

    def test_run_issue_issue_text_wrong_type(self):
        """autodev_run_issue: issue_text must be string; passing int returns -32602."""
        srv = _make_server()
        resp = _dispatch(srv, "autodev_run_issue", {
            "repo_path": "/tmp/proj",
            "issue_text": 9999,
        })
        _assert_invalid_params(resp, tool="autodev_run_issue")


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    """Edge cases for schema enforcement."""

    def test_error_message_names_missing_fields(self):
        """Error message should mention the missing field names."""
        srv = _make_server()
        resp = _dispatch(srv, "autodev_roundtable", {})
        assert "error" in resp
        msg = resp["error"]["message"]
        # At least one of the missing fields should appear in the message
        assert "topic" in msg or "skills" in msg, (
            f"Error message should name missing fields, got: {msg!r}"
        )

    def test_error_code_is_exactly_minus_32602(self):
        """Error code must be exactly -32602, not -32601 or any other value."""
        srv = _make_server()
        resp = _dispatch(srv, "autodev_scan", {})
        assert "error" in resp
        assert resp["error"]["code"] == -32602

    def test_valid_call_still_works_after_validation(self, tmp_path):
        """After a rejected call, a subsequent valid call must succeed."""
        srv = _make_server()
        # First call: rejected (missing required)
        bad_resp = _dispatch(srv, "autodev_scan", {}, req_id=1)
        _assert_invalid_params(bad_resp, tool="autodev_scan")

        # Second call: valid (with required params + mocked handler)
        mock_result = mock.MagicMock()
        mock_result.model_dump_json.return_value = json.dumps({"language": "python"})
        with mock.patch(
            "autodev.agents.repo_explorer.RepoExplorerAgent.explore",
            return_value=mock_result,
        ):
            good_resp = _dispatch(srv, "autodev_scan", {"repo_path": str(tmp_path)}, req_id=2)

        _assert_not_invalid_params(good_resp, tool="autodev_scan")
        assert "result" in good_resp, f"Expected successful result: {good_resp!r}"
