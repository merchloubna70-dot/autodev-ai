"""R9 coverage backfill for src/autodev/adapters/a2a/transports/http.py.

Targets the security tier threshold (≥90%).  All tests are deterministic —
no real network connections are made.  socket.getaddrinfo and
urllib.request.OpenerDirector.open are monkeypatched where needed.

Missing lines before this file (77%):
  83, 111-113, 131-132, 147, 164, 169-170, 175, 222-227, 231-232, 237,
  281-286, 311-317, 329-332, 340-353, 376, 538-539, 546, 560-561, 570-571,
  577, 598, 608, 616, 641, 644, 647-648, 658, 674-675, 682-683
"""
from __future__ import annotations

import socket
import urllib.error
import urllib.request
from datetime import datetime, timezone
from http.client import HTTPMessage
from io import BytesIO
from unittest.mock import MagicMock, patch
import uuid

import pytest

from autodev.adapters.a2a.transports.http import (
    A2AHttpSSRFError,
    A2AHttpTransport,
    _NoRedirectHandler,
    _PinnedHTTPHandler,
    _PinnedHTTPSConnection,
    _PinnedHTTPSHandler,
    _build_pinned_opener,
    _is_private_address,
    _resolve_and_pin_host,
    _validate_url,
)
from autodev.schemas import (
    A2AMessage,
    A2APart,
    A2ATask,
    A2ATaskStatus,
    AgentCard,
)

# ---------------------------------------------------------------------------
# Fixtures / small helpers
# ---------------------------------------------------------------------------


def _make_task(text: str = "r9 test") -> A2ATask:
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


def _make_card(endpoint: str = "http://example.com") -> AgentCard:
    return AgentCard(name="r9-agent", transport="a2a-http", endpoint=endpoint)


def _task_dict(task: A2ATask, status: str = "completed") -> dict:
    return {
        "id": task.id,
        "context_id": task.context_id,
        "status": status,
        "history": [],
        "artifacts": [],
        "metadata": {},
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": None,
    }


def _gai_public(host, port, *args, **kwargs):
    """Always returns a single public-IP result."""
    return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 0))]


def _fake_resp_200(body: bytes = b'{"ok": true}') -> MagicMock:
    resp = MagicMock()
    resp.__enter__ = lambda s: s
    resp.__exit__ = MagicMock(return_value=False)
    resp.status = 200
    resp.headers.get.return_value = None
    resp.read.return_value = body
    return resp


def _fake_opener_200(body: bytes = b'{"ok": true}') -> MagicMock:
    opener = MagicMock()
    opener.open.return_value = _fake_resp_200(body)
    return opener


# ===========================================================================
# Group 1 — _is_private_address: invalid IP string (lines 111-113)
# ===========================================================================


def test_is_private_address_invalid_string_returns_true() -> None:
    """_is_private_address treats any non-IP string as private (fail-closed)."""
    # "not-an-ip" is not a valid IP address → ValueError → return True
    assert _is_private_address("not-an-ip") is True


def test_is_private_address_empty_string_returns_true() -> None:
    """Empty string is not a valid IP → private."""
    assert _is_private_address("") is True


def test_is_private_address_public_ip_returns_false() -> None:
    """93.184.216.34 (example.com) is public → False."""
    assert _is_private_address("93.184.216.34") is False


# ===========================================================================
# Group 2 — _validate_url: no-hostname branch (line 147)
# ===========================================================================


def test_validate_url_no_hostname_raises() -> None:
    """A URL with no hostname (e.g. http:///path) must be rejected."""
    with pytest.raises(A2AHttpSSRFError, match="No hostname"):
        _validate_url("http:///no-host")


# ===========================================================================
# Group 3 — _validate_url: public literal IP is allowed (line 164 — the
#            'return' after confirming a non-private literal IP)
# ===========================================================================


def test_validate_url_public_literal_ip_allowed() -> None:
    """A URL with a public literal IP (93.184.216.34) must pass without DNS."""
    # Should not raise
    _validate_url("http://93.184.216.34/path")


def test_validate_url_public_literal_ip_https_allowed() -> None:
    """HTTPS with a public literal IP is also allowed."""
    _validate_url("https://8.8.8.8/dns-query")


# ===========================================================================
# Group 4 — _validate_url: DNS resolution failure (lines 169-170)
# ===========================================================================


def test_validate_url_dns_failure_raises(monkeypatch) -> None:
    """OSError from getaddrinfo → A2AHttpSSRFError with 'DNS resolution failed'."""
    def _gai_fail(host, port, *args, **kwargs):
        raise OSError("Name or service not known")

    monkeypatch.setattr(socket, "getaddrinfo", _gai_fail)
    with pytest.raises(A2AHttpSSRFError, match="DNS resolution failed"):
        _validate_url("http://nonexistent.example.invalid/")


# ===========================================================================
# Group 5 — _validate_url: empty addr_infos (line 175)
# ===========================================================================


def test_validate_url_empty_addr_infos_raises(monkeypatch) -> None:
    """getaddrinfo returning [] → A2AHttpSSRFError 'No addresses resolved'."""
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **kw: [])
    with pytest.raises(A2AHttpSSRFError, match="No addresses resolved"):
        _validate_url("http://ghost.example.com/")


# ===========================================================================
# Group 6 — _resolve_and_pin_host: literal private IP blocked (lines 222-227)
# ===========================================================================


def test_resolve_and_pin_host_private_literal_raises() -> None:
    """_resolve_and_pin_host with a private literal IP raises A2AHttpSSRFError."""
    with pytest.raises(A2AHttpSSRFError, match="private/restricted"):
        _resolve_and_pin_host("127.0.0.1", allow_private=False)


