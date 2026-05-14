"""Unit tests for MultiPatchVote voting logic (W7)."""
from __future__ import annotations

from autodev.flows.multi_patch_flow import MultiPatchFlow
from autodev.schemas import MultiPatchVote, PatchCandidate


def _make_candidates() -> list[PatchCandidate]:
    return [
        PatchCandidate(candidate_id="candidate-1", seed="seed-1", test_pass_count=2, test_fail_count=2, score=2.0),
        PatchCandidate(candidate_id="candidate-2", seed="seed-2", test_pass_count=4, test_fail_count=0, score=4.0),
        PatchCandidate(candidate_id="candidate-3", seed="seed-3", test_pass_count=1, test_fail_count=3, score=1.0),
    ]


def test_vote_winner_has_highest_pass_count():
    """Winner must be the candidate with the highest test_pass_count."""
    candidates = _make_candidates()
    winner = MultiPatchFlow._vote(candidates)
    assert winner is not None
    assert winner.candidate_id == "candidate-2"
    assert winner.test_pass_count == 4


def test_vote_tie_resolved_by_first_candidate_id():
    """On tie in test_pass_count, the first (lowest numeric suffix) candidate wins."""
    candidates = [
        PatchCandidate(candidate_id="candidate-1", seed="seed-1", test_pass_count=3, score=3.0),
        PatchCandidate(candidate_id="candidate-2", seed="seed-2", test_pass_count=3, score=3.0),
        PatchCandidate(candidate_id="candidate-3", seed="seed-3", test_pass_count=1, score=1.0),
    ]
    winner = MultiPatchFlow._vote(candidates)
    assert winner is not None
    # Tie between candidate-1 and candidate-2; candidate-1 has a lower suffix → wins
    assert winner.candidate_id == "candidate-1"


def test_vote_empty_returns_none():
    """No candidates → None."""
    assert MultiPatchFlow._vote([]) is None


def test_multi_patch_vote_model_stores_all_candidates():
    """MultiPatchVote must store all candidate models."""
    candidates = _make_candidates()
    vote = MultiPatchVote(
        candidates=candidates,
        winner_candidate_id="candidate-2",
        rationale="candidate-2 passed 4 tests",
    )
    assert len(vote.candidates) == 3
    assert vote.winner_candidate_id == "candidate-2"


def test_patch_candidate_defaults():
    """PatchCandidate defaults are all empty / zero."""
    c = PatchCandidate(candidate_id="c-0", seed="s-0")
    assert c.patch_text == ""
    assert c.changed_files == []
    assert c.test_pass_count == 0
    assert c.test_fail_count == 0
    assert c.score == 0.0
