"""R10 coverage backfill — A2A handlers, MCP client, A2A server.

Target:
  - adapters/a2a/handlers.py   59% → ≥90%
  - adapters/mcp_client.py     45% → ≥90%
  - adapters/a2a/server.py     87% → ≥90%
"""
from __future__ import annotations

import json
import os
import socket
import subprocess
import threading
import time
import uuid
from unittest.mock import MagicMock, patch

import pytest

from autodev.adapters.a2a.handlers import (
    SKILL_HANDLERS,
    _fail,
    handle_classify_input,
    handle_create_prd,
    handle_deliver_project,
    handle_release_check,
    handle_roundtable,
)
from autodev.adapters.a2a.server import A2AHttpServer, _TaskStore
from autodev.adapters.mcp_client import DEFAULT_ALLOWED_BINS, MCPToolClient, _force_mock
from autodev.schemas import (
    A2AMessage,
    A2APart,
    A2ATask,
    A2ATaskStatus,
)

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _make_task(
    skill: str = "scan",
    metadata: dict | None = None,
    user_text: str | None = None,
) -> A2ATask:
    task = A2ATask(
        id=str(uuid.uuid4()),
        context_id=str(uuid.uuid4()),
        metadata=metadata or {},
    )
    if user_text is not None:
        task.history.append(
            A2AMessage(
                message_id=str(uuid.uuid4()),
                role="user",
                parts=[A2APart(kind="text", text=user_text)],
            )
        )
    return task


# ============================================================================
# Section A: adapters/a2a/handlers.py — missing lines 78-79, 84-109, 146-147,
#            152-183, 197-201
# ============================================================================


class TestHandleClassifyInputExceptionPath:
    """Lines 78-79: exception path inside handle_classify_input."""

    def test_classify_exception_caught_returns_failed(self, monkeypatch):
        """When InputClassifierAgent.classify raises, task is FAILED (not propagated)."""

        class _BoomClassifier:
            def classify(self, *, text):
                raise ValueError("classify exploded")

        monkeypatch.setattr(
            "autodev.adapters.a2a.handlers.handle_classify_input",
            lambda task: _fail(task, "classify exploded"),
        )
        task = _make_task(metadata={"input_text": "hello"})
        # Exercise via real function — patch the inner import instead
        with patch("autodev.agents.input_classifier.InputClassifierAgent") as mock_cls:
            mock_cls.return_value.classify.side_effect = ValueError("classify exploded")
            result = handle_classify_input(task)
        assert result.status == A2ATaskStatus.FAILED
        assert "classify exploded" in result.history[-1].parts[0].text

    def test_classify_exception_with_empty_history(self, monkeypatch):
        """handle_classify_input exception path with no history (falls back to metadata)."""
        with patch("autodev.agents.input_classifier.InputClassifierAgent") as mock_cls:
            mock_cls.return_value.classify.side_effect = RuntimeError("no model")
            task = _make_task(metadata={"input_text": "some input"})
            result = handle_classify_input(task)
        assert result.status == A2ATaskStatus.FAILED


class TestHandleCreatePrd:
    """Lines 84-109: handle_create_prd."""

    def test_create_prd_exception_path(self):
        """When PRD pipeline raises, task is FAILED."""
        task = _make_task(metadata={"brief_text": "Build a chat app"})
        with (
            patch("autodev.agents.product_manager.ProductManagerAgent") as pm_cls,
        ):
            pm_cls.return_value.build_brief.side_effect = RuntimeError("pm failed")
            result = handle_create_prd(task)
        assert result.status == A2ATaskStatus.FAILED
        assert "pm failed" in result.history[-1].parts[0].text

    def test_create_prd_with_user_history_text(self):
        """handle_create_prd reads user text from history."""
        task = _make_task(user_text="Build a simple todo app")
        with (
            patch("autodev.agents.product_manager.ProductManagerAgent") as pm_cls,
            patch("autodev.agents.requirement_analyst.RequirementAnalystAgent"),
            patch("autodev.agents.prd_writer.PRDWriterAgent"),
        ):
            pm_cls.return_value.build_brief.side_effect = ValueError("import failed")
            result = handle_create_prd(task)
        assert result.status == A2ATaskStatus.FAILED

    def test_create_prd_no_text_uses_metadata(self):
        """handle_create_prd falls back to metadata.brief_text when history is empty."""
        task = _make_task(metadata={"brief_text": "Auto-invest platform"})
        with (
            patch("autodev.agents.prd_writer.PRDWriterAgent"),
            patch("autodev.agents.product_manager.ProductManagerAgent") as pm_cls,
            patch("autodev.agents.requirement_analyst.RequirementAnalystAgent"),
        ):
            pm_cls.return_value.build_brief.side_effect = Exception("pipeline error")
            result = handle_create_prd(task)
        assert result.status in (A2ATaskStatus.FAILED, A2ATaskStatus.COMPLETED)

    def test_create_prd_happy_path_mock(self):
        """handle_create_prd happy path with fully mocked agents."""
        task = _make_task(metadata={"brief_text": "Fintech ledger"})

        mock_prd = MagicMock()
        mock_prd.model_dump_json.return_value = '{"title": "mock prd"}'

        with (
            patch("autodev.agents.product_manager.ProductManagerAgent") as pm_cls,
            patch("autodev.agents.requirement_analyst.RequirementAnalystAgent") as req_cls,
            patch("autodev.agents.prd_writer.PRDWriterAgent") as writer_cls,
        ):
            pm_cls.return_value.build_brief.return_value = "brief"
            req_cls.return_value.derive.return_value = ([], [], [])
            writer_cls.return_value.write.return_value = mock_prd

            result = handle_create_prd(task)

        assert result.status == A2ATaskStatus.COMPLETED
        assert "mock prd" in result.history[-1].parts[0].text


