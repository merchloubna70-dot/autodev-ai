"""StepRunner — BMAD micro-file step execution framework.

Provides Step, StepRegistry, and StepRunner.  Steps are persisted to
``.dev-factory/runs/<run_id>/steps/<step_name>.json`` for resume-aware
re-entry at any granularity.
"""
from __future__ import annotations

import time
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..schemas import StepRecord, StepStatus


@dataclass
class Step:
    name: str
    description: str
    func: Callable[..., Any]
    inputs: list[str] = field(default_factory=list)
    outputs: list[str] = field(default_factory=list)
    depends_on: list[str] = field(default_factory=list)


class StepRegistry:
    """Registry of named Steps with topological ordering."""

    def __init__(self, name: str = "default") -> None:
        self.name = name
        self._steps: dict[str, Step] = {}

    def register(self, step: Step) -> None:
        self._steps[step.name] = step

    def list_steps(self) -> list[Step]:
        return list(self._steps.values())

    def find(self, name: str) -> Step:
        if name not in self._steps:
            raise KeyError(f"Step {name!r} not found in registry {self.name!r}")
        return self._steps[name]

    def topological_order(self) -> list[Step]:
        """Return steps in dependency-respecting order (Kahn's algorithm)."""
        in_degree: dict[str, int] = defaultdict(int)
        graph: dict[str, list[str]] = defaultdict(list)

        all_names = set(self._steps)
        for step in self._steps.values():
            for dep in step.depends_on:
                if dep in all_names:
                    graph[dep].append(step.name)
                    in_degree[step.name] += 1

        queue = [n for n in all_names if in_degree[n] == 0]
        # Preserve insertion order for stable results
        insertion_order = list(self._steps.keys())
        queue.sort(key=lambda n: insertion_order.index(n))

        result: list[Step] = []
        while queue:
            node = queue.pop(0)
            result.append(self._steps[node])
            for neighbour in graph[node]:
                in_degree[neighbour] -= 1
                if in_degree[neighbour] == 0:
                    queue.append(neighbour)
                    queue.sort(key=lambda n: insertion_order.index(n))

        if len(result) != len(self._steps):
            raise RuntimeError("Cycle detected in step dependency graph")
        return result


class StepRunner:
    """Execute a StepRegistry, persisting per-step status for resume support."""

    def run(
        self,
        registry: StepRegistry,
        run_state: Any,  # RunState — avoid circular import
        *,
        from_step: str | None = None,
        until_step: str | None = None,
        force_restart: bool = False,
    ) -> dict[str, StepRecord]:
        """Run all registered steps in topological order.

        Parameters
        ----------
        registry:
            The StepRegistry to execute.
        run_state:
            The active RunState (provides run_id and base_dir for persistence).
        from_step:
            When set, skip any already-completed steps that appear *before*
            this step in the ordered list (unless force_restart=True).
        until_step:
            When set, stop execution after this step (inclusive).
        force_restart:
            Re-run all steps regardless of persisted status.
        """
        ordered = registry.topological_order()
        step_names = [s.name for s in ordered]

        # Locate resume boundary
        from_idx = 0
        if from_step is not None:
            if from_step not in step_names:
                raise ValueError(
                    f"from_step={from_step!r} not in registry. "
                    f"Available: {step_names}"
                )
            from_idx = step_names.index(from_step)

        until_idx = len(ordered) - 1
        if until_step is not None:
            if until_step not in step_names:
                raise ValueError(
                    f"until_step={until_step!r} not in registry. "
                    f"Available: {step_names}"
                )
            until_idx = step_names.index(until_step)

        steps_dir = self._steps_dir(run_state)
        steps_dir.mkdir(parents=True, exist_ok=True)

        records: dict[str, StepRecord] = {}

        for idx, step in enumerate(ordered):
            # Load existing record if present
            record = self._load_record(steps_dir, step.name)

            # Steps before from_idx: skip unless force_restart
            if idx < from_idx and not force_restart:
                if record and record.status == StepStatus.COMPLETED:
                    records[step.name] = record
                    continue
                # Mark as skipped and continue
                record = StepRecord(step_name=step.name, status=StepStatus.SKIPPED)
                self._save_record(steps_dir, record)
                records[step.name] = record
                continue

            # Steps beyond until_idx: skip
            if idx > until_idx:
                record = StepRecord(step_name=step.name, status=StepStatus.SKIPPED)
                self._save_record(steps_dir, record)
                records[step.name] = record
                continue

            # Already completed and not force_restart: skip
            if (
                not force_restart
                and record is not None
                and record.status == StepStatus.COMPLETED
                and idx < from_idx
            ):
                records[step.name] = record
                continue

            # Execute
            record = StepRecord(
                step_name=step.name,
                status=StepStatus.RUNNING,
                started_at=datetime.now(timezone.utc).isoformat(),
            )
            self._save_record(steps_dir, record)

            t0 = time.monotonic()
            try:
                result = step.func(run_state)
                elapsed_ms = int((time.monotonic() - t0) * 1000)
                summary = ""
                if result is not None:
                    try:
                        summary = str(result)[:200]
                    except Exception:
                        summary = type(result).__name__
                record = StepRecord(
                    step_name=step.name,
                    status=StepStatus.COMPLETED,
                    started_at=record.started_at,
                    finished_at=datetime.now(timezone.utc).isoformat(),
                    duration_ms=elapsed_ms,
                    output_summary=summary,
                )
            except Exception as exc:
                elapsed_ms = int((time.monotonic() - t0) * 1000)
                record = StepRecord(
                    step_name=step.name,
                    status=StepStatus.FAILED,
                    started_at=record.started_at,
                    finished_at=datetime.now(timezone.utc).isoformat(),
                    duration_ms=elapsed_ms,
                    error_type=type(exc).__name__,
                    output_summary=str(exc)[:200],
                )
                self._save_record(steps_dir, record)
                records[step.name] = record
                raise

            self._save_record(steps_dir, record)
            records[step.name] = record

        return records

    # ------------------------------------------------------------------
    # Persistence helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _steps_dir(run_state: Any) -> Path:
        """Derive the steps persistence directory from a RunState object."""
        base = getattr(run_state, "base_dir", None) or Path(".dev-factory")
        run_id = getattr(run_state, "run_id", "unknown")
        # Handle both RunState (has .base_dir) and plain Path
        if isinstance(base, str):
            base = Path(base)
        return Path(base) / "runs" / str(run_id) / "steps"

    @staticmethod
    def _record_path(steps_dir: Path, step_name: str) -> Path:
        return steps_dir / f"{step_name}.json"

    def _load_record(self, steps_dir: Path, step_name: str) -> StepRecord | None:
        p = self._record_path(steps_dir, step_name)
        if not p.exists():
            return None
        try:
            return StepRecord.model_validate_json(p.read_text())
        except Exception:
            return None

    def _save_record(self, steps_dir: Path, record: StepRecord) -> None:
        p = self._record_path(steps_dir, record.step_name)
        p.write_text(record.model_dump_json(indent=2))
