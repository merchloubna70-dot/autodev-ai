"""Integration Reviewer — cross-language contract + dependency drift."""
from __future__ import annotations

from ..gates.integration_gate import IntegrationGate
from ..schemas import (
    ApiContract,
    DependencyGraph,
    IntegrationReviewReport,
    Language,
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

# Map finding keywords to severity
def _infer_severity(finding: str) -> Severity:
    fl = finding.lower()
    if "[contractdiff] breaking" in fl or "breaking change" in fl:
        return Severity.BLOCKER
    if "[contractdiff]" in fl or "duplicate" in fl or "unknown node" in fl:
        return Severity.MAJOR
    if "cross-language" in fl:
        return Severity.MINOR
    return Severity.NITPICK


class IntegrationReviewerAgent:
    def __init__(self) -> None:
        self.gate = IntegrationGate()
        self.agent = make_agent(
            role="Integration Reviewer",
            goal="Detect API/contract/schema drift across modules and languages.",
            backstory="A platform engineer who watches the seams between services.",
        )

    def review(
        self,
        *,
        api_contract: ApiContract | None,
        dependency_graph: DependencyGraph | None,
        languages: list[Language],
    ) -> IntegrationReviewReport:
        report = self.gate.review(
            api_contract=api_contract,
            dependency_graph=dependency_graph,
            languages=[l.value for l in languages],
        )

        # Build severity_findings and prefix the findings strings
        severity_findings: list[SeverityFinding] = []
        prefixed: list[str] = []
        for f in report.findings:
            sev = _infer_severity(f)
            prefix = _SEVERITY_PREFIX[sev]
            prefixed.append(f"{prefix} {f}")
            severity_findings.append(SeverityFinding(
                severity=sev,
                category="integration",
                title=f[:80],
                detail=f,
                source_agent="IntegrationReviewerAgent",
            ))

        report.findings = prefixed
        report.severity_findings = severity_findings
        return report
