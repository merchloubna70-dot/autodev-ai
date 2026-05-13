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
    # BF2: inner steps recorded by executors that support structured JSON output
    inner_steps: list[dict] = Field(default_factory=list)


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
    severity_findings: list["SeverityFinding"] = Field(default_factory=list)
    false_positives_filtered: list[str] = Field(default_factory=list)


class CodeReviewReport(BaseModel):
    findings: list[str] = Field(default_factory=list)
    coverage_summary: str = ""
    status: GateStatus = GateStatus.PASSED
    severity_findings: list["SeverityFinding"] = Field(default_factory=list)


class IntegrationReviewReport(BaseModel):
    cross_language_consistency: bool = True
    api_contract_consistent: bool = True
    schema_drift_detected: bool = False
    findings: list[str] = Field(default_factory=list)
    status: GateStatus = GateStatus.PASSED
    severity_findings: list["SeverityFinding"] = Field(default_factory=list)


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


# === MARKER OPENAPI === (Agent C appends OpenAPI / JSON-Schema diff models below this line)


class ContractDiffReport(BaseModel):
    """Result of an OpenAPI / JSON-Schema diff between two API versions."""

    added_endpoints: list[str] = Field(default_factory=list)
    removed_endpoints: list[str] = Field(default_factory=list)
    changed_endpoints: list[dict] = Field(default_factory=list)
    breaking_change: bool = False
    summary: str = ""

    @model_validator(mode="after")
    def _compute_breaking(self) -> "ContractDiffReport":
        has_changed_types = any(
            entry.get("changed_types") for entry in self.changed_endpoints
        )
        self.breaking_change = bool(self.removed_endpoints or has_changed_types)
        return self


# === MARKER TELEMETRY === (Agent D appends router cost/latency telemetry models below this line)


_BACKEND_COST_PER_KTOKEN_CENTS: dict[ExecutionBackend, float] = {
    ExecutionBackend.CODEX: 0.5,
    ExecutionBackend.CLAUDE_CODE: 2.5,
    ExecutionBackend.MOCK_CODEX: 0.0,
    ExecutionBackend.MOCK_CLAUDE: 0.0,
}


class ExecutorMetricSample(BaseModel):
    task_id: str
    milestone_id: str = ""
    backend: ExecutionBackend
    mock_used: bool = False
    fallback_used: bool = False
    duration_ms: int = 0
    estimated_tokens: int = 0          # heuristic: len(prompt) // 4 plus len(stdout) // 4
    estimated_cost_cents: float = 0.0  # backend-specific rate (rough; see policy)
    success: bool = True
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class RouterMetricsSummary(BaseModel):
    total_calls: int = 0
    total_duration_ms: int = 0
    total_estimated_tokens: int = 0
    total_estimated_cost_cents: float = 0.0
    by_backend: dict[str, int] = Field(default_factory=dict)
    mock_call_count: int = 0
    success_count: int = 0
    failure_count: int = 0
    samples: list[ExecutorMetricSample] = Field(default_factory=list)

    def add(self, sample: ExecutorMetricSample) -> None:
        self.total_calls += 1
        self.total_duration_ms += sample.duration_ms
        self.total_estimated_tokens += sample.estimated_tokens
        self.total_estimated_cost_cents += sample.estimated_cost_cents
        self.by_backend[sample.backend.value] = self.by_backend.get(sample.backend.value, 0) + 1
        if sample.mock_used:
            self.mock_call_count += 1
        if sample.success:
            self.success_count += 1
        else:
            self.failure_count += 1
        self.samples.append(sample)


class BudgetHint(BaseModel):
    max_cost_cents: float | None = None
    prefer_cheaper_backend: bool = False


# === MARKER OPUS === (Agent E appends OpusConsult / FailureCluster models below this line)


class OpusConsultMode(str, Enum):
    ARCHITECT = "architect"
    REVIEWER = "reviewer"