def test_resolve_and_pin_host_private_literal_10_raises() -> None:
    """_resolve_and_pin_host rejects 10.0.0.1 (RFC-1918 class A)."""
    with pytest.raises(A2AHttpSSRFError, match="private/restricted"):
        _resolve_and_pin_host("10.0.0.1", allow_private=False)


def test_resolve_and_pin_host_private_literal_allow_returns_ip() -> None:
    """With allow_private=True, a private literal IP is accepted and returned."""
    result = _resolve_and_pin_host("127.0.0.1", allow_private=True)
    assert result == "127.0.0.1"


def test_resolve_and_pin_host_public_literal_returned() -> None:
    """A public literal IP is validated and returned as-is."""
    result = _resolve_and_pin_host("93.184.216.34", allow_private=False)
    assert result == "93.184.216.34"


# ===========================================================================
# Group 7 — _resolve_and_pin_host: DNS failure (lines 231-232)
# ===========================================================================


def test_resolve_and_pin_host_dns_failure(monkeypatch) -> None:
    """DNS failure in _resolve_and_pin_host raises A2AHttpSSRFError."""
    def _gai_fail(host, port, *args, **kwargs):
        raise OSError("Resolver error")

    monkeypatch.setattr(socket, "getaddrinfo", _gai_fail)
    with pytest.raises(A2AHttpSSRFError, match="DNS resolution failed"):
        _resolve_and_pin_host("bad.hostname.invalid", allow_private=False)


# ===========================================================================
# Group 8 — _resolve_and_pin_host: empty addr_infos (line 237)
# ===========================================================================


def test_resolve_and_pin_host_empty_addr_infos(monkeypatch) -> None:
    """Empty getaddrinfo result → A2AHttpSSRFError 'No addresses resolved'."""
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **kw: [])
    with pytest.raises(A2AHttpSSRFError, match="No addresses resolved"):
        _resolve_and_pin_host("empty.example.com", allow_private=False)


# ===========================================================================
# Group 9 — _NoRedirectHandler.redirect_request returns None (line 83)
# ===========================================================================


def test_no_redirect_handler_returns_none() -> None:
    """redirect_request must return None so urllib raises HTTPError for 3xx."""
    handler = _NoRedirectHandler()
    # All args are placeholders — the method just returns None.
    result = handler.redirect_request(
        req=MagicMock(),
        fp=MagicMock(),
        code=302,
        msg="Found",
        headers=MagicMock(),
        newurl="http://other.example.com/",
    )
    assert result is None


# ===========================================================================
# Group 10 — _PinnedHTTPSConnection.connect (lines 281-286)
#            Test construction and that connect() calls socket.create_connection
# ===========================================================================


def test_pinned_https_connection_connect_calls_socket(monkeypatch) -> None:
    """_PinnedHTTPSConnection.connect creates socket then wraps with SSL."""
    fake_sock = MagicMock()
    fake_wrapped = MagicMock()

    create_conn_calls: list = []

    def _fake_create_connection(addr, timeout):
        create_conn_calls.append(addr)
        return fake_sock

    import ssl as ssl_mod
    fake_ctx = MagicMock()
    fake_ctx.wrap_socket.return_value = fake_wrapped

    monkeypatch.setattr(socket, "create_connection", _fake_create_connection)
    monkeypatch.setattr(ssl_mod, "create_default_context", lambda: fake_ctx)

    conn = _PinnedHTTPSConnection(
        connect_host="93.184.216.34",
        server_hostname="example.com",
        port=443,
        timeout=5.0,
    )
    conn.connect()

    # create_connection must target the pinned IP, not the hostname.
    assert create_conn_calls == [("93.184.216.34", 443)]
    # SSL wrapping must use the original hostname for SNI.
    fake_ctx.wrap_socket.assert_called_once_with(
        fake_sock, server_hostname="example.com"
    )
    assert conn.sock is fake_wrapped


# ===========================================================================
# Group 11 — _PinnedHTTPHandler.do_open / inner _pinned_conn (lines 311-317)
# ===========================================================================


def test_pinned_http_handler_do_open_injects_host_header(monkeypatch) -> None:
    """_PinnedHTTPHandler.do_open sets the Host header and connects to pinned IP."""
    handler = _PinnedHTTPHandler(
        pinned_ip="93.184.216.34",
        original_host="example.com",
        port=80,
    )

    created_connections: list = []

    # Intercept the super().do_open call to capture what http_class is used.
    def _fake_do_open(self_inner, http_class, req, **kwargs):
        # Instantiate the passed http_class to verify it connects to the pinned IP.
        conn = http_class("ignored-host")
        created_connections.append(conn)
        # Return a minimal fake response object.
        resp = MagicMock()
        resp.status = 200
        resp.read.return_value = b""
        resp.msg = "OK"
        resp.headers = HTTPMessage()
        resp.getheader = lambda name, default=None: default
        resp.fp = BytesIO(b"")
        return resp

    import urllib.request as url_req
    monkeypatch.setattr(url_req.HTTPHandler, "do_open", _fake_do_open)

    req = urllib.request.Request("http://example.com/path")
    handler.do_open(None, req)  # type: ignore[arg-type]

    # The Host header must have been injected.
    assert req.get_header("Host") == "example.com"

    # The connection created by the inner factory must target the pinned IP.
    assert len(created_connections) == 1
    conn = created_connections[0]
    assert conn.host == "93.184.216.34"
    assert conn.port == 80


# ===========================================================================
# Group 12 — _PinnedHTTPSHandler.__init__ and do_open (lines 329-332, 340-353)
# ===========================================================================


