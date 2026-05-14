"""Default milestone planner — produces the M0..M5 template, scaled by scope."""
from __future__ import annotations

from ..schemas import ArchitectureSpec, Language, Milestone, RiskLevel, Scale


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

    ENTERPRISE_EXTRA_TEMPLATE = [
        ("M3.5", "Performance", "Performance profiling and optimization",
         ["profiling report", "benchmarks", "optimizations applied"]),
        ("M3.6", "Compliance", "Regulatory compliance and audit trail review",
         ["compliance checklist", "audit log review", "regulatory sign-off"]),
    ]

    def plan(
        self,
        *,
        architecture: ArchitectureSpec,
        languages: list[Language],
        max_milestones: int = 6,
        scale: Scale | None = None,
    ) -> list[Milestone]:
        # Determine which template rows to use based on scale
        if scale is None:
            # backward-compat: use max_milestones cap on default template
            template = self.DEFAULT_TEMPLATE[:max_milestones]
        elif scale == Scale.BUG_FIX:
            # Minimal: M2 only (no M0/M1 scaffolding overhead)
            template = [t for t in self.DEFAULT_TEMPLATE if t[0] == "M2"]
        elif scale == Scale.SMALL:
            # Skip M3 integration
            template = [t for t in self.DEFAULT_TEMPLATE if t[0] != "M3"]
        elif scale == Scale.MEDIUM:
            # Keep current 6-milestone default
            template = list(self.DEFAULT_TEMPLATE)
        elif scale == Scale.ENTERPRISE:
            # Add M3.5 Performance + M3.6 Compliance after M3, before M4
            base = list(self.DEFAULT_TEMPLATE)
            m3_idx = next((i for i, t in enumerate(base) if t[0] == "M3"), None)
            if m3_idx is not None:
                insert_at = m3_idx + 1
                template = base[:insert_at] + list(self.ENTERPRISE_EXTRA_TEMPLATE) + base[insert_at:]
            else:
                template = base + list(self.ENTERPRISE_EXTRA_TEMPLATE)
        else:
            template = self.DEFAULT_TEMPLATE[:max_milestones]

        out: list[Milestone] = []
        for mid, title, objective, deliverables in template:
            risk = RiskLevel.LOW
            if mid in ("M3", "M3.5", "M3.6", "M4"):
                risk = RiskLevel.MEDIUM
            if mid == "M0":
                acceptance = ["PRD locked", "Architecture diagram present", "Module map JSON valid"]
            elif mid == "M1":
                acceptance = ["Skeleton compiles/imports", "Test runner can execute zero tests successfully"]
            elif mid == "M2":
                acceptance = ["Unit tests cover core happy paths", "Type checks pass for typed languages"]
            elif mid == "M3":
                acceptance = ["Integration tests cover cross-module flows", "API contract consistent"]
            elif mid == "M3.5":
                acceptance = ["Benchmarks established", "No regressions vs baseline"]
            elif mid == "M3.6":
                acceptance = ["Compliance checklist complete", "Audit trail reviewed and signed off"]
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
                dependencies=[] if not out else [out[-1].milestone_id],
                acceptance_criteria=acceptance,
                quality_gates=quality_gates,
                estimated_risk=risk,
                allowed_languages=languages,
                out_of_scope=[],
            ))
        return out
