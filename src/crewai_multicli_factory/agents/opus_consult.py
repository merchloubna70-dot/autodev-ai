"""OpusConsultAgent — formal agent for consulting Claude Opus 4.7.

Two modes:
- architect: planning, read-only, returns a structured plan.
- reviewer:  final review, returns APPROVE / REQUEST_CHANGES / REJECT verdict.
"""
from __future__ import annotations

from ..adapters.opus_adapter import OpusAdapter
from ..schemas import OpusConsultMode, OpusConsultResult


class OpusConsultAgent:
    """High-level agent that delegates to OpusAdapter."""

    def __init__(self, adapter: OpusAdapter | None = None) -> None:
        self._adapter = adapter or OpusAdapter()

    def architect(self, question: str) -> OpusConsultResult:
        """Consult Opus in architect mode for planning / design questions.

        Returns a structured plan (read-only, no implementation).
        """
        return self._adapter.consult(OpusConsultMode.ARCHITECT, question)

    def reviewer(self, diff_or_evidence: str) -> OpusConsultResult:
        """Consult Opus in reviewer mode for final review / merge gate.

        Returns an OpusConsultResult with verdict in
        {APPROVE, REQUEST_CHANGES, REJECT}.
        """
        return self._adapter.consult(OpusConsultMode.REVIEWER, diff_or_evidence)
