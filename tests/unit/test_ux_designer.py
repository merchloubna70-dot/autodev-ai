"""Unit tests for UXDesignerAgent (Sally)."""
from __future__ import annotations

from autodev.agents.ux_designer import UXDesignerAgent
from autodev.schemas import (
    PRD,
    AcceptanceCriterion,
    AgentCard,
    FunctionalRequirement,
    ProductBrief,
    UXDesignSpec,
)


def _sample_prd() -> PRD:
    return PRD(
        product_name="TestApp",
        overview="A test application",
        functional_requirements=[
            FunctionalRequirement(id="FR-1", title="User login", description="Users can log in", priority="must"),
            FunctionalRequirement(id="FR-2", title="Admin dashboard", description="Admins can view metrics", priority="must"),
        ],
        non_functional_requirements=[],
        acceptance_criteria=[
            AcceptanceCriterion(id="AC-1", description="Login works", verifiable_by="test"),
        ],
    )


def test_sally_persona_name():
    """Sally's name and icon must match BMAD customize.toml."""
    agent = UXDesignerAgent()
    assert agent.name == "Sally"
    assert agent.title == "UX Designer"
    assert agent.icon == "🎨"


def test_sally_principles():
    """Sally must carry at least the 3 BMAD core principles."""
    agent = UXDesignerAgent()
    assert len(agent.principles) >= 3
    full_text = " ".join(agent.principles).lower()
    assert "user need" in full_text


def test_design_returns_valid_ux_spec_from_prd():
    """design() must return a populated UXDesignSpec when given a PRD."""
    agent = UXDesignerAgent()
    prd = _sample_prd()
    spec = agent.design(prd=prd)
    assert isinstance(spec, UXDesignSpec)
    assert spec.product_name == "TestApp"
    assert len(spec.personas) >= 1
    assert len(spec.journeys) >= 1
    assert len(spec.design_tokens) >= 10
    assert len(spec.components) >= 3
    assert len(spec.breakpoints) == 3
    assert len(spec.a11y_checks) >= 5


def test_design_is_deterministic():
    """Two calls with the same PRD must produce the same spec (names, counts)."""
    agent = UXDesignerAgent()
    prd = _sample_prd()
    spec1 = agent.design(prd=prd)
    spec2 = agent.design(prd=prd)
    assert spec1.product_name == spec2.product_name
    assert len(spec1.personas) == len(spec2.personas)
    assert len(spec1.design_tokens) == len(spec2.design_tokens)
    assert [c.name for c in spec1.components] == [c.name for c in spec2.components]


def test_design_no_prd_uses_brief():
    """design() must fall back to ProductBrief when no PRD given."""
    agent = UXDesignerAgent()
    brief = ProductBrief(product_name="BriefProduct", goals=["Help users"])
    spec = agent.design(brief=brief)
    assert spec.product_name == "BriefProduct"


def test_design_factory_force_mock_doesnt_break(monkeypatch):
    """FACTORY_FORCE_MOCK=1 must not raise — agent stays deterministic."""
    monkeypatch.setenv("FACTORY_FORCE_MOCK", "1")
    agent = UXDesignerAgent(use_llm=True)  # forced back to mock/deterministic
    spec = agent.design(prd=_sample_prd())
    assert isinstance(spec, UXDesignSpec)
    assert spec.product_name == "TestApp"


def test_as_agent_card_returns_card():
    """as_agent_card() must return a valid AgentCard with expected fields."""
    agent = UXDesignerAgent()
    card = agent.as_agent_card()
    assert isinstance(card, AgentCard)
    assert card.name == "Sally"
    assert "ux-design" in card.capabilities
    assert "bmad" in card.tags


def test_render_markdown_includes_sections():
    """render_markdown() must include all major section headings."""
    agent = UXDesignerAgent()
    spec = agent.design(prd=_sample_prd())
    md = agent.render_markdown(spec)
    assert "## User Personas" in md
    assert "## User Journeys" in md
    assert "## Design System Tokens" in md
    assert "## Component Strategy" in md
    assert "## UX Patterns" in md
    assert "## Responsive Breakpoints" in md
    assert "## Accessibility Checklist" in md
