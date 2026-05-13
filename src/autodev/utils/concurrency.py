"""Bounded parallel execution helpers (thread pool based)."""
from __future__ import annotations

from collections.abc import Callable, Iterable
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any


def run_parallel(
    fn: Callable[[Any], Any],
    items: Iterable[Any],
    *,
    concurrency: int = 3,
    fail_fast: bool = True,
) -> list[Any]:
    items_list = list(items)
    if concurrency <= 1 or len(items_list) <= 1:
        return [fn(it) for it in items_list]
    results: list[Any] = [None] * len(items_list)
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        future_to_idx = {pool.submit(fn, it): i for i, it in enumerate(items_list)}
        for fut in as_completed(future_to_idx):
            idx = future_to_idx[fut]
            try:
                results[idx] = fut.result()
            except Exception:
                if fail_fast:
                    raise
                results[idx] = None
    return results


def topological_batches(
    nodes: list[str], edges: list[tuple[str, str]]
) -> list[list[str]]:
    """Return waves of nodes that can run in parallel. edges = (dep, dependent)."""
    incoming: dict[str, set[str]] = {n: set() for n in nodes}
    for dep, dependent in edges:
        if dependent in incoming and dep in incoming:
            incoming[dependent].add(dep)
    batches: list[list[str]] = []
    remaining = set(nodes)
    while remaining:
        ready = sorted([n for n in remaining if not incoming[n]])
        if not ready:
            # cycle: surface remaining as a final batch
            batches.append(sorted(remaining))
            break
        batches.append(ready)
        for n in ready:
            remaining.discard(n)
            for other in list(remaining):
                incoming[other].discard(n)
    return batches


def wave_stats(waves: list[list[str]]) -> dict:
    """Return audit statistics for a list of waves.

    Returns a dict with keys:
        num_waves         - total number of waves
        max_width         - size of the widest wave
        avg_width         - average wave width (float)
        single_task_waves - number of waves that contain exactly one task
    """
    num_waves = len(waves)
    widths = [len(w) for w in waves]
    max_width = max(widths, default=0)
    avg_width = sum(widths) / num_waves if num_waves else 0.0
    single_task_waves = sum(1 for w in widths if w == 1)
    return {
        "num_waves": num_waves,
        "max_width": max_width,
        "avg_width": avg_width,
        "single_task_waves": single_task_waves,
    }
