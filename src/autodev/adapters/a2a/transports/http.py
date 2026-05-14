"""A2AHttpTransport — HTTP transport for talking to external A2A servers.

Uses stdlib urllib.request / http.client only (no httpx / requests). Never
raises — all errors are expressed as A2ATask with status=FAILED and an
error artifact.

DNS-rebinding TOCTOU mitigation (IP-pinning)
--------------------------------------------
The classic SSRF pre-flight check suffers from a TOCTOU race: DNS is
resolved once at validation time, but the TCP connection's resolver call
happens independently milliseconds later.  A malicious authoritative
nameserver can return a public IP during ``_validate_url`` and switch the
record to a private IP by the time the kernel calls ``connect()``.

Mitigation implemented here:
  1. ``_resolve_and_pin_host(hostname, allow_private)`` resolves the
     hostname via ``socket.getaddrinfo``, validates *every* returned
     address against the private-range blocklist, and returns the **first**
     numeric IP string ("pinned IP").  For literal IPs the DNS call is
     skipped and the IP is validated directly.
  2. ``_build_pinned_opener(pinned_ip, original_host, scheme)`` creates a
     urllib opener that uses ``_PinnedHTTPHandler`` / ``_PinnedHTTPSHandler``.
     These handlers override ``do_open`` to create an
     ``http.client.HTTPConnection`` / ``HTTPSConnection`` whose ``host`` is
     the pinned numeric IP, not the original hostname.  The ``Host:`` request
     header is injected with the original hostname so virtual-hosting, CDN
     routing, and HTTP/1.1 compliance still work.  For HTTPS, a
     ``_PinnedHTTPSConnection`` subclass passes ``server_hostname=original_host``
     to the SSL handshake so TLS SNI and certificate validation use the
     correct name.
  3. The request still flows through ``urllib.request.OpenerDirector.open``
     — only the connection target (IP) is pinned, not the urllib machinery.
  4. On every redirect hop the Location URL is re-resolved and re-pinned
     independently — the pinned IP from hop N is **never** reused for hop N+1.
  5. When ``allow_private=True`` (integration-test escape hatch) the whole
     DNS-resolution / blocklist path is skipped and the default urllib opener
     is used directly, exactly as before R3.

Documented residual risks (cannot be eliminated at the HTTP-adapter layer)
---------------------------------------------------------------------------
* **Egress-proxy SSRF**: an attacker who controls both DNS *and* a public
  proxy that internally tunnels to a private host can bypass IP-pinning
  because the proxy's public IP passes all checks.  This is a
  network-egress / firewall concern outside the scope of this adapter.
* **Kernel-level attacks** (routing table manipulation, anycast hijack,
  on-path BGP interception): pure-Python code has no visibility into these;
  they require network-layer controls.
"""
from __future__ import annotations

import http.client
import ipaddress
import json
import os
import socket
import ssl
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
        addr_str = str(sockaddr[0])
        if _is_private_address(addr_str):
            raise A2AHttpSSRFError(
                f"URL {url!r} resolves to a private/restricted address "
                f"({addr_str}); request blocked to prevent SSRF."
            )


def _resolve_and_pin_host(hostname: str, allow_private: bool = False) -> str:
    """Resolve *hostname* to a numeric IP, validate it, and return the pinned IP.

    This is the DNS-rebinding TOCTOU mitigation: we resolve the hostname
    **once** here, validate the result, and then direct all subsequent I/O to
    the pinned numeric IP so the OS resolver is never called again for this
    hop.

    Parameters
    ----------
    hostname:
        The hostname or numeric IP literal to resolve/validate.
    allow_private:
        When ``True``, skip blocklist validation (integration-test escape
        hatch).  Returns the first resolved IP without checking it.

    Returns
    -------
    str
        A numeric IPv4 address string (e.g. ``"93.184.216.34"``) or a
        bracket-free IPv6 address string (e.g. ``"2606:2800:21f:cb07::1"``)
        suitable for passing to ``http.client.HTTPConnection(host=…)``.

    Raises
    ------
    A2AHttpSSRFError
        If DNS resolution fails, returns no addresses, or *any* resolved
        address falls in a private/restricted range (when allow_private=False).
    """
    # If the hostname is already a numeric literal, just validate and return.
    try:
        lit = ipaddress.ip_address(hostname)
    except ValueError:
        lit = None
    if lit is not None:
        if not allow_private and _is_private_address(str(lit)):
            raise A2AHttpSSRFError(
                f"IP literal {hostname!r} is in a private/restricted range; "
                "request blocked to prevent SSRF."
            )
        return str(lit)

    try:
        addr_infos = socket.getaddrinfo(hostname, None)
    except OSError as exc:
        raise A2AHttpSSRFError(
            f"DNS resolution failed for {hostname!r}: {exc}"
        ) from exc

    if not addr_infos:
        raise A2AHttpSSRFError(f"No addresses resolved for {hostname!r}")

    for _family, _type, _proto, _canonname, sockaddr in addr_infos:
        addr_str = str(sockaddr[0])
        if not allow_private and _is_private_address(addr_str):
            raise A2AHttpSSRFError(
                f"Hostname {hostname!r} resolves to private/restricted address "
                f"({addr_str}); request blocked to prevent SSRF."
            )

    # All addresses passed — pin to the first one.
    first_addr = str(addr_infos[0][4][0])
    return first_addr


