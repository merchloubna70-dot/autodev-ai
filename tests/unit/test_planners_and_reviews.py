from autodev.agents.code_reviewer import CodeReviewerAgent
from autodev.agents.integration_reviewer import IntegrationReviewerAgent
from autodev.agents.milestone_planner import MilestonePlannerAgent
from autodev.agents.system_architect import SystemArchitectAgent
from autodev.agents.task_decomposer import TaskDecomposerAgent
from autodev.agents.verifier import VerifierAgent
from autodev.gates.release_gate import ReleaseGate
from autodev.schemas import (
    ApiContract,
    ApiEndpoint,
    DependencyGraph,
    ExecutionResult,
    ExecutionBackend,
    GateStatus,
    Language,
    PRD,
    PipelineRunState,
    ReleaseDecision,
    RepoScanResult,
)


def _basic_prd() -> PRD:
    return PRD(product_name="X", overview="o", functional_requirements=[],
               non_functional_requirements=[], acceptance_criteria=[])


def _basic_scan() -> RepoScanResult:
    return RepoScanResult(repo_path="/tmp", is_empty=False, is_monorepo=False,
                          detected_languages=[Language.PYTHON], language_results={})


def test_milestones_then_tasks():
    arch = SystemArchitectAgent().design(prd=_basic_prd(), scan=_basic_scan(), languages=[Language.PYTHON])
    ms = MilestonePlannerAgent().plan(architecture=arch, languages=[Language.PYTHON])
    tasks = TaskDecomposerAgent().decompose(milestones=ms, architecture=arch, languages=[Language.PYTHON])
    assert ms and tasks
    assert all(t.task_id.startswith(t.milestone_id) for t in tasks)


def test_integration_reviewer_detects_duplicates():
    api = ApiContract(endpoints=[
        ApiEndpoint(name="a", method="get", path="/x", description="d"),
        ApiEndpoint(name="b", method="GET", path="/x", description="d"),
    ])
    r = IntegrationReviewerAgent().review(api_contract=api, dependency_graph=None, languages=[Language.PYTHON])
    assert r.status == GateStatus.FAILED
    assert any("duplicate" in f for f in r.findings)


def test_integration_reviewer_dependency_drift():
    dg = DependencyGraph(nodes=["a"], edges=[("a", "missing")])
    r = IntegrationReviewerAgent().review(api_contract=None, dependency_graph=dg, languages=[Language.PYTHON])
    assert r.schema_drift_detected


def test_code_reviewer_flags_missing_results():
    arch = SystemArchitectAgent().design(prd=_basic_prd(), scan=_basic_scan(), languages=[Language.PYTHON])
    ms = MilestonePlannerAgent().plan(architecture=arch, languages=[Language.PYTHON])
    tasks = TaskDecomposerAgent().decompose(milestones=ms, architecture=arch, languages=[Language.PYTHON])
    r = CodeReviewerAgent().review(tasks=tasks, results=[])
    assert any("no execution result" in f for f in r.findings)


def test_verifier_flags_mock_usage():
    state = PipelineRunState(run_id="x", repo_path="/tmp")
    state.mock_execution_used = True
    v = VerifierAgent().verify(state)
    assert any("mock" in n.lower() for n in v.notes)


def test_release_gate_blocks_on_dry_run_and_mock():
    state = PipelineRunState(run_id="x", repo_path="/tmp")
    state.mock_execution_used = True
    rc = ReleaseGate().check(state)
    assert rc.decision in (ReleaseDecision.NOT_RELEASE_READY, ReleaseDecision.BLOCKED)
    assert any("mock" in r.lower() for r in rc.reasons)
