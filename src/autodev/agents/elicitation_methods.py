"""ElicitationMethodsAgent — loads the BMAD elicitation methods registry.

Data source: ``src/autodev/data/elicitation_methods.csv``
Schema: category, method_name, description

In mock/dry-run mode (``FACTORY_FORCE_MOCK=1``) all outputs are deterministic.
Integrates with BMAD-4's ClarificationGate via the optional ``methods_agent``
constructor parameter on that gate.
"""
from __future__ import annotations

import csv
import os
from pathlib import Path
from typing import TYPE_CHECKING

from ..schemas import ElicitationMethod, ElicitationOutput

if TYPE_CHECKING:
    pass

# Locate the bundled CSV relative to this file.
_DATA_DIR = Path(__file__).parent.parent / "data"
_DEFAULT_CSV = _DATA_DIR / "elicitation_methods.csv"

# Simple keyword→template map used for prompt_template generation.
_TEMPLATE_MAP: dict[str, str] = {
    "5-whys": "Ask 'Why?' five times about: {content}",
    "critical-question": "What hidden assumptions underlie: {content}?",
    "must-might-may": "Categorise items in '{content}' as must/might/may.",
    "ai-tree": "Generate three distinct reasoning paths for: {content}",
    "role-play": "Adopt two opposing roles and debate: {content}",
    "what-if": "Explore three 'what-if' scenarios for: {content}",
    "pre-mortem": "Imagine '{content}' failed. What caused it?",
    "red-team": "Attack the following as an adversary: {content}",
    "devil-advocate": "Argue strongly against: {content}",
    "SCAMPER": "Apply SCAMPER lenses (Substitute/Combine/Adapt/Modify/Put/Eliminate/Reverse) to: {content}",
    "reverse-brainstorm": "List ways to make '{content}' fail, then invert each.",
    "analogous-reasoning": "Find a cross-domain analogy for: {content}",
    "assumption-mapping": "List and classify assumptions in: {content}",
    "knowledge-gap": "Identify what is unknown or uncertain about: {content}",
    "evidence-check": "Trace the primary evidence supporting: {content}",
}


def _default_template(method_name: str) -> str:
    return _TEMPLATE_MAP.get(method_name, "Apply {method} to: {content}").format(
        method=method_name, content="{content}"
    )


class ElicitationMethodsAgent:
    """Registry-backed agent for BMAD elicitation methods.

    Parameters
    ----------
    csv_path:
        Override the default CSV path (useful for testing).
    methods_agent:
        Unused self-reference kept for API symmetry; allows callers that
        inject this agent into ClarificationGate to pass it back without
        circular issues.
    """

    def __init__(
        self,
        csv_path: str | Path | None = None,
        *,
        methods_agent: ElicitationMethodsAgent | None = None,  # noqa: F821
    ) -> None:
        self._csv_path = Path(csv_path) if csv_path else _DEFAULT_CSV
        self._methods: list[ElicitationMethod] | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load_methods(self) -> list[ElicitationMethod]:
        """Parse the CSV and return a list of :class:`ElicitationMethod`.

        Results are cached after the first call.  Malformed rows (wrong column
        count, missing required fields) are silently skipped.
        """
        if self._methods is not None:
            return list(self._methods)

        methods: list[ElicitationMethod] = []
        try:
            with self._csv_path.open(newline="", encoding="utf-8") as fh:
                reader = csv.DictReader(fh)
                for row in reader:
                    try:
                        cat = (row.get("category") or "").strip()
                        name = (row.get("method_name") or "").strip()
                        desc = (row.get("description") or "").strip()
                        if not cat or not name or not desc:
                            continue
                        template = _default_template(name)
                        methods.append(
                            ElicitationMethod(
                                category=cat,
                                method_name=name,
                                description=desc,
                                prompt_template=template,
                                tags=[cat],
                            )
                        )
                    except (KeyError, ValueError):
                        # Malformed row — skip gracefully
                        continue
        except FileNotFoundError:
            # Return empty list; callers can detect this via len == 0
            pass

        self._methods = methods
        return list(methods)

    def list_categories(self) -> list[str]:
        """Return deduplicated category names in the order they appear."""
        seen: list[str] = []
        for m in self.load_methods():
            if m.category not in seen:
                seen.append(m.category)
        return seen

    def recommend(self, topic: str, k: int = 3) -> list[ElicitationMethod]:
        """Keyword-based recommendation: score by word overlap with description.

        Falls back to the first *k* methods when no keywords match.
        """
        keywords = set(topic.lower().split())
        scored: list[tuple[int, ElicitationMethod]] = []
        for m in self.load_methods():
            score = sum(
                1
                for kw in keywords
                if kw in m.description.lower()
                or kw in m.method_name.lower()
                or kw in m.category.lower()
            )
            scored.append((score, m))

        # Stable sort: highest score first, preserve original order on ties
        scored.sort(key=lambda t: -t[0])
        top = [m for _, m in scored[:k]]
        # If all scores are 0, return first k methods anyway
        if all(s == 0 for s, _ in scored[:k]):
            return [m for _, m in scored[:k]]
        return top

    def apply_method(
        self, method: ElicitationMethod, content: str
    ) -> ElicitationOutput:
        """Render the method's prompt template against *content*.

        When ``FACTORY_FORCE_MOCK=1`` the output is fully deterministic
        (template substitution only, no LLM call).
        """
        template = method.prompt_template or _default_template(method.method_name)
        rendered = template.replace("{content}", content)

        force_mock = os.environ.get("FACTORY_FORCE_MOCK", "0") == "1"
        if force_mock:
            output_text = f"[MOCK] {rendered}"
        else:
            # In a real implementation this would call the LLM.
            output_text = f"[MOCK] {rendered}"

        return ElicitationOutput(
            method=method,
            input_content=content,
            output_text=output_text,
        )
