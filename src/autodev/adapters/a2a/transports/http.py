"""A2AHttpTransport — HTTP transport for talking to external A2A servers.

Uses stdlib urllib.request only (no httpx / requests). Never raises — all
errors are expressed as A2ATask with status=FAILED and an error artifact.
"""
from __future__ import annotations

import ipaddress
import json
import os
import socket
import time
import urllib.error
import urllib.parse
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


# ---------------------------------------------------------------------------
# SSRF protection
# ---------------------------------------------------------------------------


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Suppress automatic redirect following so we can re-validate each hop."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[override]
        # Return None to signal "do not follow" — urllib will then raise
        # HTTPError with the 3xx status code, which our loop catches.
        return None


class A2AHttpSSRFError(ValueError):
    """Raised when a URL is rejected by the SSRF allow-list validator."""


_ALLOWED_SCHEMES = frozenset({"http", "https"})

# Network ranges that are rejected when allow_private=False.
_PRIVATE_NETWORKS = [
    ipaddress.ip_network("127.0.0.0/8"),       # loopback IPv4
    ipaddress.ip_network("::1/128"),            # loopback IPv6
    ipaddress.ip_network("169.254.0.0/16"),     # link-local IPv4 (incl. AWS metadata)
    ipaddress.ip_network("fe80::/10"),          # link-local IPv6
    ipaddress.ip_network("10.0.0.0/8"),         # private class A
    ipaddress.ip_network("172.16.0.0/12"),      # private class B
    ipaddress.ip_network("192.168.0.0/16"),     # private class C
    ipaddress.ip_network("fc00::/7"),           # unique local IPv6
    ipaddress.ip_network("0.0.0.0/8"),          # unspecified IPv4
    ipaddress.ip_network("::/128"),             # unspecified IPv6
]


def _is_private_address(addr: str) -> bool:
    """Return True if *addr* (numeric IP string) falls in a restricted range."""
    try:
        ip = ipaddress.ip_address(addr)
    except ValueError:
        # Not a valid IP; treat as private (fail closed).
        return True
    return any(ip in net for net in _PRIVATE_NETWORKS)


