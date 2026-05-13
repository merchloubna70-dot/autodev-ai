"""Tests for IssuePipelineCrewFlow and ProjectDeliveryCrewFlow stubs.

These tests verify that:
1. Both classes construct without error (no crewai required for instantiation).
2. .run(...) raises RuntimeError("crewai not installed") when crewai is unavailable.
3. The module-level _CREWAI_AVAILABLE flag correctly reflects availability.
"""
from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# IssuePipelineCrewFlow
# ---------------------------------------------------------------------------


def test_issue_pipeline_crewflow_constructs():
    """IssuePipelineCrewFlow can be instantiated without crewai installed."""
    from crewai_multicli_factory.flows.issue_pipeline_crewflow import IssuePipelineCrewFlow

    flow = IssuePipelineCrewFlow()
    assert flow is not None
    # Internal state dict is empty at construction
    assert isinstance(flow._state, dict)


def test_issue_pipeline_crewflow_run_raises_when_crewai_unavailable(monkeypatch):
    """When crewai is unavailable, .run() raises RuntimeError with correct message."""
    import crewai_multicli_factory.flows.issue_pipeline_crewflow as mod

    monkeypatch.setattr(mod, "_CREWAI_AVAILABLE", False)

    from crewai_multicli_factory.flows.issue_pipeline_crewflow import (
        IssuePipelineCrewFlow,
        IssuePipelineCrewFlowInput,
    )

    flow = IssuePipelineCrewFlow()
    inp = IssuePipelineCrewFlowInput(repo_path="/tmp/noop", issue_text="Some issue")

    with pytest.raises(RuntimeError, match="crewai not installed"):
        flow.run(inp)


# ---------------------------------------------------------------------------
# ProjectDeliveryCrewFlow
# ---------------------------------------------------------------------------


def test_project_delivery_crewflow_constructs():
    """ProjectDeliveryCrewFlow can be instantiated without crewai installed."""
    from crewai_multicli_factory.flows.project_delivery_crewflow import ProjectDeliveryCrewFlow

    flow = ProjectDeliveryCrewFlow()
    assert flow is not None
    assert isinstance(flow._state, dict)


def test_project_delivery_crewflow_run_raises_when_crewai_unavailable(monkeypatch):
    """When crewai is unavailable, .run() raises RuntimeError with correct message."""
    import crewai_multicli_factory.flows.project_delivery_crewflow as mod

    monkeypatch.setattr(mod, "_CREWAI_AVAILABLE", False)

    from crewai_multicli_factory.flows.project_delivery_crewflow import (
        ProjectDeliveryCrewFlow,
        ProjectDeliveryCrewFlowInput,
    )

    flow = ProjectDeliveryCrewFlow()
    inp = ProjectDeliveryCrewFlowInput(repo_path="/tmp/noop", brief_text="Build something cool")

    with pytest.raises(RuntimeError, match="crewai not installed"):
        flow.run(inp)


def test_crewai_availability_flag_consistency():
    """Both CrewFlow modules agree on crewai availability."""
    import crewai_multicli_factory.flows.issue_pipeline_crewflow as issue_mod
    import crewai_multicli_factory.flows.project_delivery_crewflow as delivery_mod

    # Both should report the same state (either both True or both False)
    assert issue_mod._CREWAI_AVAILABLE == delivery_mod._CREWAI_AVAILABLE
