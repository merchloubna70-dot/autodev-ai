"""ParallelSectionReviewer — runs security/perf/style sub-reviewers concurrently."""
from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor, as_completed

from ..adapters.opus_adapter import OpusAdapter
from ..schemas import (
    OpusConsultMode,
    ParallelSectionReviewReport,
    Severity,
    SeverityFinding,
)


# ---------------------------------------------------------------------------
# Sub-reviewer classes
# ---------------------------------------------------------------------------

class _SecuritySubReviewer:
    """Lightweight security sub-reviewer for parallel section review."""

    name = "security"

    def review(self, repo_path: str, results: list) -> list[SeverityFinding]:
        findings: list[SeverityFinding] = []
        try:
            from pathlib import Path

            root = Path(repo_path)
            _secret_patterns = ("AKIA", "-----BEGIN RSA", "-----BEGIN PRIVATE KEY",
                                 "ghp_", "sk-", "claude_api_key")
            for p in root.rglob("*"):
                if not p.is_file():
                    continue
                rel = str(p.relative_to(root))
                if any(s in rel.split("/") for s in ("target", "node_modules", ".git")):
                    continue
                if p.stat().st_size > 500_000:
                    continue
                try:
                    text = p.read_text(encoding="utf-8", errors="ignore")
                except Exception:
                    continue
                for pat in _secret_patterns:
                    if pat in text:
                        findings.append(SeverityFinding(
                            severity=Severity.BLOCKER,
                            category="security",
                            title=f"Secret pattern detected: {pat!r}",
                            detail=f"{rel}: possible secret {pat!r}",
                            file_path=rel,
                            source_agent="SecuritySubReviewer",
                        ))
        except Exception as exc:
            findings.append(SeverityFinding(
                severity=Severity.NITPICK,
                category="security",
                title="Security sub-review skipped",
                detail=str(exc),
                source_agent="SecuritySubReviewer",
            ))
        return findings


class _PerfSubReviewer:
    """Lightweight performance sub-reviewer for parallel section review."""

    name = "perf"

    _PERF_PATTERNS = (
        ("time.sleep(", "Blocking sleep in production code", Severity.MAJOR),
        ("SELECT *", "Unbounded SELECT * query", Severity.MAJOR),
        ("while True:", "Infinite loop without break guard", Severity.MINOR),
        (".read()", "Unbuffered file read", Severity.MINOR),
    )

    def review(self, repo_path: str, results: list) -> list[SeverityFinding]:
        findings: list[SeverityFinding] = []
        try:
            from pathlib import Path

            root = Path(repo_path)
            for p in root.rglob("*.py"):
                if not p.is_file():
                    continue
                rel = str(p.relative_to(root))
                if any(s in rel.split("/") for s in ("target", "node_modules", ".git")):
                    continue
                if p.stat().st_size > 500_000:
                    continue
                try:
                    text = p.read_text(encoding="utf-8", errors="ignore")
                except Exception:
                    continue
                for pattern, title, sev in self._PERF_PATTERNS:
                    if pattern in text:
                        findings.append(SeverityFinding(
                            severity=sev,
                            category="perf",
                            title=title,
                            detail=f"{rel}: contains {pattern!r}",
                            file_path=rel,
                            suggested_fix=f"Review usage of {pattern!r} for performance impact.",
                            source_agent="PerfSubReviewer",
                        ))
        except Exception as exc:
            findings.append(SeverityFinding(
                severity=Severity.NITPICK,
                category="perf",
                title="Perf sub-review skipped",
                detail=str(exc),
                source_agent="PerfSubReviewer",
            ))
        return findings


