"""Tests for Distillator."""
from __future__ import annotations

from autodev.adapters.distillator import Distillator, _sha256

LOREM = (
    "The quick brown fox jumps over the lazy dog. "
    "Pack my box with five dozen liquor jugs. "
    "How vexingly quick daft zebras jump. "
    "The five boxing wizards jump quickly. "
    "Sphinx of black quartz, judge my vow. "
)


def _large_text(n: int = 5) -> str:
    """Generate a text clearly longer than 600 chars."""
    para = (
        "Artificial intelligence systems have advanced rapidly in recent years. "
        "These systems can now perform tasks that once required human expertise. "
        "Natural language processing allows machines to understand and generate text. "
        "Machine learning algorithms improve with more training data over time. "
        "Deep neural networks form the backbone of modern AI applications. "
    )
    return para * n


class TestDistillator:
    def test_small_text_identity(self) -> None:
        d = Distillator()
        short = "Hello world. This is short."
        result = d.distill(short, target_chars=600)
        assert result.distilled_text == short
        assert result.ratio == 1.0
        assert result.source_chars == len(short)
        assert result.distilled_chars == len(short)

    def test_large_text_is_shorter(self) -> None:
        d = Distillator()
        text = _large_text(6)
        assert len(text) > 600
        result = d.distill(text, target_chars=600)
        assert result.distilled_chars <= len(text)
        assert result.ratio < 1.0
        assert result.distilled_text != ""

    def test_deterministic_same_sha_same_output(self) -> None:
        d = Distillator()
        text = _large_text(4)
        r1 = d.distill(text)
        r2 = d.distill(text)
        assert r1.distilled_text == r2.distilled_text
        assert r1.source_sha == r2.source_sha

    def test_sha_is_stable(self) -> None:
        d = Distillator()
        text = _large_text(3)
        r = d.distill(text)
        assert r.source_sha == _sha256(text)

    def test_ratio_sane(self) -> None:
        d = Distillator()
        text = _large_text(5)
        r = d.distill(text, target_chars=300)
        assert 0.0 < r.ratio <= 1.0
        assert r.distilled_chars == len(r.distilled_text)
        # ratio should be roughly consistent with char counts
        expected_ratio = r.distilled_chars / r.source_chars
        assert abs(r.ratio - round(expected_ratio, 4)) < 1e-3

    def test_reconstruct_contains_distilled_text(self) -> None:
        d = Distillator()
        text = _large_text(4)
        r = d.distill(text)
        recon = d.reconstruct(r)
        assert r.distilled_text in recon
        assert "RECONSTRUCTION NOTE" in recon
        assert r.source_sha in recon

    def test_verify_roundtrip(self) -> None:
        d = Distillator()
        text = _large_text(4)
        r = d.distill(text)
        check = d.verify_roundtrip(text, r)
        assert check["sha_match"] is True
        assert 0.0 < check["cosine_sim"] <= 1.0
        assert 0.0 < check["length_ratio"] <= 1.0

    def test_multi_doc_run_artifacts(self, tmp_path) -> None:
        d = Distillator()
        (tmp_path / "delivery").mkdir()
        (tmp_path / "delivery" / "final_report.md").write_text(_large_text(4))
        (tmp_path / "prd.md").write_text(_large_text(3))
        results = d.distill_run_artifacts(str(tmp_path))
        assert "final_report" in results
        assert "prd" in results
        for _key, r in results.items():
            assert r.source_chars > 0
            assert r.distilled_text != ""

    def test_run_artifacts_missing_files(self, tmp_path) -> None:
        """Missing artifact files are silently skipped."""
        d = Distillator()
        results = d.distill_run_artifacts(str(tmp_path))
        assert isinstance(results, dict)
        assert len(results) == 0

    def test_empty_text_handled(self) -> None:
        d = Distillator()
        r = d.distill("", target_chars=600)
        # Empty text ≤ threshold → identity path
        assert r.distilled_text == ""
        assert r.ratio == 1.0
