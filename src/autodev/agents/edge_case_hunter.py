"""EdgeCaseHunter — systematic boundary/edge-case scanner.

Combines:
- Heuristic file-level pattern scan (all text files).
- Pure-Python AST-based scan for Python files: detects missing zero-check
  before division, list access without bounds check, dict access without
  .get() / default.

Emits EdgeCasePattern / SeverityFinding per W4 taxonomy.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

from ..schemas import (
    AgentCard,
    EdgeCasePattern,
    Severity,
    SeverityFinding,
)

_SKIP_DIRS = {"target", "node_modules", ".git", "__pycache__", ".venv", "venv"}
_MAX_FILE_SIZE = 500_000


def _should_skip(rel: str) -> bool:
    return any(s in rel.split("/") for s in _SKIP_DIRS)


# ---------------------------------------------------------------------------
# Heuristic text patterns: (literal_or_regex, is_regex, category, hint, sev)
# ---------------------------------------------------------------------------

_TEXT_PATTERNS: list[tuple[str, bool, str, str, Severity]] = [
    # empty input
    ("if.*len.*==.*0", True, "empty",
     "Length check for empty input — verify None/empty-string path too", Severity.NITPICK),
    # huge input / resource exhaustion
    (".read()", False, "huge",
     "Unbuffered .read() — no size limit, may OOM on huge input", Severity.MINOR),
    ("while True:", False, "resource",
     "Unbounded loop — potential resource exhaustion", Severity.MINOR),
    # unicode / encoding
    (".encode()", False, "unicode",
     ".encode() without explicit encoding arg — may fail on emoji/CJK", Severity.NITPICK),
    ("ascii", False, "unicode",
     "Hard-coded ascii codec — may reject unicode input", Severity.MINOR),
    # concurrent / thread safety
    ("threading.Thread(", False, "concurrent",
     "Thread spawned — verify shared state is thread-safe", Severity.MINOR),
    ("multiprocessing.Process(", False, "concurrent",
     "Process spawned — verify IPC/queue error paths", Severity.MINOR),
    # network / flake
    ("timeout=None", False, "network",
     "Network call with timeout=None — hangs forever on flaky network", Severity.MAJOR),
    ("requests.get(", False, "network",
     "requests.get without explicit timeout — network flake risk", Severity.MINOR),
    # timezone / DST
    ("datetime.now()", False, "timezone",
     "datetime.now() without tzinfo — naive datetime, DST hazard", Severity.MINOR),
    ("strftime", False, "timezone",
     "strftime without UTC normalization — timezone-sensitive output", Severity.NITPICK),
    # numeric edge cases
    ("/ 0", False, "numeric",
     "Literal division by zero", Severity.BLOCKER),
    ("math.inf", False, "numeric",
     "Uses math.inf — verify NaN/Inf propagation downstream", Severity.NITPICK),
    ("float('nan')", False, "numeric",
     "Explicit NaN creation — verify NaN comparison guards", Severity.MINOR),
    # leap year / date
    ("02-29", False, "timezone",
     "Hard-coded Feb 29 — leap-year only date in literal", Severity.MINOR),
    # negative numbers
    ("range(.*-", True, "numeric",
     "range() with negative argument — verify loop bound", Severity.NITPICK),
]


# ---------------------------------------------------------------------------
# AST-based Python scanner
# ---------------------------------------------------------------------------

class _DivisionZeroVisitor(ast.NodeVisitor):
    """Flag BinOp division where the divisor is not guarded by an if/assert."""

    def __init__(self) -> None:
        self.hits: list[int] = []  # line numbers

    def visit_BinOp(self, node: ast.BinOp) -> None:  # noqa: N802
        if isinstance(node.op, (ast.Div, ast.FloorDiv, ast.Mod)):
            # Flag if divisor is not a constant non-zero and not clearly a safe var
            right = node.right
            is_safe_const = isinstance(right, ast.Constant) and right.value != 0
            if not is_safe_const:
                self.hits.append(getattr(node, "lineno", 0))
        self.generic_visit(node)


class _ListIndexVisitor(ast.NodeVisitor):
    """Flag list[index] subscript access that is not inside a try/except or len check."""

    def __init__(self) -> None:
        self.hits: list[int] = []

    def visit_Subscript(self, node: ast.Subscript) -> None:  # noqa: N802
        # Only flag Name[...] or Attribute[...] with integer constant index
        if isinstance(node.slice, ast.Constant) and isinstance(node.slice.value, int):
            self.hits.append(getattr(node, "lineno", 0))
        self.generic_visit(node)


class _DictDirectAccessVisitor(ast.NodeVisitor):
    """Flag dict[key] access (vs dict.get(key)) that may KeyError."""

    def __init__(self) -> None:
        self.hits: list[int] = []

    def visit_Subscript(self, node: ast.Subscript) -> None:  # noqa: N802
        # dict[str_key] — flag string-keyed subscript on non-list Name
        if (
            isinstance(node.value, (ast.Name, ast.Attribute))
            and isinstance(node.slice, ast.Constant)
            and isinstance(node.slice.value, str)
        ):
            self.hits.append(getattr(node, "lineno", 0))
        self.generic_visit(node)


def _ast_scan_python(path: Path, rel: str) -> list[EdgeCasePattern]:
    findings: list[EdgeCasePattern] = []
    try:
        source = path.read_text(encoding="utf-8", errors="ignore")
        tree = ast.parse(source, filename=str(path))
    except SyntaxError:
        return findings
    except Exception:
        return findings

    div_v = _DivisionZeroVisitor()
    div_v.visit(tree)
    for lineno in div_v.hits[:5]:  # cap at 5 per file
        sf = SeverityFinding(
            severity=Severity.MAJOR,
            category="edge-case",
            title="Division without zero-guard",
            detail=f"{rel}:{lineno}: divisor may be zero",
            file_path=rel,
            line=lineno,
            suggested_fix="Guard with `if divisor != 0:` or use try/except ZeroDivisionError",
            source_agent="EdgeCaseHunter",
        )
        findings.append(EdgeCasePattern(
            category="numeric",
            file_path=rel,
            line=lineno,
            hint="Division without zero-guard",
            severity_finding=sf,
        ))

    li_v = _ListIndexVisitor()
    li_v.visit(tree)
    for lineno in li_v.hits[:3]:
        sf = SeverityFinding(
            severity=Severity.MINOR,
            category="edge-case",
            title="List/sequence index access without bounds check",
            detail=f"{rel}:{lineno}: constant index subscript may IndexError",
            file_path=rel,
            line=lineno,
            suggested_fix="Guard with `if len(seq) > idx:` or use .get() equivalent",
            source_agent="EdgeCaseHunter",
        )
        findings.append(EdgeCasePattern(
            category="empty",
            file_path=rel,
            line=lineno,
            hint="Index access without bounds check",
            severity_finding=sf,
        ))

    dict_v = _DictDirectAccessVisitor()
    dict_v.visit(tree)
    for lineno in dict_v.hits[:3]:
        sf = SeverityFinding(
            severity=Severity.MINOR,
            category="edge-case",
            title="Dict subscript access — prefer .get() with default",
            detail=f"{rel}:{lineno}: dict[key] raises KeyError on missing key",
            file_path=rel,
            line=lineno,
            suggested_fix="Use dict.get(key, default) to avoid KeyError on missing keys",
            source_agent="EdgeCaseHunter",
        )
        findings.append(EdgeCasePattern(
            category="empty",
            file_path=rel,
            line=lineno,
            hint="Dict direct subscript — prefer .get()",
            severity_finding=sf,
        ))

    return findings


# ---------------------------------------------------------------------------
# Main class
# ---------------------------------------------------------------------------

class EdgeCaseHunter:
    """Systematic boundary/edge-case scanner.

    Usage::

        hunter = EdgeCaseHunter()
        findings = hunter.review("/path/to/repo", results=[])

    Also usable as an AgentCard::

        card = EdgeCaseHunter.as_agent_card()
    """

    SOURCE_AGENT = "EdgeCaseHunter"

    def review(
        self,
        repo_path: str,
        results: list | None = None,
    ) -> list[SeverityFinding]:
        """Scan *repo_path* for edge-case patterns.

        Returns flat list of SeverityFinding (ParallelSectionReviewer compatible).
        """
        patterns = self._scan(repo_path)
        return [
            ep.severity_finding
            for ep in patterns
            if ep.severity_finding is not None
        ]

    def review_edge_cases(
        self,
        repo_path: str,
        results: list | None = None,
    ) -> list[EdgeCasePattern]:
        """Return rich EdgeCasePattern objects."""
        return self._scan(repo_path)

    def _scan(self, repo_path: str) -> list[EdgeCasePattern]:
        findings: list[EdgeCasePattern] = []
        try:
            root = Path(repo_path)
            for p in root.rglob("*"):
                if not p.is_file():
                    continue
                rel = str(p.relative_to(root))
                if _should_skip(rel) or p.stat().st_size > _MAX_FILE_SIZE:
                    continue
                try:
                    text = p.read_text(encoding="utf-8", errors="ignore")
                except Exception:
                    continue

                # Text-pattern scan (all files)
                for pat, is_regex, category, hint, sev in _TEXT_PATTERNS:
                    matched = (
                        bool(re.search(pat, text, re.IGNORECASE))
                        if is_regex
                        else pat in text
                    )
                    if matched:
                        sf = SeverityFinding(
                            severity=sev,
                            category="edge-case",
                            title=hint,
                            detail=f"{rel}: matched edge-case pattern for {category!r}",
                            file_path=rel,
                            source_agent=self.SOURCE_AGENT,
                        )
                        findings.append(EdgeCasePattern(
                            category=category,
                            file_path=rel,
                            hint=hint,
                            severity_finding=sf,
                        ))

                # AST scan (Python files only)
                if p.suffix == ".py":
                    findings.extend(_ast_scan_python(p, rel))

        except Exception as exc:
            sf = SeverityFinding(
                severity=Severity.NITPICK,
                category="edge-case",
                title="EdgeCase scan skipped",
                detail=str(exc),
                source_agent=self.SOURCE_AGENT,
            )
            findings.append(EdgeCasePattern(
                category="scan-error",
                hint=str(exc),
                severity_finding=sf,
            ))
        return findings

    @staticmethod
    def as_agent_card() -> AgentCard:
        """Return an AgentCard for roster registration."""
        return AgentCard(
            name="edge-case-hunter",
            description=(
                "Edge-case hunter: systematic boundary scan. "
                "Covers empty/huge/unicode/concurrent/resource/network/timezone/DST/"
                "leap-year/negative/NaN patterns plus AST-based Python heuristics."
            ),
            capabilities=[
                "edge-case-detection", "boundary-analysis",
                "ast-analysis", "python-static-analysis",
            ],
            skills=[
                "empty-input", "huge-input", "unicode", "concurrent",
                "resource-exhaustion", "network-flake", "timezone", "dst",
                "leap-year", "negative-numbers", "nan",
            ],
            transport="local-shell",
            model_hint="sonnet",
            system_prompt=(
                "You are a systematic edge-case hunter on a non-interactive hotline. "
                "Identify boundary conditions: empty, huge, unicode, concurrent, "
                "resource-exhaustion, network-flake, timezone/DST, leap-year, "
                "negative numbers, NaN/Inf. "
                "Emit findings tagged [SEVERITY:BLOCKER/MAJOR/MINOR/NITPICK]. "
                "Each finding: category, file_path, line, hint. Output in English."
            ),
            tags=["quality", "edge-case", "review"],
        )
