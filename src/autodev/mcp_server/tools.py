"""Tool definitions for the autodev MCP server.

Each Tool maps a name + JSON Schema + handler callable.
All handlers are synchronous for v1; long-running tools execute inline.
"""
from __future__ import annotations

import json
import os
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class Tool:
    name: str
    description: str
    input_schema: dict[str, Any]
    handler: Callable[[dict[str, Any]], Any]


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _force_mock() -> bool:
    return os.environ.get("FACTORY_FORCE_MOCK", "0") == "1"


# ---------------------------------------------------------------------------
# 1. autodev_scan
# ---------------------------------------------------------------------------

def _handle_scan(args: dict[str, Any]) -> dict[str, Any]:
    repo_path = args.get("repo_path", ".")
    from ..agents.repo_explorer import RepoExplorerAgent
    result = RepoExplorerAgent().explore(repo_path)
    return json.loads(result.model_dump_json())


_tool_scan = Tool(
    name="autodev_scan",
    description="Scan a repository and return a RepoScanResult with language detection, directory structure, and git status.",
    input_schema={
        "type": "object",
        "properties": {
            "repo_path": {
                "type": "string",
                "description": "Absolute or relative path to the repository root.",
            }
        },
        "required": ["repo_path"],
    },
    handler=_handle_scan,
)


# ---------------------------------------------------------------------------
# 2. autodev_classify_input
# ---------------------------------------------------------------------------

def _handle_classify_input(args: dict[str, Any]) -> dict[str, Any]:
    text = args.get("text", "")
    source_path = args.get("source_path")
    source_url = args.get("source_url")
    from ..agents.input_classifier import InputClassifierAgent
    result = InputClassifierAgent().classify(
        text=text, source_path=source_path, source_url=source_url
    )
    return json.loads(result.model_dump_json())


_tool_classify = Tool(
    name="autodev_classify_input",
    description="Classify free-form text as a GitHub issue, project brief, PRD, etc., and suggest the appropriate autodev flow.",
    input_schema={
        "type": "object",
        "properties": {
            "text": {"type": "string", "description": "The input text to classify."},
            "source_path": {"type": "string", "description": "Optional file path the text came from."},
            "source_url": {"type": "string", "description": "Optional URL the text came from."},
        },
        "required": ["text"],
    },
    handler=_handle_classify_input,
)


# ---------------------------------------------------------------------------
# 3. autodev_create_prd
# ---------------------------------------------------------------------------

def _handle_create_prd(args: dict[str, Any]) -> str:
    brief_text = args.get("brief_text", "")
    from ..agents.prd_writer import PRDWriterAgent
    from ..agents.product_manager import ProductManagerAgent
    from ..agents.requirement_analyst import RequirementAnalystAgent
    pm = ProductManagerAgent()
    req = RequirementAnalystAgent()
    writer = PRDWriterAgent()
    brief = pm.build_brief(brief_text)
    fr, nf, ac = req.derive(brief=brief, source_text=brief_text)
    prd = writer.write(brief=brief, functional=fr, non_functional=nf, acceptance=ac)
    return writer.render_markdown(prd)


_tool_create_prd = Tool(
    name="autodev_create_prd",
    description="Convert a project brief into a full Product Requirements Document (PRD) in Markdown format.",
    input_schema={
        "type": "object",
        "properties": {
            "brief_text": {"type": "string", "description": "Free-form project brief text."},
            "project_name": {"type": "string", "description": "Optional project name override."},
        },
        "required": ["brief_text"],
    },
    handler=_handle_create_prd,
)


# ---------------------------------------------------------------------------
# 4. autodev_deliver_project
# ---------------------------------------------------------------------------

def _handle_deliver_project(args: dict[str, Any]) -> dict[str, Any]:
    repo_path = args.get("repo_path", ".")
    brief_text = args.get("brief_text")
    project_name = args.get("project_name")
    languages_raw = args.get("languages", ["python"])
    from_scratch = bool(args.get("from_scratch", False))
    mode_str = args.get("mode", "dry-run")

    from ..config import FactoryConfig
    from ..flows.project_delivery_flow import ProjectDeliveryFlow, ProjectDeliveryInput
    from ..schemas import Language, PipelineMode

    langs = []
    for lang in (languages_raw if isinstance(languages_raw, list) else [languages_raw]):
        try:
            langs.append(Language(str(lang).lower()))
        except ValueError:
            langs.append(Language.UNKNOWN)

    pmode = PipelineMode.APPLY if mode_str == "apply" else PipelineMode.DRY_RUN
    cfg = FactoryConfig.from_env()
    cfg.default_mode = pmode
    cfg.allow_mock_executor = _force_mock() or pmode == PipelineMode.DRY_RUN

    flow = ProjectDeliveryFlow(cfg)
    run = flow.run(ProjectDeliveryInput(
        repo_path=repo_path,
        brief_text=brief_text,
        project_name=project_name,
        languages=langs,
        mode=pmode,
        allow_mock=cfg.allow_mock_executor,
        from_scratch=from_scratch,
    ))
    release_decision = (
        run.state.release_check.decision.value if run.state.release_check else "N/A"
    )
    return {"run_id": run.run_id, "release_decision": release_decision}


