"""PydanticAIAgentFactory — migration bridge between our internal agents and pydantic_ai.

When pydantic_ai is installed, ``build_typed_classifier`` returns a real
``pydantic_ai.Agent`` configured to produce ``InputClassification`` output.

When pydantic_ai is NOT installed, it returns a lightweight stub object
with the same interface that delegates to our existing ``InputClassifierAgent``.
This makes the bridge a migration path, NOT a replacement.
"""
from __future__ import annotations

from typing import Any

from ..schemas import InputClassification, PydanticAIBridgeStatus

# ---------------------------------------------------------------------------
# Optional pydantic_ai import
# ---------------------------------------------------------------------------

try:
    import pydantic_ai  # type: ignore[import]

    _PYDANTIC_AI_AVAILABLE = True
except Exception:
    pydantic_ai = None  # type: ignore[assignment]
    _PYDANTIC_AI_AVAILABLE = False


# ---------------------------------------------------------------------------
# Stub — same interface as pydantic_ai.Agent for classify usage
# ---------------------------------------------------------------------------


class _ClassifierAgentStub:
    """Drop-in stub returned when pydantic_ai is not installed.

    Delegates to our existing InputClassifierAgent so call-sites work
    identically regardless of whether pydantic_ai is present.
    """

    def __init__(self, stub_reason: str) -> None:
        self._stub_reason = stub_reason
        # Lazy-import to avoid circular dep at module load time
        self._inner: Any = None

    def _get_inner(self):
        if self._inner is None:
            from ..agents.input_classifier import InputClassifierAgent

            self._inner = InputClassifierAgent()
        return self._inner

    def run_sync(
        self,
        text: str,
        *,
        source_url: str | None = None,
        source_path: str | None = None,
        has_existing_code: bool = False,
    ) -> InputClassification:
        """Synchronous classify call — mirrors pydantic_ai.Agent.run_sync."""
        return self._get_inner().classify(
            text=text,
            source_url=source_url,
            source_path=source_path,
            has_existing_code=has_existing_code,
        )

    async def run(
        self,
        text: str,
        *,
        source_url: str | None = None,
        source_path: str | None = None,
        has_existing_code: bool = False,
    ) -> InputClassification:
        """Async classify call — mirrors pydantic_ai.Agent.run."""
        return self.run_sync(
            text,
            source_url=source_url,
            source_path=source_path,
            has_existing_code=has_existing_code,
        )

    @property
    def is_stub(self) -> bool:
        return True

    @property
    def stub_reason(self) -> str:
        return self._stub_reason

    def __repr__(self) -> str:
        return f"<ClassifierAgentStub reason={self._stub_reason!r}>"


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


class PydanticAIAgentFactory:
    """Factory for creating pydantic_ai agents (or stubs) from our existing agents."""

    @staticmethod
    def bridge_status() -> PydanticAIBridgeStatus:
        """Return the current availability status of the pydantic_ai bridge."""
        if _PYDANTIC_AI_AVAILABLE:
            return PydanticAIBridgeStatus(
                pydantic_ai_available=True,
                fallback_to_stub=False,
                stub_reason="",
            )
        return PydanticAIBridgeStatus(
            pydantic_ai_available=False,
            fallback_to_stub=True,
            stub_reason="pydantic_ai package not installed",
        )

    @staticmethod
    def build_typed_classifier(
        model: str = "openai:gpt-4o-mini",
        system_prompt: str | None = None,
    ) -> Any:
        """Return a pydantic_ai.Agent (or stub) that classifies raw text into InputClassification.

        Args:
            model: pydantic_ai model string (ignored when falling back to stub).
            system_prompt: optional override system prompt (ignored in stub mode).

        Returns:
            A pydantic_ai.Agent[InputClassification] when pydantic_ai is installed,
            or a _ClassifierAgentStub with the same interface otherwise.
        """
        if _PYDANTIC_AI_AVAILABLE:
            try:
                agent = pydantic_ai.Agent(
                    model,
                    result_type=InputClassification,
                    system_prompt=(
                        system_prompt
                        or (
                            "You are an expert software-factory input classifier. "
                            "Classify the user input into one of the InputType categories "
                            "and return a structured InputClassification."
                        )
                    ),
                )
                return agent
            except Exception as exc:
                # pydantic_ai installed but Agent construction failed — fall through to stub
                stub_reason = f"pydantic_ai.Agent init failed: {exc}"
                return _ClassifierAgentStub(stub_reason=stub_reason)

        return _ClassifierAgentStub(
            stub_reason="pydantic_ai package not installed"
        )
