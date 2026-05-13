"""FourStagePlanner — builds the serial 4-stage bug-fix task chain.

Produces exactly 4 ``DeliveryTask`` objects with IDs::

    BUG-T1-REPRODUCE  (TaskType.TEST   — write minimal repro)
    BUG-T2-LOCATE     (TaskType.BUGFIX — locate root cause, read-only)
    BUG-T3-PATCH      (TaskType.BUGFIX — apply minimal patch)
    BUG-T4-VERIFY     (TaskType.TEST   — local gate verification)

Each stage depends on the prior one via ``TaskDependency``.  The prompts
reference the four Markdown templates shipped in
``crewai_multicli_factory/templates/four_stage/``.

When ``three_pass_locate=True`` the LOCATE stage (BUG-T2-LOCATE) is expanded
into 3 sub-tasks chained via TaskDependency:

    BUG-T2A-REPO-TREE   (repo-tree pass)
    BUG-T2B-SKELETON    (skeleton pass)
    BUG-T2C-LINE-RANGE  (line-range pass)

Default behavior (``three_pass_locate=False``) is fully preserved.
"""
from __future__ import annotations

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

# Three-pass sub-decomposition of the LOCATE stage (T2A → T2B → T2C)
_THREE_PASS_STAGES = [
    (
        "BUG-T2A-REPO-TREE",
        "Locate (pass A) — repo-tree survey",
        TaskType.BUGFIX,
        "locate.md",
        "Pass A: survey the repo tree to identify candidate directories and files.",
    ),
    (
        "BUG-T2B-SKELETON",
        "Locate (pass B) — skeleton inspection",
        TaskType.BUGFIX,
        "locate.md",
        "Pass B: read class/function skeletons of candidates to narrow the search.",
    ),
    (
        "BUG-T2C-LINE-RANGE",
        "Locate (pass C) — line-range pinpoint",
        TaskType.BUGFIX,
        "locate.md",
        "Pass C: pinpoint the exact file:line range; output root_cause.md.",
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


def _make_task(
    *,
    task_id: str,
    title: str,
    ttype: TaskType,
    tpl_name: str,
    one_liner: str,
    deps: list[TaskDependency],
    bug_description: str,
    repo_path: str,
    language: Language,
) -> DeliveryTask:
    raw_template = _load_template(tpl_name)
    prompt = raw_template.format(
        bug_description=bug_description,
        repo_path=repo_path,
        language=language.value,
        slug="bug",
    )
    return DeliveryTask(
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


class FourStagePlanner:
    """Build a 4-stage serial bug-fix plan as a list of ``DeliveryTask`` objects.

    Parameters
    ----------
    three_pass_locate:
        When True the LOCATE stage (BUG-T2-LOCATE) is expanded into 3
        sub-tasks (T2A repo-tree, T2B skeleton, T2C line-range) chained via
        TaskDependency.  Default is False; existing behavior is fully preserved.
    """

    def __init__(self, *, three_pass_locate: bool = False) -> None:
        self.three_pass_locate = three_pass_locate

    def plan(
        self,
        bug_description: str,
        repo_path: str,
        language: str | Language = Language.UNKNOWN,
    ) -> list[DeliveryTask]:
        """Return ``DeliveryTask`` objects chained as a bug-fix pipeline.

        Without ``three_pass_locate``: exactly 4 tasks (T1→T2→T3→T4).
        With ``three_pass_locate``: 6 tasks (T1→T2A→T2B→T2C→T3→T4).

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

        tasks: list[DeliveryTask] = []

        common_kwargs = dict(
            bug_description=bug_description,
            repo_path=repo_path,
            language=language,
        )

        # T1 — REPRODUCE (no deps)
        t1_id, t1_title, t1_type, t1_tpl, t1_liner = _STAGES[0]
        tasks.append(_make_task(
            task_id=t1_id, title=t1_title, ttype=t1_type, tpl_name=t1_tpl,
            one_liner=t1_liner,
            deps=[],
            **common_kwargs,
        ))

        # T2 — LOCATE (standard or 3-pass)
        prev_dep_id = t1_id  # last task before PATCH must be determined after T2 section
        if self.three_pass_locate:
            for j, (sub_id, sub_title, sub_type, sub_tpl, sub_liner) in enumerate(_THREE_PASS_STAGES):
                if j == 0:
                    sub_deps = [TaskDependency(
                        depends_on_task_id=t1_id,
                        reason="T2A repo-tree pass requires T1 repro output",
                    )]
                else:
                    prev_sub_id = _THREE_PASS_STAGES[j - 1][0]
                    sub_deps = [TaskDependency(
                        depends_on_task_id=prev_sub_id,
                        reason=f"Pass {chr(ord('A') + j)} requires pass {chr(ord('A') + j - 1)} output",
                    )]
                tasks.append(_make_task(
                    task_id=sub_id, title=sub_title, ttype=sub_type, tpl_name=sub_tpl,
                    one_liner=sub_liner, deps=sub_deps, **common_kwargs,
                ))
            prev_dep_id = _THREE_PASS_STAGES[-1][0]
        else:
            t2_id, t2_title, t2_type, t2_tpl, t2_liner = _STAGES[1]
            tasks.append(_make_task(
                task_id=t2_id, title=t2_title, ttype=t2_type, tpl_name=t2_tpl,
                one_liner=t2_liner,
                deps=[TaskDependency(
                    depends_on_task_id=t1_id,
                    reason="Stage 2 requires the output of stage 1",
                )],
                **common_kwargs,
            ))
            prev_dep_id = t2_id

        # T3 — PATCH
        t3_id, t3_title, t3_type, t3_tpl, t3_liner = _STAGES[2]
        tasks.append(_make_task(
            task_id=t3_id, title=t3_title, ttype=t3_type, tpl_name=t3_tpl,
            one_liner=t3_liner,
            deps=[TaskDependency(
                depends_on_task_id=prev_dep_id,
                reason="Stage 3 requires the output of the locate stage",
            )],
            **common_kwargs,
        ))

        # T4 — VERIFY
        t4_id, t4_title, t4_type, t4_tpl, t4_liner = _STAGES[3]
        tasks.append(_make_task(
            task_id=t4_id, title=t4_title, ttype=t4_type, tpl_name=t4_tpl,
            one_liner=t4_liner,
            deps=[TaskDependency(
                depends_on_task_id=t3_id,
                reason="Stage 4 requires the output of stage 3",
            )],
            **common_kwargs,
        ))

        return tasks
