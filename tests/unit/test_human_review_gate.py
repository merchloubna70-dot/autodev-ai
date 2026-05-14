"""Unit tests for HumanReviewGate (W7)."""
from __future__ import annotations

import threading
import time
from pathlib import Path

from autodev.agents.human_review_gate import HumanReviewGate
from autodev.schemas import HumanReviewDecision


def test_non_blocking_returns_pending(tmp_path):
    """Non-blocking mode must return immediately with decision='pending'."""
    gate = HumanReviewGate(blocking=False)
    result = gate.request_review(run_dir=tmp_path, summary="review me")
    assert result.decision == "pending"
    assert (tmp_path / "pending_review.md").exists()


def test_approved_file_flips_state(tmp_path):
    """Writing the 'approved' sentinel file should flip the decision."""
    gate = HumanReviewGate(blocking=False)
    # Non-blocking → pending
    gate.request_review(run_dir=tmp_path, summary="approve test")
    # Simulate human writing the approved sentinel
    (tmp_path / "approved").touch()
    # check() picks it up
    decision = HumanReviewGate.check(tmp_path)
    assert decision.decision == "approved"


def test_reject_path(tmp_path):
    """Writing the 'rejected' sentinel should be reflected via check()."""
    gate = HumanReviewGate(blocking=False)
    gate.request_review(run_dir=tmp_path, summary="reject test")
    (tmp_path / "rejected").touch()
    decision = HumanReviewGate.check(tmp_path)
    assert decision.decision == "rejected"


def test_blocking_mode_timeout(tmp_path):
    """Blocking mode must return 'pending' after timeout_seconds if no sentinel written."""
    gate = HumanReviewGate(blocking=True, timeout_seconds=1.0)
    start = time.monotonic()
    result = gate.request_review(run_dir=tmp_path, summary="timeout test")
    elapsed = time.monotonic() - start
    assert result.decision == "pending"
    # Should have waited approximately the timeout duration
    assert elapsed >= 0.9, f"Expected at least 0.9s elapsed, got {elapsed:.2f}s"
    # But should not have taken too long
    assert elapsed < 5.0, f"Timeout took too long: {elapsed:.2f}s"


def test_blocking_mode_approves_via_sentinel(tmp_path):
    """Blocking mode resolves to 'approved' when sentinel appears during polling."""
    gate = HumanReviewGate(blocking=True, timeout_seconds=5.0)

    def _write_sentinel():
        time.sleep(0.3)
        (tmp_path / "approved").touch()

    t = threading.Thread(target=_write_sentinel, daemon=True)
    t.start()
    result = gate.request_review(run_dir=tmp_path, summary="async approve")
    t.join(timeout=2.0)
    assert result.decision == "approved"


def test_pending_review_file_path_in_result(tmp_path):
    """The pending_review_file field should point to the written markdown file."""
    gate = HumanReviewGate(blocking=False)
    result = gate.request_review(run_dir=tmp_path, summary="file check")
    assert result.pending_review_file is not None
    assert Path(result.pending_review_file).exists()


def test_human_review_decision_default_is_pending():
    """HumanReviewDecision default decision is 'pending'."""
    d = HumanReviewDecision()
    assert d.decision == "pending"
    assert d.timestamp  # Should have a timestamp
