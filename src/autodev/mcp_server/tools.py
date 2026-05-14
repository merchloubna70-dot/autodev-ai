"""Tool definitions for the autodev MCP server.

Each Tool maps a name + JSON Schema + handler callable.
All handlers are synchronous for v1; long-running tools execute inline.

Scope vocabulary (see identity.py):
    mcp:read   — read-only tools
    mcp:write  — write / planning tools (no filesystem mutations)
    mcp:apply  — tools that may mutate the filesystem (apply mode)
"""
from __future__ import annotations

import datetime
import json
import os
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .identity import LEGACY_CALLER_ID, SCOPE_APPLY, get_current_caller
from .path_safety import MCPPathSafetyError, _validate_safe_path

# ---------------------------------------------------------------------------
# Tool → required scope mapping (exported so server.py can enforce)
# ---------------------------------------------------------------------------

TOOL_SCOPES: dict[str, str] = {
    # Read-only tools
    "autodev_scan": "mcp:read",
    "autodev_list_runs": "mcp:read",
    "autodev_report": "mcp:read",
    "autodev_release_check": "mcp:read",
    # Write / planning tools
    "autodev_classify_input": "mcp:write",
    "autodev_create_prd": "mcp:write",
    "autodev_roundtable": "mcp:write",
    "autodev_run_issue": "mcp:write",
    "autodev_deliver_project": "mcp:write",
}

# ---------------------------------------------------------------------------
# Apply-mode guardrail helpers
# ---------------------------------------------------------------------------

_ENV_ALLOW_APPLY = "AUTODEV_MCP_ALLOW_APPLY"
_ENV_AUDIT_LOG = "AUTODEV_MCP_AUDIT_LOG"
_DEFAULT_AUDIT_LOG = "/tmp/autodev_mcp_audit.log"


def _get_caller_id() -> str:
    """Return the caller_id for the current request, or LEGACY_CALLER_ID."""
    caller = get_current_caller()
    if caller is None:
        return LEGACY_CALLER_ID
    return caller.caller_id


def _write_audit_log(
    tool_name: str,
    params: dict[str, Any],
    repo_path: str,
    decision: str,
    reason: str | None = None,
) -> None:
    """Write a structured audit entry to stderr and the audit log file.

    The entry always includes a ``caller_id`` field attributed to the current
    request's authenticated identity.  In legacy single-token mode this is
    ``"legacy_shared_token"``; in per-caller mode it is the caller's unique ID.
    """
    # Sanitize params: redact any key containing 'secret', 'token', 'password', 'key'
    _REDACT_KEYS = {"secret", "token", "password", "key"}
    sanitized: dict[str, Any] = {
        k: "***REDACTED***" if any(rk in k.lower() for rk in _REDACT_KEYS) else v
        for k, v in params.items()
    }
    entry: dict[str, Any] = {
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "caller_id": _get_caller_id(),
        "tool": tool_name,
        "params": sanitized,
        "repo_path": repo_path,
        "decision": decision,
    }
    if reason:
        entry["reason"] = reason

    line = json.dumps(entry)
    # Always emit to stderr
    print(f"[autodev-mcp-audit] {line}", file=sys.stderr, flush=True)
    # Also append to audit log file
    log_path = os.environ.get(_ENV_AUDIT_LOG, _DEFAULT_AUDIT_LOG)
    try:
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except OSError:
        # Non-fatal: log to stderr but do not abort the request
        print(
            f"[autodev-mcp-audit] WARNING: could not write audit log to {log_path}",
            file=sys.stderr,
            flush=True,
        )


def _check_apply_mode_allowed(
    tool_name: str,
    args: dict[str, Any],
    repo_path: str,
) -> dict[str, Any] | None:
    """Return an isError dict if apply mode is disallowed, else None (allowed).

    Checks (TRIPLE gate):
      1. mcp:apply scope on the current caller identity
         (skipped in legacy mode — legacy identity has all scopes)
      2. allow_apply param must be True
      3. AUTODEV_MCP_ALLOW_APPLY env var must be "1"

    Writes an audit log entry regardless of outcome.
    """
    # Gate 1: scope check
    caller = get_current_caller()
    if caller is not None and not caller.has_scope(SCOPE_APPLY):
        reason = (
            f"Apply mode requires mcp:apply scope; "
            f"caller {caller.caller_id!r} does not have it"
        )
        _write_audit_log(tool_name, args, repo_path, "denied", reason)
        return {"isError": True, "content": [{"type": "text", "text": reason}]}

    # Gate 2: explicit request opt-in
    allow_apply_param = bool(args.get("allow_apply", False))
    if not allow_apply_param:
        reason = "Apply mode requires allow_apply=true explicit opt-in"
        _write_audit_log(tool_name, args, repo_path, "denied", reason)
        return {"isError": True, "content": [{"type": "text", "text": reason}]}

    # Gate 3: server environment flag
    server_permit = os.environ.get(_ENV_ALLOW_APPLY, "0") == "1"
    if not server_permit:
        reason = (
            f"Server is not configured to permit apply mode; "
            f"set {_ENV_ALLOW_APPLY}=1 to enable"
        )
        _write_audit_log(tool_name, args, repo_path, "denied", reason)
        return {"isError": True, "content": [{"type": "text", "text": reason}]}

    _write_audit_log(tool_name, args, repo_path, "allowed")
    return None


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
    try:
        _validate_safe_path(repo_path, role="repo_path")
    except MCPPathSafetyError as exc:
        return {"isError": True, "content": [{"type": "text", "text": str(exc)}]}
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

    # Preflight: validate repo_path before any file access
    try:
        _validate_safe_path(repo_path, role="repo_path")
    except MCPPathSafetyError as exc:
        return {"isError": True, "content": [{"type": "text", "text": str(exc)}]}

    # Validate mode value early
    if mode_str not in ("dry-run", "apply"):
        return {
            "isError": True,
            "content": [{"type": "text", "text": f"Invalid mode {mode_str!r}; must be 'dry-run' or 'apply'"}],
        }

    # Apply-mode guardrail — must pass BOTH allow_apply param AND server env var
    if mode_str == "apply":
        denial = _check_apply_mode_allowed("autodev_deliver_project", args, repo_path)
        if denial is not None:
            return denial

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

    # Default commit/push/tag to False; caller must explicitly pass True
    commit = bool(args.get("commit", False))
    push = bool(args.get("push", False))
    tag = bool(args.get("tag", False))

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
    return {
        "run_id": run.run_id,
        "release_decision": release_decision,
        "commit": commit,
        "push": push,
        "tag": tag,
    }


