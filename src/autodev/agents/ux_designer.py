"""UX Designer Agent — Sally.

Modeled on BMAD's bmad-agent-ux-designer (Sally persona).
Deterministic template-driven by default; no LLM required.
Set FACTORY_FORCE_MOCK=1 or use_llm=False (default) for reproducible output.
"""
from __future__ import annotations

import os
from typing import TYPE_CHECKING

from ..schemas import (
    AgentCard,
    ComponentSpec,
    DesignToken,
    Language,
    PRD,
    ProductBrief,
    ResponsiveBreakpoint,
    UserJourney,
    UserJourneyStep,
    UserPersona,
    UXDesignInput,
    UXDesignSpec,
    UXPattern,
)

if TYPE_CHECKING:
    pass

# ---------------------------------------------------------------------------
# Sally's invariant principles (mirrored from BMAD customize.toml)
# ---------------------------------------------------------------------------
_PRINCIPLES: list[str] = [
    "Every decision serves a genuine user need.",
    "Start simple, evolve through feedback.",
    "Data-informed, but always creative.",
    "Grounded in Don Norman's human-centered design.",
    "Persona discipline per Alan Cooper.",
]

# ---------------------------------------------------------------------------
# Default design system tokens
# ---------------------------------------------------------------------------
_DEFAULT_TOKENS: list[DesignToken] = [
    DesignToken(category="color", name="primary",   value="#2563EB", usage="Primary actions, links"),
    DesignToken(category="color", name="secondary", value="#7C3AED", usage="Secondary actions, accents"),
    DesignToken(category="color", name="success",   value="#16A34A", usage="Positive feedback, confirmations"),
    DesignToken(category="color", name="warning",   value="#D97706", usage="Warnings, caution states"),
    DesignToken(category="color", name="error",     value="#DC2626", usage="Errors, destructive actions"),
    DesignToken(category="color", name="neutral-50",  value="#F9FAFB", usage="Page background"),
    DesignToken(category="color", name="neutral-900", value="#111827", usage="Body text"),
    DesignToken(category="typography", name="font-sans", value="Inter, system-ui, sans-serif", usage="Body and UI"),
    DesignToken(category="typography", name="font-mono", value="JetBrains Mono, monospace",    usage="Code, IDs"),
    DesignToken(category="typography", name="size-base", value="1rem",   usage="Body text"),
    DesignToken(category="typography", name="size-lg",   value="1.125rem", usage="Subheadings"),
    DesignToken(category="typography", name="size-xl",   value="1.25rem",  usage="Section headings"),
    DesignToken(category="typography", name="size-2xl",  value="1.5rem",   usage="Page headings"),
    DesignToken(category="spacing", name="spacing-1", value="0.25rem", usage="Tight gaps"),
    DesignToken(category="spacing", name="spacing-2", value="0.5rem",  usage="Component padding"),
    DesignToken(category="spacing", name="spacing-4", value="1rem",    usage="Section gaps"),
    DesignToken(category="spacing", name="spacing-8", value="2rem",    usage="Page margins"),
    DesignToken(category="radius", name="radius-sm", value="0.25rem", usage="Inputs, badges"),
    DesignToken(category="radius", name="radius-md", value="0.375rem", usage="Cards, modals"),
    DesignToken(category="radius", name="radius-lg", value="0.5rem",   usage="Panels"),
    DesignToken(category="radius", name="radius-full", value="9999px", usage="Pills, avatars"),
]

_DEFAULT_BREAKPOINTS: list[ResponsiveBreakpoint] = [
    ResponsiveBreakpoint(name="mobile",  min_width_px=0,    max_width_px=767),
    ResponsiveBreakpoint(name="tablet",  min_width_px=768,  max_width_px=1023),
    ResponsiveBreakpoint(name="desktop", min_width_px=1024, max_width_px=None),
]

_DEFAULT_A11Y: list[str] = [
    "All interactive elements reachable and operable by keyboard (Tab, Enter, Space, arrow keys).",
    "Color contrast ≥ 4.5:1 for normal text, ≥ 3:1 for large text (WCAG AA).",
    "Focus indicators visible with min 3:1 contrast against surroundings.",
    "Form inputs have associated <label> elements (not placeholder-only).",
    "Images have descriptive alt text; decorative images use alt=''.",
    "ARIA roles used only where native HTML semantics are insufficient.",
    "Error messages programmatically associated with the input they describe.",
    "No content flashes more than 3 times per second (seizure prevention).",
]


def _default_personas(product_name: str, prd: PRD | None) -> list[UserPersona]:
    """Derive simple default personas from PRD or use generic ones."""
    if prd and prd.functional_requirements:
        categories: set[str] = set()
        for fr in prd.functional_requirements:
            title_lower = fr.title.lower()
            if "admin" in title_lower:
                categories.add("Admin")
            elif "report" in title_lower or "analyt" in title_lower:
                categories.add("Analyst")
            else:
                categories.add("End User")
        personas = []
        for cat in sorted(categories):
            personas.append(UserPersona(
                name=f"{cat} Persona",
                role=cat,
                needs=[f"Efficiently accomplish {cat.lower()} tasks in {product_name}"],
                pain_points=["Complex workflows", "Lack of feedback on actions"],
            ))
        return personas or [_generic_persona(product_name)]
    return [_generic_persona(product_name)]