class OpusConsultResult(BaseModel):
    mode: OpusConsultMode
    prompt_sha: str
    response_text: str
    exit_code: int = 0
    duration_ms: int = 0
    mock_used: bool = False
    verdict: str | None = None  # APPROVE / REQUEST_CHANGES / REJECT — reviewer only


class FailureClusterReport(BaseModel):
    milestone_id: str
    failure_count: int
    failed_task_ids: list[str]
    review_text: str = ""
    opus_consulted: bool = False
    opus_result: OpusConsultResult | None = None


# === MARKER FOURSTAGE === (Agent F appends 4-stage bug fix / WorkerIsolation models below this line)


class FourStagePlan(BaseModel):
    bug_description: str
    repo_path: str
    tasks: list[DeliveryTask] = Field(default_factory=list)
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class WorkerIsolationManifest(BaseModel):
    worker_id: str
    worker_codex_home: str
    worker_worktree: str | None = None
    symlinks_created: list[str] = Field(default_factory=list)
    private_dirs_created: list[str] = Field(default_factory=list)


# === MARKER W1 REPO-INTEL === (Wave 1 — RepoMap + Navigator + ContextProvider models below)


class RepoMapEntry(BaseModel):
    file_path: str
    signature_summary: str = ""
    score: float = 0.0
    symbol_count: int = 0


class RepoMap(BaseModel):
    repo_path: str
    entries: list[RepoMapEntry] = Field(default_factory=list)
    token_budget: int = 1024
    seeds: list[str] = Field(default_factory=list)


class NavigatorResult(BaseModel):
    task_id: str
    files: list[str] = Field(default_factory=list)
    symbols: list[str] = Field(default_factory=list)
    call_chains: list[str] = Field(default_factory=list)
    repo_map_excerpt: list[RepoMapEntry] = Field(default_factory=list)


# === MARKER W2 IMPLEMENTER-LOOP === (Wave 2 — architect/editor split + critic + SR-edit models below)


class CriticVerdict(BaseModel):
    score: float = 0.0
    done: bool = False
    notes: list[str] = Field(default_factory=list)
    iteration: int = 0


class ArchitectPlan(BaseModel):
    task_id: str
    plan_steps: list[str] = Field(default_factory=list)
    risk_notes: list[str] = Field(default_factory=list)
    target_files: list[str] = Field(default_factory=list)


class SearchReplaceBlock(BaseModel):
    file_path: str
    search_text: str
    replace_text: str


class LintGateResult(BaseModel):
    language: str
    ok: bool = True
    errors: list[str] = Field(default_factory=list)
    changed_files: list[str] = Field(default_factory=list)


# === MARKER W3 PROMPT-SANDBOX === (Wave 3 — convention-load + network allowlist models below)


class RepoConventions(BaseModel):
    sources: list[str] = Field(default_factory=list)  # file paths consulted
    body: str = ""
    char_count: int = 0
    truncated: bool = False


class AllowVerdict(BaseModel):
    target: str
    allowed: bool
    matched_rule: str | None = None
    reason: str = ""


class NetworkAllowlistPolicy(BaseModel):
    default_deny: bool = True
    allow_domains: list[str] = Field(default_factory=list)
    allow_cidrs: list[str] = Field(default_factory=list)
    audit_only: bool = True


# === MARKER W4 REVIEW-QUALITY === (Wave 4 — severity + parallel-section review models below)


class Severity(str, Enum):
    BLOCKER = "blocker"
    MAJOR = "major"
    MINOR = "minor"
    NITPICK = "nitpick"


class SeverityFinding(BaseModel):
    severity: Severity
    category: str  # "security" / "perf" / "style" / "correctness" / ...
    title: str
    detail: str = ""
    file_path: str | None = None
    line: int | None = None
    suggested_fix: str | None = None
    source_agent: str = ""