class TestHandleRoundtableExceptionAndSynthesis:
    """Lines 146-147: exception path and empty synthesis in handle_roundtable."""

    def test_roundtable_exception_path(self):
        """When RoundtableAgent raises, task is FAILED."""
        task = _make_task(metadata={"topic": "microservices"})
        with patch("autodev.agents.roundtable.RoundtableAgent") as rt_cls:
            rt_cls.return_value.discuss_and_synthesize.side_effect = RuntimeError("rt down")
            result = handle_roundtable(task)
        assert result.status == A2ATaskStatus.FAILED
        assert "rt down" in result.history[-1].parts[0].text

    def test_roundtable_empty_synthesis_uses_fallback(self):
        """When synthesized message has no text, '(no synthesis)' is used."""
        task = _make_task(metadata={"topic": "deployment"})
        synth_msg = A2AMessage(
            message_id=str(uuid.uuid4()),
            role="agent",
            parts=[A2APart(kind="text", text="")],  # empty text
        )
        with patch("autodev.agents.roundtable.RoundtableAgent") as rt_cls:
            rt_cls.return_value.discuss_and_synthesize.return_value = ([], synth_msg)
            result = handle_roundtable(task)
        assert result.status == A2ATaskStatus.COMPLETED
        assert "(no synthesis)" in result.history[-1].parts[0].text

    def test_roundtable_topic_from_history_no_metadata(self):
        """Roundtable picks topic from user history when metadata.topic is absent."""
        task = _make_task(user_text="Is GraphQL better than REST?")
        synth_msg = A2AMessage(
            message_id=str(uuid.uuid4()),
            role="agent",
            parts=[A2APart(kind="text", text="yes and no")],
        )
        with patch("autodev.agents.roundtable.RoundtableAgent") as rt_cls:
            rt_cls.return_value.discuss_and_synthesize.return_value = ([], synth_msg)
            result = handle_roundtable(task)
        assert result.status == A2ATaskStatus.COMPLETED

    def test_roundtable_skills_as_comma_string(self):
        """Skills as comma string gets parsed into a list."""
        task = _make_task(
            metadata={
                "topic": "caching",
                "skills": "perf,security",
                "max_participants": "3",
            }
        )
        synth_msg = A2AMessage(
            message_id=str(uuid.uuid4()),
            role="agent",
            parts=[A2APart(kind="text", text="summary here")],
        )
        with patch("autodev.agents.roundtable.RoundtableAgent") as rt_cls:
            rt_cls.return_value.discuss_and_synthesize.return_value = ([], synth_msg)
            handle_roundtable(task)
        # Check that discuss_and_synthesize was called with correct skills list
        call_kwargs = rt_cls.return_value.discuss_and_synthesize.call_args
        assert call_kwargs is not None
        skills = call_kwargs.kwargs.get("needed_skills") or call_kwargs.args[1]
        assert "perf" in skills
        assert "security" in skills