def test_pinned_https_handler_init() -> None:
    """_PinnedHTTPSHandler stores pinned_ip, original_host, and port."""
    handler = _PinnedHTTPSHandler(
        pinned_ip="93.184.216.34",
        original_host="example.com",
        port=443,
    )
    assert handler._pinned_ip == "93.184.216.34"
    assert handler._original_host == "example.com"
    assert handler._port == 443


def test_pinned_https_handler_do_open_creates_pinned_connection(monkeypatch) -> None:
    """_PinnedHTTPSHandler.do_open injects Host header and uses pinned HTTPS conn."""
    handler = _PinnedHTTPSHandler(
        pinned_ip="93.184.216.34",
        original_host="example.com",
        port=443,
    )

    created_connections: list = []

    def _fake_do_open(self_inner, http_class, req, **kwargs):
        # Instantiate the factory to inspect the resulting connection.
        conn = http_class("ignored", timeout=30)
        created_connections.append(conn)
        resp = MagicMock()
        resp.status = 200
        resp.read.return_value = b""
        resp.msg = "OK"
        resp.headers = HTTPMessage()
        resp.getheader = lambda name, default=None: default
        resp.fp = BytesIO(b"")
        return resp

    import urllib.request as url_req
    monkeypatch.setattr(url_req.HTTPSHandler, "do_open", _fake_do_open)

    req = urllib.request.Request("https://example.com/api")
    handler.do_open(None, req)  # type: ignore[arg-type]

    # Host header must be injected.
    assert req.get_header("Host") == "example.com"

    # The connection created by the inner factory must be a _PinnedHTTPSConnection.
    assert len(created_connections) == 1
    conn = created_connections[0]
    assert isinstance(conn, _PinnedHTTPSConnection)
    assert conn.host == "93.184.216.34"
    assert conn._pinned_server_hostname == "example.com"
    assert conn.port == 443


# ===========================================================================
# Group 13 — _build_pinned_opener: HTTP branch (line 376, else)
# ===========================================================================


def test_build_pinned_opener_http_returns_opener() -> None:
    """_build_pinned_opener with scheme='http' builds an opener with HTTPHandler."""
    opener = _build_pinned_opener(
        pinned_ip="93.184.216.34",
        original_host="example.com",
        scheme="http",
        port=80,
    )
    assert opener is not None
    # Verify there is a _PinnedHTTPHandler registered in the opener.
    handler_types = [type(h).__name__ for h in opener.handlers]
    assert "_PinnedHTTPHandler" in handler_types


def test_build_pinned_opener_https_returns_opener() -> None:
    """_build_pinned_opener with scheme='https' builds an opener with HTTPSHandler."""
    opener = _build_pinned_opener(
        pinned_ip="93.184.216.34",
        original_host="example.com",
        scheme="https",
        port=443,
    )
    assert opener is not None
    handler_types = [type(h).__name__ for h in opener.handlers]
    assert "_PinnedHTTPSHandler" in handler_types


# ===========================================================================
# Group 14 — _make_request: exc.read() raises inside HTTPError handler (line 538-539)
# ===========================================================================


def test_make_request_http_error_read_raises(monkeypatch) -> None:
    """If exc.read() itself raises inside the HTTPError handler, body becomes b''."""
    monkeypatch.delenv("AUTODEV_A2A_ALLOW_PRIVATE_NETWORKS", raising=False)
    monkeypatch.setattr(socket, "getaddrinfo", _gai_public)

    bad_fp = MagicMock()
    bad_fp.read.side_effect = OSError("read broken")

    hdrs = HTTPMessage()

    def _patched_open(self, req, *args, **kwargs):
        raise urllib.error.HTTPError(
            url=str(req),
            code=500,
            msg="Internal Server Error",
            hdrs=hdrs,
            fp=bad_fp,
        )

    def _fake_build(*args, **kwargs):
        opener = MagicMock()
        opener.open.side_effect = lambda req, *a, **kw: _patched_open(None, req)
        return opener

    monkeypatch.setattr(
        "autodev.adapters.a2a.transports.http._build_pinned_opener", _fake_build
    )

    transport = A2AHttpTransport("http://example.com")
    status, body = transport._make_request("http://example.com/path")
    # Status is 500 (from exc.code), body fell back to b''.
    assert status == 500
    assert body == b""


# ===========================================================================
# Group 15 — _make_request: redirect with no Location → return immediately (line 546)
# ===========================================================================


def test_make_request_redirect_no_location(monkeypatch) -> None:
    """A 3xx response with no Location header causes early return."""
    monkeypatch.delenv("AUTODEV_A2A_ALLOW_PRIVATE_NETWORKS", raising=False)
    monkeypatch.setattr(socket, "getaddrinfo", _gai_public)

    hdrs = HTTPMessage()
    # No Location header set.

    def _fake_build(*args, **kwargs):
        opener = MagicMock()
        # Return a 302 response with no Location.
        resp = MagicMock()
        resp.__enter__ = lambda s: s
        resp.__exit__ = MagicMock(return_value=False)
        resp.status = 302
        resp.headers.get.return_value = None  # No Location
        resp.read.return_value = b""
        opener.open.return_value = resp
        return opener

    monkeypatch.setattr(
        "autodev.adapters.a2a.transports.http._build_pinned_opener", _fake_build
    )

    transport = A2AHttpTransport("http://example.com")
    status, body = transport._make_request("http://example.com/redirect")
    # Should return the 302 status with empty body.
    assert status == 302
    assert body == b""


# ===========================================================================
# Group 16 — _make_request: generic Exception catch-all (lines 560-561)
# ===========================================================================


