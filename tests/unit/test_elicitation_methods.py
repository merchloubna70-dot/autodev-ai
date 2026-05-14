"""Tests for ElicitationMethodsAgent (BMAD-14)."""
from __future__ import annotations

import textwrap

from autodev.agents.elicitation_methods import ElicitationMethodsAgent
from autodev.schemas import ElicitationMethod, ElicitationOutput

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _agent() -> ElicitationMethodsAgent:
    return ElicitationMethodsAgent()


# ---------------------------------------------------------------------------
# Test 1: load_methods returns ≥ 12 entries
# ---------------------------------------------------------------------------

def test_load_methods_returns_at_least_12():
    methods = _agent().load_methods()
    assert len(methods) >= 12, f"Expected ≥12 methods, got {len(methods)}"


# ---------------------------------------------------------------------------
# Test 2: list_categories has ≥ 4 distinct categories
# ---------------------------------------------------------------------------

def test_list_categories_at_least_4():
    cats = _agent().list_categories()
    assert len(cats) >= 4, f"Expected ≥4 categories, got {cats}"


# ---------------------------------------------------------------------------
# Test 3: load_methods returns ElicitationMethod instances with required fields
# ---------------------------------------------------------------------------

def test_load_methods_correct_types():
    methods = _agent().load_methods()
    for m in methods:
        assert isinstance(m, ElicitationMethod)
        assert m.category
        assert m.method_name
        assert m.description


# ---------------------------------------------------------------------------
# Test 4: recommend by keyword returns ≤ k results and relevant methods
# ---------------------------------------------------------------------------

def test_recommend_by_keyword():
    agent = _agent()
    results = agent.recommend("risk failure", k=3)
    assert len(results) <= 3
    # At least one result should relate to risk or failure topics
    combined_text = " ".join(
        (r.category + " " + r.method_name + " " + r.description).lower()
        for r in results
    )
    assert any(kw in combined_text for kw in ("risk", "failure", "fail", "pre-mortem", "red"))


def test_recommend_returns_k_results():
    agent = _agent()
    results = agent.recommend("unknown topic xyzzy", k=5)
    # Falls back to first k methods regardless
    assert len(results) == 5


# ---------------------------------------------------------------------------
# Test 5: apply_method is deterministic (FACTORY_FORCE_MOCK=1)
# ---------------------------------------------------------------------------

def test_apply_method_deterministic(monkeypatch):
    monkeypatch.setenv("FACTORY_FORCE_MOCK", "1")
    agent = _agent()
    methods = agent.load_methods()
    m = methods[0]
    content = "our product requirements"

    out1 = agent.apply_method(m, content)
    out2 = agent.apply_method(m, content)

    assert isinstance(out1, ElicitationOutput)
    assert out1.output_text == out2.output_text
    assert content in out1.input_content
    assert out1.output_text.startswith("[MOCK]")


# ---------------------------------------------------------------------------
# Test 6: apply_method embeds content in output
# ---------------------------------------------------------------------------

def test_apply_method_embeds_content(monkeypatch):
    monkeypatch.setenv("FACTORY_FORCE_MOCK", "1")
    agent = _agent()
    methods = agent.load_methods()
    # Find a method with a known template that includes {content}
    m = next((x for x in methods if x.method_name == "5-whys"), methods[0])
    content = "deployment pipeline errors"
    out = agent.apply_method(m, content)
    assert content in out.output_text or content in out.input_content


# ---------------------------------------------------------------------------
# Test 7: CSV malformed rows are handled gracefully
# ---------------------------------------------------------------------------

def test_malformed_csv_handled_gracefully(tmp_path):
    bad_csv = tmp_path / "bad.csv"
    bad_csv.write_text(
        textwrap.dedent(
            """\
            category,method_name,description
            core,good-method,A valid method description
            ,missing-category,No category provided
            core,,missing method name
            core,another-good,Another valid description
            this_is_completely_wrong_no_commas_at_all
            """
        )
    )
    agent = ElicitationMethodsAgent(csv_path=bad_csv)
    methods = agent.load_methods()
    # Should load only valid rows (2 valid, skip 3 malformed)
    assert len(methods) == 2
    names = [m.method_name for m in methods]
    assert "good-method" in names
    assert "another-good" in names


# ---------------------------------------------------------------------------
# Test 8: missing CSV → empty list, no exception
# ---------------------------------------------------------------------------

def test_missing_csv_returns_empty(tmp_path):
    agent = ElicitationMethodsAgent(csv_path=tmp_path / "nonexistent.csv")
    methods = agent.load_methods()
    assert methods == []


# ---------------------------------------------------------------------------
# Test 9: load_methods is cached (same object returned)
# ---------------------------------------------------------------------------

def test_load_methods_is_cached():
    agent = _agent()
    first = agent.load_methods()
    second = agent.load_methods()
    # Same content, not necessarily same object (we return list copies)
    assert len(first) == len(second)
    assert [m.method_name for m in first] == [m.method_name for m in second]


# ---------------------------------------------------------------------------
# Test 10: ElicitationMethodsAgent importable from agents package
# ---------------------------------------------------------------------------

def test_importable_from_agents_package():
    from autodev.agents import ElicitationMethodsAgent as EMA  # noqa: F401
    assert EMA is ElicitationMethodsAgent


# ---------------------------------------------------------------------------
# Test 11: ElicitationMethod and ElicitationOutput in schemas
# ---------------------------------------------------------------------------

def test_schemas_importable():
    from autodev.schemas import ElicitationMethod as EM
    from autodev.schemas import ElicitationOutput as EO
    m = EM(category="core", method_name="test", description="desc")
    assert m.prompt_template == ""
    assert m.tags == []
    o = EO(method=m, input_content="x", output_text="y")
    assert o.generated_at  # non-empty ISO timestamp


# ---------------------------------------------------------------------------
# Test 12: all 5 epistemic methods present
# ---------------------------------------------------------------------------

def test_epistemic_methods_present():
    agent = _agent()
    methods = agent.load_methods()
    epistemic = [m for m in methods if m.category == "epistemic"]
    names = {m.method_name for m in epistemic}
    assert "assumption-mapping" in names
    assert "knowledge-gap" in names
    assert "evidence-check" in names
