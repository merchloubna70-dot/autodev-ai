"""Skill-to-handler map for the A2A HTTP server.

Each handler takes an A2ATask and returns an updated A2ATask with
an agent A2AMessage appended to task.history.
"""
from __future__ import annotations

import uuid
from collections.abc import Callable

from ...schemas import (
    A2AMessage,
    A2APart,
    A2ATask,
    A2ATaskStatus,
)


def _agent_message(text: str, task_id: str) -> A2AMessage:
    return A2AMessage(
        message_id=str(uuid.uuid4()),
        role="agent",
        parts=[A2APart(kind="text", text=text)],
        task_id=task_id,
    )


def _complete(task: A2ATask, text: str) -> A2ATask:
    task.history.append(_agent_message(text, task.id))
    task.status = A2ATaskStatus.COMPLETED
    return task


def _fail(task: A2ATask, reason: str) -> A2ATask:
    task.history.append(_agent_message(f"ERROR: {reason}", task.id))
    task.status = A2ATaskStatus.FAILED
    return task


# ---------------------------------------------------------------------------
# Skill handlers
# ---------------------------------------------------------------------------


def handle_scan(task: A2ATask) -> A2ATask:
    """skill=scan — run RepoScanner on the given repo_path."""
    try:
        from ...scanners.repo_scanner import RepoScanner

        repo_path = task.metadata.get("repo_path", ".")
        result = RepoScanner().scan(repo_path)
        text = result.model_dump_json(indent=2)
        return _complete(task, f"scan result:\n{text}")
    except Exception as exc:  # noqa: BLE001
        return _fail(task, str(exc))


def handle_classify_input(task: A2ATask) -> A2ATask:
    """skill=classify-input — classify raw input text."""
    try:
        from ...agents.input_classifier import InputClassifierAgent

        # First user message text is the input to classify
        text = ""
        for msg in task.history:
            if msg.role == "user":
                for part in msg.parts:
                    if part.kind == "text" and part.text:
                        text = part.text
                        break
                if text:
                    break
        if not text:
            text = task.metadata.get("input_text", "")

        result = InputClassifierAgent().classify(text=text)
        return _complete(task, result.model_dump_json(indent=2))
    except Exception as exc:  # noqa: BLE001
        return _fail(task, str(exc))


def handle_create_prd(task: A2ATask) -> A2ATask:
    """skill=create-prd — run PRD writer pipeline."""
    try:
        from ...agents.prd_writer import PRDWriterAgent
        from ...agents.product_manager import ProductManagerAgent
        from ...agents.requirement_analyst import RequirementAnalystAgent

        text = ""
        for msg in task.history:
            if msg.role == "user":
                for part in msg.parts:
                    if part.kind == "text" and part.text:
                        text = part.text
                        break
                if text:
                    break
        if not text:
            text = task.metadata.get("brief_text", "")

        pm = ProductManagerAgent()
        req = RequirementAnalystAgent()
        writer = PRDWriterAgent()
        brief = pm.build_brief(text)
        fr, nf, ac = req.derive(brief=brief, source_text=text)
        prd = writer.write(brief=brief, functional=fr, non_functional=nf, acceptance=ac)
        return _complete(task, prd.model_dump_json(indent=2))
    except Exception as exc:  # noqa: BLE001
        return _fail(task, str(exc))


def handle_roundtable(task: A2ATask) -> A2ATask:
    """skill=roundtable — run BMAD roundtable discussion."""
    try:
        from ...agents.roundtable import RoundtableAgent

        topic = task.metadata.get("topic", "")
        if not topic:
            for msg in task.history:
                if msg.role == "user":
                    for part in msg.parts:
                        if part.kind == "text" and part.text:
                            topic = part.text
                            break
                    if topic:
                        break

        skills_raw = task.metadata.get("skills", "architecture,security,perf")
        if isinstance(skills_raw, list):
            skills = skills_raw
        else:
            skills = [s.strip() for s in str(skills_raw).split(",") if s.strip()]

        max_participants = int(task.metadata.get("max_participants", 4))

        rt = RoundtableAgent()
        _conversation, synth_msg = rt.discuss_and_synthesize(
            topic=topic,
            needed_skills=skills,
            max_participants=max_participants,
        )
        synth_text = "\n".join(
            part.text for part in synth_msg.parts if part.kind == "text" and part.text
        ).strip()
        return _complete(task, synth_text or "(no synthesis)")
    except Exception as exc:  # noqa: BLE001
        return _fail(task, str(exc))


def handle_deliver_project(task: A2ATask) -> A2ATask:
    """skill=deliver-project — run ProjectDeliveryFlow (sync for v1)."""
    try:
        from ...config import FactoryConfig
        from ...flows.project_delivery_flow import ProjectDeliveryFlow, ProjectDeliveryInput
        from ...schemas import PipelineMode

        meta = task.metadata
        cfg = FactoryConfig.from_env()
        cfg.allow_mock_executor = True  # safe default for remote calls
        cfg.default_mode = PipelineMode.DRY_RUN

        brief_text = meta.get("brief_text") or None
        prd_text = meta.get("prd_text") or None
        repo_path = meta.get("repo_path", ".")
        project_name = meta.get("project_name") or None

        flow = ProjectDeliveryFlow(cfg)
        run = flow.run(ProjectDeliveryInput(
            repo_path=repo_path,
            brief_text=brief_text,
            prd_text=prd_text,
            project_name=project_name,
            mode=PipelineMode.DRY_RUN,
            allow_mock=True,
        ))
        text = (
            f"run_id={run.run_id} "
            f"mock={run.state.mock_execution_used} "
            f"release={run.state.release_check.decision.value if run.state.release_check else 'N/A'}"
        )
        return _complete(task, text)
    except Exception as exc:  # noqa: BLE001
        return _fail(task, str(exc))


def handle_release_check(task: A2ATask) -> A2ATask:
    """skill=release-check — run ReleaseFlow on an existing run."""
    try:
        from ...flows.release_flow import ReleaseFlow
        from ...state import RunState

        run_id = task.metadata.get("run_id", "")
        repo_path = task.metadata.get("repo_path", ".")
        if not run_id:
            return _fail(task, "missing run_id in task.metadata")

        run = RunState.load(repo_path, run_id)
        rc = ReleaseFlow().check(run)
        return _complete(task, rc.model_dump_json(indent=2))
    except Exception as exc:  # noqa: BLE001
        return _fail(task, str(exc))


# ---------------------------------------------------------------------------
# Handler registry
# ---------------------------------------------------------------------------

SKILL_HANDLERS: dict[str, Callable[[A2ATask], A2ATask]] = {
    "scan": handle_scan,
    "classify-input": handle_classify_input,
    "create-prd": handle_create_prd,
    "roundtable": handle_roundtable,
    "deliver-project": handle_deliver_project,
    "release-check": handle_release_check,
}
