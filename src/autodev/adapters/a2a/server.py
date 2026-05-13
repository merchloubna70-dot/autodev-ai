"""A2A HTTP server — exposes autodev as an A2A-compatible agent endpoint.

Uses stdlib http.server.ThreadingHTTPServer only (no new pip deps).

Endpoints:
  GET  /.well-known/agent.json   — AgentCard
  POST /tasks/send               — dispatch task to skill handler
  GET  /tasks/{id}               — fetch stored task
  GET  /tasks/{id}/events        — SSE stream of task status events

Security:
  - Default bind: 127.0.0.1 (local only)
  - Optional Bearer-token auth via env AUTODEV_A2A_TOKEN
  - Warn loudly when binding 0.0.0.0
"""
from __future__ import annotations

import json
import os
import signal
import threading
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlparse

from ...schemas import (
    A2AMessage,
    A2APart,
    A2ATask,
    A2ATaskStatus,
    AgentCard,
)
from .handlers import SKILL_HANDLERS


# ---------------------------------------------------------------------------
# AgentCard for autodev
# ---------------------------------------------------------------------------


def _autodev_card(base_url: str) -> AgentCard:
    return AgentCard(
        name="autodev",
        description=(
            "CrewAI + Codex CLI + Claude Code multi-CLI software factory. "
            "Accepts A2A tasks from Google ADK, Bedrock, Azure, and custom agents."
        ),
        version="1.0.0",
        capabilities=[
            "software-delivery",
            "code-review",
            "project-planning",
            "release-management",
            "roundtable",
        ],
        skills=[
            "deliver-project",
            "run-issue",
            "scan",
            "report",
            "release-check",
            "roundtable",
            "classify-input",
            "create-prd",
        ],
        transport="a2a-http",
        endpoint=base_url,
        auth_scheme="bearer",
        model_hint="sonnet",
        tags=["factory", "multi-cli"],
    )


# ---------------------------------------------------------------------------
# In-memory task store
# ---------------------------------------------------------------------------


class _TaskStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._tasks: dict[str, A2ATask] = {}

    def put(self, task: A2ATask) -> None:
        with self._lock:
            self._tasks[task.id] = task

    def get(self, task_id: str) -> A2ATask | None:
        with self._lock:
            return self._tasks.get(task_id)

    def all(self) -> list[A2ATask]:
        with self._lock:
            return list(self._tasks.values())


# ---------------------------------------------------------------------------
# Request handler
# ---------------------------------------------------------------------------


