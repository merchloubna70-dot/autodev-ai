"""File-system loaders for autodev pipeline artifacts.

Walks the --root directory (default ``.dev-factory``) and returns typed records
built from ``autodev.schemas``.  No Textual dependency — these are pure Python
and fully testable without any TUI installed.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Lightweight record types (avoid heavy schema validation in the loader layer
# so callers can handle partial / legacy on-disk JSON gracefully).
# ---------------------------------------------------------------------------


@dataclass
class RunRecord:
    run_id: str
    started_at: str = ""
    finished_at: str | None = None
    mode: str = "dry-run"
    flow: str = ""
    repo_path: str = ""
    languages: list[str] = field(default_factory=list)
    mock_execution_used: bool = False
    errors: list[str] = field(default_factory=list)
    # Summary counts derived on load
    milestone_count: int = 0
    task_count: int = 0
    # Gate summary
    gate_statuses: dict[str, str] = field(default_factory=dict)
    # Severity findings (flat list from all review reports)
    severity_findings: list[dict[str, Any]] = field(default_factory=list)
    # Path to the run directory on disk
    run_dir: Path = field(default_factory=Path)


@dataclass
class SprintRecord:
    sprint_id: str
    goal: str = ""
    started_at: str = ""
    health: str = "unknown"
    tasks_total: int = 0
    tasks_done: int = 0
    tasks_failed: int = 0
    progress_pct: float = 0.0
    what_went_well: list[str] = field(default_factory=list)
    what_went_wrong: list[str] = field(default_factory=list)
    actions: list[str] = field(default_factory=list)
    sprint_dir: Path = field(default_factory=Path)


@dataclass
class ConversationRecord:
    conversation_id: str
    task_id: str = ""
    participating_cards: list[str] = field(default_factory=list)
    message_count: int = 0
    preview: str = ""
    file_path: Path = field(default_factory=Path)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _safe_load(path: Path) -> dict[str, Any]:
    """Read a JSON file; return empty dict on any error."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _extract_severity_findings(state: dict[str, Any]) -> list[dict[str, Any]]:
    """Pull severity_findings from code_review, security_review, integration_review."""
    findings: list[dict[str, Any]] = []
    for key in ("code_review", "security_review", "integration_review"):
        report = state.get(key) or {}
        for f in report.get("severity_findings", []):
            if isinstance(f, dict):
                findings.append(f)
    return findings


def _gate_statuses(state: dict[str, Any]) -> dict[str, str]:
    """Return a {gate_name: status} dict summarising quality gate outcomes."""
    statuses: dict[str, str] = {}
    for qg in state.get("quality_gates", []):
        if not isinstance(qg, dict):
            continue
        lang = qg.get("language", "?")
        for outcome in qg.get("outcomes", []):
            if isinstance(outcome, dict):
                name = outcome.get("name", "gate")
                status = outcome.get("status", "unknown")
                statuses[f"{lang}/{name}"] = status
    # Also capture release_check decision
    rc = state.get("release_check") or {}
    if rc.get("decision"):
        statuses["release"] = rc["decision"]
    return statuses


# ---------------------------------------------------------------------------
# Public loaders
# ---------------------------------------------------------------------------


def load_runs(root: Path) -> list[RunRecord]:
    """Walk ``root/runs/*/run_state.json`` and return sorted RunRecord list."""
    runs_dir = root / "runs"
    if not runs_dir.exists():
        return []

    records: list[RunRecord] = []
    for run_dir in sorted(runs_dir.iterdir()):
        state_file = run_dir / "run_state.json"
        if not state_file.exists():
            continue
        state = _safe_load(state_file)
        if not state:
            continue

        # Milestone / task counts
        mp = state.get("milestone_plan") or {}
        milestone_count = len(mp.get("milestones", []))
        task_count = len(mp.get("tasks", []))

        records.append(RunRecord(
            run_id=state.get("run_id", run_dir.name),
            started_at=state.get("started_at", ""),
            finished_at=state.get("finished_at"),
            mode=state.get("mode", "dry-run"),
            flow=state.get("flow", ""),
            repo_path=state.get("repo_path", ""),
            languages=[str(x) for x in state.get("languages", [])],
            mock_execution_used=bool(state.get("mock_execution_used", False)),
            errors=list(state.get("errors", [])),
            milestone_count=milestone_count,
            task_count=task_count,
            gate_statuses=_gate_statuses(state),
            severity_findings=_extract_severity_findings(state),
            run_dir=run_dir,
        ))

    return records


def load_sprints(root: Path) -> list[SprintRecord]:
    """Walk ``root/../.autodev/sprints/`` and return SprintRecord list.

    The sprint directory is adjacent to ``.dev-factory``, rooted one level up.
    Falls back to checking ``root / "sprints"`` as well.
    """
    candidates = [
        root.parent / ".autodev" / "sprints",
        root / "sprints",
    ]
    sprints_dir: Path | None = None
    for c in candidates:
        if c.exists():
            sprints_dir = c
            break
    if sprints_dir is None:
        return []

    records: list[SprintRecord] = []
    for sprint_dir in sorted(sprints_dir.iterdir()):
        if not sprint_dir.is_dir():
            continue
        state = _safe_load(sprint_dir / "state.json")
        retro = _safe_load(sprint_dir / "retrospective.json")

        # Compute basic health from tasks
        tasks = state.get("tasks", [])
        done = sum(1 for t in tasks if isinstance(t, dict) and t.get("status") in ("completed", "done"))
        failed = sum(1 for t in tasks if isinstance(t, dict) and t.get("status") == "failed")
        total = len(tasks)
        pct = (done / total * 100.0) if total else 0.0
        health = "complete" if (total and done == total) else ("blocked" if failed else "on-track")

        records.append(SprintRecord(
            sprint_id=state.get("sprint_id", sprint_dir.name),
            goal=state.get("goal", ""),
            started_at=state.get("started_at", ""),
            health=health,
            tasks_total=total,
            tasks_done=done,
            tasks_failed=failed,
            progress_pct=pct,
            what_went_well=retro.get("what_went_well", []),
            what_went_wrong=retro.get("what_went_wrong", []),
            actions=retro.get("actions_for_next_sprint", []),
            sprint_dir=sprint_dir,
        ))

    return records


def load_conversations(root: Path) -> list[ConversationRecord]:
    """Walk ``root/roundtables/*.json`` and return ConversationRecord list."""
    roundtables_dir = root / "roundtables"
    if not roundtables_dir.exists():
        return []

    records: list[ConversationRecord] = []
    for p in sorted(roundtables_dir.glob("*.json")):
        data = _safe_load(p)
        if not data:
            continue
        conv = data.get("conversation") or data  # handle both wrapped and bare formats
        if not isinstance(conv, dict) or not conv:
            continue
        # Require at least a conversation_id or messages to treat as valid
        if not (conv.get("conversation_id") or conv.get("messages")):
            continue

        messages = conv.get("messages", [])
        # Extract preview from first text part of first message
        preview = ""
        for msg in messages[:1]:
            for part in (msg.get("parts") or []):
                if isinstance(part, dict) and part.get("kind") == "text" and part.get("text"):
                    preview = (part["text"] or "")[:120]
                    break
            if preview:
                break

        records.append(ConversationRecord(
            conversation_id=conv.get("conversation_id", p.stem),
            task_id=conv.get("task_id", ""),
            participating_cards=list(conv.get("participating_cards", [])),
            message_count=len(messages),
            preview=preview,
            file_path=p,
        ))

    return records
