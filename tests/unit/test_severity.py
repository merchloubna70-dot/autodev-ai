"""Unit tests for Severity enum and SeverityFinding / ParallelSectionReviewReport schemas."""

from autodev.schemas import (
    ParallelSectionReviewReport,
    Severity,
    SeverityFinding,
)


def test_severity_enum_values():
    """All four severity levels exist and have correct string values."""
    assert Severity.BLOCKER == "blocker"
    assert Severity.MAJOR == "major"
    assert Severity.MINOR == "minor"
    assert Severity.NITPICK == "nitpick"


def test_severity_finding_minimal():
    """SeverityFinding can be created with minimal fields."""
    f = SeverityFinding(severity=Severity.MINOR, category="style", title="test title")
    assert f.severity == Severity.MINOR
    assert f.category == "style"
    assert f.file_path is None
    assert f.source_agent == ""


def test_parallel_report_count_validator():
    """ParallelSectionReviewReport _count validator populates counts correctly."""
    report = ParallelSectionReviewReport(
        sections=["security", "perf", "style"],
        findings=[
            SeverityFinding(severity=Severity.BLOCKER, category="security", title="x"),
            SeverityFinding(severity=Severity.MAJOR, category="perf", title="y"),
            SeverityFinding(severity=Severity.MINOR, category="style", title="z"),
            SeverityFinding(severity=Severity.NITPICK, category="style", title="w"),
            SeverityFinding(severity=Severity.BLOCKER, category="security", title="b2"),
        ],
    )
    assert report.blocker_count == 2
    assert report.major_count == 1
    assert report.minor_count == 1
    assert report.nitpick_count == 1


def test_parallel_report_empty_findings():
    """ParallelSectionReviewReport with no findings has all zero counts."""
    report = ParallelSectionReviewReport()
    assert report.findings == []
    assert report.blocker_count == 0
    assert report.major_count == 0
    assert report.minor_count == 0
    assert report.nitpick_count == 0


def test_severity_finding_all_fields():
    """SeverityFinding accepts all optional fields."""
    f = SeverityFinding(
        severity=Severity.BLOCKER,
        category="security",
        title="Secret detected",
        detail="file.py: contains ghp_xxx",
        file_path="src/file.py",
        line=42,
        suggested_fix="Remove the secret",
        source_agent="SecurityReviewerAgent",
    )
    assert f.line == 42
    assert f.suggested_fix == "Remove the secret"
    assert f.source_agent == "SecurityReviewerAgent"
