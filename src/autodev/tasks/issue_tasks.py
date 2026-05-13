from __future__ import annotations

from ..agents._crewai_bridge import make_task
from ..agents.issue_analyst import IssueAnalystAgent


def build_issue_analysis_task(agent: IssueAnalystAgent, raw_issue: str):
    return make_task(
        description=f"Parse issue text into IssueRequirements:\n\n{raw_issue[:1200]}",
        agent=agent.agent,
        expected_output="An IssueRequirements JSON object.",
    )
