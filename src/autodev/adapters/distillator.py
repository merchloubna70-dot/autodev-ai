"""Distillator: TF-IDF sentence-level compression for large run-state docs.

Pure stdlib — no new pip dependencies.
"""
from __future__ import annotations

import hashlib
import math
import os
import re
from collections import defaultdict

from ..schemas import DistillResult

_SENT_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")
_TOKEN_RE = re.compile(r"[a-z0-9]+")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


def _split_sentences(text: str) -> list[str]:
    """Split text into sentences on whitespace after terminal punctuation."""
    raw = _SENT_SPLIT_RE.split(text.strip())
    return [s.strip() for s in raw if s.strip()]


def _tf(tokens: list[str]) -> dict[str, float]:
    counts: dict[str, int] = defaultdict(int)
    for tok in tokens:
        counts[tok] += 1
    n = max(len(tokens), 1)
    return {tok: cnt / n for tok, cnt in counts.items()}


def _idf(sentences: list[list[str]]) -> dict[str, float]:
    """Compute IDF over a list of tokenized sentences."""
    N = max(len(sentences), 1)
    df: dict[str, int] = defaultdict(int)
    for toks in sentences:
        for tok in set(toks):
            df[tok] += 1
    return {tok: math.log((N + 1) / (cnt + 1)) + 1.0 for tok, cnt in df.items()}


def _sentence_score(tf: dict[str, float], idf: dict[str, float]) -> float:
    return sum(tf.get(tok, 0.0) * idf.get(tok, 1.0) for tok in tf)


def _cosine_sim(a_tokens: list[str], b_tokens: list[str]) -> float:
    """Cosine similarity between two token lists."""
    af = _tf(a_tokens)
    bf = _tf(b_tokens)
    dot = sum(af.get(k, 0.0) * v for k, v in bf.items())
    na = math.sqrt(sum(v * v for v in af.values()))
    nb = math.sqrt(sum(v * v for v in bf.values()))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


# ---------------------------------------------------------------------------
# Public class
# ---------------------------------------------------------------------------

class Distillator:
    """Compress large markdown/text documents to a terse summary.

    The algorithm is deterministic: same input → same output.
    """

    def distill(self, text: str, target_chars: int = 600) -> DistillResult:
        """Return a DistillResult with top TF-IDF sentences ≤ *target_chars*.

        For very short texts (≤ target_chars) the full text is returned
        unchanged.
        """
        source_sha = _sha256(text)
        source_chars = len(text)

        if source_chars <= target_chars:
            result_text = text
            return DistillResult(
                source_sha=source_sha,
                source_chars=source_chars,
                distilled_text=result_text,
                distilled_chars=len(result_text),
                ratio=1.0,
            )

        sentences = _split_sentences(text)
        if not sentences:
            return DistillResult(
                source_sha=source_sha,
                source_chars=source_chars,
                distilled_text="",
                distilled_chars=0,
                ratio=0.0,
            )

        tokenized = [_tokenize(s) for s in sentences]
        idf = _idf(tokenized)
        scores = [
            (i, _sentence_score(_tf(toks), idf))
            for i, toks in enumerate(tokenized)
        ]
        # Sort descending by score, then ascending by index for determinism
        scores_sorted = sorted(scores, key=lambda x: (-x[1], x[0]))

        # Greedily pick sentences until target_chars is reached
        selected_idx: set[int] = set()
        running = 0
        for idx, _score in scores_sorted:
            sent_len = len(sentences[idx])
            if running + sent_len > target_chars and selected_idx:
                break
            selected_idx.add(idx)
            running += sent_len + 1  # +1 for space

        # Output in original document order
        ordered = sorted(selected_idx)
        result_text = " ".join(sentences[i] for i in ordered)

        ratio = len(result_text) / max(source_chars, 1)
        return DistillResult(
            source_sha=source_sha,
            source_chars=source_chars,
            distilled_text=result_text,
            distilled_chars=len(result_text),
            ratio=round(ratio, 4),
        )

    def reconstruct(self, distill: DistillResult) -> str:
        """Best-effort reconstruction hint.

        Rule-based: returns the distilled text with a header noting that this
        is a lossy summary. Full reconstruction is not possible from a summary
        alone; callers should verify via length ratio and cosine similarity.
        """
        header = (
            f"[RECONSTRUCTION NOTE] source_sha={distill.source_sha} "
            f"source_chars={distill.source_chars} "
            f"distilled_chars={distill.distilled_chars} "
            f"ratio={distill.ratio:.4f} "
            f"(lossy — divergence from original is expected)\n\n"
        )
        return header + distill.distilled_text

    def verify_roundtrip(
        self, original: str, distill: DistillResult
    ) -> dict[str, object]:
        """Sanity-check a distilled result against its original.

        Returns a dict with ``length_ratio``, ``cosine_sim``, and ``sha_match``.
        """
        recon = distill.distilled_text
        length_ratio = len(recon) / max(len(original), 1)
        cosine = _cosine_sim(_tokenize(original), _tokenize(recon))
        sha_match = _sha256(original) == distill.source_sha
        return {
            "length_ratio": round(length_ratio, 4),
            "cosine_sim": round(cosine, 4),
            "sha_match": sha_match,
        }

    def distill_run_artifacts(
        self, run_path: str, target_chars: int = 600
    ) -> dict[str, DistillResult]:
        """Distill standard run artifacts from *run_path*.

        Looks for: ``final_report.md``, ``prd.md``, ``architecture.md``
        (case-insensitive) under the run directory and its ``delivery/``
        sub-dir. Missing files are silently skipped.
        """
        run_dir = os.path.realpath(run_path)
        candidates = {
            "final_report": ["delivery/final_report.md", "final_report.md"],
            "prd": ["delivery/prd.md", "prd.md", "PRD.md"],
            "architecture": [
                "delivery/architecture.md",
                "architecture.md",
                "ARCHITECTURE.md",
            ],
        }
        results: dict[str, DistillResult] = {}
        for key, paths in candidates.items():
            for rel in paths:
                full = os.path.join(run_dir, rel)
                if os.path.isfile(full):
                    with open(full, encoding="utf-8") as fh:
                        text = fh.read()
                    results[key] = self.distill(text, target_chars=target_chars)
                    break
        return results
