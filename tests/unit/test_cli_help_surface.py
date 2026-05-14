"""CLI surface audit tests — one test per subcommand asserting --help works.

Approach
--------
Each test invokes the CLI via ``typer.testing.CliRunner`` with
``["<cmd>", "--help"]`` and asserts:
  1. exit_code == 0
  2. "Usage:" appears in the stripped output

The ANSI-strip helper is the same pattern used in test_prfaq_style.py.
"""
from __future__ import annotations

import re

from typer.testing import CliRunner

from autodev.cli import app

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[mK]")


def _strip(text: str) -> str:
    """Remove ANSI escape codes and normalise whitespace."""
    return _ANSI_RE.sub("", text)


runner = CliRunner()


def _assert_help(cmd: str) -> None:
    result = runner.invoke(app, [cmd, "--help"])
    out = _strip(result.output)
    assert result.exit_code == 0, (
        f"`autodev {cmd} --help` exited {result.exit_code}.\nOutput:\n{out}"
    )
    assert "Usage:" in out, (
        f"`autodev {cmd} --help` output missing 'Usage:'.\nOutput:\n{out}"
    )


# ---------------------------------------------------------------------------
# Root-level tests
# ---------------------------------------------------------------------------


def test_root_help():
    result = runner.invoke(app, ["--help"])
    out = _strip(result.output)
    assert result.exit_code == 0
    assert "Usage:" in out


def test_root_version():
    result = runner.invoke(app, ["--version"])
    out = _strip(result.output)
    assert result.exit_code == 0
    # Version string should contain at least one digit and a dot
    assert re.search(r"\d+\.\d+", out), f"No version string in: {out!r}"


# ---------------------------------------------------------------------------
# Subcommand help tests — one per command
# ---------------------------------------------------------------------------


def test_help_run_issue():
    _assert_help("run-issue")


def test_help_deliver_project():
    _assert_help("deliver-project")


def test_help_classify_input():
    _assert_help("classify-input")


def test_help_create_prd():
    _assert_help("create-prd")


def test_help_plan_project():
    _assert_help("plan-project")


def test_help_plan_milestones():
    _assert_help("plan-milestones")


def test_help_plan_tasks():
    _assert_help("plan-tasks")


def test_help_execute_milestone():
    _assert_help("execute-milestone")


def test_help_continue_run():
    _assert_help("continue-run")


def test_help_replay():
    _assert_help("replay")


def test_help_scan():
    _assert_help("scan")


def test_help_verify():
    _assert_help("verify")


def test_help_release_check():
    _assert_help("release-check")


def test_help_report():
    _assert_help("report")


def test_help_export_delivery():
    _assert_help("export-delivery")


def test_help_push():
    _assert_help("push")


def test_help_create_pr():
    _assert_help("create-pr")


def test_help_fix_bug():
    _assert_help("fix-bug")


def test_help_multi_patch_fix_bug():
    _assert_help("multi-patch-fix-bug")


def test_help_review():
    _assert_help("review")


def test_help_roundtable():
    _assert_help("roundtable")


def test_help_mcp_serve():
    _assert_help("mcp-serve")


def test_help_a2a_serve():
    _assert_help("a2a-serve")


def test_help_a2a_register():
    _assert_help("a2a-register")


def test_help_a2a_call():
    _assert_help("a2a-call")


def test_help_next():
    _assert_help("next")


def test_help_design_ux():
    _assert_help("design-ux")


def test_help_investigate():
    _assert_help("investigate")


def test_help_generate_context():
    _assert_help("generate-context")


def test_help_document_project():
    _assert_help("document-project")


def test_help_sprint_start():
    _assert_help("sprint-start")


def test_help_sprint_status():
    _assert_help("sprint-status")


def test_help_sprint_retro():
    _assert_help("sprint-retro")


def test_help_sprint_correct():
    _assert_help("sprint-correct")


def test_help_dashboard():
    _assert_help("dashboard")
