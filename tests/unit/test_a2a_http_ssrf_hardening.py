"""SSRF-hardening tests for A2AHttpTransport / _validate_url.

All 13 test cases exercise the URL allow-list validation logic introduced in
HIGH-SEC-01.  No real network connections are made — DNS is monkeypatched
where needed, and urllib.request.urlopen is monkeypatched for the redirect
test.
"""
from __future__ import annotations

import socket
import urllib.error
import urllib.request
from http.client import HTTPMessage
from io import BytesIO
from unittest.mock import MagicMock, patch

import pytest

from autodev.adapters.a2a.transports.http import (
    A2AHttpSSRFError,
    A2AHttpTransport,
    _validate_url,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fake_getaddrinfo(ip: str):
    """Return a monkeypatch value for socket.getaddrinfo that yields *ip*."""

    def _gai(host, port, *args, **kwargs):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, 0))]

    return _gai


# ---------------------------------------------------------------------------
# 1. Reject file:// scheme
# ---------------------------------------------------------------------------


def test_reject_file_scheme() -> None:
    with pytest.raises(A2AHttpSSRFError, match="file"):
        _validate_url("file:///etc/passwd")


# ---------------------------------------------------------------------------
# 2. Reject ftp:// scheme
# ---------------------------------------------------------------------------


def test_reject_ftp_scheme() -> None:
    with pytest.raises(A2AHttpSSRFError, match="ftp"):
        _validate_url("ftp://example.com/pub/file.txt")


# ---------------------------------------------------------------------------
# 3. Reject http://127.0.0.1 (loopback IPv4 literal)
# ---------------------------------------------------------------------------


def test_reject_loopback_ipv4_literal() -> None:
    with pytest.raises(A2AHttpSSRFError, match="private/restricted"):
        _validate_url("http://127.0.0.1:8080/")


# ---------------------------------------------------------------------------
# 4. Reject AWS metadata endpoint 169.254.169.254
# ---------------------------------------------------------------------------


def test_reject_aws_metadata_ip() -> None:
    with pytest.raises(A2AHttpSSRFError, match="private/restricted"):
        _validate_url("http://169.254.169.254/latest/meta-data/")


# ---------------------------------------------------------------------------
# 5. Reject http://localhost (resolves to 127.0.0.1 or ::1)
# ---------------------------------------------------------------------------


def test_reject_localhost_hostname(monkeypatch) -> None:
    monkeypatch.setattr(socket, "getaddrinfo", _fake_getaddrinfo("127.0.0.1"))
    with pytest.raises(A2AHttpSSRFError, match="private/restricted"):
        _validate_url("http://localhost/")


# ---------------------------------------------------------------------------
# 6. Reject http://0.0.0.0 (unspecified)
# ---------------------------------------------------------------------------


def test_reject_unspecified_ipv4() -> None:
    with pytest.raises(A2AHttpSSRFError, match="private/restricted"):
        _validate_url("http://0.0.0.0/")


# ---------------------------------------------------------------------------
# 7. Reject http://10.0.0.1 (RFC-1918 class A)
# ---------------------------------------------------------------------------


def test_reject_rfc1918_class_a() -> None:
    with pytest.raises(A2AHttpSSRFError, match="private/restricted"):
        _validate_url("http://10.0.0.1/")


# ---------------------------------------------------------------------------
# 8. Reject http://192.168.1.1 (RFC-1918 class C)
# ---------------------------------------------------------------------------


def test_reject_rfc1918_class_c() -> None:
    with pytest.raises(A2AHttpSSRFError, match="private/restricted"):
        _validate_url("http://192.168.1.1/")


# ---------------------------------------------------------------------------
# 9. Reject http://[::1] (loopback IPv6 literal)
# ---------------------------------------------------------------------------


def test_reject_loopback_ipv6_literal() -> None:
    with pytest.raises(A2AHttpSSRFError, match="private/restricted"):
        _validate_url("http://[::1]/")


