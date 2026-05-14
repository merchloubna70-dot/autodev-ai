"""SprintManagerAgent — thin orchestrator for the BMAD Sprint lifecycle.

Delegates all logic to SprintFlow; adds minimal agent-persona scaffolding so
it can be wired into a CrewAI-based pipeline the same way as other agents.
"""
from __future__ import annotations

from ..schemas import (
    RetrospectiveReport,
    SprintChangeProposal,
    SprintInput,
    SprintState,
    SprintStatus,
)


class SprintManagerAgent:
    """BMAD Sprint Manager — coordinates sprint planning, tracking, and course correction."""

    name = "SprintManager"
    title = "BMAD Sprint Manager"
    icon = "🏃"

    def __init__(self) -> None:
        from ..flows.sprint_flow import SprintFlow
        self._flow = SprintFlow()

    # ------------------------------------------------------------------
    # Public API — mirrors SprintFlow but adds agent-level logging
    # ------------------------------------------------------------------

    def start_sprint(self, inp: SprintInput) -> SprintState:
        """Open a new sprint and return its initial state."""
        state = self._flow.start_sprint(inp)
        return state

    def get_status(self, repo_path: str, sprint_id: str | None = None) -> SprintStatus:
        """Return current status for the active (or specified) sprint."""
        return self._flow.status(repo_path, sprint_id)

    def run_retrospective(self, repo_path: str, sprint_id: str) -> RetrospectiveReport:
        """Analyse sprint results and produce a retrospective report."""
        return self._flow.retrospective(repo_path, sprint_id)

    def correct_course(
        self,
        repo_path: str,
        sprint_id: str,
        change_description: str,
    ) -> SprintChangeProposal:
        """Analyse impact of a proposed change and return a change proposal."""
        return self._flow.correct_course(repo_path, sprint_id, change_description)
