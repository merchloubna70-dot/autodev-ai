"""Security Reviewer — static scan of generated/changed files."""
from __future__ import annotations

from pathlib import Path

from ..schemas import (
    GateStatus,
    PipelineRunState,
    RiskLevel,
    SecurityReviewReport,
    Severity,
    SeverityFinding,
)
from ..utils.command_safety import DEFAULT_DENYLIST
from ._crewai_bridge import make_agent

# File-scanning denylist: full DEFAULT_DENYLIST minus patterns that legitimately
# appear in source code as variable names (`exec `, `eval`).
# `" env "` is kept here but is doc/code-context-sensitive (see _DOC_CONTEXT_SENSITIVE_PATTERNS).
FILE_SCAN_DENYLIST: tuple[str, ...] = tuple(
    p for p in DEFAULT_DENYLIST if p not in ("eval", "exec ")
)


# Treat every file as potentially containing prose: apply line-level
# shell-context filtering for these patterns regardless of extension.
# This catches `env = os.environ.copy()` (Python prose) as a false positive,
# while still flagging `env LANG=zh subprocess.run(...)` (true shell call).
_CODE_AND_DOC_CONTEXT_PATTERNS: frozenset[str] = frozenset({" env ", "printenv"})


SECRET_PATTERNS = (
    "AKIA",            # AWS keys
    "-----BEGIN RSA",
    "-----BEGIN PRIVATE KEY",
    "AIzaSy",          # google api
    "ghp_",            # github pat
    "sk-",             # openai-ish
    "claude_api_key",
    "anthropic_api_key",
)

_SEVERITY_PREFIX = {
    Severity.BLOCKER: "[BLOCKER]",
    Severity.MAJOR: "[MAJOR]",
    Severity.MINOR: "[MINOR]",
    Severity.NITPICK: "[NITPICK]",
}

# Denylist patterns that can produce false positives in prose/doc files and
# require a shell-context marker on the same line to be considered real.
_DOC_CONTEXT_SENSITIVE_PATTERNS: frozenset[str] = frozenset({" env "})

# Markers that indicate a line is shell context even inside a doc file.
# NOTE: a single backtick is NOT enough — markdown inline backticks frequently
# wrap filenames or variable names (e.g. `.env` referring to a file) which is
# not shell context. Real shell context requires explicit hints: `$ cmd` prompts,
# `bash`/`sh`/`zsh` words, `#!` shebangs, or actual fenced code blocks
# (handled separately via `in_fence`).
_SHELL_CONTEXT_MARKERS: tuple[str, ...] = (
    "$ ",
    "bash",
    "zsh",
    "sh ",
    "#!",
    "```bash",
    "```sh",
    "```zsh",
)


def _is_doc_file(rel_path: str) -> bool:
    """Return True for documentation/text files that may contain prose with shell keywords."""
    parts = rel_path.replace("\\", "/").split("/")
    # files inside docs/ or .dev-factory/ top-level dirs
    if parts[0] in ("docs", ".dev-factory"):
        return True
    # common doc extensions
    ext = Path(rel_path).suffix.lower()
    return ext in (".md", ".rst", ".txt")


def _is_pure_shell_file(rel_path: str) -> bool:
    """Return True for files whose content is, by extension, pure shell code.
    Pattern matches in these files always indicate a real shell command,
    so we never apply line-level prose filtering to them."""
    ext = Path(rel_path).suffix.lower()
    return ext in (".sh", ".bash", ".zsh", ".fish", ".ksh")


def _line_has_shell_context(line: str) -> bool:
    """Return True if a line contains a shell-context marker indicating code, not prose."""
    lower = line.lower()
    for marker in _SHELL_CONTEXT_MARKERS:
        if marker in lower:
            return True
    return False


