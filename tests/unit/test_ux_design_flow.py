"""Unit tests for UXDesignFlow — 7-step deterministic workflow."""
from __future__ import annotations

from pathlib import Path

import pytest

from autodev.flows.ux_design_flow import UXDesignFlow
from autodev.schemas import (
    FunctionalRequirement,
    Language,
    PRD,
    ProductBrief,
    UXDesignInput,
    UXDesignSpec,
)


def _minimal_input(tmp_path: Path, name: str = "FlowProduct") -> UXDesignInput:
    return UXDesignInput(
        product_name=name,
        repo_path=str(tmp_path),
    )


def _prd_input(tmp_path: Path) -> UXDesignInput:
    prd = PRD(
        product_name="PRDProduct",
        overview="Test PRD",
        functional_requirements=[
            FunctionalRequirement(id="FR-1", title="Feature A", description="Do A", priority="must"),
        ],
        non_functional_requirements=[],
        acceptance_criteria=[],
    )
    return UXDesignInput(prd=prd, repo_path=str(tmp_path))


def test_flow_returns_ux_design_spec(tmp_path):
    """run() must return a UXDesignSpec."""
    flow = UXDesignFlow()
    spec = flow.run(_minimal_input(tmp_path))
    assert isinstance(spec, UXDesignSpec)


def test_flow_spec_has_all_required_fields(tmp_path):
    """Spec must have personas, journeys, tokens, components, patterns, breakpoints."""
    flow = UXDesignFlow()
    spec = flow.run(_minimal_input(tmp_path))
    assert spec.personas
    assert spec.journeys
    assert spec.design_tokens
    assert spec.components
    assert spec.patterns
    assert spec.breakpoints
    assert spec.a11y_checks


def test_flow_step7_writes_ux_design_md(tmp_path):
    """Complete step must write product/ux_design.md."""
    flow = UXDesignFlow()
    flow.run(_minimal_input(tmp_path))
    out = tmp_path / "product" / "ux_design.md"
    assert out.exists(), "product/ux_design.md was not created"
    content = out.read_text(encoding="utf-8")
    assert "FlowProduct" in content


def test_flow_each_step_runs_independently(tmp_path):
    """Each of the 7 step methods must be callable without raising."""
    flow = UXDesignFlow()
    prd = None
    product_name = "StepTest"

    personas = flow._step_discovery(product_name, prd)
    assert personas

    journeys = flow._step_core_experience(product_name, personas)
    assert journeys

    tokens = flow._step_design_system()
    assert tokens

    components = flow._step_component_strategy(prd)
    assert components

    patterns = flow._step_ux_patterns(prd)
    assert patterns

    breakpoints, a11y = flow._step_responsive_a11y()
    assert len(breakpoints) == 3
    assert a11y

    spec = flow._step_complete(
        product_name=product_name,
        personas=personas,
        journeys=journeys,
        tokens=tokens,
        components=components,
        patterns=patterns,
        breakpoints=breakpoints,
        a11y_checks=a11y,
        repo_path=str(tmp_path),
    )
    assert isinstance(spec, UXDesignSpec)


def test_flow_backward_compat_no_prd(tmp_path):
    """Flow must work when neither prd nor product_brief is given (just product_name)."""
    flow = UXDesignFlow()
    inp = UXDesignInput(product_name="NoPRD", repo_path=str(tmp_path))
    spec = flow.run(inp)
    assert spec.product_name == "NoPRD"
    assert isinstance(spec, UXDesignSpec)


def test_flow_uses_prd_product_name(tmp_path):
    """product_name from PRD takes precedence when no explicit name given."""
    flow = UXDesignFlow()
    inp = _prd_input(tmp_path)
    # No explicit product_name in input, should use PRD's
    inp.product_name = ""
    spec = flow.run(inp)
    assert spec.product_name == "PRDProduct"


def test_flow_is_deterministic(tmp_path):
    """Two runs with the same input must produce the same spec structure."""
    flow = UXDesignFlow()
    inp = _minimal_input(tmp_path, "Deterministic")
    spec1 = flow.run(inp)
    spec2 = flow.run(inp)
    assert spec1.product_name == spec2.product_name
    assert len(spec1.personas) == len(spec2.personas)
    assert len(spec1.design_tokens) == len(spec2.design_tokens)
