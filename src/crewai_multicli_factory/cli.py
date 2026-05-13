"""`crewai-factory` Typer CLI entrypoint."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer

from .agents.input_classifier import InputClassifierAgent
from .agents.milestone_planner import MilestonePlannerAgent
from .agents.prd_writer import PRDWriterAgent
from .agents.product_manager import ProductManagerAgent
from .agents.repo_explorer import RepoExplorerAgent
from .agents.requirement_analyst import RequirementAnalystAgent
from .agents.system_architect import SystemArchitectAgent
from .agents.task_decomposer import TaskDecomposerAgent
from .config import FactoryConfig
from .flows.issue_pipeline_flow import IssuePipelineFlow, IssuePipelineInput
from .flows.milestone_flow import MilestoneFlow, MilestoneFlowInput
from .flows.project_delivery_flow import ProjectDeliveryFlow, ProjectDeliveryInput
from .flows.release_flow import ReleaseFlow
from .reports.reporter import Reporter
from .schemas import ExecutionBackend, Language, PipelineMode
from .state import RunState
from .utils.json_io import write_json
from .utils.fs import write_text

app = typer.Typer(help="CrewAI + Codex CLI + Claude Code CLI multi-CLI software factory")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_languages(s: str) -> list[Language]:
    out: list[Language] = []
    for token in s.split(","):
        token = token.strip().lower()
        if not token:
            continue
        try:
            out.append(Language(token))
        except ValueError:
            out.append(Language.UNKNOWN)
    return out or [Language.PYTHON]


def _parse_mode(s: str) -> PipelineMode:
    s = (s or "dry-run").lower()
    return PipelineMode.APPLY if s == "apply" else PipelineMode.DRY_RUN


def _parse_backend(s: str) -> ExecutionBackend:
    s = (s or "auto").lower().replace("-", "_")
    try:
        return ExecutionBackend(s)
    except ValueError:
        return ExecutionBackend.AUTO


def _parse_tri_bool(s: Optional[str]) -> Optional[bool]:
    """Parse a tri-state flag accepting "true"/"false"/"" or None."""
    if s is None:
        return None
    s = str(s).strip().lower()
    if s in ("true", "1", "yes", "y", "on"):
        return True
    if s in ("false", "0", "no", "n", "off"):
        return False
    return None


def _read(p: str) -> str:
    return Path(p).read_text(encoding="utf-8")


def _build_config(
    *, mode: PipelineMode, allow_mock: bool | None, fail_fast: bool, continue_and_report: bool,
    concurrency: int, codex_timeout: int, claude_timeout: int,
) -> FactoryConfig:
    cfg = FactoryConfig.from_env()
    cfg.default_mode = mode
    # default allow_mock based on mode if not set explicitly
    if allow_mock is None:
        cfg.allow_mock_executor = mode == PipelineMode.DRY_RUN
    else:
        cfg.allow_mock_executor = allow_mock
    cfg.fail_fast = fail_fast
    cfg.continue_and_report = continue_and_report
    cfg.concurrency = concurrency
    cfg.codex.timeout_seconds = codex_timeout
    cfg.claude_code.timeout_seconds = claude_timeout
    return cfg


# ---------------------------------------------------------------------------
# run-issue
# ---------------------------------------------------------------------------


@app.command("run-issue")
def run_issue(
    repo_path: str = typer.Option(".", "--repo-path"),
    issue_file: Optional[str] = typer.Option(None, "--issue-file"),
    issue_url: Optional[str] = typer.Option(None, "--issue-url"),
    languages: str = typer.Option("python", "--languages"),
    mode: str = typer.Option("dry-run", "--mode"),
    executor: str = typer.Option("auto", "--executor"),
    allow_mock_executor: Optional[str] = typer.Option(None, "--allow-mock-executor"),
    claude_timeout: int = typer.Option(900, "--claude-timeout"),
    codex_timeout: int = typer.Option(600, "--codex-timeout"),
    concurrency: int = typer.Option(3, "--concurrency"),
    fail_fast: bool = typer.Option(True, "--fail-fast/--no-fail-fast"),
    continue_and_report: bool = typer.Option(False, "--continue-and-report/--no-continue-and-report"),
    commit: bool = typer.Option(False, "--commit"),
    push: bool = typer.Option(False, "--push"),
    tag: bool = typer.Option(False, "--tag"),
) -> None:
    """Run the Issue Mode flow against an existing repo."""
    pmode = _parse_mode(mode)
    langs = _parse_languages(languages)
    backend = _parse_backend(executor)
    cfg = _build_config(
        mode=pmode, allow_mock=_parse_tri_bool(allow_mock_executor), fail_fast=fail_fast,
        continue_and_report=continue_and_report, concurrency=concurrency,
        codex_timeout=codex_timeout, claude_timeout=claude_timeout,
    )
    text = _read(issue_file) if issue_file else ""
    if not text and issue_url:
        text = f"Issue URL: {issue_url}\n(remote fetch disabled; supply --issue-file for full context)\n"
    flow = IssuePipelineFlow(cfg)
    run = flow.run(IssuePipelineInput(
        repo_path=repo_path, issue_text=text, issue_id="ISSUE-0", issue_url=issue_url,
        languages=langs, mode=pmode, backend=backend,
        allow_mock=cfg.allow_mock_executor, commit=commit, push=push, tag=tag,
    ))
    typer.echo(f"run_id={run.run_id} mode={pmode.value} mock={run.state.mock_execution_used}")


# ---------------------------------------------------------------------------
# deliver-project
# ---------------------------------------------------------------------------


@app.command("deliver-project")
def deliver_project(
    repo_path: str = typer.Option(".", "--repo-path"),
    project_brief: Optional[str] = typer.Option(None, "--project-brief"),
    prd: Optional[str] = typer.Option(None, "--prd"),
    project_name: Optional[str] = typer.Option(None, "--project-name"),
    languages: str = typer.Option("python", "--languages"),
    mode: str = typer.Option("dry-run", "--mode"),
    from_scratch: str = typer.Option("false", "--from-scratch"),
    executor: str = typer.Option("auto", "--executor"),
    allow_mock_executor: Optional[str] = typer.Option(None, "--allow-mock-executor"),
    claude_timeout: int = typer.Option(900, "--claude-timeout"),
    codex_timeout: int = typer.Option(600, "--codex-timeout"),
    concurrency: int = typer.Option(3, "--concurrency"),
    fail_fast: bool = typer.Option(True, "--fail-fast/--no-fail-fast"),
    continue_and_report: bool = typer.Option(False, "--continue-and-report/--no-continue-and-report"),
    commit: bool = typer.Option(False, "--commit"),
    push: bool = typer.Option(False, "--push"),
    tag: bool = typer.Option(False, "--tag"),
) -> None:
    """Run the Project Delivery Mode flow (brief / PRD / empty repo)."""
    pmode = _parse_mode(mode)
    langs = _parse_languages(languages)
    backend = _parse_backend(executor)
    cfg = _build_config(
        mode=pmode, allow_mock=_parse_tri_bool(allow_mock_executor), fail_fast=fail_fast,
        continue_and_report=continue_and_report, concurrency=concurrency,
        codex_timeout=codex_timeout, claude_timeout=claude_timeout,
    )
    brief_text = _read(project_brief) if project_brief else None
    prd_text = _read(prd) if prd else None
    flow = ProjectDeliveryFlow(cfg)
    run = flow.run(ProjectDeliveryInput(
        repo_path=repo_path, brief_text=brief_text, prd_text=prd_text, project_name=project_name,
        languages=langs, mode=pmode, backend=backend,
        allow_mock=cfg.allow_mock_executor, from_scratch=bool(_parse_tri_bool(from_scratch)),
        commit=commit, push=push, tag=tag,
    ))
    typer.echo(
        f"run_id={run.run_id} mode={pmode.value} mock={run.state.mock_execution_used} "
        f"release={run.state.release_check.decision.value if run.state.release_check else 'N/A'}"
    )


# ---------------------------------------------------------------------------
# Planning commands
# ---------------------------------------------------------------------------


@app.command("classify-input")
def classify_input(input_path: str = typer.Option(..., "--input")) -> None:
    text = _read(input_path)
    cls = InputClassifierAgent().classify(text=text, source_path=input_path)
    typer.echo(cls.model_dump_json(indent=2))


@app.command("create-prd")
def create_prd(
    project_brief: str = typer.Option(..., "--project-brief"),
    output: str = typer.Option(".dev-factory/prd.md", "--output"),
) -> None:
    text = _read(project_brief)
    pm = ProductManagerAgent()
    req = RequirementAnalystAgent()
    writer = PRDWriterAgent()
    brief = pm.build_brief(text)
    fr, nf, ac = req.derive(brief=brief, source_text=text)
    prd = writer.write(brief=brief, functional=fr, non_functional=nf, acceptance=ac)
    write_text(output, writer.render_markdown(prd))
    write_json(Path(output).with_suffix(".json"), prd)
    typer.echo(f"wrote {output}")


@app.command("plan-project")
def plan_project(
    repo_path: str = typer.Option(".", "--repo-path"),
    prd: str = typer.Option(..., "--prd"),
    languages: str = typer.Option("python", "--languages"),
) -> None:
    langs = _parse_languages(languages)
    scan = RepoExplorerAgent().explore(repo_path)
    text = _read(prd)
    pm = ProductManagerAgent().build_brief(text)
    fr, nf, ac = RequirementAnalystAgent().derive(brief=pm, source_text=text)
    prd_obj = PRDWriterAgent().write(brief=pm, functional=fr, non_functional=nf, acceptance=ac)
    arch = SystemArchitectAgent().design(prd=prd_obj, scan=scan, languages=langs)
    typer.echo(arch.model_dump_json(indent=2))


@app.command("plan-milestones")
def plan_milestones(
    repo_path: str = typer.Option(".", "--repo-path"),
    prd: str = typer.Option(..., "--prd"),
    max_milestones: int = typer.Option(6, "--max-milestones"),
) -> None:
    text = _read(prd)
    pm = ProductManagerAgent().build_brief(text)
    fr, nf, ac = RequirementAnalystAgent().derive(brief=pm, source_text=text)
    prd_obj = PRDWriterAgent().write(brief=pm, functional=fr, non_functional=nf, acceptance=ac)
    scan = RepoExplorerAgent().explore(repo_path)
    arch = SystemArchitectAgent().design(prd=prd_obj, scan=scan, languages=[Language.PYTHON])
    milestones = MilestonePlannerAgent().plan(architecture=arch, languages=[Language.PYTHON], max_milestones=max_milestones)
    typer.echo([m.model_dump(mode="json") for m in milestones].__repr__())


@app.command("plan-tasks")
def plan_tasks(
    repo_path: str = typer.Option(".", "--repo-path"),
    milestone_id: str = typer.Option(..., "--milestone-id"),
) -> None:
    run = RunState.latest(repo_path)
    if not run or not run.state.milestone_plan:
        typer.echo("no run with milestone_plan found")
        raise typer.Exit(code=2)
    plan = run.state.milestone_plan
    tasks = [t for t in plan.tasks if t.milestone_id == milestone_id]
    typer.echo([t.model_dump(mode="json") for t in tasks].__repr__())


# ---------------------------------------------------------------------------
# Execute / replay / continue
# ---------------------------------------------------------------------------


@app.command("execute-milestone")
def execute_milestone(
    run_id: str = typer.Option(..., "--run-id"),
    milestone_id: str = typer.Option(..., "--milestone-id"),
    repo_path: str = typer.Option(".", "--repo-path"),
    mode: str = typer.Option("dry-run", "--mode"),
    executor: str = typer.Option("auto", "--executor"),
    allow_mock_executor: Optional[str] = typer.Option(None, "--allow-mock-executor"),
    concurrency: int = typer.Option(3, "--concurrency"),
    fail_fast: bool = typer.Option(True, "--fail-fast/--no-fail-fast"),
) -> None:
    pmode = _parse_mode(mode)
    backend = _parse_backend(executor)
    cfg = _build_config(
        mode=pmode, allow_mock=_parse_tri_bool(allow_mock_executor), fail_fast=fail_fast,
        continue_and_report=False, concurrency=concurrency,
        codex_timeout=600, claude_timeout=900,
    )
    flow = MilestoneFlow(cfg)
    impl = flow.run(MilestoneFlowInput(
        run_id=run_id, milestone_id=milestone_id, repo_path=repo_path,
        mode=pmode, backend=backend, allow_mock=cfg.allow_mock_executor,
        concurrency=concurrency, fail_fast=fail_fast,
    ))
    typer.echo(f"milestone={impl.milestone_id} success={impl.success} mock={impl.mock_used} failed={impl.failed_task_ids}")


@app.command("continue-run")
def continue_run(run_id: str = typer.Option(..., "--run-id"), repo_path: str = typer.Option(".", "--repo-path")) -> None:
    run = RunState.load(repo_path, run_id)
    plan = run.state.milestone_plan
    if not plan:
        typer.echo("nothing to continue: no milestone_plan")
        raise typer.Exit(code=2)
    done = {impl.milestone_id for impl in run.state.implementation_results if impl.success}
    remaining = [m for m in plan.milestones if m.milestone_id not in done]
    typer.echo(f"remaining milestones: {[m.milestone_id for m in remaining]}")


@app.command("replay")
def replay(
    run_id: str = typer.Option(..., "--run-id"),
    repo_path: str = typer.Option(".", "--repo-path"),
    from_stage: str = typer.Option("planning", "--from-stage"),
) -> None:
    from .flows.replay_flow import ReplayFlow
    run = ReplayFlow().replay(run_id=run_id, repo_path=repo_path, from_stage=from_stage)
    typer.echo(f"run_id={run.run_id} stage={from_stage}")


# ---------------------------------------------------------------------------
# Verify / release / report
# ---------------------------------------------------------------------------


@app.command("scan")
def scan(repo_path: str = typer.Option(".", "--repo-path")) -> None:
    scan = RepoExplorerAgent().explore(repo_path)
    typer.echo(scan.model_dump_json(indent=2))


@app.command("verify")
def verify(run_id: str = typer.Option(..., "--run-id"), repo_path: str = typer.Option(".", "--repo-path")) -> None:
    from .agents.verifier import VerifierAgent
    run = RunState.load(repo_path, run_id)
    v = VerifierAgent().verify(run.state)
    run.state.verification = v
    run.save_json("verification/verification_report.json", v)
    run.save()
    typer.echo(v.model_dump_json(indent=2))


@app.command("release-check")
def release_check(run_id: str = typer.Option(..., "--run-id"), repo_path: str = typer.Option(".", "--repo-path")) -> None:
    run = RunState.load(repo_path, run_id)
    rc = ReleaseFlow().check(run)
    typer.echo(rc.model_dump_json(indent=2))


@app.command("report")
def report(run_id: str = typer.Option(..., "--run-id"), repo_path: str = typer.Option(".", "--repo-path")) -> None:
    run = RunState.load(repo_path, run_id)
    Reporter().write_final_report(run)
    typer.echo(str(run.path("delivery/final_report.md")))


@app.command("export-delivery")
def export_delivery(
    run_id: str = typer.Option(..., "--run-id"),
    repo_path: str = typer.Option(".", "--repo-path"),
    output: str = typer.Option("./delivery_package", "--output"),
) -> None:
    import shutil

    run = RunState.load(repo_path, run_id)
    out = Path(output)
    out.mkdir(parents=True, exist_ok=True)
    for sub in ("delivery", "verification", "quality", "architecture", "planning", "product", "execution", "input"):
        src = run.path(sub)
        if src.exists():
            shutil.copytree(src, out / sub, dirs_exist_ok=True)
    typer.echo(str(out))


# ---------------------------------------------------------------------------
# push
# ---------------------------------------------------------------------------


@app.command("push")
def push_cmd(
    run_id: str = typer.Option(..., "--run-id"),
    repo_path: str = typer.Option(".", "--repo-path"),
    branch: Optional[str] = typer.Option(None, "--branch"),
    enable: Optional[str] = typer.Option("false", "--enable"),
) -> None:
    """Push the current branch to origin.  Off by default; pass --enable true to activate."""
    from .agents.commit_agent import CommitAgent

    enabled = _parse_tri_bool(enable) is True
    if not enabled:
        typer.echo('{"success": false, "reason": "disabled (pass --enable true to push)"}')
        return
    rc = CommitAgent().maybe_push(repo_path, branch, enabled=True)
    typer.echo(f'{{"success": {str(rc == 0).lower()}, "exit_code": {rc}}}')


# ---------------------------------------------------------------------------
# create-pr
# ---------------------------------------------------------------------------


@app.command("create-pr")
def create_pr_cmd(
    run_id: str = typer.Option(..., "--run-id"),
    repo_path: str = typer.Option(".", "--repo-path"),
    base: str = typer.Option("main", "--base"),
    enable: Optional[str] = typer.Option("false", "--enable"),
    draft: Optional[str] = typer.Option("true", "--draft"),
) -> None:
    """Create a GitHub PR via gh CLI.  Off by default; pass --enable true to activate."""
    import json as _json

    from .agents.commit_agent import CommitAgent, CommitArtifacts
    from .adapters.github_adapter import GitHubAdapter
    from .state import RunState

    enabled = _parse_tri_bool(enable) is True
    draft_flag = _parse_tri_bool(draft) is not False  # default True

    if not enabled:
        typer.echo('{"success": false, "reason": "disabled (pass --enable true to create PR)"}')
        return

    if not GitHubAdapter().gh_available():
        typer.echo('{"success": false, "reason": "gh-not-installed"}')
        return

    try:
        run = RunState.load(repo_path, run_id)
    except Exception as exc:
        typer.echo(_json.dumps({"success": False, "reason": f"run-not-found: {exc}"}))
        raise typer.Exit(code=2)

    agent = CommitAgent()
    artifacts = agent.build_artifacts(state=run.state, project_name=run_id)
    result = agent.maybe_create_pr(repo_path, artifacts, base=base, draft=draft_flag, enabled=True)
    typer.echo(_json.dumps(result))


if __name__ == "__main__":  # pragma: no cover
    app()
