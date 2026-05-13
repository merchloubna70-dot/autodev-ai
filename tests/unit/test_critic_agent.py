"""Unit tests for CriticAgent (FACTORY_FORCE_MOCK=1 path)."""
from __future__ import annotations

import pytest

from autodev.agents.critic import CriticAgent
from autodev.schemas import CriticVerdict


@pytest.fixture(autouse=True)
def _force_mock(monkeypatch):
    monkeypatch.setenv("FACTORY_FORCE_MOCK", "1")


class TestCriticAgent:
    def test_mock_returns_done_true(self):
        """Mock OpusConsultAgent always returns APPROVE → done=True."""
        critic = CriticAgent()
        verdict = critic.evaluate(
            task_description="Write a hello world function",
            implementation_output="def hello(): return 'hello'",
            iteration=0,
        )
        assert isinstance(verdict, CriticVerdict)
        assert verdict.done is True

    def test_mock_score_is_one(self):
        """Mock path should produce score=1.0 (maps APPROVE to perfect)."""
        critic = CriticAgent()
        verdict = critic.evaluate(
            task_description="Add unit tests",
            implementation_output="def test_foo(): assert foo() == 42",
            iteration=1,
        )
        assert verdict.score == 1.0

    def test_iteration_preserved(self):
        """Iteration number should be stored in the verdict."""
        critic = CriticAgent()
        for i in range(3):
            verdict = critic.evaluate(
                task_description="Task",
                implementation_output="output",
                iteration=i,
            )
            assert verdict.iteration == i

    def test_notes_present(self):
        """Mock path should still return non-empty notes list."""
        critic = CriticAgent()
        verdict = critic.evaluate(
            task_description="Refactor module",
            implementation_output="refactored code here",
            iteration=0,
        )
        assert isinstance(verdict.notes, list)
        # mock-approved note expected
        assert len(verdict.notes) > 0

    def test_parse_approve_text(self):
        """_parse should recognise APPROVE text even without [MOCK-OPUS] prefix."""
        critic = CriticAgent()
        verdict = critic._parse("APPROVE — looks good.", iteration=2)
        assert verdict.done is True
        assert verdict.score == 1.0

    def test_parse_structured_response(self):
        """_parse should extract SCORE/DONE/NOTES from structured text."""
        critic = CriticAgent()
        text = "SCORE: 0.6\nDONE: false\nNOTES:\n- missing error handling\n- add docstring"
        verdict = critic._parse(text, iteration=0)
        assert verdict.score == pytest.approx(0.6)
        assert verdict.done is False
        assert "missing error handling" in verdict.notes

    def test_parse_high_score_implies_done(self):
        """score >= 0.8 should set done=True even if DONE line says false."""
        critic = CriticAgent()
        text = "SCORE: 0.9\nDONE: false\n"
        verdict = critic._parse(text, iteration=0)
        assert verdict.done is True
