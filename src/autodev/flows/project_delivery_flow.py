"""Project Delivery Mode flow:

ProjectBrief/PRD -> Classifier -> PM -> RequirementAnalyst -> PRDWriter
-> RepoExplorer -> SystemArchitect -> MilestonePlanner -> TaskDecomposer
-> Scaffolder -> Implementer -> TestDesigner -> QualityGate -> SecurityReviewer
-> CodeReviewer -> IntegrationReviewer -> Verifier -> DocWriter -> ReleaseManager -> DeliveryReport
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..agents import (
    CodeReviewerAgent,
    CommitAgent,
    DocWriterAgent,
    ImplementerAgent,
    InputClassifierAgent,
    IntegrationReviewerAgent,
    MilestonePlannerAgent,
    PRDWriterAgent,
    ProductManagerAgent,
    QualityGateAgent,
    ReleaseManagerAgent,
    RepoExplorerAgent,
    RequirementAnalystAgent,
    ScaffolderAgent,
    SecurityReviewerAgent,
    SystemArchitectAgent,
    TaskDecomposerAgent,
    TestDesignerAgent,
    VerifierAgent,
)
from ..agents._crewai_bridge import make_crew
from ..config import FactoryConfig
from ..executors.executor_router import ExecutorRouter
from ..reports.reporter import Reporter
from ..agents._scaffold_verification import ScaffoldVerification
from ..schemas import (
    ExecutionBackend,
    Language,
    MilestonePlan,
    PipelineMode,
    Scale,
    TaskType,
)
from ..state import RunState, init_run


@dataclass
class ProjectDeliveryInput:
    repo_path: str
    brief_text: str | None = None
    prd_text: str | None = None
    project_name: str | None = None
    languages: list[Language] | None = None
    mode: PipelineMode = PipelineMode.DRY_RUN
    backend: ExecutionBackend = ExecutionBackend.AUTO
    allow_mock: bool = True
    from_scratch: bool = False
    commit: bool = False
    push: bool = False
    tag: bool = False
    scale: Scale | None = None
    prd_style: str = "prd"


class ProjectDeliveryFlow:
    def __init__(self, config: FactoryConfig | None = None):
        self.config = config or FactoryConfig()
        self.classifier = InputClassifierAgent()
        self.pm = ProductManagerAgent()
        self.req = RequirementAnalystAgent()
        self.prd_writer = PRDWriterAgent()
        self.repo_explorer = RepoExplorerAgent()
        self.architect = SystemArchitectAgent()
        self.mplanner = MilestonePlannerAgent()
        self.decomposer = TaskDecomposerAgent()
        self.scaffolder = ScaffolderAgent()
        self.test_designer = TestDesignerAgent()
        self.quality = QualityGateAgent()
        self.security = SecurityReviewerAgent()
        self.code_reviewer = CodeReviewerAgent()
        self.integration_reviewer = IntegrationReviewerAgent()
        self.verifier = VerifierAgent()
        self.doc_writer = DocWriterAgent()
        self.release_manager = ReleaseManagerAgent()
        self.commit_agent = CommitAgent()
        self.reporter = Reporter()

    def run(self, inp: ProjectDeliveryInput) -> RunState:
        languages = inp.languages or [Language.PYTHON]
        source_text = inp.prd_text or inp.brief_text or ""
        Path(inp.repo_path).mkdir(parents=True, exist_ok=True)

        run = init_run(repo_path=inp.repo_path, mode=inp.mode, flow="project_delivery_flow",
                       languages=[l.value for l in languages])
        run.save_text("input/raw_input.md", source_text)

        # 1) classify
        scan_first = self.repo_explorer.explore(inp.repo_path)
        cls = self.classifier.classify(
            text=source_text,
            source_path=None,
            is_empty_repo=scan_first.is_empty,
            has_existing_code=not scan_first.is_empty,
        )
        run.state.classification = cls
        run.save_json("input/classification.json", cls)

        # 2) product brief
        brief = self.pm.build_brief(source_text, product_name=inp.project_name)
        run.state.product_brief = brief
        run.save_json("product/product_brief.json", brief)

        # 3) requirements
        functional, nf, ac = self.req.derive(brief=brief, source_text=source_text)

        # 4) PRD
        prd = self.prd_writer.write(brief=brief, functional=functional, non_functional=nf, acceptance=ac)
        run.state.prd = prd
        run.save_text("product/prd.md", self.prd_writer.render_markdown(prd))
        run.save_json("product/prd.json", prd)

        # 5) repo scan (record)
        run.state.repo_scan = scan_first
        run.save_json("input/repo_scan.json", scan_first)

        # 6) architecture
        arch = self.architect.design(prd=prd, scan=scan_first, languages=languages)
        run.state.architecture = arch
        run.save_text("architecture/architecture.md", self.architect.render_markdown(arch))
        run.save_json("architecture/architecture.json", arch)
        run.save_json("architecture/module_map.json", [m.model_dump(mode="json") for m in arch.modules])
        run.save_json("architecture/api_contract.json", arch.api_contract)
        run.save_json("architecture/data_model.json", arch.data_model)
        run.save_json("architecture/dependency_graph.json", arch.dependency_graph)

        # 7) milestones
        # Resolve scale: use explicit input or auto-infer
        resolved_scale = inp.scale
        if resolved_scale is None:
            scale_report = self.req.infer_scale(
                prd=prd,
                brief=brief,
                languages=languages,
                from_scratch=inp.from_scratch,
            )
            resolved_scale = scale_report.scale
            import sys
            print(f"[autodev] inferred scale={resolved_scale.value} ({'; '.join(scale_report.reasoning)})", file=sys.stderr)
        milestones = self.mplanner.plan(architecture=arch, languages=languages, max_milestones=6, scale=resolved_scale)
        # 8) tasks
        tasks = self.decomposer.decompose(
            milestones=milestones,
            architecture=arch,
            languages=languages,
            prd=prd,
            product_brief=brief,
            product_name=brief.product_name,
            scale=resolved_scale,
        )
        plan = MilestonePlan(milestones=milestones, tasks=tasks)
        run.state.milestone_plan = plan
        run.save_json("planning/milestones.json", milestones)
        run.save_json("planning/tasks.json", tasks)
        run.save_text("planning/delivery_plan.md", _render_delivery_plan(milestones, tasks))

        # 9) scaffold — always run (idempotent with create_only); authoritative skeleton owner.
        # Runs BEFORE the implementation loop so M1 SCAFFOLD tasks can be filtered out when
        # the files are already present.
        sc_plan = self.scaffolder.plan(project_name=brief.product_name, languages=languages)
        run.state.scaffold_plan = sc_plan
        run.save_json("planning/scaffold_plan.json", sc_plan)
        self.scaffolder.apply(plan=sc_plan, repo_path=inp.repo_path, mode=inp.mode)

        # 9b) verify scaffold and filter redundant M1 SCAFFOLD tasks
        sc_verify = self.scaffolder.verify(repo_path=inp.repo_path, plan=sc_plan)
        present_set = set(sc_verify.present_files)

        def _task_files_all_present(task) -> bool:
            """Return True if every target_file for this task already exists on disk."""
            if not task.target_files:
                return False
            return all(f in present_set for f in task.target_files)

        dropped_ids: list[str] = []
        survived_ids: list[str] = []
        filtered_tasks = []
        for t in tasks:
            if t.task_type == TaskType.SCAFFOLD and _task_files_all_present(t):
                dropped_ids.append(t.task_id)
            else:
                if t.task_type == TaskType.SCAFFOLD:
                    # Some files genuinely missing — retitle the surviving task
                    t = t.model_copy(update={"title": "Add language-idiomatic stubs (skeleton already present)"})
                    survived_ids.append(t.task_id)
                filtered_tasks.append(t)

        sc_verify = ScaffoldVerification(
            present_files=sc_verify.present_files,
            missing_files=sc_verify.missing_files,
            dropped_task_ids=dropped_ids,
            survived_task_ids=survived_ids,
        )
        run.save_json("quality/scaffold_verification.json", sc_verify.model_dump(mode="json"))

        # Replace task list with filtered version (M1 scaffold tasks already present are dropped)
        tasks = filtered_tasks

        # 10) test plan
        tp = self.test_designer.design(milestones=milestones, tasks=tasks, languages=languages)
        run.save_json("quality/test_plan.json", tp)

        # 11) implementation per milestone
        router = ExecutorRouter(self.config, allow_mock=inp.allow_mock)
        implementer = ImplementerAgent(router)
        any_milestone_failed = False
        for m in milestones:
            impl = implementer.run_milestone(
                milestone_id=m.milestone_id, tasks=tasks, run=run, mode=inp.mode, languages=languages,
                concurrency=self.config.concurrency, fail_fast=self.config.fail_fast,
            )
            run.state.implementation_results.append(impl)
            if not impl.success:
                any_milestone_failed = True
                if self.config.fail_fast and not self.config.continue_and_report:
                    break

        # 12) gates / reviews
        qg = self.quality.run(repo_path=inp.repo_path, languages=languages,
                              dry_run=inp.mode == PipelineMode.DRY_RUN)
        run.state.quality_gates = qg
        run.save_json("quality/quality_gate.json", qg)

        sec = self.security.review(repo_path=inp.repo_path, state=run.state)
        run.state.security_review = sec
        run.save_json("quality/security_review.json", sec)

        cr = self.code_reviewer.review(
            tasks=tasks,
            results=[r for impl in run.state.implementation_results for r in impl.task_results],
        )
        run.state.code_review = cr
        run.save_json("quality/code_review.json", cr)

        ir = self.integration_reviewer.review(
            api_contract=arch.api_contract, dependency_graph=arch.dependency_graph, languages=languages
        )
        run.state.integration_review = ir
        run.save_json("quality/integration_review.json", ir)

        # 13) verification
        v = self.verifier.verify(run.state)
        run.state.verification = v
        run.save_json("verification/verification_report.json", v)

        # 14) docs
        run.save_text("delivery/README.generated.md", self.doc_writer.readme(prd=prd, architecture=arch))
        run.save_text("delivery/usage.generated.md", self.doc_writer.usage(prd=prd))

        # 15) release
        rc = self.release_manager.check(run.state)
        run.state.release_check = rc
        run.save_json("verification/release_check.json", rc)

        delivery = self.release_manager.build_delivery(run.state, project_name=brief.product_name)
        run.state.delivery_report = delivery
        run.save_text("delivery/release_notes.md",
                      self.release_manager.render_release_notes(run.state, project_name=brief.product_name))
        run.save_text("delivery/delivery_report.md",
                      self.release_manager.delivery_reporter.render_markdown(delivery))

        # 16) commit artifacts (off by default)
        artifacts = self.commit_agent.build_artifacts(state=run.state, project_name=brief.product_name)
        run.save_text("delivery/PR_BODY.md", artifacts.pr_body)
        run.save_text("delivery/COMMIT_MSG.txt", artifacts.commit_message)

        # 17) crew assembly (visibility — CrewAI Agents/Tasks/Crew actually used)
        crew = make_crew(
            agents=[self.pm.agent, self.req.agent, self.prd_writer.agent, self.architect.agent,
                    self.mplanner.agent, self.decomposer.agent, self.scaffolder.agent,
                    self.quality.agent, self.security.agent, self.code_reviewer.agent,
                    self.integration_reviewer.agent, self.verifier.agent, self.doc_writer.agent,
                    self.release_manager.agent, self.commit_agent.agent],
            tasks=[],
        )
        run.save_json("execution/crew_assembly.json",
                      {"agents": [type(a).__name__ for a in (crew.agents if hasattr(crew, 'agents') else [])]})

        # 18) final report
        self.reporter.write_final_report(run)
        run.state.errors.append("not-all-milestones-complete") if any_milestone_failed else None
        run.finish()
        return run


def _render_delivery_plan(milestones, tasks) -> str:
    lines = ["# Delivery Plan", ""]
    for m in milestones:
        lines.append(f"## {m.milestone_id}: {m.title}")
        lines.append(f"- objective: {m.objective}")
        lines.append("- tasks:")
        for t in [t for t in tasks if t.milestone_id == m.milestone_id]:
            lines.append(f"  - **{t.task_id}** ({t.task_type.value}, risk={t.risk_level.value}, lang={t.language.value}): {t.title}")
        lines.append("")
    return "\n".join(lines) + "\n"
