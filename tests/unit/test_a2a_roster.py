"""Tests for AgentRoster."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest
from autodev.schemas import AgentCard
from autodev.adapters.a2a.roster import AgentRoster


def _make_card(name: str, skills: list[str], capabilities: list[str] | None = None) -> AgentCard:
    return AgentCard(
        name=name,
        skills=skills,
        capabilities=capabilities or [],
        transport="local-shell",
        model_hint="sonnet",
    )


def test_register_and_all():
    roster = AgentRoster()
    card = _make_card("alpha", ["review", "lint"])
    roster.register(card)
    all_cards = roster.all()
    assert len(all_cards) == 1
    assert all_cards[0].name == "alpha"


def test_register_deduplicates_by_name():
    roster = AgentRoster()
    card1 = _make_card("alpha", ["review"])
    card2 = _make_card("alpha", ["security"])
    roster.register(card1)
    roster.register(card2)
    all_cards = roster.all()
    assert len(all_cards) == 1
    assert all_cards[0].skills == ["security"]  # latest wins


def test_unregister_existing():
    roster = AgentRoster()
    roster.register(_make_card("alpha", ["review"]))
    result = roster.unregister("alpha")
    assert result is True
    assert roster.all() == []


def test_unregister_nonexistent():
    roster = AgentRoster()
    result = roster.unregister("nobody")
    assert result is False


def test_find_by_skill_exact():
    roster = AgentRoster()
    roster.register(_make_card("sec", ["sast", "owasp"]))
    roster.register(_make_card("arch", ["design"]))
    found = roster.find_by_skill("sast")
    assert len(found) == 1
    assert found[0].name == "sec"


def test_find_by_skill_substring():
    roster = AgentRoster()
    roster.register(_make_card("perf", ["performance-profiling"]))
    found = roster.find_by_skill("perf")
    assert len(found) == 1


def test_find_by_skill_in_capabilities():
    roster = AgentRoster()
    card = AgentCard(
        name="ux",
        skills=[],
        capabilities=["api-design", "usability"],
        transport="mock",
    )
    roster.register(card)
    found = roster.find_by_skill("api-design")
    assert len(found) == 1
    assert found[0].name == "ux"


def test_find_by_skill_no_match():
    roster = AgentRoster()
    roster.register(_make_card("alpha", ["review"]))
    assert roster.find_by_skill("nonexistent") == []


def test_find_by_skills_min_match_1():
    roster = AgentRoster()
    roster.register(_make_card("sec", ["sast", "owasp"]))
    roster.register(_make_card("arch", ["design", "planning"]))
    found = roster.find_by_skills(["sast", "design"], min_match=1)
    assert len(found) == 2


def test_find_by_skills_min_match_2():
    roster = AgentRoster()
    roster.register(_make_card("multi", ["sast", "design"]))
    roster.register(_make_card("single", ["sast"]))
    found = roster.find_by_skills(["sast", "design"], min_match=2)
    assert len(found) == 1
    assert found[0].name == "multi"


def test_find_by_skills_empty_list():
    roster = AgentRoster()
    roster.register(_make_card("alpha", ["review"]))
    # 0 skills to match, min_match=1 → nothing matches
    found = roster.find_by_skills([], min_match=1)
    assert found == []


def test_save_and_load(tmp_path):
    roster = AgentRoster()
    roster.register(_make_card("alpha", ["review"]))
    roster.register(_make_card("beta", ["security"]))
    path = tmp_path / "roster.json"
    roster.save(path)
    assert path.exists()
    loaded = AgentRoster()
    loaded.load(path)
    names = {c.name for c in loaded.all()}
    assert names == {"alpha", "beta"}


def test_default_roster_has_at_least_4_cards():
    roster = AgentRoster.default()
    cards = roster.all()
    assert len(cards) >= 4


def test_default_roster_has_expected_specialists():
    roster = AgentRoster.default()
    names = {c.name for c in roster.all()}
    for expected in ("architect", "security", "performance", "style", "ux"):
        assert expected in names, f"Expected {expected!r} in default roster"


def test_default_roster_architect_uses_opus():
    roster = AgentRoster.default()
    architect = next(c for c in roster.all() if c.name == "architect")
    assert architect.model_hint == "opus"


def test_default_roster_style_uses_haiku():
    roster = AgentRoster.default()
    style = next(c for c in roster.all() if c.name == "style")
    assert style.model_hint == "haiku"


def test_default_roster_all_have_system_prompts():
    roster = AgentRoster.default()
    for card in roster.all():
        assert card.system_prompt, f"Card {card.name!r} missing system_prompt"


def test_default_roster_find_by_skill_security():
    roster = AgentRoster.default()
    found = roster.find_by_skill("security")
    assert len(found) >= 1
    assert any(c.name == "security" for c in found)
