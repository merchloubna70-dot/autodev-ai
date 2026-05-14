"""TailnetTransport — A2A transport that discovers and contacts peers over a Tailscale tailnet.

Instead of binding to 0.0.0.0 or a public IP, this transport:
1. Discovers the local machine's tailnet IPv4 address via ``tailscale ip -4``.
2. Discovers peer A2A endpoints via ``tailscale status --json``.
3. Delegates actual HTTP communication to A2AHttpTransport (using the tailnet IP
   as the endpoint base), which already has SSRF protection, redirect handling,
   and error normalization.

If the ``tailscale`` binary is absent or the machine is not authenticated to a
tailnet, a :class:`TailnetUnavailable` error is raised immediately with a clear
message explaining what the user needs to do.

Discovery
---------
``tailscale status --json`` returns a JSON object with a ``Peer`` map keyed by
node public key.  Each peer entry has:

  ``TailscaleIPs``   list[str]  — tailnet IPs (both IPv4 and IPv6)
  ``HostName``       str        — machine hostname
  ``Online``         bool       — whether the peer is reachable right now
  ``DNSName``        str        — FQDN in the tailnet (e.g. ``host.ts.net.``)

``tailscale ip -4`` returns the local machine's tailnet IPv4 address (one line).

Port convention
---------------
By default the A2A server binds on port 8765 (``DEFAULT_A2A_PORT``).  Callers
can override via the ``a2a_port`` constructor parameter.  This matches the
default used by ``a2a-serve`` in this project.

Port conflict handling
----------------------
``bind_address()`` calls ``socket.bind`` in a probe-only socket to verify the
port is free.  If the port is already in use a ``PortConflict`` exception is
raised describing the conflict.
"""
from __future__ import annotations

import json
import shutil
import socket
import subprocess
from datetime import datetime, timezone
from typing import Any

from ....schemas import (
    A2APart,
    A2ATask,
    A2ATaskStatus,
    AgentCard,
)
from .base import BaseA2ATransport
from .http import A2AHttpTransport

# ---------------------------------------------------------------------------
# Public constants
# ---------------------------------------------------------------------------

DEFAULT_A2A_PORT: int = 8765
"""Default port on which A2A servers listen inside the tailnet."""


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class TailnetUnavailable(RuntimeError):
    """Raised when the Tailscale binary is absent or the machine is not authenticated.

    Resolution steps are embedded in the error message so the user knows exactly
    what to do without consulting external docs.
    """


class PortConflict(OSError):
    """Raised when the requested tailnet bind port is already in use."""


# ---------------------------------------------------------------------------
# Low-level helpers (thin wrappers around subprocess calls)
# ---------------------------------------------------------------------------


def _require_tailscale() -> str:
    """Return the absolute path to the ``tailscale`` binary or raise :class:`TailnetUnavailable`."""
    path = shutil.which("tailscale")
    if path is None:
        raise TailnetUnavailable(
            "The 'tailscale' binary was not found on PATH.\n"
            "To use TailnetTransport you must:\n"
            "  1. Install Tailscale: https://tailscale.com/download\n"
            "  2. Authenticate: run 'tailscale up' and log in.\n"
            "Once authenticated, this machine will receive a tailnet IP and peer "
            "discovery will work automatically."
        )
    return path


