"""R10-F: Coverage backfill for claude_code_executor, codex_cli_executor, _fs_observer.

Targets:
  claude_code_executor  67% → ≥90%  (lines 50, 55-82, 103, 154-155, 173-188, 221-222)
  codex_cli_executor    88% → ≥90%  (lines 58, 84-85, 89-90, 113, 160, 183-184, 213-214, 247-248, 260)
  _fs_observer          80% → ≥90%  (lines 33-34, 49, 56, 59-60, 74-75, 112-115)
"""
from __future__ import annotations

import os
import subprocess
from unittest.mock import MagicMock, patch

from autodev.config import ClaudeCodeExecutorConfig, CodexCliExecutorConfig
from autodev.executors._fs_observer import (
    _git_status_set,
    _is_git_repo,
    _mtime_snapshot,
    diff_repo,
    snapshot_repo,
)
from autodev.executors.claude_code_executor import (
    ClaudeCodeExecutor,
    _parse_claude_inner_steps,
)
from autodev.executors.codex_cli_executor import (
    CodexCliExecutor,
    _parse_inner_steps,
    _sandbox_args_for,
)
from autodev.schemas import (
    ExecutionRequest,
    Language,
    PipelineMode,
    TaskType,
)

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _req(repo_path: str, *, prompt: str = "write a test", mode: PipelineMode = PipelineMode.DRY_RUN) -> ExecutionRequest:
    return ExecutionRequest(
        task_id="T-r10",
        milestone_id="M0",
        repo_path=repo_path,
        prompt=prompt,
        language=Language.PYTHON,
        mode=mode,
        task_type=TaskType.FEATURE,
    )


def _make_proc(returncode: int = 0, stdout: str = "", stderr: str = "") -> MagicMock:
    proc = MagicMock()
    proc.returncode = returncode
    proc.stdout = stdout
    proc.stderr = stderr
    return proc


# ===========================================================================
# _fs_observer
# ===========================================================================

class TestIsGitRepo:
    """Covers lines 33-34 (exception path), plus happy + unhappy paths."""

    def test_returns_true_for_git_repo(self, tmp_path):
        # Initialise a real git repo so the call succeeds.
        subprocess.run(["git", "init", str(tmp_path)], capture_output=True, check=True)
        assert _is_git_repo(str(tmp_path)) is True

    def test_returns_false_for_non_git_dir(self, tmp_path):
        assert _is_git_repo(str(tmp_path)) is False

    def test_exception_returns_false(self, tmp_path):
        # Force subprocess.run to raise; covers the except branch (lines 33-34).
        with patch("autodev.executors._fs_observer.subprocess.run", side_effect=OSError("boom")):
            assert _is_git_repo(str(tmp_path)) is False


class TestGitStatusSet:
    """Covers lines 49 (nonzero returncode), 56 (rename arrow), 59-60 (exception)."""

    def test_nonzero_returncode_returns_empty(self, tmp_path):
        # Line 49: returncode != 0 → return set()
        mock_r = MagicMock(returncode=1, stdout="")
        with patch("autodev.executors._fs_observer.subprocess.run", return_value=mock_r):
            result = _git_status_set(str(tmp_path))
        assert result == set()

    def test_rename_arrow_parsed(self, tmp_path):
        # Line 56: " -> " in rel → take the rhs
        stdout = "R  old_name.py -> new_name.py\n"
        mock_r = MagicMock(returncode=0, stdout=stdout)
        with patch("autodev.executors._fs_observer.subprocess.run", return_value=mock_r):
            result = _git_status_set(str(tmp_path))
        assert "new_name.py" in result
        assert "old_name.py" not in result

    def test_exception_returns_empty(self, tmp_path):
        # Lines 59-60: any exception → return set()
        with patch("autodev.executors._fs_observer.subprocess.run", side_effect=RuntimeError("fail")):
            result = _git_status_set(str(tmp_path))
        assert result == set()

    def test_normal_changed_files(self, tmp_path):
        stdout = " M src/foo.py\n?? new_file.py\n"
        mock_r = MagicMock(returncode=0, stdout=stdout)
        with patch("autodev.executors._fs_observer.subprocess.run", return_value=mock_r):
            result = _git_status_set(str(tmp_path))
        assert "src/foo.py" in result
        assert "new_file.py" in result


