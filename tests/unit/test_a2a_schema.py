"""Tests for A2A Pydantic schema models."""
from __future__ import annotations

from autodev.schemas import (
    A2AConversation,
    A2AMessage,
    A2APart,
    A2ARosterEntry,
    A2ATask,
    A2ATaskStatus,
    AgentCard,
)


def test_a2a_part_text_kind():
    part = A2APart(kind="text", text="hello world")
    assert part.kind == "text"
    assert part.text == "hello world"
    assert part.data is None
    assert part.mime_type is None
    assert part.filename is None


def test_a2a_part_data_kind():
    part = A2APart(kind="data", data={"key": "value"})
    assert part.kind == "data"
    assert part.data == {"key": "value"}
    assert part.text is None


def test_a2a_part_file_kind():
    part = A2APart(kind="file", mime_type="application/pdf", filename="report.pdf")
    assert part.kind == "file"
    assert part.mime_type == "application/pdf"
    assert part.filename == "report.pdf"


def test_a2a_message_roundtrip():
    msg = A2AMessage(
        message_id="msg-001",
        role="user",
        parts=[A2APart(kind="text", text="Review this code")],
        context_id="ctx-1",
        task_id="task-1",
    )
    data = msg.model_dump()
    msg2 = A2AMessage.model_validate(data)
    assert msg2.message_id == "msg-001"
    assert msg2.role == "user"
    assert len(msg2.parts) == 1
    assert msg2.parts[0].kind == "text"
    assert msg2.parts[0].text == "Review this code"
    assert msg2.context_id == "ctx-1"
    assert msg2.task_id == "task-1"
    assert msg2.created_at is not None


def test_a2a_message_default_created_at():
    msg = A2AMessage(message_id="m", role="agent", parts=[])
    assert "T" in msg.created_at  # ISO format includes T separator


def test_a2a_task_status_enum():
    assert A2ATaskStatus.SUBMITTED == "submitted"
    assert A2ATaskStatus.WORKING == "working"
    assert A2ATaskStatus.INPUT_REQUIRED == "input-required"
    assert A2ATaskStatus.COMPLETED == "completed"
    assert A2ATaskStatus.FAILED == "failed"
    assert A2ATaskStatus.CANCELED == "canceled"


def test_a2a_task_defaults():
    task = A2ATask(id="t-1", context_id="ctx-1")
    assert task.status == A2ATaskStatus.SUBMITTED
    assert task.history == []
    assert task.artifacts == []
    assert task.metadata == {}
    assert task.updated_at is None
    assert task.created_at is not None


def test_agent_card_with_skills():
    card = AgentCard(
        name="security",
        description="Security reviewer",
        capabilities=["vulnerability", "threat-modeling"],
        skills=["sast", "owasp"],
        transport="local-shell",
        model_hint="sonnet",
        tags=["core"],
    )
    assert card.name == "security"
    assert "sast" in card.skills
    assert "vulnerability" in card.capabilities
    assert card.transport == "local-shell"
    assert card.model_hint == "sonnet"
    assert card.version == "0.1.0"


def test_agent_card_defaults():
    card = AgentCard(name="minimal")
    assert card.description == ""
    assert card.version == "0.1.0"
    assert card.capabilities == []
    assert card.skills == []
    assert card.transport == "local-shell"
    assert card.endpoint is None
    assert card.auth_scheme is None
    assert card.model_hint is None
    assert card.system_prompt is None
    assert card.tags == []


def test_a2a_roster_entry():
    card = AgentCard(name="architect", model_hint="opus")
    entry = A2ARosterEntry(card=card)
    assert entry.card.name == "architect"
    assert entry.active is True
    assert entry.registered_at is not None


def test_a2a_conversation():
    conv = A2AConversation(
        conversation_id="conv-1",
        task_id="task-1",
        participating_cards=["architect", "security"],
    )
    assert conv.conversation_id == "conv-1"
    assert "architect" in conv.participating_cards
    assert conv.messages == []
