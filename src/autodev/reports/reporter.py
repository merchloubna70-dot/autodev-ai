"""Generic reporter — writes final_report.md and run-state summary."""
from __future__ import annotations

from pathlib import Path

from ..schemas import GateStatus, PipelineRunState, ReleaseDecision
from ..state import RunState


class Reporter:
    def render_final_report(self, run: RunState) -> str:
        s = run.state
        lines: list[str] = []

        # Banner: prepend warning when run is not a clean production delivery
        dry_run = s.mode.value == "dry-run"
        mock_used = s.mock_execution_used
        release_decision = s.release_check.decision if s.release_check else None
        not_release_ready = release_decision != ReleaseDecision.RELEASE_READY
        if dry_run or mock_used or not_release_ready:
            decision_str = release_decision.value if release_decision is not None else "N/A"
            lines.append("> [!WARNING]")
            lines.append("> **NOT a production delivery.**")
            lines.append(f"> - DryRun: `{dry_run}`")
            lines.append(f"> - MockExecutionUsed: `{mock_used}`")
            lines.append(f"> - ReleaseDecision: `{decision_str}`")
            lines.append("")

        lines.append(f"# Final Report — run {s.run_id}")
        lines.append("")
        lines.append(f"- flow: `{s.flow}`")
        lines.append(f"- mode: `{s.mode.value}`")
        lines.append(f"- repo: `{s.repo_path}`")
        lines.append(f"- languages: {', '.join(lang.value for lang in s.languages)}")
        lines.append(f"- backends_used: {', '.join(b.value for b in s.backends_used)}")
        lines.append(f"- MockExecutionUsed: `{s.mock_execution_used}`")
        lines.append(f"- DryRun: `{s.mode.value == 'dry-run'}`")
        lines.append("")
        if s.classification:
            lines.append("## Input Classification")
            lines.append(f"- input_type: `{s.classification.input_type.value}`")
            lines.append(f"- confidence: {s.classification.confidence:.2f}")
            lines.append(f"- rationale: {s.classification.rationale}")
            lines.append("")
        if s.milestone_plan and s.milestone_plan.milestones:
            lines.append("## Milestones")
            for m in s.milestone_plan.milestones:
                lines.append(f"- **{m.milestone_id}** {m.title} — {m.objective}")
            lines.append("")
        if s.implementation_results:
            lines.append("## Implementation")
            for impl in s.implementation_results:
                lines.append(f"- {impl.milestone_id}: success={impl.success} failed_tasks={impl.failed_task_ids}")
            lines.append("")
        if s.quality_gates:
            lines.append("## Quality Gates")
            for qg in s.quality_gates:
                lines.append(f"- {qg.language.value}: {qg.overall_status.value}")
            lines.append("")
        if s.security_review:
            lines.append("## Security Review")
            lines.append(f"- status: {s.security_review.status.value}")
            if s.security_review.blocked_commands:
                lines.append(f"- blocked: {s.security_review.blocked_commands}")
            lines.append("")
        if s.verification:
            lines.append("## Verification")
            lines.append(f"- status: {s.verification.status.value}")
            lines.append(f"- state_integrity_ok: {s.verification.state_integrity_ok}")
            lines.append("")
        if s.release_check:
            lines.append("## Release Decision")
            lines.append(f"- decision: **{s.release_check.decision.value}**")
            for r in s.release_check.reasons:
                lines.append(f"  - {r}")
            lines.append("")
        if s.errors:
            lines.append("## Errors")
            for e in s.errors:
                lines.append(f"- {e}")
            lines.append("")
        # Truthful labeling: never silently re-label skipped/failed as passed
        if any(qg.overall_status in (GateStatus.SKIPPED, GateStatus.FAILED) for qg in s.quality_gates):
            lines.append("> NOTE: One or more gates were skipped or failed; this report does NOT claim release-ready.")
        if s.release_check and s.release_check.decision != ReleaseDecision.RELEASE_READY:
            lines.append(f"> NOTE: Release decision is `{s.release_check.decision.value}`.")
        return "\n".join(lines) + "\n"

    def write_final_report(self, run: RunState) -> str:
        content = self.render_final_report(run)
        path = run.save_text("delivery/final_report.md", content)
        # If the report is large, also write a sharded version for easier navigation
        _SHARD_THRESHOLD = 3000
        if len(content) > _SHARD_THRESHOLD:
            try:
                from ..utils.doc_sharder import DocSharder
                sharder = DocSharder(threshold=_SHARD_THRESHOLD)
                delivery_dir = Path(path).parent
                sharder.shard(content, target_dir=delivery_dir, base_name="final_report_shards")
            except Exception:
                pass  # sharding is best-effort; never break report writing
        return str(path)

    def summarize(self, state: PipelineRunState) -> str:
        return (
            f"run={state.run_id} flow={state.flow} mode={state.mode.value} "
            f"mock={state.mock_execution_used} "
            f"release={state.release_check.decision.value if state.release_check else 'N/A'}"
        )
