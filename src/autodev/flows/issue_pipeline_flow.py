"""Issue Mode flow:

Issue -> InputClassifier -> IssueAnalyst -> RepoExplorer -> SystemArchitect
-> TaskDecomposer -> Implementer -> QualityGate -> CodeReviewer -> Verifier -> CommitAgent -> Final Report
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..agents import (
    CodeReviewerAgent,
    CommitAgent,
    ImplementerAgent,
    InputClassifierAgent,
    IssueAnalystAgent,
    QualityGateAgent,
    RepoExplorerAgent,
    SystemArchitectAgent,
    TaskDecomposerAgent,
    VerifierAgent,
)
from ..agents._crewai_bridge import make_crew
from ..agents.milestone_planner import MilestonePlannerAgent
from ..config import FactoryConfig
from ..executors.executor_router import ExecutorRouter
from ..reports.reporter import Reporter
from ..schemas import (
    ArchitectureSpec,
    DeliveryTask,
    ExecutionBackend,
    Language,
    Milestone,
    PRD,
    PipelineMode,
    RepoScanResult,
)
from ..state import RunState, init_run


@dataclass
class IssuePipelineInput:
    repo_path: str
    issue_text: str
    issue_id: str = "ISSUE-0"
    issue_url: str | None = None
    languages: list[Language] | None = None
    mode: PipelineMode = PipelineMode.DRY_RUN
    backend: ExecutionBackend = ExecutionBackend.AUTO
    allow_mock: bool = True
    commit: bool = False
    push: bool = False
    tag: bool = False


class IssuePipelineFlow:
    def __init__(self, config: FactoryConfig | None = None):
        self.config = config or FactoryConfig()
        self.classifier = InputClassifierAgent()
        self.issue_analyst = IssueAnalystAgent()
        self.repo_explorer = RepoExplorerAgent()
        self.architect = SystemArchitectAgent()
        self.milestone_planner = MilestonePlannerAgent()
        self.task_decomposer = TaskDecomposerAgent()
        self.router: ExecutorRouter | None = None
        self.implementer: ImplementerAgent | None = None
        self.quality = QualityGateAgent()
        self.code_reviewer = CodeReviewerAgent()
        self.verifier = VerifierAgent()
        self.commit_agent = CommitAgent()
        self.reporter = Reporter()

    def run(self, inp: IssuePipelineInput) -> RunState:
        languages = inp.languages or [Language.PYTHON]
        run = init_run(repo_path=inp.repo_path, mode=inp.mode, flow="issue_pipeline_flow",
                       languages=[l.value for l in languages])

        # Save raw input
        run.save_text("input/raw_input.md", inp.issue_text)

        # 1) classify
        cls = self.classifier.classify(
            text=inp.issue_text, source_url=inp.issue_url, source_path=None,
            has_existing_code=Path(inp.repo_path).exists() and any(Path(inp.repo_path).iterdir()),
        )
        run.state.classification = cls
        run.save_json("input/classification.json", cls)

        # 2) issue parsing
        issue = self.issue_analyst.parse(inp.issue_text, issue_id=inp.issue_id)
        run.state.issue = issue

        # 3) repo scan
        scan: RepoScanResult = self.repo_explorer.explore(inp.repo_path)
        run.state.repo_scan = scan
        run.save_json("input/repo_scan.json", scan)

        # 4) minimal architecture stub (Issue mode reuses existing repo)
        prd_stub = PRD(product_name=issue.title or "issue", overview=issue.summary or "",
                       functional_requirements=[], non_functional_requirements=[], acceptance_criteria=[])
        arch: ArchitectureSpec = self.architect.design(prd=prd_stub, scan=scan, languages=languages)
        run.state.architecture = arch
        run.save_text("architecture/architecture.md", self.architect.render_markdown(arch))
        run.save_json("architecture/architecture.json", arch)

        # 5) single-milestone plan for the issue
        m = Milestone(
            milestone_id="MI-1", title=f"Resolve {issue.issue_id}", objective=issue.title,
            deliverables=[f"Code change addressing {issue.issue_id}"],
            acceptance_criteria=issue.acceptance_criteria or [f"{issue.issue_id} acceptance"],
            quality_gates=["python_gate", "rust_gate", "typescript_gate"],
            allowed_languages=languages,
        )
        tasks: list[DeliveryTask] = self.task_decomposer.decompose(
            milestones=[m],
            architecture=arch,
            languages=languages,
            product_name=issue.title or "issue",
        )
        # If empty (no language matched defaults), synthesize a feature task
        if not tasks:
            from ..planners.task_planner import TaskPlanner
            tasks = TaskPlanner()._build_issue_default(m, issue.title, languages[0] if languages else Language.PYTHON) \
                if hasattr(TaskPlanner, "_build_issue_default") else [
                    DeliveryTask(task_id="MI-1-T1", milestone_id="MI-1", title=issue.title,
                                 description=issue.summary or issue.title)
                ]
        from ..schemas import MilestonePlan
        plan = MilestonePlan(milestones=[m], tasks=tasks)
        run.state.milestone_plan = plan
        run.save_json("planning/milestones.json", plan.milestones)
        run.save_json("planning/tasks.json", plan.tasks)

        # 6) implementation through router
        self.router = ExecutorRouter(self.config, allow_mock=inp.allow_mock)
        self.implementer = ImplementerAgent(self.router)
        impl = self.implementer.run_milestone(
            milestone_id="MI-1", tasks=tasks, run=run, mode=inp.mode, languages=languages,
            concurrency=self.config.concurrency, fail_fast=self.config.fail_fast,
        )
        run.state.implementation_results.append(impl)

        # 7) quality gates
        qg = self.quality.run(repo_path=inp.repo_path, languages=languages, dry_run=inp.mode == PipelineMode.DRY_RUN)
        run.state.quality_gates = qg
        run.save_json("quality/quality_gate.json", qg)

        # 8) code review
        cr = self.code_reviewer.review(tasks=tasks, results=impl.task_results)
        run.state.code_review = cr
        run.save_json("quality/code_review.json", cr)

        # 9) verification
        v = self.verifier.verify(run.state)
        run.state.verification = v
        run.save_json("verification/verification_report.json", v)

        # 10) commit artifacts (default off for write ops)
        artifacts = self.commit_agent.build_artifacts(state=run.state, project_name=issue.title or "issue", issue_id=issue.issue_id)
        run.save_text("delivery/PR_BODY.md", artifacts.pr_body)
        run.save_text("delivery/COMMIT_MSG.txt", artifacts.commit_message)

        # 11) optional crew kickoff to make CrewAI participation visible
        crew = make_crew(
            agents=[self.classifier.agent, self.issue_analyst.agent, self.repo_explorer.agent,
                    self.architect.agent, self.task_decomposer.agent, self.quality.agent,
                    self.code_reviewer.agent, self.verifier.agent, self.commit_agent.agent],
            tasks=[],
        )
        run.save_json("execution/crew_assembly.json",
                      {"agents": [type(a).__name__ for a in (crew.agents if hasattr(crew, 'agents') else [])]})

        # 12) final report
        self.reporter.write_final_report(run)
        run.finish()
        return run