def test_make_request_generic_exception_returns_zero(monkeypatch) -> None:
    """Any unexpected exception in _make_request returns (0, b'')."""
    monkeypatch.delenv("AUTODEV_A2A_ALLOW_PRIVATE_NETWORKS", raising=False)
    monkeypatch.setattr(socket, "getaddrinfo", _gai_public)

    def _fake_build(*args, **kwargs):
        opener = MagicMock()
        opener.open.side_effect = RuntimeError("unexpected boom")
        return opener

    monkeypatch.setattr(
        "autodev.adapters.a2a.transports.http._build_pinned_opener", _fake_build
    )

    transport = A2AHttpTransport("http://example.com")
    status, body = transport._make_request("http://example.com/boom")
    assert status == 0
    assert body == b""


# ===========================================================================
# Group 17 — _post_json: JSON parse failure (lines 570-571)
# ===========================================================================


def test_post_json_bad_json_returns_none(monkeypatch) -> None:
    """_post_json returns (status, None) when response body is invalid JSON."""
    monkeypatch.delenv("AUTODEV_A2A_ALLOW_PRIVATE_NETWORKS", raising=False)
    monkeypatch.setattr(socket, "getaddrinfo", _gai_public)

    def _fake_build(*args, **kwargs):
        opener = MagicMock()
        resp = MagicMock()
        resp.__enter__ = lambda s: s
        resp.__exit__ = MagicMock(return_value=False)
        resp.status = 200
        resp.headers.get.return_value = None
        resp.read.return_value = b"not valid json {{{"
        opener.open.return_value = resp
        return opener

    monkeypatch.setattr(
        "autodev.adapters.a2a.transports.http._build_pinned_opener", _fake_build
    )

    transport = A2AHttpTransport("http://example.com")
    status, parsed = transport._post_json("http://example.com/tasks/send", {})
    assert status == 200
    assert parsed is None


# ===========================================================================
# Group 18 — _get_json: empty raw body returns (status, None) (line 577)
# ===========================================================================


def test_get_json_empty_body_returns_none(monkeypatch) -> None:
    """_get_json returns (status, None) when raw body is empty."""
    monkeypatch.delenv("AUTODEV_A2A_ALLOW_PRIVATE_NETWORKS", raising=False)
    monkeypatch.setattr(socket, "getaddrinfo", _gai_public)

    def _fake_build(*args, **kwargs):
        opener = MagicMock()
        resp = MagicMock()
        resp.__enter__ = lambda s: s
        resp.__exit__ = MagicMock(return_value=False)
        resp.status = 200
        resp.headers.get.return_value = None
        resp.read.return_value = b""  # empty
        opener.open.return_value = resp
        return opener

    monkeypatch.setattr(
        "autodev.adapters.a2a.transports.http._build_pinned_opener", _fake_build
    )

    transport = A2AHttpTransport("http://example.com")
    status, parsed = transport._get_json("http://example.com/tasks/123")
    assert status == 200
    assert parsed is None


# ===========================================================================
# Group 19 — send_task: status_code == 0 (line 598)
# ===========================================================================


def test_send_task_connection_error_returns_failed(monkeypatch) -> None:
    """send_task returns FAILED when _make_request returns status=0 (connection error)."""
    monkeypatch.delenv("AUTODEV_A2A_ALLOW_PRIVATE_NETWORKS", raising=False)
    monkeypatch.setattr(socket, "getaddrinfo", _gai_public)

    # Force _make_request to return (0, b'') → status_code == 0
    def _fake_build(*args, **kwargs):
        opener = MagicMock()
        opener.open.side_effect = OSError("connection refused")
        return opener

    monkeypatch.setattr(
        "autodev.adapters.a2a.transports.http._build_pinned_opener", _fake_build
    )

    task = _make_task()
    card = _make_card()
    transport = A2AHttpTransport("http://example.com")
    result = transport.send_task(card, task)

    assert result.status == A2ATaskStatus.FAILED
    assert any("connection error" in (a.text or "") for a in result.artifacts)


# ===========================================================================
# Group 20 — send_task: resp is None after non-error status (line 608)
# ===========================================================================


def test_send_task_empty_response_body_returns_failed(monkeypatch) -> None:
    """send_task returns FAILED when response body is empty (resp is None)."""
    monkeypatch.delenv("AUTODEV_A2A_ALLOW_PRIVATE_NETWORKS", raising=False)
    monkeypatch.setattr(socket, "getaddrinfo", _gai_public)

    def _fake_build(*args, **kwargs):
        opener = MagicMock()
        resp = MagicMock()
        resp.__enter__ = lambda s: s
        resp.__exit__ = MagicMock(return_value=False)
        resp.status = 200
        resp.headers.get.return_value = None
        resp.read.return_value = b""  # empty → _post_json returns (200, None)
        opener.open.return_value = resp
        return opener

    monkeypatch.setattr(
        "autodev.adapters.a2a.transports.http._build_pinned_opener", _fake_build
    )

    task = _make_task()
    card = _make_card()
    transport = A2AHttpTransport("http://example.com")
    result = transport.send_task(card, task)

    assert result.status == A2ATaskStatus.FAILED
    assert any("empty or unparseable" in (a.text or "") for a in result.artifacts)


# ===========================================================================
# Group 21 — send_task: HTTP 4xx returns FAILED (line 602-606)
# ===========================================================================


def test_send_task_http_4xx_returns_failed(monkeypatch) -> None:
    """send_task returns FAILED on HTTP 4xx from the remote server."""
    monkeypatch.delenv("AUTODEV_A2A_ALLOW_PRIVATE_NETWORKS", raising=False)
    monkeypatch.setattr(socket, "getaddrinfo", _gai_public)

    def _fake_build(*args, **kwargs):
        opener = MagicMock()
        resp = MagicMock()
        resp.__enter__ = lambda s: s
        resp.__exit__ = MagicMock(return_value=False)
        resp.status = 401
        resp.headers.get.return_value = None
        resp.read.return_value = b'{"error": "unauthorized"}'
        opener.open.return_value = resp
        return opener

    monkeypatch.setattr(
        "autodev.adapters.a2a.transports.http._build_pinned_opener", _fake_build
    )

    task = _make_task()
    card = _make_card()
    transport = A2AHttpTransport("http://example.com")
    result = transport.send_task(card, task)

    assert result.status == A2ATaskStatus.FAILED
    assert any("HTTP 401" in (a.text or "") for a in result.artifacts)


