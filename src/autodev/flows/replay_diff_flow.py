"""ReplayDiffFlow — structured diff between two pipeline run artifact trees.

Compares per-stage artifacts (JSON files) between run-id-A and run-id-B and
emits a ``ReplayDiff`` result with:

- Per-stage JSON-Patch-style ``{op, path, a, b}`` diffs.
- Executor-choice changes (highlighted separately).
- Token / cost delta (when ``cost.json`` is present in both runs via
  ``execution/router_metrics.json`` which carries ``total_estimated_cost_cents``).
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any  # noqa: UP035

# ---------------------------------------------------------------------------
# Output schema (dataclasses, not Pydantic, to keep this file self-contained)
# ---------------------------------------------------------------------------


@dataclass
class JsonPatchOp:
    """Single JSON-Patch-style diff entry."""

    op: str           # "add" | "remove" | "replace"
    path: str         # JSON Pointer (RFC 6901) style path
    a: Any = None     # value in run-A (None for "add")
    b: Any = None     # value in run-B (None for "remove")


@dataclass
class StageDiff:
    """Diff for one stage / artifact file."""

    stage: str                        # e.g. "product", "planning"
    artifact: str                     # relative path within run root
    ops: list[JsonPatchOp] = field(default_factory=list)


@dataclass
class ExecutorChangeDiff:
    """Records a change in executor choice between the two runs."""

    task_id: str
    executor_a: str
    executor_b: str


@dataclass
class CostDiff:
    """Token / cost comparison (present only when both runs have metrics)."""

    cost_cents_a: float
    cost_cents_b: float
    delta_cents: float   # b - a


@dataclass
class ReplayDiff:
    """Top-level diff result returned by ``ReplayDiffFlow.diff()``."""

    run_id_a: str
    run_id_b: str
    stage_diffs: list[StageDiff] = field(default_factory=list)
    executor_changes: list[ExecutorChangeDiff] = field(default_factory=list)
    cost_diff: CostDiff | None = None
    is_empty: bool = False           # True when run-A == run-B for all stages

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a plain dict (JSON-safe)."""
        return {
            "run_id_a": self.run_id_a,
            "run_id_b": self.run_id_b,
            "is_empty": self.is_empty,
            "stage_diffs": [
                {
                    "stage": sd.stage,
                    "artifact": sd.artifact,
                    "ops": [
                        {"op": op.op, "path": op.path, "a": op.a, "b": op.b}
                        for op in sd.ops
                    ],
                }
                for sd in self.stage_diffs
            ],
            "executor_changes": [
                {
                    "task_id": ec.task_id,
                    "executor_a": ec.executor_a,
                    "executor_b": ec.executor_b,
                }
                for ec in self.executor_changes
            ],
            "cost_diff": (
                {
                    "cost_cents_a": self.cost_diff.cost_cents_a,
                    "cost_cents_b": self.cost_diff.cost_cents_b,
                    "delta_cents": self.cost_diff.delta_cents,
                }
                if self.cost_diff
                else None
            ),
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Stage subdirectories to compare, in pipeline order.
_STAGE_SUBDIRS = [
    "input",
    "product",
    "architecture",
    "planning",
    "execution",
    "quality",
    "verification",
    "delivery",
]

# JSON files that carry executor routing information.
_EXECUTOR_ARTIFACTS = {
    "execution/crew_assembly.json",
    "execution/router_metrics.json",
}


def _load_json_safe(path: Path) -> Any:
    """Load JSON from *path*; return None on any error."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _flatten(obj: Any, prefix: str = "") -> dict[str, Any]:
    """Recursively flatten a JSON value to a dict of JSON-Pointer paths."""
    result: dict[str, Any] = {}
    if isinstance(obj, dict):
        for k, v in obj.items():
            child = f"{prefix}/{k}"
            result.update(_flatten(v, child))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            child = f"{prefix}/{i}"
            result.update(_flatten(v, child))
    else:
        result[prefix] = obj
    return result


def _diff_json(a_data: Any, b_data: Any) -> list[JsonPatchOp]:
    """Produce JSON-Patch-style ops for the diff between *a_data* and *b_data*."""
    if a_data is None and b_data is None:
        return []

    if a_data is None:
        # Entire file is new in B
        return [JsonPatchOp(op="add", path="", a=None, b=b_data)]

    if b_data is None:
        # Entire file removed from B
        return [JsonPatchOp(op="remove", path="", a=a_data, b=None)]

    flat_a = _flatten(a_data)
    flat_b = _flatten(b_data)
    all_keys = set(flat_a) | set(flat_b)
    ops: list[JsonPatchOp] = []

    for key in sorted(all_keys):
        in_a = key in flat_a
        in_b = key in flat_b
        if in_a and not in_b:
            ops.append(JsonPatchOp(op="remove", path=key, a=flat_a[key], b=None))
        elif not in_a and in_b:
            ops.append(JsonPatchOp(op="add", path=key, a=None, b=flat_b[key]))
        elif flat_a[key] != flat_b[key]:
            ops.append(JsonPatchOp(op="replace", path=key, a=flat_a[key], b=flat_b[key]))

    return ops


def _load_cost(run_root: Path) -> float | None:
    """Extract total_estimated_cost_cents from router_metrics.json if present."""
    metrics_path = run_root / "execution" / "router_metrics.json"
    data = _load_json_safe(metrics_path)
    if isinstance(data, dict):
        val = data.get("total_estimated_cost_cents")
        if val is not None:
            try:
                return float(val)
            except (TypeError, ValueError):
                pass
    return None


def _extract_executor_choices(run_root: Path) -> dict[str, str]:
    """Extract task_id → executor_name from execution log or crew_assembly."""
    choices: dict[str, str] = {}

    # Try execution_calls.jsonl (each line: {"task_id": ..., "executor": ...})
    calls_log = run_root / "execution" / "execution_calls.jsonl"
    if calls_log.exists():
        try:
            for line in calls_log.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                entry = json.loads(line)
                tid = entry.get("task_id") or entry.get("id")
                exe = entry.get("executor") or entry.get("backend")
                if tid and exe:
                    choices[str(tid)] = str(exe)
        except Exception:
            pass

    return choices


# ---------------------------------------------------------------------------
# ReplayDiffFlow
# ---------------------------------------------------------------------------


class ReplayDiffFlow:
    """Compare two pipeline runs and emit a structured ``ReplayDiff``."""

    def __init__(self, state_dir: str = ".dev-factory") -> None:
        self._state_dir = state_dir

    def diff(
        self,
        run_id_a: str,
        run_id_b: str,
        repo_path: str = ".",
    ) -> ReplayDiff:
        """Diff the artifact trees of *run_id_a* and *run_id_b*.

        Parameters
        ----------
        run_id_a, run_id_b:
            The two run IDs to compare.  Both must exist on disk.
        repo_path:
            Repository root; runs are looked up under
            ``<repo_path>/<state_dir>/runs/``.

        Raises
        ------
        FileNotFoundError
            If either run directory does not exist.
        ValueError
            If *run_id_a* == *run_id_b* and we detect no differences.
        """
        root = Path(repo_path)
        runs_dir = root / self._state_dir / "runs"

        dir_a = runs_dir / run_id_a
        dir_b = runs_dir / run_id_b

        if not dir_a.exists():
            raise FileNotFoundError(f"Run not found: {run_id_a} (looked in {dir_a})")
        if not dir_b.exists():
            raise FileNotFoundError(f"Run not found: {run_id_b} (looked in {dir_b})")

        stage_diffs: list[StageDiff] = []

        # ----------------------------------------------------------------
        # Per-stage JSON diffs
        # ----------------------------------------------------------------
        for subdir in _STAGE_SUBDIRS:
            sub_a = dir_a / subdir
            sub_b = dir_b / subdir

            # Collect all JSON files from both sides
            files_a: set[str] = set()
            files_b: set[str] = set()
            if sub_a.exists():
                files_a = {str(f.relative_to(dir_a)) for f in sub_a.rglob("*.json")}
            if sub_b.exists():
                files_b = {str(f.relative_to(dir_b)) for f in sub_b.rglob("*.json")}

            all_artifacts = sorted(files_a | files_b)
            for artifact in all_artifacts:
                data_a = _load_json_safe(dir_a / artifact)
                data_b = _load_json_safe(dir_b / artifact)
                ops = _diff_json(data_a, data_b)
                if ops:
                    stage_diffs.append(StageDiff(stage=subdir, artifact=artifact, ops=ops))

        # ----------------------------------------------------------------
        # Executor-choice diffs
        # ----------------------------------------------------------------
        executor_changes: list[ExecutorChangeDiff] = []
        choices_a = _extract_executor_choices(dir_a)
        choices_b = _extract_executor_choices(dir_b)
        all_task_ids = set(choices_a) | set(choices_b)
        for tid in sorted(all_task_ids):
            exe_a = choices_a.get(tid, "(none)")
            exe_b = choices_b.get(tid, "(none)")
            if exe_a != exe_b:
                executor_changes.append(ExecutorChangeDiff(
                    task_id=tid,
                    executor_a=exe_a,
                    executor_b=exe_b,
                ))

        # ----------------------------------------------------------------
        # Cost diff
        # ----------------------------------------------------------------
        cost_diff: CostDiff | None = None
        cost_a = _load_cost(dir_a)
        cost_b = _load_cost(dir_b)
        if cost_a is not None and cost_b is not None:
            cost_diff = CostDiff(
                cost_cents_a=cost_a,
                cost_cents_b=cost_b,
                delta_cents=round(cost_b - cost_a, 6),
            )

        is_empty = (
            not stage_diffs
            and not executor_changes
            and (cost_diff is None or cost_diff.delta_cents == 0.0)
        )

        return ReplayDiff(
            run_id_a=run_id_a,
            run_id_b=run_id_b,
            stage_diffs=stage_diffs,
            executor_changes=executor_changes,
            cost_diff=cost_diff,
            is_empty=is_empty,
        )
