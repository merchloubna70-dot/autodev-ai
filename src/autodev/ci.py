"""CI integration helpers for ``autodev-x ci-run``.

Detects well-known CI environments via environment variables and runs
``deliver-project`` with sensible defaults.  When executed outside a
recognised CI environment the command prints a helpful message and exits 1.

Supported CI systems
---------------------
- GitHub Actions  — ``GITHUB_ACTIONS=true``
- GitLab CI        — ``GITLAB_CI=true``
- Drone CI         — ``DRONE=true``
"""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

# ---------------------------------------------------------------------------
# CI detection
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CIEnvironment:
    """Metadata about the detected CI system."""
    name: str
    summary_env: str | None  # env var pointing to a step-summary file (if any)


def detect_ci() -> CIEnvironment | None:
    """Return a :class:`CIEnvironment` when running inside a known CI system.

    Returns ``None`` when no recognised CI environment is detected.
    """
    if os.environ.get("GITHUB_ACTIONS") == "true":
        return CIEnvironment(name="github-actions", summary_env="GITHUB_STEP_SUMMARY")
    if os.environ.get("GITLAB_CI") == "true":
        return CIEnvironment(name="gitlab-ci", summary_env=None)
    if os.environ.get("DRONE") == "true":
        return CIEnvironment(name="drone", summary_env=None)
    return None


# ---------------------------------------------------------------------------
# CI defaults
# ---------------------------------------------------------------------------

def _has_api_keys() -> bool:
    """Return True if at least one executor API key is present in the environment."""
    for key in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "CODEX_API_KEY"):
        if os.environ.get(key):
            return True
    return False


# ---------------------------------------------------------------------------
# Summary writing
# ---------------------------------------------------------------------------

def write_summary(ci: CIEnvironment, run_id: str, mode: str, mock: bool) -> None:
    """Write a Markdown step summary when the CI system provides a summary file."""
    if ci.summary_env is None:
        return
    summary_path = os.environ.get(ci.summary_env)
    if not summary_path:
        return
    lines = [
        "## autodev-x ci-run summary",
        "",
        "| Field | Value |",
        "|-------|-------|",
        f"| CI system | {ci.name} |",
        f"| run_id | `{run_id}` |",
        f"| mode | {mode} |",
        f"| mock_executor | {mock} |",
        "",
    ]
    try:
        Path(summary_path).open("a", encoding="utf-8").write("\n".join(lines) + "\n")
    except OSError:
        # Non-fatal: summary writing failure must not abort the CI job.
        print(
            f"[autodev] warning: could not write to {ci.summary_env}={summary_path}",
            file=sys.stderr,
        )


# ---------------------------------------------------------------------------
# Main entry point (called from cli.py)
# ---------------------------------------------------------------------------

def run_ci(
    *,
    repo_path: str = ".",
    mode: str = "dry-run",
    allow_mock_executor: str | None = None,
) -> int:
    """Detect CI, run deliver-project with CI defaults, return exit code."""
    ci = detect_ci()
    if ci is None:
        print(
            "[autodev] ci-run: no recognised CI environment detected "
            "(expected GITHUB_ACTIONS=true, GITLAB_CI=true, or DRONE=true).\n"
            "Run 'autodev-x deliver-project' directly for local use.",
            file=sys.stderr,
        )
        return 1

    print(f"[autodev] ci-run: detected CI system: {ci.name}", file=sys.stderr)

    # Resolve mode and mock defaults
    resolved_mode = mode or "dry-run"
    if allow_mock_executor is not None:
        mock_str = allow_mock_executor
    else:
        # Prefer real execution when API keys are present; fall back to mock.
        mock_str = "false" if _has_api_keys() else "true"

    print(
        f"[autodev] ci-run: mode={resolved_mode} allow_mock_executor={mock_str}",
        file=sys.stderr,
    )

    # Lazy import to avoid circular dependency at module level.
    from .flows.project_delivery_flow import ProjectDeliveryFlow, ProjectDeliveryInput
    from .schemas import PipelineMode

    pmode = PipelineMode.APPLY if resolved_mode == "apply" else PipelineMode.DRY_RUN
    allow_mock_bool = mock_str.lower() in ("true", "1", "yes")

    try:
        flow = ProjectDeliveryFlow()
        run = flow.run(ProjectDeliveryInput(
            repo_path=repo_path,
            mode=pmode,
            allow_mock=allow_mock_bool,
        ))
    except Exception as exc:  # noqa: BLE001
        print(f"[autodev] ci-run: deliver-project failed: {exc}", file=sys.stderr)
        return 2

    run_id = run.run_id
    mock_used = run.state.mock_execution_used or False

    print(
        f"[autodev] ci-run: completed run_id={run_id} mode={resolved_mode} mock={mock_used}",
        file=sys.stderr,
    )

    write_summary(ci, run_id=run_id, mode=resolved_mode, mock=mock_used)
    return 0
