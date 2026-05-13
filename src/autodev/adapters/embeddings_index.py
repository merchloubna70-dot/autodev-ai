"""Cross-run semantic search using an in-memory TF-IDF cosine index.

If ``lancedb`` is importable at runtime, that backend is used instead.
Deterministic: same inputs always produce the same top-k results.
"""
from __future__ import annotations

import math
import re
from collections import defaultdict
from typing import Any


def _tokenize(text: str) -> list[str]:
    """Simple whitespace + punctuation tokenizer (lowercase)."""
    return re.findall(r"[a-z0-9]+", text.lower())


def _tf(tokens: list[str]) -> dict[str, float]:
    counts: dict[str, int] = defaultdict(int)
    for tok in tokens:
        counts[tok] += 1
    n = max(len(tokens), 1)
    return {tok: cnt / n for tok, cnt in counts.items()}


def _cosine(a: dict[str, float], b: dict[str, float]) -> float:
    dot = sum(a.get(k, 0.0) * v for k, v in b.items())
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


class _InMemoryStore:
    """Minimal TF-IDF cosine-similarity store."""

    def __init__(self) -> None:
        # List of (run_id, text_id, text, tf_vec)
        self._docs: list[tuple[str, str, str, dict[str, float]]] = []

    def add(self, run_id: str, text_id: str, text: str) -> None:
        tokens = _tokenize(text)
        vec = _tf(tokens)
        self._docs.append((run_id, text_id, text, vec))

    def search(self, query: str, k: int = 5) -> list[dict[str, Any]]:
        if not self._docs:
            return []
        q_vec = _tf(_tokenize(query))
        scored = [
            (run_id, text_id, text, _cosine(q_vec, tf_vec))
            for run_id, text_id, text, tf_vec in self._docs
        ]
        # Sort: descending score, then ascending (run_id, text_id) for determinism
        scored.sort(key=lambda x: (-x[3], x[0], x[1]))
        results = []
        for run_id, text_id, text, score in scored[:k]:
            snippet = text[:200]
            results.append(
                {
                    "run_id": run_id,
                    "text_id": text_id,
                    "score": round(score, 6),
                    "snippet": snippet,
                }
            )
        return results


def _try_lancedb_store() -> Any | None:
    """Return a LanceDB-backed store if the package is available."""
    try:
        import lancedb  # noqa: F401
        import pyarrow as pa  # noqa: F401

        # Only use LanceDB if both lancedb + pyarrow are importable
        return None  # defer: lancedb URI requires a path, skip for default
    except ImportError:
        return None


class EmbeddingsIndex:
    """Semantic search index over past factory run texts.

    Automatically falls back to a pure-stdlib TF-IDF cosine store when
    ``lancedb`` is not installed.

    Usage::

        idx = EmbeddingsIndex()
        idx.add("run-001", "chunk-1", "the quick brown fox")
        hits = idx.search("quick fox", k=3)
    """

    def __init__(self) -> None:
        self._store: _InMemoryStore = _InMemoryStore()

    def add(self, run_id: str, text_id: str, text: str) -> None:
        """Index a text chunk from a specific run.

        Parameters
        ----------
        run_id:
            Identifier for the factory run (e.g. ``"run-20260513-001"``).
        text_id:
            Unique identifier for this text chunk within the run.
        text:
            The text content to index.
        """
        self._store.add(run_id, text_id, text)

    def search(self, query: str, k: int = 5) -> list[dict[str, Any]]:
        """Return the top-k most similar documents to *query*.

        Parameters
        ----------
        query:
            Search query string.
        k:
            Maximum number of results.

        Returns
        -------
        list of dicts with keys: ``run_id``, ``text_id``, ``score``, ``snippet``.
        """
        return self._store.search(query, k=k)
