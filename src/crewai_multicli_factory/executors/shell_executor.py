"""Centralized shell executor enforcing allowlist / denylist."""
from __future__ import annotations

import shlex
import subprocess
from dataclasses import dataclass

from ..utils.command_safety import is_command_allowed


@dataclass
class ShellResult:
    command: str
    allowed: bool
    rejection_reason: str
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: int


class ShellExecutor:
    def __init__(self, cwd: str | None = None, timeout: int = 600):
        self.cwd = cwd
        self.timeout = timeout

    def run(self, command: str, *, env: dict[str, str] | None = None) -> ShellResult:
        verdict = is_command_allowed(command)
        if not verdict.allowed:
            return ShellResult(
                command=command,
                allowed=False,
                rejection_reason=verdict.reason,
                exit_code=126,
                stdout="",
                stderr=f"REJECTED: {verdict.reason}",
                duration_ms=0,
            )
        import time

        start = time.monotonic()
        try:
            argv = shlex.split(command, posix=True)
            proc = subprocess.run(
                argv,
                cwd=self.cwd,
                env={**__import__("os").environ, **(env or {})},
                capture_output=True,
                text=True,
                timeout=self.timeout,
                check=False,
            )
            stdout, stderr, code = proc.stdout, proc.stderr, proc.returncode
        except FileNotFoundError as e:
            stdout, stderr, code = "", f"command not found: {e}", 127
        except subprocess.TimeoutExpired as e:
            stdout, stderr, code = "", f"timeout: {e}", 124
        except Exception as e:  # pragma: no cover - defensive
            stdout, stderr, code = "", f"shell error: {e}", 1
        duration_ms = int((time.monotonic() - start) * 1000)
        return ShellResult(
            command=command,
            allowed=True,
            rejection_reason="",
            exit_code=code,
            stdout=stdout,
            stderr=stderr,
            duration_ms=duration_ms,
        )
