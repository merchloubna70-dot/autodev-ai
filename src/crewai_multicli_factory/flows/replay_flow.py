"""ReplayFlow — re-run pipeline stages from a given stage forward.

Supported stages (in order):
  classification, product, architecture, planning,
  implementation, quality, verification, release
"""
from __future__ import annotations

from datetime import datetime, timezone

from ..agents import (
    CodeReviewerAgent,
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
    SecurityReviewerAgent,
    SystemArchitectAgent,
    TaskDecomposerAgent,
    VerifierAgent,
)
from ..config import FactoryConfig
from ..executors.executor_router import ExecutorRouter
from ..schemas import (
    Language,
    MilestonePlan,
    PipelineMode,
)
from ..state import RunState

STAGES = [
    "classification",
    "product",
    "architecture",
    "planning",
    "implementation",
    "quality",
    "verification",
    "release",
]


class ReplayFlow:
    def __init__(self, config: FactoryConfig | None = None):
        self.config = config or FactoryConfig()

    def replay(self, run_id: str, repo_path: str, from_stage: str) -> RunState:
        if from_stage not in STAGES:
            raise ValueError(
                f"Unknown stage {from_stage!r}. Valid stages: {STAGES}"
            )

        run = RunState.load(repo_path, run_id)
        state = run.state

        # Determine languages from persisted state
        languages: list[Language] = list(state.languages) if state.languages else [Language.PYTHON]
        mode: PipelineMode = state.mode or PipelineMode.DRY_RUN

        start_idx = STAGES.index(from_stage)
        active_stages = STAGES[start_idx:]

        # --- classification ---
        if "classification" in active_stages:
            explorer = RepoExplorerAgent()
            classifier = InputClassifierAgent()
            scan = explorer.explore(repo_path)
            source_text = state.prd.overview if state.prd else ""
            cls = classifier.classify(
                text=source_text,
                source_path=None,
                is_empty_repo=scan.is_empty,
                has_existing_code=not scan.is_empty,
            )
            state.classification = cls
            run.save_json("input/classification.json", cls)

        # --- product ---
        if "product" in active_stages:
            pm = ProductManagerAgent()
            req = RequirementAnalystAgent()
            prd_writer = PRDWriterAgent()
            source_text = state.prd.overview if state.prd else ""
            brief = pm.build_brief(source_text)
            state.product_brief = brief
            run.save_json("product/product_brief.json", brief)
            functional, nf, ac = req.derive(brief=brief, source_text=source_text)
            prd = prd_writer.write(brief=brief, functional=functional, non_functional=nf, acceptance=ac)
            state.prd = prd
            run.save_text("product/prd.md", prd_writer.render_markdown(prd))
            run.save_json("product/prd.json", prd)

        # --- architecture ---
        if "architecture" in active_stages:
            explorer = RepoExplorerAgent()
            architect = SystemArchitectAgent()
            scan = explorer.explore(repo_path)
            state.repo_scan = scan
            prd = state.prd
            if prd is None:
                # Minimal fallback if no prd in state yet
                from ..schemas import PRD
                prd = PRD(product_name="unknown", overview="")
            arch = architect.design(prd=prd, scan=scan, languages=languages)
            state.architecture = arch
            run.save_text("architecture/architecture.md", architect.render_markdown(arch))
            run.save_json("architecture/architecture.json", arch)

        # --- planning ---
        if "planning" in active_stages:
            mplanner = MilestonePlannerAgent()
            decomposer = TaskDecomposerAgent()
            arch = state.architecture
            if arch is None:
                raise ValueError("Cannot replay 'planning' without architecture in state.")
            milestones = mplanner.plan(architecture=arch, languages=languages, max_milestones=6)
            tasks = decomposer.decompose(milestones=milestones, architecture=arch, languages=languages)
            plan = MilestonePlan(milestones=milestones, tasks=tasks)
            state.milestone_plan = plan
            run.save_json("planning/milestones.json", milestones)
            run.save_json("planning/tasks.json", tasks)

        # --- implementation ---
        if "implementation" in active_stages:
            plan = state.milestone_plan
            if plan is None:
                raise ValueError("Cannot replay 'implementation' without milestone_plan in state.")
            router = ExecutorRouter(self.config, allow_mock=True)
            implementer = ImplementerAgent(router)
            # Clear old results so we re-populate
            state.implementation_results = []
            for m in plan.milestones:
                impl = implementer.run_milestone(
                    milestone_id=m.milestone_id,
                    tasks=plan.tasks,
                    run=run,
                    mode=mode,
                    languages=languages,
                    concurrency=self.config.concurrency,
                    fail_fast=self.config.fail_fast,
                )
                state.implementation_results.append(impl)

        # --- quality ---
        if "quality" in active_stages:
            quality = QualityGateAgent()
            security = SecurityReviewerAgent()
            code_reviewer = CodeReviewerAgent()
            integration_reviewer = IntegrationReviewerAgent()
            arch = state.architecture

            qg = quality.run(repo_path=repo_path, languages=languages, dry_run=mode == PipelineMode.DRY_RUN)
            state.quality_gates = qg
            run.save_json("quality/quality_gate.json", qg)

            sec = security.review(repo_path=repo_path, state=state)
            state.security_review = sec
            run.save_json("quality/security_review.json", sec)

            all_task_results = [r for impl in state.implementation_results for r in impl.task_results]
            tasks = state.milestone_plan.tasks if state.milestone_plan else []
            cr = code_reviewer.review(tasks=tasks, results=all_task_results)
            state.code_review = cr
            run.save_json("quality/code_review.json", cr)

            if arch:
                ir = integration_reviewer.review(
                    api_contract=arch.api_contract,
                    dependency_graph=arch.dependency_graph,
                    languages=languages,
                )
                state.integration_review = ir
                run.save_json("quality/integration_review.json", ir)

        # --- verification ---
        if "verification" in active_stages:
            verifier = VerifierAgent()
            v = verifier.verify(state)
            state.verification = v
            run.save_json("verification/verification_report.json", v)

        # --- release ---
        if "release" in active_stages:
            release_manager = ReleaseManagerAgent()
            rc = release_manager.check(state)
            state.release_check = rc
            run.save_json("verification/release_check.json", rc)
            doc_writer = DocWriterAgent()
            prd = state.prd
            arch = state.architecture
            if prd and arch:
                run.save_text("delivery/README.generated.md", doc_writer.readme(prd=prd, architecture=arch))
                run.save_text("delivery/usage.generated.md", doc_writer.usage(prd=prd))

        # Append replay note into errors (no dedicated notes field)
        iso_ts = datetime.now(timezone.utc).isoformat()
        state.errors.append(f"replayed from stage {from_stage} at {iso_ts}")

        run.save()
        return run
