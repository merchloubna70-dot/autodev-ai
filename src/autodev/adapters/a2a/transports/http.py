"""A2AHttpTransport — HTTP transport for talking to external A2A servers.

Uses stdlib urllib.request only (no httpx / requests). Never raises — all
errors are expressed as A2ATask with status=FAILED and an error artifact.
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any

from ....schemas import (
    A2APart,
    A2ATask,
    A2ATaskStatus,
    AgentCard,
)
from .base import BaseA2ATransport


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _fail_task(task: A2ATask, reason: str) -> A2ATask:
    """Mark task as FAILED with a text error artifact. Never raises."""
    task.artifacts.append(A2APart(kind="text", text=reason))
    task.status = A2ATaskStatus.FAILED
    task.updated_at = _now_iso()
    return task


def _parse_task_from_dict(data: dict[str, Any], original: A2ATask) -> A2ATask:
    """Best-effort parse of a task dict returned by the server.

    Falls back to returning *original* with FAILED status on parse errors.
    """
    try:
        return A2ATask.model_validate(data)
    except Exception as exc:  # pragma: no cover
        return _fail_task(original, f"[A2A-HTTP] response parse error: {exc}")


class A2AHttpTransport(BaseA2ATransport):
    """HTTP + JSON-RPC A2A transport that talks to any external A2A server.

    Parameters
    ----------
    endpoint:
        Base URL of the remote agent, e.g. ``http://localhost:8421``.
    auth_token:
        Optional bearer token sent as ``Authorization: Bearer <token>``.
    timeout_sec:
        HTTP socket timeout in seconds (per request).
    poll_interval:
        Seconds to wait between status-poll requests.
    max_poll_attempts:
        Maximum number of poll requests before giving up with FAILED.
    """

    def __init__(
        self,
        endpoint: str,
        *,
        auth_token: str | None = None,
        timeout_sec: int = 120,
        poll_interval: float = 1.0,
        max_poll_attempts: int = 60,
    ) -> None:
        self._endpoint = endpoint.rstrip("/")
        self._auth_token = auth_token
        self._timeout_sec = timeout_sec
        self._poll_interval = poll_interval
        self._max_poll_attempts = max_poll_attempts

    # ------------------------------------------------------------------
    # Internal HTTP helpers
    # ------------------------------------------------------------------

    def _make_request(
        self,
        url: str,
        method: str = "GET",
        body: dict | None = None,
        timeout: int | None = None,
    ) -> tuple[int, bytes]:
        """Issue an HTTP request. Returns (status_code, response_bytes).

        Never raises — returns (0, b'') on any exception.
        """
        try:
            data = json.dumps(body).encode() if body is not None else None
            headers: dict[str, str] = {}
            if data is not None:
                headers["Content-Type"] = "application/json"
            if self._auth_token:
                headers["Authorization"] = f"Bearer {self._auth_token}"
            req = urllib.request.Request(url, data=data, headers=headers, method=method)
            t = timeout if timeout is not None else self._timeout_sec
            with urllib.request.urlopen(req, timeout=t) as resp:  # noqa: S310
                return resp.status, resp.read()
        except urllib.error.HTTPError as exc:
            try:
                return exc.code, exc.read()
            except Exception:
                return exc.code, b""
        except Exception:
            return 0, b""

    def _post_json(self, url: str, body: dict) -> tuple[int, dict | None]:
        """POST JSON body, parse JSON response. Returns (status_code, dict_or_None)."""
        status, raw = self._make_request(url, method="POST", body=body)
        if not raw:
            return status, None
        try:
            return status, json.loads(raw)
        except Exception:
            return status, None

    def _get_json(self, url: str, timeout: int | None = None) -> tuple[int, dict | None]:
        """GET, parse JSON response. Returns (status_code, dict_or_None)."""
        status, raw = self._make_request(url, method="GET", timeout=timeout)
        if not raw:
            return status, None
        try:
            return status, json.loads(raw)
        except Exception:
            return status, None

    # ------------------------------------------------------------------
    # BaseA2ATransport interface
    # ------------------------------------------------------------------

    def send_task(self, card: AgentCard, task: A2ATask) -> A2ATask:
        """POST task to ``{endpoint}/tasks/send``, then poll until terminal.

        Never raises — all errors → A2ATask with status=FAILED.
        """
        try:
            url = f"{self._endpoint}/tasks/send"
            payload = task.model_dump(mode="json")
            status_code, resp = self._post_json(url, payload)

            if status_code == 0:
                return _fail_task(
                    task,
                    f"[A2A-HTTP:{card.name}] connection error sending to {url}",
                )
            if status_code >= 400:
                return _fail_task(
                    task,
                    f"[A2A-HTTP:{card.name}] HTTP {status_code} from {url}",
                )
            if resp is None:
                return _fail_task(
                    task,
                    f"[A2A-HTTP:{card.name}] empty or unparseable response from {url}",
                )

            # Server may return the task directly or wrap in {"result": ...}
            task_data: dict = resp.get("result", resp) if isinstance(resp, dict) else resp
            if not isinstance(task_data, dict):
                return _fail_task(task, f"[A2A-HTTP:{card.name}] unexpected response shape from {url}")

            result_task = _parse_task_from_dict(task_data, task)

            # If already in terminal state, return immediately
            if result_task.status in (
                A2ATaskStatus.COMPLETED,
                A2ATaskStatus.FAILED,
                A2ATaskStatus.CANCELED,
            ):
                return result_task

            # Poll until terminal state
            return self._poll_until_done(card, result_task)

        except Exception as exc:  # pragma: no cover — defensive
            return _fail_task(task, f"[A2A-HTTP:{card.name}] unexpected exception: {exc}")

    def _poll_until_done(self, card: AgentCard, task: A2ATask) -> A2ATask:
        """Poll ``{endpoint}/tasks/{id}`` until terminal status or max attempts."""
        poll_url = f"{self._endpoint}/tasks/{task.id}"
        for _attempt in range(self._max_poll_attempts):
            time.sleep(self._poll_interval)
            status_code, resp = self._get_json(poll_url)
            if status_code == 0 or resp is None:
                continue  # transient failure; keep retrying
            task_data: dict = resp.get("result", resp) if isinstance(resp, dict) else resp
            if not isinstance(task_data, dict):
                continue
            try:
                polled = A2ATask.model_validate(task_data)
            except Exception:
                continue
            if polled.status in (
                A2ATaskStatus.COMPLETED,
                A2ATaskStatus.FAILED,
                A2ATaskStatus.CANCELED,
            ):
                return polled
            task = polled  # update with latest working state

        # Exhausted poll budget
        return _fail_task(
            task,
            f"[A2A-HTTP:{card.name}] polling timed out after {self._max_poll_attempts} attempts",
        )

    def discover_agent_card(self) -> AgentCard | None:
        """GET ``{endpoint}/.well-known/agent.json`` and parse into AgentCard.

        Returns ``None`` on any error (connection failure, bad JSON, schema mismatch).
        """
        url = f"{self._endpoint}/.well-known/agent.json"
        status_code, resp = self._get_json(url)
        if status_code == 0 or status_code >= 400 or resp is None:
            return None
        try:
            return AgentCard.model_validate(resp)
        except Exception:
            return None

    def is_reachable(self) -> bool:
        """Quick HEAD on endpoint root with 1-second timeout.

        Used by A2AClient fallback logic. Returns False on any error.
        """
        status_code, _ = self._make_request(self._endpoint, method="HEAD", timeout=1)
        return status_code not in (0,) and status_code < 500
