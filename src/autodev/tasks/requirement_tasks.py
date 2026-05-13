from __future__ import annotations

from ..agents._crewai_bridge import make_task
from ..agents.requirement_analyst import RequirementAnalystAgent


def build_requirement_task(agent: RequirementAnalystAgent):
    return make_task(
        description="Lift functional/non-functional/acceptance requirements from the locked ProductBrief.",
        agent=agent.agent,
        expected_output="Lists of FunctionalRequirement, NonFunctionalRequirement, AcceptanceCriterion.",
    )