class TestMtimeSnapshot:
    """Covers lines 74-75 (OSError stat on individual files)."""

    def test_skips_unreadable_files(self, tmp_path):
        # Broken symlink → os.stat raises OSError, covering lines 74-75.
        (tmp_path / "readable.py").write_text("ok")
        os.symlink("/nonexistent/path/target.py", tmp_path / "broken_link.py")

        result = _mtime_snapshot(str(tmp_path))

        rel_paths = {token.rsplit(":", 1)[0] for token in result}
        # readable.py must be captured; broken symlink must be silently skipped.
        assert "readable.py" in rel_paths
        assert "broken_link.py" not in rel_paths

    def test_skips_hidden_cache_dirs(self, tmp_path):
        cache_dir = tmp_path / "__pycache__"
        cache_dir.mkdir()
        (cache_dir / "compiled.pyc").write_text("bytes")
        (tmp_path / "real.py").write_text("code")

        result = _mtime_snapshot(str(tmp_path))
        rel_paths = {token.rsplit(":", 1)[0] for token in result}
        assert "real.py" in rel_paths
        # __pycache__/compiled.pyc must be excluded
        assert not any("pycache" in p for p in rel_paths)


class TestDiffRepo:
    """Covers lines 112-115 (colon handling in diff_repo)."""

    def test_git_mode_tokens_no_colon(self):
        before = {"a.py", "b.py"}
        after = {"a.py", "b.py", "c.py"}
        assert diff_repo(before, after) == ["c.py"]

    def test_mtime_mode_numeric_suffix_extracted(self):
        # mtime tokens: "path:mtime_ns"
        before: set[str] = set()
        after = {"src/foo.py:1716700000000000000"}
        result = diff_repo(before, after)
        assert result == ["src/foo.py"]

    def test_non_numeric_colon_keeps_full_token(self):
        # Lines 112-115: colon present but parts[1] is not int → keep full token
        before: set[str] = set()
        after = {"path/with:colon"}  # not a numeric mtime
        result = diff_repo(before, after)
        assert result == ["path/with:colon"]

    def test_empty_diff(self):
        before = {"x.py:111"}
        after = {"x.py:111"}
        assert diff_repo(before, after) == []

    def test_snapshot_repo_non_git(self, tmp_path):
        # snapshot_repo falls through to mtime path when not a git repo.
        (tmp_path / "hello.py").write_text("print('hi')")
        snap = snapshot_repo(str(tmp_path))
        assert any("hello.py" in t for t in snap)


# ===========================================================================
# _parse_claude_inner_steps
# ===========================================================================

