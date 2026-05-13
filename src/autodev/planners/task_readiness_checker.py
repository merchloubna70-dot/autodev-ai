"""BMAD-12: TaskReadinessChecker — validates DeliveryTask against the
'Ready for Development Standard' (6 dimensions).

All checks are pure-Python heuristics; no LLM calls.
"""
from __future__ import annotations

import re

from ..schemas import (
    DeliveryTask,
    ReadinessCheck,
    ReadinessDimension,
    ReadinessSweepReport,
    TaskReadinessReport,
)

# ---------------------------------------------------------------------------
# Token-budget constants (chars ≈ tokens × 4)
# ---------------------------------------------------------------------------
_BUDGET_MIN_CHARS = 3600
_BUDGET_MAX_CHARS = 6400

# ---------------------------------------------------------------------------
# Patterns for _check_complete
# ---------------------------------------------------------------------------
_PLACEHOLDER_RE = re.compile(r"<[^>]+>|TODO|TBD|\.\.\.")

# ---------------------------------------------------------------------------
# Action verbs for _check_actionable
# ---------------------------------------------------------------------------
_ACTION_VERBS = {
    "implement", "create", "add", "write", "update", "fix", "refactor",
    "scaffold", "migrate", "remove", "delete", "rename", "extract", "move",
    "integrate", "configure", "enable", "disable", "generate", "build",
    "deploy", "test", "document", "review", "validate", "check", "lint",
    "profile", "benchmark", "audit", "wire", "apply",
}

# ---------------------------------------------------------------------------
# Testability keywords
# ---------------------------------------------------------------------------
_TESTABILITY_GIVEN_WHEN_THEN = re.compile(r"\b(given|when|then)\b", re.IGNORECASE)
_TESTABILITY_SHOULD_MUST = re.compile(r"\b(should|must)\b", re.IGNORECASE)

# ---------------------------------------------------------------------------
# Single-goal smell patterns
# ---------------------------------------------------------------------------
_MULTI_GOAL_RE = re.compile(
    r"\band\s+also\b|\band\s+then\b|\bfurthermore\b|\bin\s+addition\b",
    re.IGNORECASE,
)
# Multiple imperative sentences: two or more verbs starting a sentence
_IMPERATIVE_SENTENCE_RE = re.compile(
    r"(?:^|[.!?]\s+)(?:implement|create|add|write|update|fix|refactor|scaffold|migrate|remove|deploy|test|document|review|validate)\b",
    re.IGNORECASE,
)


