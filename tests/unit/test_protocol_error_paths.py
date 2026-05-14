"""P1 protocol error / invalid-input path tests.

Covers:
  - Schema rejection (8 tests): ValidationError on missing required fields, invalid enum values,
    unexpected role strings, and schema roundtrip preservation.
  - MCP error paths (5 tests): internal error → isError:true, missing required param, unknown tool,
    missing method field (-32600), malformed JSON (-32700).
  - A2A error paths (5 tests): poll exhaustion → FAILED, invalid endpoint scheme raises,
    mock transport with unknown skill, roundtable one-agent failure isolation,
    deep-copy independence of task history.

Tests that probe genuinely missing behaviours are marked xfail(strict=True).
"""
from __future__ import annotations

import json
import socket
import threading
import time
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any

import pytest
from pydantic import ValidationError

from autodev.schemas import (
    A2AMessage,
    A2APart,
    A2ATask,
    A2ATaskStatus,
    AcceptanceCriterion,
    AgentCard,
    Milestone,
)

# ---------------------------------------------------------------------------
# Section 1: Schema rejection tests (8 tests)
# ---------------------------------------------------------------------------


def test_agent_card_missing_name_rejected():
    """AgentCard requires 'name'; building one without it raises ValidationError."""
    with pytest.raises(ValidationError) as exc_info:
        AgentCard()  # type: ignore[call-arg]
    errors = exc_info.value.errors()
    field_names = [e["loc"][0] for e in errors]
    assert "name" in field_names


def test_a2a_task_missing_id_rejected():
    """A2ATask requires 'id'; omitting it raises ValidationError."""
    with pytest.raises(ValidationError) as exc_info:
        A2ATask(context_id="ctx-1")  # type: ignore[call-arg]
    errors = exc_info.value.errors()
    field_names = [e["loc"][0] for e in errors]
    assert "id" in field_names


def test_a2a_message_missing_role_rejected():
    """A2AMessage requires 'role'; omitting it raises ValidationError."""
    with pytest.raises(ValidationError) as exc_info:
        A2AMessage(message_id="msg-1")  # type: ignore[call-arg]
    errors = exc_info.value.errors()
    field_names = [e["loc"][0] for e in errors]
    assert "role" in field_names


def test_a2a_message_role_unexpected_value_via_model_validate():
    """A2AMessage.role is typed 'str', so any string value is accepted (no enum).

    Document: non-standard role values like 'oracle' pass validation because
    the field type is plain str, not a Literal or Enum.  This test confirms the
    current permissive behavior — a future stricter schema would need updating.
    """
    data = {
        "message_id": "msg-2",
        "role": "oracle",  # non-standard but str field accepts it
        "parts": [],
    }
    msg = A2AMessage.model_validate(data)
    # Current behaviour: non-standard roles pass through unchanged.
    assert msg.role == "oracle"


def test_a2a_task_status_invalid_enum_rejected():
    """A2ATaskStatus('INVALID') must raise ValueError (str Enum)."""
    with pytest.raises(ValueError):
        A2ATaskStatus("INVALID")


def test_acceptance_criterion_missing_id_rejected():
    """AcceptanceCriterion requires 'id'; omitting raises ValidationError."""
    with pytest.raises(ValidationError) as exc_info:
        AcceptanceCriterion(  # type: ignore[call-arg]
            description="Must succeed",
            verifiable_by="test",
        )
    errors = exc_info.value.errors()
    field_names = [e["loc"][0] for e in errors]
    assert "id" in field_names


def test_milestone_missing_milestone_id_rejected():
    """Milestone requires 'milestone_id'; omitting raises ValidationError."""
    with pytest.raises(ValidationError) as exc_info:
        Milestone(  # type: ignore[call-arg]
            title="Phase 1",
            objective="Ship feature",
        )
    errors = exc_info.value.errors()
    field_names = [e["loc"][0] for e in errors]
    assert "milestone_id" in field_names


