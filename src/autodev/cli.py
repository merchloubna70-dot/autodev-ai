"""`autodev` Typer CLI entrypoint."""
from __future__ import annotations

from pathlib import Path

import typer

from .agents.input_classifier import InputClassifierAgent
from .agents.milestone_planner import MilestonePlannerAgent
from .agents.prd_writer import PRDWriterAgent
from .agents.product_manager import ProductManagerAgent
from .agents.repo_explorer import RepoExplorerAgent
from .agents.requirement_analyst import RequirementAnalystAgent
from .agents.system_architect import SystemArchitectAgent
from .config import FactoryConfig
from .flows.issue_pipeline_flow import IssuePipelineFlow, IssuePipelineInput
from .flows.milestone_flow import MilestoneFlow, MilestoneFlowInput
from .flows.project_delivery_flow import ProjectDeliveryFlow, ProjectDeliveryInput
from .flows.release_flow import ReleaseFlow
from .reports.reporter import Reporter
from .schemas import AgentCard, ExecutionBackend, Language, PipelineMode, Scale
from .state import RunState
from .utils.fs import write_text
from .utils.json_io import write_json

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


def _parse_tri_bool(s: str | None) -> bool | None:
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
    issue_file: str | None = typer.Option(None, "--issue-file"),
    issue_url: str | None = typer.Option(None, "--issue-url"),
    languages: str = typer.Option("python", "--languages"),
    mode: str = typer.Option("dry-run", "--mode"),
    executor: str = typer.Option("auto", "--executor"),
    allow_mock_executor: str | None = typer.Option(None, "--allow-mock-executor"),
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
    project_brief: str | None = typer.Option(None, "--project-brief"),
    prd: str | None = typer.Option(None, "--prd"),
    project_name: str | None = typer.Option(None, "--project-name"),
    languages: str = typer.Option("python", "--languages"),
    mode: str = typer.Option("dry-run", "--mode"),
    from_scratch: str = typer.Option("false", "--from-scratch"),
    executor: str = typer.Option("auto", "--executor"),
    allow_mock_executor: str | None = typer.Option(None, "--allow-mock-executor"),
    claude_timeout: int = typer.Option(900, "--claude-timeout"),
    codex_timeout: int = typer.Option(600, "--codex-timeout"),
    concurrency: int = typer.Option(3, "--concurrency"),
    fail_fast: bool = typer.Option(True, "--fail-fast/--no-fail-fast"),
    continue_and_report: bool = typer.Option(False, "--continue-and-report/--no-continue-and-report"),
    commit: bool = typer.Option(False, "--commit"),
    push: bool = typer.Option(False, "--push"),
    tag: bool = typer.Option(False, "--tag"),
    scale: str | None = typer.Option(None, "--scale", help="Project scale: bug-fix|small|medium|enterprise (auto-inferred if not given)"),
    style: str = typer.Option("prd", "--style", help="Document style: prd (default) or prfaq (Amazon Working Backwards)"),
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
    resolved_scale: Scale | None = None
    if scale is not None:
        try:
            resolved_scale = Scale(scale)
        except ValueError:
            typer.echo(f"[autodev] unknown scale '{scale}'; valid: bug-fix|small|medium|enterprise", err=True)
            raise typer.Exit(1) from None
    else:
        typer.echo("[autodev] --scale not given; will auto-infer from PRD/brief", err=True)
    flow = ProjectDeliveryFlow(cfg)
    run = flow.run(ProjectDeliveryInput(
        repo_path=repo_path, brief_text=brief_text, prd_text=prd_text, project_name=project_name,
        languages=langs, mode=pmode, backend=backend,
        allow_mock=cfg.allow_mock_executor, from_scratch=bool(_parse_tri_bool(from_scratch)),
        commit=commit, push=push, tag=tag,
        scale=resolved_scale,
        prd_style=style,
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
    style: str = typer.Option("prd", "--style", help="Document style: prd (default) or prfaq (Amazon Working Backwards)"),
) -> None:
    text = _read(project_brief)
    pm = ProductManagerAgent()
    req = RequirementAnalystAgent()
    writer = PRDWriterAgent()
    brief = pm.build_brief(text)
    fr, nf, ac = req.derive(brief=brief, source_text=text)
    prd = writer.write(brief=brief, functional=fr, non_functional=nf, acceptance=ac, style=style)
    write_text(output, writer.render_markdown(prd, style=style))
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
    allow_mock_executor: str | None = typer.Option(None, "--allow-mock-executor"),
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
    from_step: str | None = typer.Option(None, "--from-step", help="Resume at a named micro-file step"),
) -> None:
    from .flows.replay_flow import ReplayFlow
    run = ReplayFlow().replay(
        run_id=run_id,
        repo_path=repo_path,
        from_stage=from_stage,
        from_step=from_step,
    )
    if from_step:
        typer.echo(f"run_id={run.run_id} step={from_step}")
    else:
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
    branch: str | None = typer.Option(None, "--branch"),
    enable: str | None = typer.Option("false", "--enable"),
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
    enable: str | None = typer.Option("false", "--enable"),
    draft: str | None = typer.Option("true", "--draft"),
) -> None:
    """Create a GitHub PR via gh CLI.  Off by default; pass --enable true to activate."""
    import json as _json

    from .adapters.github_adapter import GitHubAdapter
    from .agents.commit_agent import CommitAgent
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
        raise typer.Exit(code=2) from None

    agent = CommitAgent()
    artifacts = agent.build_artifacts(state=run.state, project_name=run_id)
    result = agent.maybe_create_pr(repo_path, artifacts, base=base, draft=draft_flag, enabled=True)
    typer.echo(_json.dumps(result))


