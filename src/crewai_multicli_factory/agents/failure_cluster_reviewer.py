"""FailureClusterReviewer — auto-triggered when ≥ N tasks fail in a milestone.

Builds FAILURE_REVIEW.md text and calls OpusConsultAgent.reviewer for
cluster diagnosis.
"""
from __future__ import annotations

from ..schemas import ExecutionResult, FailureClusterReport
from .opus_consult import OpusConsultAgent

_MAX_ERROR_CHARS = 500


def _clip(s: str | None, max_chars: int = _MAX_ERROR_CHARS) -> str:
    if not s:
        return ""
    s = s.strip()
    return s if len(s) <= max_chars else s[:max_chars] + f"... [truncated, full={len(s)} chars]"


class FailureClusterReviewer:
    """Reviews a cluster of failed ExecutionResults via OpusConsultAgent."""

    def __init__(
        self,
        threshold: int = 2,
        agent: OpusConsultAgent | None = None,
    ) -> None:
        self.threshold = threshold
        self._agent = agent or OpusConsultAgent()

    def build_review_text(
        self,
        milestone_id: str,
        failed_results: list[ExecutionResult],
    ) -> str:
        lines = [
            "# Failure Cluster Review (auto-triggered)",
            "",
            f"Milestone: {milestone_id}",
            f"Failed tasks: {len(failed_results)}",
            "",
            "## Failed tasks",
            "",
        ]
        for r in failed_results:
            lines.append(f"- `{r.task_id}` exit_code={r.exit_code} error_type={r.error_type}")
            if r.stderr:
                lines.append(f"  stderr: {_clip(r.stderr)}")
            if r.stdout:
                lines.append(f"  stdout: {_clip(r.stdout)}")
        return "\n".join(lines) + "\n"

    def review(
        self,
        milestone_id: str,
        failed_results: list[ExecutionResult],
    ) -> FailureClusterReport:
        """Build a FailureClusterReport.  Always calls Opus when threshold is met."""
        failed_task_ids = [r.task_id for r in failed_results]
        review_text = self.build_review_text(milestone_id, failed_results)

        if len(failed_results) < self.threshold:
            return FailureClusterReport(
                milestone_id=milestone_id,
                failure_count=len(failed_results),
                failed_task_ids=failed_task_ids,
                review_text=review_text,
                opus_consulted=False,
            )

        opus_result = self._agent.reviewer(review_text)
        return FailureClusterReport(
            milestone_id=milestone_id,
            failure_count=len(failed_results),
            failed_task_ids=failed_task_ids,
            review_text=review_text,
            opus_consulted=True,
            opus_result=opus_result,
        )
