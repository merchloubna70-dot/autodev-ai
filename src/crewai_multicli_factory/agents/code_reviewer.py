"""Code Reviewer — checks task results vs. acceptance criteria."""
from __future__ import annotations

from ..schemas import CodeReviewReport, DeliveryTask, ExecutionResult, GateStatus
from ._crewai_bridge import make_agent


class CodeReviewerAgent:
    def __init__(self) -> None:
        self.agent = make_agent(
            role="Code Reviewer",
            goal="Check code quality, task completion, and test coverage signals.",
            backstory="A staff reviewer who reads diffs end-to-end.",
        )

    def review(self, *, tasks: list[DeliveryTask], results: list[ExecutionResult]) -> CodeReviewReport:
        findings: list[str] = []
        result_by_id = {r.task_id: r for r in results}
        for t in tasks:
            r = result_by_id.get(t.task_id)
            if r is None:
                findings.append(f"{t.task_id}: no execution result recorded")
                continue
            if not r.success:
                findings.append(f"{t.task_id}: execution failed ({r.error_type})")
                continue
            if t.allowed_files and not r.changed_files and not r.mock_used:
                findings.append(f"{t.task_id}: no files changed but task expected outputs in {t.allowed_files}")
            # acceptance criteria sanity
            if not t.acceptance_criteria:
                findings.append(f"{t.task_id}: no acceptance criteria defined")
        status = GateStatus.FAILED if any("failed" in f for f in findings) else GateStatus.PASSED
        return CodeReviewReport(findings=findings, coverage_summary="(no static coverage tool wired)", status=status)