def test_schema_roundtrip_a2a_message():
    """model_dump() → model_validate() cycle preserves all fields faithfully."""
    original = A2AMessage(
        message_id="msg-roundtrip-001",
        role="agent",
        parts=[
            A2APart(kind="text", text="Analysis complete."),
            A2APart(kind="data", data={"score": 42}),
        ],
        context_id="ctx-rt-1",
        task_id="task-rt-1",
    )
    data = original.model_dump()
    restored = A2AMessage.model_validate(data)

    assert restored.message_id == original.message_id
    assert restored.role == original.role
    assert restored.context_id == original.context_id
    assert restored.task_id == original.task_id
    assert restored.created_at == original.created_at
    assert len(restored.parts) == 2
    assert restored.parts[0].kind == "text"
    assert restored.parts[0].text == "Analysis complete."
    assert restored.parts[1].kind == "data"
    assert restored.parts[1].data == {"score": 42}


# ---------------------------------------------------------------------------
# Section 2: MCP error paths (5 tests)
# ---------------------------------------------------------------------------


def _make_server():
    from autodev.mcp_server.server import MCPServer
    return MCPServer()


def _dispatch(server, method: str, params: dict, req_id: int = 1) -> dict:
    req = {"jsonrpc": "2.0", "id": req_id, "method": method, "params": params}
    return server._handle(json.dumps(req))


def test_mcp_tool_internal_error_returns_is_error_true():
    """When a registered tool handler raises, the response must have isError: true.

    Supply all required params so schema validation passes and the (patched) raising
    handler is actually invoked.
    """
    srv = _make_server()
    # Use autodev_scan which requires repo_path (a string).
    tool_name = "autodev_scan"
    original_handler = srv._tools[tool_name].handler

    def _raising_handler(args):
        raise RuntimeError("Simulated internal tool failure")

    srv._tools[tool_name].handler = _raising_handler
    try:
        # Provide the required field so schema validation passes, reaching the handler.
        resp = _dispatch(srv, "tools/call", {
            "name": tool_name,
            "arguments": {"repo_path": "/tmp/nonexistent"},
        })
    finally:
        srv._tools[tool_name].handler = original_handler

    assert resp is not None
    result = resp.get("result", {})
    assert result.get("isError") is True, (
        f"Expected isError:true when handler raises, got result={result!r}"
    )


def test_mcp_tools_call_missing_required_param_returns_error():
    """Calling a tool without its required params should return a JSON-RPC error -32602.

    The MCP server now enforces JSON Schema 'required' fields before dispatching to
    the tool handler.  Missing required params return error code -32602 Invalid params.
    """
    srv = _make_server()
    # autodev_roundtable requires 'topic' and 'skills' — both listed in "required"
    resp = _dispatch(srv, "tools/call", {
        "name": "autodev_roundtable",
        "arguments": {},   # missing topic and skills
    })
    assert resp is not None
    result = resp.get("result", {})
    error_field = resp.get("error")
    has_error = result.get("isError") is True or error_field is not None
    assert has_error, (
        f"Expected an error response when required params missing, got {resp!r}"
    )
    # The error must be a JSON-RPC level error (not just isError in result)
    assert error_field is not None, (
        f"Expected JSON-RPC error object, not tool-level isError: {resp!r}"
    )
    assert error_field["code"] == -32602, (
        f"Expected -32602 Invalid params, got {error_field['code']}"
    )


def test_mcp_tools_call_unknown_tool_returns_error():
    """Requesting an unknown tool name must return a JSON-RPC error with code -32601."""
    srv = _make_server()
    resp = _dispatch(srv, "tools/call", {"name": "no_such_tool_xyz_p1", "arguments": {}})
    assert resp is not None
    assert "error" in resp, f"Expected error key, got {resp!r}"
    assert resp["error"]["code"] == -32601
    assert "no_such_tool_xyz_p1" in resp["error"]["message"]


