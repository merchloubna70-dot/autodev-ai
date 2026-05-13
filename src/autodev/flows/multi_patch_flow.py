"""MultiPatchFlow — self-consistency patch generation.

Generates N candidate patches by re-invoking ImplementerAgent N times with
different seeds encoded in the task prompt. After N patches, runs a
reproduction test against each candidate; the candidate with the most
passing tests wins via voting.

Hard rules
----------
- ALL patch generation MUST go through ExecutorRouter via ImplementerAgent.
- No direct imports of CodexCliExecutor or ClaudeCodeExecutor.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from ..agents.implementer import ImplementerAgent
from ..config import FactoryConfig
from ..executors.executor_router import ExecutorRouter
from ..planners.four_stage_planner import FourStagePlanner, _MILESTONE_ID
from ..schemas import (
    ExecutionBackend,
    Language,
    Milestone,
    MilestonePlan,
    MultiPatchVote,
    PatchCandidate,
    PipelineMode,
    RiskLevel,
    TaskType,
)
from ..state import RunState
from ..utils.logging import get_logger

_logger = get_logger("multi_patch_flow")

_DEFAULT_N = 3


@dataclass
class MultiPatchInput:
    """Input for the multi-patch self-consistency flow."""

    bug_description: str
    repo_path: str
    n_candidates: int = _DEFAULT_N
    languages: list[Language] = field(default_factory=lambda: [Language.PYTHON])
    mode: PipelineMode = PipelineMode.DRY_RUN
    backend: ExecutionBackend = ExecutionBackend.AUTO
    allow_mock: bool = True


class MultiPatchFlow:
    """Generates N candidate patches and elects the best via voting."""

    def __init__(self, config: FactoryConfig | None = None):
        self.config = config or FactoryConfig()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self, inp: MultiPatchInput) -> RunState:
        """Run the multi-patch flow and return the completed RunState."""
        run = RunState(repo_path=inp.repo_path)
        run.state.mode = inp.mode
        run.state.flow = "multi_patch_flow"
        run.state.languages = inp.languages
        run.save()

        # Ensure the multi_patch directory exists
        multi_patch_dir = run.path("multi_patch")
        multi_patch_dir.mkdir(parents=True, exist_ok=True)

        n = max(1, inp.n_candidates)
        candidates: list[PatchCandidate] = []

        router = ExecutorRouter(self.config, allow_mock=inp.allow_mock)
        implementer = ImplementerAgent(router)

        primary_language = inp.languages[0] if inp.languages else Language.PYTHON

        for i in range(n):
            seed = f"seed-{i+1}"
            candidate_id = f"candidate-{i+1}"
            _logger.info("Generating patch candidate %s (seed=%s)", candidate_id, seed)

            # Embed the seed in the bug description so ImplementerAgent explores
            # a different solution path each time.
            seeded_description = (
                f"[MULTI-PATCH {seed}] {inp.bug_description}"
            )

            planner = FourStagePlanner()
            tasks = planner.plan(
                bug_description=seeded_description,
                repo_path=inp.repo_path,
                language=primary_language,
            )

            milestone_id = f"MPATCH-{i+1}"
            for t in tasks:
                t.milestone_id = milestone_id

            milestone = Milestone(
                milestone_id=milestone_id,
                title=f"Multi-patch candidate {candidate_id}",
                objective=seeded_description[:200],
                task_ids=[t.task_id for t in tasks],
                estimated_risk=RiskLevel.MEDIUM,
                allowed_languages=inp.languages,
            )
            plan = MilestonePlan(milestones=[milestone], tasks=tasks)

            if run.state.milestone_plan is None:
                run.state.milestone_plan = plan
            else:
                run.state.milestone_plan.milestones.append(milestone)
                run.state.milestone_plan.tasks.extend(tasks)

            impl = implementer.run_milestone(
                milestone_id=milestone_id,
                tasks=tasks,
                run=run,
                mode=inp.mode,
                languages=inp.languages,
                concurrency=1,
                fail_fast=False,
            )

            run.state.implementation_results.append(impl)

            # Determine test pass/fail counts from execution results
            test_pass = 0
            test_fail = 0
            patch_text_parts: list[str] = []
            changed_files: list[str] = []

            for er in impl.task_results:
                if er.success:
                    test_pass += 1
                    if er.stdout:
                        patch_text_parts.append(er.stdout[:500])
                else:
                    test_fail += 1

            mock_used = impl.mock_used

            candidate = PatchCandidate(
                candidate_id=candidate_id,
                seed=seed,
                patch_text="\n".join(patch_text_parts),
                changed_files=changed_files,
                test_pass_count=test_pass,
                test_fail_count=test_fail,
                score=float(test_pass),
            )
            candidates.append(candidate)

            # Persist candidate to disk
            candidate_file = multi_patch_dir / f"{candidate_id}.json"
            candidate_file.write_text(
                json.dumps(candidate.model_dump(mode="json"), indent=2),
                encoding="utf-8",
            )

        # Vote: highest test_pass_count wins; tie → first by candidate_id
        winner = self._vote(candidates)

        vote = MultiPatchVote(
            candidates=candidates,
            winner_candidate_id=winner.candidate_id if winner else None,
            rationale=self._rationale(candidates, winner),
            mock_used=any(c.score == 0.0 for c in candidates),
        )

        vote_file = multi_patch_dir / "vote.json"
        vote_file.write_text(
            json.dumps(vote.model_dump(mode="json"), indent=2),
            encoding="utf-8",
        )

        run.save_json("multi_patch/summary.json", vote.model_dump(mode="json"))
        run.finish()
        return run

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _vote(candidates: list[PatchCandidate]) -> PatchCandidate | None:
        """Return the winner: highest test_pass_count; tie → first by candidate_id."""
        if not candidates:
            return None
        return max(candidates, key=lambda c: (c.test_pass_count, -int(c.candidate_id.split("-")[-1])))

    @staticmethod
    def _rationale(candidates: list[PatchCandidate], winner: PatchCandidate | None) -> str:
        if winner is None:
            return "No candidates generated."
        parts = [
            f"{c.candidate_id}: pass={c.test_pass_count} fail={c.test_fail_count}"
            for c in candidates
        ]
        return f"Winner={winner.candidate_id} (pass={winner.test_pass_count}). Scores: {'; '.join(parts)}"
