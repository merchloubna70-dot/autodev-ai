from __future__ import annotations

from ..agents._crewai_bridge import make_task
from ..agents.code_reviewer import CodeReviewerAgent
from ..agents.integration_reviewer import IntegrationReviewerAgent


def build_code_review_task(agent: CodeReviewerAgent):
    return make_task(
        description="Review task results against acceptance criteria and changed-files claims.",
        agent=agent.agent,
        expected_output="A CodeReviewReport.",
    )


def build_integration_review_task(agent: IntegrationReviewerAgent):
    return make_task(
        description="Check cross-language consistency, API contracts and schema drift.",
        agent=agent.agent,
        expected_output="An IntegrationReviewReport.",
    )