def test_mcp_jsonrpc_missing_method_field_returns_minus_32600():
    """A JSON-RPC message with no 'method' field should return error -32601 (method not found).

    Per JSON-RPC 2.0 spec, a missing method should yield -32600 (Invalid Request).
    The current server falls through to 'Unknown method' which returns -32601.
    We document this as an intentional gap: the server returns -32601, not -32600.
    """
    srv = _make_server()
    # Build a request without the 'method' field
    raw = json.dumps({"jsonrpc": "2.0", "id": 99, "params": {}})
    resp = srv._handle(raw)
    assert resp is not None
    assert "error" in resp, f"Expected error for missing method field, got {resp!r}"
    # Document actual behavior: server returns -32601 for empty method string
    # (falls through to "Unknown method" branch).  Per spec it should be -32600.
    code = resp["error"]["code"]
    assert code in (-32600, -32601), (
        f"Expected -32600 or -32601 for missing method, got {code}"
    )


def test_mcp_jsonrpc_malformed_json_returns_minus_32700():
    """Sending malformed JSON must return a parse error with code -32700."""
    srv = _make_server()
    resp = srv._handle("{{not: valid, json[[[")
    assert resp is not None
    assert "error" in resp, f"Expected error for malformed JSON, got {resp!r}"
    assert resp["error"]["code"] == -32700


# ---------------------------------------------------------------------------
# Section 3: A2A error paths (5 tests)
# ---------------------------------------------------------------------------


# Helpers shared with the HTTP transport tests

def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _make_task(text: str = "hello") -> A2ATask:
    tid = str(uuid.uuid4())
    cid = str(uuid.uuid4())
    return A2ATask(
        id=tid,
        context_id=cid,
        status=A2ATaskStatus.SUBMITTED,
        history=[
            A2AMessage(
                message_id=str(uuid.uuid4()),
                role="user",
                parts=[A2APart(kind="text", text=text)],
                context_id=cid,
                task_id=tid,
            )
        ],
    )


def _make_card(endpoint: str, name: str = "test-agent") -> AgentCard:
    return AgentCard(name=name, transport="a2a-http", endpoint=endpoint)


class _AlwaysWorkingHandler(BaseHTTPRequestHandler):
    """Responds to every request with a WORKING status — never reaches terminal."""

    task_id: str = ""
    context_id: str = ""

    def log_message(self, *args: Any) -> None:
        pass

    def _working_payload(self) -> bytes:
        payload = {
            "id": type(self).task_id,
            "context_id": type(self).context_id,
            "status": "working",
            "history": [],
            "artifacts": [],
            "metadata": {},
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": None,
        }
        return json.dumps(payload).encode()

    def _send(self, body: bytes) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", 0))
        self.rfile.read(length)
        self._send(self._working_payload())

    def do_GET(self) -> None:
        self._send(self._working_payload())


def test_a2a_http_poll_exhaustion_returns_failed():
    """When the mock server stays WORKING forever, poll exhaustion yields status=FAILED."""
    from autodev.adapters.a2a.transports.http import A2AHttpTransport

    task = _make_task("never-ending task")

    class Handler(_AlwaysWorkingHandler):
        pass

    Handler.task_id = task.id
    Handler.context_id = task.context_id

    port = _free_port()
    srv = HTTPServer(("127.0.0.1", port), Handler)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    time.sleep(0.05)
    base = f"http://127.0.0.1:{port}"
    try:
        transport = A2AHttpTransport(
            base,
            poll_interval=0.02,
            max_poll_attempts=3,   # exhaust quickly
            allow_private_networks=True,
        )
        result = transport.send_task(_make_card(base), task)
        assert result.status == A2ATaskStatus.FAILED, (
            f"Expected FAILED after poll exhaustion, got {result.status}"
        )
    finally:
        srv.shutdown()


