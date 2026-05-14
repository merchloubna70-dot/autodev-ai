"""Integration tests for `autodev a2a-serve` CLI subprocess.

Starts the server as a real subprocess, sends HTTP requests, then kills it.
"""
from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
import urllib.request
import uuid
from pathlib import Path
from urllib.error import HTTPError

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Resolve the autodev CLI: prefer venv's autodev script, fall back to
# `python -m autodev.cli` (works if autodev has a __main__.py or we call
# the module directly via its CLI entrypoint).
_AUTODEV_CMD: list[str] = []
_VENV_AUTODEV = Path(__file__).parents[2] / ".venv" / "bin" / "autodev"
if _VENV_AUTODEV.exists():
    _AUTODEV_CMD = [str(_VENV_AUTODEV)]
else:
    # fallback: use sys.executable with the installed entrypoint
    _AUTODEV_CMD = [sys.executable, "-c",
                    "from autodev.cli import app; app()"]


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("localhost", 0))
        return s.getsockname()[1]


def _wait_for_port(host: str, port: int, timeout: float = 10.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection((host, port), timeout=0.3):
                return True
        except OSError:
            time.sleep(0.1)
    return False


def _get(url: str) -> tuple[int, dict]:
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except HTTPError as e:
        return e.code, json.loads(e.read().decode("utf-8"))


def _post(url: str, body: dict) -> tuple[int, dict]:
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except HTTPError as e:
        return e.code, json.loads(e.read().decode("utf-8"))


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_a2a_serve_agent_card():
    """autodev a2a-serve: GET /.well-known/agent.json returns valid AgentCard."""
    port = _free_port()
    env = {**os.environ, "AUTODEV_A2A_TOKEN": ""}  # disable token auth
    proc = subprocess.Popen(
        [*_AUTODEV_CMD, "a2a-serve", "--port", str(port), "--bind", "127.0.0.1"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
    )
    try:
        ready = _wait_for_port("127.0.0.1", port, timeout=15.0)
        assert ready, f"Server did not start on port {port} in time"

        status, body = _get(f"http://127.0.0.1:{port}/.well-known/agent.json")
        assert status == 200, f"Expected 200, got {status}: {body}"
        assert body["name"] == "autodev"
        assert "transport" in body
        assert body["transport"] == "a2a-http"
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


def test_a2a_serve_task_send_classify_input():
    """autodev a2a-serve: POST /tasks/send with skill=classify-input returns a task."""
    port = _free_port()
    env = {**os.environ, "AUTODEV_A2A_TOKEN": ""}
    proc = subprocess.Popen(
        [*_AUTODEV_CMD, "a2a-serve", "--port", str(port), "--bind", "127.0.0.1"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
    )
    try:
        ready = _wait_for_port("127.0.0.1", port, timeout=15.0)
        assert ready, f"Server did not start on port {port} in time"

        task_body = {
            "id": str(uuid.uuid4()),
            "context_id": str(uuid.uuid4()),
            "metadata": {"skill": "classify-input"},
            "history": [
                {
                    "message_id": str(uuid.uuid4()),
                    "role": "user",
                    "parts": [{"kind": "text", "text": "Fix the login bug in auth.py"}],
                }
            ],
        }
        status, body = _post(f"http://127.0.0.1:{port}/tasks/send", task_body)
        assert status == 200, f"Expected 200, got {status}: {body}"
        # Task id should match
        assert body["id"] == task_body["id"]
        # Status should be either completed or failed (not submitted/working)
        assert body["status"] in ("completed", "failed")
        # At least one agent response
        agent_msgs = [m for m in body.get("history", []) if m["role"] == "agent"]
        assert len(agent_msgs) >= 1
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
