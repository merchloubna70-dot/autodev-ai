"""ProjectDeliveryCrewFlow — alternative implementation of project delivery using crewai.Flow.

Uses @start / @listen / @router decorators when crewai.flow is available.
Falls back to a stub with the same public API that raises RuntimeError on .run(...)
when crewai is not installed.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..schemas import ExecutionBackend, Language, PipelineMode

# ---------------------------------------------------------------------------
# Input dataclass
# ---------------------------------------------------------------------------


@dataclass
class ProjectDeliveryCrewFlowInput:
    repo_path: str
    brief_text: str | None = None
    prd_path: str | None = None
    languages: list[Language] | None = None
    mode: PipelineMode = PipelineMode.DRY_RUN
    backend: ExecutionBackend = ExecutionBackend.AUTO
    allow_mock: bool = True
    commit: bool = False
    push: bool = False
    tag: bool = False


# ---------------------------------------------------------------------------
# Try to import crewai.flow — optional dependency
# ---------------------------------------------------------------------------

try:
    from crewai.flow.flow import Flow, listen, router, start  # type: ignore[import]

    _CREWAI_AVAILABLE = True
except Exception:
    _CREWAI_AVAILABLE = False
    Flow = object  # type: ignore[misc,assignment]

    def start(fn=None):  # type: ignore[misc]
        """Stub for @start and @start()."""
        if fn is None:
            # Called as @start() — return decorator
            def decorator(f):
                return f
            return decorator
        # Called as @start — return fn directly
        return fn

    def listen(*args, **kwargs):  # type: ignore[misc]
        """Stub for @listen(node) — always returns pass-through decorator."""
        def decorator(fn):
            return fn
        return decorator

    def router(*args, **kwargs):  # type: ignore[misc]
        """Stub for @router(node) — always returns pass-through decorator."""
        def decorator(fn):
            return fn
        return decorator


# ---------------------------------------------------------------------------
# CrewFlow implementation
# ---------------------------------------------------------------------------


class ProjectDeliveryCrewFlow(Flow):  # type: ignore[misc]
    """CrewAI Flow variant of ProjectDeliveryFlow.

    When crewai is unavailable, constructing this class succeeds but calling
    .run(...) raises RuntimeError("crewai not installed").
    """

    def __init__(self) -> None:
        if _CREWAI_AVAILABLE:
            try:
                super().__init__()
            except Exception:
                pass
        self._state: dict[str, Any] = {}
        self._inp: ProjectDeliveryCrewFlowInput | None = None

    # ------------------------------------------------------------------
    # Flow nodes
    # ------------------------------------------------------------------

    @start()  # type: ignore[misc]
    def classify_input(self) -> dict[str, Any]:
        """Node 1 — classify the brief / PRD text."""
        from ..agents.input_classifier import InputClassifierAgent

        inp = self._inp
        assert inp is not None
        text = inp.brief_text or ""
        classifier = InputClassifierAgent()
        cls = classifier.classify(text=text, source_path=inp.prd_path)
        self._state["classification"] = cls
        return {"classification": cls.model_dump()}

    @listen(classify_input)  # type: ignore[misc]
    def write_prd(self, classify_result: dict[str, Any]) -> dict[str, Any]:
        """Node 2 — produce/parse PRD from brief."""
        from ..agents.prd_writer import PRDWriterAgent

        inp = self._inp
        assert inp is not None
        writer = PRDWriterAgent()
        prd = writer.write(inp.brief_text or "", path=inp.prd_path)  # type: ignore[call-arg, arg-type, misc]
        self._state["prd"] = prd
        return {"prd": prd.model_dump()}

    @listen(write_prd)  # type: ignore[misc]
    def explore_repo(self, prd_result: dict[str, Any]) -> dict[str, Any]:
        """Node 3 — scan the repository."""
        from ..agents.repo_explorer import RepoExplorerAgent

        inp = self._inp
        assert inp is not None
        explorer = RepoExplorerAgent()
        scan = explorer.explore(inp.repo_path)
        self._state["repo_scan"] = scan
        return {"repo_scan": scan.model_dump()}

    @listen(explore_repo)  # type: ignore[misc]
    def design_architecture(self, repo_result: dict[str, Any]) -> dict[str, Any]:
        """Node 4 — system architecture."""
        from ..agents.system_architect import SystemArchitectAgent

        inp = self._inp
        assert inp is not None
        languages = inp.languages or [Language.PYTHON]
        prd = self._state["prd"]
        scan = self._state["repo_scan"]
        architect = SystemArchitectAgent()
        arch = architect.design(prd=prd, scan=scan, languages=languages)
        self._state["architecture"] = arch
        return {"architecture": arch.model_dump()}

    @router(design_architecture)  # type: ignore[misc]
    def route_to_milestones(self, arch_result: dict[str, Any]) -> str:
        """Router node — proceed to milestone planning."""
        return "plan_milestones"

    @listen("plan_milestones")  # type: ignore[misc]
    def plan_milestones(self, route: str) -> dict[str, Any]:
        """Node 5 — milestone + task planning."""
        from ..agents.milestone_planner import MilestonePlannerAgent
        from ..agents.task_decomposer import TaskDecomposerAgent

        inp = self._inp
        assert inp is not None
        languages = inp.languages or [Language.PYTHON]
        prd = self._state["prd"]
        arch = self._state["architecture"]
        planner = MilestonePlannerAgent()
        milestones = planner.plan(prd=prd, architecture=arch, languages=languages)  # type: ignore[call-arg]
        decomposer = TaskDecomposerAgent()
        tasks = decomposer.decompose(milestones=milestones, architecture=arch, languages=languages)
        self._state["milestones"] = milestones
        self._state["tasks"] = tasks
        return {"milestone_count": len(milestones), "task_count": len(tasks)}

    @listen(plan_milestones)  # type: ignore[misc]
    def implement(self, plan_result: dict[str, Any]) -> dict[str, Any]:
        """Node 6 — implementation via executor router."""
        from ..agents.implementer import ImplementerAgent
        from ..config import FactoryConfig
        from ..executors.executor_router import ExecutorRouter
        from ..state import init_run

        inp = self._inp
        assert inp is not None
        languages = inp.languages or [Language.PYTHON]
        milestones = self._state["milestones"]
        tasks = self._state["tasks"]
        config = FactoryConfig()
        run = init_run(repo_path=inp.repo_path, mode=inp.mode,
                       flow="project_delivery_crewflow",
                       languages=[lang.value for lang in languages])
        router_inst = ExecutorRouter(config, allow_mock=inp.allow_mock)
        implementer = ImplementerAgent(router_inst)
        results = []
        for m in milestones:
            m_tasks = [t for t in tasks if t.milestone_id == m.milestone_id]
            if not m_tasks:
                continue
            impl = implementer.run_milestone(
                milestone_id=m.milestone_id, tasks=m_tasks, run=run,
                mode=inp.mode, languages=languages,
                concurrency=config.concurrency, fail_fast=config.fail_fast,
            )
            results.append(impl)
            run.state.implementation_results.append(impl)
        self._state["run"] = run
        return {"milestone_count": len(results)}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self, inp: ProjectDeliveryCrewFlowInput) -> Any:  # type: ignore[override]
        """Execute the flow. Raises RuntimeError when crewai is not installed."""
        if not _CREWAI_AVAILABLE:
            raise RuntimeError("crewai not installed")
        self._inp = inp
        self.classify_input()
        prd_result = self.write_prd(self._state.get("classification", {}))
        repo_result = self.explore_repo(prd_result)
        arch_result = self.design_architecture(repo_result)
        route = self.route_to_milestones(arch_result)
        self.plan_milestones(route)
        self.implement({})
        return self._state.get("run")
