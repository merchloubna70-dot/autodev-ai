"""Unit tests for A2AHttpTransport — stdlib urllib, no new pip deps.

Uses stdlib http.server.ThreadingHTTPServer to spin up a fake A2A server on
a random port. Each fixture creates a fresh server to avoid port conflicts.
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

from autodev.adapters.a2a.transports.http import A2AHttpTransport
from autodev.schemas import (
    AgentCard,
    A2AMessage,
    A2APart,
    A2ATask,
    A2ATaskStatus,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


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


def _make_card(endpoint: str) -> AgentCard:
    return AgentCard(
        name="test-agent",
        transport="a2a-http",
        endpoint=endpoint,
    )


def _completed_task_dict(task_id: str, context_id: str) -> dict[str, Any]:
    return {
        "id": task_id,
        "context_id": context_id,
        "status": "completed",
        "history": [],
        "artifacts": [{"kind": "text", "text": "done!"}],
        "metadata": {},
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# Generic fake server builder
# ---------------------------------------------------------------------------


class _FakeHandler(BaseHTTPRequestHandler):
    """Handler wired by the fixture via class attributes."""

    responses: dict[str, tuple[int, Any]] = {}   # path → (status, body)
    received_headers: list[dict] = []            # captured for assertion
    received_bodies: list[bytes] = []

    def log_message(self, *args: Any) -> None:  # silence access log
        pass

    def _dispatch(self, method: str) -> None:
        # read body
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length) if length else b""
        type(self).received_headers.append(dict(self.headers))
        type(self).received_bodies.append(body)

        path = self.path.split("?")[0]
        if path in type(self).responses:
            code, payload = type(self).responses[path]
        else:
            code, payload = 404, {"error": "not found"}

        if isinstance(payload, (dict, list)):
            encoded = json.dumps(payload).encode()
            ctype = "application/json"
        elif isinstance(payload, bytes):
            encoded = payload
            ctype = "application/octet-stream"
        elif isinstance(payload, str):
            encoded = payload.encode()
            ctype = "text/plain"
        else:
            encoded = b""
            ctype = "application/octet-stream"

        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def do_GET(self) -> None:
        self._dispatch("GET")

    def do_POST(self) -> None:
        self._dispatch("POST")

    def do_HEAD(self) -> None:
        self.send_response(200)
        self.end_headers()


def _start_server(responses: dict[str, tuple[int, Any]]) -> tuple[str, HTTPServer, threading.Thread]:
    """Start a ThreadingHTTPServer in a background daemon thread. Returns (base_url, server, thread)."""
    port = _free_port()

    class Handler(_FakeHandler):
        pass

    Handler.responses = responses
    Handler.received_headers = []
    Handler.received_bodies = []

    srv = HTTPServer(("127.0.0.1", port), Handler)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    time.sleep(0.05)  # brief settle
    return f"http://127.0.0.1:{port}", srv, t


# ---------------------------------------------------------------------------
# Test 1 — send_task with COMPLETED initial response
# ---------------------------------------------------------------------------


def test_send_task_completed_immediately() -> None:
    """Server returns COMPLETED on POST /tasks/send → transport returns that task."""
    task = _make_task("scan everything")
    completed = _completed_task_dict(task.id, task.context_id)
    base, srv, _ = _start_server({"/tasks/send": (200, completed)})
    try:
        transport = A2AHttpTransport(base, poll_interval=0.05, max_poll_attempts=5)
        result = transport.send_task(_make_card(base), task)
        assert result.status == A2ATaskStatus.COMPLETED
        assert any(a.text == "done!" for a in result.artifacts)
    finally:
        srv.shutdown()


# ---------------------------------------------------------------------------
# Test 2 — send_task with non-completed initial response, then polls
# ---------------------------------------------------------------------------


def test_send_task_polls_until_completed() -> None:
    """Server returns WORKING first, then COMPLETED on poll."""
    task = _make_task("long task")
    working = {
        "id": task.id,
        "context_id": task.context_id,
        "status": "working",
        "history": [],
        "artifacts": [],
        "metadata": {},
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": None,
    }
    completed = _completed_task_dict(task.id, task.context_id)

    poll_path = f"/tasks/{task.id}"
    call_count = {"n": 0}

    class CountingHandler(_FakeHandler):
        def _dispatch(self, method: str) -> None:
            if self.path == poll_path:
                call_count["n"] += 1
                # Return WORKING the first time, COMPLETED after
                if call_count["n"] < 2:
                    payload = working
                else:
                    payload = completed
                body = json.dumps(payload).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            if self.path == "/tasks/send":
                body = json.dumps(working).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            super()._dispatch(method)

    port = _free_port()
    CountingHandler.responses = {}
    CountingHandler.received_headers = []
    CountingHandler.received_bodies = []
    srv = HTTPServer(("127.0.0.1", port), CountingHandler)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    time.sleep(0.05)
    base = f"http://127.0.0.1:{port}"
    try:
        transport = A2AHttpTransport(base, poll_interval=0.05, max_poll_attempts=10)
        result = transport.send_task(_make_card(base), task)
        assert result.status == A2ATaskStatus.COMPLETED
        assert call_count["n"] >= 2
    finally:
        srv.shutdown()


# ---------------------------------------------------------------------------
# Test 3 — unreachable endpoint returns FAILED, no exception
# ---------------------------------------------------------------------------


def test_send_task_unreachable_returns_failed() -> None:
    """Unreachable server → FAILED task, never raises."""
    # Use a port that is definitely not listening
    base = "http://127.0.0.1:1"  # port 1 refuses connections on macOS/Linux
    task = _make_task("hi")
    transport = A2AHttpTransport(base, poll_interval=0.05, max_poll_attempts=2)
    result = transport.send_task(_make_card(base), task)
    assert result.status == A2ATaskStatus.FAILED
    assert any("A2A-HTTP" in (a.text or "") for a in result.artifacts)


# ---------------------------------------------------------------------------
# Test 4 — discover_agent_card returns parsed AgentCard
# ---------------------------------------------------------------------------


def test_discover_agent_card_returns_card() -> None:
    """GET /.well-known/agent.json → parsed AgentCard."""
    card_data = {
        "name": "remote-agent",
        "description": "A test remote agent",
        "version": "1.0.0",
        "capabilities": ["scan", "review"],
        "skills": ["scan"],
        "transport": "a2a-http",
        "endpoint": None,
    }
    base, srv, _ = _start_server({"/.well-known/agent.json": (200, card_data)})
    try:
        transport = A2AHttpTransport(base)
        card = transport.discover_agent_card()
        assert card is not None
        assert card.name == "remote-agent"
        assert "scan" in card.capabilities
    finally:
        srv.shutdown()


# ---------------------------------------------------------------------------
# Test 5 — discover_agent_card on broken JSON → returns None
# ---------------------------------------------------------------------------


def test_discover_agent_card_broken_json_returns_none() -> None:
    """Broken JSON body → discover_agent_card returns None, no exception."""
    base, srv, _ = _start_server({"/.well-known/agent.json": (200, b"not json {{{{")})
    try:
        transport = A2AHttpTransport(base)
        card = transport.discover_agent_card()
        assert card is None
    finally:
        srv.shutdown()


# ---------------------------------------------------------------------------
# Test 6 — Bearer auth token sent as Authorization header
# ---------------------------------------------------------------------------


def test_auth_token_sent_in_header() -> None:
    """When auth_token is set, Authorization: Bearer <token> must be sent."""
    task = _make_task("auth test")
    completed = _completed_task_dict(task.id, task.context_id)

    captured_headers: list[dict] = []

    class CapturingHandler(_FakeHandler):
        def _dispatch(self, method: str) -> None:
            length = int(self.headers.get("Content-Length", 0))
            self.rfile.read(length)
            captured_headers.append(dict(self.headers))
            payload = completed
            body = json.dumps(payload).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    port = _free_port()
    CapturingHandler.responses = {}
    CapturingHandler.received_headers = []
    CapturingHandler.received_bodies = []
    srv = HTTPServer(("127.0.0.1", port), CapturingHandler)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    time.sleep(0.05)
    base = f"http://127.0.0.1:{port}"
    try:
        transport = A2AHttpTransport(base, auth_token="my-secret-token")
        transport.send_task(_make_card(base), task)
        assert len(captured_headers) >= 1
        auth_header = captured_headers[0].get("Authorization", "")
        assert auth_header == "Bearer my-secret-token", f"Got: {auth_header!r}"
    finally:
        srv.shutdown()
