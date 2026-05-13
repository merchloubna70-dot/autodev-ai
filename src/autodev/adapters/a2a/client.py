"""A2AClient — thin facade that dispatches tasks to the correct transport."""
from __future__ import annotations

import os

from ...schemas import AgentCard, A2ATask
from .transports.base import BaseA2ATransport
from .transports.http import A2AHttpTransport
from .transports.local_shell import LocalShellTransport
from .transports.mock import MockTransport


_TRANSPORT_REGISTRY: dict[str, type[BaseA2ATransport]] = {
    "local-shell": LocalShellTransport,
    "mock": MockTransport,
}


class A2AClient:
    """Dispatches A2A tasks to the appropriate transport based on card.transport.

    Caches transport instances to avoid repeated instantiation.
    For ``a2a-http`` transport, instances are cached by endpoint URL.
    """

    def __init__(self) -> None:
        self._transport_cache: dict[str, BaseA2ATransport] = {}

    def _get_transport(self, transport_name: str, card: AgentCard | None = None) -> BaseA2ATransport:
        if transport_name == "a2a-http":
            endpoint = (card.endpoint or "") if card else ""
            cache_key = f"a2a-http:{endpoint}"
            if cache_key not in self._transport_cache:
                self._transport_cache[cache_key] = A2AHttpTransport(
                    endpoint=endpoint,
                    auth_token=os.environ.get("AUTODEV_A2A_TOKEN"),
                )
            return self._transport_cache[cache_key]

        if transport_name not in self._transport_cache:
            transport_cls = _TRANSPORT_REGISTRY.get(transport_name)
            if transport_cls is None:
                # Unknown transport → fall back to mock (fail-safe)
                transport_cls = MockTransport
            self._transport_cache[transport_name] = transport_cls()
        return self._transport_cache[transport_name]

    def send(self, card: AgentCard, task: A2ATask) -> A2ATask:
        """Send *task* to the agent described by *card*.

        Returns the completed (or FAILED) task. Never raises.
        """
        transport = self._get_transport(card.transport, card)
        return transport.send_task(card, task)
