"""BugFixFlow — 4-stage serial bug fix pipeline.

Builds a one-off Milestone ``MBUG-1`` with 4 tasks (reproduce → locate →
patch → verify), then executes them **serially** (no parallelism; each stage
depends on the previous) through ``ImplementerAgent`` → ``ExecutorRouter``.

Hard rules
----------
- This module MUST NOT import CodexCliExecutor or ClaudeCodeExecutor directly.
  All CLI traffic goes through ExecutorRouter via ImplementerAgent.
- 4 stages are always serial; concurrency=1 is enforced.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from ..agents.implementer import ImplementerAgent
from ..config import FactoryConfig
from ..executors.executor_router import ExecutorRouter
from ..planners.four_stage_planner import FourStagePlanner, _MILESTONE_ID
from ..schemas import (
    ExecutionBackend,
    Language,
    Milestone,
    MilestonePlan,
    PipelineMode,
    RiskLevel,
)
from ..state import RunState


@dataclass
class BugFixInput:
    """Input for a single bug-fix run."""

    bug_description: str
    repo_path: str
    languages: list[Language] = field(default_factory=lambda: [Language.PYTHON])
    mode: PipelineMode = PipelineMode.DRY_RUN
    backend: ExecutionBackend = ExecutionBackend.AUTO
    allow_mock: bool = True


class BugFixFlow:
    """Orchestrates the 4-stage bug fix pipeline serially."""

    def __init__(self, config: FactoryConfig | None = None):
        self.config = config or FactoryConfig()

    def run(self, inp: BugFixInput) -> RunState:
        """Execute the 4-stage bug-fix plan and return the completed RunState."""
        # 1. Set up run state on disk
        run = RunState(repo_path=inp.repo_path)
        run.state.mode = inp.mode
        run.state.flow = "bug_fix_flow"
        run.state.languages = inp.languages
        run.save()

        # 2. Build the plan
        primary_language = inp.languages[0] if inp.languages else Language.PYTHON
        planner = FourStagePlanner()
        tasks = planner.plan(
            bug_description=inp.bug_description,
            repo_path=inp.repo_path,
            language=primary_language,
        )

        # 3. Build a one-off Milestone
        milestone = Milestone(
            milestone_id=_MILESTONE_ID,
            title="4-stage bug fix",
            objective=inp.bug_description[:200],
            task_ids=[t.task_id for t in tasks],
            estimated_risk=RiskLevel.MEDIUM,
            allowed_languages=inp.languages,
        )

        plan = MilestonePlan(milestones=[milestone], tasks=tasks)
        run.state.milestone_plan = plan

        # Persist planning artefact
        tasks_data = [t.model_dump(mode="json") for t in tasks]
        run.save_json("planning/tasks.json", tasks_data)
        run.save()

        # 4. Execute serially (concurrency=1, fail_fast=True)
        router = ExecutorRouter(self.config, allow_mock=inp.allow_mock)
        implementer = ImplementerAgent(router)

        impl = implementer.run_milestone(
            milestone_id=_MILESTONE_ID,
            tasks=tasks,
            run=run,
            mode=inp.mode,
            languages=inp.languages,
            concurrency=1,       # serial — each stage depends on the prior
            fail_fast=True,
        )

        run.state.implementation_results = [impl]
        run.finish()
        return run
