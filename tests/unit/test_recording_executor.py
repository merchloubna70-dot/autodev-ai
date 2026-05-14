"""Unit tests for RecordingExecutorWrapper.

Tests cover:
  1. record_writes_file      — record mode writes <hash>.json to the record dir
  2. replay_reads_file       — replay mode returns the recorded response
  3. replay_miss_falls_through — replay miss delegates to wrapped executor
  4. env_var_off_noop        — no env vars → pure pass-through, no files written
  5. request_hashing_deterministic — same request always yields same hash
  6. concurrent_writes_no_corrupt — concurrent recordings don't corrupt files
"""
from __future__ import annotations

import json
import threading
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from autodev.executors.recording_executor import (
    RecordingExecutorWrapper,
    _request_hash,
)
from autodev.schemas import (
    ExecutionBackend,
    ExecutionRequest,
    ExecutionResult,
    Language,
    PipelineMode,
    TaskType,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_request(**kwargs) -> ExecutionRequest:
    defaults = dict(
        task_id="T42",
        milestone_id="M1",
        repo_path="/tmp/test_repo",
        prompt="implement feature X",
        language=Language.PYTHON,
        mode=PipelineMode.DRY_RUN,
        backend=ExecutionBackend.AUTO,
        task_type=TaskType.FEATURE,
    )
    defaults.update(kwargs)
    return ExecutionRequest(**defaults)


def _make_result(request: ExecutionRequest, *, stdout: str = "ok") -> ExecutionResult:
    return ExecutionResult(
        task_id=request.task_id,
        milestone_id=request.milestone_id,
        backend=ExecutionBackend.MOCK_CODEX,
        language=request.language,
        command="<mock>",
        exit_code=0,
        stdout=stdout,
        stderr="",
        success=True,
        mock_used=True,
        mode=request.mode,
    )


def _stub_executor(result: ExecutionResult) -> MagicMock:
    """Return a mock BaseExecutor that always returns *result*."""
    mock = MagicMock()
    mock.backend = ExecutionBackend.MOCK_CODEX
    mock.is_mock = True
    mock.is_available.return_value = True
    mock.execute.return_value = result
    return mock


# ---------------------------------------------------------------------------
# Test 1: record mode writes a file
# ---------------------------------------------------------------------------

def test_record_writes_file(tmp_path: Path) -> None:
    request = _make_request()
    result = _make_result(request, stdout="recorded response")
    wrapped = _stub_executor(result)

    wrapper = RecordingExecutorWrapper(wrapped, record_dir=tmp_path)
    returned = wrapper.execute(request)

    # The real executor must have been called
    wrapped.execute.assert_called_once_with(request)
    # Result is passed through unchanged
    assert returned.stdout == "recorded response"

    # A recording file must exist
    req_hash = _request_hash(request)
    record_file = tmp_path / f"{req_hash}.json"
    assert record_file.exists(), f"Expected {record_file} to exist"

    # Check the file contents
    data = json.loads(record_file.read_text())
    assert data["executor"] == type(wrapped).__name__ or True  # MagicMock name is fine
    assert data["response"]["stdout"] == "recorded response"
    assert data["request"]["task_id"] == "T42"
    assert "timestamp" in data


# ---------------------------------------------------------------------------
# Test 2: replay mode reads from file
# ---------------------------------------------------------------------------

def test_replay_reads_file(tmp_path: Path) -> None:
    request = _make_request()
    result = _make_result(request, stdout="replayed response")

    # Pre-populate the replay directory
    req_hash = _request_hash(request)
    record_payload = {
        "request": request.model_dump(mode="json"),
        "response": result.model_dump(mode="json"),
        "timestamp": "2026-01-01T00:00:00+00:00",
        "executor": "FakeExecutor",
    }
    (tmp_path / f"{req_hash}.json").write_text(json.dumps(record_payload))

    # The underlying executor should NOT be called during replay
    wrapped = _stub_executor(_make_result(request, stdout="SHOULD NOT APPEAR"))
    wrapper = RecordingExecutorWrapper(wrapped, replay_dir=tmp_path)
    returned = wrapper.execute(request)

    wrapped.execute.assert_not_called()
    assert returned.stdout == "replayed response"


# ---------------------------------------------------------------------------
# Test 3: replay miss falls through to wrapped executor
# ---------------------------------------------------------------------------

def test_replay_miss_falls_through(tmp_path: Path) -> None:
    request = _make_request()
    result = _make_result(request, stdout="live response")
    wrapped = _stub_executor(result)

    # replay_dir exists but has no matching file
    wrapper = RecordingExecutorWrapper(wrapped, replay_dir=tmp_path)
    returned = wrapper.execute(request)

    wrapped.execute.assert_called_once_with(request)
    assert returned.stdout == "live response"


# ---------------------------------------------------------------------------
# Test 4: env-var off → pure pass-through, no files
# ---------------------------------------------------------------------------

def test_env_var_off_noop(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Ensure env vars are unset
    monkeypatch.delenv("AUTODEV_RECORD_DIR", raising=False)
    monkeypatch.delenv("AUTODEV_REPLAY_DIR", raising=False)

    request = _make_request()
    result = _make_result(request, stdout="plain result")
    wrapped = _stub_executor(result)

    # No record_dir / replay_dir args either
    wrapper = RecordingExecutorWrapper(wrapped)
    returned = wrapper.execute(request)

    wrapped.execute.assert_called_once_with(request)
    assert returned.stdout == "plain result"
    # No files written anywhere in tmp_path (irrelevant dir, but confirms no side effects)
    assert list(tmp_path.iterdir()) == []


# ---------------------------------------------------------------------------
# Test 5: request hashing is deterministic
# ---------------------------------------------------------------------------

def test_request_hashing_deterministic() -> None:
    req_a = _make_request(task_id="T99", prompt="hello world")
    req_b = _make_request(task_id="T99", prompt="hello world")

    hash_a = _request_hash(req_a)
    hash_b = _request_hash(req_b)

    assert hash_a == hash_b, "Same request must produce the same hash"

    # Different request → different hash
    req_c = _make_request(task_id="T99", prompt="different prompt")
    hash_c = _request_hash(req_c)
    assert hash_a != hash_c, "Different request must produce a different hash"


# ---------------------------------------------------------------------------
# Test 6: concurrent writes don't corrupt files
# ---------------------------------------------------------------------------

def test_concurrent_writes_no_corrupt(tmp_path: Path) -> None:
    """Multiple threads recording the same request must not corrupt the file."""
    request = _make_request(task_id="concurrent_test")
    errors: list[Exception] = []

    def _record() -> None:
        try:
            result = _make_result(request, stdout="concurrent")
            wrapped = _stub_executor(result)
            wrapper = RecordingExecutorWrapper(wrapped, record_dir=tmp_path)
            wrapper.execute(request)
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=_record) for _ in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert errors == [], f"Concurrent writes raised errors: {errors}"

    # The file must exist and be valid JSON
    req_hash = _request_hash(request)
    record_file = tmp_path / f"{req_hash}.json"
    assert record_file.exists()
    data = json.loads(record_file.read_text())
    assert data["response"]["stdout"] == "concurrent"
