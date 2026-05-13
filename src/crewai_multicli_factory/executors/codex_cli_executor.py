"""Codex CLI adapter — the ONLY place where the codex binary is invoked."""
from __future__ import annotations

import os
import shutil
import subprocess

from ..config import CodexCliExecutorConfig
from ..schemas import ExecutionBackend, ExecutionRequest, ExecutionResult
from ..utils.command_safety import scan_prompt_for_unsafe
from ..utils.hashing import short_hash
from .base_executor import BaseExecutor


CODEX_PROMPT_BOUNDARY = """
SAFETY BOUNDARY (mandatory):
- Only modify files listed in `allowed_files` for the current task.
- Do not delete unrelated files.
- Do not read secrets (.env, credentials, tokens).
- Do not modify .env or CI configuration outside scope.
- Do not run destructive shell (rm -rf, sudo, chmod 777, curl|bash, etc).
- Do not bypass tests.
- Do not falsify "passed" / "release-ready" without evidence.
- Do not expand scope beyond the current task_id.

ESCALATION_HINT — 4 categories MUST call ask_opus before implementing:
  1. architecture / cross-module redesign / cross-subsystem design
  2. race condition / data race / concurrency / lifetime
  3. security boundary / permission boundary / RLS / tenant isolation
  4. final review / merge gate / release review
Call: ask_opus architect "<question>"  (planning, read-only plan)
Call: ask_opus reviewer  "<diff+scope>" (verdict: APPROVE/REQUEST_CHANGES/REJECT)
"""


class CodexCliExecutor(BaseExecutor):
    backend = ExecutionBackend.CODEX
    is_mock = False

    def __init__(self, config: CodexCliExecutorConfig | None = None):
        self.config = config or CodexCliExecutorConfig()

    def is_available(self) -> bool:
        if os.environ.get("FACTORY_FORCE_MOCK") == "1":
            return False
        return shutil.which(self.config.binary) is not None

    def _render_prompt(self, request: ExecutionRequest) -> str:
        return (
            f"[TASK] {request.task_id} (milestone={request.milestone_id})\n"
            f"language={request.language.value} type={request.task_type.value} "
            f"risk={request.risk_level.value}\n"
            f"allowed_files={request.allowed_files}\n"
            f"forbidden_files={request.forbidden_files}\n"
            f"context_files={request.context_files}\n"
            f"\nPROMPT:\n{request.prompt}\n"
            f"\n{CODEX_PROMPT_BOUNDARY}\n"
        )

    def execute(self, request: ExecutionRequest) -> ExecutionResult:
        start = self._start_timer()
        safety_flags = scan_prompt_for_unsafe(request.prompt)
        if safety_flags:
            return ExecutionResult(
                task_id=request.task_id,
                milestone_id=request.milestone_id,
                backend=self.backend,
                language=request.language,
                command="",
                exit_code=1,
                stdout="",
                stderr="prompt rejected: unsafe pattern",
                success=False,
                error_type="unsafe_prompt",
                safety_flags=safety_flags,
                mode=request.mode,
            )

        prompt = self._render_prompt(request)
        # Build the command from the configurable template; never shell=True.
        cmd_str = self.config.command_template.replace("{prompt}", _shell_quote(prompt))
        cmd_str = cmd_str.replace("{repo_path}", _shell_quote(request.repo_path))
        timeout = request.timeout or self.config.timeout_seconds
        try:
            import shlex

            argv = shlex.split(cmd_str, posix=True)
            proc = subprocess.run(
                argv,
                cwd=request.repo_path,
                env={**os.environ, **request.env},
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
            stdout, stderr, code = proc.stdout, proc.stderr, proc.returncode
        except FileNotFoundError:
            return ExecutionResult(
                task_id=request.task_id,
                milestone_id=request.milestone_id,
                backend=self.backend,
                language=request.language,
                command=cmd_str,
                exit_code=127,
                stdout="",
                stderr=f"codex CLI not found: {self.config.binary}",
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
                stderr="codex CLI timeout",
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
                stderr=f"codex CLI error: {e}",
                success=False,
                error_type="cli_error",
                mode=request.mode,
            )

        duration = self._elapsed_ms(start)
        success = code == 0
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
            changed_files=[],
            duration_ms=duration,
            success=success,
            error_type=None if success else "non_zero_exit",
            safety_flags=[],
            mode=request.mode,
            selected_backend_reason=f"codex CLI invoked (prompt_sha={short_hash(prompt, 16)})",
        )


def _shell_quote(s: str) -> str:
    # Minimal shell-safe quoting; used only for command template rendering.
    return "'" + s.replace("'", "'\\''") + "'"
