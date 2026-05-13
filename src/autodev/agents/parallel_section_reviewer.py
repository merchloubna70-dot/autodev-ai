"""ParallelSectionReviewer — runs security/perf/style/adversarial/edge-case
sub-reviewers concurrently.

Internal implementation now delegates to RoundtableAgent (BMAD party-mode via
A2A) while preserving the original public `.review(...)` API exactly.
"""
from __future__ import annotations

import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from ..schemas import (
    ParallelSectionReviewReport,
    Severity,
    SeverityFinding,
)

# ---------------------------------------------------------------------------
# Sub-reviewer helpers (kept as static scan functions — unchanged logic)
# ---------------------------------------------------------------------------

_SECRET_PATTERNS = ("AKIA", "-----BEGIN RSA", "-----BEGIN PRIVATE KEY",
                    "ghp_", "sk-", "claude_api_key")

_PERF_PATTERNS = (
    ("time.sleep(", "Blocking sleep in production code", Severity.MAJOR),
    ("SELECT *", "Unbounded SELECT * query", Severity.MAJOR),
    ("while True:", "Infinite loop without break guard", Severity.MINOR),
    (".read()", "Unbuffered file read", Severity.MINOR),
)

_STYLE_PATTERNS = (
    ("except:", "Bare except clause", Severity.MINOR),
    ("print(", "Debug print statement", Severity.NITPICK),
    ("TODO", "Unresolved TODO comment", Severity.NITPICK),
    ("FIXME", "Unresolved FIXME comment", Severity.MINOR),
)

_SKIP_DIRS = {"target", "node_modules", ".git"}
_MAX_FILE_SIZE = 500_000


def _should_skip(rel: str) -> bool:
    return any(s in rel.split("/") for s in _SKIP_DIRS)


def _scan_security(repo_path: str, results: list) -> list[SeverityFinding]:
    findings: list[SeverityFinding] = []
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
            for pat in _SECRET_PATTERNS:
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


def _scan_perf(repo_path: str, results: list) -> list[SeverityFinding]:
    findings: list[SeverityFinding] = []
    try:
        root = Path(repo_path)
        for p in root.rglob("*.py"):
            if not p.is_file():
                continue
            rel = str(p.relative_to(root))
            if _should_skip(rel) or p.stat().st_size > _MAX_FILE_SIZE:
                continue
            try:
                text = p.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            for pattern, title, sev in _PERF_PATTERNS:
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


def _scan_style(repo_path: str, results: list) -> list[SeverityFinding]:
    findings: list[SeverityFinding] = []
    try:
        root = Path(repo_path)
        for p in root.rglob("*.py"):
            if not p.is_file():
                continue
            rel = str(p.relative_to(root))
            if _should_skip(rel) or p.stat().st_size > _MAX_FILE_SIZE:
                continue
            try:
                text = p.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            for pattern, title, sev in _STYLE_PATTERNS:
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


# Severity tag extraction regex: [SEVERITY:BLOCKER], [SEVERITY:MAJOR], etc.
_SEV_RE = re.compile(
    r"\[SEVERITY[:\s]*(BLOCKER|MAJOR|MINOR|NITPICK)\]",
    re.IGNORECASE,
)


def _extract_severity_findings_from_text(
    text: str,
    category: str = "synthesis",
    source_agent: str = "RoundtableSynthesizer",
) -> list[SeverityFinding]:
    """Extract SeverityFinding objects from [SEVERITY:X] tagged lines."""
    findings: list[SeverityFinding] = []
    for line in text.splitlines():
        m = _SEV_RE.search(line)
        if m:
            sev_str = m.group(1).upper()
            try:
                sev = Severity[sev_str]
            except KeyError:
                sev = Severity.NITPICK
            title = _SEV_RE.sub("", line).strip(" -:[]").strip()
            if title:
                findings.append(SeverityFinding(
                    severity=sev,
                    category=category,
                    title=title[:200],
                    detail=line.strip(),
                    source_agent=source_agent,
                ))
    return findings


# ---------------------------------------------------------------------------
# Adversarial + EdgeCase sub-reviewer shims
# (lazy-import to avoid circular deps; fall back gracefully on ImportError)
# ---------------------------------------------------------------------------

def _scan_adversarial(repo_path: str, results: list) -> list[SeverityFinding]:
    try:
        from .adversarial_reviewer import AdversarialReviewer
        return AdversarialReviewer().review(repo_path, results)
    except Exception as exc:
        return [SeverityFinding(
            severity=Severity.NITPICK,
            category="adversarial",
            title="Adversarial sub-review skipped",
            detail=str(exc),
            source_agent="AdversarialReviewer",
        )]


