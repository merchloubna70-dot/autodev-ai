"""Implementation readiness gate — 6-step BMAD pre-Phase-4 alignment check.

Steps mirror the BMAD bmad-check-implementation-readiness skill:
  1. PRD completeness
  2. Architecture presence
  3. UX alignment
  4. Epics (milestones) coverage
  5. Story (task) quality
  6. Final aggregate assessment
"""
from __future__ import annotations

from ..schemas import (
    PRD,
    ArchitectureSpec,
    DeliveryTask,
    ImplementationReadinessReport,
    Milestone,
    PipelineRunState,
    ReadinessCheckResult,
    Severity,
    UXDesignSpec,
)


class ImplementationReadinessGate:
    """Pure-Python heuristic gate; no LLM calls."""

    # ------------------------------------------------------------------
    # Individual checks
    # ------------------------------------------------------------------

    def check_prd_complete(self, prd: PRD | None) -> ReadinessCheckResult:
        """Check 1: PRD has overview + ≥1 functional_requirement + ≥1 acceptance_criterion."""
        details: list[str] = []
        passed = True

        if prd is None:
            return ReadinessCheckResult(
                check_name="prd_complete",
                passed=False,
                severity=Severity.BLOCKER,
                details=["PRD is missing"],
            )

        if not prd.overview or not prd.overview.strip():
            details.append("PRD overview is empty")
            passed = False

        if not prd.functional_requirements:
            details.append("PRD has no functional requirements")
            passed = False

        if not prd.acceptance_criteria:
            details.append("PRD has no acceptance criteria")
            passed = False

        severity = Severity.BLOCKER if not passed else Severity.MINOR
        return ReadinessCheckResult(
            check_name="prd_complete",
            passed=passed,
            severity=severity,
            details=details,
        )

    def check_architecture_present(self, arch: ArchitectureSpec | None) -> ReadinessCheckResult:
        """Check 2: ArchitectureSpec has ≥1 module + non-empty dependency_graph."""
        details: list[str] = []
        passed = True

        if arch is None:
            return ReadinessCheckResult(
                check_name="architecture_present",
                passed=False,
                severity=Severity.BLOCKER,
                details=["ArchitectureSpec is missing"],
            )

        if not arch.modules:
            details.append("ArchitectureSpec has no modules defined")
            passed = False

        if not arch.dependency_graph.nodes:
            details.append("dependency_graph has no nodes")
            passed = False

        severity = Severity.BLOCKER if not passed else Severity.MINOR
        return ReadinessCheckResult(
            check_name="architecture_present",
            passed=passed,
            severity=severity,
            details=details,
        )

    def check_ux_alignment(
        self,
        prd: PRD | None,
        ux_spec: UXDesignSpec | None,
    ) -> ReadinessCheckResult:
        """Check 3: if UX spec exists, every PRD functional_requirement has ≥1 matching
        UX component name or journey step action (case-insensitive substring match).
        If no UX spec is present, the check is advisory/skipped (PASS with note).
        """
        if ux_spec is None:
            return ReadinessCheckResult(
                check_name="ux_alignment",
                passed=True,
                severity=Severity.MINOR,
                details=["No UX spec present; skipping UX alignment check"],
            )

        if prd is None:
            return ReadinessCheckResult(
                check_name="ux_alignment",
                passed=True,
                severity=Severity.MINOR,
                details=["No PRD present; skipping UX alignment check"],
            )

        # Build searchable corpus from UX spec: component names + journey step actions
        ux_tokens: list[str] = []
        for comp in ux_spec.components:
            ux_tokens.append(comp.name.lower())
            ux_tokens.append(comp.purpose.lower())
        for journey in ux_spec.journeys:
            for step in journey.steps:
                ux_tokens.append(step.action.lower())
                ux_tokens.append(step.touchpoint.lower())

        details: list[str] = []
        unmatched: list[str] = []
        for req in prd.functional_requirements:
            req_words = set(req.title.lower().split()) | set(req.id.lower().split("-"))
            matched = any(
                any(word in token for word in req_words if len(word) > 3)
                for token in ux_tokens
                if token.strip()
            )
            if not matched:
                unmatched.append(req.id)

        if unmatched:
            details.append(
                f"Functional requirements with no UX coverage: {', '.join(unmatched)}"
            )
            return ReadinessCheckResult(
                check_name="ux_alignment",
                passed=False,
                severity=Severity.MAJOR,
                details=details,
            )

        return ReadinessCheckResult(
            check_name="ux_alignment",
            passed=True,
            severity=Severity.MINOR,
            details=[f"All {len(prd.functional_requirements)} functional requirements have UX coverage"],
        )

    def check_epics_coverage(
        self,
        milestones: list[Milestone],
        prd: PRD | None,
    ) -> ReadinessCheckResult:
        """Check 4: every PRD acceptance_criterion.description is referenced (substring)
        by at least one milestone acceptance_criteria entry.
        """
        if prd is None:
            return ReadinessCheckResult(
                check_name="epics_coverage",
                passed=True,
                severity=Severity.MINOR,
                details=["No PRD present; skipping epics coverage check"],
            )

        if not prd.acceptance_criteria:
            return ReadinessCheckResult(
                check_name="epics_coverage",
                passed=True,
                severity=Severity.MINOR,
                details=["PRD has no acceptance criteria to cover"],
            )

        if not milestones:
            return ReadinessCheckResult(
                check_name="epics_coverage",
                passed=False,
                severity=Severity.BLOCKER,
                details=["No milestones/epics defined; cannot cover PRD acceptance criteria"],
            )

        # Aggregate all milestone acceptance criteria text
        all_milestone_ac: list[str] = []
        for m in milestones:
            for mac in m.acceptance_criteria:
                all_milestone_ac.append(mac.lower())

        uncovered: list[str] = []
        for prd_ac in prd.acceptance_criteria:
            needle = prd_ac.description.lower().strip()
            if not needle:
                continue
            # Try keyword overlap: any word >4 chars from AC appears in milestone ACs
            keywords = [w for w in needle.split() if len(w) > 4]
            if not keywords:
                continue
            covered = any(
                any(kw in milestone_ac for kw in keywords)
                for milestone_ac in all_milestone_ac
            )
            if not covered:
                uncovered.append(prd_ac.id)

        if uncovered:
            return ReadinessCheckResult(
                check_name="epics_coverage",
                passed=False,
                severity=Severity.MAJOR,
                details=[
                    f"PRD acceptance criteria not covered by any milestone: {', '.join(uncovered)}"
                ],
            )

        return ReadinessCheckResult(
            check_name="epics_coverage",
            passed=True,
            severity=Severity.MINOR,
            details=[
                f"All {len(prd.acceptance_criteria)} PRD acceptance criteria referenced in milestones"
            ],
        )

    def check_story_quality(self, tasks: list[DeliveryTask]) -> ReadinessCheckResult:
        """Check 5: every task has non-empty title + description + ≥1 acceptance_criterion
        + non-empty target_files OR non-empty claude_prompt/codex_prompt (clear scope).
        """
        if not tasks:
            return ReadinessCheckResult(
                check_name="story_quality",
                passed=False,
                severity=Severity.MAJOR,
                details=["No tasks/stories defined"],
            )

        issues: list[str] = []
        for task in tasks:
            tid = task.task_id
            if not task.title or not task.title.strip():
                issues.append(f"Task {tid}: missing title")
            if not task.description or not task.description.strip():
                issues.append(f"Task {tid}: missing description")
            if not task.acceptance_criteria:
                issues.append(f"Task {tid}: no acceptance criteria")
            has_scope = bool(task.target_files) or bool(task.claude_prompt.strip()) or bool(task.codex_prompt.strip())
            if not has_scope:
                issues.append(f"Task {tid}: no target_files and no prompt scope")

        if issues:
            return ReadinessCheckResult(
                check_name="story_quality",
                passed=False,
                severity=Severity.MAJOR,
                details=issues,
            )

        return ReadinessCheckResult(
            check_name="story_quality",
            passed=True,
            severity=Severity.MINOR,
            details=[f"All {len(tasks)} tasks meet quality bar"],
        )

    def check_final_assessment(self, state: PipelineRunState) -> ReadinessCheckResult:
        """Check 6: aggregate BLOCKER findings from security/code/integration reviews.
        Fails if any BLOCKER severity_finding is present in previous reviewers.
        """
        blocker_sources: list[str] = []

        if state.security_review is not None:
            for sf in state.security_review.severity_findings:
                from ..schemas import Severity as S
                if sf.severity == S.BLOCKER:
                    blocker_sources.append(f"security: {sf.title}")

        if state.code_review is not None:
            for sf in state.code_review.severity_findings:
                from ..schemas import Severity as S
                if sf.severity == S.BLOCKER:
                    blocker_sources.append(f"code: {sf.title}")

        if state.integration_review is not None:
            for sf in state.integration_review.severity_findings:
                from ..schemas import Severity as S
                if sf.severity == S.BLOCKER:
                    blocker_sources.append(f"integration: {sf.title}")

        if blocker_sources:
            return ReadinessCheckResult(
                check_name="final_assessment",
                passed=False,
                severity=Severity.BLOCKER,
                details=[f"BLOCKER findings from previous reviewers: {', '.join(blocker_sources)}"],
            )

        return ReadinessCheckResult(
            check_name="final_assessment",
            passed=True,
            severity=Severity.MINOR,
            details=["No BLOCKER findings from previous reviewers"],
        )

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def run(self, state: PipelineRunState) -> ImplementationReadinessReport:
        """Run all 6 checks and return a structured report."""
        milestones: list[Milestone] = []
        tasks: list[DeliveryTask] = []
        if state.milestone_plan is not None:
            milestones = state.milestone_plan.milestones
            tasks = state.milestone_plan.tasks

        # Retrieve UX spec if stored on state (BMAD-8 populates it)
        ux_spec: UXDesignSpec | None = getattr(state, "ux_design_spec", None)

        checks: list[ReadinessCheckResult] = [
            self.check_prd_complete(state.prd),
            self.check_architecture_present(state.architecture),
            self.check_ux_alignment(state.prd, ux_spec),
            self.check_epics_coverage(milestones, state.prd),
            self.check_story_quality(tasks),
            self.check_final_assessment(state),
        ]

        passed_count = sum(1 for c in checks if c.passed)
        failed_count = len(checks) - passed_count
        blocking_count = sum(
            1 for c in checks if not c.passed and c.severity == Severity.BLOCKER
        )
        overall_passed = failed_count == 0

        if overall_passed:
            summary = f"READY: all {len(checks)} readiness checks passed"
        else:
            summary = (
                f"NOT READY: {failed_count}/{len(checks)} checks failed "
                f"({blocking_count} blocking)"
            )

        return ImplementationReadinessReport(
            checks=checks,
            passed_count=passed_count,
            failed_count=failed_count,
            blocking_count=blocking_count,
            overall_passed=overall_passed,
            summary=summary,
        )