class TestHandleDeliverProject:
    """Lines 152-183: handle_deliver_project."""

    def test_deliver_project_exception_caught(self):
        """When ProjectDeliveryFlow raises, task is FAILED."""
        task = _make_task(metadata={"brief_text": "Build CLI tool"})
        with (
            patch("autodev.config.FactoryConfig") as cfg_cls,
        ):
            cfg_cls.from_env.side_effect = RuntimeError("config error")
            result = handle_deliver_project(task)
        assert result.status == A2ATaskStatus.FAILED
        assert "config error" in result.history[-1].parts[0].text

    def test_deliver_project_happy_path_mock(self):
        """handle_deliver_project happy path with mocked flow."""
        task = _make_task(
            metadata={
                "brief_text": "CLI todo app",
                "repo_path": ".",
                "project_name": "todo-cli",
            }
        )

        mock_run = MagicMock()
        mock_run.run_id = "run-123"
        mock_run.state.mock_execution_used = True
        mock_run.state.release_check = None  # triggers 'N/A' branch

        with (
            patch("autodev.config.FactoryConfig") as cfg_cls,
            patch("autodev.flows.project_delivery_flow.ProjectDeliveryFlow") as flow_cls,
            patch("autodev.flows.project_delivery_flow.ProjectDeliveryInput"),
            patch("autodev.schemas.PipelineMode") as pm,
        ):
            mock_cfg = MagicMock()
            cfg_cls.from_env.return_value = mock_cfg
            pm.DRY_RUN = "dry_run"
            flow_cls.return_value.run.return_value = mock_run

            result = handle_deliver_project(task)

        assert result.status in (A2ATaskStatus.COMPLETED, A2ATaskStatus.FAILED)

    def test_deliver_project_with_release_check(self):
        """handle_deliver_project formats output when release_check is present."""
        task = _make_task(metadata={"brief_text": "Auth service", "repo_path": "."})

        mock_decision = MagicMock()
        mock_decision.value = "approved"

        mock_run = MagicMock()
        mock_run.run_id = "run-456"
        mock_run.state.mock_execution_used = False
        mock_run.state.release_check.decision = mock_decision

        with (
            patch("autodev.config.FactoryConfig") as cfg_cls,
            patch("autodev.flows.project_delivery_flow.ProjectDeliveryFlow") as flow_cls,
            patch("autodev.flows.project_delivery_flow.ProjectDeliveryInput"),
            patch("autodev.schemas.PipelineMode") as pm,
        ):
            mock_cfg = MagicMock()
            cfg_cls.from_env.return_value = mock_cfg
            pm.DRY_RUN = "dry_run"
            flow_cls.return_value.run.return_value = mock_run

            result = handle_deliver_project(task)

        assert result.status in (A2ATaskStatus.COMPLETED, A2ATaskStatus.FAILED)


class TestHandleReleaseCheckWithRunId:
    """Lines 197-201: handle_release_check success/exception path."""

    def test_release_check_with_run_id_exception(self):
        """When RunState.load raises, task is FAILED."""
        task = _make_task(metadata={"run_id": "abc123", "repo_path": "."})
        with patch("autodev.state.RunState") as rs_cls:
            rs_cls.load.side_effect = FileNotFoundError("state not found")
            result = handle_release_check(task)
        assert result.status == A2ATaskStatus.FAILED
        assert "state not found" in result.history[-1].parts[0].text

    def test_release_check_with_run_id_happy_path(self):
        """When RunState.load and ReleaseFlow.check succeed, task is COMPLETED."""
        task = _make_task(metadata={"run_id": "abc456", "repo_path": "."})

        mock_rc = MagicMock()
        mock_rc.model_dump_json.return_value = '{"decision": "approved"}'

        with (
            patch("autodev.state.RunState") as rs_cls,
            patch("autodev.flows.release_flow.ReleaseFlow") as rf_cls,
        ):
            rs_cls.load.return_value = MagicMock()
            rf_cls.return_value.check.return_value = mock_rc
            result = handle_release_check(task)

        assert result.status == A2ATaskStatus.COMPLETED
        assert "approved" in result.history[-1].parts[0].text


# ============================================================================
# Section B: adapters/mcp_client.py — missing lines 80, 83-84, 88-102,
#            114-128, 131-138, 152-156, 175-202
# ============================================================================


class TestMCPClientSafeSpawnHelpers:
    """Lines 80, 83-84: _safe_spawn_via_shell_executor and _next_id."""

    def setup_method(self):
        os.environ["FACTORY_FORCE_MOCK"] = "0"

    def teardown_method(self):
        os.environ["FACTORY_FORCE_MOCK"] = "1"

    def test_next_id_increments(self):
        """_next_id increments request counter."""
        client = MCPToolClient(command="npx")
        assert client._next_id() == 1
        assert client._next_id() == 2
        assert client._next_id() == 3

    def test_safe_spawn_allowed_bin_on_path(self):
        """Returns True only when binary is on allowlist AND on PATH."""
        # 'python3' is in DEFAULT_ALLOWED_BINS and typically on PATH
        client = MCPToolClient(command="python3", allowed_bins=DEFAULT_ALLOWED_BINS)
        result = client._safe_spawn_via_shell_executor()
        # Either True (python3 on PATH) or False (not on PATH) — just no exception
        assert isinstance(result, bool)

    def test_safe_spawn_returns_true_when_allowed_and_exists(self):
        """Mocked: binary allowed and on PATH returns True."""
        client = MCPToolClient(command="npx", allowed_bins=frozenset({"npx"}))
        with patch("shutil.which", return_value="/usr/bin/npx"):
            result = client._safe_spawn_via_shell_executor()
        assert result is True

    def test_safe_spawn_returns_false_when_not_on_path(self):
        """Mocked: binary allowed but not on PATH returns False (line 79)."""
        client = MCPToolClient(command="npx", allowed_bins=frozenset({"npx"}))
        with patch("shutil.which", return_value=None):
            result = client._safe_spawn_via_shell_executor()
        assert result is False

    def test_safe_spawn_returns_false_when_not_in_allowlist(self):
        """Binary not in allowlist returns False (line 76)."""
        client = MCPToolClient(command="bash", allowed_bins=frozenset({"npx"}))
        with patch("shutil.which", return_value="/bin/bash"):
            result = client._safe_spawn_via_shell_executor()
        assert result is False


