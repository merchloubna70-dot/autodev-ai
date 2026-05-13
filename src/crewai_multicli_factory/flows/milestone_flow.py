"""Run a single milestone of an existing run (for `execute-milestone`)."""
from __future__ import annotations

from dataclasses import dataclass

from ..agents.implementer import ImplementerAgent
from ..config import FactoryConfig
from ..executors.executor_router import ExecutorRouter
from ..schemas import ExecutionBackend, ImplementationResult, Language, PipelineMode
from ..state import RunState


@dataclass
class MilestoneFlowInput:
    run_id: str
    milestone_id: str
    repo_path: str
    mode: PipelineMode = PipelineMode.DRY_RUN
    backend: ExecutionBackend = ExecutionBackend.AUTO
    allow_mock: bool = True
    concurrency: int = 3
    fail_fast: bool = True


class MilestoneFlow:
    def __init__(self, config: FactoryConfig | None = None):
        self.config = config or FactoryConfig()

    def run(self, inp: MilestoneFlowInput) -> ImplementationResult:
        run = RunState.load(inp.repo_path, inp.run_id)
        plan = run.state.milestone_plan
        if plan is None:
            raise RuntimeError("run has no milestone_plan; nothing to execute")
        languages: list[Language] = run.state.languages or [Language.PYTHON]
        router = ExecutorRouter(self.config, allow_mock=inp.allow_mock)
        impl = ImplementerAgent(router)
        # Override default backend selection per request
        result = impl.run_milestone(
            milestone_id=inp.milestone_id,
            tasks=plan.tasks,
            run=run,
            mode=inp.mode,
            languages=languages,
            concurrency=inp.concurrency,
            fail_fast=inp.fail_fast,
        )
        # update aggregate state
        run.state.implementation_results = [
            r for r in run.state.implementation_results if r.milestone_id != inp.milestone_id
        ] + [result]
        run.save()
        return result
