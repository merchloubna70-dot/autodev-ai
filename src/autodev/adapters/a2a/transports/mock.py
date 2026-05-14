"""MockTransport — pure deterministic A2A transport for tests."""
from __future__ import annotations

from datetime import datetime, timezone

from ....schemas import (
    A2AMessage,
    A2APart,
    A2ATask,
    A2ATaskStatus,
    AgentCard,
)
from ....utils.hashing import sha256_hex
from .base import BaseA2ATransport


def _mock_response(prompt: str, card_name: str) -> str:
    key = sha256_hex(prompt + card_name)[:16]
    return f"[MOCK:{card_name}] verdict key={key} pure mock response."


class MockTransport(BaseA2ATransport):
    """Always returns a deterministic mock response without any shell call."""

    def send_task(self, card: AgentCard, task: A2ATask) -> A2ATask:
        """Return a mock completed task — never raises, never shells out."""
        try:
            prompt = ""
            for msg in reversed(task.history):
                if msg.role == "user":
                    for part in msg.parts:
                        if part.kind == "text" and part.text:
                            prompt = part.text
                            break
                    break

            now = datetime.now(timezone.utc).isoformat()
            response_text = _mock_response(prompt, card.name)

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
                A2APart(kind="text", text=f"[MOCK-EXCEPTION:{card.name}] {exc}")
            )
            task.status = A2ATaskStatus.FAILED
            task.updated_at = now

        return task