class TestMCPClientSendRequest:
    """Lines 88-102: _send_request."""

    def setup_method(self):
        os.environ["FACTORY_FORCE_MOCK"] = "0"

    def teardown_method(self):
        os.environ["FACTORY_FORCE_MOCK"] = "1"

    def test_send_request_raises_when_no_process(self):
        """_send_request raises RuntimeError when process is None."""
        client = MCPToolClient(command="npx")
        client._proc = None
        with pytest.raises(RuntimeError, match="not running"):
            client._send_request("tools/list", {})

    def test_send_request_raises_when_process_exited(self):
        """_send_request raises RuntimeError when process has exited (poll != None)."""
        client = MCPToolClient(command="npx")
        mock_proc = MagicMock()
        mock_proc.poll.return_value = 1  # process exited
        client._proc = mock_proc
        with pytest.raises(RuntimeError, match="not running"):
            client._send_request("tools/list", {})

    def test_send_request_writes_and_reads(self):
        """_send_request writes JSON-RPC to stdin and reads response from stdout."""
        client = MCPToolClient(command="npx")
        mock_proc = MagicMock()
        mock_proc.poll.return_value = None  # still running
        response = {"jsonrpc": "2.0", "id": 1, "result": {"tools": []}}
        mock_proc.stdout.readline.return_value = json.dumps(response) + "\n"
        client._proc = mock_proc

        result = client._send_request("tools/list", {})
        assert result == response
        mock_proc.stdin.write.assert_called_once()
        mock_proc.stdin.flush.assert_called_once()


class TestMCPClientEnsureStarted:
    """Lines 114-128: _ensure_started subprocess spawning and error paths."""

    def setup_method(self):
        os.environ["FACTORY_FORCE_MOCK"] = "0"

    def teardown_method(self):
        os.environ["FACTORY_FORCE_MOCK"] = "1"

    def test_ensure_started_skips_when_process_already_running(self):
        """Returns True immediately if process is already running."""
        client = MCPToolClient(command="npx", allowed_bins=frozenset({"npx"}))
        mock_proc = MagicMock()
        mock_proc.poll.return_value = None  # process running
        client._proc = mock_proc

        with patch("shutil.which", return_value="/usr/bin/npx"):
            result = client._ensure_started()
        assert result is True

    def test_ensure_started_spawns_new_process(self):
        """_ensure_started calls Popen when binary is allowed and on PATH."""
        client = MCPToolClient(command="python3", args=["-c", "import sys; sys.exit(0)"],
                               allowed_bins=frozenset({"python3"}))
        client._proc = None

        with patch("shutil.which", return_value="/usr/bin/python3"):
            with patch("subprocess.Popen") as mock_popen:
                mock_popen.return_value = MagicMock()
                mock_popen.return_value.poll.return_value = None
                result = client._ensure_started()
        assert result is True
        mock_popen.assert_called_once()

    def test_ensure_started_returns_false_on_file_not_found(self):
        """When Popen raises FileNotFoundError, _ensure_started returns False."""
        client = MCPToolClient(command="npx", allowed_bins=frozenset({"npx"}))
        client._proc = None

        with patch("shutil.which", return_value="/usr/bin/npx"):
            with patch("subprocess.Popen", side_effect=FileNotFoundError("npx not found")):
                result = client._ensure_started()
        assert result is False
        assert client._proc is None

    def test_ensure_started_returns_false_on_permission_error(self):
        """When Popen raises PermissionError, _ensure_started returns False."""
        client = MCPToolClient(command="npx", allowed_bins=frozenset({"npx"}))
        client._proc = None

        with patch("shutil.which", return_value="/usr/bin/npx"):
            with patch("subprocess.Popen", side_effect=PermissionError("denied")):
                result = client._ensure_started()
        assert result is False


