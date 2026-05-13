"""Tests for ClarificationGate 3-round BMAD elicitation (BMAD-4)."""
from __future__ import annotations

import os

import pytest

from autodev.agents.clarification_gate import ClarificationGate
from autodev.schemas import (
    AcceptanceCriterion,
    ClarificationTranscript,
    FunctionalRequirement,
    PRD,
    ProductBrief,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _empty_prd() -> PRD:
    return PRD(product_name="TestProduct", overview="")


def _full_prd() -> PRD:
    return PRD(
        product_name="TestProduct",
        overview="A full PRD overview.",
        functional_requirements=[
            FunctionalRequirement(
                id="fr-001",
                title="User login",
                description="Users can log in with email and password.",
                priority="must-have",
            )
        ],
        acceptance_criteria=[
            AcceptanceCriterion(
                id="ac-001",
                description="Login succeeds with valid credentials.",
                verifiable_by="test",
            )
        ],
    )


def _brief_two_goals() -> ProductBrief:
    return ProductBrief(
        product_name="BriefProduct",
        goals=["Reduce onboarding time", "Improve retention rate"],
    )


# ---------------------------------------------------------------------------
# round1_diverge
# ---------------------------------------------------------------------------

class TestRound1Diverge:
    def test_empty_prd_returns_questions(self):
        gate = ClarificationGate()
        questions = gate.round1_diverge(prd=_empty_prd())
        assert isinstance(questions, list)
        assert 1 <= len(questions) <= 5
        assert all(isinstance(q, str) for q in questions)

    def test_no_input_returns_5_questions(self):
        gate = ClarificationGate()
        questions = gate.round1_diverge()
        assert len(questions) == 5

    def test_brief_returns_questions(self):
        gate = ClarificationGate()
        questions = gate.round1_diverge(brief=_brief_two_goals())
        assert len(questions) >= 1


# ---------------------------------------------------------------------------
# round2_converge
# ---------------------------------------------------------------------------

class TestRound2Converge:
    def test_must_have_keyword_detected(self):
        gate = ClarificationGate()
        answers = {"What are the goals?": "This is a critical and required feature."}
        decisions = gate.round2_converge(round1_answers=answers)
        assert decisions["What are the goals?"] == "must-have"

    def test_deferred_keyword_detected(self):
        gate = ClarificationGate()
        answers = {"Timeline?": "This can be done later in a future release."}
        decisions = gate.round2_converge(round1_answers=answers)
        assert decisions["Timeline?"] == "deferred"

    def test_default_nice_to_have(self):
        gate = ClarificationGate()
        answers = {"What UI style?": "Something clean and modern."}
        decisions = gate.round2_converge(round1_answers=answers)
        assert decisions["What UI style?"] == "nice-to-have"

    def test_empty_answers_returns_empty_dict(self):
        gate = ClarificationGate()
        decisions = gate.round2_converge(round1_answers={})
        assert decisions == {}


# ---------------------------------------------------------------------------
# round3_commit
# ---------------------------------------------------------------------------

class TestRound3Commit:
    def test_must_have_decisions_add_fr_and_ac(self):
        gate = ClarificationGate()
        prd = _full_prd()
        decisions = {"What are the API requirements?": "must-have"}
        updated = gate.round3_commit(prd=prd, decisions=decisions)

        assert len(updated.functional_requirements) == len(prd.functional_requirements) + 1
        assert len(updated.acceptance_criteria) == len(prd.acceptance_criteria) + 1

    def test_non_must_decisions_do_not_add_fr(self):
        gate = ClarificationGate()
        prd = _full_prd()
        orig_fr_count = len(prd.functional_requirements)
        decisions = {"Dark mode?": "deferred", "Mobile support?": "nice-to-have"}
        updated = gate.round3_commit(prd=prd, decisions=decisions)
        assert len(updated.functional_requirements) == orig_fr_count

    def test_original_prd_not_mutated(self):
        gate = ClarificationGate()
        prd = _full_prd()
        orig_fr_count = len(prd.functional_requirements)
        decisions = {"Feature X?": "must-have"}
        gate.round3_commit(prd=prd, decisions=decisions)
        # Original must be unchanged (deep copy)
        assert len(prd.functional_requirements) == orig_fr_count

    def test_commit_without_prd_creates_stub(self):
        gate = ClarificationGate()
        brief = _brief_two_goals()
        decisions = {"Core requirement?": "must-have"}
        updated = gate.round3_commit(brief=brief, decisions=decisions)
        assert isinstance(updated, PRD)
        assert len(updated.functional_requirements) == 1


# ---------------------------------------------------------------------------
# Mock determinism
# ---------------------------------------------------------------------------

class TestMockDeterminism:
    def test_round1_is_deterministic(self, monkeypatch):
        monkeypatch.setenv("FACTORY_FORCE_MOCK", "1")
        gate = ClarificationGate()
        q1 = gate.round1_diverge()
        q2 = gate.round1_diverge()
        assert q1 == q2

    def test_run_3round_produces_transcript(self):
        gate = ClarificationGate()
        answers = {"What is the primary goal of this project?": "This is a critical feature."}
        updated_prd, transcript = gate.run_3round(round1_answers=answers)
        assert isinstance(transcript, ClarificationTranscript)
        assert len(transcript.rounds) == 3
        assert isinstance(updated_prd, PRD)


# ---------------------------------------------------------------------------
# Backward compat — should_clarify unchanged
# ---------------------------------------------------------------------------

class TestShouldClarifyBackwardCompat:
    def test_full_prd_no_clarification(self):
        gate = ClarificationGate()
        result = gate.should_clarify(prd=_full_prd())
        assert result.needs_clarification is False

    def test_empty_prd_needs_clarification(self):
        gate = ClarificationGate()
        result = gate.should_clarify(prd=_empty_prd())
        assert result.needs_clarification is True