class TaskReadinessChecker:
    """Checks a DeliveryTask (or list thereof) against the BMAD Ready-for-Dev
    standard.  All methods are pure-Python heuristics — no LLM required."""

    # ------------------------------------------------------------------
    # Per-dimension check methods
    # ------------------------------------------------------------------

    def _check_actionable(self, task: DeliveryTask) -> ReadinessCheck:
        """File path present + description starts with (or contains) an action verb."""
        reasons: list[str] = []

        has_file = bool(task.target_files)
        if not has_file:
            reasons.append("No target_files specified — task lacks a concrete file path.")

        desc_lower = task.description.lower()
        first_word = desc_lower.split()[0] if desc_lower.split() else ""
        has_verb = first_word in _ACTION_VERBS or any(
            v in desc_lower for v in _ACTION_VERBS
        )
        if not has_verb:
            reasons.append(
                f"Description '{task.description[:80]}' contains no recognisable action verb."
            )

        passed = has_file and has_verb
        return ReadinessCheck(
            dimension=ReadinessDimension.ACTIONABLE,
            passed=passed,
            reasons=reasons,
        )

    def _check_logical(self, tasks: list[DeliveryTask]) -> dict[str, ReadinessCheck]:
        """Deps form a DAG; no task depends on a non-existent task_id.

        Returns a dict keyed by task_id so check_all can merge per-task.
        """
        task_ids = {t.task_id for t in tasks}
        results: dict[str, ReadinessCheck] = {}

        # Detect cycles via DFS
        graph: dict[str, list[str]] = {t.task_id: [] for t in tasks}
        for t in tasks:
            for dep in t.dependencies:
                graph[t.task_id].append(dep.depends_on_task_id)

        def _has_cycle() -> bool:
            WHITE, GRAY, BLACK = 0, 1, 2
            color: dict[str, int] = {tid: WHITE for tid in task_ids}

            def dfs(node: str) -> bool:
                color[node] = GRAY
                for nb in graph.get(node, []):
                    if nb not in color:
                        continue  # orphan dep — handled separately
                    if color[nb] == GRAY:
                        return True
                    if color[nb] == WHITE and dfs(nb):
                        return True
                color[node] = BLACK
                return False

            return any(dfs(n) for n in list(task_ids) if color[n] == 0)

        cycle_present = _has_cycle()

        for t in tasks:
            reasons: list[str] = []
            orphan_deps = [
                dep.depends_on_task_id
                for dep in t.dependencies
                if dep.depends_on_task_id not in task_ids
            ]
            if orphan_deps:
                reasons.append(
                    f"Depends on unknown task_id(s): {orphan_deps}"
                )
            if cycle_present:
                reasons.append("Dependency graph contains a cycle.")

            results[t.task_id] = ReadinessCheck(
                dimension=ReadinessDimension.LOGICAL,
                passed=not reasons,
                reasons=reasons,
            )
        return results

    def _check_testable(self, task: DeliveryTask) -> ReadinessCheck:
        """ACs contain Given/When/Then or should/must verifiable keywords."""
        reasons: list[str] = []
        all_ac = " ".join(task.acceptance_criteria)

        has_gwt = bool(_TESTABILITY_GIVEN_WHEN_THEN.search(all_ac))
        has_sm = bool(_TESTABILITY_SHOULD_MUST.search(all_ac))

        if not task.acceptance_criteria:
            reasons.append("No acceptance_criteria defined.")
        elif not (has_gwt or has_sm):
            reasons.append(
                "acceptance_criteria lack Given/When/Then or should/must verifiable language."
            )

        passed = bool(task.acceptance_criteria) and (has_gwt or has_sm)
        return ReadinessCheck(
            dimension=ReadinessDimension.TESTABLE,
            passed=passed,
            reasons=reasons,
        )

    def _check_complete(self, task: DeliveryTask) -> ReadinessCheck:
        """No <...>, TODO, TBD, or ellipsis in description or ACs."""
        reasons: list[str] = []
        combined = task.description + " " + " ".join(task.acceptance_criteria)
        matches = _PLACEHOLDER_RE.findall(combined)
        if matches:
            unique = list(dict.fromkeys(matches))[:5]
            reasons.append(
                f"Placeholder(s) found: {unique} — description or ACs are incomplete."
            )
        return ReadinessCheck(
            dimension=ReadinessDimension.COMPLETE,
            passed=not reasons,
            reasons=reasons,
        )

    def _check_single_goal(self, task: DeliveryTask) -> ReadinessCheck:
        """Description should not contain multi-goal language or ≥3 imperative sentences."""
        reasons: list[str] = []

        if _MULTI_GOAL_RE.search(task.description):
            reasons.append(
                "Description contains multi-goal connectives ('and also', 'and then', etc.)."
            )

        imperatives = _IMPERATIVE_SENTENCE_RE.findall(task.description)
        if len(imperatives) >= 3:
            reasons.append(
                f"Description appears to contain {len(imperatives)} imperative goals — "
                "consider splitting into separate tasks."
            )

        return ReadinessCheck(
            dimension=ReadinessDimension.SINGLE_GOAL,
            passed=not reasons,
            reasons=reasons,
        )

    def _check_token_budget(self, task: DeliveryTask) -> ReadinessCheck:
        """Total char count of description + codex_prompt in 3600–6400 range."""
        reasons: list[str] = []
        total = len(task.description) + len(task.codex_prompt)

        if total < _BUDGET_MIN_CHARS:
            reasons.append(
                f"Task too small: {total} chars (min {_BUDGET_MIN_CHARS}). "
                "Consider adding more context, ACs, or target-file details."
            )
        elif total > _BUDGET_MAX_CHARS:
            reasons.append(
                f"Task oversized: {total} chars (max {_BUDGET_MAX_CHARS}). "
                "Consider splitting or trimming the description/codex_prompt."
            )

        return ReadinessCheck(
            dimension=ReadinessDimension.TOKEN_BUDGET,
            passed=not reasons,
            reasons=reasons,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def check_task(
        self,
        task: DeliveryTask,
        *,
        all_tasks: list[DeliveryTask] | None = None,
    ) -> TaskReadinessReport:
        """Run all 6 checks on a single task.

        Pass *all_tasks* to enable the full DAG-level logical check; otherwise
        only orphan-dep detection is possible (cycle check skipped).
        """
        logical_results = self._check_logical(all_tasks or [task])
        logical_check = logical_results.get(
            task.task_id,
            ReadinessCheck(dimension=ReadinessDimension.LOGICAL, passed=True),
        )

        checks = [
            self._check_actionable(task),
            logical_check,
            self._check_testable(task),
            self._check_complete(task),
            self._check_single_goal(task),
            self._check_token_budget(task),
        ]

        passed = all(c.passed for c in checks)
        blocker_count = sum(1 for c in checks if not c.passed)

        return TaskReadinessReport(
            task_id=task.task_id,
            checks=checks,
            passed=passed,
            blocker_count=blocker_count,
        )

    def check_all(self, tasks: list[DeliveryTask]) -> ReadinessSweepReport:
        """Run all checks across the full task list (enables full DAG check)."""
        logical_results = self._check_logical(tasks)

        per_task: list[TaskReadinessReport] = []
        for task in tasks:
            logical_check = logical_results.get(
                task.task_id,
                ReadinessCheck(dimension=ReadinessDimension.LOGICAL, passed=True),
            )
            checks = [
                self._check_actionable(task),
                logical_check,
                self._check_testable(task),
                self._check_complete(task),
                self._check_single_goal(task),
                self._check_token_budget(task),
            ]
            passed = all(c.passed for c in checks)
            blocker_count = sum(1 for c in checks if not c.passed)
            per_task.append(
                TaskReadinessReport(
                    task_id=task.task_id,
                    checks=checks,
                    passed=passed,
                    blocker_count=blocker_count,
                )
            )

        passing = sum(1 for r in per_task if r.passed)
        failing = len(per_task) - passing

        return ReadinessSweepReport(
            total_tasks=len(tasks),
            passing_tasks=passing,
            failing_tasks=failing,
            per_task=per_task,
            overall_passed=failing == 0 and len(tasks) > 0,
        )
