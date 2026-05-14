"""ReplayFlow — re-run pipeline stages from a given stage forward.

Supported stages (in order):
  classification, product, architecture, planning,
  implementation, quality, verification, release

Additionally, ``resume_from_milestone`` provides the public API for the
``deliver-project --resume-from`` flag.  Accepted milestone / stage tags:

  input, product, architecture, planning, execution,
  quality, verification, delivery

These map onto the canonical artifact sub-directories of a run.
"""
from __future__ import annotations

import hashlib
import shutil
from datetime import datetime, timezone
from pathlib import Path

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

# ---------------------------------------------------------------------------
# Milestone / stage tag definitions for --resume-from
# ---------------------------------------------------------------------------

# Valid milestone tags accepted by ``--resume-from``.  These correspond to the
# canonical artifact sub-directories written by ProjectDeliveryFlow.
MILESTONE_TAGS = [
    "input",
    "product",
    "architecture",
    "planning",
    "execution",
    "quality",
    "verification",
    "delivery",
]

# Mapping: milestone-tag  →  equivalent coarse STAGE name used by ReplayFlow.
# "input"     corresponds to the classification stage.
# "execution" corresponds to the implementation stage.
# "delivery"  corresponds to the release stage.
_MILESTONE_TO_STAGE: dict[str, str] = {
    "input": "classification",
    "product": "product",
    "architecture": "architecture",
    "planning": "planning",
    "execution": "implementation",
    "quality": "quality",
    "verification": "verification",
    "delivery": "release",
}

# Artifact subdirectories that belong *after* each milestone tag (in order).
# Used to prune artifacts that are downstream of the resume point.
_MILESTONE_ORDER = MILESTONE_TAGS  # already ordered earliest → latest

# Subdirectories whose contents are snapshotted before a coarse-grained replay.
# We snapshot all canonical stage dirs so any overwritten artifact is preserved.
_SNAPSHOT_SUBDIRS = [
    "input",
    "product",
    "architecture",
    "planning",
    "implementation",
    "execution",
    "quality",
    "verification",
    "delivery",
]


def _snapshot_run(run_root: Path, stage: str) -> str:
    """Snapshot current run artifacts to a replay sub-directory.

    Returns the ``replay_id`` string (used in the progress echo).
    """
    iso_ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    # Short deterministic hash from timestamp + stage to ensure uniqueness
    short_hash = hashlib.sha1(f"{iso_ts}-{stage}".encode()).hexdigest()[:8]
    replay_id = f"replay_{iso_ts}_{short_hash}"
    snapshot_dir = run_root / "replays" / replay_id
    snapshot_dir.mkdir(parents=True, exist_ok=True)

    # Snapshot run_state.json
    state_file = run_root / "run_state.json"
    if state_file.exists():
        shutil.copy2(state_file, snapshot_dir / "run_state.json")

    # Snapshot each stage subdir that exists
    for sub in _SNAPSHOT_SUBDIRS:
        src = run_root / sub
        if src.exists():
            shutil.copytree(src, snapshot_dir / sub, dirs_exist_ok=True)

    return replay_id


