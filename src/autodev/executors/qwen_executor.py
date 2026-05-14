"""Qwen Code CLI adapter — opt-in executor for the `qwen` CLI (Alibaba).

Usage:
    autodev-x deliver-project --executor qwen ...

The `qwen` binary must be installed and available on PATH. Install it via:
    npm install -g @alibaba/qwen-code
or follow the official Qwen Code CLI installation instructions.
"""
from __future__ import annotations

import os
import shutil
import subprocess

from ..schemas import ExecutionBackend, ExecutionRequest, ExecutionResult
from ..utils.hashing import short_hash
from ..utils.secret_redaction import redact_env_values, redact_secrets
from ._fs_observer import diff_repo, snapshot_repo
from .base_executor import BaseExecutor

_BINARY = "qwen"

QWEN_PROMPT_BOUNDARY = """
SAFETY BOUNDARY (mandatory):
- Only modify files listed in `allowed_files` for the current task.
- Stay within the current task_id / milestone_id; do not expand scope.
- Do not delete unrelated files.
- Do not read or print secrets (.env, credentials, tokens, printenv).
- Do not run destructive shell (rm -rf, sudo, chmod 777, curl|bash, etc).
- Do not bypass tests or fabricate "passed" / "release-ready" without evidence.
"""


class QwenExecutor(BaseExecutor):
    """Opt-in executor that delegates to the `qwen` CLI (Alibaba Qwen Code).

    This executor is NOT selected by ``--executor auto``; it is only used when
    the caller explicitly passes ``--executor qwen``.
    """

    backend = ExecutionBackend.QWEN
    is_mock = False

    def __init__(self, binary: str = _BINARY, timeout_seconds: int = 600) -> None:
        self.binary = binary
        self.timeout_seconds = timeout_seconds

    def is_available(self) -> bool:
        """Return True if the ``qwen`` binary is found on PATH."""
        return shutil.which(self.binary) is not None

    def _render_prompt(self, request: ExecutionRequest) -> str:
        return (
            f"[TASK] {request.task_id} (milestone={request.milestone_id})\n"
            f"language={request.language.value} type={request.task_type.value} "
            f"risk={request.risk_level.value}\n"
            f"allowed_files={request.allowed_files}\n"
            f"forbidden_files={request.forbidden_files}\n"
            f"context_files={request.context_files}\n"
            f"\nPROMPT:\n{request.prompt}\n"
            f"\n{QWEN_PROMPT_BOUNDARY}\n"
        )

    def execute(self, request: ExecutionRequest) -> ExecutionResult:
        if not self.is_available():
            return self._fail(
                request,
                error_type="cli_missing",
                message=(
                    f"qwen CLI not found on PATH (looked for '{self.binary}'). "
                    "Install it with: npm install -g @alibaba/qwen-code "
                    "or follow the official Qwen Code CLI installation instructions."
                ),
            )

        start = self._start_timer()
        prompt = self._render_prompt(request)
        timeout = request.timeout or self.timeout_seconds

        # Build argv: `qwen --print <prompt>` (non-interactive single-shot mode)
        # Qwen Code CLI mirrors Claude Code's interface; --print for non-interactive.
        argv = [self.binary, "--print", prompt]
        cmd_str = f"{self.binary} --print <prompt_sha={short_hash(prompt, 16)}>"

        fs_before: set[str] = set()
        try:
            fs_before = snapshot_repo(request.repo_path)
        except Exception:
            pass

        try:
            proc = subprocess.run(
                argv,
                cwd=request.repo_path,
                env={**os.environ, **request.env},
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
            stdout = redact_env_values(redact_secrets(proc.stdout), request.env)
            stderr = redact_env_values(redact_secrets(proc.stderr), request.env)
            code = proc.returncode
        except FileNotFoundError:
            return ExecutionResult(
                task_id=request.task_id,
                milestone_id=request.milestone_id,
                backend=self.backend,
                language=request.language,
                command=cmd_str,
                exit_code=127,
                stdout="",
                stderr=(
                    f"qwen CLI not found: {self.binary}. "
                    "Install with: npm install -g @alibaba/qwen-code"
                ),
                success=False,
                error_type="cli_missing",
                mode=request.mode,
            )
        except subprocess.TimeoutExpired:
            return ExecutionResult(
                task_id=request.task_id,
                milestone_id=request.milestone_id,
                backend=self.backend,
                language=request.language,
                command=cmd_str,
                exit_code=124,
                stdout="",
                stderr="qwen CLI timeout",
                success=False,
                error_type="timeout",
                mode=request.mode,
            )
        except Exception as e:  # pragma: no cover
            return ExecutionResult(
                task_id=request.task_id,
                milestone_id=request.milestone_id,
                backend=self.backend,
                language=request.language,
                command=cmd_str,
                exit_code=1,
                stdout="",
                stderr=f"qwen CLI error: {e}",
                success=False,
                error_type="cli_error",
                mode=request.mode,
            )

        changed_files: list[str] = []
        try:
            fs_after = snapshot_repo(request.repo_path)
            changed_files = diff_repo(fs_before, fs_after)
        except Exception:
            pass

        duration = self._elapsed_ms(start)
        success = code == 0
        error_type: str | None = None
        if not success:
            stderr_lower = (stderr or "").lower()
            if "unknown option" in stderr_lower or "unrecognized" in stderr_lower:
                error_type = "unsupported_cli_args"
            else:
                error_type = "non_zero_exit"

        return ExecutionResult(
            task_id=request.task_id,
            milestone_id=request.milestone_id,
            backend=self.backend,
            language=request.language,
            command=cmd_str,
            exit_code=code,
            stdout=stdout,
            stderr=stderr,
            patch="",
            changed_files=changed_files,
            duration_ms=duration,
            success=success,
            error_type=error_type,
            safety_flags=[],
            mode=request.mode,
            selected_backend_reason=f"qwen CLI invoked (prompt_sha={short_hash(prompt, 16)})",
        )
