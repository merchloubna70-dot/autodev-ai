"""Compute parallel waves for task dependencies (same-file conflicts serialized)."""
from __future__ import annotations

import itertools

from ..schemas import DeliveryTask, RiskLevel
from ..utils.concurrency import topological_batches
from ._wave_explanation import WaveExplanation


class DependencyPlanner:
    def __init__(
        self,
        *,
        respect_same_file_conflicts: bool = True,
        serialize_high_risk_tail: bool = True,
    ) -> None:
        self.respect_same_file_conflicts = respect_same_file_conflicts
        self.serialize_high_risk_tail = serialize_high_risk_tail

    def _build_edges(
        self, tasks: list[DeliveryTask]
    ) -> tuple[list[tuple[str, str]], dict[str, list[str]]]:
        """Return (edges, edge_reasons) where edge_reasons maps task_id -> reasons."""
        edges: list[tuple[str, str]] = []
        edge_reasons: dict[str, list[str]] = {t.task_id: [] for t in tasks}

        # explicit declared dependencies
        for t in tasks:
            for dep in t.dependencies:
                edges.append((dep.depends_on_task_id, t.task_id))
                reason = dep.reason or "declared dependency"
                edge_reasons[t.task_id].append(
                    f"blocked-by-{dep.depends_on_task_id} ({reason})"
                )

        if self.respect_same_file_conflicts:
            # serialize same-file conflicts: only tasks that BOTH have non-empty
            # allowed_files (or target_files) AND share at least one file.
            # GUARD: skip empty file keys to avoid spurious serialization of tasks
            # with no file affinity.
            by_file: dict[str, list[str]] = {}
            for t in tasks:
                files = t.allowed_files or t.target_files
                for f in files:
                    if not f:  # skip empty string keys
                        continue
                    by_file.setdefault(f, []).append(t.task_id)
            for fname, task_ids in by_file.items():
                for a, b in itertools.pairwise(task_ids):
                    edges.append((a, b))
                    edge_reasons[b].append(
                        f"blocked-by-{a} (same-file conflict: {fname})"
                    )

        if self.serialize_high_risk_tail:
            # serialize high/critical risk: each HIGH/CRITICAL depends on the
            # previous HIGH/CRITICAL task only (not all prior tasks).
            prev: str | None = None
            for t in tasks:
                if t.risk_level in (RiskLevel.HIGH, RiskLevel.CRITICAL):
                    if prev is not None:
                        edges.append((prev, t.task_id))
                        edge_reasons[t.task_id].append(
                            f"blocked-by-{prev} (high/critical risk serialization)"
                        )
                    prev = t.task_id

        return edges, edge_reasons

    def waves(self, tasks: list[DeliveryTask]) -> list[list[str]]:
        ids = [t.task_id for t in tasks]
        edges, _ = self._build_edges(tasks)
        return topological_batches(ids, edges)

    def explain_waves(self, tasks: list[DeliveryTask]) -> WaveExplanation:
        """Return a structured audit report of wave placement reasons."""
        ids = [t.task_id for t in tasks]
        edges, edge_reasons = self._build_edges(tasks)
        wave_list = topological_batches(ids, edges)

        # build stats
        num_waves = len(wave_list)
        widths = [len(w) for w in wave_list]
        max_width = max(widths, default=0)
        avg_width = sum(widths) / num_waves if num_waves else 0.0
        single_task_waves = sum(1 for w in widths if w == 1)

        stats = {
            "num_waves": num_waves,
            "max_width": max_width,
            "avg_width": avg_width,
            "single_task_waves": single_task_waves,
        }

        # annotate tasks with no blocking reason as "wave N (no dependencies)"
        reasons: dict[str, list[str]] = {}
        for wave_idx, wave in enumerate(wave_list):
            for task_id in wave:
                r = edge_reasons.get(task_id, [])
                if not r:
                    r = [f"wave {wave_idx} (no dependencies)"]
                reasons[task_id] = r

        return WaveExplanation(waves=wave_list, reasons=reasons, stats=stats)
