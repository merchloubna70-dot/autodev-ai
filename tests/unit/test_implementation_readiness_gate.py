"""Unit tests for ImplementationReadinessGate — 6 checks + happy path."""
from __future__ import annotations

import pytest

from autodev.gates.implementation_readiness_gate import ImplementationReadinessGate
from autodev.schemas import (
    AcceptanceCriterion,
    ArchitectureSpec,
    ComponentSpec,
    DeliveryTask,
    DependencyGraph,
    FunctionalRequirement,
    Language,
    Milestone,
    MilestonePlan,
    ModuleSpec,
    PipelineRunState,
    PRD,
    Severity,
    UXDesignSpec,
    CodeReviewReport,
    SecurityReviewReport,
    SeverityFinding,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _minimal_prd() -> PRD:
    return PRD(
        product_name="TestApp",
        overview="A test product overview",
        functional_requirements=[
            FunctionalRequirement(
                id="FR-1",
                title="User login",
                description="Users can log in with email/password",
            )
        ],
        acceptance_criteria=[
            AcceptanceCriterion(
                id="AC-1",
                description="User can login successfully with valid credentials",
                verifiable_by="test",
            )
        ],
    )


def _minimal_arch() -> ArchitectureSpec:
    return ArchitectureSpec(
        title="TestArch",
        overview="Basic architecture",
        modules=[
            ModuleSpec(name="api", purpose="REST API", language=Language.PYTHON)
        ],
        dependency_graph=DependencyGraph(nodes=["api", "db"], edges=[("api", "db")]),
    )


def _minimal_task() -> DeliveryTask:
    return DeliveryTask(
        task_id="T-1",
        milestone_id="M-1",
        title="Implement login endpoint",
        description="Build the /login POST route",
        target_files=["src/api/auth.py"],
        acceptance_criteria=["Returns 200 on valid credentials"],
    )


def _minimal_milestone() -> Milestone:
    return Milestone(
        milestone_id="M-1",
        title="Alpha",
        objective="Ship MVP",
        acceptance_criteria=["User login works with valid credentials"],
    )


def _base_state(**kwargs) -> PipelineRunState:
    return PipelineRunState(
        run_id="test-run-1",
        repo_path="/tmp/test",
        **kwargs,
    )


# ---------------------------------------------------------------------------
# Check 1: PRD completeness
# ---------------------------------------------------------------------------


class TestCheckPrdComplete:
    gate = ImplementationReadinessGate()

    def test_passes_with_valid_prd(self):
        result = self.gate.check_prd_complete(_minimal_prd())
        assert result.passed is True
        assert result.check_name == "prd_complete"

    def test_fails_when_prd_is_none(self):
        result = self.gate.check_prd_complete(None)
        assert result.passed is False
        assert result.severity == Severity.BLOCKER

    def test_fails_when_overview_empty(self):
        prd = _minimal_prd()
        prd.overview = "  "
        result = self.gate.check_prd_complete(prd)
        assert result.passed is False
        assert any("overview" in d for d in result.details)

    def test_fails_when_no_functional_requirements(self):
        prd = _minimal_prd()
        prd.functional_requirements = []
        result = self.gate.check_prd_complete(prd)
        assert result.passed is False

    def test_fails_when_no_acceptance_criteria(self):
        prd = _minimal_prd()
        prd.acceptance_criteria = []
        result = self.gate.check_prd_complete(prd)
        assert result.passed is False


# ---------------------------------------------------------------------------
# Check 2: Architecture presence
# ---------------------------------------------------------------------------


class TestCheckArchitecturePresent:
    gate = ImplementationReadinessGate()

    def test_passes_with_valid_arch(self):
        result = self.gate.check_architecture_present(_minimal_arch())
        assert result.passed is True
        assert result.check_name == "architecture_present"

    def test_fails_when_arch_is_none(self):
        result = self.gate.check_architecture_present(None)
        assert result.passed is False
        assert result.severity == Severity.BLOCKER

    def test_fails_when_no_modules(self):
        arch = _minimal_arch()
        arch.modules = []
        result = self.gate.check_architecture_present(arch)
        assert result.passed is False

    def test_fails_when_no_dependency_graph_nodes(self):
        arch = _minimal_arch()
        arch.dependency_graph = DependencyGraph(nodes=[], edges=[])
        result = self.gate.check_architecture_present(arch)
        assert result.passed is False


# ---------------------------------------------------------------------------
# Check 3: UX alignment
# ---------------------------------------------------------------------------


class TestCheckUxAlignment:
    gate = ImplementationReadinessGate()

    def test_skips_when_no_ux_spec(self):
        result = self.gate.check_ux_alignment(_minimal_prd(), None)
        assert result.passed is True
        assert "skipping" in result.details[0].lower()

    def test_passes_when_requirements_matched_by_component(self):
        ux = UXDesignSpec(
            product_name="TestApp",
            components=[
                ComponentSpec(name="LoginForm", purpose="Handles user login flow")
            ],
        )
        result = self.gate.check_ux_alignment(_minimal_prd(), ux)
        assert result.passed is True

    def test_fails_when_requirement_has_no_ux_coverage(self):
        prd = PRD(
            product_name="TestApp",
            overview="Overview",
            functional_requirements=[
                FunctionalRequirement(
                    id="FR-99",
                    title="payment integration",
                    description="Process payments",
                )
            ],
            acceptance_criteria=[],
        )
        ux = UXDesignSpec(
            product_name="TestApp",
            components=[ComponentSpec(name="LoginForm", purpose="login")],
        )
        result = self.gate.check_ux_alignment(prd, ux)
        assert result.passed is False
        assert "FR-99" in result.details[0]


# ---------------------------------------------------------------------------
# Check 4: Epics coverage
# ---------------------------------------------------------------------------


class TestCheckEpicsCoverage:
    gate = ImplementationReadinessGate()

    def test_passes_when_all_ac_covered(self):
        result = self.gate.check_epics_coverage([_minimal_milestone()], _minimal_prd())
        assert result.passed is True

    def test_fails_when_no_milestones(self):
        result = self.gate.check_epics_coverage([], _minimal_prd())
        assert result.passed is False
        assert result.severity == Severity.BLOCKER

    def test_skips_when_no_prd(self):
        result = self.gate.check_epics_coverage([_minimal_milestone()], None)
        assert result.passed is True

    def test_fails_when_ac_not_referenced(self):
        prd = _minimal_prd()
        prd.acceptance_criteria = [
            AcceptanceCriterion(
                id="AC-X",
                description="Supports payment processing gateway integration",
                verifiable_by="test",
            )
        ]
        milestone = Milestone(
            milestone_id="M-1",
            title="Alpha",
            objective="Ship MVP",
            acceptance_criteria=["User login works fine"],
        )
        result = self.gate.check_epics_coverage([milestone], prd)
        assert result.passed is False
        assert "AC-X" in result.details[0]


# ---------------------------------------------------------------------------
# Check 5: Story quality
# ---------------------------------------------------------------------------


class TestCheckStoryQuality:
    gate = ImplementationReadinessGate()

    def test_passes_with_valid_tasks(self):
        result = self.gate.check_story_quality([_minimal_task()])
        assert result.passed is True

    def test_fails_when_no_tasks(self):
        result = self.gate.check_story_quality([])
        assert result.passed is False

    def test_fails_when_task_missing_title(self):
        task = _minimal_task()
        task.title = ""
        result = self.gate.check_story_quality([task])
        assert result.passed is False
        assert any("title" in d for d in result.details)

    def test_fails_when_task_missing_acceptance_criteria(self):
        task = _minimal_task()
        task.acceptance_criteria = []
        result = self.gate.check_story_quality([task])
        assert result.passed is False

    def test_fails_when_task_has_no_scope(self):
        task = _minimal_task()
        task.target_files = []
        task.claude_prompt = ""
        task.codex_prompt = ""
        result = self.gate.check_story_quality([task])
        assert result.passed is False

    def test_passes_when_scope_via_prompt(self):
        task = _minimal_task()
        task.target_files = []
        task.claude_prompt = "Implement /login route in FastAPI"
        result = self.gate.check_story_quality([task])
        assert result.passed is True


# ---------------------------------------------------------------------------
# Check 6: Final assessment
# ---------------------------------------------------------------------------


class TestCheckFinalAssessment:
    gate = ImplementationReadinessGate()

    def test_passes_when_no_reviews(self):
        state = _base_state()
        result = self.gate.check_final_assessment(state)
        assert result.passed is True

    def test_passes_when_reviews_have_no_blockers(self):
        state = _base_state(
            code_review=CodeReviewReport(findings=["minor style issue"], status="passed"),
        )
        result = self.gate.check_final_assessment(state)
        assert result.passed is True

    def test_fails_when_security_has_blocker(self):
        blocker = SeverityFinding(
            severity=Severity.BLOCKER,
            category="security",
            title="SQL injection vulnerability",
        )
        state = _base_state(
            security_review=SecurityReviewReport(severity_findings=[blocker]),
        )
        result = self.gate.check_final_assessment(state)
        assert result.passed is False
        assert result.severity == Severity.BLOCKER
        assert "SQL injection" in result.details[0]

    def test_fails_when_code_review_has_blocker(self):
        blocker = SeverityFinding(
            severity=Severity.BLOCKER,
            category="correctness",
            title="Critical null pointer dereference",
        )
        state = _base_state(
            code_review=CodeReviewReport(severity_findings=[blocker]),
        )
        result = self.gate.check_final_assessment(state)
        assert result.passed is False


# ---------------------------------------------------------------------------
# Happy path: full .run() with everything passing
# ---------------------------------------------------------------------------


class TestRunHappyPath:
    gate = ImplementationReadinessGate()

    def test_overall_passed_when_all_checks_green(self):
        state = _base_state(
            prd=_minimal_prd(),
            architecture=_minimal_arch(),
            milestone_plan=MilestonePlan(
                milestones=[_minimal_milestone()],
                tasks=[_minimal_task()],
            ),
        )
        report = self.gate.run(state)
        assert report.overall_passed is True
        assert report.failed_count == 0
        assert report.blocking_count == 0
        assert len(report.checks) == 6
        assert "READY" in report.summary

    def test_overall_fails_when_prd_missing(self):
        state = _base_state(
            architecture=_minimal_arch(),
            milestone_plan=MilestonePlan(
                milestones=[_minimal_milestone()],
                tasks=[_minimal_task()],
            ),
        )
        report = self.gate.run(state)
        assert report.overall_passed is False
        assert report.failed_count >= 1
        assert "NOT READY" in report.summary

    def test_report_has_six_check_results(self):
        state = _base_state()
        report = self.gate.run(state)
        assert len(report.checks) == 6
        names = [c.check_name for c in report.checks]
        assert "prd_complete" in names
        assert "architecture_present" in names
        assert "ux_alignment" in names
        assert "epics_coverage" in names
        assert "story_quality" in names
        assert "final_assessment" in names
