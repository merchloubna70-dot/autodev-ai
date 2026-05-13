"""CriticAgent — evaluates implementation quality and decides whether to iterate.

Uses OpusConsultAgent.reviewer (mock-friendly via FACTORY_FORCE_MOCK=1).
"""
from __future__ import annotations

from ..schemas import CriticVerdict
from .opus_consult import OpusConsultAgent


_SCORE_DONE_THRESHOLD = 0.8


class CriticAgent:
    """Evaluates an implementation attempt and returns a CriticVerdict."""

    def __init__(self, agent: OpusConsultAgent | None = None) -> None:
        self._agent = agent or OpusConsultAgent()

    def evaluate(
        self,
        task_description: str,
        implementation_output: str,
        iteration: int = 0,
    ) -> CriticVerdict:
        """Ask the reviewer to score this implementation attempt.

        Returns a CriticVerdict.  When FACTORY_FORCE_MOCK=1 the underlying
        OpusAdapter returns a mock APPROVE response which we map to a passing
        score so tests are deterministic.
        """
        prompt = (
            f"## Task\n{task_description}\n\n"
            f"## Implementation output (iteration {iteration})\n{implementation_output}\n\n"
            "## Instructions\n"
            "Score 0.0-1.0 (1.0=perfect). Mark done=true if score >= 0.8. "
            "List any blocking notes. Format:\n"
            "SCORE: <float>\nDONE: <true|false>\nNOTES:\n- <note>"
        )
        result = self._agent.reviewer(prompt)
        return self._parse(result.response_text, iteration=iteration)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _parse(self, response: str, *, iteration: int) -> CriticVerdict:
        """Parse the free-text Opus response into a CriticVerdict.

        Robust: falls back to done=True score=1.0 when the response contains
        [MOCK-OPUS] (deterministic mock path) or APPROVE.
        """
        text = response or ""

        # Mock / APPROVE fast-path
        if "[MOCK-OPUS]" in text or "APPROVE" in text:
            return CriticVerdict(score=1.0, done=True, notes=["mock-approved"], iteration=iteration)

        score = 0.0
        done = False
        notes: list[str] = []

        for line in text.splitlines():
            stripped = line.strip()
            if stripped.upper().startswith("SCORE:"):
                try:
                    score = float(stripped.split(":", 1)[1].strip())
                except ValueError:
                    pass
            elif stripped.upper().startswith("DONE:"):
                done_str = stripped.split(":", 1)[1].strip().lower()
                done = done_str in ("true", "yes", "1")
            elif stripped.startswith("- "):
                notes.append(stripped[2:])

        # Derive done from score if not explicitly set
        if not done and score >= _SCORE_DONE_THRESHOLD:
            done = True

        return CriticVerdict(score=score, done=done, notes=notes, iteration=iteration)
