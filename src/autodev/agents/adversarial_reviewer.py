"""AdversarialReviewer — assumes malicious user/input; finds abuse paths.

Runs a static heuristic scan over the repo and emits AdversarialFinding /
SeverityFinding objects per W4 taxonomy (blocker/major/minor/nitpick).
Also exposes as_agent_card() for registration in AgentRoster.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

from ..schemas import (
    AdversarialFinding,
    AgentCard,
    Severity,
    SeverityFinding,
)

# ---------------------------------------------------------------------------
# Heuristic patterns: (regex_or_literal, is_regex, attack_vector, title, sev)
# ---------------------------------------------------------------------------

_ABUSE_PATTERNS: list[tuple[str, bool, str, str, Severity]] = [
    # Auth bypass
    ("if.*==.*True.*:.*#.*noauth", True, "auth-bypass",
     "Hardcoded auth bypass comment", Severity.BLOCKER),
    ("verify=False", False, "auth-bypass",
     "SSL verification disabled", Severity.BLOCKER),
    ("allow_all.*=.*True", True, "auth-bypass",
     "Permissive allow_all flag", Severity.MAJOR),
    ("@app.route.*methods.*['\"]GET['\"].*no.*auth", True, "auth-bypass",
     "Unauthenticated GET route pattern", Severity.MAJOR),
    # Injection
    ("execute(.*%.*)", True, "injection",
     "String-interpolated SQL execute", Severity.BLOCKER),
    ("cursor.execute.*format(", False, "injection",
     "SQL execute with .format() — injection risk", Severity.BLOCKER),
    ("subprocess.*shell=True", True, "injection",
     "subprocess shell=True — command injection", Severity.BLOCKER),
    ("eval(", False, "injection",
     "eval() — code injection risk", Severity.BLOCKER),
    ("exec(", False, "injection",
     "exec() — code injection risk", Severity.MAJOR),
    ("os.system(", False, "injection",
     "os.system() — shell injection risk", Severity.MAJOR),
    # Dangerous defaults
    ("DEBUG.*=.*True", True, "dangerous-defaults",
     "DEBUG=True in production code", Severity.MAJOR),
    ("SECRET_KEY.*=.*['\"].*['\"]", True, "dangerous-defaults",
     "Hardcoded SECRET_KEY", Severity.BLOCKER),
    ("password.*=.*['\"][^'\"]{1,20}['\"]", True, "dangerous-defaults",
     "Hardcoded password literal", Severity.BLOCKER),
    # Wide CORS
    ("Access-Control-Allow-Origin.*\\*", True, "dangerous-defaults",
     "Wildcard CORS Allow-Origin header", Severity.MAJOR),
    ("origins.*=.*['\"]\\*['\"]", True, "dangerous-defaults",
     "CORS origins set to wildcard", Severity.MAJOR),
    # Race conditions
    ("time.sleep.*lock", True, "race",
     "Sleep inside lock — potential deadlock/race", Severity.MINOR),
    ("global.*counter", True, "race",
     "Global mutable counter — race under concurrency", Severity.MINOR),
    # Supply chain
    ("import.*from.*http://", True, "supply-chain",
     "HTTP (non-HTTPS) import URL", Severity.BLOCKER),
    ("--extra-index-url.*http://", True, "supply-chain",
     "Non-HTTPS extra-index-url", Severity.MAJOR),
]

_SKIP_DIRS = {"target", "node_modules", ".git", "__pycache__", ".venv", "venv"}
_MAX_FILE_SIZE = 500_000


def _should_skip(rel: str) -> bool:
    return any(s in rel.split("/") for s in _SKIP_DIRS)


class AdversarialReviewer:
    """Heuristic adversarial reviewer.

    Usage::

        reviewer = AdversarialReviewer()
        findings = reviewer.review("/path/to/repo", results=[])

    Also usable as an AgentCard for roster registration::

        card = AdversarialReviewer.as_agent_card()
    """

    SOURCE_AGENT = "AdversarialReviewer"

    def review(
        self,
        repo_path: str,
        results: list | None = None,
    ) -> list[SeverityFinding]:
        """Scan *repo_path* for adversarial / abuse patterns.

        Returns a flat list of SeverityFinding (for ParallelSectionReviewer
        compatibility) derived from detected AdversarialFinding objects.
        """
        adversarial_findings = self._scan(repo_path)
        return [
            af.severity_finding
            for af in adversarial_findings
            if af.severity_finding is not None
        ]

    def review_adversarial(
        self,
        repo_path: str,
        results: list | None = None,
    ) -> list[AdversarialFinding]:
        """Return rich AdversarialFinding objects."""
        return self._scan(repo_path)

    def _scan(self, repo_path: str) -> list[AdversarialFinding]:
        findings: list[AdversarialFinding] = []
        try:
            root = Path(repo_path)
            for p in root.rglob("*"):
                if not p.is_file():
                    continue
                rel = str(p.relative_to(root))
                if _should_skip(rel) or p.stat().st_size > _MAX_FILE_SIZE:
                    continue
                try:
                    text = p.read_text(encoding="utf-8", errors="ignore")
                except Exception:
                    continue
                for pat, is_regex, attack_vector, title, sev in _ABUSE_PATTERNS:
                    matched = (
                        bool(re.search(pat, text, re.IGNORECASE))
                        if is_regex
                        else pat in text
                    )
                    if matched:
                        sf = SeverityFinding(
                            severity=sev,
                            category="adversarial",
                            title=title,
                            detail=f"{rel}: matched pattern for {attack_vector!r}",
                            file_path=rel,
                            suggested_fix=f"Review {attack_vector} risk in {rel}",
                            source_agent=self.SOURCE_AGENT,
                        )
                        findings.append(AdversarialFinding(
                            attack_vector=attack_vector,
                            abuse_path=f"{rel}: {title}",
                            mitigation_hint=sf.suggested_fix or "",
                            severity_finding=sf,
                        ))
        except Exception as exc:
            sf = SeverityFinding(
                severity=Severity.NITPICK,
                category="adversarial",
                title="Adversarial scan skipped",
                detail=str(exc),
                source_agent=self.SOURCE_AGENT,
            )
            findings.append(AdversarialFinding(
                attack_vector="scan-error",
                abuse_path=str(exc),
                severity_finding=sf,
            ))
        return findings

    @staticmethod
    def as_agent_card() -> AgentCard:
        """Return an AgentCard describing this reviewer for roster registration."""
        return AgentCard(
            name="adversarial",
            description=(
                "Adversarial reviewer: assumes malicious user/input. "
                "Finds auth bypass, injection, dangerous defaults, race conditions, supply-chain risks."
            ),
            capabilities=[
                "adversarial-review", "abuse-path-analysis", "threat-modeling",
                "injection-detection", "auth-bypass-detection",
            ],
            skills=[
                "auth-bypass", "injection", "dangerous-defaults",
                "race-conditions", "supply-chain", "cors-review",
            ],
            transport="local-shell",
            model_hint="opus",
            system_prompt=(
                "You are an adversarial security reviewer on a non-interactive hotline. "
                "Assume all inputs are malicious. Find auth bypass paths, injection vectors, "
                "dangerous defaults, race conditions, and supply-chain risks. "
                "Emit findings tagged [SEVERITY:BLOCKER/MAJOR/MINOR/NITPICK]. "
                "Each finding: attack_vector, abuse_path, mitigation_hint. Output in English."
            ),
            tags=["security", "adversarial", "review"],
        )
