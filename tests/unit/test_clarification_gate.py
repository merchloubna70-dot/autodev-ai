"""Unit tests for ClarificationGate (W5)."""
from __future__ import annotations

import os

import pytest

from autodev.agents.clarification_gate import ClarificationGate
from autodev.schemas import (
    AcceptanceCriterion,
    ClarificationDecision,
    FunctionalRequirement,
    PRD,
    ProductBrief,
)


@pytest.fixture(autouse=True)
def _force_mock(monkeypatch):
    """Ensure all tests run in mock/deterministic mode."""
    monkeypatch.setenv("FACTORY_FORCE_MOCK", "1")


class TestClarificationGateSparse:
    """Sparse inputs should request clarification."""

    def test_sparse_brief_zero_goals_needs_clarification(self):
        gate = ClarificationGate()
        brief = ProductBrief(product_name="X", goals=[])
        decision = gate.should_clarify(brief=brief)
        assert isinstance(decision, ClarificationDecision)
        assert decision.needs_clarification is True

    def test_sparse_brief_one_goal_needs_clarification(self):
        gate = ClarificationGate()
        brief = ProductBrief(product_name="Y", goals=["ship fast"])
        decision = gate.should_clarify(brief=brief)
        assert decision.needs_clarification is True

    def test_sparse_prd_no_requirements_needs_clarification(self):
        gate = ClarificationGate()
        prd = PRD(product_name="Z", overview="")  # empty overview + no FRs
        decision = gate.should_clarify(prd=prd)
        assert decision.needs_clarification is True

    def test_no_input_needs_clarification(self):
        gate = ClarificationGate()
        decision = gate.should_clarify()
        assert decision.needs_clarification is True


class TestClarificationGateFull:
    """Full-spec inputs should NOT request clarification."""

    def test_full_brief_two_goals_no_clarification(self):
        gate = ClarificationGate()
        brief = ProductBrief(product_name="FullApp", goals=["goal A", "goal B"])
        decision = gate.should_clarify(brief=brief)
        assert decision.needs_clarification is False
        assert decision.question is None

    def test_full_prd_no_clarification(self):
        gate = ClarificationGate()
        prd = PRD(
            product_name="SolidProduct",
            overview="A well-scoped product.",
            functional_requirements=[
                FunctionalRequirement(
                    id="FR-1",
                    title="Login",
                    description="Users can log in.",
                )
            ],
        )
        decision = gate.should_clarify(prd=prd)
        assert decision.needs_clarification is False


class TestClarificationGateQuestion:
    """When clarification is needed, exactly one non-empty question must be emitted."""

    def test_question_is_non_empty_for_sparse_brief(self):
        gate = ClarificationGate()
        brief = ProductBrief(product_name="Vague", goals=[])
        decision = gate.should_clarify(brief=brief)
        assert decision.needs_clarification is True
        assert decision.question is not None
        assert len(decision.question.strip()) > 0

    def test_question_is_single_sentence(self):
        """The question should be a short, single question."""
        gate = ClarificationGate()
        brief = ProductBrief(product_name="Vague2", goals=["one goal"])
        decision = gate.should_clarify(brief=brief)
        assert decision.needs_clarification is True
        # Should be one question (ends with ?)
        assert "?" in decision.question


class TestClarificationGateRationale:
    """Rationale field must always be present."""

    def test_rationale_present_when_no_clarification(self):
        gate = ClarificationGate()
        brief = ProductBrief(product_name="Full", goals=["g1", "g2"])
        decision = gate.should_clarify(brief=brief)
        assert len(decision.rationale) > 0

    def test_rationale_present_when_clarification_needed(self):
        gate = ClarificationGate()
        brief = ProductBrief(product_name="Sparse", goals=[])
        decision = gate.should_clarify(brief=brief)
        assert len(decision.rationale) > 0