# ---------------------------------------------------------------------------
# fix-bug
# ---------------------------------------------------------------------------


@app.command("fix-bug")
def fix_bug(
    bug: str = typer.Option(..., "--bug", help="Free-text bug description"),
    repo_path: str = typer.Option(".", "--repo-path"),
    languages: str = typer.Option("python", "--languages"),
    mode: str = typer.Option("dry-run", "--mode"),
    executor: str = typer.Option("auto", "--executor"),
    allow_mock_executor: str | None = typer.Option(None, "--allow-mock-executor"),
) -> None:
    """Run the 4-stage bug-fix flow (reproduce → locate → patch → verify)."""
    from .flows.bug_fix_flow import BugFixFlow, BugFixInput

    pmode = _parse_mode(mode)
    langs = _parse_languages(languages)
    _parse_backend(executor)  # validated but overridden by router per task
    cfg = _build_config(
        mode=pmode,
        allow_mock=_parse_tri_bool(allow_mock_executor),
        fail_fast=True,
        continue_and_report=False,
        concurrency=1,
        codex_timeout=600,
        claude_timeout=900,
    )
    run = BugFixFlow(cfg).run(BugFixInput(
        bug_description=bug,
        repo_path=repo_path,
        languages=langs,
        mode=pmode,
        allow_mock=cfg.allow_mock_executor,
    ))
    impl_results = run.state.implementation_results
    success = impl_results[0].success if impl_results else False
    mock = impl_results[0].mock_used if impl_results else False
    typer.echo(f"run_id={run.run_id} success={success} mock={mock}")


# ---------------------------------------------------------------------------
# multi-patch-fix-bug
# ---------------------------------------------------------------------------


@app.command("multi-patch-fix-bug")
def multi_patch_fix_bug(
    bug: str = typer.Option(..., "--bug", help="Free-text bug description"),
    repo_path: str = typer.Option(".", "--repo-path"),
    candidates: int = typer.Option(3, "--candidates", help="Number of patch candidates to generate"),
    mode: str = typer.Option("dry-run", "--mode"),
    allow_mock_executor: str | None = typer.Option(None, "--allow-mock-executor"),
    languages: str = typer.Option("python", "--languages"),
    executor: str = typer.Option("auto", "--executor"),
) -> None:
    """Run multi-patch self-consistency: generate N candidates and vote for the best."""
    from .flows.multi_patch_flow import MultiPatchFlow, MultiPatchInput

    pmode = _parse_mode(mode)
    langs = _parse_languages(languages)
    backend = _parse_backend(executor)
    cfg = _build_config(
        mode=pmode,
        allow_mock=_parse_tri_bool(allow_mock_executor),
        fail_fast=False,
        continue_and_report=True,
        concurrency=1,
        codex_timeout=600,
        claude_timeout=900,
    )
    run = MultiPatchFlow(cfg).run(MultiPatchInput(
        bug_description=bug,
        repo_path=repo_path,
        n_candidates=candidates,
        languages=langs,
        mode=pmode,
        backend=backend,
        allow_mock=cfg.allow_mock_executor,
    ))
    typer.echo(f"run_id={run.run_id} candidates={candidates} mock={run.state.mock_execution_used}")


# ---------------------------------------------------------------------------
# review
# ---------------------------------------------------------------------------


