"""Compute parallel waves for task dependencies (same-file conflicts serialized)."""
from __future__ import annotations

from ..schemas import DeliveryTask, RiskLevel
from ..utils.concurrency import topological_batches


class DependencyPlanner:
    def waves(self, tasks: list[DeliveryTask]) -> list[list[str]]:
        ids = [t.task_id for t in tasks]
        edges: list[tuple[str, str]] = []
        for t in tasks:
            for dep in t.dependencies:
                edges.append((dep.depends_on_task_id, t.task_id))

        # serialize same-file conflicts: any two tasks writing the same file
        by_file: dict[str, list[str]] = {}
        for t in tasks:
            for f in t.allowed_files or t.target_files:
                by_file.setdefault(f, []).append(t.task_id)
        for fname, task_ids in by_file.items():
            for a, b in zip(task_ids, task_ids[1:]):
                edges.append((a, b))

        # serialize high/critical risk: depend on all previous lower-risk tasks
        prev = None
        for t in tasks:
            if t.risk_level in (RiskLevel.HIGH, RiskLevel.CRITICAL):
                if prev is not None:
                    edges.append((prev, t.task_id))
                prev = t.task_id

        return topological_batches(ids, edges)