# ===========================================================================
# Group 22 — send_task: unexpected response shape — non-dict task_data (line 616)
# ===========================================================================


def test_send_task_unexpected_response_shape_returns_failed(monkeypatch) -> None:
    """send_task returns FAILED when response JSON is not a dict-shaped task."""
    monkeypatch.delenv("AUTODEV_A2A_ALLOW_PRIVATE_NETWORKS", raising=False)
    monkeypatch.setattr(socket, "getaddrinfo", _gai_public)

    # Return a JSON array — not a dict — as the response body.
    def _fake_build(*args, **kwargs):
        opener = MagicMock()
        resp = MagicMock()
        resp.__enter__ = lambda s: s
        resp.__exit__ = MagicMock(return_value=False)
        resp.status = 200
        resp.headers.get.return_value = None
        resp.read.return_value = b'[1, 2, 3]'
        opener.open.return_value = resp
        return opener

    monkeypatch.setattr(
        "autodev.adapters.a2a.transports.http._build_pinned_opener", _fake_build
    )

    task = _make_task()
    card = _make_card()
    transport = A2AHttpTransport("http://example.com")
    result = transport.send_task(card, task)

    assert result.status == A2ATaskStatus.FAILED
    assert any("unexpected response shape" in (a.text or "") for a in result.artifacts)


# ===========================================================================
# Group 23 — _poll_until_done: status_code==0 / resp is None → continue (line 641)
# ===========================================================================


def test_poll_until_done_transient_failure_retries_then_succeeds(monkeypatch) -> None:
    """_poll_until_done continues past transient failures (status 0) and eventually succeeds."""
    monkeypatch.delenv("AUTODEV_A2A_ALLOW_PRIVATE_NETWORKS", raising=False)
    monkeypatch.setattr(socket, "getaddrinfo", _gai_public)

    call_n = {"n": 0}
    task = _make_task()
    completed_body = _task_dict(task, status="completed")

    import json as _json

    def _fake_build(*args, **kwargs):
        opener = MagicMock()

        def _open(req, *a, **kw):
            call_n["n"] += 1
            resp = MagicMock()
            resp.__enter__ = lambda s: s
            resp.__exit__ = MagicMock(return_value=False)
            resp.headers.get.return_value = None
            # First two GET poll calls return empty body (transient failure).
            # POST send_task returns working status; polls return completed after 2 fails.
            if req.get_method() == "POST":
                working = _task_dict(task, status="working")
                resp.status = 200
                resp.read.return_value = _json.dumps(working).encode()
            elif call_n["n"] <= 3:
                # Transient: empty body → (200, None)
                resp.status = 200
                resp.read.return_value = b""
            else:
                resp.status = 200
                resp.read.return_value = _json.dumps(completed_body).encode()
            return resp

        opener.open.side_effect = _open
        return opener

    monkeypatch.setattr(
        "autodev.adapters.a2a.transports.http._build_pinned_opener", _fake_build
    )

    card = _make_card()
    transport = A2AHttpTransport(
        "http://example.com", poll_interval=0.0, max_poll_attempts=10
    )
    result = transport.send_task(card, task)
    assert result.status == A2ATaskStatus.COMPLETED


# ===========================================================================
# Group 24 — _poll_until_done: task_data not dict → continue (line 644)
# ===========================================================================


def test_poll_until_done_non_dict_task_data_continues(monkeypatch) -> None:
    """_poll_until_done skips a poll response where task_data is not a dict."""
    monkeypatch.delenv("AUTODEV_A2A_ALLOW_PRIVATE_NETWORKS", raising=False)
    monkeypatch.setattr(socket, "getaddrinfo", _gai_public)

    call_n = {"n": 0}
    task = _make_task()
    import json as _json

    # POST returns working; first poll returns array (not dict); second returns completed.
    def _fake_build(*args, **kwargs):
        opener = MagicMock()

        def _open(req, *a, **kw):
            call_n["n"] += 1
            resp = MagicMock()
            resp.__enter__ = lambda s: s
            resp.__exit__ = MagicMock(return_value=False)
            resp.headers.get.return_value = None
            if req.get_method() == "POST":
                working = _task_dict(task, status="working")
                resp.status = 200
                resp.read.return_value = _json.dumps(working).encode()
            elif call_n["n"] == 2:
                # First poll: non-dict response
                resp.status = 200
                resp.read.return_value = _json.dumps([1, 2, 3]).encode()
            else:
                resp.status = 200
                resp.read.return_value = _json.dumps(
                    _task_dict(task, status="completed")
                ).encode()
            return resp

        opener.open.side_effect = _open
        return opener

    monkeypatch.setattr(
        "autodev.adapters.a2a.transports.http._build_pinned_opener", _fake_build
    )

    card = _make_card()
    transport = A2AHttpTransport(
        "http://example.com", poll_interval=0.0, max_poll_attempts=10
    )
    result = transport.send_task(card, task)
    assert result.status == A2ATaskStatus.COMPLETED


# ===========================================================================
# Group 25 — _poll_until_done: model_validate exception → continue (lines 647-648)
# ===========================================================================