@app.command("review")
def review_cmd(
    run_id: str = typer.Option(..., "--run-id", help="Run ID whose pending review to resolve"),
    decision: str = typer.Option(..., "--decision", help="approve or reject"),
    repo_path: str = typer.Option(".", "--repo-path"),
) -> None:
    """Write an approved/rejected sentinel so a paused HumanReviewGate can resume."""
    import json as _json

    decision = decision.strip().lower()
    if decision not in ("approve", "reject", "approved", "rejected"):
        typer.echo(_json.dumps({"success": False, "reason": f"invalid decision: {decision!r}; use approve or reject"}))
        raise typer.Exit(code=2)

    # Normalise to approved / rejected
    sentinel_name = "approved" if decision.startswith("approve") else "rejected"

    run_dir = Path(repo_path) / ".dev-factory" / "runs" / run_id
    if not run_dir.exists():
        typer.echo(_json.dumps({"success": False, "reason": f"run_dir not found: {run_dir}"}))
        raise typer.Exit(code=2)

    sentinel = run_dir / sentinel_name
    sentinel.touch()
    typer.echo(_json.dumps({"success": True, "run_id": run_id, "decision": sentinel_name, "sentinel": str(sentinel)}))


# ---------------------------------------------------------------------------
# roundtable
# ---------------------------------------------------------------------------


@app.command("roundtable")
def roundtable_cmd(
    topic: str = typer.Option(..., "--topic", help="Discussion topic for the roundtable"),
    skills: str = typer.Option("architecture,security,perf", "--skills", help="Comma-separated skill names to recruit"),
    max_participants: int = typer.Option(4, "--max-participants", help="Maximum number of agent participants"),
    repo_path: str = typer.Option(".", "--repo-path", help="Repo path (used for output directory)"),
) -> None:
    """Run a BMAD party-mode roundtable: N independent agents discuss a topic and synthesize.

    By default invokes REAL `claude` CLI subprocesses per AgentCard. Export
    FACTORY_FORCE_MOCK=1 in the environment to force deterministic mock
    output (CI / testing without spending tokens).
    """
    import json as _json

    from .agents.roundtable import RoundtableAgent

    skill_list = [s.strip() for s in skills.split(",") if s.strip()]

    rt = RoundtableAgent()
    conversation, synth_msg = rt.discuss_and_synthesize(
        topic=topic,
        needed_skills=skill_list,
        max_participants=max_participants,
    )

    # Collect synthesized text
    synth_text = "\n".join(
        part.text for part in synth_msg.parts if part.kind == "text" and part.text
    ).strip()

    typer.echo(synth_text or "(no synthesis text)")

    # Write full conversation JSON to .dev-factory/roundtables/<conversation_id>.json
    out_dir = Path(repo_path) / ".dev-factory" / "roundtables"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"{conversation.conversation_id}.json"
    payload = {
        "conversation": conversation.model_dump(mode="json"),
        "synthesis": synth_msg.model_dump(mode="json"),
    }
    out_file.write_text(_json.dumps(payload, indent=2), encoding="utf-8")
    typer.echo(f"wrote {out_file}")


# ---------------------------------------------------------------------------
# mcp-serve
# ---------------------------------------------------------------------------


@app.command("mcp-serve")
def mcp_serve() -> None:
    """Start autodev as an MCP server on stdio (JSON-RPC 2.0).

    Reads JSON-RPC requests line-by-line from stdin and writes responses to
    stdout.  All logging goes to stderr.  Example registration in
    claude_desktop_config.json:

        "autodev": {"command": "autodev", "args": ["mcp-serve"]}
    """
    from .mcp_server.server import MCPServer

    MCPServer().run()


# ---------------------------------------------------------------------------
# a2a-serve
# ---------------------------------------------------------------------------


@app.command("a2a-serve")
def a2a_serve(
    port: int = typer.Option(8421, "--port", help="TCP port to listen on"),
    bind: str = typer.Option("127.0.0.1", "--bind", help="IP address to bind (default: 127.0.0.1)"),
) -> None:
    """Start the A2A HTTP server so external agents can send tasks to autodev."""
    from .adapters.a2a.server import A2AHttpServer

    server = A2AHttpServer(port=port, bind=bind)
    typer.echo(f"A2A server on http://{bind}:{port}")
    server.serve_forever()


# ---------------------------------------------------------------------------
# a2a-register / a2a-call
# ---------------------------------------------------------------------------


