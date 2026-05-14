"""Named step definitions for ProjectDeliveryMicroFlow.

Each step is a thin wrapper that delegates to existing agent logic already
present in ProjectDeliveryFlow.  No agent logic is re-implemented here.

The ``PROJECT_DELIVERY_REGISTRY`` at module level is ready for use by
ProjectDeliveryMicroFlow and ReplayFlow.
"""
from __future__ import annotations

import sys
from typing import Any

from ..step_runner import Step, StepRegistry

# ---------------------------------------------------------------------------
# Build shared registry
# ---------------------------------------------------------------------------

PROJECT_DELIVERY_REGISTRY: StepRegistry = StepRegistry(name="project_delivery")

# ---------------------------------------------------------------------------
# Step functions — each receives the ``_MicroRunContext`` (duck-typed dict-like
# object built by ProjectDeliveryMicroFlow) and mutates it.
# ---------------------------------------------------------------------------


def _classify_input(ctx: Any) -> str:
    from ...agents import InputClassifierAgent, RepoExplorerAgent

    inp = ctx["inp"]
    run = ctx["run"]
    if ctx.get("scan_first") is None:
        explorer = RepoExplorerAgent()
        ctx["scan_first"] = explorer.explore(inp.repo_path)
    scan = ctx["scan_first"]
    source_text = inp.prd_text or inp.brief_text or ""
    ctx["source_text"] = source_text
    classifier = InputClassifierAgent()
    cls = classifier.classify(
        text=source_text,
        source_path=None,
        is_empty_repo=scan.is_empty,
        has_existing_code=not scan.is_empty,
    )
    run.state.classification = cls
    run.save_json("input/classification.json", cls)
    return f"type={cls.input_type}"


def _product_manager_brief(ctx: Any) -> str:
    from ...agents import ProductManagerAgent

    inp = ctx["inp"]
    run = ctx["run"]
    source_text = ctx.get("source_text") or inp.prd_text or inp.brief_text or ""
    pm = ProductManagerAgent()
    brief = pm.build_brief(source_text, product_name=inp.project_name)
    run.state.product_brief = brief
    ctx["brief"] = brief
    run.save_json("product/product_brief.json", brief)
    return f"product={brief.product_name}"


def _requirement_analysis(ctx: Any) -> str:
    from ...agents import RequirementAnalystAgent

    ctx["run"]
    brief = ctx["brief"]
    source_text = ctx.get("source_text", "")
    req = RequirementAnalystAgent()
    functional, nf, ac = req.derive(brief=brief, source_text=source_text)
    ctx["functional"] = functional
    ctx["nf"] = nf
    ctx["ac"] = ac
    return f"functional={len(functional)}"


def _prd_write(ctx: Any) -> str:
    from ...agents import PRDWriterAgent

    run = ctx["run"]
    brief = ctx["brief"]
    prd_writer = PRDWriterAgent()
    prd = prd_writer.write(
        brief=brief,
        functional=ctx["functional"],
        non_functional=ctx["nf"],
        acceptance=ctx["ac"],
    )
    run.state.prd = prd
    run.save_text("product/prd.md", prd_writer.render_markdown(prd))
    run.save_json("product/prd.json", prd)
    ctx["prd"] = prd
    return f"prd={prd.product_name}"


def _repo_scan(ctx: Any) -> str:
    from ...agents import RepoExplorerAgent

    inp = ctx["inp"]
    run = ctx["run"]
    scan = ctx.get("scan_first") or RepoExplorerAgent().explore(inp.repo_path)
    ctx["scan_first"] = scan
    run.state.repo_scan = scan
    run.save_json("input/repo_scan.json", scan)
    return f"files={len(scan.files) if hasattr(scan, 'files') else '?'}"


def _architecture_design(ctx: Any) -> str:
    from ...agents import SystemArchitectAgent

    run = ctx["run"]
    prd = ctx["prd"]
    scan = ctx["scan_first"]
    ctx["inp"]
    languages = ctx["languages"]
    architect = SystemArchitectAgent()
    arch = architect.design(prd=prd, scan=scan, languages=languages)
    run.state.architecture = arch
    run.save_text("architecture/architecture.md", architect.render_markdown(arch))
    run.save_json("architecture/architecture.json", arch)
    run.save_json("architecture/module_map.json", [m.model_dump(mode="json") for m in arch.modules])
    run.save_json("architecture/api_contract.json", arch.api_contract)
    run.save_json("architecture/data_model.json", arch.data_model)
    run.save_json("architecture/dependency_graph.json", arch.dependency_graph)
    ctx["arch"] = arch
    return f"modules={len(arch.modules)}"


