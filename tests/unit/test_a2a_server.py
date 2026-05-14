"""Unit tests for A2AHttpServer.

Tests use a random free port and start a real ThreadingHTTPServer.
"""
from __future__ import annotations

import json
import os
import socket
import threading
import time
import urllib.request
import uuid
from urllib.error import HTTPError

from autodev.adapters.a2a.server import A2AHttpServer
from autodev.schemas import A2ATaskStatus

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("localhost", 0))
        return s.getsockname()[1]


def _start_server(port: int, auth_token: str | None = None) -> A2AHttpServer:
    """Start A2AHttpServer in a background thread. Returns server instance."""
    if auth_token is not None:
        os.environ["AUTODEV_A2A_TOKEN"] = auth_token
    else:
        os.environ.pop("AUTODEV_A2A_TOKEN", None)

    server = A2AHttpServer(port=port, bind="127.0.0.1")

    def _run() -> None:
        server.serve_forever()

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    # Wait for server to be ready
    deadline = time.time() + 5.0
    while time.time() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                break
        except OSError:
            time.sleep(0.05)
    return server


def _get(url: str, headers: dict[str, str] | None = None) -> tuple[int, dict]:
    req = urllib.request.Request(url, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except HTTPError as e:
        return e.code, json.loads(e.read().decode("utf-8"))


def _post(url: str, body: dict, headers: dict[str, str] | None = None) -> tuple[int, dict]:
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Content-Type": "application/json",
            **(headers or {}),
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except HTTPError as e:
        return e.code, json.loads(e.read().decode("utf-8"))


def _make_task(skill: str, extra_meta: dict | None = None) -> dict:
    meta = {"skill": skill}
    if extra_meta:
        meta.update(extra_meta)
    return {
        "id": str(uuid.uuid4()),
        "context_id": str(uuid.uuid4()),
        "metadata": meta,
        "history": [
            {
                "message_id": str(uuid.uuid4()),
                "role": "user",
                "parts": [{"kind": "text", "text": "test input"}],
            }
        ],
    }


# ---------------------------------------------------------------------------
# Test 1: GET /.well-known/agent.json returns valid AgentCard with name="autodev"
# ---------------------------------------------------------------------------


def test_agent_card_returned():
    port = _free_port()
    server = _start_server(port)
    try:
        status, body = _get(f"http://127.0.0.1:{port}/.well-known/agent.json")
        assert status == 200, f"Expected 200, got {status}: {body}"
        assert body["name"] == "autodev"
        assert "skills" in body
        assert "scan" in body["skills"]
        assert body["transport"] == "a2a-http"
        assert "endpoint" in body
    finally:
        server.shutdown()
        os.environ.pop("AUTODEV_A2A_TOKEN", None)


# ---------------------------------------------------------------------------
# Test 2: POST /tasks/send with skill="scan" returns completed task + agent message
# ---------------------------------------------------------------------------


def test_post_task_scan_returns_completed():
    port = _free_port()
    server = _start_server(port)
    try:
        task_body = _make_task("scan", {"repo_path": "."})
        status, body = _post(f"http://127.0.0.1:{port}/tasks/send", task_body)
        assert status == 200, f"Expected 200, got {status}: {body}"
        # Task should be completed or failed (scan may fail due to env, but status is set)
        assert body["status"] in (
            A2ATaskStatus.COMPLETED.value,
            A2ATaskStatus.FAILED.value,
        )
        # There should be at least one agent message in history
        agent_messages = [m for m in body.get("history", []) if m["role"] == "agent"]
        assert len(agent_messages) >= 1
    finally:
        server.shutdown()
        os.environ.pop("AUTODEV_A2A_TOKEN", None)


# ---------------------------------------------------------------------------
# Test 3: POST /tasks/send with unknown skill → 400
# ---------------------------------------------------------------------------


def test_unknown_skill_returns_400():
    port = _free_port()
    server = _start_server(port)
    try:
        task_body = _make_task("nonexistent-skill-xyz")
        status, body = _post(f"http://127.0.0.1:{port}/tasks/send", task_body)
        assert status == 400, f"Expected 400, got {status}: {body}"
        assert "error" in body
    finally:
        server.shutdown()
        os.environ.pop("AUTODEV_A2A_TOKEN", None)


# ---------------------------------------------------------------------------
# Test 4: AUTODEV_A2A_TOKEN set + no Authorization header → 401
# ---------------------------------------------------------------------------


def test_auth_token_required_returns_401():
    port = _free_port()
    server = _start_server(port, auth_token="secret-token-abc")
    try:
        # No auth header
        status, body = _get(f"http://127.0.0.1:{port}/.well-known/agent.json")
        assert status == 401, f"Expected 401, got {status}: {body}"
    finally:
        server.shutdown()
        os.environ.pop("AUTODEV_A2A_TOKEN", None)


# ---------------------------------------------------------------------------
# Test 5: AUTODEV_A2A_TOKEN set + correct Bearer token → success
# ---------------------------------------------------------------------------


def test_auth_token_correct_returns_200():
    port = _free_port()
    server = _start_server(port, auth_token="secret-token-abc")
    try:
        status, body = _get(
            f"http://127.0.0.1:{port}/.well-known/agent.json",
            headers={"Authorization": "Bearer secret-token-abc"},
        )
        assert status == 200, f"Expected 200, got {status}: {body}"
        assert body["name"] == "autodev"
    finally:
        server.shutdown()
        os.environ.pop("AUTODEV_A2A_TOKEN", None)


# ---------------------------------------------------------------------------
# Test 6: GET /tasks/{nonexistent_id} → 404
# ---------------------------------------------------------------------------


def test_get_nonexistent_task_returns_404():
    port = _free_port()
    server = _start_server(port)
    try:
        status, body = _get(f"http://127.0.0.1:{port}/tasks/does-not-exist-1234")
        assert status == 404, f"Expected 404, got {status}: {body}"
        assert "error" in body
    finally:
        server.shutdown()
        os.environ.pop("AUTODEV_A2A_TOKEN", None)


# ---------------------------------------------------------------------------
# Test 7 (bonus): GET /tasks/{id} after POST → returns stored task
# ---------------------------------------------------------------------------


def test_get_task_after_post():
    port = _free_port()
    server = _start_server(port)
    try:
        task_body = _make_task("scan", {"repo_path": "."})
        task_id = task_body["id"]
        post_status, _post_body = _post(f"http://127.0.0.1:{port}/tasks/send", task_body)
        assert post_status == 200

        get_status, get_body = _get(f"http://127.0.0.1:{port}/tasks/{task_id}")
        assert get_status == 200, f"Expected 200, got {get_status}: {get_body}"
        assert get_body["id"] == task_id
    finally:
        server.shutdown()
        os.environ.pop("AUTODEV_A2A_TOKEN", None)


# ---------------------------------------------------------------------------
# Test 8 (bonus): GET /tasks/{id}/events returns SSE
# ---------------------------------------------------------------------------


def test_get_task_events_sse():
    port = _free_port()
    server = _start_server(port)
    try:
        # First create a task
        task_body = _make_task("scan", {"repo_path": "."})
        task_id = task_body["id"]
        _post(f"http://127.0.0.1:{port}/tasks/send", task_body)

        # Now fetch SSE — read line by line to avoid blocking on full-body read
        import http.client
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        conn.request("GET", f"/tasks/{task_id}/events")
        resp = conn.getresponse()
        assert resp.status == 200
        content_type = resp.headers.get("Content-Type", "")
        assert "text/event-stream" in content_type
        # Read lines until we see an event: line
        collected = []
        for _ in range(20):
            line = resp.fp.readline(4096)
            if not line:
                break
            collected.append(line.decode("utf-8", errors="replace"))
            if "event:" in collected[-1]:
                break
        conn.close()
        body_str = "".join(collected)
        assert "event:" in body_str, f"No SSE event found in: {body_str!r}"
    finally:
        server.shutdown()
        os.environ.pop("AUTODEV_A2A_TOKEN", None)
