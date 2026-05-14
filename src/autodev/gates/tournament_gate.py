"""TournamentGate — tournament-based quality gate with Borda-count voting.

After the existing QualityGate step in the pipeline, this gate can spawn N
subprocess judge agents (opt-in, default N=0 = disabled).  Each judge
evaluates the same artifact and emits a structured verdict.  Verdicts are
aggregated via Borda voting (rank-based, not raw-score average) and the
gate either passes, requests revisions, or rejects the artifact.

Subprocess design notes
-----------------------
- Each judge runs in a CLEAN subprocess to avoid context bleed (same pattern
  as ExecutorRouter / ClaudeCodeExecutor).
- In production the subprocess calls the real ``claude`` CLI.
- In tests, callers mock ``subprocess.run`` to avoid real CLI invocations.
- If a subprocess fails (non-zero exit, JSON parse error, timeout) the judge
  is recorded as a soft failure with ``recommend=revise, score=1`` so the
  gate degrades gracefully rather than hard-crashing.

Borda voting
------------
Given recommendations ``keep``, ``revise``, ``reject`` we rank them:
  keep   → rank 2 (best)
  revise → rank 1
  reject → rank 0 (worst)

Each judge's verdict awards the corresponding rank-points to that option.
The option with the highest total Borda score wins.  Ties go to the
**least-disruptive** option (keep > revise > reject).

Aggregate decision
------------------
- ``keep``   → gate passes; artifact advances unchanged.
- ``revise`` → gate emits ``JudgePanelRevision`` event and attaches
               ``quality/tournament_revisions.json``.
- ``reject`` → gate raises ``TournamentGateRejectError`` with all issues.

Both the per-judge raw verdicts (``quality/tournament_verdicts.json``) and
the revision summary (``quality/tournament_revisions.json``) are written to
the run directory when ``run`` is provided.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

Recommendation = Literal["keep", "revise", "reject"]

_BORDA_RANK: dict[str, int] = {"keep": 2, "revise": 1, "reject": 0}
_BORDA_TIE_PRIORITY: list[str] = ["keep", "revise", "reject"]  # least-disruptive wins ties

# Path to the bundled judge prompt template (relative to this file)
_TEMPLATE_PATH = Path(__file__).parent.parent / "templates" / "tournament_judge.txt"


@dataclass
class JudgeVerdict:
    """Structured output from a single judge subprocess."""

    judge_index: int
    score: int  # 1-5
    top_issue: str
    recommend: Recommendation
    raw_output: str = ""
    error: str = ""  # non-empty if the judge subprocess failed


@dataclass
class TournamentResult:
    """Aggregated result from the full judge panel."""

    n_judges: int
    verdicts: list[JudgeVerdict]
    borda_scores: dict[str, int]
    consensus: Recommendation
    top_issues: list[str]
    revisions_path: str | None = None  # path written if consensus == "revise"
    verdicts_path: str | None = None   # path of the raw verdicts JSON


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class TournamentGateRejectError(RuntimeError):
    """Raised when the judge panel consensus is ``reject``."""

    def __init__(self, top_issues: list[str], result: TournamentResult) -> None:
        summary = "; ".join(top_issues) if top_issues else "no specific issues recorded"
        super().__init__(
            f"TournamentGate: artifact rejected by judge panel "
            f"(borda={result.borda_scores}). "
            f"Issues: {summary}"
        )
        self.result = result


# ---------------------------------------------------------------------------
# Borda aggregator (pure function — easily unit-tested)
# ---------------------------------------------------------------------------


def borda_aggregate(verdicts: list[JudgeVerdict]) -> tuple[Recommendation, dict[str, int]]:
    """Return (consensus, borda_scores) from a list of verdicts.

    Ties are broken in favour of the least-disruptive option:
    keep > revise > reject.

    Parameters
    ----------
    verdicts:
        Non-empty list of JudgeVerdict objects.

    Returns
    -------
    tuple[Recommendation, dict[str, int]]
        The winning recommendation and the per-option Borda score totals.
    """
    if not verdicts:
        return "keep", {"keep": 0, "revise": 0, "reject": 0}

    totals: dict[str, int] = {"keep": 0, "revise": 0, "reject": 0}
    for v in verdicts:
        rec = v.recommend if v.recommend in totals else "revise"
        totals[rec] += _BORDA_RANK[rec]

    # Find the maximum score, then pick the least-disruptive among ties
    max_score = max(totals.values())
    for option in _BORDA_TIE_PRIORITY:  # keep → revise → reject
        if totals[option] == max_score:
            return option, totals  # type: ignore[return-value]

    # Unreachable, but satisfy type checker
    return "keep", totals  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Subprocess judge runner
# ---------------------------------------------------------------------------


def _load_template() -> str:
    """Load the judge prompt template from disk."""
    if _TEMPLATE_PATH.exists():
        return _TEMPLATE_PATH.read_text(encoding="utf-8")
    # Minimal fallback so tests that don't care about prompt content still work
    return (
        "Review the following artifact and respond with JSON: "
        '{"score": <1-5>, "top_issue": "<str>", "recommend": "keep|revise|reject"}\n\n'
        "Artifact:\n{artifact}"
    )


def _build_prompt(artifact: str) -> str:
    template = _load_template()
    return template.replace("{artifact}", artifact)


def _run_judge_subprocess(
    judge_index: int,
    prompt: str,
    *,
    timeout: int = 120,
    env: dict[str, str] | None = None,
) -> JudgeVerdict:
    """Invoke a judge subprocess and parse its JSON verdict.

    The subprocess command is ``claude --print --output-format json`` (the
    Claude Code CLI non-interactive mode).  If the ``claude`` binary is not
    available or the subprocess fails for any reason the verdict defaults to
    ``recommend=revise, score=1`` (safe degradation).

    The env var ``AUTODEV_TOURNAMENT_CMD`` can override the binary name for
    testing/CI without mocking subprocess directly.
    """
    cmd_binary = (env or os.environ).get("AUTODEV_TOURNAMENT_CMD") or "claude"
    cmd = [cmd_binary, "--print", "--output-format", "json", prompt]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            env={**os.environ, **(env or {})},
        )
    except FileNotFoundError:
        return JudgeVerdict(
            judge_index=judge_index,
            score=1,
            top_issue="judge subprocess binary not found",
            recommend="revise",
            error=f"binary not found: {cmd_binary}",
        )
    except subprocess.TimeoutExpired:
        return JudgeVerdict(
            judge_index=judge_index,
            score=1,
            top_issue="judge subprocess timed out",
            recommend="revise",
            error=f"timeout after {timeout}s",
        )
    except Exception as exc:  # noqa: BLE001
        return JudgeVerdict(
            judge_index=judge_index,
            score=1,
            top_issue="judge subprocess failed",
            recommend="revise",
            error=str(exc),
        )

    raw = result.stdout.strip()
    if result.returncode != 0:
        return JudgeVerdict(
            judge_index=judge_index,
            score=1,
            top_issue="judge subprocess non-zero exit",
            recommend="revise",
            raw_output=raw,
            error=f"exit_code={result.returncode} stderr={result.stderr[:200]}",
        )

    return _parse_verdict(judge_index=judge_index, raw=raw)


def _parse_verdict(judge_index: int, raw: str) -> JudgeVerdict:
    """Parse a raw JSON string from the judge into a JudgeVerdict.

    Handles:
    - Valid JSON objects at top-level
    - JSON embedded in markdown fences (the model may wrap in ```json ... ```)
    - Missing or out-of-range fields (clamped / defaulted)
    """
    text = raw.strip()

    # Strip markdown code fences if present
    for fence in ("```json", "```"):
        if text.startswith(fence):
            text = text[len(fence):]
            if "```" in text:
                text = text[: text.rfind("```")]
            text = text.strip()
            break

    try:
        obj: dict[str, Any] = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return JudgeVerdict(
            judge_index=judge_index,
            score=1,
            top_issue="could not parse judge JSON response",
            recommend="revise",
            raw_output=raw,
            error="json_parse_error",
        )

    # score: clamp 1-5
    try:
        score = max(1, min(5, int(obj.get("score", 1))))
    except (TypeError, ValueError):
        score = 1

    top_issue = str(obj.get("top_issue", "")).strip()

    # recommend: default to "revise" if unrecognised
    raw_rec = str(obj.get("recommend", "revise")).strip().lower()
    recommend: Recommendation = raw_rec if raw_rec in ("keep", "revise", "reject") else "revise"  # type: ignore[assignment]

    return JudgeVerdict(
        judge_index=judge_index,
        score=score,
        top_issue=top_issue,
        recommend=recommend,
        raw_output=raw,
    )


# ---------------------------------------------------------------------------
# TournamentGate
# ---------------------------------------------------------------------------


class TournamentGate:
    """Tournament-based quality gate.

    Usage::

        gate = TournamentGate(n_judges=3)
        result = gate.run(artifact="...", run=run)
        # raises TournamentGateRejectError on reject
        # result.consensus is "keep" or "revise"

    When ``n_judges=0`` the gate is a no-op and returns immediately with
    ``consensus="keep"``.
    """

    def __init__(
        self,
        n_judges: int = 0,
        *,
        judge_timeout: int = 120,
        subprocess_env: dict[str, str] | None = None,
    ) -> None:
        if n_judges < 0 or n_judges > 7:
            raise ValueError(f"n_judges must be 0-7, got {n_judges}")
        self.n_judges = n_judges
        self.judge_timeout = judge_timeout
        self.subprocess_env = subprocess_env

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(
        self,
        artifact: str,
        *,
        run: Any | None = None,  # RunState | None — avoid circular import
    ) -> TournamentResult:
        """Run the tournament gate against ``artifact``.

        Parameters
        ----------
        artifact:
            The text artifact to evaluate (PRD, architecture doc, etc.).
        run:
            Optional ``RunState``.  When provided, results are persisted under
            ``quality/tournament_verdicts.json`` and (on revise)
            ``quality/tournament_revisions.json``.

        Returns
        -------
        TournamentResult
            The aggregated result.  If consensus is ``reject``, this method
            raises ``TournamentGateRejectError`` *before* returning.
        """
        # 0 judges = bypass
        if self.n_judges == 0:
            return TournamentResult(
                n_judges=0,
                verdicts=[],
                borda_scores={"keep": 0, "revise": 0, "reject": 0},
                consensus="keep",
                top_issues=[],
            )

        prompt = _build_prompt(artifact)
        verdicts = self._spawn_judges(prompt)
        consensus, borda_scores = borda_aggregate(verdicts)

        # Reject-override: Borda assigns rank 0 to "reject", so pure Borda can
        # never produce a "reject" winner.  We apply a majority-count override:
        # if more than half of the judges explicitly recommended "reject", the
        # gate overrides the Borda consensus to "reject".
        reject_count = sum(1 for v in verdicts if v.recommend == "reject")
        if reject_count > len(verdicts) / 2:
            consensus = "reject"

        top_issues = [v.top_issue for v in verdicts if v.top_issue]

        result = TournamentResult(
            n_judges=self.n_judges,
            verdicts=verdicts,
            borda_scores=borda_scores,
            consensus=consensus,
            top_issues=top_issues,
        )

        # Persist raw verdicts
        if run is not None:
            self._save_verdicts(run, result)

        # Handle consensus
        if consensus == "revise":
            if run is not None:
                self._save_revisions(run, result)
            self._emit_revision_event(result)
        elif consensus == "reject":
            if run is not None:
                self._save_revisions(run, result)
            raise TournamentGateRejectError(top_issues=top_issues, result=result)

        return result

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _spawn_judges(self, prompt: str) -> list[JudgeVerdict]:
        """Spawn N judge subprocesses sequentially and collect verdicts."""
        verdicts: list[JudgeVerdict] = []
        for i in range(self.n_judges):
            verdict = _run_judge_subprocess(
                judge_index=i,
                prompt=prompt,
                timeout=self.judge_timeout,
                env=self.subprocess_env,
            )
            verdicts.append(verdict)
        return verdicts

    def _save_verdicts(self, run: Any, result: TournamentResult) -> None:
        """Write per-judge raw verdicts to ``quality/tournament_verdicts.json``."""
        payload: list[dict[str, Any]] = []
        for v in result.verdicts:
            payload.append({
                "judge_index": v.judge_index,
                "score": v.score,
                "top_issue": v.top_issue,
                "recommend": v.recommend,
                "raw_output": v.raw_output,
                "error": v.error,
            })
        try:
            path = run.save_json("quality/tournament_verdicts.json", payload)
            if path is not None:
                result.verdicts_path = str(path)
        except Exception as exc:  # noqa: BLE001
            print(f"[TournamentGate] warning: could not save verdicts: {exc}", file=sys.stderr)

    def _save_revisions(self, run: Any, result: TournamentResult) -> None:
        """Write revision summary to ``quality/tournament_revisions.json``."""
        payload = {
            "consensus": result.consensus,
            "borda_scores": result.borda_scores,
            "top_issues": result.top_issues,
            "n_judges": result.n_judges,
            "verdicts": [
                {
                    "judge_index": v.judge_index,
                    "score": v.score,
                    "top_issue": v.top_issue,
                    "recommend": v.recommend,
                }
                for v in result.verdicts
            ],
        }
        try:
            path = run.save_json("quality/tournament_revisions.json", payload)
            if path is not None:
                result.revisions_path = str(path)
        except Exception as exc:  # noqa: BLE001
            print(f"[TournamentGate] warning: could not save revisions: {exc}", file=sys.stderr)

    def _emit_revision_event(self, result: TournamentResult) -> None:
        """Log the JudgePanelRevision event to stderr."""
        issues_summary = "; ".join(result.top_issues) if result.top_issues else "(none)"
        print(
            f"[TournamentGate] JudgePanelRevision: borda={result.borda_scores} "
            f"issues={issues_summary}",
            file=sys.stderr,
        )
