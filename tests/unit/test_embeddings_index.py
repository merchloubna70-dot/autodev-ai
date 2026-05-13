"""Tests for EmbeddingsIndex — deterministic in-memory TF-IDF."""
from __future__ import annotations

import pytest

from crewai_multicli_factory.adapters.embeddings_index import EmbeddingsIndex


class TestEmbeddingsIndex:
    def setup_method(self) -> None:
        self.idx = EmbeddingsIndex()

    def test_add_and_search_basic(self) -> None:
        self.idx.add("run-1", "doc-a", "the quick brown fox jumps over the lazy dog")
        self.idx.add("run-1", "doc-b", "a fast red car drives down the street")
        results = self.idx.search("quick fox", k=5)
        assert len(results) >= 1
        assert results[0]["text_id"] == "doc-a"

    def test_top_k_respected(self) -> None:
        for i in range(10):
            self.idx.add("run-1", f"doc-{i}", f"document {i} about python testing")
        results = self.idx.search("python testing", k=2)
        assert len(results) == 2

    def test_empty_index_returns_empty(self) -> None:
        results = self.idx.search("anything", k=5)
        assert results == []

    def test_same_input_same_output(self) -> None:
        self.idx.add("run-1", "a", "apple banana cherry date elderberry")
        self.idx.add("run-1", "b", "fig grape honeydew kiwi lemon")
        r1 = self.idx.search("apple cherry", k=3)
        r2 = self.idx.search("apple cherry", k=3)
        assert r1 == r2

    def test_result_fields_present(self) -> None:
        self.idx.add("run-x", "chunk-1", "hello world")
        results = self.idx.search("hello", k=1)
        assert len(results) == 1
        hit = results[0]
        assert "run_id" in hit
        assert "text_id" in hit
        assert "score" in hit
        assert "snippet" in hit

    def test_cross_run_search(self) -> None:
        self.idx.add("run-a", "d1", "machine learning neural network deep learning")
        self.idx.add("run-b", "d2", "regression analysis statistics data")
        self.idx.add("run-c", "d3", "deep learning transformer attention mechanism")
        results = self.idx.search("deep learning", k=2)
        text_ids = {r["text_id"] for r in results}
        assert "d1" in text_ids or "d3" in text_ids

    def test_score_is_float(self) -> None:
        self.idx.add("run-1", "x", "hello world foo bar")
        results = self.idx.search("hello", k=1)
        assert isinstance(results[0]["score"], float)

    def test_snippet_truncated(self) -> None:
        long_text = "word " * 100
        self.idx.add("run-1", "long", long_text)
        results = self.idx.search("word", k=1)
        assert len(results[0]["snippet"]) <= 200