def test_poll_until_done_bad_schema_continues(monkeypatch) -> None:
    """_poll_until_done skips a poll response that fails A2ATask.model_validate."""
    monkeypatch.delenv("AUTODEV_A2A_ALLOW_PRIVATE_NETWORKS", raising=False)
    monkeypatch.setattr(socket, "getaddrinfo", _gai_public)

    call_n = {"n": 0}
    task = _make_task()
    import json as _json

    def _fake_build(*args, **kwargs):
        opener = MagicMock()

        def _open(req, *a, **kw):
            call_n["n"] += 1
            resp = MagicMock()
            resp.__enter__ = lambda s: s
            resp.__exit__ = MagicMock(return_value=False)
            resp.headers.get.return_value = None
            if req.get_method() == "POST":
                working = _task_dict(task, status="working")
                resp.status = 200
                resp.read.return_value = _json.dumps(working).encode()
            elif call_n["n"] == 2:
                # First poll: dict with missing required fields → model_validate fails
                resp.status = 200
                resp.read.return_value = _json.dumps({"status": "working"}).encode()
            else:
                resp.status = 200
                resp.read.return_value = _json.dumps(
                    _task_dict(task, status="completed")
                ).encode()
            return resp

        opener.open.side_effect = _open
        return opener

    monkeypatch.setattr(
        "autodev.adapters.a2a.transports.http._build_pinned_opener", _fake_build
    )

    card = _make_card()
    transport = A2AHttpTransport(
        "http://example.com", poll_interval=0.0, max_poll_attempts=10
    )
    result = transport.send_task(card, task)
    assert result.status == A2ATaskStatus.COMPLETED


# ===========================================================================
# Group 26 — _poll_until_done: exhausted poll budget (line 658)
# ===========================================================================


def test_poll_until_done_exhausted_returns_failed(monkeypatch) -> None:
    """_poll_until_done returns FAILED task after exhausting max_poll_attempts."""
    monkeypatch.delenv("AUTODEV_A2A_ALLOW_PRIVATE_NETWORKS", raising=False)
    monkeypatch.setattr(socket, "getaddrinfo", _gai_public)

    task = _make_task()
    import json as _json

    def _fake_build(*args, **kwargs):
        opener = MagicMock()

        def _open(req, *a, **kw):
            resp = MagicMock()
            resp.__enter__ = lambda s: s
            resp.__exit__ = MagicMock(return_value=False)
            resp.headers.get.return_value = None
            # Always return WORKING — never terminal.
            working = _task_dict(task, status="working")
            resp.status = 200
            resp.read.return_value = _json.dumps(working).encode()
            return resp

        opener.open.side_effect = _open
        return opener

    monkeypatch.setattr(
        "autodev.adapters.a2a.transports.http._build_pinned_opener", _fake_build
    )

    card = _make_card()
    transport = A2AHttpTransport(
        "http://example.com", poll_interval=0.0, max_poll_attempts=3
    )
    result = transport.send_task(card, task)

    assert result.status == A2ATaskStatus.FAILED
    assert any("polling timed out" in (a.text or "") for a in result.artifacts)


# ===========================================================================
# Group 27 — discover_agent_card: AgentCard.model_validate exception (lines 674-675)
# ===========================================================================


def test_discover_agent_card_schema_error_returns_none(monkeypatch) -> None:
    """discover_agent_card returns None when response JSON fails AgentCard validation."""
    monkeypatch.delenv("AUTODEV_A2A_ALLOW_PRIVATE_NETWORKS", raising=False)
    monkeypatch.setattr(socket, "getaddrinfo", _gai_public)

    def _fake_build(*args, **kwargs):
        opener = MagicMock()
        resp = MagicMock()
        resp.__enter__ = lambda s: s
        resp.__exit__ = MagicMock(return_value=False)
        resp.status = 200
        resp.headers.get.return_value = None
        # Valid JSON but missing required AgentCard fields (e.g. 'name').
        resp.read.return_value = b'{"description": "missing name field"}'
        opener.open.return_value = resp
        return opener

    monkeypatch.setattr(
        "autodev.adapters.a2a.transports.http._build_pinned_opener", _fake_build
    )

    transport = A2AHttpTransport("http://example.com")
    result = transport.discover_agent_card()
    assert result is None


# ===========================================================================
# Group 28 — discover_agent_card: HTTP 4xx returns None
# ===========================================================================


def test_discover_agent_card_http_4xx_returns_none(monkeypatch) -> None:
    """discover_agent_card returns None on HTTP 404."""
    monkeypatch.delenv("AUTODEV_A2A_ALLOW_PRIVATE_NETWORKS", raising=False)
    monkeypatch.setattr(socket, "getaddrinfo", _gai_public)

    def _fake_build(*args, **kwargs):
        opener = MagicMock()
        resp = MagicMock()
        resp.__enter__ = lambda s: s
        resp.__exit__ = MagicMock(return_value=False)
        resp.status = 404
        resp.headers.get.return_value = None
        resp.read.return_value = b'{"error": "not found"}'
        opener.open.return_value = resp
        return opener

    monkeypatch.setattr(
        "autodev.adapters.a2a.transports.http._build_pinned_opener", _fake_build
    )

    transport = A2AHttpTransport("http://example.com")
    result = transport.discover_agent_card()
    assert result is None


# ===========================================================================
# Group 29 — is_reachable: returns True on 2xx (lines 682-683)
# ===========================================================================


def test_is_reachable_true_on_200(monkeypatch) -> None:
    """is_reachable returns True when HEAD returns 200."""
    monkeypatch.delenv("AUTODEV_A2A_ALLOW_PRIVATE_NETWORKS", raising=False)
    monkeypatch.setattr(socket, "getaddrinfo", _gai_public)

    def _fake_build(*args, **kwargs):
        opener = MagicMock()
        resp = MagicMock()
        resp.__enter__ = lambda s: s
        resp.__exit__ = MagicMock(return_value=False)
        resp.status = 200
        resp.headers.get.return_value = None
        resp.read.return_value = b""
        opener.open.return_value = resp
        return opener

    monkeypatch.setattr(
        "autodev.adapters.a2a.transports.http._build_pinned_opener", _fake_build
    )

    transport = A2AHttpTransport("http://example.com")
    assert transport.is_reachable() is True


