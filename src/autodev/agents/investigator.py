"""InvestigatorAgent — opens a structured case file for forensic investigation.

Classifies the input token (ticket-id / log-path / error-msg / code-area /
problem-description), collects evidence without making real network calls,
calibrates the investigation mode, and writes a markdown case file.
"""
from __future__ import annotations

import re
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path

from ..schemas import CaseFile, EvidenceEntry, InvestigationInputKind

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

_TICKET_RE = re.compile(r"^[A-Z][A-Z0-9]{1,9}-\d+$")


def _slug(token: str) -> str:
    """Return a lowercase-alphanumeric-hyphens slug from an arbitrary token."""
    s = re.sub(r"[^a-z0-9]+", "-", token.lower())
    s = s.strip("-")[:64]
    return s or "case"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# InvestigatorAgent
# ---------------------------------------------------------------------------


class InvestigatorAgent:
    """Forensic case investigator — Detective persona."""

    name = "Detective"
    title = "Investigator"
    icon = "🔍"

    # ------------------------------------------------------------------
    # 1. open_case
    # ------------------------------------------------------------------

    def open_case(self, input_token: str, repo_path: str) -> CaseFile:
        """Classify ``input_token`` and build the initial CaseFile."""
        kind = self._classify(input_token, repo_path)
        case_id = str(uuid.uuid4())[:8]
        slug = _slug(input_token if kind == InvestigationInputKind.TICKET_ID else input_token[:40])
        return CaseFile(
            case_id=case_id,
            slug=slug,
            input_token=input_token,
            input_kind=kind,
            mode="calibrating",
        )

    # ------------------------------------------------------------------
    # 2. collect_evidence
    # ------------------------------------------------------------------

    def collect_evidence(self, case: CaseFile, repo_path: str = ".") -> CaseFile:
        """Collect evidence based on the classified input kind (no real network).

        ``repo_path`` anchors all file-system operations (grep, glob, git blame)
        to the target repository rather than the process CWD.
        """
        entries: list[EvidenceEntry] = list(case.evidence)

        kind = case.input_kind
        token = case.input_token

        if kind == InvestigationInputKind.TICKET_ID:
            entries.extend(self._collect_ticket(token))

        elif kind == InvestigationInputKind.LOG_PATH:
            entries.extend(self._collect_log(token))

        elif kind == InvestigationInputKind.ERROR_MSG:
            entries.extend(self._collect_error_msg(token, case, repo_path))

        elif kind == InvestigationInputKind.CODE_AREA:
            entries.extend(self._collect_code_area(token, case, repo_path))

        elif kind == InvestigationInputKind.PROBLEM_DESC:
            entries.extend(self._collect_prose(token, case, repo_path))

        elif kind == InvestigationInputKind.RESUME:
            entries.extend(self._collect_resume(token))

        case.evidence = entries
        case.updated_at = _now_iso()
        return case

    # ------------------------------------------------------------------
    # 3. calibrate
    # ------------------------------------------------------------------

    def calibrate(self, case: CaseFile) -> str:
        """Return 'defect-chasing' or 'area-exploration'."""
        symptom_kinds = {
            InvestigationInputKind.TICKET_ID,
            InvestigationInputKind.LOG_PATH,
            InvestigationInputKind.ERROR_MSG,
        }
        if case.input_kind in symptom_kinds:
            return "defect-chasing"
        return "area-exploration"

    # ------------------------------------------------------------------
    # 4. summarize
    # ------------------------------------------------------------------

    def summarize(self, case: CaseFile) -> str:
        """Render the case file as a markdown report string."""
        lines = [
            f"# Case File: {case.slug}",
            "",
            f"**ID:** {case.case_id}  ",
            f"**Input:** `{case.input_token}`  ",
            f"**Kind:** {case.input_kind.value}  ",
            f"**Mode:** {case.mode}  ",
            f"**Created:** {case.created_at}  ",
            "",
            "## Evidence",
            "",
        ]
        if case.evidence:
            for e in case.evidence:
                ref = f" — [{e.reference}]" if e.reference else ""
                path_part = f" `{e.path}`" if e.path else ""
                snippet_part = f"\n  > {e.snippet[:200]}" if e.snippet else ""
                lines.append(f"- **{e.kind}**{path_part}{ref}{snippet_part}")
        else:
            lines.append("_No evidence collected._")

        lines += ["", "## Hypotheses", ""]
        if case.hypotheses:
            for h in case.hypotheses:
                lines.append(f"- {h}")
        else:
            lines.append("_None yet._")

        lines += ["", "## Recommended Next Steps", ""]
        if case.next_steps:
            for ns in case.next_steps:
                lines.append(f"- {ns}")
        else:
            lines.append("_See mode-specific guidance._")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # 5. run (orchestrator)
    # ------------------------------------------------------------------

    def run(self, input_token: str, repo_path: str) -> CaseFile:
        """Orchestrate open → collect → calibrate → summarize → write."""
        case = self.open_case(input_token, repo_path)
        case = self.collect_evidence(case, repo_path)
        mode = self.calibrate(case)
        case.mode = mode

        # Build next_steps based on mode
        if mode == "defect-chasing":
            case.next_steps = [
                "Identify the first Confirmed evidence (error string, stack frame, test name).",
                "Trace backward from the symptom to the producing condition.",
                "Form ≥1 falsifiable hypothesis with confirm/refute criteria.",
                "Run `autodev fix-bug --bug '...'` once root cause is located.",
            ]
        else:
            case.next_steps = [
                "Map the public interfaces (entry points, outputs, side effects).",
                "Scan frequently-used symbols with grep / repo-map.",
                "Build a control-flow model (branches, loops, state-machine transitions).",
                "Document the mental model in the case file for handoff.",
            ]

        summary = self.summarize(case)
        case.summary = summary

        # Write case file
        out_dir = Path(repo_path) / ".dev-factory" / "investigations"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"{case.slug}.md"
        out_path.write_text(summary, encoding="utf-8")
        case.file_path = str(out_path)
        case.updated_at = _now_iso()

        return case

    # ------------------------------------------------------------------
    # Internal evidence collectors (all wrapped in try/except — no crash)
    # ------------------------------------------------------------------

    def _classify(self, token: str, repo_path: str) -> InvestigationInputKind:
        """Classify a raw input token into one of the InvestigationInputKind values."""
        # Resume: path to an existing .md case file
        p = Path(token)
        if p.suffix == ".md" and p.exists():
            return InvestigationInputKind.RESUME

        # Ticket ID: e.g. PROJ-123
        if _TICKET_RE.match(token.strip()):
            return InvestigationInputKind.TICKET_ID

        # Log path: file path that exists on disk
        if p.exists() and p.is_file():
            return InvestigationInputKind.LOG_PATH

        # Code area: glob-like or directory/module path (no spaces, contains / or *)
        if not any(c == " " for c in token) and ("/" in token or "*" in token or token.endswith(".py") or token.endswith(".rs")):
            return InvestigationInputKind.CODE_AREA

        # Error message: contains typical error keywords
        error_keywords = ("error", "exception", "traceback", "panicked", "failed", "fatal", "assert", "TypeError", "ValueError")
        if any(kw.lower() in token.lower() for kw in error_keywords):
            return InvestigationInputKind.ERROR_MSG

        # Default: prose problem description
        return InvestigationInputKind.PROBLEM_DESC

    def _collect_ticket(self, ticket_id: str) -> list[EvidenceEntry]:
        """Try gh issue view; silently skip on failure."""
        entries: list[EvidenceEntry] = []
        try:
            result = subprocess.run(
                ["gh", "issue", "view", ticket_id, "--json", "title,body,state,labels"],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0 and result.stdout.strip():
                entries.append(EvidenceEntry(
                    kind="issue",
                    reference=ticket_id,
                    snippet=result.stdout.strip()[:500],
                ))
        except Exception:
            pass
        if not entries:
            entries.append(EvidenceEntry(
                kind="issue",
                reference=ticket_id,
                snippet=f"[ticket {ticket_id}] — gh CLI unavailable or ticket not found; treat as hypothesis anchor.",
            ))
        return entries

    def _collect_log(self, log_path: str) -> list[EvidenceEntry]:
        """Sample the last 40 lines of a log file."""
        entries: list[EvidenceEntry] = []
        try:
            p = Path(log_path)
            if p.exists() and p.is_file():
                text = p.read_text(encoding="utf-8", errors="replace")
                lines = text.splitlines()
                sample = "\n".join(lines[-40:]) if len(lines) > 40 else text
                entries.append(EvidenceEntry(
                    kind="log-sample",
                    path=log_path,
                    snippet=sample[:1000],
                ))
        except Exception:
            pass
        if not entries:
            entries.append(EvidenceEntry(
                kind="log-sample",
                path=log_path,
                snippet="[log file not found or unreadable]",
            ))
        return entries

    def _collect_error_msg(self, error_msg: str, case: CaseFile, repo_path: str = ".") -> list[EvidenceEntry]:
        """Grep for the error across the repo (first keyword only, fail-safe)."""
        entries: list[EvidenceEntry] = []
        resolved_repo = str(Path(repo_path).resolve())
        # Extract first meaningful word from error message as search term
        words = [w for w in re.split(r"\W+", error_msg) if len(w) >= 4]
        keyword = words[0] if words else error_msg[:20]
        try:
            result = subprocess.run(
                ["grep", "-r", "--include=*.py", "--include=*.rs", "-n", "-l", keyword, "."],
                capture_output=True, text=True, timeout=15, cwd=resolved_repo,
            )
            if result.returncode == 0 and result.stdout.strip():
                for fp in result.stdout.strip().splitlines()[:5]:
                    entries.append(EvidenceEntry(
                        kind="grep-hit",
                        path=str(Path(resolved_repo) / fp.strip().lstrip("./")),
                        snippet=f"contains keyword: {keyword!r}",
                    ))
        except Exception:
            pass
        if not entries:
            entries.append(EvidenceEntry(
                kind="grep-hit",
                snippet=f"[no grep results for keyword {keyword!r} or grep unavailable]",
            ))
        # Register the raw error as a hypothesis
        case.hypotheses.append(f"Hypothesis #1 (user-supplied): {error_msg[:200]}")
        return entries

    def _collect_code_area(self, area: str, case: CaseFile, repo_path: str = ".") -> list[EvidenceEntry]:
        """List files matching the area glob + sample git blame on first hit."""
        entries: list[EvidenceEntry] = []
        resolved_repo = Path(repo_path).resolve()
        try:
            import glob as _glob
            # Anchor the glob pattern to repo_path: if area is relative, search within repo_path
            if not Path(area).is_absolute():
                anchor = str(resolved_repo / area)
            else:
                anchor = area
            hits = list(_glob.glob(anchor, recursive=True))[:10]
            for fp in hits:
                entries.append(EvidenceEntry(
                    kind="file",
                    path=fp,
                    snippet="",
                ))
            if hits:
                # Attempt git blame on first file (first 10 lines)
                try:
                    blame = subprocess.run(
                        ["git", "blame", "--porcelain", "-l", hits[0]],
                        capture_output=True, text=True, timeout=10,
                        cwd=str(resolved_repo),
                    )
                    if blame.returncode == 0:
                        entries.append(EvidenceEntry(
                            kind="git-blame",
                            path=hits[0],
                            snippet=blame.stdout[:600],
                        ))
                except Exception:
                    pass
        except Exception:
            pass
        if not entries:
            entries.append(EvidenceEntry(
                kind="file",
                path=area,
                snippet="[no files found matching area pattern]",
            ))
        case.hypotheses.append(f"Exploration target: {area}")
        return entries

    def _collect_prose(self, prose: str, case: CaseFile, repo_path: str = ".") -> list[EvidenceEntry]:
        """Extract keywords from prose and run a broad grep."""
        entries: list[EvidenceEntry] = []
        resolved_repo = str(Path(repo_path).resolve())
        words = [w for w in re.split(r"\W+", prose) if len(w) >= 5]
        keywords = list(dict.fromkeys(words))[:3]  # top 3 unique
        for kw in keywords:
            try:
                result = subprocess.run(
                    ["grep", "-r", "--include=*.py", "--include=*.rs", "-l", "-n", kw, "."],
                    capture_output=True, text=True, timeout=10, cwd=resolved_repo,
                )
                if result.returncode == 0 and result.stdout.strip():
                    for fp in result.stdout.strip().splitlines()[:3]:
                        entries.append(EvidenceEntry(
                            kind="grep-hit",
                            path=str(Path(resolved_repo) / fp.strip().lstrip("./")),
                            snippet=f"keyword: {kw!r}",
                        ))
            except Exception:
                pass
        if not entries:
            entries.append(EvidenceEntry(
                kind="grep-hit",
                snippet=f"[no grep results for keywords {keywords} or grep unavailable]",
            ))
        case.hypotheses.append(f"Hypothesis #1 (prose): {prose[:200]}")
        return entries

    def _collect_resume(self, path: str) -> list[EvidenceEntry]:
        """Load an existing case file for resumption."""
        entries: list[EvidenceEntry] = []
        try:
            text = Path(path).read_text(encoding="utf-8", errors="replace")
            entries.append(EvidenceEntry(
                kind="file",
                path=path,
                snippet=text[:500],
            ))
        except Exception:
            entries.append(EvidenceEntry(
                kind="file",
                path=path,
                snippet="[case file not readable]",
            ))
        return entries


# BMAD-17: register agent menu at module load time
from ..schemas import AgentMenuEntry  # noqa: E402
from ._menu import register_default_menu  # noqa: E402

register_default_menu("investigator", [
    AgentMenuEntry(code="OC", description="Open investigation case", skill="investigator"),
    AgentMenuEntry(code="CE", description="Collect evidence", skill="investigator"),
    AgentMenuEntry(code="RS", description="Resume case from file", skill="investigator"),
])
