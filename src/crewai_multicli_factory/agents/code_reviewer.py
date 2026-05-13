"""Code Reviewer — checks task results vs. acceptance criteria."""
from __future__ import annotations

from ..schemas import (
    CodeReviewReport,
    DeliveryTask,
    ExecutionResult,
    GateStatus,
    Severity,
    SeverityFinding,
)
from ._crewai_bridge import make_agent

_SEVERITY_PREFIX = {
    Severity.BLOCKER: "[BLOCKER]",
    Severity.MAJOR: "[MAJOR]",
    Severity.MINOR: "[MINOR]",
    Severity.NITPICK: "[NITPICK]",
}


class CodeReviewerAgent:
    def __init__(self) -> None:
        self.agent = make_agent(
            role="Code Reviewer",
            goal="Check code quality, task completion, and test coverage signals.",
            backstory="A staff reviewer who reads diffs end-to-end.",
        )

    def review(self, *, tasks: list[DeliveryTask], results: list[ExecutionResult]) -> CodeReviewReport:
        findings: list[str] = []
        severity_findings: list[SeverityFinding] = []
        result_by_id = {r.task_id: r for r in results}
        for t in tasks:
            r = result_by_id.get(t.task_id)
            if r is None:
                sev = Severity.MAJOR
                msg = f"{t.task_id}: no execution result recorded"
                findings.append(f"{_SEVERITY_PREFIX[sev]} {msg}")
                severity_findings.append(SeverityFinding(
                    severity=sev,
                    category="correctness",
                    title="No execution result recorded",
                    detail=msg,
                    source_agent="CodeReviewerAgent",
                ))
                continue
            if not r.success:
                sev = Severity.BLOCKER
                msg = f"{t.task_id}: execution failed ({r.error_type})"
                findings.append(f"{_SEVERITY_PREFIX[sev]} {msg}")
                severity_findings.append(SeverityFinding(
                    severity=sev,
                    category="correctness",
                    title="Execution failed",
                    detail=msg,
                    source_agent="CodeReviewerAgent",
                ))
                continue
            if t.allowed_files and not r.changed_files and not r.mock_used:
                sev = Severity.MAJOR
                msg = f"{t.task_id}: no files changed but task expected outputs in {t.allowed_files}"
                findings.append(f"{_SEVERITY_PREFIX[sev]} {msg}")
                severity_findings.append(SeverityFinding(
                    severity=sev,
                    category="correctness",
                    title="No files changed but outputs expected",
                    detail=msg,
                    source_agent="CodeReviewerAgent",
                ))
            # acceptance criteria sanity
            if not t.acceptance_criteria:
                sev = Severity.MINOR
                msg = f"{t.task_id}: no acceptance criteria defined"
                findings.append(f"{_SEVERITY_PREFIX[sev]} {msg}")
                severity_findings.append(SeverityFinding(
                    severity=sev,
                    category="correctness",
                    title="No acceptance criteria defined",
                    detail=msg,
                    source_agent="CodeReviewerAgent",
                ))
        status = GateStatus.FAILED if any("failed" in f for f in findings) else GateStatus.PASSED
        return CodeReviewReport(
            findings=findings,
            coverage_summary="(no static coverage tool wired)",
            status=status,
            severity_findings=severity_findings,
        )
