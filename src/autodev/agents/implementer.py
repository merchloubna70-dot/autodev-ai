"""Implementer — executes DeliveryTasks through ExecutorRouter only.

Hard rule: this module must NEVER import CodexCliExecutor or
ClaudeCodeExecutor directly. All CLI traffic goes through ExecutorRouter.

W2 additions:
- architect_editor_split: bool — when True, call OpusConsultAgent.architect
  before executing each task to get a plan, then pass plan context to executor.
- post_edit_lint: bool — when True, run PostEditLintGate after each task;
  retry up to 3 times if lint fails (pass error feedback to executor).
- evaluator_optimizer_iters: int — number of critic evaluation iterations
  (0 = disabled). Uses CriticAgent to score output and loop.
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

_MAX_LINT_RETRIES = 3
_MAX_CRITIC_ITERS = 3


class ImplementerAgent:
    def __init__(
        self,
        router: ExecutorRouter,
        failure_cluster_threshold: int = 2,
        architect_editor_split: bool = False,
        post_edit_lint: bool = False,
        evaluator_optimizer_iters: int = 0,
    ):
        # The router is the ONLY way this agent reaches Codex/Claude.
        self.router = router
        self.dep_planner = DependencyPlanner()
        self.failure_cluster_threshold = failure_cluster_threshold
        self.architect_editor_split = architect_editor_split
        self.post_edit_lint = post_edit_lint
        self.evaluator_optimizer_iters = min(evaluator_optimizer_iters, _MAX_CRITIC_ITERS)
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
                return self._run_task_with_loops(
                    task=t, run=_run, mode=_mode, cross_language=_cross
                )

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

    # ------------------------------------------------------------------
    # Per-task execution with optional loops
    # ------------------------------------------------------------------

    def _run_task_with_loops(
        self,
        *,
        task: DeliveryTask,
        run: RunState,
        mode: PipelineMode,
        cross_language: bool,
    ) -> ExecutionResult:
        """Execute one task, optionally with architect plan, lint retries, critic loop."""

        # 1. Optional architect plan
        plan_context: str = ""
        if self.architect_editor_split:
            plan_context = self._architect_plan(task, run)

        # 2. Build initial request (inject plan context into prompt if available)
        req = self._to_request(task, run=run, mode=mode, extra_context=plan_context)

        # 3. Execute with optional lint-retry loop
        result = self._execute_with_lint_retries(
            req, task=task, run=run, cross_language=cross_language, mode=mode
        )

        # 4. Optional evaluator-optimizer critic loop
        if self.evaluator_optimizer_iters > 0 and result.success:
            result = self._critic_loop(
                result, task=task, run=run, cross_language=cross_language, mode=mode
            )

        return result

    def _architect_plan(self, task: DeliveryTask, run: RunState) -> str:
        """Call OpusConsultAgent.architect and return the plan as a string."""
        try:
            from .opus_consult import OpusConsultAgent
            agent = OpusConsultAgent()
            question = (
                f"Task: {task.title}\nDescription: {task.description}\n"
                f"Language: {task.language}\n"
                "Provide a concise implementation plan."
            )
            opus_result = agent.architect(question)
            plan = opus_result.response_text or ""
            run.save_text(f"execution/architect_plan_{task.task_id}.md", plan)
            _logger.info("architect plan obtained for task=%s", task.task_id)
            return plan
        except Exception as exc:
            _logger.warning("architect plan failed for task=%s: %s", task.task_id, exc)
            return ""

    def _execute_with_lint_retries(
        self,
        req: ExecutionRequest,
        *,
        task: DeliveryTask,
        run: RunState,
        cross_language: bool,
        mode: PipelineMode,
    ) -> ExecutionResult:
        """Execute the request, retrying up to _MAX_LINT_RETRIES if post-edit lint fails."""
        result: ExecutionResult | None = None
        for attempt in range(1, _MAX_LINT_RETRIES + 2):  # +1 for initial attempt
            result, decision = self.router.execute(req, cross_language=cross_language)
            run.append_execution_call(result)
            run.save_json(
                f"execution/executor_selection_{task.task_id}.json", decision.to_json()
            )

            if not self.post_edit_lint or not result.success:
                return result

            lint_result = self._run_lint(task=task, run=run)
            if lint_result.ok:
                return result

            if attempt > _MAX_LINT_RETRIES:
                _logger.warning(
                    "lint gate failed after %d retries for task=%s errors=%s",
                    _MAX_LINT_RETRIES,
                    task.task_id,
                    lint_result.errors[:3],
                )
                return result

            # Rebuild request with lint error feedback
            error_feedback = "\n".join(lint_result.errors[:10])
            req = self._to_request(
                task,
                run=run,
                mode=mode,
                extra_context=f"Previous lint errors (fix these):\n{error_feedback}",
            )
            _logger.info(
                "lint retry %d for task=%s errors=%d",
                attempt,
                task.task_id,
                len(lint_result.errors),
            )

        return result  # type: ignore[return-value]

    def _run_lint(self, *, task: DeliveryTask, run: RunState):
        """Run PostEditLintGate for changed files inferred from the task."""
        from ..gates.post_edit_lint_gate import PostEditLintGate

        gate = PostEditLintGate()
        changed = list(task.allowed_files or [])
        lang = task.language or Language.UNKNOWN
        lint_result = gate.run(
            repo_path=run.repo_path,
            changed_files=changed,
            language=lang,
        )
        run.save_json(
            f"execution/lint_gate_{task.task_id}.json",
            lint_result,
        )
        return lint_result

    def _critic_loop(
        self,
        initial_result: ExecutionResult,
        *,
        task: DeliveryTask,
        run: RunState,
        cross_language: bool,
        mode: PipelineMode,
    ) -> ExecutionResult:
        """Run the evaluator-optimizer critic loop up to evaluator_optimizer_iters times."""
        from .critic import CriticAgent

        critic = CriticAgent()
        result = initial_result

        for i in range(self.evaluator_optimizer_iters):
            verdict = critic.evaluate(
                task_description=task.description,
                implementation_output=result.stdout or "",
                iteration=i,
            )
            run.save_json(
                f"execution/critic_verdict_{task.task_id}_iter{i}.json",
                verdict,
            )
            _logger.info(
                "critic iter=%d task=%s score=%.2f done=%s",
                i,
                task.task_id,
                verdict.score,
                verdict.done,
            )

            if verdict.done:
                break

            # Request another implementation pass with critic feedback
            notes = "; ".join(verdict.notes) if verdict.notes else "improve quality"
            req = self._to_request(
                task,
                run=run,
                mode=mode,
                extra_context=f"Critic score={verdict.score:.2f}. Improve: {notes}",
            )
            new_result, decision = self.router.execute(req, cross_language=cross_language)
            run.append_execution_call(new_result)
            run.save_json(
                f"execution/executor_selection_{task.task_id}_iter{i}.json",
                decision.to_json(),
            )
            if new_result.success:
                result = new_result

        return result

    def _to_request(
        self,
        task: DeliveryTask,
        *,
        run: RunState,
        mode: PipelineMode,
        extra_context: str = "",
    ) -> ExecutionRequest:
        backend = task.preferred_executor or ExecutionBackend.AUTO
        base_prompt = (
            task.codex_prompt
            if backend == ExecutionBackend.CODEX
            else (task.claude_prompt or task.codex_prompt)
        )
        prompt = base_prompt or task.description
        if extra_context:
            prompt = f"{prompt}\n\n---\n{extra_context}"
        return ExecutionRequest(
            task_id=task.task_id,
            milestone_id=task.milestone_id,
            repo_path=run.repo_path,
            prompt=prompt,
            language=task.language,
            mode=mode,
            backend=backend,
            allowed_files=task.allowed_files,
            forbidden_files=task.forbidden_files,
            context_files=task.context_files,
            risk_level=task.risk_level,
            task_type=task.task_type,
        )
