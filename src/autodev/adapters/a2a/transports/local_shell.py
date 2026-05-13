"""LocalShellTransport — A2A transport that wraps OpusAdapter / claude CLI.

Falls back to deterministic mock when:
- env FACTORY_FORCE_MOCK=1, OR
- shutil.which("claude") is None.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import time
from datetime import datetime, timezone

from ....schemas import (
    AgentCard,
    A2AMessage,
    A2APart,
    A2ATask,
    A2ATaskStatus,
)
from ....utils.hashing import sha256_hex
from .base import BaseA2ATransport


def _extract_latest_user_text(task: A2ATask) -> str:
    """Return the text of the most recent user message in task.history."""
    for msg in reversed(task.history):
        if msg.role == "user":
            for part in msg.parts:
                if part.kind == "text" and part.text:
                    return part.text
    return ""


def _mock_response(prompt: str, card_name: str) -> str:
    key = sha256_hex(prompt + card_name)[:16]
    return f"[MOCK-LOCAL-SHELL:{card_name}] verdict key={key} mock response, no real analysis performed."


class LocalShellTransport(BaseA2ATransport):
    """Transport that invokes the claude CLI via subprocess (OpusAdapter pattern).

    Uses FACTORY_FORCE_MOCK or missing claude binary to return deterministic mock.
    """

    def __init__(self, binary: str = "claude", timeout_sec: int = 120) -> None:
        self._binary = binary
        self._timeout_sec = timeout_sec

    def _should_mock(self) -> bool:
        if os.environ.get("FACTORY_FORCE_MOCK") == "1":
            return True
        return shutil.which(self._binary) is None

    def _run_claude(self, prompt: str, system_prompt: str | None, model_hint: str | None) -> tuple[int, str]:
        """Invoke claude CLI. Returns (exit_code, response_text)."""
        model = model_hint or "sonnet"
        argv = [
            self._binary,
            "-p",
            "--model", model,
            "--permission-mode", "plan",
            "--no-session-persistence",
            "--output-format", "text",
        ]
        if system_prompt:
            argv += ["--append-system-prompt", system_prompt]
        argv.append(prompt)
        try:
            proc = subprocess.run(
                argv,
                env=os.environ.copy(),
                capture_output=True,
                text=True,
                timeout=self._timeout_sec,
                check=False,
            )
            return proc.returncode, proc.stdout
        except FileNotFoundError:
            return 127, ""
        except subprocess.TimeoutExpired:
            return 124, ""
        except Exception as exc:  # pragma: no cover
            return 1, str(exc)

    def send_task(self, card: AgentCard, task: A2ATask) -> A2ATask:
        """Send task to agent via local shell. Never raises."""
        try:
            prompt = _extract_latest_user_text(task)
            now = datetime.now(timezone.utc).isoformat()

            if self._should_mock():
                response_text = _mock_response(prompt, card.name)
                exit_code = 0
            else:
                exit_code, response_text = self._run_claude(
                    prompt, card.system_prompt, card.model_hint
                )

            if exit_code != 0 and not response_text:
                # Shell failed with no output — mark as FAILED
                error_text = f"[LOCAL-SHELL-ERROR:{card.name}] exit_code={exit_code}"
                error_part = A2APart(kind="text", text=error_text)
                task.artifacts.append(error_part)
                task.status = A2ATaskStatus.FAILED
                task.updated_at = now
                return task

            agent_msg = A2AMessage(
                message_id=sha256_hex(response_text + card.name + now)[:16],
                role="agent",
                parts=[A2APart(kind="text", text=response_text)],
                context_id=task.context_id,
                task_id=task.id,
            )
            task.history.append(agent_msg)
            task.artifacts.append(A2APart(kind="text", text=response_text))
            task.status = A2ATaskStatus.COMPLETED
            task.updated_at = now

        except Exception as exc:  # pragma: no cover — defensive
            now = datetime.now(timezone.utc).isoformat()
            task.artifacts.append(
                A2APart(kind="text", text=f"[LOCAL-SHELL-EXCEPTION:{card.name}] {exc}")
            )
            task.status = A2ATaskStatus.FAILED
            task.updated_at = now

        return task
