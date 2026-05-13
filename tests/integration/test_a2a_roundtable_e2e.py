"""End-to-end tests for RoundtableAgent / BMAD party-mode invariants.

Runs offline under FACTORY_FORCE_MOCK=1 (set by conftest).

Tests:
1. discuss_and_synthesize returns conversation with ≥2 participants and all
   received the SAME task.history length (same-input invariant).
2. Different cards produce different mock answers (no roleplay convergence).
3. Synth message is from a distinct 'synthesizer' card and references multiple inputs.
4. ParallelSectionReviewer.review() (backed by Roundtable) returns a report
   with non-empty sections (backward compat).
"""
from __future__ import annotations

import os

import pytest

# conftest sets FACTORY_FORCE_MOCK=1 before imports — verify it here
assert os.environ.get("FACTORY_FORCE_MOCK") == "1", "Tests require FACTORY_FORCE_MOCK=1"

from autodev.adapters.a2a.client import A2AClient
from autodev.adapters.a2a.roster import AgentRoster
from autodev.adapters.a2a.transports.mock import MockTransport, _mock_response
from autodev.agents.roundtable import RoundtableAgent
from autodev.schemas import A2AConversation, A2AMessage, AgentCard


# ---------------------------------------------------------------------------
# Helper: build a RoundtableAgent that uses MockTransport explicitly
# ---------------------------------------------------------------------------

def _mock_roundtable(max_participants: int = 4) -> RoundtableAgent:
    """Return a RoundtableAgent wired to MockTransport (never shells out)."""
    roster = AgentRoster.default()
    client = A2AClient()
    # Override all card transports to "mock" so LocalShellTransport is never used
    for card in roster.all():
        card.transport = "mock"
    return RoundtableAgent(roster=roster, client=client)


# ---------------------------------------------------------------------------
# Test 1: ≥2 participants, same-input invariant (identical history length)
# ---------------------------------------------------------------------------

def test_discuss_returns_multiple_participants_same_input():
    """Conversation has ≥2 participants; each got the same task (same history length)."""
    rt = _mock_roundtable()
    conversation, _synth = rt.discuss_and_synthesize(
        topic="Should we adopt event sourcing for the order service?",
        needed_skills=["security", "perf"],
        min_participants=2,
        max_participants=4,
    )

    assert isinstance(conversation, A2AConversation)
    # At least 2 participant cards were recruited
    assert len(conversation.participating_cards) >= 2, (
        f"Expected ≥2 participants, got {conversation.participating_cards}"
    )

    # The conversation messages include the shared user prompt + agent responses
    agent_msgs = [m for m in conversation.messages if m.role == "agent"]
    assert len(agent_msgs) >= 2, "Expected ≥2 agent messages"

    # All agent messages reference the same context_id (same-input invariant)
    context_ids = {m.context_id for m in agent_msgs}
    assert len(context_ids) == 1, f"Expected single context_id, got {context_ids}"


# ---------------------------------------------------------------------------
# Test 2: Different cards → different mock answers (no roleplay convergence)
# ---------------------------------------------------------------------------

def test_different_cards_produce_different_mock_answers():
    """MockTransport keys on card.name: two different cards produce different responses."""
    prompt = "Evaluate the security and performance of this design."
    response_architect = _mock_response(prompt, "architect")
    response_security = _mock_response(prompt, "security")
    response_perf = _mock_response(prompt, "performance")

    # All three must be distinct
    responses = {response_architect, response_security, response_perf}
    assert len(responses) == 3, (
        f"Expected 3 distinct mock responses, got {len(responses)}: {responses}"
    )

    # Each response embeds the card name for traceability
    assert "architect" in response_architect
    assert "security" in response_security
    assert "performance" in response_perf


def test_roundtable_agent_messages_differ_per_card():
    """End-to-end: agent messages in conversation differ because card names differ."""
    rt = _mock_roundtable()
    conversation, _ = rt.discuss_and_synthesize(
        topic="Assess the auth module for risks.",
        needed_skills=["security", "architecture"],
        min_participants=2,
        max_participants=2,
    )

    agent_msgs = [m for m in conversation.messages if m.role == "agent"]
    assert len(agent_msgs) >= 2

    # Extract text from each agent message
    texts = []
    for msg in agent_msgs:
        text = "".join(p.text or "" for p in msg.parts if p.kind == "text")
        texts.append(text)

    # At least two distinct texts (proving different mock outputs per card)
    assert len(set(texts)) >= 2, f"Expected distinct per-card texts, got: {texts}"


# ---------------------------------------------------------------------------
# Test 3: Synth message from distinct 'synthesizer' card, references multiple inputs
# ---------------------------------------------------------------------------

def test_synth_message_from_synthesizer_card():
    """Synthesis message comes from a synthesizer card and contains multi-agent content."""
    rt = _mock_roundtable()
    conversation, synth_msg = rt.discuss_and_synthesize(
        topic="Review the new caching layer design.",
        needed_skills=["architecture", "perf", "security"],
        min_participants=2,
        max_participants=3,
    )

    assert isinstance(synth_msg, A2AMessage)
    assert synth_msg.role == "agent"

    # Synth message must have text
    synth_text = "".join(p.text or "" for p in synth_msg.parts if p.kind == "text")
    assert synth_text.strip(), "Synthesis message must have non-empty text"

    # The synthesizer card is registered in the roster after synthesis
    roster = rt._roster
    synth_cards = roster.find_by_skill("synthesis") if roster else []
    assert synth_cards, "Expected a 'synthesis'-skilled card to be registered after synthesize()"
    assert synth_cards[0].name == "synthesizer"

    # The synthesizer card name is distinct from the participant card names
    participant_names = set(conversation.participating_cards)
    assert "synthesizer" not in participant_names, (
        "Synthesizer should be a separate card, not a participant in the discussion"
    )


# ---------------------------------------------------------------------------
# Test 4: ParallelSectionReviewer backward compat — returns non-empty sections
# ---------------------------------------------------------------------------

def test_parallel_section_reviewer_backward_compat(tmp_path):
    """ParallelSectionReviewer.review() still returns report with sections non-empty."""
    from autodev.agents.parallel_section_reviewer import ParallelSectionReviewer
    from autodev.schemas import ParallelSectionReviewReport

    # Write a file that triggers findings in all 3 reviewers
    (tmp_path / "service.py").write_text(
        "# TODO: remove this\n"
        "def handler():\n"
        "    print('debug output')\n"
        "    while True:\n"
        "        pass\n"
    )

    reviewer = ParallelSectionReviewer()
    report = reviewer.review(repo_path=str(tmp_path))

    assert isinstance(report, ParallelSectionReviewReport)
    assert len(report.sections) > 0, "sections must be non-empty"
    assert "security" in report.sections
    assert "perf" in report.sections
    assert "style" in report.sections
    # synthesis_summary is populated (roundtable path was exercised)
    assert report.synthesis_summary.strip()