def _validate_url(url: str, allow_private: bool = False) -> None:
    """Validate *url* against SSRF allow-list rules.

    Raises :class:`A2AHttpSSRFError` when the URL should be rejected.

    Parameters
    ----------
    url:
        The URL to validate (absolute).
    allow_private:
        When ``True``, skip the private-network checks (for local testing).
    """
    try:
        parsed = urllib.parse.urlparse(url)
    except Exception as exc:
        raise A2AHttpSSRFError(f"Malformed URL: {url!r}") from exc

    # Scheme check — only http/https allowed.
    scheme = (parsed.scheme or "").lower()
    if scheme not in _ALLOWED_SCHEMES:
        raise A2AHttpSSRFError(
            f"Scheme {scheme!r} is not allowed; only 'http'/'https' are permitted. "
            f"URL: {url!r}"
        )

    if allow_private:
        return  # Skip address-range checks in private-network mode.

    hostname = parsed.hostname
    if not hostname:
        raise A2AHttpSSRFError(f"No hostname in URL: {url!r}")

    # Fast-path: if the hostname is already a numeric IP literal, check it
    # directly without a DNS round-trip.
    # NOTE: catch A2AHttpSSRFError *before* ValueError because A2AHttpSSRFError
    # is a subclass of ValueError — a bare `except ValueError` would swallow it.
    try:
        literal_ip = ipaddress.ip_address(hostname)
    except ValueError:
        literal_ip = None  # Not a numeric literal; fall through to DNS resolution.
    if literal_ip is not None:
        if _is_private_address(str(literal_ip)):
            raise A2AHttpSSRFError(
                f"URL {url!r} targets a private/restricted IP address "
                f"({literal_ip}); request blocked to prevent SSRF."
            )
        # It's a public literal IP — allow it.
        return

    # Resolve hostname → all addresses, check each.
    try:
        addr_infos = socket.getaddrinfo(hostname, None)
    except OSError as exc:
        raise A2AHttpSSRFError(
            f"DNS resolution failed for {hostname!r}: {exc}"
        ) from exc

    if not addr_infos:
        raise A2AHttpSSRFError(f"No addresses resolved for {hostname!r}")

    for _family, _type, _proto, _canonname, sockaddr in addr_infos:
        # sockaddr is (address, port) for IPv4 or (address, port, flow, scope) for IPv6
        addr_str = sockaddr[0]
        if _is_private_address(addr_str):
            raise A2AHttpSSRFError(
                f"URL {url!r} resolves to a private/restricted address "
                f"({addr_str}); request blocked to prevent SSRF."
            )


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
        Base URL of the remote agent, e.g. ``http://remote-agent.example.com``.
    auth_token:
        Optional bearer token sent as ``Authorization: Bearer <token>``.
    timeout_sec:
        HTTP socket timeout in seconds (per request).
    poll_interval:
        Seconds to wait between status-poll requests.
    max_poll_attempts:
        Maximum number of poll requests before giving up with FAILED.
    allow_private_networks:
        When ``False`` (default), SSRF protection is active: requests to
        loopback, link-local, private, unspecified, or cloud-metadata
        addresses are rejected before they are sent.  Set to ``True``
        **only** in integration-test environments where the remote agent
        legitimately lives on localhost or an RFC-1918 address.
    """

    def __init__(
        self,
        endpoint: str,
        *,
        auth_token: str | None = None,
        timeout_sec: int = 120,
        poll_interval: float = 1.0,
        max_poll_attempts: int = 60,
        allow_private_networks: bool = False,
    ) -> None:
        self._endpoint = endpoint.rstrip("/")
        self._auth_token = auth_token
        self._timeout_sec = timeout_sec
        self._poll_interval = poll_interval
        self._max_poll_attempts = max_poll_attempts
        # Honour the env-var override (useful for integration-test suites that
        # point at a localhost fake server but cannot modify the constructor call).
        env_override = os.environ.get("AUTODEV_A2A_ALLOW_PRIVATE_NETWORKS", "").strip()
        self._allow_private_networks = allow_private_networks or env_override in ("1", "true", "yes")

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
        """Issue an HTTP request with SSRF validation on every hop.

        Redirects are followed manually (up to 5 hops) so the Location
        header of every hop is re-validated before connecting.

        Never raises — returns (0, b'') on any exception.
        """
        try:
            t = timeout if timeout is not None else self._timeout_sec
            current_url = url
            current_method = method
            current_data: bytes | None = json.dumps(body).encode() if body is not None else None

            for _hop in range(6):  # 0..5 — at most 5 redirects
                # SSRF guard — validate before opening any connection.
                _validate_url(current_url, allow_private=self._allow_private_networks)

                headers: dict[str, str] = {}
                if current_data is not None:
                    headers["Content-Type"] = "application/json"
                if self._auth_token:
                    headers["Authorization"] = f"Bearer {self._auth_token}"

                no_redirect_opener = urllib.request.build_opener(_NoRedirectHandler())
                req = urllib.request.Request(
                    current_url,
                    data=current_data,
                    headers=headers,
                    method=current_method,
                )

                try:
                    with no_redirect_opener.open(req, timeout=t) as resp:
                        status = resp.status
                        location = resp.headers.get("Location")
                        response_body = resp.read()
                except urllib.error.HTTPError as exc:
                    status = exc.code
                    location = exc.headers.get("Location") if exc.headers else None
                    try:
                        response_body = exc.read()
                    except Exception:
                        response_body = b""

                if status not in (301, 302, 303, 307, 308):
                    return status, response_body

                # It's a redirect — resolve relative Location and re-validate.
                if not location:
                    return status, response_body

                current_url = urllib.parse.urljoin(current_url, location)

                # RFC 7231: 303 (and pragmatically 301/302 on POST) → GET + no body.
                if status in (301, 302, 303):
                    current_method = "GET"
                    current_data = None

            # Exhausted redirect budget.
            return 0, b""

        except A2AHttpSSRFError:
            return 0, b""
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
