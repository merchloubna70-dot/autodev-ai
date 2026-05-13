"""InvestigationFlow — thin wrapper around InvestigatorAgent.

Sets up the state directory and delegates to InvestigatorAgent.run().
"""
from __future__ import annotations

from pathlib import Path

from ..agents.investigator import InvestigatorAgent
from ..schemas import CaseFile, InvestigationInput


class InvestigationFlow:
    """Orchestrates a single investigation run."""

    def __init__(self) -> None:
        self.agent = InvestigatorAgent()

    def run(self, inp: InvestigationInput) -> CaseFile:
        """Execute investigation and return the populated CaseFile."""
        # Ensure state directory exists
        state_dir = Path(inp.repo_path) / ".dev-factory" / "investigations"
        state_dir.mkdir(parents=True, exist_ok=True)

        return self.agent.run(inp.input_token, inp.repo_path)