# ---------------------------------------------------------------------------
# 10. Reject DNS name that resolves to loopback (monkeypatched DNS)
# ---------------------------------------------------------------------------


def test_reject_dns_resolves_to_loopback(monkeypatch) -> None:
    monkeypatch.setattr(socket, "getaddrinfo", _fake_getaddrinfo("127.0.0.1"))
    with pytest.raises(A2AHttpSSRFError, match="private/restricted"):
        _validate_url("http://internal.corp.example.com/api")


# ---------------------------------------------------------------------------
# 11. Allow http://example.com when DNS returns a public IP
# ---------------------------------------------------------------------------


def test_allow_public_hostname(monkeypatch) -> None:
    # 93.184.216.34 is the real example.com address — definitely public.
    monkeypatch.setattr(socket, "getaddrinfo", _fake_getaddrinfo("93.184.216.34"))
    # Should not raise.
    _validate_url("http://example.com/api/v1")


# ---------------------------------------------------------------------------
# 12. allow_private=True bypasses all address-range checks
# ---------------------------------------------------------------------------


def test_allow_private_flag_bypasses_checks() -> None:
    # These would all raise without allow_private=True.
    _validate_url("http://127.0.0.1:9999/", allow_private=True)
    _validate_url("http://192.168.0.1/", allow_private=True)
    _validate_url("http://10.0.0.1/", allow_private=True)
    _validate_url("http://169.254.169.254/", allow_private=True)


# ---------------------------------------------------------------------------
# 13. Redirect from public to private address must be rejected
# ---------------------------------------------------------------------------


def test_redirect_to_private_is_rejected(monkeypatch) -> None:
    """A 302 whose Location points to a private address must be blocked.

    Strategy: monkeypatch socket.getaddrinfo so that:
      - the initial public URL resolves to a public IP (no SSRF error)
      - after redirect, the Location points to 169.254.169.254 directly
        (literal IP, no DNS needed) — which is in the private range.

    We also monkeypatch urllib.request.OpenerDirector.open to return a fake
    302 response with Location: http://169.254.169.254/secret so we never
    touch the network.
    """
    # Ensure the global test-suite env-var bypass is NOT active for this test,
    # so SSRF protection is enforced even in the conftest environment.
    monkeypatch.delenv("AUTODEV_A2A_ALLOW_PRIVATE_NETWORKS", raising=False)

    # Always resolve to a public IP for DNS lookups (the initial URL).
    monkeypatch.setattr(socket, "getaddrinfo", _fake_getaddrinfo("93.184.216.34"))

    # Build a fake 302 HTTPError that _NoRedirectHandler will surface.
    fake_headers = HTTPMessage()
    fake_headers["Location"] = "http://169.254.169.254/secret"
    redirect_exc = urllib.error.HTTPError(
        url="http://example.com/tasks/send",
        code=302,
        msg="Found",
        hdrs=fake_headers,
        fp=BytesIO(b""),
    )

    original_open = urllib.request.OpenerDirector.open

    call_count = {"n": 0}

    def _patched_open(self, req, *args, **kwargs):
        call_count["n"] += 1
        # First call → simulate a 302 redirect to the metadata endpoint.
        if call_count["n"] == 1:
            raise redirect_exc
        # Should never reach here — SSRF guard should block the second hop.
        return original_open(self, req, *args, **kwargs)  # pragma: no cover

    monkeypatch.setattr(urllib.request.OpenerDirector, "open", _patched_open)

    transport = A2AHttpTransport("http://example.com")
    # _make_request must return (0, b'') — blocked, not an exception.
    status, body = transport._make_request("http://example.com/tasks/send", method="POST")
    assert status == 0
    assert body == b""
    # The redirect hop to 169.254.169.254 must have been attempted to validate.
    assert call_count["n"] == 1  # Only one actual network call (the redirect source).
