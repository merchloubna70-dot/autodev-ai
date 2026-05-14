"""HTML export helpers for autodev-x dashboard and roundtable commands.

These are pure-Python, Textual-free utilities that walk artifact trees and
render self-contained HTML files via Jinja2 templates.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .loaders import RunRecord, load_runs

# ---------------------------------------------------------------------------
# Template environment
# ---------------------------------------------------------------------------

_TEMPLATES_DIR = Path(__file__).parent.parent / "templates" / "html"


def _env() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(_TEMPLATES_DIR)),
        autoescape=select_autoescape(["html", "j2"]),
        keep_trailing_newline=True,
    )


# ---------------------------------------------------------------------------
# Dashboard export
# ---------------------------------------------------------------------------

_STAGE_SUBDIRS: list[str] = [
    "input",
    "product",
    "architecture",
    "planning",
    "execution",
    "quality",
    "verification",
    "delivery",
]

_MAX_FILE_BYTES = 128 * 1024  # 128 KB cap per artifact to keep HTML manageable


@dataclass
class ArtifactFile:
    relative_path: str
    content: str
    language: str = "json"


@dataclass
class StageSection:
    name: str
    files: list[ArtifactFile] = field(default_factory=list)


@dataclass
class RoutingRow:
    task_id: str
    milestone_id: str
    executor: str
    success: bool | None


def _guess_language(path: Path) -> str:
    suffix = path.suffix.lower()
    return {
        ".json": "json",
        ".md": "markdown",
        ".py": "python",
        ".rs": "rust",
        ".ts": "typescript",
        ".js": "javascript",
        ".yaml": "yaml",
        ".yml": "yaml",
        ".toml": "toml",
        ".sh": "bash",
        ".txt": "text",
    }.get(suffix, "json")


def _read_artifact(path: Path, run_dir: Path) -> ArtifactFile:
    """Read a file safely, capping large files with a truncation notice."""
    try:
        raw = path.read_bytes()
        if len(raw) > _MAX_FILE_BYTES:
            content = raw[:_MAX_FILE_BYTES].decode("utf-8", errors="replace")
            content += f"\n\n[… truncated — file is {len(raw):,} bytes …]"
        else:
            content = raw.decode("utf-8", errors="replace")
    except Exception as exc:
        content = f"[error reading file: {exc}]"
    try:
        rel = str(path.relative_to(run_dir))
    except ValueError:
        rel = path.name
    return ArtifactFile(
        relative_path=rel,
        content=content,
        language=_guess_language(path),
    )


def _load_stages(run_dir: Path) -> list[StageSection]:
    stages: list[StageSection] = []
    for stage_name in _STAGE_SUBDIRS:
        stage_dir = run_dir / stage_name
        section = StageSection(name=stage_name)
        if stage_dir.exists() and stage_dir.is_dir():
            for fpath in sorted(stage_dir.rglob("*")):
                if fpath.is_file():
                    section.files.append(_read_artifact(fpath, run_dir))
        stages.append(section)
    return stages


def _load_routing_rows(run_dir: Path) -> list[RoutingRow]:
    """Extract task-to-executor routing from run_state.json."""
    state_file = run_dir / "run_state.json"
    if not state_file.exists():
        return []
    try:
        state: dict[str, Any] = json.loads(state_file.read_text(encoding="utf-8"))
    except Exception:
        return []

    rows: list[RoutingRow] = []
    for result in state.get("implementation_results", []):
        if not isinstance(result, dict):
            continue
        rows.append(RoutingRow(
            task_id=result.get("task_id", "?"),
            milestone_id=result.get("milestone_id", ""),
            executor=result.get("executor", "auto"),
            success=result.get("success"),
        ))
    return rows


def _latest_run_dir(root: Path) -> Path | None:
    """Return the most-recently-modified run directory under root/runs/."""
    runs_dir = root / "runs"
    if not runs_dir.exists():
        return None
    candidates = [d for d in runs_dir.iterdir() if d.is_dir() and (d / "run_state.json").exists()]
    if not candidates:
        return None
    return max(candidates, key=lambda d: d.stat().st_mtime)


def export_dashboard_html(
    root: str | Path,
    output: str | Path,
) -> Path:
    """Walk the latest run under *root* and emit a self-contained HTML file.

    Parameters
    ----------
    root:
        Path to the ``.dev-factory`` directory (or equivalent).
    output:
        Destination path for the generated ``.html`` file.

    Returns
    -------
    Path
        Absolute path to the written HTML file.

    Raises
    ------
    FileNotFoundError
        If *root* does not exist or contains no runs.
    """
    root = Path(root)
    if not root.exists():
        raise FileNotFoundError(f"dev-factory root not found: {root}")

    run_dir = _latest_run_dir(root)
    if run_dir is None:
        # No runs yet — render an empty-state page
        run = RunRecord(run_id="(no runs)", run_dir=root)
        stages: list[StageSection] = []
        routing: list[RoutingRow] = []
    else:
        runs = load_runs(root)
        # Match by directory name
        matching = [r for r in runs if r.run_dir == run_dir]
        run = matching[0] if matching else RunRecord(run_id=run_dir.name, run_dir=run_dir)
        stages = _load_stages(run_dir)
        routing = _load_routing_rows(run_dir)

    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    template = _env().get_template("dashboard.html.j2")
    html = template.render(
        run=run,
        stages=stages,
        routing_rows=routing,
        generated_at=generated_at,
    )

    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(html, encoding="utf-8")
    return output.resolve()


# ---------------------------------------------------------------------------
# Roundtable export
# ---------------------------------------------------------------------------

@dataclass
class AgentAnalysis:
    agent_name: str
    text: str


def export_roundtable_html(
    *,
    topic: str,
    participants: list[str],
    agent_analyses: list[AgentAnalysis],
    consensus_text: str,
    conversation_id: str = "",
    output: str | Path,
) -> Path:
    """Render a roundtable conversation as a self-contained HTML file.

    Parameters
    ----------
    topic:
        The discussion topic.
    participants:
        List of participating agent names.
    agent_analyses:
        Per-agent analysis objects (name + text).
    consensus_text:
        The synthesizer's merged consensus text.
    conversation_id:
        Optional conversation UUID for display.
    output:
        Destination path for the HTML file.

    Returns
    -------
    Path
        Absolute path to the written HTML file.
    """
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    template = _env().get_template("roundtable.html.j2")
    html = template.render(
        topic=topic,
        participants=participants,
        agent_analyses=agent_analyses,
        consensus_text=consensus_text,
        conversation_id=conversation_id,
        generated_at=generated_at,
    )

    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(html, encoding="utf-8")
    return output.resolve()
