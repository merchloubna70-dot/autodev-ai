"""HumanReviewGate — pure-Python gate for human-in-the-loop review.

When enabled, this gate writes a ``pending_review.md`` file to the run
directory and either:
  (a) blocks (poll mode) until an ``approved`` or ``rejected`` file appears
      in the same directory, respecting a configurable timeout; or
  (b) returns immediately with decision="pending" (non-blocking mode).

Default mode is non-blocking. Tests MUST use non-blocking mode only.
"""
from __future__ import annotations

import time
from pathlib import Path

from ..schemas import HumanReviewDecision
from ..utils.logging import get_logger

_logger = get_logger("human_review_gate")

_POLL_INTERVAL = 0.5  # seconds between poll checks


class HumanReviewGate:
    """Gate that optionally pauses a pipeline awaiting a human decision."""

    def __init__(
        self,
        *,
        blocking: bool = False,
        timeout_seconds: float = 300.0,
    ) -> None:
        """
        Parameters
        ----------
        blocking:
            If False (default), return immediately with decision="pending"
            without waiting for an ``approved``/``rejected`` file.
        timeout_seconds:
            Maximum seconds to wait in blocking mode before returning with
            decision="pending".  Tests should use ≤5 s.
        """
        self.blocking = blocking
        self.timeout_seconds = timeout_seconds

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def request_review(
        self,
        *,
        run_dir: Path,
        summary: str = "",
        notes: str = "",
    ) -> HumanReviewDecision:
        """Write the pending_review.md and optionally wait for a decision.

        Parameters
        ----------
        run_dir:
            Path to the run directory (e.g. ``.dev-factory/runs/<run_id>/``).
        summary:
            Human-readable summary of what needs review.
        notes:
            Additional free-text notes to include in the review file.

        Returns
        -------
        HumanReviewDecision
            A model with ``decision`` set to "pending", "approved", or
            "rejected" depending on mode and poll outcome.
        """
        run_dir = Path(run_dir)
        run_dir.mkdir(parents=True, exist_ok=True)

        review_file = run_dir / "pending_review.md"
        approved_sentinel = run_dir / "approved"
        rejected_sentinel = run_dir / "rejected"

        # Write the review request file
        content_lines = [
            "# Pending Human Review",
            "",
            "## Summary",
            summary or "(no summary provided)",
            "",
        ]
        if notes:
            content_lines += ["## Notes", notes, ""]
        content_lines += [
            "## Instructions",
            f"To approve: `touch {approved_sentinel}`",
            f"To reject:  `touch {rejected_sentinel}`",
        ]
        review_file.write_text("\n".join(content_lines), encoding="utf-8")
        _logger.info("Pending review written to %s", review_file)

        decision_obj = HumanReviewDecision(
            decision="pending",
            notes=notes,
            pending_review_file=str(review_file),
        )

        if not self.blocking:
            return decision_obj

        # --- blocking poll mode ---
        deadline = time.monotonic() + self.timeout_seconds
        while time.monotonic() < deadline:
            if approved_sentinel.exists():
                _logger.info("Review approved (sentinel found)")
                decision_obj.decision = "approved"
                return decision_obj
            if rejected_sentinel.exists():
                _logger.info("Review rejected (sentinel found)")
                decision_obj.decision = "rejected"
                return decision_obj
            time.sleep(_POLL_INTERVAL)

        _logger.warning(
            "HumanReviewGate timed out after %.1f s; returning pending",
            self.timeout_seconds,
        )
        return decision_obj

    # ------------------------------------------------------------------
    # Convenience: check current state without blocking
    # ------------------------------------------------------------------

    @staticmethod
    def check(run_dir: Path) -> HumanReviewDecision:
        """Return the current decision state without writing or waiting."""
        run_dir = Path(run_dir)
        approved_sentinel = run_dir / "approved"
        rejected_sentinel = run_dir / "rejected"
        review_file = run_dir / "pending_review.md"

        if approved_sentinel.exists():
            return HumanReviewDecision(
                decision="approved",
                pending_review_file=str(review_file) if review_file.exists() else None,
            )
        if rejected_sentinel.exists():
            return HumanReviewDecision(
                decision="rejected",
                pending_review_file=str(review_file) if review_file.exists() else None,
            )
        return HumanReviewDecision(
            decision="pending",
            pending_review_file=str(review_file) if review_file.exists() else None,
        )
