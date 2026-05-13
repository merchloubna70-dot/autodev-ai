"""IssuePipelineCrewFlow — alternative implementation of the issue pipeline using crewai.Flow.

Uses @start / @listen / @router decorators when crewai.flow is available.
Falls back to a stub with the same public API that raises RuntimeError on .run(...)
when crewai is not installed.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..schemas import ExecutionBackend, Language, PipelineMode

# ---------------------------------------------------------------------------
# Input dataclass — mirrors IssuePipelineInput for interop
# ---------------------------------------------------------------------------


@dataclass
class IssuePipelineCrewFlowInput:
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


# ---------------------------------------------------------------------------
# Try to import crewai.flow — optional dependency
# ---------------------------------------------------------------------------

try:
    from crewai.flow.flow import Flow, listen, router, start  # type: ignore[import]

    _CREWAI_AVAILABLE = True
except Exception:  # ImportError or anything else
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


class IssuePipelineCrewFlow(Flow):  # type: ignore[misc]
    """CrewAI Flow variant of IssuePipelineFlow.

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
        self._inp: IssuePipelineCrewFlowInput | None = None

    # ------------------------------------------------------------------
    # Flow nodes
    # ------------------------------------------------------------------

    @start()  # type: ignore[misc]
    def classify_input(self) -> dict[str, Any]:
        """Node 1 — classify the raw issue text."""
        from ..agents.input_classifier import InputClassifierAgent
        from pathlib import Path

        inp = self._inp
        assert inp is not None
        classifier = InputClassifierAgent()
        cls = classifier.classify(
            text=inp.issue_text,
            source_url=inp.issue_url,
            source_path=None,
            has_existing_code=Path(inp.repo_path).exists() and any(Path(inp.repo_path).iterdir()),
        )
        self._state["classification"] = cls
        return {"classification": cls.model_dump()}

    @listen(classify_input)  # type: ignore[misc]
    def analyse_issue(self, classify_result: dict[str, Any]) -> dict[str, Any]:
        """Node 2 — parse the issue into structured form."""
        from ..agents.issue_analyst import IssueAnalystAgent

        inp = self._inp
        assert inp is not None
        analyst = IssueAnalystAgent()
        issue = analyst.parse(inp.issue_text, issue_id=inp.issue_id)
        self._state["issue"] = issue
        return {"issue": issue.model_dump()}

    @listen(analyse_issue)  # type: ignore[misc]
    def explore_repo(self, issue_result: dict[str, Any]) -> dict[str, Any]:
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
        """Node 4 — produce architecture spec."""
        from ..agents.system_architect import SystemArchitectAgent
        from ..schemas import PRD

        inp = self._inp
        assert inp is not None
        issue = self._state["issue"]
        scan = self._state["repo_scan"]
        prd_stub = PRD(
            product_name=issue.title or "issue",
            overview=issue.summary or "",
            functional_requirements=[],
            non_functional_requirements=[],
            acceptance_criteria=[],
        )
        languages = inp.languages or [Language.PYTHON]
        architect = SystemArchitectAgent()
        arch = architect.design(prd=prd_stub, scan=scan, languages=languages)
        self._state["architecture"] = arch
        return {"architecture": arch.model_dump()}

    @router(design_architecture)  # type: ignore[misc]
    def route_to_implementation(self, arch_result: dict[str, Any]) -> str:
        """Router node — always proceed to implement."""
        return "implement"

    @listen("implement")  # type: ignore[misc]
    def implement(self, route: str) -> dict[str, Any]:
        """Node 5 — task decomposition + implementation."""
        from ..agents.task_decomposer import TaskDecomposerAgent
        from ..schemas import DeliveryTask, Milestone, MilestonePlan
        from ..config import FactoryConfig
        from ..executors.executor_router import ExecutorRouter
        from ..agents.implementer import ImplementerAgent
        from ..state import init_run

        inp = self._inp
        assert inp is not None
        languages = inp.languages or [Language.PYTHON]
        arch = self._state["architecture"]
        issue = self._state["issue"]

        m = Milestone(
            milestone_id="MI-1",
            title=f"Resolve {issue.issue_id}",
            objective=issue.title,
            deliverables=[f"Code change addressing {issue.issue_id}"],
            acceptance_criteria=issue.acceptance_criteria or [f"{issue.issue_id} acceptance"],
            quality_gates=["python_gate"],
            allowed_languages=languages,
        )
        decomposer = TaskDecomposerAgent()
        tasks = decomposer.decompose(milestones=[m], architecture=arch, languages=languages)
        if not tasks:
            tasks = [
                DeliveryTask(
                    task_id="MI-1-T1",
                    milestone_id="MI-1",
                    title=issue.title,
                    description=issue.summary or issue.title,
                )
            ]
        config = FactoryConfig()
        run = init_run(repo_path=inp.repo_path, mode=inp.mode, flow="issue_pipeline_crewflow",
                       languages=[l.value for l in languages])
        router_inst = ExecutorRouter(config, allow_mock=inp.allow_mock)
        implementer = ImplementerAgent(router_inst)
        impl = implementer.run_milestone(
            milestone_id="MI-1", tasks=tasks, run=run, mode=inp.mode,
            languages=languages, concurrency=config.concurrency, fail_fast=config.fail_fast,
        )
        self._state["run"] = run
        self._state["impl"] = impl
        return {"success": impl.success}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self, inp: IssuePipelineCrewFlowInput) -> Any:  # type: ignore[override]
        """Execute the flow. Raises RuntimeError when crewai is not installed."""
        if not _CREWAI_AVAILABLE:
            raise RuntimeError("crewai not installed")
        self._inp = inp
        self.classify_input()
        issue_result = self.analyse_issue(self._state.get("classification", {}))
        repo_result = self.explore_repo(issue_result)
        arch_result = self.design_architecture(repo_result)
        route = self.route_to_implementation(arch_result)
        self.implement(route)
        return self._state.get("run")
