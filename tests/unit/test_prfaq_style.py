"""Unit tests for PRDWriter PRFAQ style support."""
from __future__ import annotations

from typer.testing import CliRunner

from autodev.agents.prd_writer import PRDWriterAgent
from autodev.schemas import (
    AcceptanceCriterion,
    FunctionalRequirement,
    NonFunctionalRequirement,
    ProductBrief,
    PRFAQDocument,
)
from autodev.cli import app


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_writer_and_prd(style: str = "prd"):
    writer = PRDWriterAgent()
    brief = ProductBrief(
        product_name="TestProduct",
        goals=["Automate deployments", "Reduce toil"],
        non_goals=["Manual patches"],
        delivery_boundary="Q1 2027",
    )
    functional = [
        FunctionalRequirement(id="F-1", title="CI Pipeline", description="Runs tests automatically", priority="MUST"),
        FunctionalRequirement(id="F-2", title="CD Deploy", description="Deploys to staging", priority="MUST"),
    ]
    non_functional = [
        NonFunctionalRequirement(id="NF-1", category="Performance", description="Runs < 5 min", measurable_target="< 5min"),
    ]
    acceptance = [
        AcceptanceCriterion(id="AC-1", description="Pipeline passes on PR", verifiable_by="test"),
    ]
    prd = writer.write(
        brief=brief, functional=functional, non_functional=non_functional,
        acceptance=acceptance, style=style,
    )
    return writer, prd


# ---------------------------------------------------------------------------
# 1. PRD default style unchanged
# ---------------------------------------------------------------------------

def test_prd_default_style_has_functional_section():
    writer, prd = _make_writer_and_prd(style="prd")
    md = writer.render_markdown(prd, style="prd")
    assert "## Functional Requirements" in md
    assert "## Non-Functional Requirements" in md
    assert "## Acceptance Criteria" in md


def test_prd_default_style_no_press_release():
    writer, prd = _make_writer_and_prd(style="prd")
    md = writer.render_markdown(prd, style="prd")
    assert "Press Release" not in md
    assert "## FAQ" not in md


# ---------------------------------------------------------------------------
# 2. PRFAQ style has required sections
# ---------------------------------------------------------------------------

def test_prfaq_has_headline_body_quote_availability_faq():
    writer, prd = _make_writer_and_prd(style="prfaq")
    md = writer.render_markdown(prd, style="prfaq")
    assert "Press Release" in md
    assert "## Headline" in md
    assert "## Body" in md
    assert "## Customer Quote" in md
    assert "## Available Today" in md
    assert "## FAQ" in md


def test_prfaq_faq_contains_functional_questions():
    writer, prd = _make_writer_and_prd(style="prfaq")
    md = writer.render_markdown(prd, style="prfaq")
    # Should contain Q1: prefix from FAQ rendering
    assert "**Q1:" in md


def test_prfaq_product_name_in_title():
    writer, prd = _make_writer_and_prd(style="prfaq")
    md = writer.render_markdown(prd, style="prfaq")
    assert "TestProduct" in md


# ---------------------------------------------------------------------------
# 3. PRFAQDocument schema
# ---------------------------------------------------------------------------

def test_prfaq_document_schema_instantiation():
    doc = PRFAQDocument(
        product_name="Foo",
        headline="Foo launches today",
        body="Foo does X",
        customer_quote='"Amazing" — user',
        availability="Available now",
        faqs=[{"question": "What is Foo?", "answer": "A tool."}],
    )
    assert doc.product_name == "Foo"
    assert len(doc.faqs) == 1
    assert doc.faqs[0]["question"] == "What is Foo?"


# ---------------------------------------------------------------------------
# 4. CLI --style prfaq flag works (smoke test)
# ---------------------------------------------------------------------------

def test_cli_style_flag_accepted():
    """--style prfaq should be accepted by the CLI without error."""
    runner = CliRunner()
    # Invoke with --help to confirm the flag is registered
    result = runner.invoke(app, ["create-prd", "--help"])
    assert result.exit_code == 0
    assert "--style" in result.output


def test_cli_deliver_project_style_flag_accepted():
    runner = CliRunner()
    result = runner.invoke(app, ["deliver-project", "--help"])
    assert result.exit_code == 0
    assert "--style" in result.output
