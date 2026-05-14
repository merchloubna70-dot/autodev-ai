"""Commit Agent — produces branch/commit/PR artifacts; default OFF for write ops."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..adapters.git_adapter import GitAdapter
from ..adapters.github_adapter import GitHubAdapter
from ..schemas import PipelineRunState
from ..utils.slug import slugify
from ._crewai_bridge import make_agent


@dataclass
class CommitArtifacts:
    branch_name: str
    commit_message: str
    pr_body: str


class CommitAgent:
    def __init__(self) -> None:
        self.agent = make_agent(
            role="Commit Agent",
            goal="Generate branch / commit / PR artifacts. Never push or tag unless explicitly enabled.",
            backstory="A release-discipline-obsessed engineer.",
        )

    def build_artifacts(self, *, state: PipelineRunState, project_name: str, issue_id: str | None = None) -> CommitArtifacts:
        if issue_id:
            branch = f"fix/{slugify(issue_id)}"
        elif state.flow == "project_delivery_flow":
            branch = f"delivery/{slugify(project_name)}"
        else:
            branch = f"feature/{slugify(state.run_id)}/software-factory"
        summary = f"Software factory run {state.run_id}"
        mock = state.mock_execution_used
        dry = state.mode.value == "dry-run"
        msg = (
            f"{summary}\n\n"
            f"flow={state.flow}\n"
            f"mode={state.mode.value}\n"
            f"backends={[b.value for b in state.backends_used]}\n"
            f"MockExecutionUsed={mock}\n"
            f"DryRun={dry}\n"
        )
        pr_body = self._render_pr_body(state, project_name, mock=mock, dry=dry)
        return CommitArtifacts(branch_name=branch, commit_message=msg, pr_body=pr_body)

    def maybe_commit(self, *, repo_path: str, artifacts: CommitArtifacts, enabled: bool) -> int:
        git = GitAdapter(repo_path)
        if not enabled or not git.has_git():
            return 0
        # Stage everything under .dev-factory + project files; caller may pre-stage
        return git.commit(artifacts.commit_message, enabled=enabled)

    def maybe_push(self, repo_path: str, branch: str | None, enabled: bool) -> int:
        """Push to origin if enabled=True; no-op otherwise. Never force-pushes."""
        git = GitAdapter(repo_path)
        if not enabled or not git.has_git():
            return 0
        return git.push(remote="origin", branch=branch, enabled=enabled)

    def maybe_create_pr(
        self,
        repo_path: str,
        artifacts: CommitArtifacts,
        *,
        base: str = "main",
        draft: bool = True,
        enabled: bool,
    ) -> dict:
        """Create a GitHub PR if enabled=True and gh is available.

        Always returns a dict — never raises.
        """
        if not enabled:
            return {"success": False, "reason": "disabled"}
        gh = GitHubAdapter()
        if not gh.gh_available():
            return {"success": False, "reason": "gh-not-installed", "error": "gh-missing"}
        # Write PR body to .dev-factory/PR_BODY.md
        body_path = Path(repo_path) / ".dev-factory" / "PR_BODY.md"
        body_path.parent.mkdir(parents=True, exist_ok=True)
        body_path.write_text(artifacts.pr_body, encoding="utf-8")
        result = gh.create_pr(
            repo_path=repo_path,
            title=f"[factory] {artifacts.branch_name}",
            body_path=str(body_path),
            base=base,
            head=artifacts.branch_name,
            draft=draft,
        )
        if not result.get("success") and "error" not in result:
            result["error"] = result.get("stderr") or "gh-pr-create-failed"
        return result

    def maybe_tag(self, *, repo_path: str, name: str, enabled: bool) -> int:
        git = GitAdapter(repo_path)
        if not enabled or not git.has_git():
            return 0
        return git.tag(name, enabled=enabled)

    def _render_pr_body(self, state: PipelineRunState, project_name: str, *, mock: bool, dry: bool) -> str:
        lines = [
            f"# Software factory PR — {project_name}",
            "",
            "## Summary",
            f"Run `{state.run_id}` produced by {state.flow}.",
            "",
            "## Scope",
            f"- languages: {[lang.value for lang in state.languages]}",
            f"- backends_used: {[b.value for b in state.backends_used]}",
            "",
            "## Milestones",
        ]
        if state.milestone_plan:
            for m in state.milestone_plan.milestones:
                lines.append(f"- **{m.milestone_id}** {m.title} — {m.objective}")
        lines += [
            "",
            "## Tests",
            "See Quality Gates section below.",
            "",
            "## Quality Gates",
        ]
        for qg in state.quality_gates:
            lines.append(f"- {qg.language.value}: {qg.overall_status.value}")
        lines += [
            "",
            "## Security Review",
            (f"- status: {state.security_review.status.value}" if state.security_review else "- not run"),
            "",
            "## Release Gate Result",
            (f"- decision: {state.release_check.decision.value}" if state.release_check else "- not run"),
            "",
            "## Known Limitations",
            f"- MockExecutionUsed: `{mock}`",
            f"- DryRun: `{dry}`",
        ]
        return "\n".join(lines) + "\n"
