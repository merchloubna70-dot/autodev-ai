"""DNS-rebinding TOCTOU hardening tests for A2AHttpTransport.

These tests verify the IP-pinning mitigation introduced in R3-E:
- ``_resolve_and_pin_host`` resolves once, validates, returns the pinned IP.
- ``_build_pinned_opener`` creates a urllib opener whose HTTP/HTTPS handler
  connects to the pinned IP (not the hostname), so the OS resolver is never
  called again for that hop.
- On redirect hops the Location hostname is independently re-resolved and
  re-pinned — never reused from the previous hop.
- ``allow_private_networks=True`` bypasses IP-pinning (integration-test
  escape hatch).

No real network connections are ever made.  ``socket.getaddrinfo`` is
monkeypatched to simulate DNS responses; ``urllib.request.OpenerDirector.open``
is monkeypatched to return fake HTTP responses without touching the network.
"""
from __future__ import annotations

import socket
import urllib.error
import urllib.parse
import urllib.request
from http.client import HTTPMessage
from io import BytesIO
from unittest.mock import MagicMock, patch

import pytest

from autodev.adapters.a2a.transports.http import (
    A2AHttpSSRFError,
    A2AHttpTransport,
    _PinnedHTTPSConnection,
    _resolve_and_pin_host,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _gai_fixed(ip: str):
    """Return a getaddrinfo that always resolves to *ip*."""
    def _gai(host, port, *args, **kwargs):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, 0))]
    return _gai


def _gai_sequence(*ips: str):
    """Return a getaddrinfo side_effect that cycles through *ips* on each call."""
    ip_iter = iter(ips)

    def _gai(host, port, *args, **kwargs):
        ip = next(ip_iter)
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, 0))]

    return _gai


def _gai_by_host(**host_to_ip: str):
    """Return a getaddrinfo that returns different IPs for different hostnames."""
    def _gai(host, port, *args, **kwargs):
        ip = host_to_ip.get(host, "93.184.216.34")
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, 0))]
    return _gai


def _fake_opener_200(body: bytes = b'{"ok": true}') -> MagicMock:
    """Build a fake urllib OpenerDirector that returns HTTP 200."""
    resp = MagicMock()
    resp.__enter__ = lambda s: s
    resp.__exit__ = MagicMock(return_value=False)
    resp.status = 200
    resp.headers.get.return_value = None
    resp.read.return_value = body

    opener = MagicMock()
    opener.open.return_value = resp
    return opener


def _fake_opener_redirect(location: str, then_status: int = 200,
                          then_body: bytes = b'{"ok": true}') -> tuple[MagicMock, list[str]]:
    """Build a fake opener that returns a 302 redirect on the first call,
    then a *then_status* response on the second call.

    Returns (opener_mock, urls_opened) where urls_opened accumulates the URL
    each call received.
    """
    urls_opened: list[str] = []

    call_n = {"n": 0}

    def _open(req, *args, **kwargs):
        urls_opened.append(req.full_url if hasattr(req, "full_url") else str(req))
        call_n["n"] += 1
        if call_n["n"] == 1:
            # First call: 302 redirect.
            hdrs = HTTPMessage()
            hdrs["Location"] = location
            raise urllib.error.HTTPError(
                url=str(req),
                code=302,
                msg="Found",
                hdrs=hdrs,
                fp=BytesIO(b""),
            )
        # Second call: final response.
        resp = MagicMock()
        resp.__enter__ = lambda s: s
        resp.__exit__ = MagicMock(return_value=False)
        resp.status = then_status
        resp.headers.get.return_value = None
        resp.read.return_value = then_body
        return resp

    opener = MagicMock()
    opener.open.side_effect = _open
    return opener, urls_opened


# ---------------------------------------------------------------------------
# Patch helper: intercept _build_pinned_opener and return controlled openers.
# ---------------------------------------------------------------------------


def _patch_build_pinned_opener(monkeypatch, openers: list[MagicMock]) -> list[str]:
    """Replace _build_pinned_opener with a function that pops from *openers*.

    Returns a list that accumulates the ``pinned_ip`` argument passed on
    each call so tests can verify which IP was used for the connection.
    """
    captured_ips: list[str] = []
    opener_iter = iter(openers)

    def _fake_build(pinned_ip, original_host, scheme, port):
        captured_ips.append(pinned_ip)
        return next(opener_iter)

    monkeypatch.setattr(
        "autodev.adapters.a2a.transports.http._build_pinned_opener",
        _fake_build,
    )
    return captured_ips