class ParallelSectionReviewReport(BaseModel):
    sections: list[str] = Field(default_factory=list)  # which sub-reviewers ran
    findings: list[SeverityFinding] = Field(default_factory=list)
    blocker_count: int = 0
    major_count: int = 0
    minor_count: int = 0
    nitpick_count: int = 0
    synthesis_summary: str = ""

    @model_validator(mode="after")
    def _count(self) -> "ParallelSectionReviewReport":
        for f in self.findings:
            if f.severity == Severity.BLOCKER:
                self.blocker_count += 1
            elif f.severity == Severity.MAJOR:
                self.major_count += 1
            elif f.severity == Severity.MINOR:
                self.minor_count += 1
            else:
                self.nitpick_count += 1
        return self


# === MARKER W5 PRECHECK === (Wave 5 — clarification + property-test + 3-pass locate models below)


class ClarificationDecision(BaseModel):
    needs_clarification: bool = False
    question: str | None = None
    rationale: str = ""


class PropertyTestSuggestion(BaseModel):
    target_file: str
    function_name: str
    given_strategies: list[str] = Field(default_factory=list)  # e.g. ["integers()", "text(min_size=1)"]
    invariants: list[str] = Field(default_factory=list)  # human-readable invariant
    risk_notes: list[str] = Field(default_factory=list)


class LocatePassResult(BaseModel):
    pass_kind: str  # "repo-tree" / "skeleton" / "line-range"
    candidates: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class ThreePassLocateReport(BaseModel):
    task_id: str
    repo_tree_pass: LocatePassResult | None = None
    skeleton_pass: LocatePassResult | None = None
    line_range_pass: LocatePassResult | None = None
    final_target: str | None = None


# === MARKER W6 MCP-UI-EMBED === (Wave 6 — MCP client + replay UI + embeddings models below)


class MCPToolDescriptor(BaseModel):
    name: str
    description: str = ""
    input_schema: dict = Field(default_factory=dict)


class MCPCallResult(BaseModel):
    tool_name: str
    success: bool
    response_text: str = ""
    error: str | None = None
    duration_ms: int = 0
    mock_used: bool = False


class ReplayStep(BaseModel):
    step_index: int
    timestamp: str
    backend: str
    task_id: str
    success: bool
    duration_ms: int = 0
    summary: str = ""


class EmbeddingHit(BaseModel):
    run_id: str
    text_id: str
    score: float
    snippet: str = ""


# === MARKER W7 BUGFIX-PLUS === (Wave 7 — multi-patch self-consistency + HumanReviewGate models below)


class PatchCandidate(BaseModel):
    candidate_id: str
    seed: str
    patch_text: str = ""
    changed_files: list[str] = Field(default_factory=list)
    test_pass_count: int = 0
    test_fail_count: int = 0
    score: float = 0.0


class MultiPatchVote(BaseModel):
    candidates: list[PatchCandidate] = Field(default_factory=list)
    winner_candidate_id: str | None = None
    rationale: str = ""
    mock_used: bool = False


class HumanReviewDecision(BaseModel):
    decision: str = "pending"  # pending / approved / rejected
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    notes: str = ""
    pending_review_file: str | None = None


# === MARKER W8 FRAMEWORK-MOD === (Wave 8 — CrewAI Flow rewrite + SandboxedExecutor + Pydantic-AI models below)


class CrewFlowNodeRecord(BaseModel):
    node_name: str
    started_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    finished_at: str | None = None
    success: bool = True
    listener_of: list[str] = Field(default_factory=list)


class SandboxedExecutionContext(BaseModel):
    inner_backend: str
    network_audit_only: bool = True
    allow_domains: list[str] = Field(default_factory=list)
    sandbox_provider: str = "none"  # "none" / "e2b" / "modal" / "anthropic-sandbox-runtime"


class PydanticAIBridgeStatus(BaseModel):
    pydantic_ai_available: bool = False
    fallback_to_stub: bool = True
    stub_reason: str = ""


# === MARKER BF1 PROMPT === (Bugfix agent BF1 appends task-prompt-context models below)