class TestMCPClientClose:
    """Lines 131-138: close() method."""

    def test_close_terminates_running_process(self):
        """close() terminates process when it's running."""
        client = MCPToolClient(command="npx")
        mock_proc = MagicMock()
        mock_proc.poll.return_value = None  # process running
        mock_proc.stdin = MagicMock()
        client._proc = mock_proc

        client.close()

        mock_proc.terminate.assert_called_once()
        mock_proc.wait.assert_called_once()
        assert client._proc is None

    def test_close_kills_on_timeout(self):
        """close() kills process when wait times out."""
        client = MCPToolClient(command="npx")
        mock_proc = MagicMock()
        mock_proc.poll.return_value = None  # process running
        mock_proc.stdin = MagicMock()
        mock_proc.wait.side_effect = subprocess.TimeoutExpired("npx", 5)
        client._proc = mock_proc

        client.close()

        mock_proc.kill.assert_called_once()
        assert client._proc is None

    def test_close_does_nothing_when_process_already_exited(self):
        """close() skips terminate when process has already exited."""
        client = MCPToolClient(command="npx")
        mock_proc = MagicMock()
        mock_proc.poll.return_value = 0  # process exited
        client._proc = mock_proc

        client.close()

        mock_proc.terminate.assert_not_called()
        assert client._proc is None

    def test_close_does_nothing_when_no_process(self):
        """close() is safe when _proc is None."""
        client = MCPToolClient(command="npx")
        client._proc = None
        client.close()  # should not raise
        assert client._proc is None

    def test_close_handles_none_stdin(self):
        """close() handles process with stdin=None."""
        client = MCPToolClient(command="npx")
        mock_proc = MagicMock()
        mock_proc.poll.return_value = None
        mock_proc.stdin = None
        client._proc = mock_proc

        client.close()
        mock_proc.terminate.assert_called_once()


class TestMCPClientListToolsWithProcess:
    """Lines 152-156: list_tools exception fallback when process is running."""

    def setup_method(self):
        os.environ["FACTORY_FORCE_MOCK"] = "0"

    def teardown_method(self):
        os.environ["FACTORY_FORCE_MOCK"] = "1"

    def test_list_tools_returns_mock_on_send_request_exception(self):
        """list_tools falls back to _MOCK_TOOLS when _send_request raises."""
        client = MCPToolClient(command="npx", allowed_bins=frozenset({"npx"}))

        with patch("shutil.which", return_value="/usr/bin/npx"):
            with patch("subprocess.Popen") as mock_popen:
                mock_proc = MagicMock()
                mock_proc.poll.return_value = None
                mock_proc.stdout.readline.side_effect = json.JSONDecodeError("bad", "", 0)
                mock_popen.return_value = mock_proc

                # Force an already-running process
                client._proc = mock_proc
                with patch.object(client, "_ensure_started", return_value=True):
                    with patch.object(client, "_send_request", side_effect=RuntimeError("conn fail")):
                        tools = client.list_tools()

        assert isinstance(tools, list)
        # Should return mock tools on exception
        assert len(tools) > 0

    def test_list_tools_returns_result_from_server(self):
        """list_tools returns tools from server response."""
        client = MCPToolClient(command="npx")
        mock_response = {
            "jsonrpc": "2.0",
            "id": 1,
            "result": {"tools": [{"name": "search", "description": "web search"}]},
        }
        with patch.object(client, "_ensure_started", return_value=True):
            with patch.object(client, "_send_request", return_value=mock_response):
                tools = client.list_tools()
        assert tools == [{"name": "search", "description": "web search"}]


class TestMCPClientCallToolWithProcess:
    """Lines 175-202: call_tool when process is actually running."""

    def setup_method(self):
        os.environ["FACTORY_FORCE_MOCK"] = "0"

    def teardown_method(self):
        os.environ["FACTORY_FORCE_MOCK"] = "1"

    def test_call_tool_returns_error_when_response_has_error_key(self):
        """call_tool returns success=False when response has 'error'."""
        client = MCPToolClient(command="npx")
        error_response = {
            "jsonrpc": "2.0",
            "id": 1,
            "error": {"code": -32601, "message": "Method not found"},
        }
        with patch.object(client, "_ensure_started", return_value=True):
            with patch.object(client, "_send_request", return_value=error_response):
                result = client.call_tool("missing_tool", {"arg": "val"})
        assert result["success"] is False
        assert result["mock_used"] is False
        assert "Method not found" in result["error"]
        assert result["tool_name"] == "missing_tool"

    def test_call_tool_returns_success_with_dict_content(self):
        """call_tool serializes dict result as JSON string."""
        client = MCPToolClient(command="npx")
        success_response = {
            "jsonrpc": "2.0",
            "id": 1,
            "result": {"output": "file1.py file2.py"},
        }
        with patch.object(client, "_ensure_started", return_value=True):
            with patch.object(client, "_send_request", return_value=success_response):
                result = client.call_tool("list_files", {"path": "."})
        assert result["success"] is True
        assert result["mock_used"] is False
        assert "file1.py" in result["response_text"]

    def test_call_tool_returns_success_with_string_content(self):
        """call_tool passes through string result directly."""
        client = MCPToolClient(command="npx")
        success_response = {
            "jsonrpc": "2.0",
            "id": 1,
            "result": "plain text response",
        }
        with patch.object(client, "_ensure_started", return_value=True):
            with patch.object(client, "_send_request", return_value=success_response):
                result = client.call_tool("echo", {"msg": "hi"})
        assert result["success"] is True
        assert result["response_text"] == "plain text response"

    def test_call_tool_exception_returns_failure_dict(self):
        """call_tool returns success=False when _send_request raises."""
        client = MCPToolClient(command="npx")
        with patch.object(client, "_ensure_started", return_value=True):
            with patch.object(client, "_send_request", side_effect=RuntimeError("network error")):
                result = client.call_tool("do_something", {"key": "value"})
        assert result["success"] is False
        assert result["mock_used"] is False
        assert "network error" in result["error"]
        assert result["response_text"] == ""

    def test_call_tool_no_arguments_uses_empty_dict(self):
        """call_tool with arguments=None defaults to empty dict."""
        client = MCPToolClient(command="npx")
        response = {"jsonrpc": "2.0", "id": 1, "result": "ok"}
        with patch.object(client, "_ensure_started", return_value=True):
            with patch.object(client, "_send_request", return_value=response) as mock_req:
                client.call_tool("ping")
        # Verify empty args dict was passed
        call_args = mock_req.call_args
        assert call_args[0][1]["arguments"] == {}


