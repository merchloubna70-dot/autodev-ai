"""Security Reviewer — static scan of generated/changed files."""
from __future__ import annotations

from pathlib import Path

from ..schemas import (
    GateStatus,
    PipelineRunState,
    RiskLevel,
    SecurityReviewReport,
    Severity,
    SeverityFinding,
)
from ..utils.command_safety import DEFAULT_DENYLIST
from ._crewai_bridge import make_agent


SECRET_PATTERNS = (
    "AKIA",            # AWS keys
    "-----BEGIN RSA",
    "-----BEGIN PRIVATE KEY",
    "AIzaSy",          # google api
    "ghp_",            # github pat
    "sk-",             # openai-ish
    "claude_api_key",
    "anthropic_api_key",
)

_SEVERITY_PREFIX = {
    Severity.BLOCKER: "[BLOCKER]",
    Severity.MAJOR: "[MAJOR]",
    Severity.MINOR: "[MINOR]",
    Severity.NITPICK: "[NITPICK]",
}


class SecurityReviewerAgent:
    def __init__(self) -> None:
        self.agent = make_agent(
            role="Security Reviewer",
            goal="Find unsafe shell, secrets, dangerous deps, missing input validation.",
            backstory="An AppSec engineer who blocks releases on critical findings.",
        )

    def review(self, *, repo_path: str, state: PipelineRunState | None = None) -> SecurityReviewReport:
        findings: list[str] = []
        severity_findings: list[SeverityFinding] = []
        blocked: list[str] = []
        severity = RiskLevel.LOW
        root = Path(repo_path)
        for p in root.rglob("*"):
            if not p.is_file():
                continue
            rel = str(p.relative_to(root))
            if any(skip in rel.split("/") for skip in ("target", "node_modules", ".dev-factory", ".git")):
                continue
            if p.stat().st_size > 1_500_000:
                continue
            try:
                text = p.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            for pat in DEFAULT_DENYLIST:
                if pat in text:
                    msg = f"{rel}: forbidden shell pattern {pat!r}"
                    sev = Severity.BLOCKER
                    findings.append(f"{_SEVERITY_PREFIX[sev]} {msg}")
                    severity_findings.append(SeverityFinding(
                        severity=sev,
                        category="security",
                        title=f"Forbidden shell pattern {pat!r}",
                        detail=msg,
                        file_path=rel,
                        source_agent="SecurityReviewerAgent",
                    ))
                    blocked.append(pat)
                    severity = max(severity, RiskLevel.HIGH, key=lambda r: ["low","medium","high","critical"].index(r.value))
            for pat in SECRET_PATTERNS:
                if pat in text:
                    msg = f"{rel}: possible secret pattern {pat!r}"
                    sev = Severity.BLOCKER
                    findings.append(f"{_SEVERITY_PREFIX[sev]} {msg}")
                    severity_findings.append(SeverityFinding(
                        severity=sev,
                        category="security",
                        title=f"Possible secret pattern {pat!r}",
                        detail=msg,
                        file_path=rel,
                        source_agent="SecurityReviewerAgent",
                    ))
                    severity = RiskLevel.CRITICAL
        status = GateStatus.PASSED
        if severity in (RiskLevel.HIGH, RiskLevel.CRITICAL):
            status = GateStatus.FAILED
        elif findings:
            status = GateStatus.PASSED  # findings but not severe
        return SecurityReviewReport(
            findings=findings,
            blocked_commands=sorted(set(blocked)),
            severity=severity,
            status=status,
            severity_findings=severity_findings,
        )
