"""Integration tests for ParallelSectionReviewer."""


from autodev.agents.parallel_section_reviewer import ParallelSectionReviewer
from autodev.schemas import ParallelSectionReviewReport


def test_parallel_section_reviewer_runs_three_sections(tmp_path):
    """ParallelSectionReviewer runs all 3 sub-reviewers (security/perf/style)."""
    # Create a minimal Python file so reviewers have something to scan
    (tmp_path / "app.py").write_text("# empty module\ndef hello():\n    pass\n")

    reviewer = ParallelSectionReviewer()
    report = reviewer.review(repo_path=str(tmp_path))

    assert isinstance(report, ParallelSectionReviewReport)
    # All three sections should appear
    assert "security" in report.sections
    assert "perf" in report.sections
    assert "style" in report.sections
    assert len(report.sections) >= 3


def test_parallel_section_reviewer_merges_and_dedupes(tmp_path):
    """Synthesis produces a non-empty summary and findings are deduplicated."""
    # Create a file that triggers multiple patterns
    (tmp_path / "messy.py").write_text(
        "import os\n"
        "# TODO: fix this\n"
        "# FIXME: also this\n"
        "def run():\n"
        "    print('debug')\n"
        "    while True:\n"
        "        pass\n"
    )

    reviewer = ParallelSectionReviewer()
    report = reviewer.review(repo_path=str(tmp_path))

    assert isinstance(report, ParallelSectionReviewReport)
    # synthesis_summary should be populated
    assert report.synthesis_summary
    # Deduplication: no two findings should share the same (severity, category, title, file_path)
    seen: set = set()
    for f in report.findings:
        key = (f.severity, f.category, f.title, f.file_path)
        assert key not in seen, f"Duplicate finding detected: {key}"
        seen.add(key)
    # Total counts must add up
    total = report.blocker_count + report.major_count + report.minor_count + report.nitpick_count
    assert total == len(report.findings)