class TaskPromptContext(BaseModel):
    product_name: str = ""
    prd_overview: str = ""
    acceptance_criteria: list[str] = Field(default_factory=list)
    delivery_boundary: str = ""
    non_goals: list[str] = Field(default_factory=list)
    include_in_prompt: bool = True


def render_task_prompt(
    *,
    task_id: str,
    title: str,
    description: str,
    target_files: list[str],
    context: "TaskPromptContext | None" = None,
) -> str:
    """Pure helper: assemble structured task prompt. Stable, testable."""
    lines = [f"[{task_id}] {title}"]
    if context and context.include_in_prompt:
        if context.product_name:
            lines.append(f"PRODUCT: {context.product_name}")
        if context.prd_overview:
            lines.append(f"OVERVIEW: {context.prd_overview}")
        if context.acceptance_criteria:
            lines.append("ACCEPTANCE CRITERIA:")
            for ac in context.acceptance_criteria:
                lines.append(f"  - {ac}")
        if context.delivery_boundary:
            lines.append(f"DELIVERY BOUNDARY: {context.delivery_boundary}")
        if context.non_goals:
            lines.append("NON-GOALS: " + "; ".join(context.non_goals))
    lines.append(f"YOUR TASK: {description}")
    if target_files:
        lines.append(f"TARGET FILES: {target_files}")
    return "\n".join(lines)


# === MARKER BF2 EXECUTOR === (Bugfix agent BF2 appends executor inner-audit models below)


class CodexInnerStep(BaseModel):
    step_index: int
    kind: str = ""              # "tool" / "thinking" / "shell" / "patch" / "result"
    content_summary: str = ""
    command: str | None = None
    exit_code: int | None = None
    duration_ms: int = 0


class FilesystemObservation(BaseModel):
    method: str = "none"         # "git" / "mtime-walk" / "none"
    before_count: int = 0
    after_count: int = 0
    added: list[str] = Field(default_factory=list)
    modified: list[str] = Field(default_factory=list)
    deleted: list[str] = Field(default_factory=list)



# === MARKER A2A === (A2A-compatible Task / Message / Part / AgentCard models below)


class A2APart(BaseModel):
    kind: str  # "text" / "data" / "file"
    text: str | None = None
    data: dict | None = None
    mime_type: str | None = None
    filename: str | None = None


class A2AMessage(BaseModel):
    message_id: str
    role: str  # "user" / "agent" / "system"
    parts: list[A2APart] = Field(default_factory=list)
    context_id: str | None = None
    task_id: str | None = None
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class A2ATaskStatus(str, Enum):
    SUBMITTED = "submitted"
    WORKING = "working"
    INPUT_REQUIRED = "input-required"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELED = "canceled"


class A2ATask(BaseModel):
    id: str
    context_id: str
    status: A2ATaskStatus = A2ATaskStatus.SUBMITTED
    history: list[A2AMessage] = Field(default_factory=list)
    artifacts: list[A2APart] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str | None = None


class AgentCard(BaseModel):
    name: str
    description: str = ""
    version: str = "0.1.0"
    capabilities: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    transport: str = "local-shell"  # "local-shell" / "mock" / "a2a-http"
    endpoint: str | None = None     # http URL when transport == "a2a-http"
    auth_scheme: str | None = None  # "none" / "bearer" / "oauth2"
    model_hint: str | None = None   # "opus" / "sonnet" / "haiku"
    system_prompt: str | None = None
    tags: list[str] = Field(default_factory=list)


class A2ARosterEntry(BaseModel):
    card: AgentCard
    registered_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    active: bool = True


class A2AConversation(BaseModel):
    conversation_id: str
    task_id: str
    participating_cards: list[str] = Field(default_factory=list)  # AgentCard.name list
    messages: list[A2AMessage] = Field(default_factory=list)


# === MARKER SRV1 MCP-SERVER ===


class MCPToolHandlerResult(BaseModel):
    tool_name: str
    success: bool
    content_text: str = ""
    content_json: dict | None = None
    error: str | None = None
    duration_ms: int = 0


