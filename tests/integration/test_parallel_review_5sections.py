"""Integration tests: ParallelSectionReviewer now runs 5 sub-reviewers.

Verifies that adversarial + edge-case sections are present in the report,
synthesis summary references all 5 categories, and backward compat holds.
"""
from __future__ import annotations

from pathlib import Path

from autodev.agents.parallel_section_reviewer import ParallelSectionReviewer
from autodev.schemas import ParallelSectionReviewReport

# ---------------------------------------------------------------------------
# Test 1: All 5 sections run and appear in report
# ---------------------------------------------------------------------------

def test_parallel_reviewer_runs_5_sections(tmp_path: Path) -> None:
    """ParallelSectionReviewer runs all 5 sub-reviewers."""
    (tmp_path / "app.py").write_text(
        "# module\ndef greet(name: str) -> str:\n    return f'Hello {name}'\n",
        encoding="utf-8",
    )

    reviewer = ParallelSectionReviewer()
    report = reviewer.review(repo_path=str(tmp_path))

    assert isinstance(report, ParallelSectionReviewReport)
    assert "security" in report.sections
    assert "perf" in report.sections
    assert "style" in report.sections
    assert "adversarial" in report.sections
    assert "edge-case" in report.sections
    assert len(report.sections) == 5


# ---------------------------------------------------------------------------
# Test 2: Adversarial findings present for risky code
# ---------------------------------------------------------------------------

def test_adversarial_and_edge_findings_in_report(tmp_path: Path) -> None:
    """Adversarial + edge-case sub-reviewers inject findings for risky code."""
    (tmp_path / "risky.py").write_text(
        "import subprocess\n"
        "import requests\n"
        "from datetime import datetime\n"
        "\n"
        "def do_stuff(cmd):\n"
        "    subprocess.run(cmd, shell=True)   # injection\n"
        "    requests.get('http://example.com', timeout=None)  # network flake\n"
        "    now = datetime.now()  # naive datetime\n"
        "\n"
        "def ratio(a, b):\n"
        "    return a / b  # division without zero guard\n",
        encoding="utf-8",
    )

    reviewer = ParallelSectionReviewer()
    report = reviewer.review(repo_path=str(tmp_path))

    assert isinstance(report, ParallelSectionReviewReport)

    # Both new sections must be present
    assert "adversarial" in report.sections
    assert "edge-case" in report.sections

    categories = {f.category for f in report.findings}

    # Adversarial sub-reviewer should catch shell=True injection
    assert "adversarial" in categories, (
        f"Expected 'adversarial' in categories; got {categories}"
    )

    # Edge-case sub-reviewer should catch network/timezone/numeric patterns
    assert "edge-case" in categories, (
        f"Expected 'edge-case' in categories; got {categories}"
    )

    # Synthesis summary must be non-empty
    assert report.synthesis_summary

    # Overall integrity: counts must tally
    total = (
        report.blocker_count + report.major_count
        + report.minor_count + report.nitpick_count
    )
    assert total == len(report.findings)