@app.command("a2a-register")
def a2a_register(
    endpoint: str = typer.Option(..., "--endpoint", help="Base URL of the remote A2A agent"),
    name: str | None = typer.Option(None, "--name", help="Override agent name in roster"),
    save_to: str = typer.Option("~/.autodev/a2a-roster.json", "--save-to", help="Roster file path"),
) -> None:
    """Discover an AgentCard from a remote A2A endpoint and append to the roster."""
    import json as _json

    from .adapters.a2a.transports.http import A2AHttpTransport

    transport = A2AHttpTransport(
        endpoint=endpoint,
        auth_token=__import__("os").environ.get("AUTODEV_A2A_TOKEN"),
    )
    card = transport.discover_agent_card()
    if card is None:
        typer.echo(_json.dumps({"success": False, "reason": f"could not discover agent card from {endpoint}"}))
        raise typer.Exit(code=2)

    if name:
        card = card.model_copy(update={"name": name})

    typer.echo(card.model_dump_json(indent=2))

    # Append / update roster file
    roster_path = Path(save_to).expanduser()
    roster_path.parent.mkdir(parents=True, exist_ok=True)
    roster: list[dict] = []
    if roster_path.exists():
        try:
            roster = _json.loads(roster_path.read_text(encoding="utf-8"))
            if not isinstance(roster, list):
                roster = []
        except Exception:
            roster = []

    # Remove existing entry for same endpoint to avoid duplicates
    roster = [e for e in roster if not (isinstance(e, dict) and e.get("card", {}).get("endpoint") == endpoint)]
    roster.append({"card": card.model_dump(mode="json"), "registered_via": "discovered"})
    roster_path.write_text(_json.dumps(roster, indent=2), encoding="utf-8")
    typer.echo(f"registered to {roster_path}")


@app.command("a2a-call")
def a2a_call(
    endpoint: str = typer.Option(..., "--endpoint", help="Base URL of the remote A2A agent"),
    skill: str = typer.Option("default", "--skill", help="Skill/capability to call"),
    task_json: str = typer.Option("{}", "--task-json", help="JSON dict for the task user message text"),
) -> None:
    """Build an A2ATask and send it to a remote A2A agent via HTTP transport.

    ``--task-json`` may be a bare text string or a JSON object with a ``text`` key.
    Prints the result message from the completed task.
    """
    import json as _json
    import os as _os
    import uuid

    from .adapters.a2a.transports.http import A2AHttpTransport
    from .schemas import A2AMessage, A2APart, A2ATask, A2ATaskStatus

    # Parse task-json
    try:
        payload = _json.loads(task_json)
        if isinstance(payload, str):
            text_content = payload
        else:
            text_content = payload.get("text", task_json)
    except Exception:
        text_content = task_json

    task_id = str(uuid.uuid4())
    context_id = str(uuid.uuid4())
    task = A2ATask(
        id=task_id,
        context_id=context_id,
        status=A2ATaskStatus.SUBMITTED,
        history=[
            A2AMessage(
                message_id=str(uuid.uuid4()),
                role="user",
                parts=[A2APart(kind="text", text=text_content)],
                context_id=context_id,
                task_id=task_id,
            )
        ],
        metadata={"skill": skill},
    )

    card_obj = AgentCard(
        name=f"remote@{endpoint}",
        transport="a2a-http",
        endpoint=endpoint,
        skills=[skill],
    )

    transport = A2AHttpTransport(
        endpoint=endpoint,
        auth_token=_os.environ.get("AUTODEV_A2A_TOKEN"),
    )
    result = transport.send_task(card_obj, task)
    typer.echo(_json.dumps(result.model_dump(mode="json"), indent=2))


# --- BMAD-3 NEXT-ADVISOR ---


@app.command("next")
def next_cmd(
    run_id: str = typer.Option(..., "--run-id"),
    repo_path: str = typer.Option(".", "--repo-path"),
) -> None:
    """Suggest the next concrete action based on current run state."""
    from .agents.next_step_advisor import NextStepAdvisor
    from .state import RunState

    run = RunState.load(repo_path, run_id)
    advice = NextStepAdvisor().advise(run.state)
    typer.echo(f"NEXT: {advice.next_command}")
    typer.echo(f"WHY:  {advice.rationale}")
    typer.echo(f"CONFIDENCE: {advice.confidence:.2f}")
    if advice.evidence_paths:
        typer.echo("EVIDENCE:")
        for p in advice.evidence_paths:
            typer.echo(f"  {p}")


