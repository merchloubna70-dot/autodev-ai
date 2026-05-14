"""Tests for DocSharder."""
from __future__ import annotations

from pathlib import Path

from autodev.utils.doc_sharder import DocSharder

SMALL_DOC = "# Title\n\nShort content."

MULTI_H2_DOC = """# Big Doc

Preamble text before any heading.

## Section Alpha

Content for alpha section, with some details about this topic.

## Section Beta

Content for beta section, with different information entirely.

## Section Gamma

Final section with concluding remarks and additional context.
"""

MIXED_H2_H3_DOC = """# Mixed Doc

## Chapter One

Some text here.

### Sub-section 1.1

Details about 1.1.

### Sub-section 1.2

Details about 1.2.

## Chapter Two

More top-level content.
"""

SINGLE_H2_DOC = "## Only Section\n\n" + "x" * 3500


def _big_multi_h2() -> str:
    """Multi-H2 doc that exceeds 3000 chars."""
    body = "word " * 200  # ~1000 chars per section
    return (
        "# Big\n\n"
        f"## Alpha\n\n{body}\n\n"
        f"## Beta\n\n{body}\n\n"
        f"## Gamma\n\n{body}\n"
    )


class TestDocSharder:
    def test_under_threshold_no_shard(self, tmp_path: Path) -> None:
        sharder = DocSharder(threshold=3000)
        report = sharder.shard(SMALL_DOC, tmp_path, base_name="small")
        assert report.sharded is False
        assert report.shard_count == 0
        assert report.toc_path is None
        # No files written
        assert not (tmp_path / "small.md").exists()

    def test_single_h2_sharded(self, tmp_path: Path) -> None:
        sharder = DocSharder(threshold=100)
        report = sharder.shard(SINGLE_H2_DOC, tmp_path, base_name="single")
        assert report.sharded is True
        assert report.shard_count == 1
        assert report.toc_path is not None
        toc = Path(report.toc_path)
        assert toc.exists()
        toc_text = toc.read_text()
        assert "Only Section" in toc_text

    def test_multi_h2_shard_count(self, tmp_path: Path) -> None:
        doc = _big_multi_h2()
        sharder = DocSharder(threshold=3000)
        report = sharder.shard(doc, tmp_path, base_name="multi")
        assert report.sharded is True
        assert report.shard_count == 3
        shard_dir = tmp_path / "multi"
        assert shard_dir.is_dir()
        shard_files = list(shard_dir.glob("*.md"))
        assert len(shard_files) == 3
        # TOC references all sections
        toc_text = Path(report.toc_path).read_text()
        for title in ("Alpha", "Beta", "Gamma"):
            assert title in toc_text

    def test_mixed_h2_h3(self, tmp_path: Path) -> None:
        big_mixed = MIXED_H2_H3_DOC + ("extra " * 400)
        sharder = DocSharder(threshold=100)
        report = sharder.shard(big_mixed, tmp_path, base_name="mixed")
        assert report.sharded is True
        assert report.shard_count >= 2  # at least H2 sections
        levels = {e.level for e in report.shards}
        assert 2 in levels  # H2 sections included

    def test_idempotent_rerun(self, tmp_path: Path) -> None:
        doc = _big_multi_h2()
        sharder = DocSharder(threshold=3000)
        report1 = sharder.shard(doc, tmp_path, base_name="idem")
        report2 = sharder.shard(doc, tmp_path, base_name="idem")
        assert report1.shard_count == report2.shard_count
        assert report1.toc_path == report2.toc_path
        # Content unchanged on second run
        toc_text_1 = Path(report1.toc_path).read_text()
        toc_text_2 = Path(report2.toc_path).read_text()
        assert toc_text_1 == toc_text_2

    def test_shard_entries_have_correct_levels(self, tmp_path: Path) -> None:
        big_mixed = MIXED_H2_H3_DOC + ("pad " * 600)
        sharder = DocSharder(threshold=100)
        report = sharder.shard(big_mixed, tmp_path, base_name="levels")
        h2_entries = [e for e in report.shards if e.level == 2]
        h3_entries = [e for e in report.shards if e.level == 3]
        assert len(h2_entries) >= 1
        assert len(h3_entries) >= 1
        for entry in report.shards:
            assert entry.char_count > 0

    def test_source_chars_reported(self, tmp_path: Path) -> None:
        doc = _big_multi_h2()
        sharder = DocSharder(threshold=3000)
        report = sharder.shard(doc, tmp_path, base_name="chars")
        assert report.source_chars == len(doc)