class TestParseClaudeInnerSteps:
    """Covers lines 50, 55-82 of claude_code_executor."""

    def test_empty_string_returns_empty_list(self):
        assert _parse_claude_inner_steps("") == []

    def test_blank_lines_skipped(self):
        # Line 50: blank lines are continued over.
        jsonl = '\n\n{"type":"text","summary":"done"}\n\n'
        steps = _parse_claude_inner_steps(jsonl)
        assert len(steps) == 1
        assert steps[0].kind == "text"

    def test_malformed_json_returns_empty(self):
        # Line 54: JSONDecodeError → return []
        result = _parse_claude_inner_steps("not-json\n")
        assert result == []

    def test_malformed_after_valid_returns_empty(self):
        jsonl = '{"type":"assistant","summary":"ok"}\nnot-json\n'
        result = _parse_claude_inner_steps(jsonl)
        assert result == []

    def test_summary_field(self):
        # Line 62-63
        jsonl = '{"type":"result","summary":"task complete"}\n'
        steps = _parse_claude_inner_steps(jsonl)
        assert steps[0].content_summary == "task complete"

    def test_content_field_truncated(self):
        # Lines 64-65
        long_content = "x" * 300
        jsonl = f'{{"type":"text","content":"{long_content}"}}\n'
        steps = _parse_claude_inner_steps(jsonl)
        assert len(steps[0].content_summary) == 200

    def test_content_field_none(self):
        # Line 65: content is falsy → ""
        jsonl = '{"type":"text","content":""}\n'
        steps = _parse_claude_inner_steps(jsonl)
        assert steps[0].content_summary == ""

    def test_message_field(self):
        # Line 67
        jsonl = '{"type":"log","message":"some log entry"}\n'
        steps = _parse_claude_inner_steps(jsonl)
        assert steps[0].content_summary == "some log entry"

    def test_command_field(self):
        # Line 70
        jsonl = '{"type":"tool_use","command":"pytest tests/"}\n'
        steps = _parse_claude_inner_steps(jsonl)
        assert steps[0].command == "pytest tests/"

    def test_exit_code_valid(self):
        # Lines 72-73
        jsonl = '{"type":"tool_result","exit_code":0}\n'
        steps = _parse_claude_inner_steps(jsonl)
        assert steps[0].exit_code == 0

    def test_exit_code_invalid_type(self):
        # Line 74: int() raises TypeError/ValueError → skip
        jsonl = '{"type":"tool_result","exit_code":"bad"}\n'
        steps = _parse_claude_inner_steps(jsonl)
        assert steps[0].exit_code is None

    def test_duration_ms_valid(self):
        # Lines 77-78
        jsonl = '{"type":"tool_use","duration_ms":42}\n'
        steps = _parse_claude_inner_steps(jsonl)
        assert steps[0].duration_ms == 42

    def test_duration_ms_invalid(self):
        # Lines 79-80: int() fails → keep default 0
        jsonl = '{"type":"tool_use","duration_ms":"nope"}\n'
        steps = _parse_claude_inner_steps(jsonl)
        assert steps[0].duration_ms == 0

    def test_kind_falls_back_to_kind_key(self):
        # Line 55: obj.get("type", obj.get("kind", ""))
        jsonl = '{"kind":"assistant_response","summary":"ok"}\n'
        steps = _parse_claude_inner_steps(jsonl)
        assert steps[0].kind == "assistant_response"

    def test_multiple_valid_lines(self):
        jsonl = (
            '{"type":"assistant","summary":"thinking"}\n'
            '{"type":"tool_use","command":"ls"}\n'
            '{"type":"tool_result","exit_code":0}\n'
        )
        steps = _parse_claude_inner_steps(jsonl)
        assert len(steps) == 3
        assert steps[1].command == "ls"


# ===========================================================================
# ClaudeCodeExecutor
# ===========================================================================

class TestClaudeCodeExecutorIsAvailable:
    """Covers line 103 (FACTORY_FORCE_MOCK env var path)."""

    def test_force_mock_env_returns_false(self, tmp_path, monkeypatch):
        monkeypatch.setenv("FACTORY_FORCE_MOCK", "1")
        cfg = ClaudeCodeExecutorConfig(binary="echo")
        assert ClaudeCodeExecutor(cfg).is_available() is False

    def test_missing_binary_returns_false(self, monkeypatch):
        monkeypatch.delenv("FACTORY_FORCE_MOCK", raising=False)
        cfg = ClaudeCodeExecutorConfig(binary="__nonexistent_claude_bin__")
        assert ClaudeCodeExecutor(cfg).is_available() is False

    def test_existing_binary_returns_true(self, monkeypatch):
        monkeypatch.delenv("FACTORY_FORCE_MOCK", raising=False)
        cfg = ClaudeCodeExecutorConfig(binary="echo")
        assert ClaudeCodeExecutor(cfg).is_available() is True


class TestClaudeCodeExecutorFileNotFound:
    """Covers lines 173-186 (FileNotFoundError path)."""

    def test_missing_binary_execution_returns_cli_missing(self, tmp_path):
        cfg = ClaudeCodeExecutorConfig(
            binary="__no_such_claude__",
            command_template="__no_such_claude__ {prompt}",
        )
        res = ClaudeCodeExecutor(cfg).execute(_req(str(tmp_path)))
        assert res.success is False
        assert res.error_type == "cli_missing"
        assert res.exit_code == 127
        assert "__no_such_claude__" in res.stderr


