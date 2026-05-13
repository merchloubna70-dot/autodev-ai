"""Base executor abstract class."""
from __future__ import annotations

import time
from abc import ABC, abstractmethod

from ..schemas import ExecutionBackend, ExecutionRequest, ExecutionResult


class BaseExecutor(ABC):
    backend: ExecutionBackend = ExecutionBackend.AUTO
    is_mock: bool = False

    @abstractmethod
    def is_available(self) -> bool:
        """Return True if the underlying CLI is installed/usable."""

    @abstractmethod
    def execute(self, request: ExecutionRequest) -> ExecutionResult:
        ...

    # helpers ------------------------------------------------------------

    def _start_timer(self) -> float:
        return time.monotonic()

    def _elapsed_ms(self, start: float) -> int:
        return int((time.monotonic() - start) * 1000)

    def _fail(self, request: ExecutionRequest, *, error_type: str, message: str) -> ExecutionResult:
        return ExecutionResult(
            task_id=request.task_id,
            milestone_id=request.milestone_id,
            backend=self.backend,
            language=request.language,
            command="",
            exit_code=1,
            stdout="",
            stderr=message,
            success=False,
            error_type=error_type,
            mock_used=self.is_mock,
            mode=request.mode,
        )
