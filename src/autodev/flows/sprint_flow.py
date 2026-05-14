"""SprintFlow — disk-based multi-run sprint lifecycle.

Each sprint has its own directory under .autodev/sprints/sprint-NNN/ and
keeps state in state.json.  No LLM is required in the default path; all
logic is pure-Python deterministic analysis of on-disk evidence.

BMAD Skills informed:
  - bmad-sprint-planning  (start_sprint)
  - bmad-sprint-status    (status)
  - bmad-retrospective    (retrospective)
  - bmad-correct-course   (correct_course)
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..schemas import (
    DeliveryTask,
    RetrospectiveReport,
    Severity,
    SprintChangeImpact,
    SprintChangeProposal,
    SprintInput,
    SprintState,
    SprintStatus,
)

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

_SPRINT_DIR_RE = re.compile(r"^sprint-(\d+)$")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sprint_base(repo_path: str) -> Path:
    return Path(repo_path) / ".autodev" / "sprints"


def _next_sprint_id(base: Path) -> str:
    """Return the next sprint-NNN id by scanning existing sprint dirs."""
    if not base.exists():
        return "sprint-001"
    nums = []
    for d in base.iterdir():
        m = _SPRINT_DIR_RE.match(d.name)
        if m:
            nums.append(int(m.group(1)))
    next_n = (max(nums) + 1) if nums else 1
    return f"sprint-{next_n:03d}"


def _load_state_json(sprint_dir: Path) -> dict[str, Any]:
    p = sprint_dir / "state.json"
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def _save_state_json(sprint_dir: Path, data: dict[str, Any]) -> None:
    sprint_dir.mkdir(parents=True, exist_ok=True)
    (sprint_dir / "state.json").write_text(
        json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def _resolve_sprint_dir(repo_path: str, sprint_id: str | None) -> Path:
    """Return the sprint dir for the given id, or the latest if None."""
    base = _sprint_base(repo_path)
    if sprint_id:
        return base / sprint_id
    # latest = highest number
    if not base.exists():
        raise FileNotFoundError(f"No sprint directory found under {base}")
    dirs = [d for d in base.iterdir() if _SPRINT_DIR_RE.match(d.name)]
    if not dirs:
        raise FileNotFoundError(f"No sprint directory found under {base}")
    return max(dirs, key=lambda d: int(_SPRINT_DIR_RE.match(d.name).group(1)))  # type: ignore[union-attr]


def _previous_retro_summary(base: Path, prev_sprint_id: str) -> str:
    """Load summary from previous sprint's retrospective if it exists."""
    retro_path = base / prev_sprint_id / "retrospective.json"
    if not retro_path.exists():
        return ""
    try:
        data = json.loads(retro_path.read_text(encoding="utf-8"))
        actions = data.get("actions_for_next_sprint", [])
        if actions:
            return "; ".join(actions[:5])
    except Exception:
        pass
    return ""


# ---------------------------------------------------------------------------
# SprintFlow
# ---------------------------------------------------------------------------