class TestClaudeCodeExecutorTimeout:
    """Covers lines 187-200 (TimeoutExpired path)."""

    def test_timeout_returns_timeout_error(self, tmp_path):
        cfg = ClaudeCodeExecutorConfig(binary="echo", command_template="echo {prompt}")
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="echo", timeout=1)):
            res = ClaudeCodeExecutor(cfg).execute(_req(str(tmp_path)))
        assert res.success is False
        assert res.error_type == "timeout"
        assert res.exit_code == 124
        assert "timeout" in res.stderr.lower()


class TestClaudeCodeExecutorFsSnapshot:
    """Covers lines 154-155 (fs snapshot exception path)."""

    def test_snapshot_exception_does_not_crash(self, tmp_path):
        cfg = ClaudeCodeExecutorConfig(binary="echo", command_template="echo {prompt}")
        with patch("autodev.executors.claude_code_executor.snapshot_repo", side_effect=RuntimeError("disk error")):
            with patch("subprocess.run", return_value=_make_proc(returncode=0, stdout="", stderr="")):
                res = ClaudeCodeExecutor(cfg).execute(_req(str(tmp_path)))
        # Should succeed despite snapshot failure.
        assert res.success is True

    def test_post_snapshot_exception_does_not_crash(self, tmp_path):
        cfg = ClaudeCodeExecutorConfig(binary="echo", command_template="echo {prompt}")
        call_count = 0

        def snapshot_side_effect(path):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return set()
            raise RuntimeError("post snapshot error")

        with patch("autodev.executors.claude_code_executor.snapshot_repo", side_effect=snapshot_side_effect):
            with patch("subprocess.run", return_value=_make_proc(returncode=0, stdout="", stderr="")):
                res = ClaudeCodeExecutor(cfg).execute(_req(str(tmp_path)))
        assert res.success is True
        assert res.changed_files == []


class TestClaudeCodeExecutorUnsupportedArgs:
    """Covers lines 221-222 (unsupported_cli_args error type)."""

    def test_unknown_option_in_stderr_sets_error_type(self, tmp_path):
        cfg = ClaudeCodeExecutorConfig(binary="echo", command_template="echo {prompt}")
        with patch(
            "subprocess.run",
            return_value=_make_proc(returncode=1, stdout="", stderr="Error: Unknown option --output-format"),
        ):
            res = ClaudeCodeExecutor(cfg).execute(_req(str(tmp_path)))
        assert res.success is False
        assert res.error_type == "unsupported_cli_args"

    def test_non_zero_exit_sets_non_zero_exit_type(self, tmp_path):
        cfg = ClaudeCodeExecutorConfig(binary="echo", command_template="echo {prompt}")
        with patch(
            "subprocess.run",
            return_value=_make_proc(returncode=2, stdout="", stderr="some unrelated error"),
        ):
            res = ClaudeCodeExecutor(cfg).execute(_req(str(tmp_path)))
        assert res.success is False
        assert res.error_type == "non_zero_exit"


class TestClaudeCodeExecutorStreamJson:
    """Covers JSONL parsing integration via execute() (lines 55-82 indirectly)."""

    def test_valid_jsonl_inner_steps_captured(self, tmp_path):
        jsonl_output = '{"type":"assistant","summary":"I will write tests"}\n{"type":"tool_use","command":"pytest","exit_code":0}\n'
        cfg = ClaudeCodeExecutorConfig(binary="echo", command_template="echo {prompt}")
        with patch("subprocess.run", return_value=_make_proc(returncode=0, stdout=jsonl_output, stderr="")):
            res = ClaudeCodeExecutor(cfg).execute(_req(str(tmp_path)))
        assert res.success is True
        assert len(res.inner_steps) == 2
        assert res.inner_steps[0]["kind"] == "assistant"