class _StyleSubReviewer:
    """Lightweight style sub-reviewer for parallel section review."""

    name = "style"

    _STYLE_PATTERNS = (
        ("except:", "Bare except clause", Severity.MINOR),
        ("print(", "Debug print statement", Severity.NITPICK),
        ("TODO", "Unresolved TODO comment", Severity.NITPICK),
        ("FIXME", "Unresolved FIXME comment", Severity.MINOR),
    )

    def review(self, repo_path: str, results: list) -> list[SeverityFinding]:
        findings: list[SeverityFinding] = []
        try:
            from pathlib import Path

            root = Path(repo_path)
            for p in root.rglob("*.py"):
                if not p.is_file():
                    continue
                rel = str(p.relative_to(root))
                if any(s in rel.split("/") for s in ("target", "node_modules", ".git")):
                    continue
                if p.stat().st_size > 500_000:
                    continue
                try:
                    text = p.read_text(encoding="utf-8", errors="ignore")
                except Exception:
                    continue
                for pattern, title, sev in self._STYLE_PATTERNS:
                    if pattern in text:
                        findings.append(SeverityFinding(
                            severity=sev,
                            category="style",
                            title=title,
                            detail=f"{rel}: contains {pattern!r}",
                            file_path=rel,
                            source_agent="StyleSubReviewer",
                        ))
        except Exception as exc:
            findings.append(SeverityFinding(
                severity=Severity.NITPICK,
                category="style",
                title="Style sub-review skipped",
                detail=str(exc),
                source_agent="StyleSubReviewer",
            ))
        return findings


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------

class ParallelSectionReviewer:
    """Runs security/perf/style sub-reviewers concurrently (max 3 threads).

    Synthesizer step uses OpusConsultAgent.reviewer in MOCK mode to merge and
    deduplicate findings into a coherent summary.
    """

    MAX_WORKERS = 3

    def __init__(self, adapter: OpusAdapter | None = None) -> None:
        self._sub_reviewers = [
            _SecuritySubReviewer(),
            _PerfSubReviewer(),
            _StyleSubReviewer(),
        ]
        self._adapter = adapter or OpusAdapter()

    def review(self, repo_path: str, results: list | None = None) -> ParallelSectionReviewReport:
        """Run all sub-reviewers concurrently and synthesize findings."""
        if results is None:
            results = []

        all_findings: list[SeverityFinding] = []
        sections_run: list[str] = []

        with ThreadPoolExecutor(max_workers=self.MAX_WORKERS) as executor:
            future_to_name = {
                executor.submit(sr.review, repo_path, results): sr.name
                for sr in self._sub_reviewers
            }
            for future in as_completed(future_to_name):
                name = future_to_name[future]
                sections_run.append(name)
                try:
                    sub_findings = future.result()
                    all_findings.extend(sub_findings)
                except Exception as exc:
                    all_findings.append(SeverityFinding(
                        severity=Severity.NITPICK,
                        category=name,
                        title=f"{name} sub-reviewer raised exception",
                        detail=str(exc),
                        source_agent="ParallelSectionReviewer",
                    ))

        # Deduplicate by (severity, category, title, file_path)
        seen: set[tuple] = set()
        deduped: list[SeverityFinding] = []
        for f in all_findings:
            key = (f.severity, f.category, f.title, f.file_path)
            if key not in seen:
                seen.add(key)
                deduped.append(f)

        # Synthesize via Opus (MOCK when FACTORY_FORCE_MOCK=1)
        synthesis_summary = self._synthesize(deduped)

        return ParallelSectionReviewReport(
            sections=sorted(sections_run),
            findings=deduped,
            synthesis_summary=synthesis_summary,
        )

    def _synthesize(self, findings: list[SeverityFinding]) -> str:
        """1-shot synthesis via OpusConsultAgent.reviewer (mock-safe)."""
        if not findings:
            return "No findings from any sub-reviewer."

        counts = {sev: 0 for sev in Severity}
        for f in findings:
            counts[f.severity] += 1

        summary_lines = [f"Total findings: {len(findings)}"]
        for sev in (Severity.BLOCKER, Severity.MAJOR, Severity.MINOR, Severity.NITPICK):
            if counts[sev]:
                summary_lines.append(f"  {sev.value}: {counts[sev]}")

        prompt = (
            "Parallel section review summary:\n"
            + "\n".join(summary_lines)
            + "\n\nCategories present: "
            + ", ".join(sorted({f.category for f in findings}))
            + "\n\nSynthesize and deduplicate the above into one paragraph."
        )

        try:
            result = self._adapter.consult(OpusConsultMode.REVIEWER, prompt)
            return result.response_text
        except Exception as exc:
            return f"Synthesis failed: {exc}. " + " | ".join(summary_lines)
