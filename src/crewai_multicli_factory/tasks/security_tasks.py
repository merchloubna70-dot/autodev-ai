from __future__ import annotations

from ..agents._crewai_bridge import make_task
from ..agents.security_reviewer import SecurityReviewerAgent


def build_security_task(agent: SecurityReviewerAgent):
    return make_task(
        description="Scan changed surface for secrets, unsafe shell, and risky dependency patterns.",
        agent=agent.agent,
        expected_output="A SecurityReviewReport.",
    )
