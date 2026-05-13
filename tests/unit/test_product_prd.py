from crewai_multicli_factory.agents.prd_writer import PRDWriterAgent
from crewai_multicli_factory.agents.product_manager import ProductManagerAgent
from crewai_multicli_factory.agents.requirement_analyst import RequirementAnalystAgent


def test_brief_to_prd():
    text = """# X
Goals:
- ship MVP
Use Cases:
- upload csv
MVP scope:
- cli upload
Non-Goals:
- streaming
Delivery boundary: single repo
"""
    brief = ProductManagerAgent().build_brief(text)
    assert brief.product_name == "X"
    assert any("ship" in g.lower() for g in brief.goals)
    fr, nf, ac = RequirementAnalystAgent().derive(brief=brief, source_text=text)
    assert fr and nf and ac
    prd = PRDWriterAgent().write(brief=brief, functional=fr, non_functional=nf, acceptance=ac)
    md = PRDWriterAgent().render_markdown(prd)
    assert "# PRD" in md