# --- END BMAD-3 NEXT-ADVISOR ---

# --- BMAD-8 UX-DESIGN ---


@app.command("design-ux")
def design_ux_cmd(
    project_brief: str | None = typer.Option(None, "--project-brief"),
    project_name: str | None = typer.Option(None, "--project-name"),
    repo_path: str = typer.Option(".", "--repo-path"),
    languages: str = typer.Option("python", "--languages"),
) -> None:
    """Run BMAD-Sally-style UX design workflow (7 steps, deterministic)."""

    from .flows.ux_design_flow import UXDesignFlow
    from .schemas import Language, UXDesignInput

    lang_list: list[Language] = []
    for raw in languages.split(","):
        raw = raw.strip().lower()
        try:
            lang_list.append(Language(raw))
        except ValueError:
            lang_list.append(Language.UNKNOWN)

    name = project_name or "Product"

    inputs = UXDesignInput(
        product_name=name,
        languages=lang_list,
        repo_path=repo_path,
    )

    flow = UXDesignFlow(use_llm=False)
    spec = flow.run(inputs)

    typer.echo(f"[design-ux] Sally completed 7-step UX design for '{spec.product_name}'.")
    typer.echo(f"  Personas   : {len(spec.personas)}")
    typer.echo(f"  Journeys   : {len(spec.journeys)}")
    typer.echo(f"  Tokens     : {len(spec.design_tokens)}")
    typer.echo(f"  Components : {len(spec.components)}")
    typer.echo(f"  Patterns   : {len(spec.patterns)}")
    typer.echo(f"  Written to : {repo_path}/product/ux_design.md")


# --- END BMAD-8 UX-DESIGN ---

# --- BMAD-10 INVESTIGATE ---


@app.command("investigate")
def investigate_cmd(
    input_token: str = typer.Option(..., "--input", help="ticket-id / log path / error msg / code area / problem description"),
    repo_path: str = typer.Option(".", "--repo-path"),
) -> None:
    """Open a structured case file for an investigation."""
    from .flows.investigation_flow import InvestigationFlow, InvestigationInput

    flow = InvestigationFlow()
    case = flow.run(InvestigationInput(input_token=input_token, repo_path=repo_path))
    typer.echo(f"case_id={case.case_id} slug={case.slug} mode={case.mode}")
    if case.file_path:
        typer.echo(f"file={case.file_path}")
    typer.echo(f"evidence_count={len(case.evidence)}")


# --- END BMAD-10 INVESTIGATE ---

# --- BMAD-11 PROJECT-CONTEXT ---


@app.command("generate-context")
def generate_context_cmd(
    repo_path: str = typer.Option(".", "--repo-path"),
    project_brief: str | None = typer.Option(None, "--project-brief"),
    product_name: str | None = typer.Option(None, "--product-name"),
) -> None:
    """Generate _autodev/project-context.md from repo + optional brief."""
    from .flows.project_context_flow import ProjectContextFlow, ProjectContextInput

    inp = ProjectContextInput(
        repo_path=repo_path,
        product_name=product_name or "",
        brief_path=project_brief,
    )
    flow = ProjectContextFlow()
    ctx = flow.run(inp)
    typer.echo(f"[generate-context] product={ctx.product_name} rules={len(ctx.rules)}")
    typer.echo(f"  md  : {ctx.file_path}")
    if ctx.file_path:
        import pathlib
        json_path = pathlib.Path(ctx.file_path).with_suffix(".json")
        typer.echo(f"  json: {json_path}")


# --- END BMAD-11 PROJECT-CONTEXT ---

# --- BMAD-13 DOCUMENT-PROJECT ---


@app.command("document-project")
def document_project_cmd(
    repo_path: str = typer.Option(".", "--repo-path"),
    languages: str = typer.Option("python", "--languages"),
) -> None:
    """Generate brownfield AI-onboarding docs from existing repo."""
    from .flows.brownfield_doc_flow import BrownfieldDocFlow, BrownfieldDocInput

    langs = _parse_languages(languages)
    inp = BrownfieldDocInput(repo_path=repo_path, languages=langs)
    flow = BrownfieldDocFlow()
    doc = flow.run(inp)
    typer.echo(f"[document-project] repo={doc.repo_path} sections={len(doc.sections)}")
    typer.echo(f"  output_dir: {doc.output_dir}")
    for section in doc.sections:
        typer.echo(f"  - {section.name}: {section.file_path}")


# --- END BMAD-13 DOCUMENT-PROJECT ---