def _run_tailscale(args: list[str], timeout: float = 10.0) -> str:
    """Run ``tailscale <args>`` and return stdout as a stripped string.

    Raises :class:`TailnetUnavailable` if the binary is absent, the process
    fails, or the output is empty.
    """
    binary = _require_tailscale()
    try:
        result = subprocess.run(
            [binary, *args],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError as exc:
        raise TailnetUnavailable(
            f"'tailscale' binary disappeared during execution: {exc}\n"
            "Please ensure Tailscale is properly installed."
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise TailnetUnavailable(
            f"'tailscale {' '.join(args)}' timed out after {timeout}s.\n"
            "Tailscale may be unresponsive — try 'tailscale status' in a terminal."
        ) from exc

    if result.returncode != 0:
        stderr_hint = result.stderr.strip()
        raise TailnetUnavailable(
            f"'tailscale {' '.join(args)}' exited with code {result.returncode}.\n"
            f"Stderr: {stderr_hint or '(empty)'}\n"
            "Ensure Tailscale is running and authenticated: run 'tailscale up'."
        )

    output = result.stdout.strip()
    if not output:
        raise TailnetUnavailable(
            f"'tailscale {' '.join(args)}' produced no output.\n"
            "Tailscale may not be authenticated — run 'tailscale up' to log in."
        )
    return output


def get_local_tailnet_ip() -> str:
    """Return this machine's tailnet IPv4 address (from ``tailscale ip -4``).

    Raises :class:`TailnetUnavailable` if tailscale is absent or unauthenticated.
    """
    return _run_tailscale(["ip", "-4"])


def list_online_peers(a2a_port: int = DEFAULT_A2A_PORT) -> list[dict[str, Any]]:
    """Return a list of peer descriptors for all *online* tailnet peers.

    Each descriptor is a ``dict`` with keys:

    ``hostname``   str  — machine hostname
    ``tailnet_ip`` str  — first tailnet IPv4 address
    ``dns_name``   str  — fully-qualified tailnet DNS name (trailing dot stripped)
    ``endpoint``   str  — inferred A2A base URL, e.g. ``http://100.64.0.2:8765``
    ``online``     bool — always ``True`` (offline peers are filtered out)

    The raw ``tailscale status --json`` peer map is consulted; peers with no
    IPv4 tailnet address or with ``Online=false`` are skipped.

    Raises :class:`TailnetUnavailable` if tailscale is absent or unauthenticated.
    """
    raw_json = _run_tailscale(["status", "--json"])
    try:
        data: dict[str, Any] = json.loads(raw_json)
    except json.JSONDecodeError as exc:
        raise TailnetUnavailable(
            f"Failed to parse 'tailscale status --json' output: {exc}"
        ) from exc

    peers_raw: dict[str, Any] = data.get("Peer", {})
    peers: list[dict[str, Any]] = []

    for _key, peer in peers_raw.items():
        if not peer.get("Online", False):
            continue
        ips: list[str] = peer.get("TailscaleIPs", [])
        ipv4s = [ip for ip in ips if "." in ip]  # crude but correct: v4 has dots
        if not ipv4s:
            continue

        tailnet_ip = ipv4s[0]
        hostname: str = peer.get("HostName", "unknown")
        dns_name: str = peer.get("DNSName", "").rstrip(".")

        peers.append(
            {
                "hostname": hostname,
                "tailnet_ip": tailnet_ip,
                "dns_name": dns_name,
                "endpoint": f"http://{tailnet_ip}:{a2a_port}",
                "online": True,
            }
        )

    return peers


# ---------------------------------------------------------------------------
# Port probe helper
# ---------------------------------------------------------------------------


def _probe_port_free(ip: str, port: int) -> None:
    """Raise :class:`PortConflict` if *port* is already in use on *ip*.

    Uses a short-lived TCP socket with SO_REUSEADDR to simulate what the server
    would do when binding.  The socket is closed immediately after the probe.
    """
    probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        probe.bind((ip, port))
    except OSError as exc:
        raise PortConflict(
            f"Port {port} is already in use on tailnet IP {ip}.\n"
            f"Pick a different port via the 'a2a_port' constructor parameter.\n"
            f"OS error: {exc}"
        ) from exc
    finally:
        probe.close()


# ---------------------------------------------------------------------------
# TailnetTransport
# ---------------------------------------------------------------------------


class TailnetTransport(BaseA2ATransport):
    """A2A transport that routes traffic over the local Tailscale tailnet.

    Discovery (``discover_peers()``) invokes ``tailscale status --json`` to
    enumerate online peers and exposes their inferred A2A endpoints.

    ``send_task()`` delegates to the HTTP transport (private-networks mode
    enabled, because tailnet IPs are RFC-1918/CGNAT ranges) so all existing
    HTTP error-handling, redirect tracking, and poll logic is reused.

    Parameters
    ----------
    a2a_port:
        TCP port that A2A servers in the tailnet listen on.
        Default: :data:`DEFAULT_A2A_PORT` (8765).
    auth_token:
        Optional bearer token forwarded on every outgoing request.
    timeout_sec:
        HTTP socket timeout for task submissions.
    bind_check:
        When ``True`` (default), :meth:`bind_address` probes that the port is
        free before returning the bind address.  Set to ``False`` in unit tests
        that do not actually open sockets.
    """

    def __init__(
        self,
        *,
        a2a_port: int = DEFAULT_A2A_PORT,
        auth_token: str | None = None,
        timeout_sec: int = 120,
        bind_check: bool = True,
    ) -> None:
        self._a2a_port = a2a_port
        self._auth_token = auth_token
        self._timeout_sec = timeout_sec
        self._bind_check = bind_check

    # ------------------------------------------------------------------
    # Discovery
    # ------------------------------------------------------------------

    def get_local_ip(self) -> str:
        """Return this machine's tailnet IPv4 address.

        Raises :class:`TailnetUnavailable` if tailscale is absent or not
        authenticated.
        """
        return get_local_tailnet_ip()

    def bind_address(self) -> tuple[str, int]:
        """Return ``(tailnet_ip, port)`` that A2A server should bind on.

        By binding to the tailnet IP (not ``0.0.0.0``) the server is only
        reachable from within the tailnet, not from the public internet.

        Raises
        ------
        TailnetUnavailable
            If tailscale is absent or not authenticated.
        PortConflict
            If the port is already in use on the tailnet IP.
        """
        ip = self.get_local_ip()
        if self._bind_check:
            _probe_port_free(ip, self._a2a_port)
        return ip, self._a2a_port

    def discover_peers(self) -> list[dict[str, Any]]:
        """Return descriptors for all online tailnet peers.

        See :func:`list_online_peers` for the descriptor schema.

        Raises :class:`TailnetUnavailable` if tailscale is absent or
        unauthenticated.
        """
        return list_online_peers(self._a2a_port)

    # ------------------------------------------------------------------
    # BaseA2ATransport interface
    # ------------------------------------------------------------------

    def send_task(self, card: AgentCard, task: A2ATask) -> A2ATask:
        """Send *task* to the agent described by *card* via the tailnet.

        The card's ``endpoint`` field must be set to the tailnet HTTP URL
        (e.g. ``http://100.64.0.2:8765``).  If it is absent, the task is
        marked FAILED immediately.

        Tailnet IPs are in RFC-1918 / CGNAT ranges, so this method creates an
        HTTP transport with ``allow_private_networks=True`` to bypass the SSRF
        blocklist that would otherwise reject them.  This is safe because
        tailnet traffic is encrypted end-to-end by WireGuard and all peers are
        authenticated by Tailscale's control plane.

        Never raises — all errors are expressed as ``task.status = FAILED``.
        """
        try:
            endpoint = card.endpoint
            if not endpoint:
                return _fail_task(
                    task,
                    f"[TAILNET:{card.name}] card.endpoint is not set. "
                    "Set it to the agent's tailnet URL, e.g. http://100.64.0.2:8765",
                )

            http_transport = A2AHttpTransport(
                endpoint=endpoint,
                auth_token=self._auth_token,
                timeout_sec=self._timeout_sec,
                allow_private_networks=True,  # tailnet IPs are private by design
            )
            return http_transport.send_task(card, task)

        except Exception as exc:  # pragma: no cover — defensive
            return _fail_task(
                task,
                f"[TAILNET:{card.name}] unexpected exception: {exc}",
            )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _fail_task(task: A2ATask, reason: str) -> A2ATask:
    """Mark task as FAILED with a text error artifact. Never raises."""
    task.artifacts.append(A2APart(kind="text", text=reason))
    task.status = A2ATaskStatus.FAILED
    task.updated_at = _now_iso()
    return task
