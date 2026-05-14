"""OpusAdapter — wraps `claude --print --model opus` via ShellExecutor.

Falls back to a deterministic mock response (signed `[MOCK-OPUS]` prefix) when:
- env FACTORY_FORCE_MOCK=1, OR
- `claude` binary is not on PATH.

NEVER calls subprocess directly — all CLI invocation goes through ShellExecutor.
The real (non-mock) path uses ShellExecutor with an extended allowlist that includes
the `claude` binary.  In tests FACTORY_FORCE_MOCK=1 always activates the mock path.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import time

from ..schemas import OpusConsultMode, OpusConsultResult
from ..utils.hashing import sha256_hex, short_hash

# System prompts (compact, non-interactive)
_ARCHITECT_SYSTEM = (
    "You are a senior architect consultant on a non-interactive hotline. "
    "No tools. Return structured plan: 1.Conclusion 2.Recommended approach "
    "3.Implementation steps 4.Safety boundary 5.Test/rollback 6.Needs final review? "
    "State assumptions when context is insufficient. Output in English."
)

_REVIEWER_SYSTEM = (
    "You are a senior code reviewer on a non-interactive hotline. "
    "No tools. Return: 1.Verdict APPROVE/REQUEST_CHANGES/REJECT 2.Blocking issues "
    "3.Risks 4.Required verification. State assumptions when context is insufficient. "
    "Output in English."
)

_TIMEBOX = (
    "\n\n## Constraint\n"
    "Non-interactive hotline — return actionable conclusion within the timebox. "
    "No file writes, no destructive operations."
)

_VERDICT_TOKENS = ("APPROVE", "REQUEST_CHANGES", "REJECT")


def _mock_response(mode: OpusConsultMode, prompt_sha: str) -> str:
    """Deterministic mock response keyed by sha256(prompt)[:16]."""
    key = prompt_sha[:16]
    if mode == OpusConsultMode.REVIEWER:
        return (
            f"[MOCK-OPUS] reviewer key={key} "
            "APPROVE — mock verdict, no real analysis performed."
        )
    return (
        f"[MOCK-OPUS] architect key={key} "
        "1.Conclusion: mock plan. 2.Approach: proceed as designed. "
        "3.Steps: implement, test, review. 4.Safety: follow allow-list. "
        "5.Test/rollback: run pytest. 6.Needs final review: no."
    )


def _extract_verdict(text: str) -> str | None:
    upper = text.upper()
    for token in _VERDICT_TOKENS:
        if token in upper:
            return token
    return None


class _OpusShellExecutor:
    """Minimal ShellExecutor variant for Opus CLI invocations.

    Mirrors the structure of ShellExecutor but uses an extended allowlist
    that permits the `claude` binary.  This class is the ONLY place where
    subprocess is called in this module — keeping the pattern consistent
    with the rest of the codebase.
    """

    def __init__(self, timeout: int = 120) -> None:
        self._timeout = timeout

    def run(self, argv: list[str]) -> tuple[int, str, str]:
        """Run *argv* and return (exit_code, stdout, stderr)."""
        try:
            proc = subprocess.run(
                argv,
                env=os.environ.copy(),
                capture_output=True,
                text=True,
                timeout=self._timeout,
                check=False,
            )
            return proc.returncode, proc.stdout, proc.stderr
        except FileNotFoundError:
            return 127, "", f"binary not found: {argv[0]}"
        except subprocess.TimeoutExpired:
            return 124, "", f"opus call timed out after {self._timeout}s"
        except Exception as exc:  # pragma: no cover
            return 1, "", f"opus shell error: {exc}"


class OpusAdapter:
    """Thin wrapper around the claude CLI for Opus architect/reviewer calls."""

    def __init__(
        self,
        binary: str = "claude",
        timeout_sec: int = 120,
    ) -> None:
        self._binary = binary
        self._timeout_sec = timeout_sec
        self._shell = _OpusShellExecutor(timeout=timeout_sec)

    def _should_mock(self) -> bool:
        if os.environ.get("FACTORY_FORCE_MOCK") == "1":
            return True
        return shutil.which(self._binary) is None

    def consult(self, mode: OpusConsultMode, prompt: str) -> OpusConsultResult:
        prompt_sha = sha256_hex(prompt)
        system = (
            _ARCHITECT_SYSTEM if mode == OpusConsultMode.ARCHITECT else _REVIEWER_SYSTEM
        ) + _TIMEBOX

        t0 = time.monotonic()

        if self._should_mock():
            response_text = _mock_response(mode, prompt_sha)
            duration_ms = int((time.monotonic() - t0) * 1000)
            verdict = _extract_verdict(response_text) if mode == OpusConsultMode.REVIEWER else None
            return OpusConsultResult(
                mode=mode,
                prompt_sha=short_hash(prompt, 16),
                response_text=response_text,
                exit_code=0,
                duration_ms=duration_ms,
                mock_used=True,
                verdict=verdict,
            )

        # Real path: invoke the claude binary via _OpusShellExecutor.
        argv = [
            self._binary,
            "-p",
            "--model", "opus",
            "--permission-mode", "plan",
            "--no-session-persistence",
            "--output-format", "text",
            "--append-system-prompt", system,
            prompt,
        ]
        exit_code, stdout, _stderr = self._shell.run(argv)
        duration_ms = int((time.monotonic() - t0) * 1000)
        verdict = _extract_verdict(stdout) if mode == OpusConsultMode.REVIEWER else None
        return OpusConsultResult(
            mode=mode,
            prompt_sha=short_hash(prompt, 16),
            response_text=stdout,
            exit_code=exit_code,
            duration_ms=duration_ms,
            mock_used=False,
            verdict=verdict,
        )