# ===========================================================================
# _parse_inner_steps (codex)
# ===========================================================================

class TestParseInnerStepsCodex:
    """Covers lines 58, 84-85, 89-90 of codex_cli_executor."""

    def test_empty_string_returns_empty(self):
        assert _parse_inner_steps("") == []

    def test_blank_lines_skipped(self):
        # Line 58
        jsonl = '\n\n{"type":"text","summary":"ok"}\n\n'
        steps = _parse_inner_steps(jsonl)
        assert len(steps) == 1

    def test_malformed_json_returns_empty(self):
        assert _parse_inner_steps("not-json\n") == []

    def test_exit_code_invalid_type(self):
        # Lines 84-85
        jsonl = '{"type":"tool_result","exit_code":"bad"}\n'
        steps = _parse_inner_steps(jsonl)
        assert steps[0].exit_code is None

    def test_duration_ms_invalid(self):
        # Lines 89-90
        jsonl = '{"type":"tool_use","duration_ms":"nope"}\n'
        steps = _parse_inner_steps(jsonl)
        assert steps[0].duration_ms == 0

    def test_content_none_gives_empty(self):
        jsonl = '{"type":"text","content":""}\n'
        steps = _parse_inner_steps(jsonl)
        assert steps[0].content_summary == ""


# ===========================================================================
# CodexCliExecutor
# ===========================================================================

class TestCodexCliExecutorIsAvailable:
    """Covers line 113 (FACTORY_FORCE_MOCK for codex)."""

    def test_force_mock_returns_false(self, monkeypatch):
        monkeypatch.setenv("FACTORY_FORCE_MOCK", "1")
        cfg = CodexCliExecutorConfig(binary="echo")
        assert CodexCliExecutor(cfg).is_available() is False

    def test_missing_binary_returns_false(self, monkeypatch):
        monkeypatch.delenv("FACTORY_FORCE_MOCK", raising=False)
        cfg = CodexCliExecutorConfig(binary="__no_codex__")
        assert CodexCliExecutor(cfg).is_available() is False


class TestCodexCliExecutorSafetyRejection:
    """Covers line 160 (unsafe_prompt early return)."""

    def test_unsafe_prompt_rejected(self, tmp_path):
        cfg = CodexCliExecutorConfig(binary="echo", command_template="echo {prompt}")
        res = CodexCliExecutor(cfg).execute(_req(str(tmp_path), prompt="please rm -rf /"))
        assert res.success is False
        assert res.error_type == "unsafe_prompt"


class TestCodexCliExecutorFileNotFound:
    """Covers lines 183-184 (FileNotFoundError path for codex)."""

    def test_missing_binary_returns_cli_missing(self, tmp_path):
        cfg = CodexCliExecutorConfig(
            binary="__no_codex_ever__",
            command_template="__no_codex_ever__ exec {prompt}",
        )
        res = CodexCliExecutor(cfg).execute(_req(str(tmp_path)))
        assert res.success is False
        assert res.error_type == "cli_missing"
        assert res.exit_code == 127


class TestCodexCliExecutorTimeout:
    """Covers lines 213-214 (TimeoutExpired for codex)."""

    def test_timeout_returns_timeout_error(self, tmp_path):
        cfg = CodexCliExecutorConfig(binary="echo", command_template="echo exec {prompt}")
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="echo", timeout=1)):
            res = CodexCliExecutor(cfg).execute(_req(str(tmp_path)))
        assert res.success is False
        assert res.error_type == "timeout"
        assert res.exit_code == 124