def test_is_reachable_false_on_500(monkeypatch) -> None:
    """is_reachable returns False when HEAD returns 500."""
    monkeypatch.delenv("AUTODEV_A2A_ALLOW_PRIVATE_NETWORKS", raising=False)
    monkeypatch.setattr(socket, "getaddrinfo", _gai_public)

    def _fake_build(*args, **kwargs):
        opener = MagicMock()
        resp = MagicMock()
        resp.__enter__ = lambda s: s
        resp.__exit__ = MagicMock(return_value=False)
        resp.status = 500
        resp.headers.get.return_value = None
        resp.read.return_value = b""
        opener.open.return_value = resp
        return opener

    monkeypatch.setattr(
        "autodev.adapters.a2a.transports.http._build_pinned_opener", _fake_build
    )

    transport = A2AHttpTransport("http://example.com")
    assert transport.is_reachable() is False


def test_is_reachable_false_on_connection_error(monkeypatch) -> None:
    """is_reachable returns False when connection fails (status 0)."""
    monkeypatch.delenv("AUTODEV_A2A_ALLOW_PRIVATE_NETWORKS", raising=False)
    monkeypatch.setattr(socket, "getaddrinfo", _gai_public)

    def _fake_build(*args, **kwargs):
        opener = MagicMock()
        opener.open.side_effect = OSError("refused")
        return opener

    monkeypatch.setattr(
        "autodev.adapters.a2a.transports.http._build_pinned_opener", _fake_build
    )

    transport = A2AHttpTransport("http://example.com")
    assert transport.is_reachable() is False


# ===========================================================================
# Group 30 — AUTODEV_A2A_ALLOW_PRIVATE_NETWORKS env var override
# ===========================================================================


def test_env_var_allow_private_networks_1(monkeypatch) -> None:
    """AUTODEV_A2A_ALLOW_PRIVATE_NETWORKS=1 enables private network mode."""
    monkeypatch.setenv("AUTODEV_A2A_ALLOW_PRIVATE_NETWORKS", "1")
    transport = A2AHttpTransport("http://127.0.0.1:9999", allow_private_networks=False)
    assert transport._allow_private_networks is True


def test_env_var_allow_private_networks_true(monkeypatch) -> None:
    """AUTODEV_A2A_ALLOW_PRIVATE_NETWORKS=true enables private network mode."""
    monkeypatch.setenv("AUTODEV_A2A_ALLOW_PRIVATE_NETWORKS", "true")
    transport = A2AHttpTransport("http://127.0.0.1:9999", allow_private_networks=False)
    assert transport._allow_private_networks is True


def test_env_var_allow_private_networks_yes(monkeypatch) -> None:
    """AUTODEV_A2A_ALLOW_PRIVATE_NETWORKS=yes enables private network mode."""
    monkeypatch.setenv("AUTODEV_A2A_ALLOW_PRIVATE_NETWORKS", "yes")
    transport = A2AHttpTransport("http://example.com", allow_private_networks=False)
    assert transport._allow_private_networks is True


def test_env_var_not_set_uses_constructor(monkeypatch) -> None:
    """When env var is absent, constructor kwarg is used."""
    monkeypatch.delenv("AUTODEV_A2A_ALLOW_PRIVATE_NETWORKS", raising=False)
    transport_on = A2AHttpTransport("http://example.com", allow_private_networks=True)
    transport_off = A2AHttpTransport("http://example.com", allow_private_networks=False)
    assert transport_on._allow_private_networks is True
    assert transport_off._allow_private_networks is False


# ===========================================================================
# Group 31 — SSRF: additional ranges (172.16.x, fe80::, fc00::, ::)
# ===========================================================================


def test_validate_url_172_16_rejected() -> None:
    """172.16.0.1 is in RFC-1918 class B → rejected."""
    with pytest.raises(A2AHttpSSRFError, match="private/restricted"):
        _validate_url("http://172.16.0.1/api")


def test_validate_url_172_31_rejected() -> None:
    """172.31.255.255 is at the top of the RFC-1918 class B range → rejected."""
    with pytest.raises(A2AHttpSSRFError, match="private/restricted"):
        _validate_url("http://172.31.255.255/")


def test_validate_url_fe80_rejected() -> None:
    """fe80::1 is link-local IPv6 → rejected."""
    with pytest.raises(A2AHttpSSRFError, match="private/restricted"):
        _validate_url("http://[fe80::1]/")


def test_validate_url_fc00_rejected() -> None:
    """fc00::1 is unique local IPv6 → rejected."""
    with pytest.raises(A2AHttpSSRFError, match="private/restricted"):
        _validate_url("http://[fc00::1]/")


def test_validate_url_unspecified_ipv6_rejected() -> None:
    """:: (unspecified IPv6) is rejected."""
    with pytest.raises(A2AHttpSSRFError, match="private/restricted"):
        _validate_url("http://[::]/")


def test_validate_url_169_254_169_254_rejected() -> None:
    """169.254.169.254 (AWS metadata) is rejected."""
    with pytest.raises(A2AHttpSSRFError, match="private/restricted"):
        _validate_url("http://169.254.169.254/latest/meta-data/iam/")


# ===========================================================================
# Group 32 — _get_json: bad JSON returns (status, None) (lines 579-580)
# ===========================================================================


