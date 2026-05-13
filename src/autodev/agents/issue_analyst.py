"""Parse GitHub Issues / local issue files into IssueRequirements."""
from __future__ import annotations

import re

from ..adapters.github_adapter import GitHubAdapter
from ..schemas import IssueRequirements, RiskLevel
from ._crewai_bridge import make_agent


class IssueAnalystAgent:
    def __init__(self) -> None:
        self.gh = GitHubAdapter()
        self.agent = make_agent(
            role="Issue Analyst",
            goal="Convert a free-form issue into a structured IssueRequirements object.",
            backstory="A staff engineer who turns vague tickets into testable acceptance criteria.",
        )

    def parse(self, text: str, *, issue_id: str = "ISSUE-0") -> IssueRequirements:
        if text.lstrip().startswith("{"):
            payload = self.gh.parse_issue_json(text)
        else:
            payload = self.gh.parse_issue_text(text, fallback_id=issue_id)
        ac = self._extract_acceptance(text)
        impacted = self._extract_impacted_areas(text)
        risk = RiskLevel.MEDIUM if any(t in text.lower() for t in ("security", "auth", "rce", "crash", "data loss")) else RiskLevel.LOW
        return IssueRequirements(
            issue_id=payload.issue_id,
            title=payload.title,
            summary=self._first_paragraph(payload.body),
            raw_text=text,
            acceptance_criteria=ac,
            impacted_areas=impacted,
            labels=payload.labels,
            risk_level=risk,
        )

    def _extract_acceptance(self, text: str) -> list[str]:
        out: list[str] = []
        in_ac = False
        for line in text.splitlines():
            if re.match(r"#+\s*acceptance", line, re.IGNORECASE):
                in_ac = True
                continue
            if in_ac:
                if line.startswith("#"):
                    in_ac = False
                    continue
                bullet = re.match(r"\s*[-*]\s+(.*)", line)
                if bullet:
                    out.append(bullet.group(1).strip())
        return out

    def _extract_impacted_areas(self, text: str) -> list[str]:
        m = re.search(r"impacted\s*areas?:\s*([^\n]+)", text, re.IGNORECASE)
        if not m:
            return []
        return [tok.strip() for tok in re.split(r"[,;]+", m.group(1)) if tok.strip()]

    def _first_paragraph(self, body: str) -> str:
        body = body.strip()
        return body.split("\n\n")[0][:600] if body else ""
