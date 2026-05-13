from __future__ import annotations

from ..agents._crewai_bridge import make_task
from ..agents.doc_writer import DocWriterAgent


def build_doc_task(agent: DocWriterAgent):
    return make_task(
        description="Produce README, usage and architecture documentation for the delivered project.",
        agent=agent.agent,
        expected_output="Markdown docs.",
    )
