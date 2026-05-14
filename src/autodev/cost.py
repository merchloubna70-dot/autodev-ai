"""Cost estimation and ledger for autodev-x runs.

Selling point: subscription leverage — users need to know their token usage
stays within their Claude Max / Codex Pro monthly cap.

Usage
-----
Dry-cost estimation (no real run):

    from autodev.cost import CostEstimator
    est = CostEstimator()
    report = est.estimate(brief_text="...")
    print(report.to_text())

Actual-run recording (called at run end):

    from autodev.cost import CostLedger
    ledger = CostLedger(repo_path="/path/to/repo")
    ledger.record(run_id="run-abc", executor_tokens={"codex": (1000, 2000)})
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Pricing constants
# Update when vendor pricing changes; last verified 2026-05.
# All prices in USD per 1 000 000 tokens.
# ---------------------------------------------------------------------------

# Claude Sonnet 4.5 / Sonnet 4.6 (API pay-as-you-go)
CLAUDE_INPUT_USD_PER_1M: float = 3.00
CLAUDE_OUTPUT_USD_PER_1M: float = 15.00

# OpenAI Codex (o4-mini / codex-mini as of 2026-05)
CODEX_INPUT_USD_PER_1M: float = 1.50
CODEX_OUTPUT_USD_PER_1M: float = 6.00

# Claude Max subscription monthly token caps (approximate hard limits):
#   $20/mo  — 40×  normal usage  → ~1 000 000 output tokens/month
#   $100/mo — 5×  Pro  ≈ 5 000 000 output tokens/month
#   $200/mo — 20× Pro  ≈ 20 000 000 output tokens/month
# Represented as (total_monthly_output_tokens_cap, display_label).
CLAUDE_MAX_TIERS: list[tuple[int, str]] = [
    (1_000_000, "$20/mo"),
    (5_000_000, "$100/mo"),
    (20_000_000, "$200/mo"),
]

# Codex Pro subscription monthly output-token budget (community estimate, 2026-05)
CODEX_PRO_MONTHLY_OUTPUT_TOKENS: int = 10_000_000

# ---------------------------------------------------------------------------
# Agent-graph fan-out heuristics
# 12 agents × avg tasks each × avg tokens per task.
# These constants calibrate the estimator; adjust as empirics improve.
# ---------------------------------------------------------------------------
_AGENT_COUNT: int = 12
_AVG_TASKS_PER_AGENT: int = 4   # low-end for a brief-sized project
_INPUT_TOKENS_PER_TASK: int = 1_500   # prompt + context
_OUTPUT_TOKENS_PER_TASK: int = 800    # generated patch / text
# Brief text overhead (ingested N times across agents during planning stages)
_BRIEF_FANOUT: int = 6   # rough number of agents that read the brief in full


# ---------------------------------------------------------------------------
# CostEstimate — result object (no Pydantic; keep dependency-free)
# ---------------------------------------------------------------------------


class CostEstimate:
    """Result of a dry-cost estimation."""

    def __init__(
        self,
        brief_chars: int,
        brief_tokens_input: int,
        task_input_tokens: int,
        task_output_tokens: int,
        total_input_tokens: int,
        total_output_tokens: int,
        total_tokens: int,
        claude_api_cost_usd: float,
        codex_api_cost_usd: float,
        claude_max_pct: list[dict[str, Any]],
        codex_pro_pct: float,
    ) -> None:
        self.brief_chars = brief_chars
        self.brief_tokens_input = brief_tokens_input
        self.task_input_tokens = task_input_tokens
        self.task_output_tokens = task_output_tokens
        self.total_input_tokens = total_input_tokens
        self.total_output_tokens = total_output_tokens
        self.total_tokens = total_tokens
        self.claude_api_cost_usd = claude_api_cost_usd
        self.codex_api_cost_usd = codex_api_cost_usd
        self.claude_max_pct = claude_max_pct
        self.codex_pro_pct = codex_pro_pct

    def to_dict(self) -> dict[str, Any]:
        return {
            "brief_chars": self.brief_chars,
            "brief_tokens_input": self.brief_tokens_input,
            "task_input_tokens": self.task_input_tokens,
            "task_output_tokens": self.task_output_tokens,
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_tokens": self.total_tokens,
            "claude_api_cost_usd": round(self.claude_api_cost_usd, 4),
            "codex_api_cost_usd": round(self.codex_api_cost_usd, 4),
            "claude_max_subscription": self.claude_max_pct,
            "codex_pro_subscription": {
                "monthly_output_cap": CODEX_PRO_MONTHLY_OUTPUT_TOKENS,
                "this_run_pct": round(self.codex_pro_pct, 2),
            },
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    def to_text(self) -> str:
        lines = [
            "=== autodev-x dry-cost estimate ===",
            f"Brief size            : {self.brief_chars:,} chars / ~{self.brief_tokens_input:,} tokens",
            f"Agent fan-out         : {_AGENT_COUNT} agents x ~{_AVG_TASKS_PER_AGENT} tasks",
            f"Task input tokens     : {self.task_input_tokens:,}",
            f"Task output tokens    : {self.task_output_tokens:,}",
            f"Total input tokens    : {self.total_input_tokens:,}",
            f"Total output tokens   : {self.total_output_tokens:,}",
            f"Total tokens          : {self.total_tokens:,}",
            "",
            f"API cost (Claude)     : ${self.claude_api_cost_usd:.4f}",
            f"API cost (Codex)      : ${self.codex_api_cost_usd:.4f}",
            "",
            "Claude Max subscription cap usage:",
        ]
        for tier in self.claude_max_pct:
            lines.append(
                f"  {tier['tier']:10s} : {tier['this_run_pct']:.2f}% of monthly cap "
                f"({tier['monthly_output_cap']:,} output tokens)"
            )
        lines.append(
            f"Codex Pro subscription : {self.codex_pro_pct:.2f}% of monthly cap "
            f"({CODEX_PRO_MONTHLY_OUTPUT_TOKENS:,} output tokens)"
        )
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# CostEstimator
# ---------------------------------------------------------------------------


def _chars_to_tokens(n: int) -> int:
    """Rough approximation: 4 chars ≈ 1 token (BPE heuristic)."""
    return max(1, n // 4)


class CostEstimator:
    """Estimate token cost for a deliver-project run without executing it.

    All parameters are wired to module-level constants so a single change
    propagates everywhere.
    """

    def estimate(self, brief_text: str) -> CostEstimate:
        """Return a :class:`CostEstimate` for the given brief text."""
        brief_chars = len(brief_text)
        # Brief is read by _BRIEF_FANOUT agents; each reading = 1 input block
        brief_tokens_input = _chars_to_tokens(brief_chars) * _BRIEF_FANOUT

        total_tasks = _AGENT_COUNT * _AVG_TASKS_PER_AGENT
        task_input_tokens = total_tasks * _INPUT_TOKENS_PER_TASK
        task_output_tokens = total_tasks * _OUTPUT_TOKENS_PER_TASK

        total_input_tokens = brief_tokens_input + task_input_tokens
        total_output_tokens = task_output_tokens  # brief reading is input-only
        total_tokens = total_input_tokens + total_output_tokens

        # Dollar costs at raw API rates
        claude_api_cost_usd = (
            total_input_tokens * CLAUDE_INPUT_USD_PER_1M / 1_000_000
            + total_output_tokens * CLAUDE_OUTPUT_USD_PER_1M / 1_000_000
        )
        codex_api_cost_usd = (
            total_input_tokens * CODEX_INPUT_USD_PER_1M / 1_000_000
            + total_output_tokens * CODEX_OUTPUT_USD_PER_1M / 1_000_000
        )

        # Subscription cap percentages (based on output tokens, which is the
        # binding constraint for Max and Pro)
        claude_max_pct = [
            {
                "tier": label,
                "monthly_output_cap": cap,
                "this_run_pct": round(total_output_tokens / cap * 100, 2),
            }
            for cap, label in CLAUDE_MAX_TIERS
        ]
        codex_pro_pct = total_output_tokens / CODEX_PRO_MONTHLY_OUTPUT_TOKENS * 100

        return CostEstimate(
            brief_chars=brief_chars,
            brief_tokens_input=brief_tokens_input,
            task_input_tokens=task_input_tokens,
            task_output_tokens=task_output_tokens,
            total_input_tokens=total_input_tokens,
            total_output_tokens=total_output_tokens,
            total_tokens=total_tokens,
            claude_api_cost_usd=claude_api_cost_usd,
            codex_api_cost_usd=codex_api_cost_usd,
            claude_max_pct=claude_max_pct,
            codex_pro_pct=codex_pro_pct,
        )


# ---------------------------------------------------------------------------
# CostLedger — actual-run recording
# ---------------------------------------------------------------------------


class CostLedger:
    """Record and persist actual token usage from a completed deliver-project run.

    Writes two files:
    - ``<repo>/.dev-factory/runs/<run_id>/quality/cost.json``
    - ``<repo>/.dev-factory/cost_ledger.jsonl``  (append-only, cumulative)
    """

    def __init__(self, repo_path: str) -> None:
        self.repo_path = str(Path(repo_path).resolve())
        self._dev_factory = Path(self.repo_path) / ".dev-factory"

    def _runs_dir(self) -> Path:
        return self._dev_factory / "runs"

    def _ledger_path(self) -> Path:
        return self._dev_factory / "cost_ledger.jsonl"

    def record(
        self,
        run_id: str,
        executor_tokens: dict[str, tuple[int, int]],
    ) -> Path:
        """Persist cost data for a completed run and append to the cumulative ledger.

        Parameters
        ----------
        run_id:
            The run identifier (matches the directory name under .dev-factory/runs/).
        executor_tokens:
            Mapping from executor name (``"codex"``, ``"claude_code"``, ``"mock"``)
            to a ``(input_tokens, output_tokens)`` tuple.  Pass an empty dict when
            real executors did not report token counts.

        Returns
        -------
        Path
            Path to the written ``quality/cost.json`` file.
        """
        per_executor: dict[str, dict[str, Any]] = {}
        total_input = 0
        total_output = 0
        for executor_name, (inp, out) in executor_tokens.items():
            inp_cost = inp * CLAUDE_INPUT_USD_PER_1M / 1_000_000
            out_cost = out * CLAUDE_OUTPUT_USD_PER_1M / 1_000_000
            per_executor[executor_name] = {
                "input_tokens": inp,
                "output_tokens": out,
                "estimated_cost_usd": round(inp_cost + out_cost, 6),
                "pricing_note": (
                    "Uses Claude API rates; adjust for Codex if executor=codex. "
                    "Update when vendor pricing changes; last verified 2026-05."
                ),
            }
            total_input += inp
            total_output += out

        total_cost_usd = (
            total_input * CLAUDE_INPUT_USD_PER_1M / 1_000_000
            + total_output * CLAUDE_OUTPUT_USD_PER_1M / 1_000_000
        )

        payload: dict[str, Any] = {
            "run_id": run_id,
            "recorded_at": datetime.now(timezone.utc).isoformat(),
            "executor_breakdown": per_executor,
            "totals": {
                "input_tokens": total_input,
                "output_tokens": total_output,
                "total_tokens": total_input + total_output,
                "estimated_cost_usd": round(total_cost_usd, 6),
            },
        }

        # Write per-run file
        run_quality_dir = self._runs_dir() / run_id / "quality"
        run_quality_dir.mkdir(parents=True, exist_ok=True)
        cost_path = run_quality_dir / "cost.json"
        cost_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

        # Append to cumulative ledger
        ledger_path = self._ledger_path()
        ledger_path.parent.mkdir(parents=True, exist_ok=True)
        ledger_entry = {
            "run_id": run_id,
            "recorded_at": payload["recorded_at"],
            "total_tokens": total_input + total_output,
            "estimated_cost_usd": round(total_cost_usd, 6),
        }
        with ledger_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(ledger_entry, ensure_ascii=False) + "\n")

        return cost_path
