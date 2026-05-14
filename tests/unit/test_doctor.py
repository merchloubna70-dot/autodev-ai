"""Tests for autodev.doctor diagnostic module."""
from __future__ import annotations

from unittest.mock import patch


def test_doctor_command_exists_in_cli() -> None:
    """The 'doctor' command must be registered in the Typer app."""
    from autodev.cli import app

    command_names = [cmd.name for cmd in app.registered_commands]
    assert "doctor" in command_names, f"'doctor' not found in {command_names}"


def test_run_checks_returns_expected_keys() -> None:
    """run_checks() must return a dict with all expected diagnostic keys."""
    from autodev.doctor import run_checks

    results = run_checks()
    expected_keys = {
        "autodev_version",
        "python_version",
        "codex",
        "claude",
        "AUTODEV_MCP_ALLOW_APPLY",
        "writable_cwd",
        "git",
    }
    assert expected_keys.issubset(set(results.keys())), (
        f"Missing keys: {expected_keys - set(results.keys())}"
    )


def test_run_checks_each_entry_has_status_and_detail() -> None:
    """Each entry returned by run_checks() must have 'status' and 'detail'."""
    from autodev.doctor import run_checks

    results = run_checks()
    for key, info in results.items():
        assert "status" in info, f"Entry '{key}' missing 'status'"
        assert "detail" in info, f"Entry '{key}' missing 'detail'"
        assert info["status"] in ("ok", "warn", "fail"), (
            f"Entry '{key}' has unexpected status: {info['status']!r}"
        )


def test_python_version_check_passes_current_interpreter() -> None:
    """Python version check must report 'ok' for the current (>=3.10) interpreter."""
    from autodev.doctor import run_checks

    results = run_checks()
    # The project requires >=3.10 and the test runner must satisfy that.
    assert results["python_version"]["status"] == "ok", (
        f"Expected ok but got: {results['python_version']}"
    )


def test_run_checks_does_not_crash_without_optional_binaries() -> None:
    """run_checks() must complete without exception even when codex/claude are absent."""
    from autodev.doctor import run_checks

    with patch("shutil.which", return_value=None):
        # Should not raise
        results = run_checks()

    assert "codex" in results
    assert "claude" in results


def test_print_table_runs_without_error(capsys: object) -> None:
    """print_table() must produce output and not raise."""
    from autodev.doctor import print_table, run_checks

    results = run_checks()
    print_table(results)

    captured = capsys.readouterr()  # type: ignore[union-attr]
    assert len(captured.out) > 0, "Expected non-empty output from print_table"
