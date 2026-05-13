"""Release notes / release report renderer."""
from __future__ import annotations

from ..schemas import PipelineRunState


class ReleaseReporter:
    def render_release_notes(self, state: PipelineRunState, *, project_name: str) -> str:
        lines = [
            f"# Release Notes — {project_name}",
            "",
            f"- run_id: `{state.run_id}`",
            f"- mode: `{state.mode.value}`",
            f"- mock_execution_used: `{state.mock_execution_used}`",
            "",
            "## Milestones",
        ]
        if state.milestone_plan:
            for m in state.milestone_plan.milestones:
                lines.append(f"- {m.milestone_id}: {m.title}")
                for ac in m.acceptance_criteria:
                    lines.append(f"  - acceptance: {ac}")
        lines.append("")
        lines.append("## Quality Gates")
        for qg in state.quality_gates:
            lines.append(f"- {qg.language.value}: {qg.overall_status.value}")
        if state.release_check:
            lines.append("")
            lines.append(f"## Decision: **{state.release_check.decision.value}**")
            for r in state.release_check.reasons:
                lines.append(f"- {r}")
        return "\n".join(lines) + "\n"