class SprintFlow:
    """Disk-based Sprint lifecycle: start → status → retrospective → correct-course."""

    # ------------------------------------------------------------------
    # start_sprint
    # ------------------------------------------------------------------

    def start_sprint(self, inp: SprintInput) -> SprintState:
        """Open a new sprint directory, snapshot artifacts, link previous retro.

        Creates:
          .autodev/sprints/sprint-NNN/
            state.json
            planning/   (snapshot references)
            implementation/  (empty, filled during run)
        """
        base = _sprint_base(inp.repo_path)
        sprint_id = _next_sprint_id(base)
        sprint_dir = base / sprint_id

        # Determine previous sprint
        prev_dirs = sorted(
            [d for d in base.iterdir() if base.exists() and _SPRINT_DIR_RE.match(d.name)],
            key=lambda d: int(_SPRINT_DIR_RE.match(d.name).group(1)),  # type: ignore[union-attr]
        ) if base.exists() else []
        prev_sprint_id: str | None = prev_dirs[-1].name if prev_dirs else None
        prev_retro_summary = _previous_retro_summary(base, prev_sprint_id) if prev_sprint_id else ""

        planning_path = str(sprint_dir / "planning")
        impl_path = str(sprint_dir / "implementation")

        # Snapshot existing planning artifacts from repo root
        repo_planning = Path(inp.repo_path) / ".autodev" / "planning"
        artifacts_snapshot: list[str] = []
        if repo_planning.exists():
            for f in repo_planning.rglob("*.md"):
                artifacts_snapshot.append(str(f))
            for f in repo_planning.rglob("*.json"):
                artifacts_snapshot.append(str(f))

        state = SprintState(
            sprint_id=sprint_id,
            goal=inp.goal,
            started_at=_now_iso(),
            previous_sprint_id=prev_sprint_id,
            previous_retrospective_summary=prev_retro_summary,
            tasks=[],
            acceptance_criteria_carryover=[],
            planning_artifacts_path=planning_path,
            implementation_artifacts_path=impl_path,
        )

        # Persist
        sprint_dir.mkdir(parents=True, exist_ok=True)
        Path(planning_path).mkdir(parents=True, exist_ok=True)
        Path(impl_path).mkdir(parents=True, exist_ok=True)

        raw = state.model_dump(mode="json")
        raw["_artifacts_snapshot"] = artifacts_snapshot
        raw["_product_name"] = inp.product_name
        raw["_duration_days"] = inp.duration_days
        _save_state_json(sprint_dir, raw)

        return state

    # ------------------------------------------------------------------
    # status
    # ------------------------------------------------------------------

    def status(self, repo_path: str, sprint_id: str | None = None) -> SprintStatus:
        """Read on-disk sprint state and compute health metrics.

        Health classification:
          complete  — all tasks done
          blocked   — any task has a blocker note
          on-track  — >50 % done
          at-risk   — ≤50 % done
        """
        sprint_dir = _resolve_sprint_dir(repo_path, sprint_id)
        raw = _load_state_json(sprint_dir)
        sid = raw.get("sprint_id", sprint_dir.name)

        tasks_raw: list[dict] = raw.get("tasks", [])
        tasks_total = len(tasks_raw)
        tasks_done = sum(1 for t in tasks_raw if t.get("_status") == "done")
        tasks_failed = sum(1 for t in tasks_raw if t.get("_status") == "failed")

        # Scan implementation dir for result files
        impl_path = Path(raw.get("implementation_artifacts_path", str(sprint_dir / "implementation")))
        if impl_path.exists():
            for result_file in impl_path.glob("**/*_result.json"):
                try:
                    rdata = json.loads(result_file.read_text(encoding="utf-8"))
                    if rdata.get("success") is True:
                        tasks_done += 1
                    elif rdata.get("success") is False:
                        tasks_failed += 1
                    tasks_total = max(tasks_total, tasks_done + tasks_failed)
                except Exception:
                    pass

        blockers: list[str] = list(raw.get("_blockers", []))

        # Compute progress
        progress_pct = (tasks_done / tasks_total * 100.0) if tasks_total > 0 else 0.0

        # Classify health
        if tasks_total > 0 and tasks_done == tasks_total:
            health = "complete"
        elif blockers:
            health = "blocked"
        elif progress_pct > 50.0:
            health = "on-track"
        else:
            health = "at-risk"

        return SprintStatus(
            sprint_id=sid,
            health=health,
            tasks_total=tasks_total,
            tasks_done=tasks_done,
            tasks_failed=tasks_failed,
            blockers=blockers,
            progress_pct=round(progress_pct, 1),
        )

    # ------------------------------------------------------------------
    # retrospective
    # ------------------------------------------------------------------

    def retrospective(self, repo_path: str, sprint_id: str) -> RetrospectiveReport:
        """Analyse sprint run results and produce a structured retro doc.

        Evidence sources (pure-disk, no LLM):
          - implementation/*.json (success/failure)
          - state.json tasks
          - state.json acceptance_criteria_carryover
        """
        sprint_dir = _resolve_sprint_dir(repo_path, sprint_id)
        raw = _load_state_json(sprint_dir)
        sid = raw.get("sprint_id", sprint_id)

        impl_path = Path(raw.get("implementation_artifacts_path", str(sprint_dir / "implementation")))

        what_went_well: list[str] = []
        what_went_wrong: list[str] = []
        surprises: list[str] = []
        evidence_refs: list[str] = []
        failed_tasks: list[str] = []
        passed_tasks: list[str] = []

        # Scan result files
        if impl_path.exists():
            for result_file in sorted(impl_path.glob("**/*_result.json")):
                evidence_refs.append(str(result_file))
                try:
                    rdata = json.loads(result_file.read_text(encoding="utf-8"))
                    tid = rdata.get("task_id", result_file.stem)
                    if rdata.get("success") is True:
                        passed_tasks.append(tid)
                    elif rdata.get("success") is False:
                        failed_tasks.append(tid)
                        err = rdata.get("stderr", "") or rdata.get("error_type", "")
                        if err:
                            what_went_wrong.append(f"Task {tid} failed: {err[:120]}")
                except Exception:
                    surprises.append(f"Unreadable result file: {result_file.name}")

        if passed_tasks:
            what_went_well.append(f"{len(passed_tasks)} tasks completed successfully: {', '.join(passed_tasks[:5])}")
        if not failed_tasks and not what_went_well:
            what_went_well.append("Sprint completed with no recorded failures.")
        if failed_tasks and not what_went_wrong:
            what_went_wrong.append(f"{len(failed_tasks)} tasks failed: {', '.join(failed_tasks[:5])}")

        # Carryover acceptance criteria = tasks that were NOT done
        carryover_ac: list[str] = list(raw.get("acceptance_criteria_carryover", []))
        tasks_raw: list[dict] = raw.get("tasks", [])
        for t in tasks_raw:
            if t.get("_status") not in ("done",):
                for ac in t.get("acceptance_criteria", []):
                    if ac not in carryover_ac:
                        carryover_ac.append(ac)

        # Previous retro summary informs actions
        actions: list[str] = []
        prev_summary = raw.get("previous_retrospective_summary", "")
        if prev_summary:
            actions.append(f"Review and apply lessons from previous sprint: {prev_summary}")
        if failed_tasks:
            actions.append(f"Investigate root cause for {len(failed_tasks)} failed task(s).")
        if carryover_ac:
            actions.append(f"Carry over {len(carryover_ac)} acceptance criteria to next sprint.")
        if not actions:
            actions.append("Continue velocity; no blocking issues detected.")

        report = RetrospectiveReport(
            sprint_id=sid,
            what_went_well=what_went_well,
            what_went_wrong=what_went_wrong,
            surprises=surprises,
            actions_for_next_sprint=actions,
            carryover_acceptance_criteria=carryover_ac,
            raw_evidence_refs=evidence_refs,
        )

        # Persist retro alongside state
        retro_path = sprint_dir / "retrospective.json"
        retro_path.write_text(
            json.dumps(report.model_dump(mode="json"), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        return report

    # ------------------------------------------------------------------
    # correct_course
    # ------------------------------------------------------------------

    def correct_course(
        self,
        repo_path: str,
        sprint_id: str,
        change_description: str,
    ) -> SprintChangeProposal:
        """Analyse change impact across PRD/Epic/Arch/UX and propose actions.

        Impact analysis is done by scanning planning artifacts for keyword
        overlaps with the change description (pure-Python, no LLM).
        """
        sprint_dir = _resolve_sprint_dir(repo_path, sprint_id)
        raw = _load_state_json(sprint_dir)
        sid = raw.get("sprint_id", sprint_id)

        planning_path = Path(raw.get("planning_artifacts_path", str(sprint_dir / "planning")))
        # Also look in repo-level planning dir
        repo_planning = Path(repo_path) / ".autodev" / "planning"

        keywords = set(re.findall(r"\w+", change_description.lower()))
        impacts: list[SprintChangeImpact] = []

        artifact_map = {
            "PRD": ["prd", "requirements", "product"],
            "Epic": ["epic", "story", "stories", "sprint"],
            "Architecture": ["architecture", "arch", "design", "module", "api"],
            "UX": ["ux", "ui", "user", "interface", "flow", "screen"],
            "Tests": ["test", "tests", "acceptance", "criteria", "qa"],
        }

        def _scan_dir(d: Path) -> dict[str, list[str]]:
            hits: dict[str, list[str]] = {}
            if not d.exists():
                return hits
            for f in d.rglob("*.md"):
                content = ""
                try:
                    content = f.read_text(encoding="utf-8", errors="ignore").lower()
                except Exception:
                    continue
                for artifact, artifact_kws in artifact_map.items():
                    # Check if file is relevant to this artifact type
                    fname_lower = f.name.lower()
                    relevant = any(k in fname_lower or k in content[:200] for k in artifact_kws)
                    if relevant:
                        # Count keyword matches
                        match_count = sum(1 for kw in keywords if kw in content and len(kw) > 3)
                        if match_count > 0:
                            hits.setdefault(artifact, []).append(f.name)
            return hits

        all_hits: dict[str, list[str]] = {}
        for d in (planning_path, repo_planning):
            partial = _scan_dir(d)
            for k, v in partial.items():
                all_hits.setdefault(k, []).extend(v)

        # Always include at least a placeholder impact
        if not all_hits:
            all_hits["Architecture"] = ["(no matching files found)"]

        severity_map = {
            "PRD": Severity.BLOCKER,
            "Epic": Severity.MAJOR,
            "Architecture": Severity.MAJOR,
            "UX": Severity.MINOR,
            "Tests": Severity.MINOR,
        }

        for artifact, files in all_hits.items():
            summary = f"Files potentially affected: {', '.join(files[:3])}" + (
                f" +{len(files) - 3} more" if len(files) > 3 else ""
            )
            impacts.append(SprintChangeImpact(
                artifact=artifact,
                change_summary=summary,
                severity=severity_map.get(artifact, Severity.MAJOR),
            ))

        # Recommended actions derived from impacts
        recommended_actions: list[str] = [
            f"Review and update {imp.artifact} artifacts: {imp.change_summary}"
            for imp in impacts
            if imp.severity in (Severity.BLOCKER, Severity.MAJOR)
        ]
        if not recommended_actions:
            recommended_actions = [
                f"Minor impact detected; review UX/Tests artifacts for '{change_description[:60]}'"
            ]
        recommended_actions.append("Re-run sprint-status after applying changes to verify health.")

        proposal = SprintChangeProposal(
            sprint_id=sid,
            change_description=change_description,
            impacts=impacts,
            recommended_actions=recommended_actions,
        )

        # Persist proposal
        proposal_path = sprint_dir / "course_correction.json"
        proposal_path.write_text(
            json.dumps(proposal.model_dump(mode="json"), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        return proposal