def test_get_json_bad_json_returns_none(monkeypatch) -> None:
    """_get_json returns (status, None) when body is invalid JSON."""
    monkeypatch.delenv("AUTODEV_A2A_ALLOW_PRIVATE_NETWORKS", raising=False)
    monkeypatch.setattr(socket, "getaddrinfo", _gai_public)

    def _fake_build(*args, **kwargs):
        opener = MagicMock()
        resp = MagicMock()
        resp.__enter__ = lambda s: s
        resp.__exit__ = MagicMock(return_value=False)
        resp.status = 200
        resp.headers.get.return_value = None
        resp.read.return_value = b"INVALID JSON {{{"
        opener.open.return_value = resp
        return opener

    monkeypatch.setattr(
        "autodev.adapters.a2a.transports.http._build_pinned_opener", _fake_build
    )

    transport = A2AHttpTransport("http://example.com")
    status, parsed = transport._get_json("http://example.com/tasks/abc")
    assert status == 200
    assert parsed is None


# ===========================================================================
# Group 33 — A2AHttpSSRFError caught in _make_request returns (0, b'') (line 558-559)
# ===========================================================================


def test_make_request_ssrf_blocked_returns_zero(monkeypatch) -> None:
    """_make_request returns (0, b'') when URL is blocked by SSRF guard."""
    monkeypatch.delenv("AUTODEV_A2A_ALLOW_PRIVATE_NETWORKS", raising=False)

    transport = A2AHttpTransport("http://example.com")
    # 127.0.0.1 is a private literal → _validate_url raises A2AHttpSSRFError.
    status, body = transport._make_request("http://127.0.0.1:8080/admin")
    assert status == 0
    assert body == b""


# ===========================================================================
# Group 34 — send_task: FAILED initial response returned immediately
# ===========================================================================


def test_send_task_initial_failed_response_returned(monkeypatch) -> None:
    """send_task returns FAILED immediately when initial server response is FAILED."""
    monkeypatch.delenv("AUTODEV_A2A_ALLOW_PRIVATE_NETWORKS", raising=False)
    monkeypatch.setattr(socket, "getaddrinfo", _gai_public)

    task = _make_task()
    import json as _json

    def _fake_build(*args, **kwargs):
        opener = MagicMock()
        resp = MagicMock()
        resp.__enter__ = lambda s: s
        resp.__exit__ = MagicMock(return_value=False)
        resp.status = 200
        resp.headers.get.return_value = None
        resp.read.return_value = _json.dumps(
            _task_dict(task, status="failed")
        ).encode()
        opener.open.return_value = resp
        return opener

    monkeypatch.setattr(
        "autodev.adapters.a2a.transports.http._build_pinned_opener", _fake_build
    )

    card = _make_card()
    transport = A2AHttpTransport("http://example.com")
    result = transport.send_task(card, task)
    assert result.status == A2ATaskStatus.FAILED


# ===========================================================================
# Group 35 — send_task: CANCELED initial response returned immediately
# ===========================================================================


def test_send_task_initial_canceled_response_returned(monkeypatch) -> None:
    """send_task returns CANCELED immediately when initial server response is CANCELED."""
    monkeypatch.delenv("AUTODEV_A2A_ALLOW_PRIVATE_NETWORKS", raising=False)
    monkeypatch.setattr(socket, "getaddrinfo", _gai_public)

    task = _make_task()
    import json as _json

    def _fake_build(*args, **kwargs):
        opener = MagicMock()
        resp = MagicMock()
        resp.__enter__ = lambda s: s
        resp.__exit__ = MagicMock(return_value=False)
        resp.status = 200
        resp.headers.get.return_value = None
        resp.read.return_value = _json.dumps(
            _task_dict(task, status="canceled")
        ).encode()
        opener.open.return_value = resp
        return opener

    monkeypatch.setattr(
        "autodev.adapters.a2a.transports.http._build_pinned_opener", _fake_build
    )

    card = _make_card()
    transport = A2AHttpTransport("http://example.com")
    result = transport.send_task(card, task)
    assert result.status == A2ATaskStatus.CANCELED


# ===========================================================================
# Group 36 — _poll_until_done: result wrapped in {"result": ...}
# ===========================================================================


def test_poll_until_done_unwraps_result_key(monkeypatch) -> None:
    """_poll_until_done correctly unwraps {"result": task_dict} from poll response."""
    monkeypatch.delenv("AUTODEV_A2A_ALLOW_PRIVATE_NETWORKS", raising=False)
    monkeypatch.setattr(socket, "getaddrinfo", _gai_public)

    call_n = {"n": 0}
    task = _make_task()
    import json as _json

    def _fake_build(*args, **kwargs):
        opener = MagicMock()

        def _open(req, *a, **kw):
            call_n["n"] += 1
            resp = MagicMock()
            resp.__enter__ = lambda s: s
            resp.__exit__ = MagicMock(return_value=False)
            resp.headers.get.return_value = None
            if req.get_method() == "POST":
                # POST send_task returns working
                working = _task_dict(task, status="working")
                resp.status = 200
                resp.read.return_value = _json.dumps(working).encode()
            else:
                # GET poll returns wrapped {"result": completed_task}
                resp.status = 200
                resp.read.return_value = _json.dumps(
                    {"result": _task_dict(task, status="completed")}
                ).encode()
            return resp

        opener.open.side_effect = _open
        return opener

    monkeypatch.setattr(
        "autodev.adapters.a2a.transports.http._build_pinned_opener", _fake_build
    )

    card = _make_card()
    transport = A2AHttpTransport(
        "http://example.com", poll_interval=0.0, max_poll_attempts=5
    )
    result = transport.send_task(card, task)
    assert result.status == A2ATaskStatus.COMPLETED