def _generic_persona(product_name: str) -> UserPersona:
    return UserPersona(
        name="Primary User",
        role="End User",
        needs=[f"Accomplish core tasks in {product_name} without friction"],
        pain_points=["Unclear navigation", "Too many steps to complete common tasks"],
    )


def _default_components(prd: PRD | None) -> list[ComponentSpec]:
    base = [
        ComponentSpec(
            name="Button",
            purpose="Primary and secondary call-to-action",
            states=["default", "hover", "active", "disabled", "loading"],
            a11y_notes=["Use <button> element", "Visible focus ring", "Disabled state communicates reason via aria-describedby"],
        ),
        ComponentSpec(
            name="FormField",
            purpose="Data entry with validation feedback",
            states=["default", "focused", "error", "success", "disabled"],
            a11y_notes=["Associated <label>", "aria-invalid on error", "Error message via aria-describedby"],
        ),
        ComponentSpec(
            name="DataTable",
            purpose="Tabular display with sort and filter",
            states=["loading", "empty", "populated", "row-selected"],
            a11y_notes=["<caption> or aria-label", "Column headers with scope='col'", "Sort state via aria-sort"],
        ),
        ComponentSpec(
            name="Modal",
            purpose="Focused overlay for forms or confirmations",
            states=["closed", "open", "loading", "error"],
            a11y_notes=["Focus trap on open", "role='dialog' + aria-modal='true'", "Escape closes", "Return focus on close"],
        ),
        ComponentSpec(
            name="NavigationBar",
            purpose="Primary site navigation",
            states=["default", "active-item", "collapsed-mobile"],
            a11y_notes=["<nav> landmark", "aria-current='page' on active link", "Skip-to-content link at top"],
        ),
    ]
    return base


def _default_patterns(prd: PRD | None) -> list[UXPattern]:
    patterns = [
        UXPattern(
            name="progressive-disclosure",
            rationale="Show only what the user needs at each stage; reveal complexity on demand.",
            applied_to=["Settings", "Advanced filters"],
        ),
        UXPattern(
            name="dashboard",
            rationale="Surface key metrics and recent activity at a glance.",
            applied_to=["Home", "Overview"],
        ),
        UXPattern(
            name="wizard",
            rationale="Guide users through multi-step processes with clear progress indication.",
            applied_to=["Onboarding", "Complex forms"],
        ),
        UXPattern(
            name="search-then-filter",
            rationale="Quick search for broad navigation; faceted filters for refinement.",
            applied_to=["List views", "Data exploration"],
        ),
    ]
    return patterns


def _default_journey(product_name: str, persona: UserPersona) -> UserJourney:
    return UserJourney(
        name=f"Core {persona.role} Journey",
        persona_name=persona.name,
        steps=[
            UserJourneyStep(step_number=1, action="Arrive at product", thought="What can I do here?", feeling="curious", touchpoint="Landing / Dashboard"),
            UserJourneyStep(step_number=2, action="Navigate to primary feature", thought="How do I find what I need?", feeling="focused", touchpoint="Navigation Bar"),
            UserJourneyStep(step_number=3, action="Complete primary task", thought="Is this doing what I expect?", feeling="engaged", touchpoint="Main content area"),
            UserJourneyStep(step_number=4, action="Review result / confirmation", thought="Did it work?", feeling="relieved", touchpoint="Confirmation / Toast"),
            UserJourneyStep(step_number=5, action="Continue or exit", thought="What next?", feeling="satisfied", touchpoint="Navigation / Exit"),
        ],
    )


