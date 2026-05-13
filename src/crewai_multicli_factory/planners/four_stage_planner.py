"""FourStagePlanner — builds the serial 4-stage bug-fix task chain.

Produces exactly 4 ``DeliveryTask`` objects with IDs::

    BUG-T1-REPRODUCE  (TaskType.TEST   — write minimal repro)
    BUG-T2-LOCATE     (TaskType.BUGFIX — locate root cause, read-only)
    BUG-T3-PATCH      (TaskType.BUGFIX — apply minimal patch)
    BUG-T4-VERIFY     (TaskType.TEST   — local gate verification)

Each stage depends on the prior one via ``TaskDependency``.  The prompts
reference the four Markdown templates shipped in
``crewai_multicli_factory/templates/four_stage/``.
"""
from __future__ import annotations

from importlib import resources
from pathlib import Path

from ..schemas import (
    DeliveryTask,
    ExecutionBackend,
    Language,
    RiskLevel,
    TaskDependency,
    TaskType,
)

_MILESTONE_ID = "MBUG-1"

# Stage metadata: (task_id, title, task_type, template_name, description_one_liner)
_STAGES = [
    (
        "BUG-T1-REPRODUCE",
        "Reproduce — write minimal failing test",
        TaskType.TEST,
        "reproduce.md",
        "Write a minimal reproduction script that fails on the current commit, proving the bug exists.",
    ),
    (
        "BUG-T2-LOCATE",
        "Locate — read-only root cause analysis",
        TaskType.BUGFIX,
        "locate.md",
        "Using the repro output, locate the exact file:line root cause. Read-only; output root_cause.md.",
    ),
    (
        "BUG-T3-PATCH",
        "Patch — minimal targeted fix",
        TaskType.BUGFIX,
        "patch.md",
        "Apply the minimal fix (±20 lines) identified in root_cause.md so the repro test passes.",
    ),
    (
        "BUG-T4-VERIFY",
        "Verify — local gate check",
        TaskType.TEST,
        "verify.md",
        "Run the project's local dev-CI gate; confirm no regressions; produce verify.md.",
    ),
]


def _load_template(name: str) -> str:
    """Load a four_stage template by filename, falling back to a stub on error."""
    try:
        pkg_root = Path(__file__).resolve().parent.parent
        tpl_path = pkg_root / "templates" / "four_stage" / name
        return tpl_path.read_text(encoding="utf-8")
    except Exception:
        return f"# {name}\n{{bug_description}}\nRepo: {{repo_path}}\nLanguage: {{language}}\n"


class FourStagePlanner:
    """Build a 4-stage serial bug-fix plan as a list of ``DeliveryTask`` objects."""

    def plan(
        self,
        bug_description: str,
        repo_path: str,
        language: str | Language = Language.UNKNOWN,
    ) -> list[DeliveryTask]:
        """Return exactly 4 ``DeliveryTask`` objects chained T1→T2→T3→T4.

        Parameters
        ----------
        bug_description:
            Free-text description of the bug (copied into each task prompt).
        repo_path:
            Absolute or relative path to the repository root.
        language:
            Primary language of the codebase.
        """
        if isinstance(language, str):
            try:
                language = Language(language.lower())
            except ValueError:
                language = Language.UNKNOWN

        lang_str = language.value
        tasks: list[DeliveryTask] = []

        for i, (task_id, title, ttype, tpl_name, one_liner) in enumerate(_STAGES):
            raw_template = _load_template(tpl_name)
            prompt = raw_template.format(
                bug_description=bug_description,
                repo_path=repo_path,
                language=lang_str,
                slug="bug",
            )

            # Each stage after the first depends on the immediately preceding one
            deps: list[TaskDependency] = []
            if i > 0:
                prev_id = _STAGES[i - 1][0]
                deps = [TaskDependency(
                    depends_on_task_id=prev_id,
                    reason=f"Stage {i+1} requires the output of stage {i}",
                )]

            task = DeliveryTask(
                task_id=task_id,
                milestone_id=_MILESTONE_ID,
                title=title,
                description=one_liner,
                language=language,
                task_type=ttype,
                dependencies=deps,
                codex_prompt=prompt,
                claude_prompt=prompt,
                risk_level=RiskLevel.MEDIUM,
                preferred_executor=ExecutionBackend.AUTO,
                forbidden_files=[".env", ".env.*", "**/secrets/**"],
                context_files=[repo_path],
            )
            tasks.append(task)

        return tasks
