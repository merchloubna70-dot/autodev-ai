"""MultiRepoFlow — run deliver-project semantics across multiple repos in one invocation.

Reads a YAML config describing a group of repos and runs ProjectDeliveryFlow
against each one, aggregating results into a shared artifact tree:

    .dev-factory/multi-runs/<group_id>/
        summary.json
        <repo-slug>/
            run_id, status, errors, ...

Repos are processed sequentially; each runs its own isolated ProjectDeliveryFlow.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..config import FactoryConfig
from ..flows.project_delivery_flow import ProjectDeliveryFlow, ProjectDeliveryInput
from ..schemas import ExecutionBackend, Language, PipelineMode, Scale
from ..utils.slug import new_run_id

# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass
class RepoSpec:
    """Specification for a single repo within a multi-repo group."""

    path: str
    brief_file: str | None = None
    brief_text: str | None = None
    languages: list[Language] = field(default_factory=lambda: [Language.PYTHON])
    project_name: str | None = None


@dataclass
class MultiRepoConfig:
    """Parsed representation of the YAML config file."""

    group_name: str
    repos: list[RepoSpec]


@dataclass
class RepoRunResult:
    """Per-repo outcome recorded in the aggregate artifact tree."""

    repo_slug: str
    repo_path: str
    run_id: str | None
    status: str  # "success" | "failed" | "error"
    errors: list[str]
    artifact_dir: str


@dataclass
class MultiRunSummary:
    """Top-level summary written to summary.json."""

    group_id: str
    group_name: str
    started_at: str
    finished_at: str
    total: int
    succeeded: int
    failed: int
    results: list[dict[str, Any]]
    artifact_root: str


# ---------------------------------------------------------------------------
# YAML parsing helpers
# ---------------------------------------------------------------------------


def _parse_languages(raw: list[str] | str | None) -> list[Language]:
    """Convert a list of raw language strings to Language enum values."""
    if raw is None:
        return [Language.PYTHON]
    if isinstance(raw, str):
        raw = [raw]
    out: list[Language] = []
    for token in raw:
        token = token.strip().lower()
        if not token:
            continue
        try:
            out.append(Language(token))
        except ValueError:
            out.append(Language.UNKNOWN)
    return out or [Language.PYTHON]


def _slugify(text: str) -> str:
    """Convert a string to a safe directory name."""
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug or "repo"


def parse_multi_repo_config(config_path: str | Path) -> MultiRepoConfig:
    """Parse a YAML multi-repo config file and return a MultiRepoConfig.

    Raises ValueError for missing required fields.
    Raises FileNotFoundError if the config file does not exist.
    """
    try:
        import yaml  # type: ignore[import-untyped]
    except ImportError as exc:
        raise ImportError(
            "PyYAML is required for deliver-multi; install it with: pip install pyyaml"
        ) from exc

    p = Path(config_path)
    if not p.exists():
        raise FileNotFoundError(f"Multi-repo config not found: {p}")

    raw = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    group_name = raw.get("group_name") or "unnamed-group"

    raw_repos = raw.get("repos")
    if not raw_repos or not isinstance(raw_repos, list):
        raise ValueError(
            f"Config {p} must have a 'repos' list with at least one entry."
        )

    config_dir = p.parent
    specs: list[RepoSpec] = []
    for idx, entry in enumerate(raw_repos):
        if not isinstance(entry, dict):
            raise ValueError(f"repos[{idx}] must be a mapping, got {type(entry).__name__}")

        repo_path_raw = entry.get("path")
        if not repo_path_raw:
            raise ValueError(f"repos[{idx}] is missing required 'path' field")

        # Resolve relative to config file's directory
        repo_path = str((config_dir / repo_path_raw).resolve())

        brief_file: str | None = None
        brief_text: str | None = None
        if "brief_file" in entry:
            bf = (config_dir / entry["brief_file"]).resolve()
            if not bf.exists():
                raise FileNotFoundError(
                    f"repos[{idx}] brief_file not found: {bf}"
                )
            brief_file = str(bf)
            brief_text = bf.read_text(encoding="utf-8")

        languages = _parse_languages(entry.get("languages"))
        project_name = entry.get("project_name") or None

        specs.append(RepoSpec(
            path=repo_path,
            brief_file=brief_file,
            brief_text=brief_text,
            languages=languages,
            project_name=project_name,
        ))

    return MultiRepoConfig(group_name=group_name, repos=specs)


# ---------------------------------------------------------------------------
# Main flow
# ---------------------------------------------------------------------------


class MultiRepoFlow:
    """Run ProjectDeliveryFlow across multiple repos and aggregate results.

    Parameters
    ----------
    config:
        Shared FactoryConfig applied to every per-repo run.
    mode:
        Pipeline mode (dry-run or apply) applied to every repo.
    scale:
        Optional Scale hint forwarded to each per-repo run.
    output_base:
        Root directory for multi-run artifacts; defaults to
        ``.dev-factory/multi-runs`` relative to cwd.
    """

    def __init__(
        self,
        config: FactoryConfig | None = None,
        mode: PipelineMode = PipelineMode.DRY_RUN,
        scale: Scale | None = None,
        output_base: str | Path | None = None,
    ) -> None:
        self.config = config or FactoryConfig()
        self.mode = mode
        self.scale = scale
        self._output_base = Path(output_base) if output_base else Path(".dev-factory") / "multi-runs"

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def run(self, multi_config: MultiRepoConfig) -> MultiRunSummary:
        """Execute deliver-project for each repo in *multi_config*.

        Returns a MultiRunSummary with per-repo outcomes and writes
        artifact directories under ``output_base/<group_id>/``.
        """
        group_id = new_run_id()
        group_root = self._output_base / group_id
        group_root.mkdir(parents=True, exist_ok=True)

        started_at = datetime.now(tz=timezone.utc).isoformat()
        results: list[RepoRunResult] = []

        for spec in multi_config.repos:
            result = self._run_single(spec, group_root)
            results.append(result)

        finished_at = datetime.now(tz=timezone.utc).isoformat()
        succeeded = sum(1 for r in results if r.status == "success")
        failed = len(results) - succeeded

        summary = MultiRunSummary(
            group_id=group_id,
            group_name=multi_config.group_name,
            started_at=started_at,
            finished_at=finished_at,
            total=len(results),
            succeeded=succeeded,
            failed=failed,
            results=[
                {
                    "repo_slug": r.repo_slug,
                    "repo_path": r.repo_path,
                    "run_id": r.run_id,
                    "status": r.status,
                    "errors": r.errors,
                    "artifact_dir": r.artifact_dir,
                }
                for r in results
            ],
            artifact_root=str(group_root),
        )

        # Write aggregate summary
        (group_root / "summary.json").write_text(
            json.dumps(
                {
                    "group_id": summary.group_id,
                    "group_name": summary.group_name,
                    "started_at": summary.started_at,
                    "finished_at": summary.finished_at,
                    "total": summary.total,
                    "succeeded": summary.succeeded,
                    "failed": summary.failed,
                    "results": summary.results,
                    "artifact_root": summary.artifact_root,
                },
                indent=2,
            ),
            encoding="utf-8",
        )

        return summary

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _run_single(self, spec: RepoSpec, group_root: Path) -> RepoRunResult:
        """Run ProjectDeliveryFlow for one repo and record the result."""
        slug = _slugify(
            spec.project_name or Path(spec.path).name or "repo"
        )
        repo_artifact_dir = group_root / slug
        repo_artifact_dir.mkdir(parents=True, exist_ok=True)

        try:
            # Ensure the repo path exists
            repo_path = Path(spec.path)
            if not repo_path.exists():
                raise FileNotFoundError(
                    f"Repo path does not exist: {spec.path}"
                )

            flow = ProjectDeliveryFlow(self.config)
            run = flow.run(ProjectDeliveryInput(
                repo_path=spec.path,
                brief_text=spec.brief_text,
                project_name=spec.project_name,
                languages=spec.languages,
                mode=self.mode,
                backend=ExecutionBackend.AUTO,
                allow_mock=self.config.allow_mock_executor,
                scale=self.scale,
            ))

            # Write per-repo manifest into group artifact dir
            manifest: dict[str, Any] = {
                "repo_slug": slug,
                "repo_path": spec.path,
                "run_id": run.run_id,
                "status": "success",
                "errors": run.state.errors,
                "run_artifact_dir": str(
                    Path(spec.path) / ".dev-factory" / "runs" / run.run_id
                ),
            }
            (repo_artifact_dir / "manifest.json").write_text(
                json.dumps(manifest, indent=2), encoding="utf-8"
            )

            return RepoRunResult(
                repo_slug=slug,
                repo_path=spec.path,
                run_id=run.run_id,
                status="success" if not run.state.errors else "failed",
                errors=run.state.errors,
                artifact_dir=str(repo_artifact_dir),
            )

        except Exception as exc:  # noqa: BLE001
            error_msg = str(exc)
            manifest = {
                "repo_slug": slug,
                "repo_path": spec.path,
                "run_id": None,
                "status": "error",
                "errors": [error_msg],
            }
            (repo_artifact_dir / "manifest.json").write_text(
                json.dumps(manifest, indent=2), encoding="utf-8"
            )
            return RepoRunResult(
                repo_slug=slug,
                repo_path=spec.path,
                run_id=None,
                status="error",
                errors=[error_msg],
                artifact_dir=str(repo_artifact_dir),
            )
