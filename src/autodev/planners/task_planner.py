"""Per-milestone task decomposition into Codex / Claude-executable units."""
from __future__ import annotations

from ..schemas import (
    ArchitectureSpec,
    DeliveryTask,
    ExecutionBackend,
    Language,
    Milestone,
    PRD,
    ProductBrief,
    RiskLevel,
    TaskPromptContext,
    TaskType,
    render_task_prompt,
)


class TaskPlanner:
    def plan(
        self,
        *,
        milestones: list[Milestone],
        architecture: ArchitectureSpec,
        languages: list[Language],
        prd: PRD | None = None,
        product_brief: ProductBrief | None = None,
        product_name: str | None = None,
        skip_m0_redundant_arch: bool = True,
    ) -> list[DeliveryTask]:
        # Build a shared context from provided kwargs
        ctx = self._build_context(prd=prd, product_brief=product_brief, product_name=product_name)

        tasks: list[DeliveryTask] = []
        for m in milestones:
            if m.milestone_id == "M0":
                if skip_m0_redundant_arch:
                    # Collapsed M0: architecture is already constructed in-flow by
                    # SystemArchitectAgent.design() and written to disk before tasks
                    # run. There is nothing left for an LLM-driven task to do here,
                    # so we emit ZERO tasks for M0. The flow's verifier still
                    # validates milestone_acceptance based on implementation_results,
                    # and a milestone with no tasks is trivially "complete".
                    pass
                else:
                    # Legacy M0 behavior
                    tasks.append(self._mk(
                        m, 1, "Lock PRD and architecture", "architecture",
                        TaskType.ARCHITECTURE, RiskLevel.LOW, ExecutionBackend.CLAUDE_CODE,
                        target=[".dev-factory/runs/<run_id>/architecture/architecture.md"],
                        context=ctx,
                    ))
            elif m.milestone_id == "M1":
                for lang in languages:
                    tasks.append(self._mk(
                        m, len(tasks) + 1,
                        f"Scaffold {lang.value} skeleton",
                        f"Create idiomatic {lang.value} project skeleton (src/, tests/, package manifest).",
                        TaskType.SCAFFOLD, RiskLevel.LOW, ExecutionBackend.CODEX,
                        language=lang,
                        target=self._scaffold_files(lang),
                        context=ctx,
                    ))
            elif m.milestone_id == "M2":
                for lang in languages:
                    tasks.append(self._mk(
                        m, len(tasks) + 1,
                        f"Implement core domain in {lang.value}",
                        f"Implement core domain entities and business logic with unit tests in {lang.value}.",
                        TaskType.FEATURE, RiskLevel.MEDIUM, ExecutionBackend.AUTO,
                        language=lang,
                        context=ctx,
                    ))
            elif m.milestone_id == "M3":
                tasks.append(self._mk(
                    m, len(tasks) + 1, "Cross-language integration",
                    "Wire modules together; cross-language contract checks; integration tests.",
                    TaskType.INTEGRATION, RiskLevel.MEDIUM, ExecutionBackend.CLAUDE_CODE,
                    context=ctx,
                ))
            elif m.milestone_id == "M4":
                tasks.append(self._mk(
                    m, len(tasks) + 1, "Security review", "Static security review across changed surface.",
                    TaskType.SECURITY, RiskLevel.HIGH, ExecutionBackend.CLAUDE_CODE,
                    context=ctx,
                ))
                tasks.append(self._mk(
                    m, len(tasks) + 1, "Lint & typecheck cleanup",
                    "Pass language-specific lint and typecheck.",
                    TaskType.BUGFIX, RiskLevel.LOW, ExecutionBackend.CODEX,
                    context=ctx,
                ))
            elif m.milestone_id == "M5":
                tasks.append(self._mk(
                    m, len(tasks) + 1, "Documentation", "README, usage, architecture docs.",
                    TaskType.DOCS, RiskLevel.LOW, ExecutionBackend.CLAUDE_CODE,
                    context=ctx,
                ))
                tasks.append(self._mk(
                    m, len(tasks) + 1, "Release prep", "Release notes + delivery report.",
                    TaskType.RELEASE, RiskLevel.LOW, ExecutionBackend.CLAUDE_CODE,
                    context=ctx,
                ))
            # collect ids on milestone
            m.task_ids = [t.task_id for t in tasks if t.milestone_id == m.milestone_id]
        return tasks

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_context(
        self,
        *,
        prd: PRD | None,
        product_brief: ProductBrief | None,
        product_name: str | None,
    ) -> TaskPromptContext | None:
        """Build a TaskPromptContext from optional PRD/brief/name kwargs.
        Returns None when no meaningful context is available (backward compat)."""
        # Collect fields from available sources, preferring PRD > brief > name
        resolved_name = (
            product_name
            or (prd.product_name if prd else None)
            or (product_brief.product_name if product_brief else None)
            or ""
        )
        prd_overview = prd.overview if prd else ""
        ac: list[str] = []
        if prd and prd.acceptance_criteria:
            ac = [a.description for a in prd.acceptance_criteria]
        delivery_boundary = product_brief.delivery_boundary if product_brief else ""
        non_goals = product_brief.non_goals if product_brief else []

        if not any([resolved_name, prd_overview, ac, delivery_boundary, non_goals]):
            return None

        return TaskPromptContext(
            product_name=resolved_name,
            prd_overview=prd_overview,
            acceptance_criteria=ac,
            delivery_boundary=delivery_boundary,
            non_goals=non_goals,
        )

    def _mk(
        self,
        m: Milestone,
        n: int,
        title: str,
        description: str,
        ttype: TaskType,
        risk: RiskLevel,
        preferred: ExecutionBackend,
        *,
        language: Language = Language.UNKNOWN,
        target: list[str] | None = None,
        context: TaskPromptContext | None = None,
    ) -> DeliveryTask:
        tid = f"{m.milestone_id}-T{n}"
        target_files = target or []

        codex_prompt = render_task_prompt(
            task_id=tid,
            title=title,
            description=description,
            target_files=target_files,
            context=context,
        )
        claude_prompt = render_task_prompt(
            task_id=tid,
            title=title,
            description=description,
            target_files=target_files,
            context=context,
        ) + "\nProduce a small, scoped, reviewable change."

        return DeliveryTask(
            task_id=tid,
            milestone_id=m.milestone_id,
            title=title,
            description=description,
            target_files=target_files,
            allowed_files=target_files,
            forbidden_files=[".env", ".env.*", "**/secrets/**"],
            context_files=[],
            language=language,
            task_type=ttype,
            dependencies=[],
            codex_prompt=codex_prompt,
            claude_prompt=claude_prompt,
            expected_outputs=target_files,
            acceptance_criteria=[f"{tid} acceptance satisfied"],
            required_tests=[],
            risk_level=risk,
            rollback_strategy="revert generated files; rerun task with stricter prompt",
            preferred_executor=preferred,
        )

    def _scaffold_files(self, lang: Language) -> list[str]:
        if lang == Language.PYTHON:
            return ["pyproject.toml", "src/__init__.py", "tests/__init__.py", "README.md"]
        if lang == Language.RUST:
            return ["Cargo.toml", "src/lib.rs", "tests/.gitkeep"]
        if lang == Language.TYPESCRIPT:
            return ["package.json", "tsconfig.json", "src/index.ts", "tests/.gitkeep"]
        return []