# --- BMAD-7 SPRINT ---


@app.command("sprint-start")
def sprint_start_cmd(
    repo_path: str = typer.Option(".", "--repo-path", help="Repo / project root"),
    goal: str = typer.Option("", "--goal", help="Sprint goal statement"),
    product_name: str = typer.Option("", "--product-name", help="Product name"),
    duration_days: int = typer.Option(14, "--duration-days", help="Planned sprint duration in days"),
) -> None:
    """Open a new BMAD sprint under .autodev/sprints/sprint-NNN/."""
    from .flows.sprint_flow import SprintFlow
    from .schemas import SprintInput

    inp = SprintInput(
        repo_path=repo_path,
        product_name=product_name,
        goal=goal,
        duration_days=duration_days,
    )
    state = SprintFlow().start_sprint(inp)
    typer.echo(f"sprint_id={state.sprint_id} started_at={state.started_at}")
    typer.echo(f"planning={state.planning_artifacts_path}")
    typer.echo(f"implementation={state.implementation_artifacts_path}")
    if state.previous_sprint_id:
        typer.echo(f"previous={state.previous_sprint_id}")


@app.command("sprint-status")
def sprint_status_cmd(
    repo_path: str = typer.Option(".", "--repo-path", help="Repo / project root"),
    sprint_id: str | None = typer.Option(None, "--sprint-id", help="Sprint ID (e.g. sprint-001); defaults to latest"),
) -> None:
    """Report health metrics for the current or specified sprint."""
    from .flows.sprint_flow import SprintFlow

    status = SprintFlow().status(repo_path, sprint_id)
    typer.echo(f"sprint_id={status.sprint_id} health={status.health}")
    typer.echo(f"tasks_total={status.tasks_total} done={status.tasks_done} failed={status.tasks_failed}")
    typer.echo(f"progress={status.progress_pct:.1f}%")
    if status.blockers:
        typer.echo(f"blockers={status.blockers}")


@app.command("sprint-retro")
def sprint_retro_cmd(
    repo_path: str = typer.Option(".", "--repo-path", help="Repo / project root"),
    sprint_id: str = typer.Option(..., "--sprint-id", help="Sprint ID to retrospect (e.g. sprint-001)"),
) -> None:
    """Run a retrospective analysis for the given sprint and save report."""
    from .flows.sprint_flow import SprintFlow

    report = SprintFlow().retrospective(repo_path, sprint_id)
    typer.echo(f"sprint_id={report.sprint_id}")
    typer.echo(f"well={len(report.what_went_well)} wrong={len(report.what_went_wrong)}")
    typer.echo(f"actions={len(report.actions_for_next_sprint)}")
    typer.echo(f"carryover_ac={len(report.carryover_acceptance_criteria)}")
    typer.echo(f"generated_at={report.generated_at}")


@app.command("sprint-correct")
def sprint_correct_cmd(
    repo_path: str = typer.Option(".", "--repo-path", help="Repo / project root"),
    sprint_id: str = typer.Option(..., "--sprint-id", help="Sprint ID to analyse"),
    change: str = typer.Option(..., "--change", help="Description of the proposed change"),
) -> None:
    """Analyse impact of a change across PRD/Epic/Arch/UX and emit a proposal."""
    from .flows.sprint_flow import SprintFlow

    proposal = SprintFlow().correct_course(repo_path, sprint_id, change)
    typer.echo(f"sprint_id={proposal.sprint_id}")
    typer.echo(f"impacts={len(proposal.impacts)}")
    for imp in proposal.impacts:
        typer.echo(f"  [{imp.severity.value}] {imp.artifact}: {imp.change_summary}")
    typer.echo(f"actions={len(proposal.recommended_actions)}")


# --- END BMAD-7 SPRINT ---

# ---------------------------------------------------------------------------
# dashboard (optional textual TUI)
# ---------------------------------------------------------------------------


@app.command("dashboard")
def dashboard_cmd(
    root: str = typer.Option(".dev-factory", "--root", help="dev-factory root directory"),
) -> None:
    """Launch the Textual TUI dashboard (requires: pip install autodev-ai[tui])."""
    try:
        from .tui.dashboard import run as _run  # lazy import — textual is optional
    except ImportError:
        typer.echo(
            "[autodev] Textual is not installed. Run: pip install autodev-ai[tui]",
            err=True,
        )
        raise typer.Exit(code=1) from None
    _run(root=root)


if __name__ == "__main__":  # pragma: no cover
    app()