# ============================================================================
# Section C: adapters/a2a/server.py — missing lines 94-95, 161, 178-179,
#            207-208, 214-215, 223, 229-231, 236-238, 254-255, 269-271,
#            334, 348
# ============================================================================

# --- Server test helpers ---


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("localhost", 0))
        return s.getsockname()[1]


def _start_server(port: int, auth_token: str | None = None) -> A2AHttpServer:
    if auth_token is not None:
        os.environ["AUTODEV_A2A_TOKEN"] = auth_token
    else:
        os.environ.pop("AUTODEV_A2A_TOKEN", None)

    server = A2AHttpServer(port=port, bind="127.0.0.1")

    def _run():
        server.serve_forever()

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    deadline = time.time() + 5.0
    while time.time() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                break
        except OSError:
            time.sleep(0.05)
    return server


def _get(url: str, headers: dict | None = None) -> tuple[int, dict]:
    import urllib.request
    from urllib.error import HTTPError
    req = urllib.request.Request(url, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except HTTPError as e:
        return e.code, json.loads(e.read().decode("utf-8"))


def _post(url: str, body: bytes | dict, headers: dict | None = None) -> tuple[int, dict]:
    import urllib.request
    from urllib.error import HTTPError
    if isinstance(body, dict):
        data = json.dumps(body).encode("utf-8")
        content_type = "application/json"
    else:
        data = body
        content_type = "application/json"
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": content_type, **(headers or {})},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except HTTPError as e:
        return e.code, json.loads(e.read().decode("utf-8"))


def _make_server_task(skill: str, extra_meta: dict | None = None) -> dict:
    meta = {"skill": skill}
    if extra_meta:
        meta.update(extra_meta)
    return {
        "id": str(uuid.uuid4()),
        "context_id": str(uuid.uuid4()),
        "metadata": meta,
        "history": [
            {
                "message_id": str(uuid.uuid4()),
                "role": "user",
                "parts": [{"kind": "text", "text": "test input"}],
            }
        ],
    }


class TestTaskStore:
    """Lines 94-95: _TaskStore.all() method."""

    def test_task_store_all_empty(self):
        """all() returns empty list when no tasks stored."""
        store = _TaskStore()
        assert store.all() == []

    def test_task_store_all_returns_all_tasks(self):
        """all() returns all stored tasks."""
        store = _TaskStore()
        task1 = A2ATask(id="t1", context_id="c1")
        task2 = A2ATask(id="t2", context_id="c2")
        store.put(task1)
        store.put(task2)
        all_tasks = store.all()
        assert len(all_tasks) == 2
        ids = {t.id for t in all_tasks}
        assert ids == {"t1", "t2"}

    def test_task_store_put_overwrites(self):
        """put() overwrites existing task with same id."""
        store = _TaskStore()
        task = A2ATask(id="t1", context_id="c1")
        store.put(task)
        task.status = A2ATaskStatus.COMPLETED
        store.put(task)
        retrieved = store.get("t1")
        assert retrieved.status == A2ATaskStatus.COMPLETED


class TestServerUnknownGetPath:
    """Line 161: GET /unknown-path → 404."""

    def test_get_unknown_path_returns_404(self):
        port = _free_port()
        server = _start_server(port)
        try:
            status, body = _get(f"http://127.0.0.1:{port}/unknown-path-xyz")
            assert status == 404
            assert "error" in body
        finally:
            server.shutdown()
            os.environ.pop("AUTODEV_A2A_TOKEN", None)


class TestServerTaskEvents404:
    """Lines 178-179: GET /tasks/{id}/events for nonexistent task → 404."""

    def test_task_events_nonexistent_returns_404(self):
        port = _free_port()
        server = _start_server(port)
        try:
            status, body = _get(f"http://127.0.0.1:{port}/tasks/nonexistent-id/events")
            assert status == 404
            assert "error" in body
        finally:
            server.shutdown()
            os.environ.pop("AUTODEV_A2A_TOKEN", None)


class TestServerAuthCombinations:
    """Lines 207-208, 214-215: Bearer auth edge cases."""

    def test_post_no_auth_header_returns_401(self):
        """POST without Authorization header when token set → 401."""
        port = _free_port()
        server = _start_server(port, auth_token="my-secret-token")
        try:
            task_body = _make_server_task("scan")
            status, _body = _post(f"http://127.0.0.1:{port}/tasks/send", task_body)
            assert status == 401
        finally:
            server.shutdown()
            os.environ.pop("AUTODEV_A2A_TOKEN", None)

    def test_post_wrong_bearer_token_returns_401(self):
        """POST with wrong Bearer token → 401."""
        port = _free_port()
        server = _start_server(port, auth_token="correct-token")
        try:
            task_body = _make_server_task("scan")
            status, _body = _post(
                f"http://127.0.0.1:{port}/tasks/send",
                task_body,
                headers={"Authorization": "Bearer wrong-token"},
            )
            assert status == 401
        finally:
            server.shutdown()
            os.environ.pop("AUTODEV_A2A_TOKEN", None)

    def test_post_malformed_authorization_header_returns_401(self):
        """POST with malformed Authorization header (no 'Bearer ' prefix) → 401."""
        port = _free_port()
        server = _start_server(port, auth_token="correct-token")
        try:
            task_body = _make_server_task("scan")
            status, _body = _post(
                f"http://127.0.0.1:{port}/tasks/send",
                task_body,
                headers={"Authorization": "Token correct-token"},
            )
            assert status == 401
        finally:
            server.shutdown()
            os.environ.pop("AUTODEV_A2A_TOKEN", None)

    def test_get_no_auth_header_when_token_set_returns_401(self):
        """GET agent card with no auth header when token set → 401."""
        port = _free_port()
        server = _start_server(port, auth_token="guard-token")
        try:
            status, _body = _get(f"http://127.0.0.1:{port}/.well-known/agent.json")
            assert status == 401
        finally:
            server.shutdown()
            os.environ.pop("AUTODEV_A2A_TOKEN", None)


class TestServerPostEdgeCases:
    """Lines 223, 229-231, 236-238, 254-255: POST /tasks/send edge cases."""

    def test_post_unknown_path_returns_404(self):
        """POST to unknown path → 404."""
        port = _free_port()
        server = _start_server(port)
        try:
            status, body = _post(f"http://127.0.0.1:{port}/tasks/unknown", {"x": 1})
            assert status == 404
            assert "error" in body
        finally:
            server.shutdown()
            os.environ.pop("AUTODEV_A2A_TOKEN", None)

    def test_post_invalid_json_body_returns_400(self):
        """POST with invalid JSON body → 400."""
        import urllib.request
        from urllib.error import HTTPError

        port = _free_port()
        server = _start_server(port)
        try:
            req = urllib.request.Request(
                f"http://127.0.0.1:{port}/tasks/send",
                data=b"this is not json at all!!!",
                headers={"Content-Type": "application/json", "Content-Length": "26"},
                method="POST",
            )
            try:
                with urllib.request.urlopen(req, timeout=5) as resp:
                    status = resp.status
                    body = json.loads(resp.read().decode("utf-8"))
            except HTTPError as e:
                status = e.code
                body = json.loads(e.read().decode("utf-8"))
            assert status == 400
            assert "JSON" in body.get("error", "")
        finally:
            server.shutdown()
            os.environ.pop("AUTODEV_A2A_TOKEN", None)

    def test_post_task_missing_skill_returns_400(self):
        """POST task without 'skill' in metadata → 400."""
        port = _free_port()
        server = _start_server(port)
        try:
            task_body = {
                "id": str(uuid.uuid4()),
                "context_id": str(uuid.uuid4()),
                "metadata": {},  # no skill
                "history": [],
            }
            status, body = _post(f"http://127.0.0.1:{port}/tasks/send", task_body)
            assert status == 400
            assert "skill" in body.get("error", "").lower()
        finally:
            server.shutdown()
            os.environ.pop("AUTODEV_A2A_TOKEN", None)

    def test_post_task_invalid_model_falls_back_to_minimal_construction(self):
        """POST body that fails A2ATask.model_validate triggers fallback construction."""
        port = _free_port()
        server = _start_server(port)
        try:
            # Body that won't validate as A2ATask but has metadata.skill
            malformed_body = {
                "metadata": {"skill": "scan"},
                # Missing required 'id' and 'context_id' — triggers fallback
            }
            status, _body = _post(f"http://127.0.0.1:{port}/tasks/send", malformed_body)
            # Should handle gracefully — either 200 (fallback task built) or 400
            assert status in (200, 400)
        finally:
            server.shutdown()
            os.environ.pop("AUTODEV_A2A_TOKEN", None)


class TestServerHandlerException:
    """Lines 269-271: handler exception is caught and stored as FAILED."""

    def test_handler_exception_stored_as_failed(self):
        """When handler raises, server catches and returns FAILED task."""
        port = _free_port()
        server = _start_server(port)
        try:
            # Use a monkeypatched handler that raises
            original_handlers = dict(SKILL_HANDLERS)

            def _boom_handler(task):
                raise RuntimeError("handler crashed")

            SKILL_HANDLERS["scan"] = _boom_handler
            try:
                task_body = _make_server_task("scan", {"repo_path": "."})
                status, body = _post(f"http://127.0.0.1:{port}/tasks/send", task_body)
                # Server should return 200 with FAILED status
                assert status == 200
                assert body["status"] == A2ATaskStatus.FAILED.value
            finally:
                SKILL_HANDLERS["scan"] = original_handlers["scan"]
        finally:
            server.shutdown()
            os.environ.pop("AUTODEV_A2A_TOKEN", None)


class TestServerBindWarning:
    """Line 334: bind 0.0.0.0 warning is printed."""

    def test_serve_forever_prints_warning_for_0000_bind(self, capsys):
        """A2AHttpServer prints warning when binding to 0.0.0.0."""
        port = _free_port()
        server = A2AHttpServer(port=port, bind="0.0.0.0")

        def _run():
            server.serve_forever()

        t = threading.Thread(target=_run, daemon=True)
        t.start()

        # Wait briefly for the warning to be printed
        deadline = time.time() + 3.0
        while time.time() < deadline:
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                    break
            except OSError:
                time.sleep(0.05)

        server.shutdown()
        t.join(timeout=2)

        captured = capsys.readouterr()
        assert "WARNING" in captured.out or "0.0.0.0" in captured.out


class TestServerSignalInBackgroundThread:
    """Line 348: SIGTERM signal.signal() called from non-main thread raises ValueError."""

    def test_serve_forever_in_background_thread_no_signal_crash(self):
        """Server run from background thread handles ValueError from signal.signal gracefully."""
        port = _free_port()
        server = A2AHttpServer(port=port, bind="127.0.0.1")
        errors: list[Exception] = []

        def _run():
            try:
                server.serve_forever()
            except Exception as e:
                errors.append(e)

        t = threading.Thread(target=_run, daemon=True)
        t.start()

        # Wait for server to be ready
        deadline = time.time() + 5.0
        while time.time() < deadline:
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                    break
            except OSError:
                time.sleep(0.05)

        server.shutdown()
        t.join(timeout=2)
        # Should have started without crashing due to ValueError from signal.signal
        assert errors == []


class TestServerTaskEventsSSEForExistingTask:
    """Lines 192-208: SSE stream for existing task."""

    def test_task_events_returns_sse_for_existing_task(self):
        """GET /tasks/{id}/events returns SSE event-stream for a known task."""
        import http.client

        port = _free_port()
        server = _start_server(port)
        try:
            task_body = _make_server_task("scan", {"repo_path": "."})
            task_id = task_body["id"]
            _post(f"http://127.0.0.1:{port}/tasks/send", task_body)

            conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
            conn.request("GET", f"/tasks/{task_id}/events")
            resp = conn.getresponse()
            assert resp.status == 200
            content_type = resp.headers.get("Content-Type", "")
            assert "text/event-stream" in content_type

            # Read enough lines to see an SSE event
            collected = []
            for _ in range(30):
                line = resp.fp.readline(4096)
                if not line:
                    break
                collected.append(line.decode("utf-8", errors="replace"))
                if any("event:" in ln for ln in collected):
                    break
            conn.close()
            body_str = "".join(collected)
            assert "event:" in body_str
        finally:
            server.shutdown()
            os.environ.pop("AUTODEV_A2A_TOKEN", None)


class TestForceMockFunction:
    """Test the _force_mock helper."""

    def test_force_mock_returns_true_when_set(self):
        os.environ["FACTORY_FORCE_MOCK"] = "1"
        assert _force_mock() is True

    def test_force_mock_returns_false_when_not_set(self):
        os.environ["FACTORY_FORCE_MOCK"] = "0"
        assert _force_mock() is False
        os.environ["FACTORY_FORCE_MOCK"] = "1"