_tool_deliver_project = Tool(
    name="autodev_deliver_project",
    description=(
        "Run the full Project Delivery flow: brief → PRD → architecture → milestones → implementation → release check. "
        "NOTE: synchronous in v1; long-running. Use mode='dry-run' for safe offline planning."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "repo_path": {"type": "string", "description": "Repository root path."},
            "brief_text": {"type": "string", "description": "Project brief text."},
            "project_name": {"type": "string", "description": "Optional project name."},
            "languages": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Target languages, e.g. ['python', 'typescript'].",
            },
            "from_scratch": {"type": "boolean", "description": "Start from an empty repo.", "default": False},
            "mode": {
                "type": "string",
                "enum": ["dry-run", "apply"],
                "description": "Execution mode.",
                "default": "dry-run",
            },
        },
        "required": ["repo_path", "brief_text"],
    },
    handler=_handle_deliver_project,
)


# ---------------------------------------------------------------------------
# 5. autodev_run_issue
# ---------------------------------------------------------------------------

def _handle_run_issue(args: dict[str, Any]) -> dict[str, Any]:
    repo_path = args.get("repo_path", ".")
    issue_text = args.get("issue_text", "")
    issue_id = args.get("issue_id", "ISSUE-0")
    languages_raw = args.get("languages", ["python"])
    mode_str = args.get("mode", "dry-run")

    from ..config import FactoryConfig
    from ..flows.issue_pipeline_flow import IssuePipelineFlow, IssuePipelineInput
    from ..schemas import Language, PipelineMode

    langs = []
    for lang in (languages_raw if isinstance(languages_raw, list) else [languages_raw]):
        try:
            langs.append(Language(str(lang).lower()))
        except ValueError:
            langs.append(Language.UNKNOWN)

    pmode = PipelineMode.APPLY if mode_str == "apply" else PipelineMode.DRY_RUN
    cfg = FactoryConfig.from_env()
    cfg.default_mode = pmode
    cfg.allow_mock_executor = _force_mock() or pmode == PipelineMode.DRY_RUN

    flow = IssuePipelineFlow(cfg)
    run = flow.run(IssuePipelineInput(
        repo_path=repo_path,
        issue_text=issue_text,
        issue_id=str(issue_id),
        languages=langs,
        mode=pmode,
        allow_mock=cfg.allow_mock_executor,
    ))
    return {
        "run_id": run.run_id,
        "mock_used": run.state.mock_execution_used,
        "mode": pmode.value,
    }


_tool_run_issue = Tool(
    name="autodev_run_issue",
    description="Run the Issue Pipeline flow against an existing repo. Classifies, plans, and implements a fix for the given issue text.",
    input_schema={
        "type": "object",
        "properties": {
            "repo_path": {"type": "string", "description": "Repository root path."},
            "issue_text": {"type": "string", "description": "Full text of the GitHub issue or bug report."},
            "issue_id": {"type": "string", "description": "Optional issue identifier, e.g. 'GH-42'."},
            "languages": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Target languages.",
            },
            "mode": {
                "type": "string",
                "enum": ["dry-run", "apply"],
                "default": "dry-run",
            },
        },
        "required": ["repo_path", "issue_text"],
    },
    handler=_handle_run_issue,
)


# ---------------------------------------------------------------------------
# 6. autodev_report
# ---------------------------------------------------------------------------

def _handle_report(args: dict[str, Any]) -> str:
    repo_path = args.get("repo_path", ".")
    run_id = args.get("run_id", "")
    from ..reports.reporter import Reporter
    from ..state import RunState
    run = RunState.load(repo_path, run_id)
    Reporter().write_final_report(run)
    report_path = run.path("delivery/final_report.md")
    return report_path.read_text(encoding="utf-8") if report_path.exists() else f"report written to {report_path}"


