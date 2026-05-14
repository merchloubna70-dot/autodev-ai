"""RoundtableAgent — BMAD party-mode using A2A.

Spawns N independent agents (via A2AClient) on the same task, each agent
thinks independently (no inter-agent visibility — BMAD party-mode invariant),
then synthesizes a merged verdict.
"""
from __future__ import annotations

import os
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed

# Defensive imports — A2A-1 may not have committed yet
try:
    from ..adapters.a2a.roster import AgentRoster
    _ROSTER_AVAILABLE = True
except ImportError:
    AgentRoster = None  # type: ignore[assignment,misc]
    _ROSTER_AVAILABLE = False

try:
    from ..adapters.a2a.client import A2AClient
    _CLIENT_AVAILABLE = True
except ImportError:
    A2AClient = None  # type: ignore[assignment,misc]
    _CLIENT_AVAILABLE = False

from ..schemas import (
    A2AConversation,
    A2AMessage,
    A2APart,
    A2ATask,
    A2ATaskStatus,
    AgentCard,
)

_MAX_WORKERS = 4
_FORCE_MOCK = os.environ.get("FACTORY_FORCE_MOCK", "0") == "1"


def _make_text_message(role: str, text: str, task_id: str | None = None,
                       context_id: str | None = None) -> A2AMessage:
    """Helper: build an A2AMessage with a single text part."""
    return A2AMessage(
        message_id=str(uuid.uuid4()),
        role=role,
        parts=[A2APart(kind="text", text=text)],
        task_id=task_id,
        context_id=context_id,
    )


def _last_agent_message(task: A2ATask) -> A2AMessage | None:
    """Return the last agent-role message in *task.history*, or None."""
    for msg in reversed(task.history):
        if msg.role == "agent":
            return msg
    return None


def _message_text(msg: A2AMessage) -> str:
    """Extract concatenated text from all text-kind parts of a message."""
    parts = []
    for part in msg.parts:
        if part.kind == "text" and part.text:
            parts.append(part.text)
    return "\n".join(parts)


class _FallbackMockClient:
    """Used when A2AClient is not yet available (A2A-1 still in flight)."""

    def send(self, card: AgentCard, task: A2ATask) -> A2ATask:
        t = task.model_copy(deep=True)
        mock_text = (
            f"[MOCK-{card.name}] Review complete. "
            f"[SEVERITY:MINOR] No critical issues found in {card.name} domain. "
            f"Recommendation: proceed with caution."
        )
        t.history.append(_make_text_message("agent", mock_text, task_id=t.id))
        t.status = A2ATaskStatus.COMPLETED
        return t


def _build_base_task(
    topic: str,
    context: str,
    conversation_id: str,
) -> A2ATask:
    """Build the base A2ATask given to every participant (identical input)."""
    task_id = str(uuid.uuid4())
    user_text = topic
    if context:
        user_text = f"{topic}\n\nContext:\n{context}"
    task = A2ATask(
        id=task_id,
        context_id=conversation_id,
    )
    task.history.append(
        _make_text_message("user", user_text, task_id=task_id, context_id=conversation_id)
    )
    return task