class _A2AHandler(BaseHTTPRequestHandler):
    """HTTP request handler for the A2A server."""

    # Injected by A2AHttpServer before serving
    _store: _TaskStore
    _base_url: str
    _auth_token: str | None

    # ------------------------------------------------------------------ misc

    def log_message(self, fmt: str, *args: Any) -> None:  # noqa: ANN001
        # Suppress default Apache-style access log; use print for important events
        pass

    def _check_auth(self) -> bool:
        """Return True if request is authorized."""
        token = self._auth_token
        if not token:
            return True  # no auth required
        auth_header = self.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return False
        return auth_header[len("Bearer "):] == token

    def _send_json(self, status: int, data: Any) -> None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_error_json(self, status: int, message: str) -> None:
        self._send_json(status, {"error": message, "status": status})

    def _read_body(self) -> bytes:
        length = int(self.headers.get("Content-Length", 0))
        return self.rfile.read(length) if length > 0 else b""

    # ----------------------------------------------------------------- GET

    def do_GET(self) -> None:
        if not self._check_auth():
            self._send_error_json(401, "Unauthorized: missing or invalid Bearer token")
            return

        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")

        if path == "/.well-known/agent.json":
            self._handle_agent_card()
        elif path.startswith("/tasks/") and path.endswith("/events"):
            task_id = path[len("/tasks/"):-len("/events")]
            self._handle_task_events(task_id)
        elif path.startswith("/tasks/"):
            task_id = path[len("/tasks/"):]
            self._handle_get_task(task_id)
        else:
            self._send_error_json(404, f"Not found: {path}")

    def _handle_agent_card(self) -> None:
        card = _autodev_card(self._base_url)
        self._send_json(200, card.model_dump(mode="json"))

    def _handle_get_task(self, task_id: str) -> None:
        task = self._store.get(task_id)
        if task is None:
            self._send_error_json(404, f"Task not found: {task_id}")
            return
        self._send_json(200, task.model_dump(mode="json"))

    def _handle_task_events(self, task_id: str) -> None:
        """SSE stream: emit initial submitted event + final status event."""
        task = self._store.get(task_id)
        if task is None:
            self._send_error_json(404, f"Task not found: {task_id}")
            return

        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.end_headers()

        def _sse_event(event_type: str, data: Any) -> bytes:
            payload = json.dumps(data, ensure_ascii=False)
            return f"event: {event_type}\ndata: {payload}\n\n".encode("utf-8")

        # Initial status event
        try:
            self.wfile.write(
                _sse_event("task-status", {
                    "task_id": task_id,
                    "status": task.status.value,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
            )
            self.wfile.flush()

            # Final event — task content
            self.wfile.write(
                _sse_event("task-complete", task.model_dump(mode="json"))
            )
            self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            pass

    # ----------------------------------------------------------------- POST

    def do_POST(self) -> None:
        if not self._check_auth():
            self._send_error_json(401, "Unauthorized: missing or invalid Bearer token")
            return

        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")

        if path == "/tasks/send":
            self._handle_tasks_send()
        else:
            self._send_error_json(404, f"Not found: {path}")

    def _handle_tasks_send(self) -> None:
        raw = self._read_body()
        try:
            data = json.loads(raw) if raw else {}
        except json.JSONDecodeError as exc:
            self._send_error_json(400, f"Invalid JSON: {exc}")
            return

        # Build or validate task
        try:
            task = A2ATask.model_validate(data)
        except Exception as exc:  # noqa: BLE001
            # Build minimal task from the data dict
            task = A2ATask(
                id=data.get("id") or str(uuid.uuid4()),
                context_id=data.get("context_id") or str(uuid.uuid4()),
                metadata=data.get("metadata") or {},
                history=[
                    A2AMessage(
                        message_id=str(uuid.uuid4()),
                        role="user",
                        parts=[A2APart(kind="text", text=str(data))],
                    )
                ] if "history" not in data else [],
            )

        # Determine skill
        skill = task.metadata.get("skill", "")
        if not skill:
            self._send_error_json(400, "Missing 'skill' key in task.metadata")
            return

        handler = SKILL_HANDLERS.get(skill)
        if handler is None:
            self._send_error_json(400, f"Unknown skill: {skill!r}. Available: {sorted(SKILL_HANDLERS)}")
            return

        # Set working status, store, dispatch
        task.status = A2ATaskStatus.WORKING
        task.updated_at = datetime.now(timezone.utc).isoformat()
        self._store.put(task)

        try:
            task = handler(task)
        except Exception as exc:  # noqa: BLE001
            task.status = A2ATaskStatus.FAILED
            task.history.append(A2AMessage(
                message_id=str(uuid.uuid4()),
                role="agent",
                parts=[A2APart(kind="text", text=f"Handler error: {exc}")],
                task_id=task.id,
            ))

        task.updated_at = datetime.now(timezone.utc).isoformat()
        self._store.put(task)
        self._send_json(200, task.model_dump(mode="json"))


# ---------------------------------------------------------------------------
# Server class
# ---------------------------------------------------------------------------


class A2AHttpServer:
    """Threaded HTTP server exposing autodev as an A2A agent.

    Parameters
    ----------
    port:
        TCP port to listen on (default 8421).
    bind:
        IP to bind. Default ``127.0.0.1`` (local-only). Pass ``"0.0.0.0"``
        to expose publicly — a warning is printed.
    auth_token_env:
        Name of the env-var that holds the bearer token. When the env-var is
        unset/empty, auth is disabled (suitable for local-only use).
    """

    def __init__(
        self,
        port: int = 8421,
        bind: str = "127.0.0.1",
        auth_token_env: str = "AUTODEV_A2A_TOKEN",
    ) -> None:
        self.port = port
        self.bind = bind
        self.auth_token_env = auth_token_env
        self._store = _TaskStore()
        self._server: ThreadingHTTPServer | None = None

    @property
    def base_url(self) -> str:
        return f"http://{self.bind}:{self.port}"

    def _make_handler_class(self) -> type:
        store = self._store
        base_url = self.base_url
        auth_token: str | None = os.environ.get(self.auth_token_env) or None

        class Handler(_A2AHandler):
            _store = store  # type: ignore[assignment]
            _base_url = base_url  # type: ignore[assignment]
            _auth_token = auth_token  # type: ignore[assignment]

        return Handler

    def serve_forever(self) -> None:
        """Start serving. Blocks until shutdown() is called."""
        if self.bind == "0.0.0.0":
            print(
                "WARNING: A2A server binding to 0.0.0.0 — "
                "server is reachable from the network. "
                "Set AUTODEV_A2A_TOKEN for authentication.",
                flush=True,
            )

        self._server = ThreadingHTTPServer(
            (self.bind, self.port), self._make_handler_class()
        )

        # SIGTERM → clean shutdown (only allowed in main thread)
        try:
            def _sigterm(_signum: int, _frame: Any) -> None:
                threading.Thread(target=self._server.shutdown, daemon=True).start()  # type: ignore[union-attr]

            signal.signal(signal.SIGTERM, _sigterm)
        except ValueError:
            # signal.signal() is only valid in the main thread; skip when running
            # inside a background thread (e.g., during tests).
            pass

        print(f"A2A server on http://{self.bind}:{self.port}", flush=True)
        self._server.serve_forever()

    def shutdown(self) -> None:
        """Shutdown the server (thread-safe)."""
        if self._server is not None:
            self._server.shutdown()
