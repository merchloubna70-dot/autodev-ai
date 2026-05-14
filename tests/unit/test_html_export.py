"""Unit tests for HTML export features.

Tests cover:
1. dashboard export produces valid HTML5
2. roundtable html produces valid HTML5
3. both output files self-contain Prism.js CDN script tag
4. malformed / empty artifact tree handled gracefully
5. default markdown still works for roundtable (--output-format markdown)
"""
from __future__ import annotations

import json
from html.parser import HTMLParser
from pathlib import Path

import pytest

from autodev.tui.html_export import (
    AgentAnalysis,
    export_dashboard_html,
    export_roundtable_html,
)

# ---------------------------------------------------------------------------
# HTML validation helper
# ---------------------------------------------------------------------------


class _HTMLValidator(HTMLParser):
    """Minimal HTML5 well-formedness checker via html.parser (no unmatched tags)."""

    _VOID_ELEMENTS = frozenset({
        "area", "base", "br", "col", "embed", "hr", "img", "input",
        "link", "meta", "param", "source", "track", "wbr",
    })

    def __init__(self) -> None:
        super().__init__()
        self.errors: list[str] = []
        self._stack: list[str] = []

    def handle_starttag(self, tag: str, attrs: list) -> None:
        if tag not in self._VOID_ELEMENTS:
            self._stack.append(tag)

    def handle_endtag(self, tag: str) -> None:
        if tag in self._VOID_ELEMENTS:
            return
        if self._stack and self._stack[-1] == tag:
            self._stack.pop()
        else:
            self.errors.append(f"unexpected </{tag}> (stack top: {self._stack[-1] if self._stack else 'empty'})")

    @property
    def unclosed(self) -> list[str]:
        return list(self._stack)


def _assert_valid_html(html: str) -> None:
    """Assert that *html* is well-formed HTML5."""
    assert html.strip().startswith("<!DOCTYPE html"), "Missing <!DOCTYPE html>"
    validator = _HTMLValidator()
    validator.feed(html)
    assert not validator.errors, f"HTML parse errors: {validator.errors}"
    # Allow a small set of elements that may remain open (e.g. <html>, <body>)
    tolerated_open = {"html", "body", "head"}
    unexpected = [t for t in validator.unclosed if t not in tolerated_open]
    assert not unexpected, f"Unclosed tags: {unexpected}"


def _contains_prism(html: str) -> bool:
    return "prism" in html.lower() and "cdnjs.cloudflare.com" in html


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def dev_factory_root(tmp_path: Path) -> Path:
    """Create a minimal .dev-factory tree with one run."""
    root = tmp_path / ".dev-factory"
    run_dir = root / "runs" / "run-test-001"
    run_dir.mkdir(parents=True)

    state = {
        "run_id": "run-test-001",
        "started_at": "2026-01-01T00:00:00+00:00",
        "finished_at": "2026-01-01T01:00:00+00:00",
        "mode": "dry-run",
        "flow": "project_delivery_flow",
        "repo_path": "/tmp/project",
        "languages": ["python"],
        "mock_execution_used": True,
        "errors": [],
        "milestone_plan": {
            "milestones": [{"milestone_id": "M1", "title": "Scaffold"}],
            "tasks": [{"task_id": "T1", "milestone_id": "M1", "title": "Init"}],
        },
        "quality_gates": [
            {
                "language": "python",
                "outcomes": [
                    {"name": "lint", "status": "passed"},
                    {"name": "tests", "status": "passed"},
                ],
            }
        ],
        "release_check": {"decision": "GoForRelease"},
        "implementation_results": [
            {
                "task_id": "T1",
                "milestone_id": "M1",
                "executor": "codex",
                "success": True,
            }
        ],
    }
    (run_dir / "run_state.json").write_text(json.dumps(state), encoding="utf-8")

    # Add an artifact in the planning stage
    planning_dir = run_dir / "planning"
    planning_dir.mkdir()
    (planning_dir / "milestone_plan.json").write_text(
        json.dumps({"milestones": [{"id": "M1"}]}), encoding="utf-8"
    )
    return root


# ---------------------------------------------------------------------------
# Test 1: dashboard export produces valid HTML
# ---------------------------------------------------------------------------


def test_dashboard_export_produces_valid_html(dev_factory_root: Path, tmp_path: Path) -> None:
    """export_dashboard_html writes a valid HTML5 file."""
    out = tmp_path / "dashboard.html"
    result = export_dashboard_html(root=dev_factory_root, output=out)

    assert result.exists(), "Output file was not created"
    html = out.read_text(encoding="utf-8")
    _assert_valid_html(html)
    # Spot-check key content
    assert "run-test-001" in html
    assert "dry-run" in html