class UXDesignerAgent:
    """Sally — BMAD UX Designer, ported as a deterministic autodev agent."""

    name = "Sally"
    title = "UX Designer"
    icon = "🎨"
    principles: list[str] = _PRINCIPLES

    def __init__(self, *, use_llm: bool = False) -> None:
        self._use_llm = use_llm and not _force_mock()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def design(
        self,
        prd: PRD | None = None,
        brief: ProductBrief | None = None,
        languages: list[Language] | None = None,
        repo_path: str = ".",
    ) -> UXDesignSpec:
        """Produce a structured UXDesignSpec from optional PRD / brief.

        Default path is fully deterministic (no LLM). Pass use_llm=True in
        the constructor to enable future LLM-driven generation.
        """
        product_name = _resolve_product_name(prd, brief)
        personas = _default_personas(product_name, prd)
        journeys = [_default_journey(product_name, personas[0])]
        return UXDesignSpec(
            product_name=product_name,
            personas=personas,
            journeys=journeys,
            design_tokens=list(_DEFAULT_TOKENS),
            components=_default_components(prd),
            patterns=_default_patterns(prd),
            breakpoints=list(_DEFAULT_BREAKPOINTS),
            a11y_checks=list(_DEFAULT_A11Y),
            notes=[
                f"Generated by {self.name} ({self.title}) — autodev BMAD-8.",
                "Deterministic template; swap to LLM mode for project-specific design.",
            ],
        )

    def render_markdown(self, spec: UXDesignSpec) -> str:
        """Render a UXDesignSpec to Markdown for product/ux_design.md."""
        lines: list[str] = [
            f"# UX Design — {spec.product_name}",
            "",
            f"_Generated by {self.name} ({self.title}) {self.icon} at {spec.generated_at}_",
            "",
        ]

        # Personas
        lines += ["## User Personas", ""]
        for p in spec.personas:
            lines.append(f"### {p.name} — {p.role}")
            if p.needs:
                lines.append("**Needs:**")
                for n in p.needs:
                    lines.append(f"- {n}")
            if p.pain_points:
                lines.append("**Pain points:**")
                for pp in p.pain_points:
                    lines.append(f"- {pp}")
            lines.append("")

        # User journeys
        lines += ["## User Journeys", ""]
        for j in spec.journeys:
            lines.append(f"### {j.name} ({j.persona_name})")
            lines.append("")
            lines.append("| # | Action | Thought | Feeling | Touchpoint |")
            lines.append("|---|--------|---------|---------|------------|")
            for s in j.steps:
                lines.append(f"| {s.step_number} | {s.action} | {s.thought} | {s.feeling} | {s.touchpoint} |")
            lines.append("")

        # Design tokens
        lines += ["## Design System Tokens", ""]
        categories = sorted({t.category for t in spec.design_tokens})
        for cat in categories:
            lines.append(f"### {cat.capitalize()}")
            lines.append("| Name | Value | Usage |")
            lines.append("|------|-------|-------|")
            for t in spec.design_tokens:
                if t.category == cat:
                    lines.append(f"| `{t.name}` | `{t.value}` | {t.usage} |")
            lines.append("")

        # Components
        lines += ["## Component Strategy", ""]
        for c in spec.components:
            lines.append(f"### {c.name}")
            if c.purpose:
                lines.append(f"_{c.purpose}_")
            if c.states:
                lines.append(f"**States:** {', '.join(c.states)}")
            if c.a11y_notes:
                lines.append("**A11y:**")
                for note in c.a11y_notes:
                    lines.append(f"- {note}")
            lines.append("")

        # UX Patterns
        lines += ["## UX Patterns", ""]
        for pat in spec.patterns:
            lines.append(f"### {pat.name}")
            if pat.rationale:
                lines.append(pat.rationale)
            if pat.applied_to:
                lines.append(f"_Applied to: {', '.join(pat.applied_to)}_")
            lines.append("")

        # Responsive
        lines += ["## Responsive Breakpoints", ""]
        lines.append("| Name | Min px | Max px |")
        lines.append("|------|--------|--------|")
        for bp in spec.breakpoints:
            max_v = str(bp.max_width_px) if bp.max_width_px is not None else "∞"
            lines.append(f"| {bp.name} | {bp.min_width_px} | {max_v} |")
        lines.append("")

        # A11y
        lines += ["## Accessibility Checklist", ""]
        for check in spec.a11y_checks:
            lines.append(f"- [ ] {check}")
        lines.append("")

        # Notes
        if spec.notes:
            lines += ["## Notes", ""]
            for note in spec.notes:
                lines.append(f"- {note}")
            lines.append("")

        return "\n".join(lines)

    def as_agent_card(self) -> AgentCard:
        """Return an A2A AgentCard describing Sally."""
        return AgentCard(
            name=self.name,
            description=(
                f"{self.title} ({self.icon}): translates user needs into UX design specs. "
                "Deterministic by default; LLM-driven via use_llm=True."
            ),
            version="0.1.0",
            capabilities=["ux-design", "persona-creation", "design-system", "a11y"],
            skills=["design", "render_markdown"],
            transport="local-shell",
            tags=["bmad", "ux", "design", "sally"],
        )

    def register_into(self, roster: object) -> None:  # type: ignore[type-arg]
        """Register this agent's card into an existing AgentRoster."""
        card = self.as_agent_card()
        if hasattr(roster, "register"):
            roster.register(card)
        elif hasattr(roster, "add"):
            roster.add(card)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _force_mock() -> bool:
    return os.environ.get("FACTORY_FORCE_MOCK", "0") not in ("0", "", "false", "False")


def _resolve_product_name(prd: PRD | None, brief: ProductBrief | None) -> str:
    if prd and prd.product_name:
        return prd.product_name
    if brief and brief.product_name:
        return brief.product_name
    return "Product"


# BMAD-17: register agent menu at module load time
from ._menu import register_default_menu  # noqa: E402
from ..schemas import AgentMenuEntry  # noqa: E402

register_default_menu("ux_designer", [
    AgentMenuEntry(code="UX", description="Generate UX design spec", skill="ux_designer"),
    AgentMenuEntry(code="JM", description="Create user journey map", skill="ux_designer"),
])