def _scan_edge_case(repo_path: str, results: list) -> list[SeverityFinding]:
    try:
        from .edge_case_hunter import EdgeCaseHunter
        return EdgeCaseHunter().review(repo_path, results)
    except Exception as exc:
        return [SeverityFinding(
            severity=Severity.NITPICK,
            category="edge-case",
            title="EdgeCase sub-review skipped",
            detail=str(exc),
            source_agent="EdgeCaseHunter",
        )]


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------

class ParallelSectionReviewer:
    """Runs security/perf/style/adversarial/edge-case sub-reviewers concurrently.

    Internally delegates to RoundtableAgent (BMAD party-mode via A2A) for the
    synthesis step.  The file-scan sub-reviewers remain the same static scan
    functions; only synthesis is now routed through the roundtable.

    Public API is fully preserved: ``review(repo_path, results) -> ParallelSectionReviewReport``.
    """

    MAX_WORKERS = 5

    def __init__(self, roundtable=None) -> None:
        # Lazy import to handle A2A-1 not yet committed
        self._roundtable = roundtable  # injected (tests / DI)

    def _get_roundtable(self):
        if self._roundtable is not None:
            return self._roundtable
        try:
            from .roundtable import RoundtableAgent
            return RoundtableAgent()
        except Exception:
            return None

    def review(self, repo_path: str, results: list | None = None) -> ParallelSectionReviewReport:
        """Run all sub-reviewers concurrently and synthesize findings."""
        if results is None:
            results = []

        # --- Phase 1: Parallel file scans (unchanged behaviour) ---
        all_findings: list[SeverityFinding] = []
        sections_run: list[str] = []

        scan_jobs = [
            ("security", _scan_security),
            ("perf", _scan_perf),
            ("style", _scan_style),
            ("adversarial", _scan_adversarial),
            ("edge-case", _scan_edge_case),
        ]

        with ThreadPoolExecutor(max_workers=self.MAX_WORKERS) as executor:
            future_to_name = {
                executor.submit(fn, repo_path, results): name
                for name, fn in scan_jobs
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

        # --- Phase 2: Synthesis via RoundtableAgent ---
        synthesis_summary = self._synthesize_via_roundtable(deduped, repo_path)

        return ParallelSectionReviewReport(
            sections=sorted(sections_run),
            findings=deduped,
            synthesis_summary=synthesis_summary,
        )

    def _synthesize_via_roundtable(
        self,
        findings: list[SeverityFinding],
        repo_path: str,
    ) -> str:
        """Synthesize via RoundtableAgent; fall back to local summary on error."""
        if not findings:
            return "No findings from any sub-reviewer."

        counts = {sev: 0 for sev in Severity}
        for f in findings:
            counts[f.severity] += 1

        summary_lines = [f"Total findings: {len(findings)}"]
        for sev in (Severity.BLOCKER, Severity.MAJOR, Severity.MINOR, Severity.NITPICK):
            if counts[sev]:
                summary_lines.append(f"  {sev.value}: {counts[sev]}")

        topic = "Parallel section review: synthesize security/perf/style/adversarial/edge-case findings"
        context = (
            "Parallel section review summary:\n"
            + "\n".join(summary_lines)
            + "\n\nCategories present: "
            + ", ".join(sorted({f.category for f in findings}))
            + "\n\nTop findings:\n"
            + "\n".join(
                f"  [{f.severity.value}] [{f.category}] {f.title}"
                for f in findings[:10]
            )
        )

        try:
            rt = self._get_roundtable()
            if rt is None:
                return self._local_summary(summary_lines, findings)

            _conversation, synth_msg = rt.discuss_and_synthesize(
                topic=topic,
                context=context,
                needed_skills=["security", "perf", "style", "adversarial", "edge-case"],
                min_participants=2,
                max_participants=4,
            )

            from ..schemas import A2AMessage
            if isinstance(synth_msg, A2AMessage):
                parts_text = []
                for part in synth_msg.parts:
                    if part.kind == "text" and part.text:
                        parts_text.append(part.text)
                text = "\n".join(parts_text).strip()
                if text:
                    return text

            return self._local_summary(summary_lines, findings)

        except Exception as exc:
            return f"Synthesis via roundtable failed: {exc}. " + " | ".join(summary_lines)

    @staticmethod
    def _local_summary(summary_lines: list[str], findings: list[SeverityFinding]) -> str:
        cats = sorted({f.category for f in findings})
        return (
            " | ".join(summary_lines)
            + f" | Categories: {', '.join(cats)}"
        )
