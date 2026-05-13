"""GitHub adapter — issue / PR helpers.

Network access is NOT required for the default flow; this adapter only
exposes structured helpers that consume cached / supplied content.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass


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
