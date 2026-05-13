"""Integration tests for ParallelSectionReviewer using RoundtableAgent.

Verifies that the migrated ParallelSectionReviewer:
1. Still produces a ParallelSectionReviewReport with a sections list.
2. Supports SeverityFinding extraction from synthesized text.
3. The existing test_parallel_section_review.py tests continue to pass
   (those tests import and run the reviewer directly).
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from autodev.agents.parallel_section_reviewer import (
    ParallelSectionReviewer,
    _extract_severity_findings_from_text,
)
from autodev.schemas import ParallelSectionReviewReport, Severity, SeverityFinding


# ---------------------------------------------------------------------------
# Test 1: ParallelSectionReviewer still produces ParallelSectionReviewReport
# ---------------------------------------------------------------------------

def test_parallel_section_reviewer_produces_report(tmp_path):
    """ParallelSectionReviewer returns a ParallelSectionReviewReport with sections."""
    (tmp_path / "app.py").write_text(
        "# TODO: fix this\n"
        "def run():\n"
        "    print('debug')\n"
    )

    reviewer = ParallelSectionReviewer()
    report = reviewer.review(repo_path=str(tmp_path))

    assert isinstance(report, ParallelSectionReviewReport)
    assert isinstance(report.sections, list)
    assert len(report.sections) >= 3
    assert "security" in report.sections
    assert "perf" in report.sections
    assert "style" in report.sections
    # synthesis_summary should be set (non-empty)
    assert report.synthesis_summary


# ---------------------------------------------------------------------------
# Test 2: SeverityFinding extraction from synth message works
# ---------------------------------------------------------------------------

def test_severity_finding_extraction_from_synth_text():
    """_extract_severity_findings_from_text correctly parses [SEVERITY:X] tagged lines."""
    synth_text = (
        "Review complete.\n"
        "- [SEVERITY:BLOCKER] SQL injection risk in login handler\n"
        "- [SEVERITY:MAJOR] Unbounded memory allocation in parser\n"
        "- [SEVERITY:MINOR] Missing input validation\n"
        "- [SEVERITY:NITPICK] Inconsistent naming conventions\n"
        "- This line has no severity tag and should be ignored\n"
    )

    findings = _extract_severity_findings_from_text(
        synth_text, category="synthesis", source_agent="test"
    )

    assert len(findings) == 4
    severities = {f.severity for f in findings}
    assert Severity.BLOCKER in severities
    assert Severity.MAJOR in severities
    assert Severity.MINOR in severities
    assert Severity.NITPICK in severities
    # All should have non-empty titles
    for f in findings:
        assert f.title.strip()


# ---------------------------------------------------------------------------
# Test 3: RoundtableAgent synthesis text is embedded in report
# ---------------------------------------------------------------------------

def test_roundtable_synth_flows_into_report(tmp_path):
    """RoundtableAgent synth output ends up in synthesis_summary of the report."""
    # File with patterns that trigger findings in all 3 reviewers
    (tmp_path / "messy.py").write_text(
        "import os\n"
        "# FIXME: remove this\n"
        "def run():\n"
        "    print('debug')\n"
        "    while True:\n"
        "        pass\n"
    )

    reviewer = ParallelSectionReviewer()
    report = reviewer.review(repo_path=str(tmp_path))

    assert isinstance(report, ParallelSectionReviewReport)
    # synthesis_summary must be non-empty
    assert report.synthesis_summary.strip()
    # Counts should be consistent
    total = (
        report.blocker_count
        + report.major_count
        + report.minor_count
        + report.nitpick_count
    )
    assert total == len(report.findings)