_tool_deliver_project = Tool(
    name="autodev_deliver_project",
    description=(
        "Run the full Project Delivery flow: brief → PRD → architecture → milestones → implementation → release check. "
        "NOTE: synchronous in v1; long-running. Use mode='dry-run' for safe offline planning. "
        "WARNING: mode='apply' requires allow_apply=true AND server env AUTODEV_MCP_ALLOW_APPLY=1."
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
                "description": "Execution mode. Defaults to 'dry-run'.",
                "default": "dry-run",
            },
            "allow_apply": {
                "type": "boolean",
                "description": (
                    "Explicit opt-in required when mode='apply'. "
                    "Must be true AND server env AUTODEV_MCP_ALLOW_APPLY=1 must be set."
                ),
                "default": False,
            },
            "commit": {
                "type": "boolean",
                "description": "Whether to commit generated changes. Defaults to false.",
                "default": False,
            },
            "push": {
                "type": "boolean",
                "description": "Whether to push to remote. Defaults to false.",
                "default": False,
            },
            "tag": {
                "type": "boolean",
                "description": "Whether to create a release tag. Defaults to false.",
                "default": False,
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

    # Preflight: validate repo_path before any file access
    try:
        _validate_safe_path(repo_path, role="repo_path")
    except MCPPathSafetyError as exc:
        return {"isError": True, "content": [{"type": "text", "text": str(exc)}]}

    # Validate mode value early
    if mode_str not in ("dry-run", "apply"):
        return {
            "isError": True,
            "content": [{"type": "text", "text": f"Invalid mode {mode_str!r}; must be 'dry-run' or 'apply'"}],
        }

    # Apply-mode guardrail — must pass BOTH allow_apply param AND server env var
    if mode_str == "apply":
        denial = _check_apply_mode_allowed("autodev_run_issue", args, repo_path)
        if denial is not None:
            return denial

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

    # Default commit/push/tag to False; caller must explicitly pass True
    commit = bool(args.get("commit", False))
    push = bool(args.get("push", False))
    tag = bool(args.get("tag", False))

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
        "commit": commit,
        "push": push,
        "tag": tag,
    }


_tool_run_issue = Tool(
    name="autodev_run_issue",
    description=(
        "Run the Issue Pipeline flow against an existing repo. Classifies, plans, and implements a fix for the given issue text. "
        "WARNING: mode='apply' requires allow_apply=true AND server env AUTODEV_MCP_ALLOW_APPLY=1."
    ),
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
                "description": "Execution mode. Defaults to 'dry-run'.",
                "default": "dry-run",
            },
            "allow_apply": {
                "type": "boolean",
                "description": (
                    "Explicit opt-in required when mode='apply'. "
                    "Must be true AND server env AUTODEV_MCP_ALLOW_APPLY=1 must be set."
                ),
                "default": False,
            },
            "commit": {
                "type": "boolean",
                "description": "Whether to commit generated changes. Defaults to false.",
                "default": False,
            },
            "push": {
                "type": "boolean",
                "description": "Whether to push to remote. Defaults to false.",
                "default": False,
            },
            "tag": {
                "type": "boolean",
                "description": "Whether to create a release tag. Defaults to false.",
                "default": False,
            },
        },
        "required": ["repo_path", "issue_text"],
    },
    handler=_handle_run_issue,
)


# ---------------------------------------------------------------------------
# 6. autodev_report
# ---------------------------------------------------------------------------

def _handle_report(args: dict[str, Any]) -> str | dict[str, Any]:
    repo_path = args.get("repo_path", ".")
    try:
        _validate_safe_path(repo_path, role="repo_path")
    except MCPPathSafetyError as exc:
        return {"isError": True, "content": [{"type": "text", "text": str(exc)}]}
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
    try:
        _validate_safe_path(repo_path, role="repo_path")
    except MCPPathSafetyError as exc:
        return {"isError": True, "content": [{"type": "text", "text": str(exc)}]}
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

def _handle_list_runs(args: dict[str, Any]) -> list[dict[str, Any]] | dict[str, Any]:
    repo_path = args.get("repo_path", ".")
    try:
        _validate_safe_path(repo_path, role="repo_path")
    except MCPPathSafetyError as exc:
        return {"isError": True, "content": [{"type": "text", "text": str(exc)}]}
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