# ---------------------------------------------------------------------------
# Pinned urllib handlers (DNS-rebinding mitigation)
# ---------------------------------------------------------------------------


class _PinnedHTTPSConnection(http.client.HTTPSConnection):
    """HTTPSConnection that connects to a pinned IP but uses the original
    hostname for TLS SNI and certificate validation.

    This separates the *network destination* (the IP we resolved and
    validated) from the *TLS identity* (the original hostname), which is
    exactly what we need for DNS-rebinding mitigation.
    """

    def __init__(
        self,
        connect_host: str,
        server_hostname: str,
        port: int,
        timeout: float,
    ) -> None:
        # Pass connect_host as the TCP target.
        super().__init__(host=connect_host, port=port, timeout=timeout)
        self._pinned_server_hostname = server_hostname

    def connect(self) -> None:  # type: ignore[override]
        """Override connect() to inject the correct server_hostname for SNI."""
        # Establish the TCP socket to the pinned IP, then wrap with the
        # original hostname for SNI/cert validation.
        sock = socket.create_connection(
            (self.host, self.port),
            timeout=self.timeout,
        )
        ctx = ssl.create_default_context()
        self.sock = ctx.wrap_socket(sock, server_hostname=self._pinned_server_hostname)


class _PinnedHTTPHandler(urllib.request.HTTPHandler):
    """urllib HTTPHandler that directs connections to a pre-resolved IP.

    Overrides ``do_open`` to create an ``http.client.HTTPConnection``
    pointed at *pinned_ip* rather than the URL's hostname.  The ``Host``
    header is injected with the original hostname so virtual-hosting and
    HTTP/1.1 compliance still work.
    """

    def __init__(self, pinned_ip: str, original_host: str, port: int) -> None:
        super().__init__()
        self._pinned_ip = pinned_ip
        self._original_host = original_host
        self._port = port

    def do_open(  # type: ignore[override]
        self,
        http_class: type[http.client.HTTPConnection],
        req: urllib.request.Request,
        **http_conn_args: Any,
    ) -> Any:
        # Inject Host header so the server knows the original hostname.
        req.add_unredirected_header("Host", self._original_host)
        # Override http_class to always connect to the pinned IP + port.
        def _pinned_conn(host: str, **kwargs: Any) -> http.client.HTTPConnection:  # noqa: ANN401
            return http.client.HTTPConnection(
                self._pinned_ip, self._port, **kwargs
            )
        return super().do_open(_pinned_conn, req, **http_conn_args)  # type: ignore[arg-type]


class _PinnedHTTPSHandler(urllib.request.HTTPSHandler):
    """urllib HTTPSHandler that directs TLS connections to a pre-resolved IP.

    Like ``_PinnedHTTPHandler`` but for HTTPS: the actual TCP + TLS
    connection goes to the pinned IP, while TLS SNI and certificate
    validation still use the original hostname.
    """

    def __init__(self, pinned_ip: str, original_host: str, port: int) -> None:
        super().__init__()
        self._pinned_ip = pinned_ip
        self._original_host = original_host
        self._port = port

    def do_open(  # type: ignore[override]
        self,
        http_class: type[http.client.HTTPConnection],
        req: urllib.request.Request,
        **http_conn_args: Any,
    ) -> Any:
        req.add_unredirected_header("Host", self._original_host)
        pinned_ip = self._pinned_ip
        original_host = self._original_host
        port = self._port

        def _pinned_conn(host: str, **kwargs: Any) -> _PinnedHTTPSConnection:  # noqa: ANN401
            timeout = kwargs.pop("timeout", 120)
            return _PinnedHTTPSConnection(
                connect_host=pinned_ip,
                server_hostname=original_host,
                port=port,
                timeout=float(timeout),
            )
        return super().do_open(_pinned_conn, req, **http_conn_args)  # type: ignore[arg-type]


