"""Implementer — executes DeliveryTasks through ExecutorRouter only.

Hard rule: this module must NEVER import CodexCliExecutor or
ClaudeCodeExecutor directly. All CLI traffic goes through ExecutorRouter.
"""
from __future__ import annotations

from ..executors.executor_router import ExecutorRouter, is_cross_language
from ..planners.dependency_planner import DependencyPlanner
from ..schemas import (
    DeliveryTask,
    ExecutionBackend,
    ExecutionRequest,
    ExecutionResult,
    ImplementationResult,
    Language,
    PipelineMode,
)
from ..state import RunState
from ..utils.concurrency import run_parallel
from ..utils.logging import get_logger
from ._crewai_bridge import make_agent
from .failure_cluster_reviewer import FailureClusterReviewer

_logger = get_logger("implementer")


class ImplementerAgent:
    def __init__(self, router: ExecutorRouter, failure_cluster_threshold: int = 2):
        # The router is the ONLY way this agent reaches Codex/Claude.
        self.router = router
        self.dep_planner = DependencyPlanner()
        self.failure_cluster_threshold = failure_cluster_threshold
        self.agent = make_agent(
            role="Implementer",
            goal="Execute delivery tasks via the multi-CLI ExecutorRouter, never directly.",
            backstory="A senior engineer who delegates to Codex or Claude based on task shape.",
        )

    def run_milestone(
        self,
        *,
        milestone_id: str,
        tasks: list[DeliveryTask],
        run: RunState,
        mode: PipelineMode,
        languages: list[Language],
        concurrency: int = 3,
        fail_fast: bool = True,
    ) -> ImplementationResult:
        milestone_tasks = [t for t in tasks if t.milestone_id == milestone_id]
        if not milestone_tasks:
            return ImplementationResult(milestone_id=milestone_id, success=True)
        waves = self.dep_planner.waves(milestone_tasks)
        results: list[ExecutionResult] = []
        failed: list[str] = []
        cross_lang = is_cross_language(languages)
        for wave in waves:
            wave_tasks = [t for t in milestone_tasks if t.task_id in wave]
            def run_one(t: DeliveryTask, _run=run, _mode=mode, _cross=cross_lang) -> ExecutionResult:
                req = self._to_request(t, run=_run, mode=_mode)
                result, decision = self.router.execute(req, cross_language=_cross)
                _run.append_execution_call(result)
                _run.save_json(
                    f"execution/executor_selection_{t.task_id}.json", decision.to_json()
                )
                return result
            wave_results = run_parallel(run_one, wave_tasks, concurrency=concurrency, fail_fast=fail_fast)
            for r in wave_results:
                if r is None:
                    continue
                results.append(r)
                if not r.success:
                    failed.append(r.task_id)
                    _logger.warning("task failed: %s reason=%s", r.task_id, r.error_type)
            if failed and fail_fast:
                break

        any_mock = any(r.mock_used for r in results)
        impl = ImplementationResult(
            milestone_id=milestone_id,
            task_results=results,
            success=len(failed) == 0,
            mock_used=any_mock,
            failed_task_ids=failed,
        )
        run.save_json(f"execution/milestone_{milestone_id}_results.json", impl)

        # Failure-cluster review: auto-trigger OpusConsultAgent when ≥ threshold tasks fail.
        threshold = self.failure_cluster_threshold
        if threshold > 0 and len(failed) >= threshold:
            failed_results = [r for r in results if not r.success]
            reviewer = FailureClusterReviewer(threshold=threshold)
            cluster_report = reviewer.review(
                milestone_id=milestone_id,
                failed_results=failed_results,
            )
            run.save_text(
                "quality/failure_cluster_review.md",
                cluster_report.review_text,
            )
            if cluster_report.opus_result is not None:
                run.save_json(
                    "quality/failure_cluster_opus_result.json",
                    cluster_report.opus_result,
                )
            _logger.info(
                "failure cluster review: milestone=%s failures=%d opus_consulted=%s",
                milestone_id,
                cluster_report.failure_count,
                cluster_report.opus_consulted,
            )

        return impl

    def _to_request(self, task: DeliveryTask, *, run: RunState, mode: PipelineMode) -> ExecutionRequest:
        backend = task.preferred_executor or ExecutionBackend.AUTO
        prompt = task.codex_prompt if backend == ExecutionBackend.CODEX else (task.claude_prompt or task.codex_prompt)
        return ExecutionRequest(
            task_id=task.task_id,
            milestone_id=task.milestone_id,
            repo_path=run.repo_path,
            prompt=prompt or task.description,
            language=task.language,
            mode=mode,
            backend=backend,
            allowed_files=task.allowed_files,
            forbidden_files=task.forbidden_files,
            context_files=task.context_files,
            risk_level=task.risk_level,
            task_type=task.task_type,
        )
