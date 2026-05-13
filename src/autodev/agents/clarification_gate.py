"""ClarificationGate — decides whether clarification is needed before planning.

In mock / dry-run mode the decision is fully deterministic:
- Full-spec PRDs (goals >= 2) → no clarification needed.
- Sparse PRDs (goals < 2)    → needs clarification; emits exactly one question.

In real mode (future) this would call the Opus architect to generate the
question from the PRD context.

BMAD-style 3-round elicitation (added in BMAD-4):
- round1_diverge  → up to 5 follow-up questions
- round2_converge → categorise each answer as must/nice/deferred
- round3_commit   → return updated PRD with added FRs + ACs
"""
from __future__ import annotations

import copy
import os
from typing import Any

from ..schemas import (
    AcceptanceCriterion,
    ClarificationDecision,
    ClarificationRound,
    ClarificationTranscript,
    FunctionalRequirement,
    PRD,
    ProductBrief,
)


class ClarificationGate:
    """Decide if a planning session needs clarification before proceeding.

    The gate asks at most one question and is deterministic in mock mode so
    that tests are stable without network access.

    3-round BMAD elicitation is available via ``round1_diverge``,
    ``round2_converge``, and ``round3_commit``.
    """

    # ------------------------------------------------------------------
    # Original API (backward-compat)
    # ------------------------------------------------------------------

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
    # 3-round BMAD elicitation
    # ------------------------------------------------------------------

    def round1_diverge(
        self,
        prd: PRD | None = None,
        brief: ProductBrief | None = None,
    ) -> list[str]:
        """Emit up to 5 follow-up questions to surface ambiguities.

        Deterministic in mock mode (FACTORY_FORCE_MOCK=1).
        """
        questions: list[str] = []

        if prd is not None:
            fr_count = len(prd.functional_requirements)
            ac_count = len(prd.acceptance_criteria)
            if fr_count == 0:
                questions.append(
                    "What are the primary functional requirements for this product?"
                )
            if ac_count == 0:
                questions.append(
                    "How will we measure success? Please provide at least one acceptance criterion."
                )
            if not prd.overview.strip():
                questions.append(
                    "Can you provide a brief overview / executive summary of the product?"
                )
            if not prd.risks:
                questions.append(
                    "Are there known risks or constraints we should capture?"
                )
            if not prd.out_of_scope:
                questions.append(
                    "What is explicitly out of scope for this release?"
                )
        elif brief is not None:
            if len(brief.goals) == 0:
                questions.append("What are the primary goals this product should achieve?")
            if len(brief.goals) < 2:
                questions.append(
                    "Can you add a second goal or success criterion to reduce ambiguity?"
                )
            questions.append("Who is the primary target user for this product?")
            questions.append("What is the desired timeline / milestone for the first release?")
            questions.append("Are there any regulatory or compliance constraints to be aware of?")
        else:
            questions = [
                "What is the primary goal of this project?",
                "Who are the intended end-users?",
                "What does a successful outcome look like?",
                "Are there hard technical constraints (language, platform, budget)?",
                "What is explicitly out of scope?",
            ]

        return questions[:5]

    def round2_converge(
        self,
        prd: PRD | None = None,
        brief: ProductBrief | None = None,
        round1_answers: dict[str, str] | None = None,
    ) -> dict[str, str]:
        """Categorise each round-1 answer as 'must-have'/'nice-to-have'/'deferred'.

        Deterministic heuristic in mock mode:
        - Answers that contain 'must', 'required', 'critical', 'essential'
          → 'must-have'
        - Answers that contain 'nice', 'optional', 'later', 'future', 'deferred'
          → 'deferred'
        - Everything else → 'nice-to-have'
        """
        if round1_answers is None:
            round1_answers = {}

        decisions: dict[str, str] = {}
        for question, answer in round1_answers.items():
            low = answer.lower()
            if any(kw in low for kw in ("must", "required", "critical", "essential")):
                decisions[question] = "must-have"
            elif any(kw in low for kw in ("nice", "optional", "later", "future", "deferred")):
                decisions[question] = "deferred"
            else:
                decisions[question] = "nice-to-have"
        return decisions

    def round3_commit(
        self,
        prd: PRD | None = None,
        brief: ProductBrief | None = None,
        decisions: dict[str, str] | None = None,
    ) -> PRD:
        """Return updated PRD with new FRs + ACs derived from must-have decisions.

        For each question whose decision is 'must-have', a new FunctionalRequirement
        and AcceptanceCriterion are added to the PRD.

        If *prd* is None a minimal stub PRD is created.
        """
        if decisions is None:
            decisions = {}

        # Build a working copy of the PRD (or a minimal stub)
        if prd is not None:
            updated = prd.model_copy(deep=True)
        else:
            product_name = (brief.name if brief and hasattr(brief, "name") else "Unknown Product")
            overview = (
                " ".join(brief.goals) if brief and brief.goals else "Auto-generated overview."
            )
            updated = PRD(product_name=product_name, overview=overview)

        must_items = {q: d for q, d in decisions.items() if d == "must-have"}

        for idx, (question, _) in enumerate(must_items.items(), start=1):
            fr_id = f"clarify-fr-{len(updated.functional_requirements) + 1:03d}"
            updated.functional_requirements.append(
                FunctionalRequirement(
                    id=fr_id,
                    title=f"Clarification requirement {idx}",
                    description=f"Derived from clarification: {question}",
                    priority="must-have",
                )
            )
            ac_id = f"clarify-ac-{len(updated.acceptance_criteria) + 1:03d}"
            updated.acceptance_criteria.append(
                AcceptanceCriterion(
                    id=ac_id,
                    description=f"Acceptance criterion for: {question}",
                    verifiable_by="manual",
                )
            )

        return updated

    def run_3round(
        self,
        prd: PRD | None = None,
        brief: ProductBrief | None = None,
        round1_answers: dict[str, str] | None = None,
    ) -> tuple[PRD, ClarificationTranscript]:
        """Convenience wrapper that runs all 3 rounds and returns updated PRD + transcript.

        ``round1_answers`` maps question → answer text.  If not provided, empty
        answers are used (deterministic / all → 'nice-to-have').
        """
        if round1_answers is None:
            round1_answers = {}

        questions = self.round1_diverge(prd=prd, brief=brief)
        answers_for_asked = {q: round1_answers.get(q, "") for q in questions}

        decisions = self.round2_converge(
            prd=prd, brief=brief, round1_answers=answers_for_asked
        )

        round1 = ClarificationRound(
            round_index=1,
            questions=questions,
            answers=answers_for_asked,
        )
        round2 = ClarificationRound(
            round_index=2,
            questions=questions,
            answers=answers_for_asked,
            decisions=decisions,
        )

        updated_prd = self.round3_commit(prd=prd, brief=brief, decisions=decisions)

        must_items = [q for q, d in decisions.items() if d == "must-have"]
        final_changes = [
            f"Added FR + AC from must-have: {q}" for q in must_items
        ]

        round3 = ClarificationRound(
            round_index=3,
            questions=[],
            answers={},
            decisions=decisions,
        )

        transcript = ClarificationTranscript(
            rounds=[round1, round2, round3],
            final_changes=final_changes,
        )

        return updated_prd, transcript

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
