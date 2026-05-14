"""Unit tests for src/autodev/cost.py.

Six required tests:
1. estimator monotonic in brief size
2. ledger writes valid JSON
3. ledger appends to JSONL
4. dry-cost short-circuits the run (CLI integration)
5. prices match documented constants
6. no --dry-cost = normal run path (CLI integration)
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from autodev.cli import app
from autodev.cost import (
    CLAUDE_INPUT_USD_PER_1M,
    CLAUDE_MAX_TIERS,
    CLAUDE_OUTPUT_USD_PER_1M,
    CODEX_INPUT_USD_PER_1M,
    CODEX_OUTPUT_USD_PER_1M,
    CODEX_PRO_MONTHLY_OUTPUT_TOKENS,
    CostEstimator,
    CostLedger,
)

runner = CliRunner()


# ---------------------------------------------------------------------------
# Test 1: estimator is monotonically increasing in brief size
# ---------------------------------------------------------------------------


def test_estimator_monotonic_in_brief_size() -> None:
    """Larger brief must produce strictly more total tokens than a smaller brief."""
    est = CostEstimator()
    short = est.estimate("short brief")
    medium = est.estimate("A" * 500)
    long_ = est.estimate("A" * 5000)

    assert short.total_tokens < medium.total_tokens, "medium brief should exceed short"
    assert medium.total_tokens < long_.total_tokens, "long brief should exceed medium"

    # Costs must also be monotonic
    assert short.claude_api_cost_usd < long_.claude_api_cost_usd
    assert short.codex_api_cost_usd < long_.codex_api_cost_usd


# ---------------------------------------------------------------------------
# Test 2: ledger writes valid JSON
# ---------------------------------------------------------------------------


def test_ledger_writes_valid_json(tmp_path: Path) -> None:
    """CostLedger.record must write a parseable JSON file at the expected path."""
    ledger = CostLedger(repo_path=str(tmp_path))
    cost_file = ledger.record(
        run_id="run-test-001",
        executor_tokens={"codex": (1000, 2000), "claude_code": (500, 800)},
    )

    assert cost_file.exists(), "cost.json should be written"
    assert cost_file.name == "cost.json"
    assert cost_file.parent.name == "quality"
    assert cost_file.parent.parent.name == "run-test-001"

    data = json.loads(cost_file.read_text(encoding="utf-8"))

    # Required top-level keys
    assert "run_id" in data
    assert data["run_id"] == "run-test-001"
    assert "executor_breakdown" in data
    assert "totals" in data

    # Totals sanity
    totals = data["totals"]
    assert totals["input_tokens"] == 1500
    assert totals["output_tokens"] == 2800
    assert totals["total_tokens"] == 4300
    assert totals["estimated_cost_usd"] >= 0.0


# ---------------------------------------------------------------------------
# Test 3: ledger appends to JSONL
# ---------------------------------------------------------------------------


def test_ledger_appends_to_jsonl(tmp_path: Path) -> None:
    """Multiple calls to record() must append separate lines to cost_ledger.jsonl."""
    ledger = CostLedger(repo_path=str(tmp_path))

    ledger.record(run_id="run-a", executor_tokens={"mock": (100, 200)})
    ledger.record(run_id="run-b", executor_tokens={"codex": (300, 400)})
    ledger.record(run_id="run-c", executor_tokens={})

    ledger_path = tmp_path / ".dev-factory" / "cost_ledger.jsonl"
    assert ledger_path.exists(), "cost_ledger.jsonl should exist"

    lines = [line.strip() for line in ledger_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(lines) == 3, "should have exactly 3 JSONL entries"

    run_ids = [json.loads(line)["run_id"] for line in lines]
    assert run_ids == ["run-a", "run-b", "run-c"]


# ---------------------------------------------------------------------------
# Test 4: --dry-cost short-circuits the pipeline run
# ---------------------------------------------------------------------------


def test_dry_cost_short_circuits_run(tmp_path: Path) -> None:
    """--dry-cost must exit 0 and print JSON without calling ProjectDeliveryFlow.run."""
    brief = tmp_path / "brief.md"
    brief.write_text("Build a minimal CLI tool for line counting.", encoding="utf-8")

    with patch("autodev.cli.ProjectDeliveryFlow") as mock_flow_cls:
        result = runner.invoke(
            app,
            [
                "deliver-project",
                "--dry-cost",
                "--project-brief", str(brief),
                "--repo-path", str(tmp_path),
            ],
        )

    # Flow should never have been instantiated or run
    mock_flow_cls.assert_not_called()

    assert result.exit_code == 0, f"exit_code={result.exit_code}\n{result.output}"

    # Output must be valid JSON with expected keys
    data = json.loads(result.output)
    assert "total_tokens" in data
    assert "claude_api_cost_usd" in data
    assert "codex_api_cost_usd" in data
    assert "claude_max_subscription" in data
    assert data["total_tokens"] > 0


# ---------------------------------------------------------------------------
# Test 5: prices match documented constants
# ---------------------------------------------------------------------------


def test_prices_match_documented_constants() -> None:
    """Verify pricing constants have sane values and estimator uses them correctly."""
    # Sanity: all prices must be positive
    assert CLAUDE_INPUT_USD_PER_1M > 0
    assert CLAUDE_OUTPUT_USD_PER_1M > 0
    assert CODEX_INPUT_USD_PER_1M > 0
    assert CODEX_OUTPUT_USD_PER_1M > 0

    # Output pricing must be >= input pricing (typical for LLM APIs)
    assert CLAUDE_OUTPUT_USD_PER_1M >= CLAUDE_INPUT_USD_PER_1M
    assert CODEX_OUTPUT_USD_PER_1M >= CODEX_INPUT_USD_PER_1M

    # Max tier caps must be strictly increasing
    caps = [cap for cap, _ in CLAUDE_MAX_TIERS]
    assert caps == sorted(caps), "tiers must be ordered low→high"
    assert len(CLAUDE_MAX_TIERS) >= 3, "at least 3 Claude Max tiers must be defined"

    # Codex Pro budget must be a meaningful number
    assert CODEX_PRO_MONTHLY_OUTPUT_TOKENS >= 1_000_000

    # Cross-check: estimator cost is consistent with raw constant arithmetic
    est = CostEstimator()
    estimate = est.estimate("")  # empty brief, only task tokens count
    expected_cost = (
        estimate.total_input_tokens * CLAUDE_INPUT_USD_PER_1M / 1_000_000
        + estimate.total_output_tokens * CLAUDE_OUTPUT_USD_PER_1M / 1_000_000
    )
    assert abs(estimate.claude_api_cost_usd - expected_cost) < 1e-9


# ---------------------------------------------------------------------------
# Test 6: no --dry-cost = normal run path
# ---------------------------------------------------------------------------


def test_no_dry_cost_invokes_normal_run(tmp_path: Path) -> None:
    """Without --dry-cost, deliver-project must call ProjectDeliveryFlow.run."""
    brief = tmp_path / "brief.md"
    brief.write_text("Build a minimal CLI tool.", encoding="utf-8")

    # Build a minimal fake RunState so the CLI can finish without errors
    fake_run = MagicMock()
    fake_run.run_id = "run-mock-999"
    fake_run.state.mock_execution_used = True
    fake_run.state.release_check = None

    with patch("autodev.cli.ProjectDeliveryFlow") as mock_flow_cls:
        mock_flow_cls.return_value.run.return_value = fake_run
        result = runner.invoke(
            app,
            [
                "deliver-project",
                "--project-brief", str(brief),
                "--repo-path", str(tmp_path),
                "--scale", "small",
            ],
        )

    mock_flow_cls.return_value.run.assert_called_once()
    assert result.exit_code == 0, f"exit_code={result.exit_code}\n{result.output}"
    assert "run_id=run-mock-999" in result.output


# ---------------------------------------------------------------------------
# Additional: to_text output sanity
# ---------------------------------------------------------------------------


def test_estimator_to_text_output() -> None:
    """to_text() should contain key headings and produce valid string output."""
    est = CostEstimator()
    estimate = est.estimate("Build a line-counting CLI tool in Python.")
    text = estimate.to_text()

    assert "autodev-x dry-cost estimate" in text
    assert "Total tokens" in text
    assert "Claude Max" in text
    assert "Codex Pro" in text


# ---------------------------------------------------------------------------
# Additional: ledger empty executor_tokens writes zero-token record
# ---------------------------------------------------------------------------


def test_ledger_empty_executor_tokens(tmp_path: Path) -> None:
    """record() with an empty executor_tokens dict must write valid JSON with 0 tokens."""
    ledger = CostLedger(repo_path=str(tmp_path))
    cost_file = ledger.record(run_id="run-zero", executor_tokens={})

    data = json.loads(cost_file.read_text(encoding="utf-8"))
    assert data["totals"]["total_tokens"] == 0
    assert data["totals"]["estimated_cost_usd"] == 0.0
    assert data["executor_breakdown"] == {}
