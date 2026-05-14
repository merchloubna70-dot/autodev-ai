"""Tests for Bug7: codex --json JSONL inner-step parsing."""
from __future__ import annotations

import json

from autodev.executors.codex_cli_executor import _parse_inner_steps
from autodev.schemas import CodexInnerStep

JSONL_SAMPLE = "\n".join([
    json.dumps({"type": "thinking", "content": "I need to write a function", "duration_ms": 120}),
    json.dumps({"type": "shell", "command": "pytest .", "exit_code": 0, "duration_ms": 4500}),
    json.dumps({"type": "patch", "summary": "Added hello.py with 10 lines", "duration_ms": 50}),
    json.dumps({"type": "result", "message": "Done", "duration_ms": 10}),
])


def test_parse_jsonl_returns_inner_steps():
    """Valid JSONL stdout produces a list of CodexInnerStep objects."""
    steps = _parse_inner_steps(JSONL_SAMPLE)
    assert len(steps) == 4
    assert all(isinstance(s, CodexInnerStep) for s in steps)


def test_parse_jsonl_step_fields():
    """Fields are extracted correctly from JSONL records."""
    steps = _parse_inner_steps(JSONL_SAMPLE)
    shell_step = next(s for s in steps if s.kind == "shell")
    assert shell_step.command == "pytest ."
    assert shell_step.exit_code == 0
    assert shell_step.duration_ms == 4500

    patch_step = next(s for s in steps if s.kind == "patch")
    assert "Added hello.py" in patch_step.content_summary


def test_non_json_stdout_yields_empty_list():
    """Non-JSONL stdout (plain text) returns an empty inner_steps list."""
    plain_stdout = "Task completed successfully.\nAll tests passed.\n"
    steps = _parse_inner_steps(plain_stdout)
    assert steps == []


def test_empty_stdout_yields_empty_list():
    """Empty stdout yields empty list with no errors."""
    steps = _parse_inner_steps("")
    assert steps == []


def test_partial_json_bails_out_gracefully():
    """If one line is not JSON, the whole parse bails returning empty list."""
    mixed = 'some plain text line\n{"type": "result"}\n'
    steps = _parse_inner_steps(mixed)
    assert steps == []


def test_step_index_increments():
    """step_index values match line positions in the JSONL stream."""
    steps = _parse_inner_steps(JSONL_SAMPLE)
    for i, step in enumerate(steps):
        assert step.step_index == i
