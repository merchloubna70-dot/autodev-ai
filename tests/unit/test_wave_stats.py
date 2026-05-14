"""Unit tests for wave_stats helper in utils/concurrency.py."""
from __future__ import annotations

from autodev.utils.concurrency import wave_stats


def test_max_width():
    waves = [["A", "B", "C"], ["D"], ["E", "F"]]
    stats = wave_stats(waves)
    assert stats["num_waves"] == 3
    assert stats["max_width"] == 3
    assert stats["avg_width"] == pytest_approx_close(2.0, abs=0.01)
    assert stats["single_task_waves"] == 1


def pytest_approx_close(value: float, *, abs: float = 1e-6) -> _Approx:
    return _Approx(value, abs)


class _Approx:
    def __init__(self, value: float, tol: float) -> None:
        self.value = value
        self.tol = tol

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, (int, float)):
            return NotImplemented
        return abs(other - self.value) <= self.tol

    def __repr__(self) -> str:
        return f"~{self.value}±{self.tol}"


def test_single_task_waves_count():
    waves = [["X"], ["Y"], ["Z", "W"]]
    stats = wave_stats(waves)
    assert stats["single_task_waves"] == 2
    assert stats["max_width"] == 2
    assert stats["num_waves"] == 3


def test_empty_waves():
    stats = wave_stats([])
    assert stats["num_waves"] == 0
    assert stats["max_width"] == 0
    assert stats["avg_width"] == 0.0
    assert stats["single_task_waves"] == 0
