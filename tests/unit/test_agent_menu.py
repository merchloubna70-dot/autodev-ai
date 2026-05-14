"""BMAD-17: Tests for AgentMenu registry."""
from __future__ import annotations

import pytest

from autodev.agents._menu import AgentMenu, register_default_menu, list_for, list_all
from autodev.schemas import AgentMenuEntry, AgentMenuSnapshot


# Ensure all agent modules are imported so their module-level register calls fire
import autodev.agents.product_manager  # noqa: F401
import autodev.agents.requirement_analyst  # noqa: F401
import autodev.agents.prd_writer  # noqa: F401
import autodev.agents.system_architect  # noqa: F401
import autodev.agents.milestone_planner  # noqa: F401
import autodev.agents.task_decomposer  # noqa: F401
import autodev.agents.ux_designer  # noqa: F401
import autodev.agents.context_generator  # noqa: F401
import autodev.agents.document_project  # noqa: F401
import autodev.agents.investigator  # noqa: F401


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_register_and_list_for_known_agent() -> None:
    """Registering a menu should make it retrievable via list_for."""
    register_default_menu("_test_agent_menu", [
        AgentMenuEntry(code="X1", description="test entry one"),
        AgentMenuEntry(code="X2", description="test entry two"),
    ])
    entries = list_for("_test_agent_menu")
    assert len(entries) == 2
    assert entries[0].code == "X1"
    assert entries[1].code == "X2"


def test_list_for_unknown_agent_returns_empty() -> None:
    """list_for on an unregistered agent should return an empty list."""
    result = list_for("__nonexistent_agent_xyz__")
    assert result == []


def test_list_all_contains_all_registered() -> None:
    """list_all should include all registered agents."""
    register_default_menu("_test_all_probe", [
        AgentMenuEntry(code="A", description="probe"),
    ])
    all_menus = list_all()
    assert "_test_all_probe" in all_menus
    assert len(all_menus["_test_all_probe"]) == 1


def test_at_least_five_agents_registered_after_imports() -> None:
    """At least 5 core agents should have menus after importing their modules."""
    all_menus = list_all()
    registered_names = set(all_menus.keys())
    expected = {
        "product_manager", "requirement_analyst", "prd_writer",
        "system_architect", "milestone_planner",
    }
    assert expected <= registered_names, f"Missing: {expected - registered_names}"


def test_agent_menu_class_static_methods_consistent() -> None:
    """AgentMenu class methods should return the same data as module functions."""
    register_default_menu("_test_class_vs_func", [
        AgentMenuEntry(code="Z", description="class test"),
    ])
    assert AgentMenu.list_for("_test_class_vs_func") == list_for("_test_class_vs_func")
    assert AgentMenu.list_all() == list_all()


def test_snapshot_for_wraps_list() -> None:
    """snapshot_for should return an AgentMenuSnapshot with correct fields."""
    register_default_menu("_test_snapshot", [
        AgentMenuEntry(code="SN", description="snapshot test", skill="my_skill"),
    ])
    snap = AgentMenu.snapshot_for("_test_snapshot")
    assert isinstance(snap, AgentMenuSnapshot)
    assert snap.agent_name == "_test_snapshot"
    assert snap.menu[0].skill == "my_skill"


def test_register_replaces_existing_menu() -> None:
    """Registering twice for same agent should replace (last-writer wins)."""
    register_default_menu("_test_replace", [
        AgentMenuEntry(code="OLD", description="old"),
    ])
    register_default_menu("_test_replace", [
        AgentMenuEntry(code="NEW", description="new"),
    ])
    entries = list_for("_test_replace")
    assert len(entries) == 1
    assert entries[0].code == "NEW"
