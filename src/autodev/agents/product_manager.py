"""Product Manager — turn a free-form project brief into a ProductBrief."""
from __future__ import annotations

import re

from ..schemas import ProductBrief
from ._crewai_bridge import make_agent


class ProductManagerAgent:
    def __init__(self) -> None:
        self.agent = make_agent(
            role="Product Manager",
            goal="Turn project brief text into a sharp, testable product brief.",
            backstory="A pragmatic PM who insists on clear MVP scope and non-goals.",
        )

    def build_brief(self, text: str, *, product_name: str | None = None) -> ProductBrief:
        name = product_name or self._guess_name(text)
        goals = self._collect(text, ("goals", "objectives"))
        users = self._collect(text, ("users", "personas", "user personas"))
        cases = self._collect(text, ("use cases", "scenarios"))
        mvp = self._collect(text, ("mvp", "in scope", "scope"))
        non_goals = self._collect(text, ("non-goals", "out of scope", "not goals"))
        boundary = self._first_match(text, r"delivery\s*boundary[:\s]+(.*)")
        return ProductBrief(
            product_name=name,
            goals=goals or [f"Deliver {name}"],
            user_personas=users,
            use_cases=cases,
            mvp_scope=mvp,
            non_goals=non_goals,
            delivery_boundary=boundary or "Single deliverable repository; no external SaaS infra.",
        )

    def _guess_name(self, text: str) -> str:
        for line in text.splitlines():
            ln = line.strip()
            if ln.startswith("# "):
                return ln.lstrip("# ").strip()
            if ln:
                return ln.split(":")[0][:60]
        return "untitled-project"

    def _collect(self, text: str, headings: tuple[str, ...]) -> list[str]:
        out: list[str] = []
        capture = False
        for line in text.splitlines():
            lower = line.lower()
            if any(h in lower for h in headings) and (line.startswith("#") or ":" in line):
                capture = True
                continue
            if capture:
                if line.startswith("#"):
                    capture = False
                    continue
                m = re.match(r"\s*[-*]\s+(.*)", line)
                if m:
                    out.append(m.group(1).strip())
        return out

    def _first_match(self, text: str, pattern: str) -> str | None:
        m = re.search(pattern, text, re.IGNORECASE)
        return m.group(1).strip() if m else None


# BMAD-17: register agent menu at module load time
from ._menu import register_default_menu  # noqa: E402
from ..schemas import AgentMenuEntry  # noqa: E402

register_default_menu("product_manager", [
    AgentMenuEntry(code="CB", description="Create product brief", skill="product_manager"),
    AgentMenuEntry(code="GB", description="Generate goals from text", skill="product_manager"),
    AgentMenuEntry(code="NGL", description="Identify non-goals", skill="product_manager"),
])
