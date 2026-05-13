"""Unit tests for FailureClusterReviewer."""
from __future__ import annotations

import pytest

from crewai_multicli_factory.agents.failure_cluster_reviewer import FailureClusterReviewer
from crewai_multicli_factory.schemas import (
    ExecutionBackend,
    ExecutionResult,
    Language,
    PipelineMode,
)


@pytest.fixture(autouse=True)
def _force_mock(monkeypatch):
    monkeypatch.setenv("FACTORY_FORCE_MOCK", "1")


def _make_failed_result(task_id: str) -> ExecutionResult:
    return ExecutionResult(
        task_id=task_id,
        milestone_id="M2",
        backend=ExecutionBackend.MOCK_CODEX,
        language=Language.PYTHON,
        command="codex ...",
        exit_code=1,
        stdout="",
        stderr=f"Task {task_id} failed with error X",
        success=False,
        error_type="non_zero_exit",
        mode=PipelineMode.APPLY,
    )


class TestFailureClusterReviewer:
    def test_opus_consulted_true_when_threshold_met(self):
        failed = [_make_failed_result(f"T{i}") for i in range(3)]
        reviewer = FailureClusterReviewer(threshold=2)
        report = reviewer.review(milestone_id="M2", failed_results=failed)
        assert report.opus_consulted is True

    def test_failure_count_equals_three(self):
        failed = [_make_failed_result(f"T{i}") for i in range(3)]
        reviewer = FailureClusterReviewer(threshold=2)
        report = reviewer.review(milestone_id="M2", failed_results=failed)
        assert report.failure_count == 3

    def test_review_text_contains_all_task_ids(self):
        failed = [_make_failed_result(f"T{i}") for i in range(3)]
        reviewer = FailureClusterReviewer(threshold=2)
        report = reviewer.review(milestone_id="M2", failed_results=failed)
        for i in range(3):
            assert f"T{i}" in report.review_text

    def test_failed_task_ids_list(self):
        failed = [_make_failed_result(f"T{i}") for i in range(3)]
        reviewer = FailureClusterReviewer(threshold=2)
        report = reviewer.review(milestone_id="M2", failed_results=failed)
        assert set(report.failed_task_ids) == {"T0", "T1", "T2"}

    def test_opus_result_not_none_when_consulted(self):
        failed = [_make_failed_result(f"T{i}") for i in range(3)]
        reviewer = FailureClusterReviewer(threshold=2)
        report = reviewer.review(milestone_id="M2", failed_results=failed)
        assert report.opus_result is not None

    def test_no_opus_below_threshold(self):
        failed = [_make_failed_result("T0")]
        reviewer = FailureClusterReviewer(threshold=2)
        report = reviewer.review(milestone_id="M2", failed_results=failed)
        assert report.opus_consulted is False
        assert report.opus_result is None

    def test_milestone_id_preserved(self):
        failed = [_make_failed_result(f"T{i}") for i in range(3)]
        reviewer = FailureClusterReviewer(threshold=2)
        report = reviewer.review(milestone_id="M2", failed_results=failed)
        assert report.milestone_id == "M2"

    def test_review_text_has_header(self):
        failed = [_make_failed_result(f"T{i}") for i in range(3)]
        reviewer = FailureClusterReviewer(threshold=2)
        report = reviewer.review(milestone_id="M2", failed_results=failed)
        assert "Failure Cluster Review" in report.review_text