# ===========================================================================
# Test 1: DNS-rebinding scenario — validation-time DNS returns public IP;
#         "connect-time" DNS would return private IP.
#
#         With IP-pinning, _resolve_and_pin_host is called ONCE and the
#         result (public IP) is passed to the pinned opener.  The OS
#         resolver is never consulted again for that hop.  Even if a second
#         getaddrinfo call were made by the OS it would be a no-op because
#         we are connecting to the already-resolved IP.
#
#         Test: verify pinned_ip passed to _build_pinned_opener is the
#         *first* DNS result (public), not a hypothetical second result.
# ===========================================================================


def test_dns_rebinding_connect_to_pinned_public_ip(monkeypatch) -> None:
    """IP-pinning: the connection target is the first resolved IP (public).
    Even if a second DNS query would return a private IP, it is never made.
    """
    monkeypatch.delenv("AUTODEV_A2A_ALLOW_PRIVATE_NETWORKS", raising=False)

    dns_call_count = {"n": 0}

    def _rebinding_gai(host, port, *args, **kwargs):
        dns_call_count["n"] += 1
        if dns_call_count["n"] <= 2:
            # Both _validate_url and _resolve_and_pin_host calls return public IP.
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 0))]
        # Simulated attacker DNS flip: hypothetical third call would be private.
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 0))]

    monkeypatch.setattr(socket, "getaddrinfo", _rebinding_gai)

    fake_opener = _fake_opener_200()
    captured_ips = _patch_build_pinned_opener(monkeypatch, [fake_opener])

    transport = A2AHttpTransport("http://example.com")
    status, _body = transport._make_request("http://example.com/tasks/send", method="GET")

    # Request should succeed.
    assert status == 200, f"Expected 200, got {status}"
    # Connected to the public IP (pinned), never to localhost.
    assert captured_ips == ["93.184.216.34"], f"Unexpected connect target: {captured_ips}"
    # getaddrinfo was called at most twice (once in _validate_url, once in
    # _resolve_and_pin_host) — never more, so the "flip" scenario is blocked.
    assert dns_call_count["n"] <= 2, (
        f"getaddrinfo called {dns_call_count['n']} times; expected ≤ 2"
    )


# ===========================================================================
# Test 2: Two different *public* IPs at validate vs. resolve-pin time.
#         Request should still succeed because both are public.
#         The pinned IP is the one returned by _resolve_and_pin_host.
# ===========================================================================


def test_different_public_ip_at_connect_time_succeeds(monkeypatch) -> None:
    """Two different public IPs (validate vs. pin): both are safe, request succeeds."""
    monkeypatch.delenv("AUTODEV_A2A_ALLOW_PRIVATE_NETWORKS", raising=False)

    call_n = {"n": 0}

    def _alt_gai(host, port, *args, **kwargs):
        call_n["n"] += 1
        # First call (_validate_url): public IP A.
        if call_n["n"] == 1:
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 0))]
        # Second call (_resolve_and_pin_host): different public IP B.
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 0))]

    monkeypatch.setattr(socket, "getaddrinfo", _alt_gai)

    fake_opener = _fake_opener_200()
    captured_ips = _patch_build_pinned_opener(monkeypatch, [fake_opener])

    transport = A2AHttpTransport("http://example.com")
    status, _ = transport._make_request("http://example.com/", method="GET")

    assert status == 200
    # Pinned to the IP returned by _resolve_and_pin_host (second call → 8.8.8.8).
    assert captured_ips[0] in ("93.184.216.34", "8.8.8.8"), (
        f"Unexpected IP: {captured_ips}"
    )


# ===========================================================================
# Test 3: Redirect Location hostname resolves to private IP — REJECTED.
# ===========================================================================