class SecurityReviewerAgent:
    def __init__(self) -> None:
        self.agent = make_agent(
            role="Security Reviewer",
            goal="Find unsafe shell, secrets, dangerous deps, missing input validation.",
            backstory="An AppSec engineer who blocks releases on critical findings.",
        )

    def review(self, *, repo_path: str, state: PipelineRunState | None = None) -> SecurityReviewReport:
        findings: list[str] = []
        severity_findings: list[SeverityFinding] = []
        blocked: list[str] = []
        false_positives_filtered: list[str] = []
        severity = RiskLevel.LOW
        root = Path(repo_path)
        for p in root.rglob("*"):
            if not p.is_file():
                continue
            rel = str(p.relative_to(root))
            if any(skip in rel.split("/") for skip in ("target", "node_modules", ".dev-factory", ".git", ".venv", "venv", ".pytest_cache", ".mypy_cache", ".ruff_cache", "__pycache__", "dist", "build")):
                continue
            if p.stat().st_size > 1_500_000:
                continue
            try:
                text = p.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            is_doc = _is_doc_file(rel)
            for pat in FILE_SCAN_DENYLIST:
                if pat not in text:
                    continue
                # Pure-shell files (.sh / .bash / .zsh / …) always flag — never
                # filter as "could be prose". Otherwise:
                # - patterns that frequently appear in both prose AND legitimate code
                #   (` env ` matches Python `env = os.environ`) go through line-level
                #   shell-context filtering regardless of file extension.
                # - patterns that are only doc-sensitive go through filtering only in docs.
                is_pure_shell = _is_pure_shell_file(rel)
                apply_line_filter = (not is_pure_shell) and (
                    pat in _CODE_AND_DOC_CONTEXT_PATTERNS
                    or (is_doc and pat in _DOC_CONTEXT_SENSITIVE_PATTERNS)
                )
                if apply_line_filter:
                    lines = text.splitlines()
                    in_fence = False
                    any_shell_match = False
                    for ln in lines:
                        stripped = ln.strip()
                        if stripped.startswith("```") or stripped.startswith("~~~"):
                            in_fence = not in_fence
                        if pat in ln:
                            if in_fence or _line_has_shell_context(ln):
                                any_shell_match = True
                                break
                    if not any_shell_match:
                        # Pure prose mention — skip and record as filtered FP
                        false_positives_filtered.append(
                            f"{rel}: doc-context FP suppressed for pattern {pat!r}"
                        )
                        continue
                msg = f"{rel}: forbidden shell pattern {pat!r}"
                sev = Severity.BLOCKER
                findings.append(f"{_SEVERITY_PREFIX[sev]} {msg}")
                severity_findings.append(SeverityFinding(
                    severity=sev,
                    category="security",
                    title=f"Forbidden shell pattern {pat!r}",
                    detail=msg,
                    file_path=rel,
                    source_agent="SecurityReviewerAgent",
                ))
                blocked.append(pat)
                severity = max(severity, RiskLevel.HIGH, key=lambda r: ["low","medium","high","critical"].index(r.value))
            for pat in SECRET_PATTERNS:
                if pat in text:
                    msg = f"{rel}: possible secret pattern {pat!r}"
                    sev = Severity.BLOCKER
                    findings.append(f"{_SEVERITY_PREFIX[sev]} {msg}")
                    severity_findings.append(SeverityFinding(
                        severity=sev,
                        category="security",
                        title=f"Possible secret pattern {pat!r}",
                        detail=msg,
                        file_path=rel,
                        source_agent="SecurityReviewerAgent",
                    ))
                    severity = RiskLevel.CRITICAL
        status = GateStatus.PASSED
        if severity in (RiskLevel.HIGH, RiskLevel.CRITICAL):
            status = GateStatus.FAILED
        elif findings:
            status = GateStatus.PASSED  # findings but not severe
        return SecurityReviewReport(
            findings=findings,
            blocked_commands=sorted(set(blocked)),
            severity=severity,
            status=status,
            severity_findings=severity_findings,
            false_positives_filtered=false_positives_filtered,
        )