class MCPServerStatus(BaseModel):
    protocol_version: str = "2024-11-05"
    tools_count: int = 0
    uptime_seconds: float = 0.0


# === MARKER SRV2 A2A-SERVER ===


class A2AHttpServerConfig(BaseModel):
    bind: str = "127.0.0.1"
    port: int = 8421
    auth_token_env: str = "AUTODEV_A2A_TOKEN"
    max_concurrent_tasks: int = 4
    enable_sse: bool = True


class A2AServerTaskRecord(BaseModel):
    task: "A2ATask"
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str | None = None
    handler_name: str = ""
    error: str | None = None


# === MARKER SRV3 A2A-HTTP-CLIENT ===


class A2AHttpTransportConfig(BaseModel):
    endpoint: str
    auth_token: str | None = None
    timeout_sec: int = 120
    poll_interval: float = 1.0
    max_poll_attempts: int = 60
    verify_tls: bool = True


class A2ARemoteAgentRegistration(BaseModel):
    card: AgentCard
    registered_via: str = "manual"  # "manual" / "discovered" / "config"
    last_reachability_check_at: str | None = None
    reachable: bool | None = None


# === MARKER BMAD1 SCALE ===


class Scale(str, Enum):
    BUG_FIX = "bug-fix"
    SMALL = "small"
    MEDIUM = "medium"
    ENTERPRISE = "enterprise"


class ScaleInferenceReport(BaseModel):
    scale: Scale
    reasoning: list[str] = Field(default_factory=list)
    ac_count: int = 0
    fr_count: int = 0
    language_count: int = 0
    risk_level: str = "low"


# === MARKER BMAD2 ADV-EDGE ===


class AdversarialFinding(BaseModel):
    attack_vector: str  # "injection" / "auth-bypass" / "race" / "supply-chain" / ...
    abuse_path: str
    mitigation_hint: str = ""
    severity_finding: SeverityFinding | None = None


class EdgeCasePattern(BaseModel):
    category: str  # "empty" / "huge" / "unicode" / "concurrent" / "resource" / "network" / "timezone" / "numeric"
    file_path: str | None = None
    line: int | None = None
    hint: str = ""
    severity_finding: SeverityFinding | None = None


# === MARKER BMAD3 NEXT-ADVISOR ===


class NextStepAdvice(BaseModel):
    next_command: str
    rationale: str = ""
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    evidence_paths: list[str] = Field(default_factory=list)
    stage_hint: str = ""  # "ship" / "fix-security" / "fix-quality" / "fix-impl" / "verify" / "apply"


# === MARKER BMAD4 CLARIFY-EDITORIAL ===


class ClarificationRound(BaseModel):
    round_index: int  # 1, 2, or 3
    questions: list[str] = Field(default_factory=list)
    answers: dict[str, str] = Field(default_factory=dict)
    decisions: dict[str, str] = Field(default_factory=dict)  # answer → "must"/"nice"/"deferred"


class ClarificationTranscript(BaseModel):
    rounds: list[ClarificationRound] = Field(default_factory=list)
    final_changes: list[str] = Field(default_factory=list)  # human-readable PRD diff summary
    truncated: bool = False


class EditorialFinding(BaseModel):
    layer: str  # "prose" / "structure"
    check: str  # "typo" / "passive" / "long-sentence" / "missing-h1" / "broken-link" / ...
    line: int | None = None
    snippet: str = ""
    severity_finding: SeverityFinding | None = None


class EditorialReport(BaseModel):
    file_path: str | None = None
    prose_findings: list[EditorialFinding] = Field(default_factory=list)
    structure_findings: list[EditorialFinding] = Field(default_factory=list)
    blocker_count: int = 0
    major_count: int = 0
    minor_count: int = 0
    passable: bool = True


# === MARKER BMAD5 SHARD-DISTILL ===

# === MARKER BMAD6 CONFIG-PRFAQ ===

# === MARKER BMAD7 SPRINT ===
