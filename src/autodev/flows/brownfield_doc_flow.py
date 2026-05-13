"""BrownfieldDocFlow — orchestrates DocumentProjectAgent."""
from __future__ import annotations

from ..agents.document_project import DocumentProjectAgent
from ..schemas import BrownfieldDoc, BrownfieldDocInput


class BrownfieldDocFlow:
    """Flow wrapper for brownfield project documentation generation."""

    def __init__(self) -> None:
        self._agent = DocumentProjectAgent()

    def run(self, inp: BrownfieldDocInput) -> BrownfieldDoc:
        return self._agent.document(
            repo_path=inp.repo_path,
            languages=inp.languages or None,
        )
