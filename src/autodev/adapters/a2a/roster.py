"""AgentRoster — registry of AgentCard entries with find/persist helpers."""
from __future__ import annotations

import json
from pathlib import Path

from ...schemas import A2ARosterEntry, AgentCard


class AgentRoster:
    """In-memory registry of AgentCards with optional JSON persistence."""

    def __init__(self) -> None:
        self._entries: dict[str, A2ARosterEntry] = {}

    # ------------------------------------------------------------------
    # Mutation
    # ------------------------------------------------------------------

    def register(self, card: AgentCard) -> None:
        """Register *card*, replacing any existing entry with the same name."""
        self._entries[card.name] = A2ARosterEntry(card=card)

    def unregister(self, name: str) -> bool:
        """Remove the card with *name*. Returns True if it existed."""
        if name in self._entries:
            del self._entries[name]
            return True
        return False

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def all(self) -> list[AgentCard]:
        """Return all active registered cards."""
        return [entry.card for entry in self._entries.values() if entry.active]

    def find_by_skill(self, skill: str) -> list[AgentCard]:
        """Return cards whose skills or capabilities contain *skill* (substring)."""
        skill_lower = skill.lower()
        result: list[AgentCard] = []
        for card in self.all():
            combined = [s.lower() for s in card.skills + card.capabilities]
            if any(skill_lower in item for item in combined):
                result.append(card)
        return result

    def find_by_skills(self, skills: list[str], min_match: int = 1) -> list[AgentCard]:
        """Return cards matching at least *min_match* of the given skills."""
        result: list[AgentCard] = []
        for card in self.all():
            combined = [s.lower() for s in card.skills + card.capabilities]
            matches = sum(
                1
                for skill in skills
                if any(skill.lower() in item for item in combined)
            )
            if matches >= min_match:
                result.append(card)
        return result

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save(self, path: str | Path) -> None:
        """Persist the roster to a JSON file."""
        data = [entry.model_dump() for entry in self._entries.values()]
        Path(path).write_text(json.dumps(data, indent=2), encoding="utf-8")

    def load(self, path: str | Path) -> None:
        """Load roster from a JSON file, merging into the current registry."""
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        for item in raw:
            entry = A2ARosterEntry.model_validate(item)
            self._entries[entry.card.name] = entry

    # ------------------------------------------------------------------
    # Built-in defaults
    # ------------------------------------------------------------------

    @classmethod
    def default(cls) -> AgentRoster:
        """Return a roster pre-loaded with five standard specialist cards."""
        roster = cls()
        defaults = [
            AgentCard(
                name="architect",
                description="Senior software architect for design and planning decisions.",
                capabilities=["architecture", "design", "planning", "system-design"],
                skills=["design-review", "adr", "technology-selection", "scalability"],
                transport="local-shell",
                model_hint="opus",
                system_prompt=(
                    "You are a senior software architect consultant on a non-interactive hotline. "
                    "Evaluate architecture decisions, trade-offs, and system designs. "
                    "Return structured output: 1.Conclusion 2.Recommended approach "
                    "3.Implementation steps 4.Safety boundary 5.Test/rollback 6.Needs final review? "
                    "State assumptions when context is insufficient. Output in English."
                ),
                tags=["core", "planning"],
            ),
            AgentCard(
                name="security",
                description="Security reviewer focused on vulnerabilities and threat modeling.",
                capabilities=["security", "vulnerability", "threat-modeling", "compliance"],
                skills=["sast", "owasp", "secrets-detection", "auth-review", "input-validation"],
                transport="local-shell",
                model_hint="sonnet",
                system_prompt=(
                    "You are a senior security engineer on a non-interactive hotline. "
                    "Identify vulnerabilities, insecure patterns, and compliance gaps. "
                    "Return: 1.Severity (CRITICAL/HIGH/MEDIUM/LOW) 2.Vulnerability list "
                    "3.Attack vectors 4.Recommended fixes 5.Verification steps. "
                    "Be precise and actionable. Output in English."
                ),
                tags=["core", "security"],
            ),
            AgentCard(
                name="performance",
                description="Performance engineer for bottleneck analysis and optimization.",
                capabilities=["performance", "profiling", "optimization", "benchmarking"],
                skills=["complexity-analysis", "database-query-review", "memory-profiling", "latency"],
                transport="local-shell",
                model_hint="sonnet",
                system_prompt=(
                    "You are a senior performance engineer on a non-interactive hotline. "
                    "Analyze code for performance bottlenecks, inefficient patterns, and scalability limits. "
                    "Return: 1.Performance verdict 2.Bottlenecks identified 3.Complexity analysis "
                    "4.Optimization recommendations 5.Benchmark guidance. Output in English."
                ),
                tags=["core", "quality"],
            ),
            AgentCard(
                name="style",
                description="Code style and readability reviewer enforcing conventions.",
                capabilities=["style", "readability", "conventions", "linting"],
                skills=["code-review", "naming-conventions", "documentation", "formatting"],
                transport="local-shell",
                model_hint="haiku",
                system_prompt=(
                    "You are a code style and readability specialist on a non-interactive hotline. "
                    "Review code for style consistency, naming conventions, documentation, and readability. "
                    "Return: 1.Style verdict (PASS/WARN/FAIL) 2.Issues list 3.Convention violations "
                    "4.Recommended rewrites. Keep feedback concise and actionable. Output in English."
                ),
                tags=["quality"],
            ),
            AgentCard(
                name="ux",
                description="UX reviewer for API design and developer experience.",
                capabilities=["ux", "api-design", "developer-experience", "usability"],
                skills=["api-review", "dx", "interface-design", "ergonomics", "error-messages"],
                transport="local-shell",
                model_hint="sonnet",
                system_prompt=(
                    "You are a UX and developer-experience specialist on a non-interactive hotline. "
                    "Evaluate APIs, CLI interfaces, and code ergonomics from a user-perspective. "
                    "Return: 1.UX verdict 2.Pain points 3.Confusing interfaces 4.Improvement suggestions "
                    "5.Example rewrites. Focus on clarity and ease-of-use. Output in English."
                ),
                tags=["quality", "api"],
            ),
        ]
        for card in defaults:
            roster.register(card)

        # BMAD-2: adversarial + edge-case reviewers
        try:
            from ...agents.adversarial_reviewer import AdversarialReviewer
            roster.register(AdversarialReviewer.as_agent_card())
        except Exception:
            pass

        try:
            from ...agents.edge_case_hunter import EdgeCaseHunter
            roster.register(EdgeCaseHunter.as_agent_card())
        except Exception:
            pass

        return roster
