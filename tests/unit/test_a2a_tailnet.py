"""Unit tests for TailnetTransport.

All subprocess calls are mocked — no real ``tailscale`` binary is invoked.
"""
from __future__ import annotations

import json
import socket
from unittest.mock import MagicMock, patch

import pytest

from autodev.adapters.a2a.transports import (
    DEFAULT_A2A_PORT,
    PortConflict,
    TailnetTransport,
    TailnetUnavailable,
)
from autodev.adapters.a2a.transports.tailnet import (
    _probe_port_free,
    get_local_tailnet_ip,
    list_online_peers,
)
from autodev.schemas import (
    A2AMessage,
    A2APart,
    A2ATask,
    A2ATaskStatus,
    AgentCard,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_TAILSCALE_STATUS_JSON = json.dumps(
    {
        "Version": "1.62.0",
        "TailscaleIPs": ["100.64.0.1"],
        "Self": {
            "HostName": "local-machine",
            "TailscaleIPs": ["100.64.0.1"],
            "Online": True,
            "DNSName": "local-machine.tail1234.ts.net.",
        },
        "Peer": {
            "key:peer1": {
                "HostName": "peer-alpha",
                "TailscaleIPs": ["100.64.0.2", "fd7a::1"],
                "Online": True,
                "DNSName": "peer-alpha.tail1234.ts.net.",
            },
            "key:peer2": {
                "HostName": "peer-beta",
                "TailscaleIPs": ["100.64.0.3"],
                "Online": False,  # offline — must be filtered out
                "DNSName": "peer-beta.tail1234.ts.net.",
            },
            "key:peer3": {
                "HostName": "peer-gamma",
                "TailscaleIPs": ["100.64.0.4"],
                "Online": True,
                "DNSName": "peer-gamma.tail1234.ts.net.",
            },
        },
    }
)


def _make_successful_run(stdout: str) -> MagicMock:
    """Build a mock CompletedProcess that looks like a successful subprocess.run result."""
    mock = MagicMock()
    mock.returncode = 0
    mock.stdout = stdout
    mock.stderr = ""
    return mock


def _make_task(prompt: str = "hello tailnet", task_id: str = "t-1", context_id: str = "ctx-1") -> A2ATask:
    msg = A2AMessage(
        message_id="m-1",
        role="user",
        parts=[A2APart(kind="text", text=prompt)],
        task_id=task_id,
        context_id=context_id,
    )
    return A2ATask(id=task_id, context_id=context_id, history=[msg])


def _make_card(name: str = "remote-agent", endpoint: str | None = "http://100.64.0.2:8765") -> AgentCard:
    return AgentCard(
        name=name,
        transport="tailnet",
        endpoint=endpoint,
    )


# ---------------------------------------------------------------------------
# Test 1: tailscale binary absent → TailnetUnavailable
# ---------------------------------------------------------------------------


class TestTailscaleBinaryAbsent:
    """When 'tailscale' is not on PATH, all operations must raise TailnetUnavailable."""

    def test_get_local_ip_raises_unavailable(self):
        with patch("shutil.which", return_value=None):
            with pytest.raises(TailnetUnavailable) as exc_info:
                get_local_tailnet_ip()
        msg = str(exc_info.value)
        assert "tailscale" in msg.lower()
        assert "install" in msg.lower() or "Install" in msg

    def test_list_peers_raises_unavailable(self):
        with patch("shutil.which", return_value=None):
            with pytest.raises(TailnetUnavailable):
                list_online_peers()

    def test_transport_bind_address_raises_unavailable(self):
        transport = TailnetTransport(bind_check=True)
        with patch("shutil.which", return_value=None):
            with pytest.raises(TailnetUnavailable) as exc_info:
                transport.bind_address()
        assert "tailscale" in str(exc_info.value).lower()

    def test_send_task_without_endpoint_returns_failed(self):
        """No tailscale call needed — endpoint is absent so we fail immediately."""
        transport = TailnetTransport(bind_check=False)
        card = _make_card(endpoint=None)
        task = _make_task()
        result = transport.send_task(card, task)
        assert result.status == A2ATaskStatus.FAILED
        assert any("endpoint" in (p.text or "").lower() for p in result.artifacts)

    def test_error_message_mentions_install_and_authenticate(self):
        with patch("shutil.which", return_value=None):
            with pytest.raises(TailnetUnavailable) as exc_info:
                get_local_tailnet_ip()
        msg = str(exc_info.value)
        # Must guide the user on both installation and authentication
        assert "install" in msg.lower() or "Install" in msg
        assert "tailscale up" in msg or "log in" in msg.lower() or "authenticated" in msg.lower()


# ---------------------------------------------------------------------------
# Test 2: peers parsed from mocked tailscale status --json
# ---------------------------------------------------------------------------


class TestPeerDiscovery:
    """list_online_peers() must correctly parse tailscale status --json output."""

    def _run_patch(self, args, **kwargs):
        """Side-effect for subprocess.run mock that dispatches on args."""
        if "status" in args:
            return _make_successful_run(_TAILSCALE_STATUS_JSON)
        return _make_successful_run("100.64.0.1")

    def test_only_online_peers_returned(self):
        with patch("shutil.which", return_value="/usr/bin/tailscale"):
            with patch("subprocess.run", side_effect=self._run_patch):
                peers = list_online_peers()
        # peer-beta is offline — must be absent
        hostnames = {p["hostname"] for p in peers}
        assert "peer-beta" not in hostnames

    def test_online_peers_count(self):
        with patch("shutil.which", return_value="/usr/bin/tailscale"):
            with patch("subprocess.run", side_effect=self._run_patch):
                peers = list_online_peers()
        assert len(peers) == 2  # peer-alpha + peer-gamma

    def test_peer_descriptor_fields(self):
        with patch("shutil.which", return_value="/usr/bin/tailscale"):
            with patch("subprocess.run", side_effect=self._run_patch):
                peers = list_online_peers()
        alpha = next(p for p in peers if p["hostname"] == "peer-alpha")
        assert alpha["tailnet_ip"] == "100.64.0.2"
        assert alpha["endpoint"] == f"http://100.64.0.2:{DEFAULT_A2A_PORT}"
        assert alpha["online"] is True
        assert alpha["dns_name"] == "peer-alpha.tail1234.ts.net"  # trailing dot stripped

    def test_custom_port_reflected_in_endpoint(self):
        with patch("shutil.which", return_value="/usr/bin/tailscale"):
            with patch("subprocess.run", side_effect=self._run_patch):
                peers = list_online_peers(a2a_port=9999)
        for p in peers:
            assert ":9999" in p["endpoint"]

    def test_ipv4_preferred_over_ipv6(self):
        """peer-alpha has both IPv4 and IPv6; IPv4 must be selected."""
        with patch("shutil.which", return_value="/usr/bin/tailscale"):
            with patch("subprocess.run", side_effect=self._run_patch):
                peers = list_online_peers()
        alpha = next(p for p in peers if p["hostname"] == "peer-alpha")
        # IPv6 address fd7a::1 must NOT appear in tailnet_ip
        assert ":" not in alpha["tailnet_ip"]


# ---------------------------------------------------------------------------
# Test 3: bind IP from mocked tailscale ip -4
# ---------------------------------------------------------------------------


class TestBindAddress:
    """bind_address() must return the IP from 'tailscale ip -4' plus the port."""

    def _run_ip_patch(self, args, **kwargs):
        if "ip" in args:
            return _make_successful_run("100.64.0.1\n")
        return _make_successful_run(_TAILSCALE_STATUS_JSON)

    def test_bind_address_returns_tailnet_ip(self):
        transport = TailnetTransport(a2a_port=8765, bind_check=False)
        with patch("shutil.which", return_value="/usr/bin/tailscale"):
            with patch("subprocess.run", side_effect=self._run_ip_patch):
                ip, port = transport.bind_address()
        assert ip == "100.64.0.1"
        assert port == 8765

    def test_bind_address_uses_custom_port(self):
        transport = TailnetTransport(a2a_port=9090, bind_check=False)
        with patch("shutil.which", return_value="/usr/bin/tailscale"):
            with patch("subprocess.run", side_effect=self._run_ip_patch):
                _ip, port = transport.bind_address()
        assert port == 9090

    def test_get_local_ip_strips_whitespace(self):
        """tailscale ip -4 may include a trailing newline — must be stripped."""
        with patch("shutil.which", return_value="/usr/bin/tailscale"):
            with patch("subprocess.run", return_value=_make_successful_run("100.64.0.1\n")):
                ip = get_local_tailnet_ip()
        assert ip == "100.64.0.1"
        assert "\n" not in ip

    def test_tailscale_ip_nonzero_exit_raises_unavailable(self):
        bad_run = MagicMock()
        bad_run.returncode = 1
        bad_run.stdout = ""
        bad_run.stderr = "not connected"
        with patch("shutil.which", return_value="/usr/bin/tailscale"):
            with patch("subprocess.run", return_value=bad_run):
                with pytest.raises(TailnetUnavailable) as exc_info:
                    get_local_tailnet_ip()
        assert "tailscale up" in str(exc_info.value) or "authenticated" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Test 4: port conflict handling
# ---------------------------------------------------------------------------


class TestPortConflict:
    """_probe_port_free() and bind_address() must raise PortConflict when port is taken."""

    def test_probe_free_port_succeeds(self):
        """A genuinely free port should not raise."""
        # Bind a socket to find a free port, then release it and immediately probe.
        with socket.socket() as finder:
            finder.bind(("127.0.0.1", 0))
            free_port = finder.getsockname()[1]
        # Port is now free — probe must not raise
        _probe_port_free("127.0.0.1", free_port)

    def test_probe_taken_port_raises_port_conflict(self):
        """Binding a port that is already in use must raise PortConflict."""
        holder = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            # Do NOT set SO_REUSEADDR — we WANT the second bind to fail
            holder.bind(("127.0.0.1", 0))
            holder.listen(1)  # listen() forces a real conflict cross-platform
            taken_port = holder.getsockname()[1]
            with pytest.raises(PortConflict) as exc_info:
                _probe_port_free("127.0.0.1", taken_port)
            msg = str(exc_info.value)
            assert str(taken_port) in msg
        finally:
            holder.close()

    def test_port_conflict_message_mentions_alternative(self):
        """PortConflict message must guide the user to pick a different port."""
        holder = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            holder.bind(("127.0.0.1", 0))
            holder.listen(1)
            taken_port = holder.getsockname()[1]
            with pytest.raises(PortConflict) as exc_info:
                _probe_port_free("127.0.0.1", taken_port)
            assert "port" in str(exc_info.value).lower()
        finally:
            holder.close()

    def test_bind_address_with_check_enabled_passes_when_free(self):
        """bind_check=True should succeed when the port is actually free."""
        transport = TailnetTransport(a2a_port=0, bind_check=True)
        # port=0 — OS assigns a free one; but _probe_port_free uses bind() with port=0
        # which succeeds trivially. Use a known-free port via finder socket instead.
        with socket.socket() as finder:
            finder.bind(("127.0.0.1", 0))
            free_port = finder.getsockname()[1]

        transport = TailnetTransport(a2a_port=free_port, bind_check=True)

        def _run_ip_patch(args, **kwargs):
            return _make_successful_run("127.0.0.1\n")

        with patch("shutil.which", return_value="/usr/bin/tailscale"):
            with patch("subprocess.run", side_effect=_run_ip_patch):
                ip, port = transport.bind_address()
        assert ip == "127.0.0.1"
        assert port == free_port


# ---------------------------------------------------------------------------
# Test 5: transport registers correctly in the transports package
# ---------------------------------------------------------------------------


class TestTransportRegistration:
    """TailnetTransport must be importable from the transports package __init__."""

    def test_tailnet_transport_importable_from_package(self):
        from autodev.adapters.a2a.transports import TailnetTransport as T
        assert T is TailnetTransport

    def test_tailnet_unavailable_importable_from_package(self):
        from autodev.adapters.a2a.transports import TailnetUnavailable as E
        assert E is TailnetUnavailable

    def test_port_conflict_importable_from_package(self):
        from autodev.adapters.a2a.transports import PortConflict as E
        assert E is PortConflict

    def test_default_a2a_port_importable_from_package(self):
        from autodev.adapters.a2a.transports import DEFAULT_A2A_PORT as P
        assert P == 8765

    def test_existing_transports_still_importable(self):
        """Registering TailnetTransport must not break existing transport imports."""
        from autodev.adapters.a2a.transports import (
            A2AHttpTransport,
            BaseA2ATransport,
            LocalShellTransport,
            MockTransport,
        )
        assert A2AHttpTransport is not None
        assert LocalShellTransport is not None
        assert MockTransport is not None
        assert BaseA2ATransport is not None

    def test_tailnet_transport_is_subclass_of_base(self):
        from autodev.adapters.a2a.transports import BaseA2ATransport
        assert issubclass(TailnetTransport, BaseA2ATransport)

    def test_tailnet_transport_implements_send_task(self):
        transport = TailnetTransport(bind_check=False)
        assert callable(transport.send_task)

    def test_send_task_missing_endpoint_fails_gracefully(self):
        """No tailscale binary needed — the failure is pre-flight (no endpoint)."""
        transport = TailnetTransport(bind_check=False)
        card = _make_card(name="orphan", endpoint=None)
        task = _make_task()
        result = transport.send_task(card, task)
        assert result.status == A2ATaskStatus.FAILED
        error_texts = [p.text or "" for p in result.artifacts]
        combined = " ".join(error_texts).lower()
        assert "endpoint" in combined


# ---------------------------------------------------------------------------
# Test 6: send_task delegates to HTTP transport with private networks enabled
# ---------------------------------------------------------------------------


class TestSendTaskDelegation:
    """send_task() must delegate to A2AHttpTransport with allow_private_networks=True."""

    def test_send_task_calls_http_transport(self):
        transport = TailnetTransport(bind_check=False)
        card = _make_card(endpoint="http://100.64.0.2:8765")
        task = _make_task()

        # Patch A2AHttpTransport to a mock that returns a completed task
        completed_task = _make_task()
        completed_task.status = A2ATaskStatus.COMPLETED
        completed_task.artifacts.append(A2APart(kind="text", text="remote result"))

        mock_http_transport = MagicMock()
        mock_http_transport.send_task.return_value = completed_task

        with patch(
            "autodev.adapters.a2a.transports.tailnet.A2AHttpTransport",
            return_value=mock_http_transport,
        ) as MockHTTPClass:
            result = transport.send_task(card, task)

        # Verify A2AHttpTransport was constructed with allow_private_networks=True
        call_kwargs = MockHTTPClass.call_args.kwargs
        assert call_kwargs.get("allow_private_networks") is True
        assert call_kwargs.get("endpoint") == "http://100.64.0.2:8765"

        # Verify send_task was called through
        mock_http_transport.send_task.assert_called_once_with(card, task)
        assert result.status == A2ATaskStatus.COMPLETED

    def test_send_task_passes_auth_token(self):
        transport = TailnetTransport(auth_token="secret-token", bind_check=False)
        card = _make_card(endpoint="http://100.64.0.2:8765")
        task = _make_task()

        mock_http_transport = MagicMock()
        mock_http_transport.send_task.return_value = _make_task()

        with patch(
            "autodev.adapters.a2a.transports.tailnet.A2AHttpTransport",
            return_value=mock_http_transport,
        ) as MockHTTPClass:
            transport.send_task(card, task)

        call_kwargs = MockHTTPClass.call_args.kwargs
        assert call_kwargs.get("auth_token") == "secret-token"

    def test_send_task_passes_timeout(self):
        transport = TailnetTransport(timeout_sec=30, bind_check=False)
        card = _make_card(endpoint="http://100.64.0.2:8765")
        task = _make_task()

        mock_http_transport = MagicMock()
        mock_http_transport.send_task.return_value = _make_task()

        with patch(
            "autodev.adapters.a2a.transports.tailnet.A2AHttpTransport",
            return_value=mock_http_transport,
        ) as MockHTTPClass:
            transport.send_task(card, task)

        call_kwargs = MockHTTPClass.call_args.kwargs
        assert call_kwargs.get("timeout_sec") == 30
