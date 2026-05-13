"""Deterministic mock for Codex CLI — used when codex binary is unavailable
or when ``allow_mock_executor=true`` and we're in dry-run/test mode.

The mock generates a deterministic patch derived from the task_id + prompt
hash so unit/integration tests are stable across runs.
"""
from __future__ import annotations

from ..schemas import ExecutionBackend, ExecutionRequest, ExecutionResult
from ..utils.hashing import short_hash
from .base_executor import BaseExecutor
from .patch_executor import FilePatch, PatchExecutor


class MockCodexExecutor(BaseExecutor):
    backend = ExecutionBackend.MOCK_CODEX
    is_mock = True

    def is_available(self) -> bool:  # mock is always available
        return True

    def execute(self, request: ExecutionRequest) -> ExecutionResult:
        start = self._start_timer()
        digest = short_hash(f"{request.task_id}|{request.prompt}|codex", 12)
        rel_path = f".dev-factory/mock/codex_{request.task_id}_{digest}.txt"
        patch = FilePatch(
            path=rel_path,
            new_content=(
                f"# mock codex output\n"
                f"task_id={request.task_id}\n"
                f"milestone_id={request.milestone_id}\n"
                f"language={request.language.value}\n"
                f"task_type={request.task_type.value}\n"
                f"prompt_sha={short_hash(request.prompt, 16)}\n"
            ),
            create_only=False,
        )
        applier = PatchExecutor(request.repo_path, mode=request.mode)
        changed = applier.apply([patch])
        diff = PatchExecutor.synthesize_unified_diff([patch])
        duration = self._elapsed_ms(start)
        return ExecutionResult(
            task_id=request.task_id,
            milestone_id=request.milestone_id,
            backend=self.backend,
            language=request.language,
            command=f"<mock-codex task={request.task_id}>",
            exit_code=0,
            stdout=f"[mock-codex] simulated patch for {request.task_id}",
            stderr="",
            patch=diff,
            changed_files=changed,
            duration_ms=duration,
            success=True,
            mock_used=True,
            fallback_used=False,
            mode=request.mode,
            selected_backend_reason="mock_codex deterministic stand-in",
        )
