"""Pydantic schemas for the CrewAI multi-CLI software factory.

All structured I/O between agents, executors, gates and reports flows through
these models so that runs are replayable, auditable, and fail-closed.
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, model_validator


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class InputType(str, Enum):
    GITHUB_ISSUE = "github_issue"
    LOCAL_ISSUE = "local_issue"
    PROJECT_BRIEF = "project_brief"
    PRD = "prd"
    ARCHITECTURE_DOC = "architecture_doc"
    EMPTY_REPO_PROJECT = "empty_repo_project"
    EXISTING_REPO_PROJECT = "existing_repo_project"
    MILESTONE_REQUEST = "milestone_request"
    BUGFIX_REQUEST = "bugfix_request"
    UNKNOWN = "unknown"


class PipelineMode(str, Enum):
    DRY_RUN = "dry-run"
    APPLY = "apply"


class Language(str, Enum):
    PYTHON = "python"
    RUST = "rust"
    TYPESCRIPT = "typescript"
    JAVASCRIPT = "javascript"
    MIXED = "mixed"
    UNKNOWN = "unknown"


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class TaskType(str, Enum):
    SCAFFOLD = "scaffold"
    ARCHITECTURE = "architecture"
    FEATURE = "feature"
    REFACTOR = "refactor"
    TEST = "test"
    DOCS = "docs"
    INTEGRATION = "integration"
    SECURITY = "security"
    RELEASE = "release"
    BUGFIX = "bugfix"


class ExecutionBackend(str, Enum):
    CODEX = "codex"
    CLAUDE_CODE = "claude_code"
    MOCK_CODEX = "mock_codex"
    MOCK_CLAUDE = "mock_claude"
    AUTO = "auto"


class GateStatus(str, Enum):
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    NOT_APPLICABLE = "not_applicable"


class ReleaseDecision(str, Enum):
    RELEASE_READY = "ReleaseReady"
    NOT_RELEASE_READY = "NotReleaseReady"
    BLOCKED = "Blocked"


# ---------------------------------------------------------------------------
# Input / Classification
# ---------------------------------------------------------------------------


class InputClassification(BaseModel):
    input_type: InputType
    confidence: float = Field(ge=0.0, le=1.0)
    rationale: str
    detected_languages: list[Language] = Field(default_factory=list)
    suggested_flow: str  # "issue_pipeline_flow" | "project_delivery_flow"
    source_path: str | None = None
    source_url: str | None = None


class IssueRequirements(BaseModel):
    issue_id: str
    title: str
    summary: str
    raw_text: str
    acceptance_criteria: list[str] = Field(default_factory=list)
    impacted_areas: list[str] = Field(default_factory=list)
    labels: list[str] = Field(default_factory=list)
    risk_level: RiskLevel = RiskLevel.LOW


# ---------------------------------------------------------------------------
# Product / Requirements / PRD
# ---------------------------------------------------------------------------


class ProductBrief(BaseModel):
    product_name: str
    goals: list[str]
    user_personas: list[str] = Field(default_factory=list)
    use_cases: list[str] = Field(default_factory=list)
    mvp_scope: list[str] = Field(default_factory=list)
    non_goals: list[str] = Field(default_factory=list)
    delivery_boundary: str = ""


class FunctionalRequirement(BaseModel):
    id: str
    title: str
    description: str
    priority: str = "MUST"  # MUST/SHOULD/COULD/WONT
    acceptance_criteria: list[str] = Field(default_factory=list)


class NonFunctionalRequirement(BaseModel):
    id: str
    category: str  # performance / security / compliance / availability / ...
    description: str
    measurable_target: str | None = None


class AcceptanceCriterion(BaseModel):
    id: str
    description: str
    verifiable_by: str  # test / manual / metric / contract


class PRD(BaseModel):
    product_name: str
    overview: str
    functional_requirements: list[FunctionalRequirement] = Field(default_factory=list)
    non_functional_requirements: list[NonFunctionalRequirement] = Field(default_factory=list)
    acceptance_criteria: list[AcceptanceCriterion] = Field(default_factory=list)
    out_of_scope: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Repo scanning
# ---------------------------------------------------------------------------


class LanguageScanResult(BaseModel):
    language: Language
    detected: bool
    package_files: list[str] = Field(default_factory=list)
    source_dirs: list[str] = Field(default_factory=list)
    test_dirs: list[str] = Field(default_factory=list)
    entrypoints: list[str] = Field(default_factory=list)
    test_framework: str | None = None
    notes: list[str] = Field(default_factory=list)


class RepoScanResult(BaseModel):
    repo_path: str
    is_empty: bool
    is_monorepo: bool
    detected_languages: list[Language]
    language_results: dict[str, LanguageScanResult]
    top_level_dirs: list[str] = Field(default_factory=list)
    has_git: bool = False


# ---------------------------------------------------------------------------
# Architecture
# ---------------------------------------------------------------------------


class ModuleSpec(BaseModel):
    name: str
    purpose: str
    language: Language
    paths: list[str] = Field(default_factory=list)
    depends_on: list[str] = Field(default_factory=list)
    public_interfaces: list[str] = Field(default_factory=list)


class ApiEndpoint(BaseModel):
    name: str
    method: str
    path: str
    description: str
    request_schema: str | None = None
    response_schema: str | None = None


class ApiContract(BaseModel):
    version: str = "0.1.0"
    endpoints: list[ApiEndpoint] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class DataModelEntity(BaseModel):
    name: str
    fields: dict[str, str] = Field(default_factory=dict)
    invariants: list[str] = Field(default_factory=list)


class DataModel(BaseModel):
    entities: list[DataModelEntity] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class DependencyGraph(BaseModel):
    nodes: list[str] = Field(default_factory=list)
    edges: list[tuple[str, str]] = Field(default_factory=list)


class ArchitectureSpec(BaseModel):
    title: str
    overview: str
    modules: list[ModuleSpec] = Field(default_factory=list)
    api_contract: ApiContract = Field(default_factory=ApiContract)
    data_model: DataModel = Field(default_factory=DataModel)
    dependency_graph: DependencyGraph = Field(default_factory=DependencyGraph)
    decisions: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Milestones / Tasks
# ---------------------------------------------------------------------------


class TaskDependency(BaseModel):
    depends_on_task_id: str
    reason: str | None = None


class DeliveryTask(BaseModel):
    task_id: str
    milestone_id: str
    title: str
    description: str
    target_files: list[str] = Field(default_factory=list)
    allowed_files: list[str] = Field(default_factory=list)
    forbidden_files: list[str] = Field(default_factory=list)
    context_files: list[str] = Field(default_factory=list)
    language: Language = Language.UNKNOWN
    task_type: TaskType = TaskType.FEATURE
    dependencies: list[TaskDependency] = Field(default_factory=list)
    codex_prompt: str = ""
    claude_prompt: str = ""
    expected_outputs: list[str] = Field(default_factory=list)
    acceptance_criteria: list[str] = Field(default_factory=list)
    required_tests: list[str] = Field(default_factory=list)
    risk_level: RiskLevel = RiskLevel.LOW
    rollback_strategy: str = ""
    preferred_executor: ExecutionBackend = ExecutionBackend.AUTO


class Milestone(BaseModel):
    milestone_id: str
    title: str
    objective: str
    deliverables: list[str] = Field(default_factory=list)
    task_ids: list[str] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)
    acceptance_criteria: list[str] = Field(default_factory=list)
    quality_gates: list[str] = Field(default_factory=list)
    estimated_risk: RiskLevel = RiskLevel.LOW
    allowed_languages: list[Language] = Field(default_factory=list)
    out_of_scope: list[str] = Field(default_factory=list)


class MilestonePlan(BaseModel):
    milestones: list[Milestone] = Field(default_factory=list)
    tasks: list[DeliveryTask] = Field(default_factory=list)

    def tasks_for(self, milestone_id: str) -> list[DeliveryTask]:
        return [t for t in self.tasks if t.milestone_id == milestone_id]


class ScaffoldPlan(BaseModel):
    project_name: str
    languages: list[Language]
    files_to_create: list[str] = Field(default_factory=list)
    directories_to_create: list[str] = Field(default_factory=list)
    template_engine: str = "jinja2"
    notes: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Execution / Executor Router
# ---------------------------------------------------------------------------


class ExecutorSelectionPolicy(BaseModel):
    default_backend: ExecutionBackend = ExecutionBackend.AUTO
    preferred_backend_by_task_type: dict[str, ExecutionBackend] = Field(default_factory=dict)
    preferred_backend_by_language: dict[str, ExecutionBackend] = Field(default_factory=dict)
    max_files_for_codex: int = 5
    max_risk_for_codex: RiskLevel = RiskLevel.MEDIUM
    claude_for_architecture_changes: bool = True
    claude_for_cross_language_changes: bool = True
    fallback_to_mock: bool = True
    timeout_seconds: int = 600


class ExecutionRequest(BaseModel):
    task_id: str
    milestone_id: str = ""
    repo_path: str
    prompt: str
    language: Language = Language.UNKNOWN
    mode: PipelineMode = PipelineMode.DRY_RUN
    backend: ExecutionBackend = ExecutionBackend.AUTO
    allowed_files: list[str] = Field(default_factory=list)
    forbidden_files: list[str] = Field(default_factory=list)
    context_files: list[str] = Field(default_factory=list)
    risk_level: RiskLevel = RiskLevel.LOW
    task_type: TaskType = TaskType.FEATURE
    timeout: int = 600
    env: dict[str, str] = Field(default_factory=dict)


class ExecutionResult(BaseModel):
    task_id: str
    milestone_id: str = ""
    backend: ExecutionBackend
    selected_backend_reason: str = ""
    fallback_used: bool = False
    mock_used: bool = False
    language: Language = Language.UNKNOWN
    command: str = ""
    exit_code: int = 0
    stdout: str = ""
    stderr: str = ""
    patch: str = ""
    changed_files: list[str] = Field(default_factory=list)
    duration_ms: int = 0
    success: bool = False
    error_type: str | None = None
    safety_flags: list[str] = Field(default_factory=list)
    mode: PipelineMode = PipelineMode.DRY_RUN
    started_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class CodexCallResult(ExecutionResult):
    backend: ExecutionBackend = ExecutionBackend.CODEX


class ClaudeCodeCallResult(ExecutionResult):
    backend: ExecutionBackend = ExecutionBackend.CLAUDE_CODE


class ImplementationResult(BaseModel):
    milestone_id: str
    task_results: list[ExecutionResult] = Field(default_factory=list)
    success: bool = False
    mock_used: bool = False
    failed_task_ids: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Tests / Quality / Security / Review / Verification / Release
# ---------------------------------------------------------------------------


class TestPlanEntry(BaseModel):
    task_id: str | None = None
    milestone_id: str | None = None
    kind: str  # unit / integration / e2e / smoke
    description: str
    target_files: list[str] = Field(default_factory=list)
    command: str | None = None


class TestPlan(BaseModel):
    entries: list[TestPlanEntry] = Field(default_factory=list)


class GateOutcome(BaseModel):
    name: str
    status: GateStatus
    command: str | None = None
    stdout: str = ""
    stderr: str = ""
    exit_code: int | None = None
    notes: list[str] = Field(default_factory=list)


class QualityGateResult(BaseModel):
    language: Language
    outcomes: list[GateOutcome] = Field(default_factory=list)
    overall_status: GateStatus = GateStatus.SKIPPED
    mock_used: bool = False


class SecurityReviewReport(BaseModel):
    findings: list[str] = Field(default_factory=list)
    blocked_commands: list[str] = Field(default_factory=list)
    severity: RiskLevel = RiskLevel.LOW
    status: GateStatus = GateStatus.PASSED


class CodeReviewReport(BaseModel):
    findings: list[str] = Field(default_factory=list)
    coverage_summary: str = ""
    status: GateStatus = GateStatus.PASSED


class IntegrationReviewReport(BaseModel):
    cross_language_consistency: bool = True
    api_contract_consistent: bool = True
    schema_drift_detected: bool = False
    findings: list[str] = Field(default_factory=list)
    status: GateStatus = GateStatus.PASSED


class VerificationReport(BaseModel):
    rerun_tests: list[GateOutcome] = Field(default_factory=list)
    milestone_acceptance: dict[str, GateStatus] = Field(default_factory=dict)
    state_integrity_ok: bool = True
    status: GateStatus = GateStatus.PASSED
    notes: list[str] = Field(default_factory=list)


class ReleaseCheckReport(BaseModel):
    all_milestones_complete: bool = False
    all_acceptance_evidence_present: bool = False
    open_critical_issues: int = 0
    delivery_report_present: bool = False
    docs_present: bool = False
    mock_execution_used: bool = False
    dry_run: bool = True
    decision: ReleaseDecision = ReleaseDecision.NOT_RELEASE_READY
    reasons: list[str] = Field(default_factory=list)


class DeliveryReport(BaseModel):
    run_id: str
    project_name: str
    mode: PipelineMode
    backends_used: list[ExecutionBackend] = Field(default_factory=list)
    mock_execution_used: bool = False
    milestones: list[Milestone] = Field(default_factory=list)
    release_decision: ReleaseDecision = ReleaseDecision.NOT_RELEASE_READY
    summary: str = ""
    generated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# ---------------------------------------------------------------------------
# Overall pipeline run state
# ---------------------------------------------------------------------------


class PipelineRunState(BaseModel):
    run_id: str
    started_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    finished_at: str | None = None
    mode: PipelineMode = PipelineMode.DRY_RUN
    flow: str = ""  # issue_pipeline_flow / project_delivery_flow
    repo_path: str
    languages: list[Language] = Field(default_factory=list)
    classification: InputClassification | None = None
    issue: IssueRequirements | None = None
    product_brief: ProductBrief | None = None
    prd: PRD | None = None
    architecture: ArchitectureSpec | None = None
    repo_scan: RepoScanResult | None = None
    milestone_plan: MilestonePlan | None = None
    scaffold_plan: ScaffoldPlan | None = None
    implementation_results: list[ImplementationResult] = Field(default_factory=list)
    quality_gates: list[QualityGateResult] = Field(default_factory=list)
    security_review: SecurityReviewReport | None = None
    code_review: CodeReviewReport | None = None
    integration_review: IntegrationReviewReport | None = None
    verification: VerificationReport | None = None
    release_check: ReleaseCheckReport | None = None
    delivery_report: DeliveryReport | None = None
    backends_used: list[ExecutionBackend] = Field(default_factory=list)
    mock_execution_used: bool = False
    errors: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _normalize(self) -> "PipelineRunState":
        # de-dupe backends
        seen: list[ExecutionBackend] = []
        for b in self.backends_used:
            if b not in seen:
                seen.append(b)
        self.backends_used = seen
        return self

    def add_error(self, msg: str) -> None:
        self.errors.append(msg)

    def mark_backend(self, backend: ExecutionBackend) -> None:
        if backend not in self.backends_used:
            self.backends_used.append(backend)
        if backend in (ExecutionBackend.MOCK_CODEX, ExecutionBackend.MOCK_CLAUDE):
            self.mock_execution_used = True


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def dump_model(model: BaseModel) -> dict[str, Any]:
    return model.model_dump(mode="json")