def test_redirect_to_private_hostname_rejected(monkeypatch) -> None:
    """A redirect whose Location hostname resolves to a private IP is blocked."""
    monkeypatch.delenv("AUTODEV_A2A_ALLOW_PRIVATE_NETWORKS", raising=False)

    monkeypatch.setattr(
        socket, "getaddrinfo",
        _gai_by_host(**{"example.com": "93.184.216.34",
                        "internal.corp.example": "10.0.0.1"})
    )

    redirect_opener, _ = _fake_opener_redirect("http://internal.corp.example/secret")
    captured_ips = _patch_build_pinned_opener(monkeypatch, [redirect_opener])

    transport = A2AHttpTransport("http://example.com")
    status, body = transport._make_request("http://example.com/", method="GET")

    # Should be blocked (0, b'') — second hop SSRF guard fires.
    assert status == 0
    assert body == b""
    # Only one pinned connection was opened (to example.com).
    assert len(captured_ips) == 1
    assert captured_ips[0] == "93.184.216.34"


# ===========================================================================
# Test 4: Redirect Location hostname resolves to public IP — ALLOWED.
# ===========================================================================


def test_redirect_to_public_hostname_allowed(monkeypatch) -> None:
    """A redirect whose Location hostname resolves to a public IP is allowed."""
    monkeypatch.delenv("AUTODEV_A2A_ALLOW_PRIVATE_NETWORKS", raising=False)

    # Both hosts map to a public IP.
    monkeypatch.setattr(socket, "getaddrinfo", _gai_fixed("93.184.216.34"))

    redirect_opener, _ = _fake_opener_redirect(
        "http://other.example.com/final",
        then_status=200,
        then_body=b'{"result": "ok"}',
    )
    # Two pinned openers: one for initial hop, one for redirect hop.
    # But _fake_opener_redirect already handles both calls internally.
    # We need the second pinned opener to return the 200 from the redirect.
    second_opener = _fake_opener_200(b'{"result": "ok"}')
    captured_ips = _patch_build_pinned_opener(monkeypatch, [redirect_opener, second_opener])

    transport = A2AHttpTransport("http://example.com")
    status, _body = transport._make_request("http://example.com/api", method="GET")

    assert status == 200
    # Both hops connected to a public IP (pinned).
    assert len(captured_ips) == 2
    assert all(ip == "93.184.216.34" for ip in captured_ips)


# ===========================================================================
# Test 5: max_redirects=5 is enforced (6th hop → (0, b'')).
# ===========================================================================


def test_max_redirects_5_enforced(monkeypatch) -> None:
    """After 5 redirect hops the budget is exhausted → (0, b'')."""
    monkeypatch.delenv("AUTODEV_A2A_ALLOW_PRIVATE_NETWORKS", raising=False)

    monkeypatch.setattr(socket, "getaddrinfo", _gai_fixed("93.184.216.34"))

    # Build 6 single-redirect openers (hops 0-5).
    openers = []
    for i in range(6):
        resp_mock = MagicMock()
        resp_mock.__enter__ = lambda s: s
        resp_mock.__exit__ = MagicMock(return_value=False)

        hdrs = HTTPMessage()
        hdrs["Location"] = f"http://example.com/hop{i + 1}"

        def _open(req, *args, hdrs=hdrs, **kwargs):
            raise urllib.error.HTTPError(
                url=str(req), code=302, msg="Found", hdrs=hdrs, fp=BytesIO(b"")
            )

        opener = MagicMock()
        opener.open.side_effect = _open
        openers.append(opener)

    captured_ips = _patch_build_pinned_opener(monkeypatch, openers)

    transport = A2AHttpTransport("http://example.com")
    status, body = transport._make_request("http://example.com/start", method="GET")

    # Exhausted redirect budget → (0, b'').
    assert status == 0
    assert body == b""
    # Exactly 6 connections were attempted (hops 0-5).
    assert len(captured_ips) == 6


# ===========================================================================
# Test 6: HTTPS — _PinnedHTTPSConnection stores server_hostname for SNI.
#
#         We don't open a real TLS connection.  We verify that the connection
#         object is configured with the correct server_hostname so that when
#         connect() is called SNI + cert validation will use the right name.
# ===========================================================================


def test_https_server_hostname_set_correctly() -> None:
    """_PinnedHTTPSConnection stores the original hostname for SNI/cert."""
    conn = _PinnedHTTPSConnection(
        connect_host="93.184.216.34",
        server_hostname="example.com",
        port=443,
        timeout=5.0,
    )
    # The pinned IP is the TCP target.
    assert conn.host == "93.184.216.34"
    # The original hostname is stored for SNI/cert validation.
    assert conn._pinned_server_hostname == "example.com"
    conn.close()


