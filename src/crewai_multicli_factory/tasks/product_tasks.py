from __future__ import annotations

from ..agents._crewai_bridge import make_task
from ..agents.product_manager import ProductManagerAgent


def build_product_task(agent: ProductManagerAgent, brief_text: str):
    return make_task(
        description=f"Construct a ProductBrief from the given brief:\n\n{brief_text[:1200]}",
        agent=agent.agent,
        expected_output="A ProductBrief JSON object.",
    )