_tool_report = Tool(
    name="autodev_report",
    description="Generate and return the final delivery report for a completed run.",
    input_schema={
        "type": "object",
        "properties": {
            "repo_path": {"type": "string", "description": "Repository root path."},
            "run_id": {"type": "string", "description": "Run ID to report on."},
        },
        "required": ["repo_path", "run_id"],
    },
    handler=_handle_report,
)


# ---------------------------------------------------------------------------
# 7. autodev_roundtable
# ---------------------------------------------------------------------------

def _handle_roundtable(args: dict[str, Any]) -> dict[str, Any]:
    topic = args.get("topic", "")
    skills = args.get("skills", ["architecture", "security", "perf"])
    max_participants = int(args.get("max_participants", 4))

    from ..agents.roundtable import RoundtableAgent

    rt = RoundtableAgent()
    conversation, synth_msg = rt.discuss_and_synthesize(
        topic=topic,
        needed_skills=skills,
        max_participants=max_participants,
    )
    synth_text = "\n".join(
        part.text for part in synth_msg.parts if part.kind == "text" and part.text
    ).strip()
    return {
        "synth_text": synth_text or "(no synthesis text)",
        "conversation": conversation.model_dump(mode="json"),
    }


_tool_roundtable = Tool(
    name="autodev_roundtable",
    description="Run a BMAD party-mode roundtable: N independent agents discuss a topic and synthesize a merged verdict.",
    input_schema={
        "type": "object",
        "properties": {
            "topic": {"type": "string", "description": "The discussion topic."},
            "skills": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Skill names to recruit, e.g. ['architecture', 'security'].",
            },
            "max_participants": {
                "type": "integer",
                "description": "Maximum number of agent participants.",
                "default": 4,
            },
        },
        "required": ["topic", "skills"],
    },
    handler=_handle_roundtable,
)


# ---------------------------------------------------------------------------
# 8. autodev_release_check
# ---------------------------------------------------------------------------

def _handle_release_check(args: dict[str, Any]) -> dict[str, Any]:
    repo_path = args.get("repo_path", ".")
    run_id = args.get("run_id", "")
    from ..flows.release_flow import ReleaseFlow
    from ..state import RunState
    run = RunState.load(repo_path, run_id)
    rc = ReleaseFlow().check(run)
    return json.loads(rc.model_dump_json())


_tool_release_check = Tool(
    name="autodev_release_check",
    description="Run a release readiness check on a completed run and return a ReleaseCheckReport.",
    input_schema={
        "type": "object",
        "properties": {
            "repo_path": {"type": "string", "description": "Repository root path."},
            "run_id": {"type": "string", "description": "Run ID to check."},
        },
        "required": ["repo_path", "run_id"],
    },
    handler=_handle_release_check,
)


# ---------------------------------------------------------------------------
# 9. autodev_list_runs
# ---------------------------------------------------------------------------

def _handle_list_runs(args: dict[str, Any]) -> list[dict[str, Any]]:
    repo_path = args.get("repo_path", ".")
    runs_root = Path(repo_path) / ".dev-factory" / "runs"
    if not runs_root.exists():
        return []
    results: list[dict[str, Any]] = []
    for run_dir in sorted(runs_root.iterdir(), key=lambda p: p.name, reverse=True)[:20]:
        if not run_dir.is_dir():
            continue
        state_file = run_dir / "run_state.json"
        summary: dict[str, Any] = {"run_id": run_dir.name}
        if state_file.exists():
            try:
                data = json.loads(state_file.read_text(encoding="utf-8"))
                summary["mode"] = data.get("mode", "unknown")
                summary["flow"] = data.get("flow", "unknown")
            except Exception:
                pass
        results.append(summary)
    return results


_tool_list_runs = Tool(
    name="autodev_list_runs",
    description="List recent run IDs (up to 20) for a repository with summary metadata.",
    input_schema={
        "type": "object",
        "properties": {
            "repo_path": {"type": "string", "description": "Repository root path."},
        },
        "required": ["repo_path"],
    },
    handler=_handle_list_runs,
)


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

def get_tools() -> list[Tool]:
    return [
        _tool_scan,
        _tool_classify,
        _tool_create_prd,
        _tool_deliver_project,
        _tool_run_issue,
        _tool_report,
        _tool_roundtable,
        _tool_release_check,
        _tool_list_runs,
    ]
