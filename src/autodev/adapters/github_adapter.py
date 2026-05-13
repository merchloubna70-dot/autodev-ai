"""GitHub adapter — issue / PR helpers.

Network access is NOT required for the default flow; this adapter only
exposes structured helpers that consume cached / supplied content.
"""
from __future__ import annotations

import json
import re
import shutil
from dataclasses import dataclass
from pathlib import Path


@dataclass
class IssuePayload:
    issue_id: str
    title: str
    body: str
    labels: list[str]


class GitHubAdapter:
    """Pure-Python adapter; no network calls in the default code path.

    If a future caller wires in real HTTP, it must do so through this class
    so the rest of the system stays decoupled.
    """

    URL_RE = re.compile(r"github\.com/[^/]+/[^/]+/issues/(\d+)")
    PR_URL_RE = re.compile(r"https://github\.com/[^\s]+/pull/\d+")

    def parse_issue_text(self, text: str, *, fallback_id: str = "ISSUE-0") -> IssuePayload:
        """Parse a markdown / plaintext issue. Title is the first heading or line."""
        title = ""
        for line in text.splitlines():
            ln = line.strip()
            if not ln:
                continue
            if ln.startswith("# "):
                title = ln.lstrip("# ").strip()
                break
            title = ln
            break
        labels: list[str] = []
        for m in re.finditer(r"label[s]?:\s*([^\n]+)", text, re.IGNORECASE):
            for tok in re.split(r"[,\s]+", m.group(1)):
                tok = tok.strip()
                if tok:
                    labels.append(tok)
        return IssuePayload(issue_id=fallback_id, title=title or "untitled", body=text, labels=labels)

    def parse_issue_json(self, text: str) -> IssuePayload:
        data = json.loads(text)
        return IssuePayload(
            issue_id=str(data.get("id") or data.get("number") or "ISSUE-0"),
            title=str(data.get("title", "untitled")),
            body=str(data.get("body", "")),
            labels=list(data.get("labels", []) or []),
        )

    def extract_issue_id_from_url(self, url: str) -> str | None:
        m = self.URL_RE.search(url)
        return m.group(1) if m else None

    # ------------------------------------------------------------------
    # gh CLI helpers — all off by default; require gh binary to be present
    # ------------------------------------------------------------------

    def gh_available(self) -> bool:
        """Return True iff the `gh` binary is on PATH."""
        return shutil.which("gh") is not None

    def auth_status(self, repo_path: str) -> dict:
        """Call `gh auth status`; returns dict with success, stdout, stderr."""
        if not self.gh_available():
            return {"success": False, "error": "gh-missing"}
        from ..executors.shell_executor import ShellExecutor
        sh = ShellExecutor(cwd=str(Path(repo_path).resolve()))
        result = sh.run("gh auth status")
        return {
            "success": result.exit_code == 0,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "exit_code": result.exit_code,
        }

    def create_pr(
        self,
        repo_path: str,
        title: str,
        body_path: str,
        base: str = "main",
        head: str | None = None,
        draft: bool = True,
    ) -> dict:
        """Create a GitHub PR via `gh pr create`.

        Returns dict with at minimum:
            success (bool), stdout (str), stderr (str), pr_url (str | None)

        Never raises — all errors are returned in the dict.
        """
        if not self.gh_available():
            return {"success": False, "error": "gh-missing", "stdout": "", "stderr": "", "pr_url": None}

        from ..executors.shell_executor import ShellExecutor
        sh = ShellExecutor(cwd=str(Path(repo_path).resolve()))

        cmd_parts = [
            "gh pr create",
            f'--title "{title}"',
            f"--body-file {body_path}",
            f"--base {base}",
        ]
        if head:
            cmd_parts.append(f"--head {head}")
        if draft:
            cmd_parts.append("--draft")

        cmd = " ".join(cmd_parts)
        result = sh.run(cmd)

        # Extract PR URL from stdout
        pr_url: str | None = None
        m = self.PR_URL_RE.search(result.stdout)
        if m:
            pr_url = m.group(0)

        if not result.allowed:
            return {
                "success": False,
                "error": "command-rejected",
                "stdout": result.stdout,
                "stderr": result.stderr,
                "pr_url": None,
            }

        return {
            "success": result.exit_code == 0,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "exit_code": result.exit_code,
            "pr_url": pr_url,
        }
