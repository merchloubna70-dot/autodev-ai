"""BMAD-17: AgentMenu registry — each agent can register a code→skill menu.

Usage (in any agent module):
    from ._menu import register_default_menu
    from ..schemas import AgentMenuEntry

    register_default_menu("product_manager", [
        AgentMenuEntry(code="CB", description="Create Brief", skill="product_manager"),
    ])
"""
from __future__ import annotations

from ..schemas import AgentMenuEntry, AgentMenuSnapshot

# ---------------------------------------------------------------------------
# Registry (module-level singleton)
# ---------------------------------------------------------------------------

_REGISTRY: dict[str, list[AgentMenuEntry]] = {}


def register_default_menu(agent_name: str, items: list[AgentMenuEntry]) -> None:
    """Register (or replace) the menu for *agent_name*.

    Safe to call at module import time; idempotent if called multiple times with
    the same agent_name (last writer wins).
    """
    _REGISTRY[agent_name] = list(items)


def list_for(agent_name: str) -> list[AgentMenuEntry]:
    """Return the menu entries for *agent_name*, or [] if not registered."""
    return list(_REGISTRY.get(agent_name, []))


def list_all() -> dict[str, list[AgentMenuEntry]]:
    """Return a snapshot of all registered menus."""
    return {k: list(v) for k, v in _REGISTRY.items()}


def snapshot_for(agent_name: str) -> AgentMenuSnapshot:
    return AgentMenuSnapshot(agent_name=agent_name, menu=list_for(agent_name))


# ---------------------------------------------------------------------------
# AgentMenu convenience class (wraps module-level functions)
# ---------------------------------------------------------------------------


class AgentMenu:
    """Thin class wrapper around the module-level registry for OO callers."""

    @staticmethod
    def register(agent_name: str, items: list[AgentMenuEntry]) -> None:
        register_default_menu(agent_name, items)

    @staticmethod
    def list_for(agent_name: str) -> list[AgentMenuEntry]:
        return list_for(agent_name)

    @staticmethod
    def list_all() -> dict[str, list[AgentMenuEntry]]:
        return list_all()

    @staticmethod
    def snapshot_for(agent_name: str) -> AgentMenuSnapshot:
        return snapshot_for(agent_name)
