from __future__ import annotations

from ..agents._crewai_bridge import make_task
from ..agents.commit_agent import CommitAgent


def build_commit_task(agent: CommitAgent):
    return make_task(
        description="Build branch name, commit message, and PR body. Do not push or tag unless explicitly enabled.",
        agent=agent.agent,
        expected_output="CommitArtifacts (branch + commit + PR body).",
    )
