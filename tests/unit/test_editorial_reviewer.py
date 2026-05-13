"""Tests for EditorialReviewer — prose and structure checks (BMAD-4)."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

from autodev.agents.editorial_reviewer import EditorialReviewer
from autodev.schemas import EditorialReport, Severity


# ---------------------------------------------------------------------------
# Prose checks
# ---------------------------------------------------------------------------

class TestTypo:
    def test_detects_common_typo(self):
        reviewer = EditorialReviewer()
        findings = reviewer.review_prose("We will recieve the package tomorrow.")
        checks = [f.check for f in findings]
        assert "typo" in checks

    def test_no_false_positive_on_correct_text(self):
        reviewer = EditorialReviewer()
        findings = reviewer.review_prose("We will receive the package tomorrow.")
        typo_findings = [f for f in findings if f.check == "typo"]
        assert len(typo_findings) == 0

    def test_multiple_typos_in_one_document(self):
        reviewer = EditorialReviewer()
        text = "The occurance of the seperate issue was definately noticed."
        findings = reviewer.review_prose(text)
        typo_findings = [f for f in findings if f.check == "typo"]
        assert len(typo_findings) >= 3


class TestPassiveVoice:
    def test_detects_excessive_passive(self):
        reviewer = EditorialReviewer()
        # All sentences passive → ratio = 1.0 >> 0.30
        text = (
            "The report was written by the team. "
            "The results were presented by the manager. "
            "The project was completed by the engineers. "
            "The document was reviewed by the committee."
        )
        findings = reviewer.review_prose(text)
        passive = [f for f in findings if f.check == "passive"]
        assert len(passive) == 1

    def test_no_passive_flag_when_active(self):
        reviewer = EditorialReviewer()
        text = "The team wrote the report. The manager presented the results. The engineers built the system."
        findings = reviewer.review_prose(text)
        passive = [f for f in findings if f.check == "passive"]
        assert len(passive) == 0


class TestLongSentence:
    def test_flags_long_sentence(self):
        reviewer = EditorialReviewer()
        long = " ".join(["word"] * 45) + "."
        findings = reviewer.review_prose(long)
        long_f = [f for f in findings if f.check == "long-sentence"]
        assert len(long_f) >= 1

    def test_no_flag_for_normal_sentence(self):
        reviewer = EditorialReviewer()
        text = "This is a normal sentence with just a few words."
        findings = reviewer.review_prose(text)
        long_f = [f for f in findings if f.check == "long-sentence"]
        assert len(long_f) == 0


# ---------------------------------------------------------------------------
# Structure checks
# ---------------------------------------------------------------------------

class TestMissingH1:
    def test_flags_missing_h1(self):
        reviewer = EditorialReviewer()
        text = "## Section 1\n\nSome text.\n\n### Sub-section\n\nMore text."
        findings = reviewer.review_structure(text)
        checks = [f.check for f in findings]
        assert "missing-h1" in checks

    def test_no_flag_when_h1_present(self):
        reviewer = EditorialReviewer()
        text = "# Title\n\n## Section 1\n\nSome text."
        findings = reviewer.review_structure(text)
        missing = [f for f in findings if f.check == "missing-h1"]
        assert len(missing) == 0


class TestHeadingLevelSkip:
    def test_flags_h1_to_h3_skip(self):
        reviewer = EditorialReviewer()
        text = "# Title\n\n### Jumped heading\n\nSome text."
        findings = reviewer.review_structure(text)
        skips = [f for f in findings if f.check == "heading-skip"]
        assert len(skips) >= 1

    def test_no_flag_for_sequential_headings(self):
        reviewer = EditorialReviewer()
        text = "# Title\n\n## Section\n\n### Subsection\n\nText."
        findings = reviewer.review_structure(text)
        skips = [f for f in findings if f.check == "heading-skip"]
        assert len(skips) == 0


class TestBrokenLink:
    def test_flags_broken_local_link(self):
        reviewer = EditorialReviewer()
        text = "# Doc\n\nSee [this file](nonexistent_file_that_does_not_exist.md) for details."
        findings = reviewer.review_structure(text)
        broken = [f for f in findings if f.check == "broken-link"]
        assert len(broken) >= 1

    def test_no_flag_for_http_link(self):
        reviewer = EditorialReviewer()
        text = "# Doc\n\nSee [this](https://example.com) for details."
        findings = reviewer.review_structure(text)
        broken = [f for f in findings if f.check == "broken-link"]
        assert len(broken) == 0

    def test_no_flag_for_existing_file(self, tmp_path):
        real_file = tmp_path / "real.md"
        real_file.write_text("hello")
        text = f"# Doc\n\nSee [real](real.md) for details."
        reviewer = EditorialReviewer()
        findings = reviewer.review_structure(text, file_path=str(tmp_path / "index.md"))
        broken = [f for f in findings if f.check == "broken-link"]
        assert len(broken) == 0


# ---------------------------------------------------------------------------
# review_doc (combined)
# ---------------------------------------------------------------------------

class TestReviewDoc:
    def test_passable_for_clean_doc(self):
        reviewer = EditorialReviewer()
        text = (
            "# Clean Document\n\n"
            "## Introduction\n\n"
            "This document describes the system.\n\n"
            "### Details\n\n"
            "Everything works as expected."
        )
        report = reviewer.review_doc(text)
        assert isinstance(report, EditorialReport)
        assert report.passable is True
        assert report.blocker_count == 0
        assert report.major_count == 0

    def test_not_passable_when_major_found(self):
        reviewer = EditorialReviewer()
        # No H1 → MAJOR → not passable
        text = "## Section\n\nSome text without an H1."
        report = reviewer.review_doc(text)
        assert report.passable is False
        assert report.major_count >= 1

    def test_file_path_stored_in_report(self):
        reviewer = EditorialReviewer()
        text = "# Title\n\nText."
        report = reviewer.review_doc(text, file_path="/tmp/test.md")
        assert report.file_path == "/tmp/test.md"