class RoundtableAgent:
    """BMAD party-mode agent: each participant gets the same task independently.

    Parameters
    ----------
    roster:
        Agent registry. Falls back to ``AgentRoster.default()`` when omitted.
    client:
        Transport client for dispatching tasks. Falls back to a default
        ``A2AClient`` (or a mock when A2AClient is unavailable / FORCE_MOCK=1).
    default_model:
        Hint for inline synthesizer card when not found in roster.
    """

    def __init__(
        self,
        roster: AgentRoster | None = None,  # type: ignore[type-arg]
        client: A2AClient | None = None,  # type: ignore[type-arg]
        default_model: str = "auto",
    ) -> None:
        # Roster
        if roster is not None:
            self._roster = roster
        elif _ROSTER_AVAILABLE and AgentRoster is not None:
            self._roster = AgentRoster.default()
        else:
            self._roster = None  # type: ignore[assignment]

        # Client
        if client is not None:
            self._client = client
        elif _FORCE_MOCK or not _CLIENT_AVAILABLE or A2AClient is None:
            self._client = _FallbackMockClient()  # type: ignore[assignment]
        else:
            self._client = A2AClient()  # type: ignore[call-arg]

        self._default_model = default_model

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _pick_cards(
        self,
        needed_skills: list[str],
        min_participants: int,
        max_participants: int,
    ) -> list[AgentCard]:
        """Pick 2-4 cards from roster matching *needed_skills*."""
        if self._roster is None:
            return []

        # Try to find cards matching each skill — one card per skill,
        # preserving BMAD party-mode independence (different specialties)
        selected: list[AgentCard] = []
        seen_names: set[str] = set()

        for skill in needed_skills:
            if len(selected) >= max_participants:
                break
            matches = self._roster.find_by_skill(skill)
            for card in matches:
                if card.name not in seen_names:
                    selected.append(card)
                    seen_names.add(card.name)
                    break  # one card per skill attempt

        # If we still need more to meet min, pull any remaining cards
        if len(selected) < min_participants:
            for card in self._roster.all():
                if len(selected) >= max_participants:
                    break
                if card.name not in seen_names:
                    selected.append(card)
                    seen_names.add(card.name)

        # Cap at max
        return selected[:max_participants]

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def discuss(
        self,
        *,
        topic: str,
        context: str = "",
        needed_skills: list[str],
        min_participants: int = 2,
        max_participants: int = 4,
        conversation_id: str | None = None,
    ) -> A2AConversation:
        """Spawn N agents on the same task and collect their responses.

        Each card receives an IDENTICAL task — agents think independently with
        no visibility into each other's responses (BMAD party-mode invariant).

        Returns an A2AConversation aggregating all agent messages.
        """
        if conversation_id is None:
            conversation_id = str(uuid.uuid4())

        cards = self._pick_cards(needed_skills, min_participants, max_participants)

        if not cards:
            # Return empty conversation — no exception per spec
            return A2AConversation(
                conversation_id=conversation_id,
                task_id="",
                participating_cards=[],
                messages=[],
            )

        # All participants get the same base task (independent copies)
        base_task = _build_base_task(topic, context, conversation_id)

        # Spawn in parallel via ThreadPoolExecutor (bounded at 4).
        # KEY: keep card↔task association via a dict; do NOT rely on
        # as_completed ordering or zip-truncation.
        workers = min(_MAX_WORKERS, len(cards))
        results_by_card: dict[str, A2ATask] = {}

        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(self._client.send, card, base_task.model_copy(deep=True)): card
                for card in cards
            }
            for future in as_completed(futures):
                card = futures[future]
                try:
                    result_task = future.result()
                    results_by_card[card.name] = result_task
                except Exception as exc:
                    err_task = base_task.model_copy(deep=True)
                    err_task.history.append(
                        _make_text_message(
                            "agent",
                            f"[{card.name}] Task failed: {exc}",
                            task_id=err_task.id,
                        )
                    )
                    err_task.status = A2ATaskStatus.FAILED
                    results_by_card[card.name] = err_task

        # Assemble conversation in original card order so output is deterministic
        # regardless of completion order.
        all_messages: list[A2AMessage] = []
        card_names: list[str] = []

        # Include the shared user prompt once
        all_messages.append(base_task.history[0])

        for card in cards:
            card_names.append(card.name)
            task = results_by_card.get(card.name)
            if task is None:
                # Future was never scheduled / completed (defensive)
                continue
            agent_msg = _last_agent_message(task)
            if agent_msg is not None:
                # Tag the message with the card name in metadata-like prefix for traceability
                tagged_parts = [
                    A2APart(kind="text", text=f"[{card.name}] " + (_message_text(agent_msg)))
                ]
                tagged_msg = A2AMessage(
                    message_id=agent_msg.message_id,
                    role="agent",
                    parts=tagged_parts,
                    task_id=task.id,
                    context_id=conversation_id,
                    created_at=agent_msg.created_at,
                )
                all_messages.append(tagged_msg)

        return A2AConversation(
            conversation_id=conversation_id,
            task_id=base_task.id,
            participating_cards=card_names,
            messages=all_messages,
        )

    def synthesize(self, conversation: A2AConversation) -> A2AMessage:
        """Synthesize a merged verdict from all agent messages in *conversation*.

        Uses a 'synthesizer' card from the roster (if present) or builds an
        inline synthesizer card.  Returns an agent-role A2AMessage.
        """
        # Build prompt from conversation history (agent messages only)
        agent_msgs = [m for m in conversation.messages if m.role == "agent"]

        if not agent_msgs:
            return _make_text_message(
                "agent",
                "No agent responses to synthesize.",
                context_id=conversation.conversation_id,
            )

        agent_transcript = "\n\n".join(
            f"--- {_message_text(m)} ---" for m in agent_msgs
        )

        synth_prompt = (
            "You are a synthesizer reviewing the output of multiple independent expert agents.\n\n"
            "Agent responses:\n\n"
            f"{agent_transcript}\n\n"
            "Summarize:\n"
            "1. Agreements across agents\n"
            "2. Disagreements or conflicting assessments\n"
            "3. Dissenting views that warrant attention\n"
            "4. Recommended next step\n\n"
            "Be concise and actionable."
        )

        # Find or build synthesizer card
        synth_card: AgentCard | None = None
        if self._roster is not None:
            matches = self._roster.find_by_skill("synthesis")
            if matches:
                synth_card = matches[0]

        if synth_card is None:
            synth_card = AgentCard(
                name="synthesizer",
                description="Roundtable synthesis agent.",
                skills=["synthesis", "summarization"],
                transport="local-shell",
                model_hint=self._default_model if self._default_model != "auto" else "sonnet",
            )
            # Register it for reuse if roster available
            if self._roster is not None:
                self._roster.register(synth_card)

        synth_task = A2ATask(
            id=str(uuid.uuid4()),
            context_id=conversation.conversation_id,
        )
        synth_task.history.append(
            _make_text_message(
                "user",
                synth_prompt,
                task_id=synth_task.id,
                context_id=conversation.conversation_id,
            )
        )

        result_task = self._client.send(synth_card, synth_task)
        agent_msg = _last_agent_message(result_task)

        if agent_msg is not None:
            return agent_msg

        # Fallback if client produced no agent message
        return _make_text_message(
            "agent",
            "Synthesis complete. See individual agent responses for details.",
            context_id=conversation.conversation_id,
        )

    def discuss_and_synthesize(
        self,
        **kwargs,
    ) -> tuple[A2AConversation, A2AMessage]:
        """Convenience: run discuss() then synthesize().

        All kwargs are forwarded to discuss().
        """
        conversation = self.discuss(**kwargs)
        synth_msg = self.synthesize(conversation)
        return conversation, synth_msg
