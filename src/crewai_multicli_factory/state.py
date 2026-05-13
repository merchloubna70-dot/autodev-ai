"""Run state persistence under .dev-factory/runs/{run_id}/."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .schemas import (
    ExecutionBackend,
    ExecutionResult,
    PipelineMode,
    PipelineRunState,
)
from .utils.fs import ensure_dir, write_text
from .utils.json_io import append_jsonl, read_json, write_json
from .utils.slug import new_run_id


class RunState:
    """Wrapper that owns disk layout for a pipeline run."""

    SUBDIRS = (
        "input",
        "product",
        "architecture",
        "planning",
        "execution",
        "quality",
        "verification",
        "delivery",
    )

    def __init__(self, repo_path: str, state_dir: str = ".dev-factory", run_id: str | None = None):
        self.repo_path = str(Path(repo_path).resolve())
        self.run_id = run_id or new_run_id()
        self.root = Path(self.repo_path) / state_dir / "runs" / self.run_id
        ensure_dir(self.root)
        for d in self.SUBDIRS:
            ensure_dir(self.root / d)
        self.state = PipelineRunState(run_id=self.run_id, repo_path=self.repo_path)

    # ------------------------------------------------------------------
    # Disk paths
    # ------------------------------------------------------------------

    def path(self, *parts: str) -> Path:
        return self.root.joinpath(*parts)

    @property
    def state_file(self) -> Path:
        return self.root / "run_state.json"

    @property
    def execution_calls_log(self) -> Path:
        return self.root / "execution" / "execution_calls.jsonl"

    @property
    def codex_calls_log(self) -> Path:
        return self.root / "execution" / "codex_calls.jsonl"

    @property
    def claude_calls_log(self) -> Path:
        return self.root / "execution" / "claude_code_calls.jsonl"

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save(self) -> Path:
        return write_json(self.state_file, self.state)

    def save_text(self, rel: str, content: str) -> Path:
        return write_text(self.root / rel, content)

    def save_json(self, rel: str, obj: Any) -> Path:
        return write_json(self.root / rel, obj)

    def append_execution_call(self, result: ExecutionResult) -> None:
        append_jsonl(self.execution_calls_log, result)
        if result.backend == ExecutionBackend.CODEX or result.backend == ExecutionBackend.MOCK_CODEX:
            append_jsonl(self.codex_calls_log, result)
        elif result.backend == ExecutionBackend.CLAUDE_CODE or result.backend == ExecutionBackend.MOCK_CLAUDE:
            append_jsonl(self.claude_calls_log, result)
        self.state.mark_backend(result.backend)

    def finish(self) -> None:
        self.state.finished_at = datetime.now(timezone.utc).isoformat()
        self.save()

    # ------------------------------------------------------------------
    # Replay
    # ------------------------------------------------------------------

    @classmethod
    def load(cls, repo_path: str, run_id: str, state_dir: str = ".dev-factory") -> "RunState":
        rs = cls.__new__(cls)
        rs.repo_path = str(Path(repo_path).resolve())
        rs.run_id = run_id
        rs.root = Path(rs.repo_path) / state_dir / "runs" / run_id
        if not rs.root.exists():
            raise FileNotFoundError(f"run not found: {rs.root}")
        rs.state = PipelineRunState.model_validate(read_json(rs.root / "run_state.json"))
        return rs

    @classmethod
    def latest(cls, repo_path: str, state_dir: str = ".dev-factory") -> "RunState | None":
        runs_root = Path(repo_path) / state_dir / "runs"
        if not runs_root.exists():
            return None
        candidates = sorted(runs_root.iterdir(), key=lambda p: p.name)
        if not candidates:
            return None
        return cls.load(repo_path, candidates[-1].name, state_dir=state_dir)


def init_run(repo_path: str, mode: PipelineMode, flow: str, languages: list[str]) -> RunState:
    rs = RunState(repo_path=repo_path)
    rs.state.mode = mode
    rs.state.flow = flow
    rs.state.languages = [_lang(x) for x in languages]
    rs.save()
    return rs


def _lang(name: str):
    from .schemas import Language

    try:
        return Language(name.lower())
    except Exception:
        return Language.UNKNOWN
