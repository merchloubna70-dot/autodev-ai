"""Default milestone planner — produces the M0..M5 template, scaled by scope."""
from __future__ import annotations

from ..schemas import ArchitectureSpec, Language, Milestone, RiskLevel


class MilestonePlanner:
    DEFAULT_TEMPLATE = [
        ("M0", "Product & Architecture", "Lock PRD, architecture and module map",
         ["PRD", "architecture.md", "module_map.json", "delivery_plan.md"]),
        ("M1", "Project Scaffold", "Generate project skeleton for each detected language",
         ["pyproject.toml / Cargo.toml / package.json", "src and tests dirs", "minimal CLI/API skeleton"]),
        ("M2", "Core Domain", "Implement core data structures, logic and unit tests",
         ["core models", "core business logic", "state machines", "unit tests"]),
        ("M3", "Integration", "Cross-module / cross-language integration + integration tests",
         ["API/CLI/worker integration", "integration tests"]),
        ("M4", "Quality & Security", "Lint, typecheck, security review, audit logging, error handling",
         ["lint/typecheck pass", "security review report", "audit logs"]),
        ("M5", "Documentation & Release", "Docs, release notes, delivery report",
         ["README.md", "usage.md", "architecture.md", "release_notes.md", "delivery_report.md"]),
    ]

    def plan(
        self,
        *,
        architecture: ArchitectureSpec,
        languages: list[Language],
        max_milestones: int = 6,
    ) -> list[Milestone]:
        out: list[Milestone] = []
        for mid, title, objective, deliverables in self.DEFAULT_TEMPLATE[:max_milestones]:
            risk = RiskLevel.LOW
            if mid in ("M3", "M4"):
                risk = RiskLevel.MEDIUM
            if mid == "M0":
                acceptance = ["PRD locked", "Architecture diagram present", "Module map JSON valid"]
            elif mid == "M1":
                acceptance = ["Skeleton compiles/imports", "Test runner can execute zero tests successfully"]
            elif mid == "M2":
                acceptance = ["Unit tests cover core happy paths", "Type checks pass for typed languages"]
            elif mid == "M3":
                acceptance = ["Integration tests cover cross-module flows", "API contract consistent"]
            elif mid == "M4":
                acceptance = ["Lint passes or has waivers", "Security review has no critical findings"]
            else:
                acceptance = ["All required docs present", "Release notes generated"]
            quality_gates = ["python_gate", "rust_gate", "typescript_gate", "integration_gate", "release_gate"]
            out.append(Milestone(
                milestone_id=mid,
                title=title,
                objective=objective,
                deliverables=list(deliverables),
                task_ids=[],  # filled by TaskPlanner
                dependencies=[] if mid == "M0" else [out[-1].milestone_id],
                acceptance_criteria=acceptance,
                quality_gates=quality_gates,
                estimated_risk=risk,
                allowed_languages=languages,
                out_of_scope=[],
            ))
        return out
