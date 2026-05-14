"""Tests for PydanticAIAgentFactory bridge.

Verifies that:
1. The factory returns a valid stub when pydantic_ai is missing.
2. The stub forwards to InputClassifierAgent.classify and returns InputClassification.
3. PydanticAIBridgeStatus correctly reports stub state.
"""
from __future__ import annotations

from autodev.adapters.pydantic_ai_bridge import PydanticAIAgentFactory
from autodev.schemas import InputClassification, PydanticAIBridgeStatus

# ---------------------------------------------------------------------------
# Test 1: factory returns a valid stub when pydantic_ai is missing
# ---------------------------------------------------------------------------


def test_build_typed_classifier_returns_stub_when_pydantic_ai_missing(monkeypatch):
    """When pydantic_ai is unavailable, factory returns a stub, not None."""
    import autodev.adapters.pydantic_ai_bridge as mod

    monkeypatch.setattr(mod, "_PYDANTIC_AI_AVAILABLE", False)
    monkeypatch.setattr(mod, "pydantic_ai", None)

    agent = PydanticAIAgentFactory.build_typed_classifier()

    # Should be the stub, not None
    assert agent is not None
    # Stub exposes is_stub property
    assert hasattr(agent, "is_stub")
    assert agent.is_stub is True


# ---------------------------------------------------------------------------
# Test 2: stub forwards to InputClassifierAgent.classify
# ---------------------------------------------------------------------------


def test_stub_forwards_to_input_classifier_agent(monkeypatch):
    """Stub.run_sync() delegates to InputClassifierAgent and returns InputClassification."""
    import autodev.adapters.pydantic_ai_bridge as mod

    monkeypatch.setattr(mod, "_PYDANTIC_AI_AVAILABLE", False)
    monkeypatch.setattr(mod, "pydantic_ai", None)

    agent = PydanticAIAgentFactory.build_typed_classifier()

    result = agent.run_sync("Steps to reproduce: click the button and it crashes")

    assert isinstance(result, InputClassification)
    # Bug-report text → should classify as bugfix_request or similar
    assert result.input_type is not None
    assert result.confidence >= 0.0


# ---------------------------------------------------------------------------
# Test 3: PydanticAIBridgeStatus reflects stub state
# ---------------------------------------------------------------------------


def test_bridge_status_reports_stub_when_unavailable(monkeypatch):
    """bridge_status() returns stub=True when pydantic_ai is not installed."""
    import autodev.adapters.pydantic_ai_bridge as mod

    monkeypatch.setattr(mod, "_PYDANTIC_AI_AVAILABLE", False)

    status = PydanticAIAgentFactory.bridge_status()

    assert isinstance(status, PydanticAIBridgeStatus)
    assert status.pydantic_ai_available is False
    assert status.fallback_to_stub is True
    assert len(status.stub_reason) > 0  # reason must be non-empty


def test_bridge_status_schema_fields():
    """PydanticAIBridgeStatus can be constructed with all fields."""
    status = PydanticAIBridgeStatus(
        pydantic_ai_available=True,
        fallback_to_stub=False,
        stub_reason="",
    )
    assert status.pydantic_ai_available is True
    assert status.fallback_to_stub is False


def test_build_typed_classifier_consistent_with_bridge_status(monkeypatch):
    """build_typed_classifier stub state is consistent with bridge_status."""
    import autodev.adapters.pydantic_ai_bridge as mod

    monkeypatch.setattr(mod, "_PYDANTIC_AI_AVAILABLE", False)
    monkeypatch.setattr(mod, "pydantic_ai", None)

    agent = PydanticAIAgentFactory.build_typed_classifier()
    status = PydanticAIAgentFactory.bridge_status()

    # If status says stub, agent should also be a stub
    assert status.fallback_to_stub == agent.is_stub
