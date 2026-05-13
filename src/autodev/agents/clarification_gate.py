"""ClarificationGate — decides whether clarification is needed before planning.

In mock / dry-run mode the decision is fully deterministic:
- Full-spec PRDs (goals >= 2) → no clarification needed.
- Sparse PRDs (goals < 2)    → needs clarification; emits exactly one question.

In real mode (future) this would call the Opus architect to generate the
question from the PRD context.
"""
from __future__ import annotations

import os

from ..schemas import ClarificationDecision, PRD, ProductBrief


class ClarificationGate:
    """Decide if a planning session needs clarification before proceeding.

    The gate asks at most one question and is deterministic in mock mode so
    that tests are stable without network access.
    """

    def should_clarify(
        self,
        prd: PRD | None = None,
        brief: ProductBrief | None = None,
    ) -> ClarificationDecision:
        """Evaluate the PRD/brief and return a clarification decision.

        Parameters
        ----------
        prd:
            Fully expanded PRD (preferred).  When supplied, the gate checks
            whether the PRD has enough functional requirements to proceed.
        brief:
            Lightweight product brief.  Used when a full PRD is not yet
            available.  The gate counts ``goals``; < 2 goals → sparse.

        Returns
        -------
        ClarificationDecision
            ``needs_clarification=False`` for well-specified inputs;
            ``needs_clarification=True`` + a single ``question`` for sparse ones.
        """
        force_mock = os.environ.get("FACTORY_FORCE_MOCK", "0") not in ("0", "false", "")

        if force_mock or not _real_mode_available():
            return self._mock_decide(prd=prd, brief=brief)

        # Real mode placeholder (would call Opus architect)  # pragma: no cover
        return self._mock_decide(prd=prd, brief=brief)  # pragma: no cover

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _mock_decide(
        self,
        *,
        prd: PRD | None,
        brief: ProductBrief | None,
    ) -> ClarificationDecision:
        """Deterministic mock decision for CI / dry-run mode."""
        if prd is not None:
            return self._decide_from_prd(prd)
        if brief is not None:
            return self._decide_from_brief(brief)
        # No input supplied → treat as sparse
        return ClarificationDecision(
            needs_clarification=True,
            question="What is the primary goal of this project?",
            rationale="No PRD or brief was provided; cannot proceed without at least one goal.",
        )

    def _decide_from_prd(self, prd: PRD) -> ClarificationDecision:
        """Evaluate a full PRD."""
        fr_count = len(prd.functional_requirements)
        if fr_count >= 1 and prd.overview.strip():
            return ClarificationDecision(
                needs_clarification=False,
                question=None,
                rationale=(
                    f"PRD has {fr_count} functional requirement(s) and a non-empty overview; "
                    "sufficient to begin planning."
                ),
            )
        return ClarificationDecision(
            needs_clarification=True,
            question=(
                "Could you describe the primary functional requirement "
                "so we can begin planning?"
            ),
            rationale=(
                "PRD lacks functional requirements or overview; "
                "at least one is needed before planning."
            ),
        )

    def _decide_from_brief(self, brief: ProductBrief) -> ClarificationDecision:
        """Evaluate a lightweight ProductBrief."""
        goal_count = len(brief.goals)
        if goal_count >= 2:
            return ClarificationDecision(
                needs_clarification=False,
                question=None,
                rationale=(
                    f"Brief has {goal_count} goals; sufficient to proceed with PRD generation."
                ),
            )
        if goal_count == 1:
            return ClarificationDecision(
                needs_clarification=True,
                question=(
                    "Could you add a second goal or success criterion so we can "
                    "scope the solution properly?"
                ),
                rationale="Brief has only 1 goal; 2+ goals reduce ambiguity in PRD generation.",
            )
        return ClarificationDecision(
            needs_clarification=True,
            question="What are the primary goals this product should achieve?",
            rationale="Brief has no goals listed; cannot generate a meaningful PRD.",
        )


def _real_mode_available() -> bool:
    """Return True if a live LLM backend is configured."""
    return bool(
        os.environ.get("ANTHROPIC_API_KEY")
        or os.environ.get("OPENAI_API_KEY")
    )