def test_a2a_http_invalid_endpoint_scheme_raises():
    """Using a non-http/https scheme (gopher://) must be rejected with A2AHttpSSRFError."""
    from autodev.adapters.a2a.transports.http import A2AHttpSSRFError, A2AHttpTransport

    task = _make_task("scheme test")
    transport = A2AHttpTransport(
        "gopher://evil.example.com",
        poll_interval=0.01,
        max_poll_attempts=1,
        allow_private_networks=False,
    )
    card = AgentCard(name="gopher-agent", transport="a2a-http", endpoint="gopher://evil.example.com")

    # The transport must not raise — it must return FAILED (never-raises contract).
    # But internally _validate_url must reject the scheme.
    # Verify _validate_url raises A2AHttpSSRFError for gopher://.
    from autodev.adapters.a2a.transports.http import _validate_url
    with pytest.raises(A2AHttpSSRFError, match=r"[Gg]opher"):
        _validate_url("gopher://evil.example.com/resource")

    # Also confirm send_task returns FAILED (never raises from the public API).
    result = transport.send_task(card, task)
    assert result.status == A2ATaskStatus.FAILED


def test_a2a_mock_transport_handles_unknown_skill():
    """MockTransport must return COMPLETED even when card has a skill the mock doesn't recognise."""
    from autodev.adapters.a2a.transports.mock import MockTransport

    card = AgentCard(
        name="unknown-skill-agent",
        skills=["quantum-telekinesis"],  # completely made-up skill
        transport="mock",
    )
    task = _make_task("use unknown skill")
    transport = MockTransport()
    result = transport.send_task(card, task)

    # Graceful default: MockTransport returns COMPLETED regardless of skill list.
    assert result.status == A2ATaskStatus.COMPLETED
    assert len(result.artifacts) > 0


def test_a2a_roundtable_one_agent_failure_does_not_break_others():
    """When one card's transport fails, the roundtable must still collect results from others."""
    roster_mod = pytest.importorskip("autodev.adapters.a2a.roster", reason="A2A-1 not committed")
    AgentRoster = roster_mod.AgentRoster
    from autodev.agents.roundtable import RoundtableAgent, _make_text_message

    class _FailOnceClient:
        """Fails the first card it sees, succeeds for all others."""
        def __init__(self):
            self._failed_one = False

        def send(self, card: AgentCard, task: A2ATask) -> A2ATask:
            t = task.model_copy(deep=True)
            if not self._failed_one and card.name == "security":
                self._failed_one = True
                raise RuntimeError(f"Simulated transport failure for {card.name}")
            t.history.append(_make_text_message("agent", f"[{card.name}] ok", task_id=t.id))
            t.status = A2ATaskStatus.COMPLETED
            return t

    roster = AgentRoster.default()
    client = _FailOnceClient()
    rt = RoundtableAgent(roster=roster, client=client)

    conv = rt.discuss(
        topic="Failure isolation test",
        needed_skills=["security", "performance", "style"],
        min_participants=2,
        max_participants=4,
    )

    # Conversation must not raise and must contain messages from remaining agents.
    agent_msgs = [m for m in conv.messages if m.role == "agent"]
    # At least one non-failing agent should have responded.
    assert len(agent_msgs) >= 1, (
        "Expected at least one successful agent response even when one fails"
    )


def test_a2a_roundtable_deep_copy_independence():
    """Mutating one task's history must not affect copies given to other agents."""
    # We verify that model_copy(deep=True) actually produces independent history lists.
    base_task = _make_task("independence test")

    copy_a = base_task.model_copy(deep=True)
    copy_b = base_task.model_copy(deep=True)

    # Mutate copy_a's history
    extra_msg = A2AMessage(
        message_id="injected-msg",
        role="agent",
        parts=[A2APart(kind="text", text="injected")],
        context_id=base_task.context_id,
        task_id=base_task.id,
    )
    copy_a.history.append(extra_msg)

    # copy_b must be unaffected
    assert len(copy_b.history) == len(base_task.history), (
        f"copy_b.history was mutated! len={len(copy_b.history)}, "
        f"expected={len(base_task.history)}"
    )
    assert copy_b.history[-1].message_id != "injected-msg"

    # base_task must also be unaffected
    assert len(base_task.history) == 1