# ---------------------------------------------------------------------------
# Test 2: roundtable html produces valid HTML
# ---------------------------------------------------------------------------


def test_roundtable_html_produces_valid_html(tmp_path: Path) -> None:
    """export_roundtable_html writes a valid HTML5 file."""
    out = tmp_path / "roundtable.html"
    result = export_roundtable_html(
        topic="Should we adopt Rust for the core engine?",
        participants=["architecture-agent", "security-agent"],
        agent_analyses=[
            AgentAnalysis(agent_name="architecture-agent", text="Rust is strongly typed."),
            AgentAnalysis(agent_name="security-agent", text="Memory safety is great."),
        ],
        consensus_text="Both agents agree: Rust adoption is beneficial.",
        conversation_id="conv-abc-123",
        output=out,
    )

    assert result.exists()
    html = out.read_text(encoding="utf-8")
    _assert_valid_html(html)
    assert "Should we adopt Rust" in html
    assert "architecture-agent" in html
    assert "Both agents agree" in html


# ---------------------------------------------------------------------------
# Test 3: both outputs self-contain Prism.js CDN script tag
# ---------------------------------------------------------------------------


def test_dashboard_html_contains_prism(dev_factory_root: Path, tmp_path: Path) -> None:
    """Dashboard HTML includes Prism.js CDN references."""
    out = tmp_path / "dash.html"
    export_dashboard_html(root=dev_factory_root, output=out)
    html = out.read_text(encoding="utf-8")
    assert _contains_prism(html), "Prism.js CDN reference not found in dashboard HTML"


def test_roundtable_html_contains_prism(tmp_path: Path) -> None:
    """Roundtable HTML includes Prism.js CDN references."""
    out = tmp_path / "rt.html"
    export_roundtable_html(
        topic="Topic",
        participants=[],
        agent_analyses=[],
        consensus_text="",
        output=out,
    )
    html = out.read_text(encoding="utf-8")
    assert _contains_prism(html), "Prism.js CDN reference not found in roundtable HTML"


# ---------------------------------------------------------------------------
# Test 4: malformed / empty artifact tree handled gracefully
# ---------------------------------------------------------------------------


def test_dashboard_empty_root_raises(tmp_path: Path) -> None:
    """export_dashboard_html raises FileNotFoundError when root does not exist."""
    with pytest.raises(FileNotFoundError):
        export_dashboard_html(root=tmp_path / "nonexistent", output=tmp_path / "out.html")


def test_dashboard_root_with_no_runs(tmp_path: Path) -> None:
    """export_dashboard_html handles a root with no runs directory (renders empty-state HTML)."""
    root = tmp_path / ".dev-factory"
    root.mkdir()
    # No runs/ subdirectory
    out = tmp_path / "out.html"
    result = export_dashboard_html(root=root, output=out)
    assert result.exists()
    html = out.read_text(encoding="utf-8")
    _assert_valid_html(html)


def test_dashboard_malformed_run_state(tmp_path: Path) -> None:
    """export_dashboard_html handles a malformed run_state.json without crashing."""
    root = tmp_path / ".dev-factory"
    run_dir = root / "runs" / "bad-run"
    run_dir.mkdir(parents=True)
    (run_dir / "run_state.json").write_text("{{{invalid json", encoding="utf-8")

    out = tmp_path / "out.html"
    result = export_dashboard_html(root=root, output=out)
    assert result.exists()
    html = out.read_text(encoding="utf-8")
    _assert_valid_html(html)


# ---------------------------------------------------------------------------
# Test 5: default markdown still works for roundtable (CLI integration)
# ---------------------------------------------------------------------------


def test_roundtable_cli_default_format_is_markdown(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Calling roundtable without --output-format still produces JSON + stdout (markdown mode)."""
    from typer.testing import CliRunner

    from autodev.cli import app

    monkeypatch.setenv("FACTORY_FORCE_MOCK", "1")
    monkeypatch.chdir(tmp_path)

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "roundtable",
            "--topic", "Should we refactor the auth module?",
            "--skills", "security",
            "--max-participants", "1",
            "--repo-path", str(tmp_path),
        ],
        catch_exceptions=False,
    )
    # Should succeed and write a JSON file (markdown mode — no HTML file)
    assert result.exit_code == 0, f"exit_code={result.exit_code}\n{result.output}"
    # JSON file is written
    roundtables_dir = tmp_path / ".dev-factory" / "roundtables"
    json_files = list(roundtables_dir.glob("*.json"))
    assert json_files, "Expected at least one JSON roundtable file"
    # No HTML file produced (markdown mode)
    html_files = list(roundtables_dir.glob("*.html"))
    assert not html_files, "HTML file should NOT be produced in markdown mode"
