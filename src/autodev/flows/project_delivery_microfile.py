"""ProjectDeliveryMicroFlow — BMAD micro-file architecture pilot.

Behaves equivalently to ProjectDeliveryFlow but orchestrates via StepRunner +
StepRegistry.  The original ProjectDeliveryFlow is left untouched for backward
compatibility.
"""
from __future__ import annotations

from pathlib import Path

from ..config import FactoryConfig
from ..schemas import Language, PipelineMode
from ..state import RunState, init_run
from .project_delivery_flow import ProjectDeliveryInput
from .step_definitions.project_delivery_steps import PROJECT_DELIVERY_REGISTRY
from .step_runner import StepRunner


class _CtxStepRunner(StepRunner):
    """StepRunner subclass that resolves the steps persistence dir from ctx['run'].

    ctx['run'] is a real RunState object which exposes `.root` (the run directory
    Path).  Falls back to base_dir + run_id attrs for test fakes.
    """

    @staticmethod
    def _steps_dir(ctx) -> Path:  # type: ignore[override]
        run = ctx.get("run")
        if run is None:
            return Path(".dev-factory/runs/unknown/steps")
        # Real RunState: use `.root` directly
        root = getattr(run, "root", None)
        if root is not None:
            return Path(root) / "steps"
        # Test fakes: base_dir + run_id
        base = getattr(run, "base_dir", ".dev-factory")
        run_id = getattr(run, "run_id", "unknown")
        return Path(str(base)) / "runs" / str(run_id) / "steps"


class ProjectDeliveryMicroFlow:
    """BMAD micro-file alternative to ProjectDeliveryFlow.

    Uses StepRunner internally so each phase is named, trackable, and
    individually resumable via ReplayFlow --from-step.
    """

    def __init__(self, config: FactoryConfig | None = None) -> None:
        self.config = config or FactoryConfig()
        self._runner = _CtxStepRunner()

    def run(
        self,
        inp: ProjectDeliveryInput,
        *,
        from_step: str | None = None,
        until_step: str | None = None,
        force_restart: bool = False,
    ) -> RunState:
        languages = inp.languages or [Language.PYTHON]
        Path(inp.repo_path).mkdir(parents=True, exist_ok=True)

        run = init_run(
            repo_path=inp.repo_path,
            mode=inp.mode,
            flow="project_delivery_microfile",
            languages=[l.value for l in languages],
        )
        source_text = inp.prd_text or inp.brief_text or ""
        run.save_text("input/raw_input.md", source_text)

        # Shared mutable context dict passed to every step function.
        # StepRunner passes run_state as first arg; we supply ctx as run_state
        # so all step funcs receive the full shared context.
        ctx: dict = {
            "inp": inp,
            "run": run,
            "config": self.config,
            "languages": languages,
            "source_text": source_text,
            # Step functions populate these as they run:
            "scan_first": None,
            "brief": None,
            "prd": None,
            "arch": None,
            "milestones": None,
            "resolved_scale": None,
            "tasks": None,
            "functional": None,
            "nf": None,
            "ac": None,
            "any_milestone_failed": False,
        }

        self._runner.run(
            registry=PROJECT_DELIVERY_REGISTRY,
            run_state=ctx,
            from_step=from_step,
            until_step=until_step,
            force_restart=force_restart,
        )

        return run
