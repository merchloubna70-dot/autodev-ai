"""Delivery report generation for Project Delivery Mode."""
from __future__ import annotations

from ..schemas import DeliveryReport, PipelineRunState, ReleaseDecision


class DeliveryReporter:
    def build(self, state: PipelineRunState, *, project_name: str) -> DeliveryReport:
        decision = state.release_check.decision if state.release_check else ReleaseDecision.NOT_RELEASE_READY
        summary_parts = [
            f"run_id={state.run_id}",
            f"mode={state.mode.value}",
            f"languages={[lang.value for lang in state.languages]}",
            f"mock={state.mock_execution_used}",
            f"decision={decision.value}",
        ]
        return DeliveryReport(
            run_id=state.run_id,
            project_name=project_name,
            mode=state.mode,
            backends_used=state.backends_used,
            mock_execution_used=state.mock_execution_used,
            milestones=state.milestone_plan.milestones if state.milestone_plan else [],
            release_decision=decision,
            summary="; ".join(summary_parts),
        )

    def render_markdown(self, dr: DeliveryReport) -> str:
        lines = [
            f"# Delivery Report — {dr.project_name}",
            "",
            f"- run_id: `{dr.run_id}`",
            f"- mode: `{dr.mode.value}`",
            f"- mock_execution_used: `{dr.mock_execution_used}`",
            f"- backends_used: {', '.join(b.value for b in dr.backends_used)}",
            f"- release_decision: **{dr.release_decision.value}**",
            "",
            "## Milestones",
        ]
        for m in dr.milestones:
            lines.append(f"- **{m.milestone_id}** {m.title} — {m.objective}")
        lines.append("")
        lines.append(f"_summary_: {dr.summary}")
        lines.append("")
        if dr.mode.value == "dry-run":
            lines.append("> This is a DRY-RUN report; no real changes were applied.")
        if dr.mock_execution_used:
            lines.append("> Mock executor was used; do not treat as a true production delivery.")
        return "\n".join(lines) + "\n"