def _milestone_plan(ctx: Any) -> str:
    from ...agents import MilestonePlannerAgent, RequirementAnalystAgent

    run = ctx["run"]
    arch = ctx["arch"]
    prd = ctx["prd"]
    brief = ctx["brief"]
    inp = ctx["inp"]
    languages = ctx["languages"]
    resolved_scale = inp.scale
    if resolved_scale is None:
        req = RequirementAnalystAgent()
        scale_report = req.infer_scale(
            prd=prd,
            brief=brief,
            languages=languages,
            from_scratch=inp.from_scratch,
        )
        resolved_scale = scale_report.scale
        print(
            f"[autodev] inferred scale={resolved_scale.value} ({'; '.join(scale_report.reasoning)})",
            file=sys.stderr,
        )
    ctx["resolved_scale"] = resolved_scale
    mplanner = MilestonePlannerAgent()
    milestones = mplanner.plan(
        architecture=arch, languages=languages, max_milestones=6, scale=resolved_scale
    )
    ctx["milestones"] = milestones
    run.save_json("planning/milestones.json", milestones)
    return f"milestones={len(milestones)}"


def _task_decompose(ctx: Any) -> str:
    from ...agents import TaskDecomposerAgent
    from ...schemas import MilestonePlan

    run = ctx["run"]
    arch = ctx["arch"]
    prd = ctx["prd"]
    brief = ctx["brief"]
    languages = ctx["languages"]
    milestones = ctx["milestones"]
    resolved_scale = ctx["resolved_scale"]
    decomposer = TaskDecomposerAgent()
    tasks = decomposer.decompose(
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
    ctx["tasks"] = tasks
    run.save_json("planning/tasks.json", tasks)
    return f"tasks={len(tasks)}"


def _scaffolder_apply(ctx: Any) -> str:
    from ...agents import ScaffolderAgent
    from ...agents._scaffold_verification import ScaffoldVerification
    from ...schemas import TaskType

    run = ctx["run"]
    inp = ctx["inp"]
    languages = ctx["languages"]
    brief = ctx["brief"]
    tasks = ctx["tasks"]
    scaffolder = ScaffolderAgent()
    sc_plan = scaffolder.plan(project_name=brief.product_name, languages=languages)
    run.state.scaffold_plan = sc_plan
    run.save_json("planning/scaffold_plan.json", sc_plan)
    scaffolder.apply(plan=sc_plan, repo_path=inp.repo_path, mode=inp.mode)

    sc_verify = scaffolder.verify(repo_path=inp.repo_path, plan=sc_plan)
    present_set = set(sc_verify.present_files)

    def _task_files_all_present(task) -> bool:
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
                t = t.model_copy(
                    update={"title": "Add language-idiomatic stubs (skeleton already present)"}
                )
                survived_ids.append(t.task_id)
            filtered_tasks.append(t)

    sc_verify = ScaffoldVerification(
        present_files=sc_verify.present_files,
        missing_files=sc_verify.missing_files,
        dropped_task_ids=dropped_ids,
        survived_task_ids=survived_ids,
    )
    run.save_json("quality/scaffold_verification.json", sc_verify.model_dump(mode="json"))
    ctx["tasks"] = filtered_tasks
    # Update plan in state with filtered tasks
    from ...schemas import MilestonePlan
    run.state.milestone_plan = MilestonePlan(milestones=ctx["milestones"], tasks=filtered_tasks)
    return f"scaffold_files={len(sc_verify.present_files)},dropped={len(dropped_ids)}"


def _test_design(ctx: Any) -> str:
    from ...agents import TestDesignerAgent

    run = ctx["run"]
    languages = ctx["languages"]
    milestones = ctx["milestones"]
    tasks = ctx["tasks"]
    tp = TestDesignerAgent().design(milestones=milestones, tasks=tasks, languages=languages)
    run.save_json("quality/test_plan.json", tp)
    return "test_plan=ok"


def _implementation_loop(ctx: Any) -> str:
    from ...agents import ImplementerAgent
    from ...executors.executor_router import ExecutorRouter

    run = ctx["run"]
    inp = ctx["inp"]
    languages = ctx["languages"]
    milestones = ctx["milestones"]
    tasks = ctx["tasks"]
    config = ctx["config"]
    router = ExecutorRouter(config, allow_mock=inp.allow_mock)
    implementer = ImplementerAgent(router)
    any_failed = False
    for m in milestones:
        impl = implementer.run_milestone(
            milestone_id=m.milestone_id,
            tasks=tasks,
            run=run,
            mode=inp.mode,
            languages=languages,
            concurrency=config.concurrency,
            fail_fast=config.fail_fast,
        )
        run.state.implementation_results.append(impl)
        if not impl.success:
            any_failed = True
            if config.fail_fast and not config.continue_and_report:
                break
    ctx["any_milestone_failed"] = any_failed
    return f"failed={any_failed}"


def _quality_gate(ctx: Any) -> str:
    from ...agents import QualityGateAgent
    from ...schemas import PipelineMode

    run = ctx["run"]
    inp = ctx["inp"]
    languages = ctx["languages"]
    qg = QualityGateAgent().run(
        repo_path=inp.repo_path,
        languages=languages,
        dry_run=inp.mode == PipelineMode.DRY_RUN,
    )
    run.state.quality_gates = qg
    run.save_json("quality/quality_gate.json", qg)
    return "quality_gate=ok"


def _security_review(ctx: Any) -> str:
    from ...agents import SecurityReviewerAgent

    run = ctx["run"]
    inp = ctx["inp"]
    sec = SecurityReviewerAgent().review(repo_path=inp.repo_path, state=run.state)
    run.state.security_review = sec
    run.save_json("quality/security_review.json", sec)
    return "security=ok"


def _code_review(ctx: Any) -> str:
    from ...agents import CodeReviewerAgent

    run = ctx["run"]
    tasks = ctx["tasks"]
    results = [r for impl in run.state.implementation_results for r in impl.task_results]
    cr = CodeReviewerAgent().review(tasks=tasks, results=results)
    run.state.code_review = cr
    run.save_json("quality/code_review.json", cr)
    return "code_review=ok"


def _integration_review(ctx: Any) -> str:
    from ...agents import IntegrationReviewerAgent

    run = ctx["run"]
    arch = ctx["arch"]
    languages = ctx["languages"]
    ir = IntegrationReviewerAgent().review(
        api_contract=arch.api_contract,
        dependency_graph=arch.dependency_graph,
        languages=languages,
    )
    run.state.integration_review = ir
    run.save_json("quality/integration_review.json", ir)
    return "integration=ok"


def _verification(ctx: Any) -> str:
    from ...agents import VerifierAgent

    run = ctx["run"]
    v = VerifierAgent().verify(run.state)
    run.state.verification = v
    run.save_json("verification/verification_report.json", v)
    return "verified=ok"


def _doc_write(ctx: Any) -> str:
    from ...agents import DocWriterAgent

    run = ctx["run"]
    prd = ctx["prd"]
    arch = ctx["arch"]
    dw = DocWriterAgent()
    run.save_text("delivery/README.generated.md", dw.readme(prd=prd, architecture=arch))
    run.save_text("delivery/usage.generated.md", dw.usage(prd=prd))
    return "docs=ok"


def _release_check(ctx: Any) -> str:
    from ...agents import ReleaseManagerAgent

    run = ctx["run"]
    brief = ctx["brief"]
    rm = ReleaseManagerAgent()
    rc = rm.check(run.state)
    run.state.release_check = rc
    run.save_json("verification/release_check.json", rc)
    delivery = rm.build_delivery(run.state, project_name=brief.product_name)
    run.state.delivery_report = delivery
    run.save_text(
        "delivery/release_notes.md",
        rm.render_release_notes(run.state, project_name=brief.product_name),
    )
    run.save_text(
        "delivery/delivery_report.md",
        rm.delivery_reporter.render_markdown(delivery),
    )
    ctx["rm"] = rm
    return "release_check=ok"


def _commit_artifacts(ctx: Any) -> str:
    from ...agents import CommitAgent

    run = ctx["run"]
    brief = ctx["brief"]
    artifacts = CommitAgent().build_artifacts(state=run.state, project_name=brief.product_name)
    run.save_text("delivery/PR_BODY.md", artifacts.pr_body)
    run.save_text("delivery/COMMIT_MSG.txt", artifacts.commit_message)
    return "artifacts=ok"


def _final_report(ctx: Any) -> str:
    from ...agents._crewai_bridge import make_crew
    from ...reports.reporter import Reporter

    run = ctx["run"]
    ctx_ref = ctx  # local alias
    # crew assembly for visibility
    try:
        [
            ctx_ref.get("pm_agent"),
            ctx_ref.get("req_agent"),
        ]
        crew = make_crew(agents=[], tasks=[])
        run.save_json(
            "execution/crew_assembly.json",
            {"agents": [type(a).__name__ for a in (crew.agents if hasattr(crew, "agents") else [])]},
        )
    except Exception:
        run.save_json("execution/crew_assembly.json", {"agents": []})
    Reporter().write_final_report(run)
    if ctx.get("any_milestone_failed"):
        run.state.errors.append("not-all-milestones-complete")
    run.finish()
    return "final_report=ok"


# ---------------------------------------------------------------------------
# Register all steps
# ---------------------------------------------------------------------------

_STEP_DEFS: list[dict] = [
    dict(name="classify_input",       description="Classify input type and explore repo",               func=_classify_input,       inputs=["inp"], outputs=["classification"]),
    dict(name="product_manager_brief",description="Build product manager brief",                        func=_product_manager_brief,inputs=["source_text"], outputs=["brief"],         depends_on=["classify_input"]),
    dict(name="requirement_analysis", description="Derive functional/non-functional requirements",      func=_requirement_analysis, inputs=["brief"], outputs=["functional","nf","ac"],depends_on=["product_manager_brief"]),
    dict(name="prd_write",            description="Write the PRD from requirements",                    func=_prd_write,            inputs=["brief","functional"], outputs=["prd"],    depends_on=["requirement_analysis"]),
    dict(name="repo_scan",            description="Record repo scan result",                            func=_repo_scan,            inputs=["inp"], outputs=["repo_scan"],             depends_on=["classify_input"]),
    dict(name="architecture_design",  description="Design system architecture",                         func=_architecture_design,  inputs=["prd","scan"], outputs=["arch"],           depends_on=["prd_write","repo_scan"]),
    dict(name="milestone_plan",       description="Plan delivery milestones",                           func=_milestone_plan,       inputs=["arch"], outputs=["milestones"],           depends_on=["architecture_design"]),
    dict(name="task_decompose",       description="Decompose milestones into tasks",                    func=_task_decompose,       inputs=["milestones"], outputs=["tasks"],          depends_on=["milestone_plan"]),
    dict(name="scaffolder_apply",     description="Apply scaffold and filter redundant tasks",          func=_scaffolder_apply,     inputs=["tasks"], outputs=["filtered_tasks"],      depends_on=["task_decompose"]),
    dict(name="test_design",          description="Design test plan",                                   func=_test_design,          inputs=["milestones","tasks"], outputs=["tp"],     depends_on=["scaffolder_apply"]),
    dict(name="implementation_loop",  description="Run implementation per milestone",                   func=_implementation_loop,  inputs=["tasks"], outputs=["impl_results"],        depends_on=["test_design"]),
    dict(name="quality_gate",         description="Run quality gates",                                  func=_quality_gate,         inputs=[], outputs=["qg"],                         depends_on=["implementation_loop"]),
    dict(name="security_review",      description="Run security review",                                func=_security_review,      inputs=[], outputs=["sec"],                        depends_on=["implementation_loop"]),
    dict(name="code_review",          description="Review generated code",                              func=_code_review,          inputs=["tasks"], outputs=["cr"],                  depends_on=["implementation_loop"]),
    dict(name="integration_review",   description="Integration contract review",                        func=_integration_review,   inputs=["arch"], outputs=["ir"],                   depends_on=["implementation_loop"]),
    dict(name="verification",         description="Verify full run state",                              func=_verification,         inputs=[], outputs=["v"],                          depends_on=["quality_gate","security_review","code_review","integration_review"]),
    dict(name="doc_write",            description="Generate README and usage docs",                     func=_doc_write,            inputs=["prd","arch"], outputs=["docs"],           depends_on=["verification"]),
    dict(name="release_check",        description="Release readiness check + notes",                    func=_release_check,        inputs=[], outputs=["rc"],                         depends_on=["doc_write"]),
    dict(name="commit_artifacts",     description="Build PR body and commit message artifacts",         func=_commit_artifacts,     inputs=[], outputs=["artifacts"],                  depends_on=["release_check"]),
    dict(name="final_report",         description="Write final delivery report and finish run",         func=_final_report,         inputs=[], outputs=["report"],                     depends_on=["commit_artifacts"]),
]

for _d in _STEP_DEFS:
    PROJECT_DELIVERY_REGISTRY.register(
        Step(
            name=_d["name"],
            description=_d["description"],
            func=_d["func"],
            inputs=_d.get("inputs", []),
            outputs=_d.get("outputs", []),
            depends_on=_d.get("depends_on", []),
        )
    )