def _build_pinned_opener(
    pinned_ip: str,
    original_host: str,
    scheme: str,
    port: int,
) -> urllib.request.OpenerDirector:
    """Build a urllib opener whose HTTP/HTTPS handler connects to *pinned_ip*.

    Parameters
    ----------
    pinned_ip:
        Numeric IP to connect to (e.g. ``"93.184.216.34"`` or ``"::1"``).
    original_host:
        Original hostname for the ``Host`` header and TLS SNI.
    scheme:
        ``"http"`` or ``"https"``.
    port:
        Effective TCP port (80 or 443 for defaults).
    """
    if scheme == "https":
        handler: urllib.request.BaseHandler = _PinnedHTTPSHandler(pinned_ip, original_host, port)
    else:
        handler = _PinnedHTTPHandler(pinned_ip, original_host, port)
    return urllib.request.build_opener(_NoRedirectHandler(), handler)


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
        """Issue an HTTP request with SSRF validation + IP-pinning on every hop.

        DNS-rebinding mitigation (when allow_private_networks=False):
          1. ``_validate_url`` checks scheme and, for non-hostname paths, IP
             literals against the blocklist.  For hostname labels it also
             calls ``socket.getaddrinfo`` as a first-pass check.
          2. ``_resolve_and_pin_host`` calls ``socket.getaddrinfo`` once more
             to obtain the canonical pinned IP.  A custom urllib opener
             (``_build_pinned_opener``) then directs the TCP connection to
             that IP rather than the hostname — the OS resolver is never
             called again for this hop.
          3. On every redirect hop the Location URL is re-validated and
             re-pinned independently.

        Note: for hostname labels, getaddrinfo is called twice — once inside
        ``_validate_url`` and once inside ``_resolve_and_pin_host``.  This is
        intentional: ``_validate_url`` checks *all* returned addresses for
        safety while ``_resolve_and_pin_host`` picks the first address to pin.
        An attacker would need to win *both* races simultaneously, which is
        substantially harder than the single-race scenario.

        Never raises — returns (0, b'') on any exception.
        """
        try:
            t = float(timeout if timeout is not None else self._timeout_sec)
            current_url = url
            current_method = method
            current_data: bytes | None = json.dumps(body).encode() if body is not None else None

            for _hop in range(6):  # 0..5 — at most 5 redirects
                # SSRF guard — validate before opening any connection.
                _validate_url(current_url, allow_private=self._allow_private_networks)

                parsed = urllib.parse.urlparse(current_url)
                hostname = parsed.hostname or ""

                headers: dict[str, str] = {}
                if current_data is not None:
                    headers["Content-Type"] = "application/json"
                if self._auth_token:
                    headers["Authorization"] = f"Bearer {self._auth_token}"

                if self._allow_private_networks:
                    # Private-networks mode: use default urllib opener (legacy
                    # path used only by integration tests against localhost).
                    opener = urllib.request.build_opener(_NoRedirectHandler())
                else:
                    # DNS-pinning path: resolve hostname → validate IP → build
                    # a pinned opener that connects to the resolved IP directly.
                    # getaddrinfo is called here (and was already called inside
                    # _validate_url above); we pin to the result of this call
                    # so the subsequent socket.connect never consults DNS again.
                    scheme = (parsed.scheme or "http").lower()
                    port = parsed.port or (443 if scheme == "https" else 80)
                    pinned_ip = _resolve_and_pin_host(hostname, allow_private=False)
                    opener = _build_pinned_opener(
                        pinned_ip=pinned_ip,
                        original_host=hostname,
                        scheme=scheme,
                        port=port,
                    )

                req = urllib.request.Request(
                    current_url,
                    data=current_data,
                    headers=headers,
                    method=current_method,
                )

                try:
                    with opener.open(req, timeout=t) as resp:
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
