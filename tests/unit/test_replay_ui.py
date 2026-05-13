"""Tests for ReplayTimelineRenderer."""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

import pytest

from crewai_multicli_factory.reports.replay_ui import ReplayTimelineRenderer


def _make_run(tmp_path: Path, run_id: str, steps: list[dict]) -> Path:
    run_dir = tmp_path / ".dev-factory" / "runs" / run_id / "execution"
    run_dir.mkdir(parents=True, exist_ok=True)
    jsonl_path = run_dir / "execution_calls.jsonl"
    with jsonl_path.open("w") as fh:
        for step in steps:
            fh.write(json.dumps(step) + "\n")
    return tmp_path


class TestReplayTimelineRenderer:
    def setup_method(self) -> None:
        self.renderer = ReplayTimelineRenderer()

    def test_renders_valid_html(self, tmp_path: Path) -> None:
        repo = _make_run(
            tmp_path,
            "run-001",
            [
                {"backend": "claude", "task_id": "t1", "success": True, "timestamp": "2026-01-01T00:00:00", "duration_ms": 100},
                {"backend": "gpt4", "task_id": "t2", "success": False, "timestamp": "2026-01-01T00:00:01", "duration_ms": 200},
            ],
        )
        html_out = self.renderer.render_html("run-001", str(repo))
        assert "<!DOCTYPE html>" in html_out
        assert "<html" in html_out
        assert "</html>" in html_out

    def test_contains_scrubber_input(self, tmp_path: Path) -> None:
        repo = _make_run(
            tmp_path,
            "run-002",
            [{"backend": "deepseek", "task_id": "x", "success": True, "timestamp": "t", "duration_ms": 0}],
        )
        html_out = self.renderer.render_html("run-002", str(repo))
        assert '<input type="range"' in html_out

    def test_handles_empty_jsonl(self, tmp_path: Path) -> None:
        repo = _make_run(tmp_path, "run-empty", [])
        html_out = self.renderer.render_html("run-empty", str(repo))
        assert "<!DOCTYPE html>" in html_out
        assert "run-empty" in html_out

    def test_missing_jsonl_does_not_crash(self, tmp_path: Path) -> None:
        # Directory exists but no jsonl file
        html_out = self.renderer.render_html("run-nonexistent", str(tmp_path))
        assert "<!DOCTYPE html>" in html_out

    def test_run_id_appears_in_output(self, tmp_path: Path) -> None:
        repo = _make_run(tmp_path, "run-abc123", [{"backend": "b", "task_id": "t", "success": True, "timestamp": "ts"}])
        html_out = self.renderer.render_html("run-abc123", str(repo))
        assert "run-abc123" in html_out

    def test_backend_colour_coded(self, tmp_path: Path) -> None:
        repo = _make_run(
            tmp_path,
            "run-colours",
            [
                {"backend": "claude", "task_id": "a", "success": True, "timestamp": "t"},
                {"backend": "gpt4", "task_id": "b", "success": True, "timestamp": "t"},
            ],
        )
        html_out = self.renderer.render_html("run-colours", str(repo))
        assert "claude" in html_out
        assert "gpt4" in html_out

    def test_no_external_assets(self, tmp_path: Path) -> None:
        repo = _make_run(tmp_path, "run-self", [{"backend": "x", "task_id": "y", "success": True, "timestamp": "t"}])
        html_out = self.renderer.render_html("run-self", str(repo))
        # No CDN references
        assert "cdn." not in html_out
        assert "https://unpkg" not in html_out
        assert "https://cdn" not in html_out