class ReplayFlow:
    def __init__(self, config: FactoryConfig | None = None):
        self.config = config or FactoryConfig()

    def replay(
        self,
        run_id: str,
        repo_path: str,
        from_stage: str = "planning",
        *,
        from_step: str | None = None,
    ) -> RunState:
        # ------------------------------------------------------------------
        # Fine-grained step resume via StepRunner
        # ------------------------------------------------------------------
        if from_step is not None:
            from .project_delivery_flow import ProjectDeliveryInput
            from .step_definitions.project_delivery_steps import PROJECT_DELIVERY_REGISTRY

            run = RunState.load(repo_path, run_id)
            state = run.state

            languages: list[Language] = list(state.languages) if state.languages else [Language.PYTHON]
            mode: PipelineMode = state.mode or PipelineMode.DRY_RUN

            source_text = state.prd.overview if state.prd else ""
            ctx: dict = {
                "inp": ProjectDeliveryInput(
                    repo_path=repo_path,
                    prd_text=source_text,
                    languages=languages,
                    mode=mode,
                    allow_mock=True,
                ),
                "run": run,
                "config": self.config,
                "languages": languages,
                "source_text": source_text,
                "scan_first": state.repo_scan,
                "brief": state.product_brief,
                "prd": state.prd,
                "arch": state.architecture,
                "milestones": state.milestone_plan.milestones if state.milestone_plan else None,
                "resolved_scale": None,
                "tasks": state.milestone_plan.tasks if state.milestone_plan else None,
                "functional": None,
                "nf": None,
                "ac": None,
                "any_milestone_failed": False,
            }

            from .project_delivery_microfile import _CtxStepRunner  # noqa: PLC0415
            runner = _CtxStepRunner()
            runner.run(
                registry=PROJECT_DELIVERY_REGISTRY,
                run_state=ctx,
                from_step=from_step,
            )

            iso_ts = datetime.now(timezone.utc).isoformat()
            run.state.errors.append(f"replayed from step {from_step} at {iso_ts}")
            run.save()
            return run

        # ------------------------------------------------------------------
        # Coarse-grained stage resume (existing behaviour)
        # ------------------------------------------------------------------
        if from_stage not in STAGES:
            raise ValueError(
                f"Unknown stage {from_stage!r}. Valid stages: {STAGES}"
            )

        run = RunState.load(repo_path, run_id)

        # Snapshot current artifacts BEFORE overwriting anything so the
        # original state is preserved even if replay is non-deterministic.
        replay_id = _snapshot_run(run.root, from_stage)
        print(  # noqa: T201
            f"replay run_id={run_id} stage={from_stage} "
            f"snapshot=.dev-factory/runs/{run_id}/replays/{replay_id}/"
        )

        state = run.state

        # Determine languages from persisted state
        languages: list[Language] = list(state.languages) if state.languages else [Language.PYTHON]  # type: ignore[no-redef]
        mode: PipelineMode = state.mode or PipelineMode.DRY_RUN  # type: ignore[no-redef]

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
            prd = state.prd  # type: ignore[assignment]
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
            arch = state.architecture  # type: ignore[assignment]
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
            plan = state.milestone_plan  # type: ignore[assignment]
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
            arch = state.architecture  # type: ignore[assignment]

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
            prd = state.prd  # type: ignore[assignment]
            arch = state.architecture  # type: ignore[assignment]
            if prd and arch:
                run.save_text("delivery/README.generated.md", doc_writer.readme(prd=prd, architecture=arch))
                run.save_text("delivery/usage.generated.md", doc_writer.usage(prd=prd))

        # Append replay note into errors (no dedicated notes field)
        iso_ts = datetime.now(timezone.utc).isoformat()
        state.errors.append(f"replayed from stage {from_stage} at {iso_ts}")

        run.save()
        return run


# ---------------------------------------------------------------------------
# Public helper: resume_from_milestone
# ---------------------------------------------------------------------------


def _clear_artifacts_after(run_root: Path, from_milestone: str) -> list[str]:
    """Delete artifact subdirectories that come *after* ``from_milestone``.

    Returns a list of directory paths that were removed (for logging).
    """
    from_idx = _MILESTONE_ORDER.index(from_milestone)
    later_tags = _MILESTONE_ORDER[from_idx + 1:]
    removed: list[str] = []
    for tag in later_tags:
        target = run_root / tag
        if target.exists():
            shutil.rmtree(target)
            removed.append(str(target))
    return removed


def resume_from_milestone(
    run_id: str,
    repo_path: str,
    milestone: str,
    config: FactoryConfig | None = None,
) -> RunState:
    """Resume a pipeline run from a specific milestone / stage tag.

    Parameters
    ----------
    run_id:
        The run to resume.
    repo_path:
        Root of the repository (same value as used when the run was created).
    milestone:
        One of the valid milestone tags: ``input``, ``product``,
        ``architecture``, ``planning``, ``execution``, ``quality``,
        ``verification``, ``delivery``.  The run must have an artifact
        directory for this tag (i.e. it must exist on disk).
    config:
        Optional :class:`~autodev.config.FactoryConfig`.  Defaults to a
        fresh instance when not provided.

    Returns
    -------
    RunState
        The updated :class:`~autodev.state.RunState` after the resumed replay.

    Raises
    ------
    ValueError
        When ``milestone`` is not a recognised tag or the corresponding
        artifact directory does not exist in the run tree.
    """
    if milestone not in MILESTONE_TAGS:
        raise ValueError(
            f"Unknown milestone tag {milestone!r}. "
            f"Valid tags: {MILESTONE_TAGS}"
        )

    run = RunState.load(repo_path, run_id)

    # Validate that the milestone's artifact directory exists on disk.
    artifact_dir = run.root / milestone
    if not artifact_dir.exists():
        raise ValueError(
            f"Milestone artifact directory not found for tag {milestone!r}: "
            f"{artifact_dir}. "
            f"The run may not have reached this stage yet."
        )

    # Clear downstream artifacts so the replay starts fresh from this point.
    removed = _clear_artifacts_after(run.root, milestone)
    if removed:
        print(  # noqa: T201
            f"[resume-from] cleared {len(removed)} downstream artifact dir(s): "
            + ", ".join(removed)
        )

    # Map the milestone tag to the equivalent replay stage.
    from_stage = _MILESTONE_TO_STAGE[milestone]

    # Delegate to the existing ReplayFlow.
    flow = ReplayFlow(config=config)
    return flow.replay(run_id=run_id, repo_path=repo_path, from_stage=from_stage)
