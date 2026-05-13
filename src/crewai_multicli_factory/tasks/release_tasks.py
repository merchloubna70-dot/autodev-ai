from __future__ import annotations

from ..agents._crewai_bridge import make_task
from ..agents.release_manager import ReleaseManagerAgent


def build_release_task(agent: ReleaseManagerAgent):
    return make_task(
        description="Run release checks and produce release notes + delivery report. Never overstate readiness.",
        agent=agent.agent,
        expected_output="ReleaseCheckReport + DeliveryReport.",
    )
