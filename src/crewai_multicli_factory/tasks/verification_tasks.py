from __future__ import annotations

from ..agents._crewai_bridge import make_task
from ..agents.verifier import VerifierAgent


def build_verification_task(agent: VerifierAgent):
    return make_task(
        description="Independently verify acceptance evidence and state integrity. Fail-closed on gaps.",
        agent=agent.agent,
        expected_output="A VerificationReport.",
    )