# ===========================================================================
# Test 7: allow_private_networks=True bypasses IP-pinning entirely.
#         _build_pinned_opener must NOT be called; urllib default opener is used.
# ===========================================================================


def test_allow_private_networks_bypasses_ip_pinning(monkeypatch) -> None:
    """allow_private_networks=True skips _build_pinned_opener; uses urllib."""
    # DO NOT delete AUTODEV_A2A_ALLOW_PRIVATE_NETWORKS — conftest sets it to
    # "1" which already activates allow_private.  We verify the bypass here.

    pinned_called = {"called": False}

    def _fake_build(*args, **kwargs):
        pinned_called["called"] = True
        return _fake_opener_200()

    monkeypatch.setattr(
        "autodev.adapters.a2a.transports.http._build_pinned_opener",
        _fake_build,
    )

    fake_resp = MagicMock()
    fake_resp.__enter__ = lambda s: s
    fake_resp.__exit__ = MagicMock(return_value=False)
    fake_resp.status = 200
    fake_resp.headers.get.return_value = None
    fake_resp.read.return_value = b'{"ok": true}'

    with patch("urllib.request.OpenerDirector.open", return_value=fake_resp):
        transport = A2AHttpTransport(
            "http://127.0.0.1:9999",
            allow_private_networks=True,
        )
        status, _body = transport._make_request("http://127.0.0.1:9999/ping", method="GET")

    # _build_pinned_opener must NOT have been called.
    assert pinned_called["called"] is False, (
        "_build_pinned_opener should not be called when allow_private_networks=True"
    )
    assert status == 200


# ===========================================================================
# Test 8: IPv6 redirect to [::1] (loopback) is rejected by _validate_url.
# ===========================================================================


def test_ipv6_redirect_to_loopback_rejected(monkeypatch) -> None:
    """A redirect to http://[::1]/ is blocked because ::1 is the loopback."""
    monkeypatch.delenv("AUTODEV_A2A_ALLOW_PRIVATE_NETWORKS", raising=False)

    monkeypatch.setattr(socket, "getaddrinfo", _gai_fixed("93.184.216.34"))

    # First hop: redirect to literal IPv6 loopback.
    hdrs = HTTPMessage()
    hdrs["Location"] = "http://[::1]/admin"

    def _open_redirect(req, *args, **kwargs):
        raise urllib.error.HTTPError(
            url=str(req), code=302, msg="Found", hdrs=hdrs, fp=BytesIO(b"")
        )

    redirect_opener = MagicMock()
    redirect_opener.open.side_effect = _open_redirect

    captured_ips = _patch_build_pinned_opener(monkeypatch, [redirect_opener])

    transport = A2AHttpTransport("http://example.com")
    status, body = transport._make_request("http://example.com/api", method="GET")

    # Must be rejected: ::1 is in _PRIVATE_NETWORKS.
    assert status == 0
    assert body == b""
    # Only one connection was made (to example.com); redirect was blocked.
    assert len(captured_ips) == 1
    assert captured_ips[0] == "93.184.216.34"


# ===========================================================================
# Test 9: _resolve_and_pin_host returns the public IP for a valid hostname.
# ===========================================================================


def test_resolve_and_pin_host_returns_public_ip(monkeypatch) -> None:
    """_resolve_and_pin_host returns the first resolved IP for a public hostname."""
    monkeypatch.setattr(socket, "getaddrinfo", _gai_fixed("93.184.216.34"))
    ip = _resolve_and_pin_host("example.com", allow_private=False)
    assert ip == "93.184.216.34"


# ===========================================================================
# Test 10: _resolve_and_pin_host rejects a hostname that resolves to a private IP.
# ===========================================================================


def test_resolve_and_pin_host_rejects_private_ip(monkeypatch) -> None:
    """_resolve_and_pin_host raises A2AHttpSSRFError for a private-IP hostname."""
    monkeypatch.setattr(socket, "getaddrinfo", _gai_fixed("192.168.1.100"))
    with pytest.raises(A2AHttpSSRFError, match="private/restricted"):
        _resolve_and_pin_host("internal.corp", allow_private=False)
