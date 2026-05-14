"""Unit tests for the three opt-in executor adapters: Gemini, Qwen, Aider.

Each adapter is tested for:
1. Binary present: execute() delegates to subprocess and produces a sensible
   ExecutionResult (mocked via unittest.mock.patch so no real CLI is called).
2. Binary missing: is_available() returns False, and execute() returns a clean
   error with error_type="cli_missing" and an install hint in stderr.
"""
from __future__ import annotations

import subprocess
from unittest.mock import MagicMock, patch

from autodev.executors.aider_executor import AiderExecutor
from autodev.executors.gemini_executor import GeminiExecutor
from autodev.executors.qwen_executor import QwenExecutor
from autodev.schemas import (
    ExecutionBackend,
    ExecutionRequest,
    Language,
    PipelineMode,
    TaskType,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _req(tmp_path, prompt: str = "write a hello world function") -> ExecutionRequest:
    return ExecutionRequest(
        task_id="T-test",
        milestone_id="M-test",
        repo_path=str(tmp_path),
        prompt=prompt,
        language=Language.PYTHON,
        mode=PipelineMode.DRY_RUN,
        task_type=TaskType.FEATURE,
    )


def _mock_proc(returncode: int = 0, stdout: str = "done", stderr: str = "") -> MagicMock:
    proc = MagicMock()
    proc.returncode = returncode
    proc.stdout = stdout
    proc.stderr = stderr
    return proc


# ---------------------------------------------------------------------------
# GeminiExecutor
# ---------------------------------------------------------------------------


class TestGeminiExecutor:
    def test_backend_enum(self) -> None:
        assert GeminiExecutor.backend == ExecutionBackend.GEMINI

    def test_missing_binary_returns_cli_missing_error(self, tmp_path) -> None:
        executor = GeminiExecutor(binary="gemini-nonexistent-xyz")
        result = executor.execute(_req(tmp_path))

        assert result.success is False
        assert result.error_type == "cli_missing"
        assert "gemini" in result.stderr.lower()
        # Must include an install hint — not a silent fallback.
        assert "install" in result.stderr.lower()

    def test_binary_present_success(self, tmp_path) -> None:
        executor = GeminiExecutor(binary="gemini")
        with (
            patch("autodev.executors.gemini_executor.shutil.which", return_value="/usr/bin/gemini"),
            patch("autodev.executors.gemini_executor.subprocess.run", return_value=_mock_proc(0, "ok output")),
        ):
            result = executor.execute(_req(tmp_path))

        assert result.success is True
        assert result.backend == ExecutionBackend.GEMINI
        assert result.exit_code == 0
        assert result.stdout == "ok output"
        assert result.error_type is None

    def test_binary_present_nonzero_exit(self, tmp_path) -> None:
        executor = GeminiExecutor(binary="gemini")
        with (
            patch("autodev.executors.gemini_executor.shutil.which", return_value="/usr/bin/gemini"),
            patch("autodev.executors.gemini_executor.subprocess.run", return_value=_mock_proc(1, "", "gemini error")),
        ):
            result = executor.execute(_req(tmp_path))

        assert result.success is False
        assert result.exit_code == 1
        assert result.error_type == "non_zero_exit"

    def test_timeout_returns_timeout_error(self, tmp_path) -> None:
        executor = GeminiExecutor(binary="gemini")
        with (
            patch("autodev.executors.gemini_executor.shutil.which", return_value="/usr/bin/gemini"),
            patch(
                "autodev.executors.gemini_executor.subprocess.run",
                side_effect=subprocess.TimeoutExpired(cmd="gemini", timeout=1),
            ),
        ):
            result = executor.execute(_req(tmp_path))

        assert result.success is False
        assert result.error_type == "timeout"


# ---------------------------------------------------------------------------
# QwenExecutor
# ---------------------------------------------------------------------------


class TestQwenExecutor:
    def test_backend_enum(self) -> None:
        assert QwenExecutor.backend == ExecutionBackend.QWEN

    def test_missing_binary_returns_cli_missing_error(self, tmp_path) -> None:
        executor = QwenExecutor(binary="qwen-nonexistent-xyz")
        result = executor.execute(_req(tmp_path))

        assert result.success is False
        assert result.error_type == "cli_missing"
        assert "qwen" in result.stderr.lower()
        assert "install" in result.stderr.lower()

    def test_binary_present_success(self, tmp_path) -> None:
        executor = QwenExecutor(binary="qwen")
        with (
            patch("autodev.executors.qwen_executor.shutil.which", return_value="/usr/bin/qwen"),
            patch("autodev.executors.qwen_executor.subprocess.run", return_value=_mock_proc(0, "qwen output")),
        ):
            result = executor.execute(_req(tmp_path))

        assert result.success is True
        assert result.backend == ExecutionBackend.QWEN
        assert result.exit_code == 0
        assert result.stdout == "qwen output"
        assert result.error_type is None

    def test_binary_present_nonzero_exit(self, tmp_path) -> None:
        executor = QwenExecutor(binary="qwen")
        with (
            patch("autodev.executors.qwen_executor.shutil.which", return_value="/usr/bin/qwen"),
            patch("autodev.executors.qwen_executor.subprocess.run", return_value=_mock_proc(2, "", "some error")),
        ):
            result = executor.execute(_req(tmp_path))

        assert result.success is False
        assert result.error_type == "non_zero_exit"

    def test_timeout_returns_timeout_error(self, tmp_path) -> None:
        executor = QwenExecutor(binary="qwen")
        with (
            patch("autodev.executors.qwen_executor.shutil.which", return_value="/usr/bin/qwen"),
            patch(
                "autodev.executors.qwen_executor.subprocess.run",
                side_effect=subprocess.TimeoutExpired(cmd="qwen", timeout=1),
            ),
        ):
            result = executor.execute(_req(tmp_path))

        assert result.success is False
        assert result.error_type == "timeout"


# ---------------------------------------------------------------------------
# AiderExecutor
# ---------------------------------------------------------------------------


class TestAiderExecutor:
    def test_backend_enum(self) -> None:
        assert AiderExecutor.backend == ExecutionBackend.AIDER

    def test_missing_binary_returns_cli_missing_error(self, tmp_path) -> None:
        executor = AiderExecutor(binary="aider-nonexistent-xyz")
        result = executor.execute(_req(tmp_path))

        assert result.success is False
        assert result.error_type == "cli_missing"
        assert "aider" in result.stderr.lower()
        assert "install" in result.stderr.lower()

    def test_binary_present_success(self, tmp_path) -> None:
        executor = AiderExecutor(binary="aider")
        with (
            patch("autodev.executors.aider_executor.shutil.which", return_value="/usr/bin/aider"),
            patch("autodev.executors.aider_executor.subprocess.run", return_value=_mock_proc(0, "aider output")),
        ):
            result = executor.execute(_req(tmp_path))

        assert result.success is True
        assert result.backend == ExecutionBackend.AIDER
        assert result.exit_code == 0
        assert result.stdout == "aider output"
        assert result.error_type is None

    def test_binary_present_nonzero_exit(self, tmp_path) -> None:
        executor = AiderExecutor(binary="aider")
        with (
            patch("autodev.executors.aider_executor.shutil.which", return_value="/usr/bin/aider"),
            patch("autodev.executors.aider_executor.subprocess.run", return_value=_mock_proc(1, "", "aider error")),
        ):
            result = executor.execute(_req(tmp_path))

        assert result.success is False
        assert result.error_type == "non_zero_exit"

    def test_allowed_files_passed_as_argv(self, tmp_path) -> None:
        """Aider receives allowed_files as positional argv entries."""
        executor = AiderExecutor(binary="aider")
        aider_calls: list[list[str]] = []

        def capture_run(argv, **kwargs):
            # Only capture the aider invocation, not git sub-calls.
            if argv and argv[0] == "aider":
                aider_calls.append(list(argv))
            return _mock_proc(0)

        req = ExecutionRequest(
            task_id="T-files",
            milestone_id="M-files",
            repo_path=str(tmp_path),
            prompt="fix the bug",
            language=Language.PYTHON,
            mode=PipelineMode.DRY_RUN,
            task_type=TaskType.BUGFIX,
            allowed_files=["src/main.py", "src/utils.py"],
        )

        with (
            patch("autodev.executors.aider_executor.shutil.which", return_value="/usr/bin/aider"),
            patch("autodev.executors.aider_executor.subprocess.run", side_effect=capture_run),
        ):
            result = executor.execute(req)

        assert result.success is True
        assert len(aider_calls) == 1
        argv = aider_calls[0]
        assert "src/main.py" in argv
        assert "src/utils.py" in argv
        # Non-interactive flags must be present
        assert "--yes-always" in argv
        assert "--no-git" in argv

    def test_timeout_returns_timeout_error(self, tmp_path) -> None:
        executor = AiderExecutor(binary="aider")
        with (
            patch("autodev.executors.aider_executor.shutil.which", return_value="/usr/bin/aider"),
            patch(
                "autodev.executors.aider_executor.subprocess.run",
                side_effect=subprocess.TimeoutExpired(cmd="aider", timeout=1),
            ),
        ):
            result = executor.execute(_req(tmp_path))

        assert result.success is False
        assert result.error_type == "timeout"


# ---------------------------------------------------------------------------
# Router integration: opt-in backends routed correctly, auto NOT affected
# ---------------------------------------------------------------------------


class TestRouterOptInIntegration:
    def test_gemini_backend_routes_to_gemini_executor(self, tmp_path) -> None:
        from autodev.executors.executor_router import ExecutorRouter
        from autodev.schemas import ExecutionBackend

        router = ExecutorRouter()
        req = ExecutionRequest(
            task_id="T-r",
            milestone_id="M-r",
            repo_path=str(tmp_path),
            prompt="hello",
            language=Language.PYTHON,
            mode=PipelineMode.DRY_RUN,
            task_type=TaskType.FEATURE,
            backend=ExecutionBackend.GEMINI,
        )
        decision = router.decide(req)
        assert decision.selected_backend == ExecutionBackend.GEMINI
        assert decision.mock_used is False

    def test_qwen_backend_routes_to_qwen_executor(self, tmp_path) -> None:
        from autodev.executors.executor_router import ExecutorRouter
        from autodev.schemas import ExecutionBackend

        router = ExecutorRouter()
        req = ExecutionRequest(
            task_id="T-q",
            milestone_id="M-q",
            repo_path=str(tmp_path),
            prompt="hello",
            language=Language.PYTHON,
            mode=PipelineMode.DRY_RUN,
            task_type=TaskType.FEATURE,
            backend=ExecutionBackend.QWEN,
        )
        decision = router.decide(req)
        assert decision.selected_backend == ExecutionBackend.QWEN
        assert decision.mock_used is False

    def test_aider_backend_routes_to_aider_executor(self, tmp_path) -> None:
        from autodev.executors.executor_router import ExecutorRouter
        from autodev.schemas import ExecutionBackend

        router = ExecutorRouter()
        req = ExecutionRequest(
            task_id="T-a",
            milestone_id="M-a",
            repo_path=str(tmp_path),
            prompt="hello",
            language=Language.PYTHON,
            mode=PipelineMode.DRY_RUN,
            task_type=TaskType.FEATURE,
            backend=ExecutionBackend.AIDER,
        )
        decision = router.decide(req)
        assert decision.selected_backend == ExecutionBackend.AIDER
        assert decision.mock_used is False

    def test_auto_route_does_not_select_gemini_qwen_aider(self, tmp_path) -> None:
        """--executor auto must never select the three opt-in backends."""
        from autodev.executors.base_executor import BaseExecutor
        from autodev.executors.executor_router import ExecutorRouter
        from autodev.schemas import ExecutionBackend, TaskType

        _opt_in = {ExecutionBackend.GEMINI, ExecutionBackend.QWEN, ExecutionBackend.AIDER}

        class _Available(BaseExecutor):
            def __init__(self, backend):
                self.backend = backend
                self.is_mock = False
            def is_available(self):
                return True
            def execute(self, r):
                raise NotImplementedError

        router = ExecutorRouter(
            codex=_Available(ExecutionBackend.CODEX),
            claude=_Available(ExecutionBackend.CLAUDE_CODE),
        )

        for task_type in list(TaskType):
            req = ExecutionRequest(
                task_id="T-auto",
                milestone_id="M-auto",
                repo_path=str(tmp_path),
                prompt="hello",
                language=Language.PYTHON,
                mode=PipelineMode.DRY_RUN,
                task_type=task_type,
                backend=ExecutionBackend.AUTO,
            )
            decision = router.decide(req)
            assert decision.selected_backend not in _opt_in, (
                f"auto routing selected opt-in backend {decision.selected_backend} "
                f"for task_type={task_type}"
            )
