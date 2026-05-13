"""Unit tests for OpusConsultAgent under FACTORY_FORCE_MOCK=1."""
from __future__ import annotations

import os

import pytest

from crewai_multicli_factory.agents.opus_consult import OpusConsultAgent
from crewai_multicli_factory.schemas import OpusConsultMode, OpusConsultResult


@pytest.fixture(autouse=True)
def _force_mock(monkeypatch):
    monkeypatch.setenv("FACTORY_FORCE_MOCK", "1")


class TestOpusConsultArchitect:
    def test_returns_opus_consult_result(self):
        agent = OpusConsultAgent()
        result = agent.architect("How should we redesign the ingestion pipeline?")
        assert isinstance(result, OpusConsultResult)

    def test_mock_used_is_true(self):
        agent = OpusConsultAgent()
        result = agent.architect("design question")
        assert result.mock_used is True

    def test_mode_is_architect(self):
        agent = OpusConsultAgent()
        result = agent.architect("some architecture question")
        assert result.mode == OpusConsultMode.ARCHITECT

    def test_response_has_mock_opus_prefix(self):
        agent = OpusConsultAgent()
        result = agent.architect("design question")
        assert result.response_text.startswith("[MOCK-OPUS]")

    def test_verdict_is_none_for_architect(self):
        agent = OpusConsultAgent()
        result = agent.architect("any question")
        assert result.verdict is None

    def test_prompt_sha_is_set(self):
        agent = OpusConsultAgent()
        result = agent.architect("some question")
        assert len(result.prompt_sha) == 16

    def test_deterministic_for_same_prompt(self):
        agent = OpusConsultAgent()
        r1 = agent.architect("identical question")
        r2 = agent.architect("identical question")
        assert r1.prompt_sha == r2.prompt_sha
        assert r1.response_text == r2.response_text


class TestOpusConsultReviewer:
    def test_returns_opus_consult_result(self):
        agent = OpusConsultAgent()
        result = agent.reviewer("diff showing security changes")
        assert isinstance(result, OpusConsultResult)

    def test_mock_used_is_true(self):
        agent = OpusConsultAgent()
        result = agent.reviewer("some diff")
        assert result.mock_used is True

    def test_mode_is_reviewer(self):
        agent = OpusConsultAgent()
        result = agent.reviewer("some diff")
        assert result.mode == OpusConsultMode.REVIEWER

    def test_mock_response_contains_approve(self):
        agent = OpusConsultAgent()
        result = agent.reviewer("some diff")
        # Default mock always returns APPROVE
        assert "APPROVE" in result.response_text.upper()

    def test_verdict_approve_extracted(self):
        agent = OpusConsultAgent()
        result = agent.reviewer("diff text")
        assert result.verdict == "APPROVE"

    def test_verdict_request_changes_extracted(self, monkeypatch):
        """Inject a custom mock that returns REQUEST_CHANGES."""
        from crewai_multicli_factory.adapters import opus_adapter as _mod

        original = _mod._mock_response

        def patched(mode, sha):
            if mode == OpusConsultMode.REVIEWER:
                return "[MOCK-OPUS] REQUEST_CHANGES — needs fixes"
            return original(mode, sha)

        monkeypatch.setattr(_mod, "_mock_response", patched)
        agent = OpusConsultAgent()
        result = agent.reviewer("diff text")
        assert result.verdict == "REQUEST_CHANGES"

    def test_verdict_reject_extracted(self, monkeypatch):
        """Inject a custom mock that returns REJECT."""
        from crewai_multicli_factory.adapters import opus_adapter as _mod

        original = _mod._mock_response

        def patched(mode, sha):
            if mode == OpusConsultMode.REVIEWER:
                return "[MOCK-OPUS] REJECT — critical issues found"
            return original(mode, sha)

        monkeypatch.setattr(_mod, "_mock_response", patched)
        agent = OpusConsultAgent()
        result = agent.reviewer("diff text")
        assert result.verdict == "REJECT"

    def test_exit_code_zero(self):
        agent = OpusConsultAgent()
        result = agent.reviewer("diff")
        assert result.exit_code == 0
