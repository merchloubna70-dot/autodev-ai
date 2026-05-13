"""Per-milestone task decomposition into Codex / Claude-executable units."""
from __future__ import annotations

from ..schemas import (
    ArchitectureSpec,
    DeliveryTask,
    ExecutionBackend,
    Language,
    Milestone,
    RiskLevel,
    TaskType,
)


class TaskPlanner:
    def plan(
        self,
        *,
        milestones: list[Milestone],
        architecture: ArchitectureSpec,
        languages: list[Language],
    ) -> list[DeliveryTask]:
        tasks: list[DeliveryTask] = []
        for m in milestones:
            if m.milestone_id == "M0":
                tasks.append(self._mk(
                    m, 1, "Lock PRD and architecture", "architecture",
                    TaskType.ARCHITECTURE, RiskLevel.LOW, ExecutionBackend.CLAUDE_CODE,
                    target=[".dev-factory/runs/<run_id>/architecture/architecture.md"],
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
                    ))
            elif m.milestone_id == "M2":
                for lang in languages:
                    tasks.append(self._mk(
                        m, len(tasks) + 1,
                        f"Implement core domain in {lang.value}",
                        f"Implement core domain entities and business logic with unit tests in {lang.value}.",
                        TaskType.FEATURE, RiskLevel.MEDIUM, ExecutionBackend.AUTO,
                        language=lang,
                    ))
            elif m.milestone_id == "M3":
                tasks.append(self._mk(
                    m, len(tasks) + 1, "Cross-language integration",
                    "Wire modules together; cross-language contract checks; integration tests.",
                    TaskType.INTEGRATION, RiskLevel.MEDIUM, ExecutionBackend.CLAUDE_CODE,
                ))
            elif m.milestone_id == "M4":
                tasks.append(self._mk(
                    m, len(tasks) + 1, "Security review", "Static security review across changed surface.",
                    TaskType.SECURITY, RiskLevel.HIGH, ExecutionBackend.CLAUDE_CODE,
                ))
                tasks.append(self._mk(
                    m, len(tasks) + 1, "Lint & typecheck cleanup",
                    "Pass language-specific lint and typecheck.",
                    TaskType.BUGFIX, RiskLevel.LOW, ExecutionBackend.CODEX,
                ))
            elif m.milestone_id == "M5":
                tasks.append(self._mk(
                    m, len(tasks) + 1, "Documentation", "README, usage, architecture docs.",
                    TaskType.DOCS, RiskLevel.LOW, ExecutionBackend.CLAUDE_CODE,
                ))
                tasks.append(self._mk(
                    m, len(tasks) + 1, "Release prep", "Release notes + delivery report.",
                    TaskType.RELEASE, RiskLevel.LOW, ExecutionBackend.CLAUDE_CODE,
                ))
            # collect ids on milestone
            m.task_ids = [t.task_id for t in tasks if t.milestone_id == m.milestone_id]
        return tasks

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
    ) -> DeliveryTask:
        tid = f"{m.milestone_id}-T{n}"
        return DeliveryTask(
            task_id=tid,
            milestone_id=m.milestone_id,
            title=title,
            description=description,
            target_files=target or [],
            allowed_files=target or [],
            forbidden_files=[".env", ".env.*", "**/secrets/**"],
            context_files=[],
            language=language,
            task_type=ttype,
            dependencies=[],
            codex_prompt=f"[{tid}] {title}: {description}",
            claude_prompt=f"[{tid}] {title}: {description}\nProduce a small, scoped, reviewable change.",
            expected_outputs=target or [],
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
