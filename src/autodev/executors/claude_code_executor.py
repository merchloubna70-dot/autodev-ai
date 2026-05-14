"""Claude Code CLI adapter — only place where `claude` binary is invoked."""
from __future__ import annotations

import json
import os
import shutil
import subprocess

from ..config import ClaudeCodeExecutorConfig
from ..schemas import CodexInnerStep, ExecutionBackend, ExecutionRequest, ExecutionResult
from ..utils.command_safety import scan_prompt_for_unsafe
from ..utils.hashing import short_hash
from ..utils.secret_redaction import redact_env_values, redact_secrets
from ._fs_observer import diff_repo, snapshot_repo
from .base_executor import BaseExecutor

CLAUDE_PROMPT_BOUNDARY = """
SAFETY BOUNDARY (mandatory):
- Only modify files listed in `allowed_files` for the current task.
- Stay within the current task_id / milestone_id; do not expand scope.
- Do not delete unrelated files.
- Do not read or print secrets (.env, credentials, tokens, printenv).
- Do not modify .env or CI configuration outside scope.
- Do not run destructive shell (rm -rf, sudo, chmod 777, curl|bash, etc).
- Do not bypass tests or fabricate "passed" / "release-ready" without evidence.

CONVENTIONS:
If repo contains AGENTS.md / CLAUDE.md / .cursor/rules — those are authoritative; do not contradict them.

ESCALATION_HINT — 4 categories MUST call ask_opus before implementing:
  1. architecture / cross-module redesign / cross-subsystem design
  2. race condition / data race / concurrency / lifetime
  3. security boundary / permission boundary / RLS / tenant isolation
  4. final review / merge gate / release review
Call: ask_opus architect "<question>"  (planning, read-only plan)
Call: ask_opus reviewer  "<diff+scope>" (verdict: APPROVE/REQUEST_CHANGES/REJECT)
"""


def _parse_claude_inner_steps(stdout: str) -> list[CodexInnerStep]:
    """Parse ``claude --output-format stream-json`` JSONL into inner step records.

    If the output is not valid JSONL (older claude without stream-json support),
    return an empty list gracefully.
    """
    steps: list[CodexInnerStep] = []
    for i, line in enumerate(stdout.splitlines()):
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            return []
        kind = obj.get("type", obj.get("kind", ""))
        content_summary = ""
        command_val = None
        exit_code_val = None
        duration_val = 0

        if "summary" in obj:
            content_summary = str(obj["summary"])
        elif "content" in obj:
            c = obj["content"]
            content_summary = str(c)[:200] if c else ""
        elif "message" in obj:
            content_summary = str(obj["message"])[:200]

        if "command" in obj:
            command_val = obj["command"]
        if "exit_code" in obj:
            try:
                exit_code_val = int(obj["exit_code"])
            except (TypeError, ValueError):
                pass
        if "duration_ms" in obj:
            try:
                duration_val = int(obj["duration_ms"])
            except (TypeError, ValueError):
                pass

        steps.append(CodexInnerStep(
            step_index=i,
            kind=str(kind),
            content_summary=content_summary,
            command=command_val,
            exit_code=exit_code_val,
            duration_ms=duration_val,
        ))
    return steps


class ClaudeCodeExecutor(BaseExecutor):
    backend = ExecutionBackend.CLAUDE_CODE
    is_mock = False

    def __init__(self, config: ClaudeCodeExecutorConfig | None = None):
        self.config = config or ClaudeCodeExecutorConfig()

    def is_available(self) -> bool:
        if os.environ.get("FACTORY_FORCE_MOCK") == "1":
            return False
        return shutil.which(self.config.binary) is not None

    def _render_prompt(self, request: ExecutionRequest) -> str:
        return (
            f"[TASK] {request.task_id} (milestone={request.milestone_id})\n"
            f"language={request.language.value} type={request.task_type.value} "
            f"risk={request.risk_level.value}\n"
            f"allowed_tools={self.config.allowed_tools}\n"
            f"allowed_files={request.allowed_files}\n"
            f"forbidden_files={request.forbidden_files}\n"
            f"context_files={request.context_files}\n"
            f"\nPROMPT:\n{request.prompt}\n"
            f"\n{CLAUDE_PROMPT_BOUNDARY}\n"
        )

    def _prompt_violates_config(self, prompt: str) -> list[str]:
        flags: list[str] = []
        for pattern in self.config.disallowed_patterns:
            if pattern in prompt:
                flags.append(f"prompt contains disallowed pattern: {pattern!r}")
        return flags

    def execute(self, request: ExecutionRequest) -> ExecutionResult:
        start = self._start_timer()
        safety_flags = scan_prompt_for_unsafe(request.prompt)
        safety_flags += self._prompt_violates_config(request.prompt)
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
        cmd_str = self.config.command_template.replace("{prompt}", _shell_quote(prompt))
        cmd_str = cmd_str.replace("{repo_path}", _shell_quote(request.repo_path))
        timeout = request.timeout or self.config.timeout_seconds

        # Pre-execution filesystem snapshot.
        fs_before: set[str] = set()
        try:
            fs_before = snapshot_repo(request.repo_path)
        except Exception:
            pass

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
                stderr=f"claude CLI not found: {self.config.binary}",
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
                stderr="claude CLI timeout",
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
                stderr=f"claude CLI error: {e}",
                success=False,
                error_type="cli_error",
                mode=request.mode,
            )

        # Post-execution filesystem snapshot → changed_files.
        changed_files: list[str] = []
        try:
            fs_after = snapshot_repo(request.repo_path)
            changed_files = diff_repo(fs_before, fs_after)
        except Exception:
            pass

        # Parse inner steps from stream-json output if available.
        inner_steps = _parse_claude_inner_steps(stdout)

        duration = self._elapsed_ms(start)
        success = code == 0
        # Some Claude CLI versions don't support certain args — surface that
        # explicitly rather than crashing.
        error_type = None if success else (
            "unsupported_cli_args" if "unknown option" in (stderr or "").lower() else "non_zero_exit"
        )
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
            selected_backend_reason=f"claude CLI invoked (prompt_sha={short_hash(prompt, 16)})",
            inner_steps=[s.model_dump() for s in inner_steps],
        )


def _shell_quote(s: str) -> str:
    return "'" + s.replace("'", "'\\''") + "'"
