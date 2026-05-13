"""Integration tests: A2AHttpTransport round-trip via a local stdlib HTTP fake.

Uses stdlib only (no SRV-2 real server). Verifies end-to-end behaviour of
A2AHttpTransport including polling and auth, through A2AClient dispatch.
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

from autodev.adapters.a2a.client import A2AClient
from autodev.adapters.a2a.transports.http import A2AHttpTransport
from autodev.schemas import (
    AgentCard,
    A2AMessage,
    A2APart,
    A2ATask,
    A2ATaskStatus,
)


# ---------------------------------------------------------------------------
# Helpers (duplicated locally to keep tests independent from SRV-2)
# ---------------------------------------------------------------------------


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _make_task(text: str = "roundtrip test") -> A2ATask:
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


def _completed_payload(task_id: str, context_id: str, reply: str = "roundtrip OK") -> dict:
    return {
        "id": task_id,
        "context_id": context_id,
        "status": "completed",
        "history": [
            {
                "message_id": str(uuid.uuid4()),
                "role": "agent",
                "parts": [{"kind": "text", "text": reply}],
                "context_id": context_id,
                "task_id": task_id,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        ],
        "artifacts": [{"kind": "text", "text": reply}],
        "metadata": {},
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


class _EchoHandler(BaseHTTPRequestHandler):
    """Minimal A2A fake: echoes back a completed task with agent reply."""

    _auth_token: str | None = None
    _auth_errors: list[str] = []
    _received_tasks: list[dict] = []

    def log_message(self, *args: Any) -> None:
        pass

    def _read_body(self) -> bytes:
        length = int(self.headers.get("Content-Length", 0))
        return self.rfile.read(length) if length else b""

    def _send_json(self, status: int, payload: Any) -> None:
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:
        if self.path == "/tasks/send":
            raw = self._read_body()
            # Validate bearer auth if configured
            if type(self)._auth_token:
                auth = self.headers.get("Authorization", "")
                if auth != f"Bearer {type(self)._auth_token}":
                    type(self)._auth_errors.append(f"bad auth: {auth!r}")
                    self._send_json(401, {"error": "unauthorized"})
                    return
            try:
                task_dict = json.loads(raw)
            except Exception:
                self._send_json(400, {"error": "bad json"})
                return
            type(self)._received_tasks.append(task_dict)
            task_id = task_dict.get("id", str(uuid.uuid4()))
            context_id = task_dict.get("context_id", str(uuid.uuid4()))
            reply_text = "echo: " + "".join(
                p.get("text", "")
                for msg in task_dict.get("history", [])
                for p in msg.get("parts", [])
                if p.get("kind") == "text"
            )
            self._send_json(200, _completed_payload(task_id, context_id, reply=reply_text))
        else:
            self._send_json(404, {"error": "not found"})

    def do_GET(self) -> None:
        self._read_body()
        if self.path == "/.well-known/agent.json":
            self._send_json(200, {
                "name": "echo-agent",
                "description": "Integration test echo agent",
                "version": "0.0.1",
                "capabilities": ["echo"],
                "skills": ["echo"],
                "transport": "a2a-http",
                "endpoint": None,
            })
        else:
            self._send_json(404, {"error": "not found"})

    def do_HEAD(self) -> None:
        self.send_response(200)
        self.end_headers()


def _start_echo_server(auth_token: str | None = None) -> tuple[str, HTTPServer]:
    port = _free_port()

    class Handler(_EchoHandler):
        pass

    Handler._auth_token = auth_token
    Handler._auth_errors = []
    Handler._received_tasks = []

    srv = HTTPServer(("127.0.0.1", port), Handler)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    time.sleep(0.05)
    return f"http://127.0.0.1:{port}", srv


# ---------------------------------------------------------------------------
# Integration test 1 — full round-trip via A2AHttpTransport directly
# ---------------------------------------------------------------------------


def test_roundtrip_send_task_via_transport() -> None:
    """A2AHttpTransport.send_task → fake echo server → COMPLETED task with echo body."""
    base, srv = _start_echo_server()
    try:
        task = _make_task("scan the repo please")
        transport = A2AHttpTransport(base, poll_interval=0.05, max_poll_attempts=5)
        card = AgentCard(name="echo-agent", transport="a2a-http", endpoint=base)
        result = transport.send_task(card, task)

        assert result.status == A2ATaskStatus.COMPLETED
        texts = [a.text for a in result.artifacts if a.text]
        assert any("scan the repo please" in t for t in texts), f"artifacts={texts}"
    finally:
        srv.shutdown()


# ---------------------------------------------------------------------------
# Integration test 2 — round-trip via A2AClient dispatch (a2a-http branch)
# ---------------------------------------------------------------------------


def test_roundtrip_via_a2a_client_dispatch(monkeypatch: Any) -> None:
    """A2AClient.send() dispatches to A2AHttpTransport when card.transport='a2a-http'."""
    base, srv = _start_echo_server()
    try:
        # Make sure AUTODEV_A2A_TOKEN is unset so no auth confusion
        monkeypatch.delenv("AUTODEV_A2A_TOKEN", raising=False)

        task = _make_task("client dispatch test")
        card = AgentCard(
            name="echo-agent",
            transport="a2a-http",
            endpoint=base,
        )
        client = A2AClient()
        result = client.send(card, task)

        assert result.status == A2ATaskStatus.COMPLETED
        texts = [a.text for a in result.artifacts if a.text]
        assert any("client dispatch test" in t for t in texts), f"artifacts={texts}"
    finally:
        srv.shutdown()