class TestCodexCliExecutorFsSnapshot:
    """Covers lines 183-184 (pre-snapshot exception) and 247-248 (post-snapshot exception for codex)."""

    def test_pre_snapshot_exception_does_not_crash(self, tmp_path):
        # Lines 183-184: exception during pre-execution snapshot_repo call.
        cfg = CodexCliExecutorConfig(binary="echo", command_template="echo exec {prompt}")
        with patch("autodev.executors.codex_cli_executor.snapshot_repo", side_effect=RuntimeError("disk error")):
            with patch("subprocess.run", return_value=_make_proc(returncode=0, stdout="", stderr="")):
                res = CodexCliExecutor(cfg).execute(_req(str(tmp_path)))
        assert res.success is True

    def test_post_snapshot_exception_does_not_crash(self, tmp_path):
        cfg = CodexCliExecutorConfig(binary="echo", command_template="echo exec {prompt}")
        call_count = 0

        def snapshot_side_effect(path):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return set()
            raise RuntimeError("disk error")

        with patch("autodev.executors.codex_cli_executor.snapshot_repo", side_effect=snapshot_side_effect):
            with patch("subprocess.run", return_value=_make_proc(returncode=0, stdout="", stderr="")):
                res = CodexCliExecutor(cfg).execute(_req(str(tmp_path)))
        assert res.success is True
        assert res.changed_files == []


class TestCodexCliExecutorUnsupportedArgs:
    """Covers line 260 (unrecognized flag error_type)."""

    def test_unrecognized_flag_sets_error_type(self, tmp_path):
        cfg = CodexCliExecutorConfig(binary="echo", command_template="echo exec {prompt}")
        with patch(
            "subprocess.run",
            return_value=_make_proc(returncode=1, stdout="", stderr="error: unrecognized argument --json"),
        ):
            res = CodexCliExecutor(cfg).execute(_req(str(tmp_path)))
        assert res.success is False
        assert res.error_type == "unsupported_cli_args"

    def test_unknown_option_sets_error_type(self, tmp_path):
        cfg = CodexCliExecutorConfig(binary="echo", command_template="echo exec {prompt}")
        with patch(
            "subprocess.run",
            return_value=_make_proc(returncode=1, stdout="", stderr="unknown option: --sandbox"),
        ):
            res = CodexCliExecutor(cfg).execute(_req(str(tmp_path)))
        assert res.success is False
        assert res.error_type == "unsupported_cli_args"

    def test_generic_failure_sets_non_zero_exit(self, tmp_path):
        cfg = CodexCliExecutorConfig(binary="echo", command_template="echo exec {prompt}")
        with patch(
            "subprocess.run",
            return_value=_make_proc(returncode=1, stdout="", stderr="compilation failed"),
        ):
            res = CodexCliExecutor(cfg).execute(_req(str(tmp_path)))
        assert res.success is False
        assert res.error_type == "non_zero_exit"


class TestSandboxArgsFor:
    """Covers _sandbox_args_for helper."""

    def test_dry_run_gives_read_only(self):
        args = _sandbox_args_for(PipelineMode.DRY_RUN)
        assert args == ["--sandbox", "read-only"]

    def test_other_mode_gives_workspace_write(self):
        args = _sandbox_args_for(PipelineMode.APPLY)
        assert args == ["--sandbox", "workspace-write"]


class TestCodexBuildCommand:
    """Covers _build_command injection logic."""

    def test_json_flag_injected_when_absent(self, tmp_path):
        cfg = CodexCliExecutorConfig(
            binary="echo",
            command_template="codex exec {prompt}",
        )
        ex = CodexCliExecutor(cfg)
        req = _req(str(tmp_path))
        cmd_str, _argv = ex._build_command(req, "hello")
        assert "--json" in cmd_str

    def test_json_flag_not_duplicated_when_present(self, tmp_path):
        cfg = CodexCliExecutorConfig(
            binary="echo",
            command_template="codex exec --json {prompt}",
        )
        ex = CodexCliExecutor(cfg)
        req = _req(str(tmp_path))
        cmd_str, _argv = ex._build_command(req, "hello")
        assert cmd_str.count("--json") == 1

    def test_sandbox_flag_injected_when_absent(self, tmp_path):
        cfg = CodexCliExecutorConfig(
            binary="echo",
            command_template="codex exec {prompt}",
        )
        ex = CodexCliExecutor(cfg)
        req = _req(str(tmp_path))
        cmd_str, _argv = ex._build_command(req, "hello")
        assert "--sandbox" in cmd_str
