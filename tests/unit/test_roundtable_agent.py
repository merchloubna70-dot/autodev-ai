"""Unit tests for RoundtableAgent (BMAD party-mode via A2A)."""
from __future__ import annotations

import os
import uuid

import pytest

# If A2A-1 hasn't committed yet, skip the whole module gracefully
roster_mod = pytest.importorskip("autodev.adapters.a2a.roster", reason="A2A-1 not yet committed")
AgentRoster = roster_mod.AgentRoster

from autodev.schemas import (
    A2AConversation,
    A2AMessage,
    A2APart,
    A2ATask,
    A2ATaskStatus,
    AgentCard,
)
from autodev.agents.roundtable import RoundtableAgent, _make_text_message, _FallbackMockClient


# ---------------------------------------------------------------------------
# Fixture: mock client that echoes back a deterministic message per card
# ---------------------------------------------------------------------------

class _EchoClient:
    """Returns a completed task with a single agent message containing card name."""

    def send(self, card: AgentCard, task: A2ATask) -> A2ATask:
        t = task.model_copy(deep=True)
        text = (
            f"[MOCK-{card.name}] Echo response from {card.name}. "
            f"[SEVERITY:MINOR] Minor issue found. Proceed."
        )
        t.history.append(_make_text_message("agent", text, task_id=t.id))
        t.status = A2ATaskStatus.COMPLETED
        return t


@pytest.fixture
def echo_client():
    return _EchoClient()


@pytest.fixture
def default_roster():
    return AgentRoster.default()


@pytest.fixture
def roundtable(echo_client, default_roster):
    return RoundtableAgent(roster=default_roster, client=echo_client)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_discuss_returns_conversation_with_n_participants(roundtable):
    """discuss() returns an A2AConversation with participating cards."""
    conv = roundtable.discuss(
        topic="Review this change",
        needed_skills=["security", "performance", "style"],
        min_participants=2,
        max_participants=4,
    )
    assert isinstance(conv, A2AConversation)
    assert len(conv.participating_cards) >= 2
    assert len(conv.participating_cards) <= 4
    # Should have at least user message + agent messages
    assert len(conv.messages) >= 2


def test_each_card_received_same_input_message(roundtable):
    """All participating agents received the identical user prompt."""
    topic = "Check security of auth module"
    context = "JWT tokens used throughout"

    conv = roundtable.discuss(
        topic=topic,
        context=context,
        needed_skills=["security", "style"],
        min_participants=2,
        max_participants=3,
    )

    # The first message in conversation is the user prompt
    user_msgs = [m for m in conv.messages if m.role == "user"]
    assert len(user_msgs) == 1
    user_text = " ".join(p.text or "" for p in user_msgs[0].parts)
    assert topic in user_text
    assert context in user_text


def test_synthesize_produces_nonempty_agent_message(roundtable):
    """synthesize() returns a non-empty agent message."""
    conv = roundtable.discuss(
        topic="Analyze performance bottlenecks",
        needed_skills=["performance", "style"],
        min_participants=2,
        max_participants=3,
    )
    synth = roundtable.synthesize(conv)
    assert isinstance(synth, A2AMessage)
    assert synth.role == "agent"
    text = " ".join(p.text or "" for p in synth.parts)
    assert len(text) > 0


def test_force_mock_deterministic(monkeypatch):
    """With FACTORY_FORCE_MOCK=1 and same inputs, results are deterministic (no exception)."""
    monkeypatch.setenv("FACTORY_FORCE_MOCK", "1")
    roster = AgentRoster.default()
    # Use FallbackMockClient explicitly to avoid env-sensitive import path
    client = _FallbackMockClient()
    rt = RoundtableAgent(roster=roster, client=client)

    conv1 = rt.discuss(
        topic="Same topic",
        needed_skills=["security"],
        min_participants=1,
        max_participants=2,
    )
    conv2 = rt.discuss(
        topic="Same topic",
        needed_skills=["security"],
        min_participants=1,
        max_participants=2,
    )
    # Both should succeed and have agent messages
    assert isinstance(conv1, A2AConversation)
    assert isinstance(conv2, A2AConversation)
    agent_msgs_1 = [m for m in conv1.messages if m.role == "agent"]
    agent_msgs_2 = [m for m in conv2.messages if m.role == "agent"]
    assert len(agent_msgs_1) == len(agent_msgs_2)


def test_fewer_cards_than_min_participants_no_exception():
    """When fewer cards match needed_skills than min_participants, return whatever we have."""
    roster = AgentRoster()  # Empty roster
    client = _FallbackMockClient()
    rt = RoundtableAgent(roster=roster, client=client)

    # Should return empty conversation, not raise
    conv = rt.discuss(
        topic="Find nothing",
        needed_skills=["nonexistent_skill_xyz"],
        min_participants=3,
        max_participants=4,
    )
    assert isinstance(conv, A2AConversation)
    # Either empty or has whatever was found
    assert len(conv.participating_cards) <= 4


def test_max_participants_caps_selection(echo_client):
    """max_participants caps the number of cards selected."""
    # Build a roster with many cards
    roster = AgentRoster.default()
    # Add extra cards
    for i in range(5):
        roster.register(AgentCard(
            name=f"extra-agent-{i}",
            skills=["security", "performance", "style"],
            transport="local-shell",
        ))

    rt = RoundtableAgent(roster=roster, client=echo_client)
    conv = rt.discuss(
        topic="Max cap test",
        needed_skills=["security", "performance", "style"],
        min_participants=1,
        max_participants=2,
    )
    assert len(conv.participating_cards) <= 2
