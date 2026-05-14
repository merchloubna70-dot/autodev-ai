"""RepoMap — lightweight import-graph + identifier scoring for context ranking.

Scoring algorithm (pure Python, NetworkX-free):
  1. Build import graph from Python files using regex heuristics.
  2. Compute weighted in-degree (how many files import each file).
  3. Apply seed boost: +10x if any seed identifier appears in file content,
     +50x if the file is in the ``open_files`` set.
  4. Rank by composite score descending; truncate to token_budget.

tree-sitter is a future enhancement only — not required. This module uses
stdlib pathlib / re / collections exclusively.
"""
from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Sequence
from pathlib import Path

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_IMPORT_RE = re.compile(
    r"^\s*(?:from\s+([\w.]+)\s+import|import\s+([\w.,\s]+))",
    re.MULTILINE,
)

_DEF_RE = re.compile(r"^\s*(?:def|class|async def)\s+(\w+)", re.MULTILINE)

_MAX_FILE_BYTES = 128 * 1024  # skip very large files to stay fast


def _read_safe(path: Path) -> str:
    """Read up to _MAX_FILE_BYTES of a file, ignoring decode errors."""
    try:
        with path.open("rb") as fh:
            raw = fh.read(_MAX_FILE_BYTES)
        return raw.decode("utf-8", errors="replace")
    except OSError:
        return ""


def _extract_imports(content: str) -> list[str]:
    """Return list of module strings referenced in import statements."""
    modules: list[str] = []
    for m in _IMPORT_RE.finditer(content):
        mod = m.group(1) or m.group(2) or ""
        for part in mod.split(","):
            part = part.strip().split(" ")[0]  # handle `import a as b`
            if part:
                modules.append(part)
    return modules


def _module_to_relpath(module: str, root: Path, known_paths: set[str]) -> str | None:
    """Best-effort: convert a dotted module to a relative path we know about."""
    candidate = module.replace(".", "/") + ".py"
    if candidate in known_paths:
        return candidate
    # Try with src/ prefix (src-layout)
    src_candidate = "src/" + candidate
    if src_candidate in known_paths:
        return src_candidate
    return None


def _count_tokens(text: str) -> int:
    """Rough token estimate: 4 chars per token."""
    return max(1, len(text) // 4)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


class RepoMapEntry:
    """Mutable scoring entry; converted to schema after ranking."""

    __slots__ = ("file_path", "score", "signature_summary", "symbol_count")

    def __init__(self, file_path: str, signature_summary: str, score: float, symbol_count: int) -> None:
        self.file_path = file_path
        self.signature_summary = signature_summary
        self.score = score
        self.symbol_count = symbol_count


class RepoMap:
    """Rank repository files by relevance to a set of seed identifiers.

    Parameters
    ----------
    repo_path:
        Absolute (or relative) path to the repository root.
    seeds:
        List of identifier names relevant to the current task (e.g. class /
        function names from the task description).
    open_files:
        Files that are currently open / being edited — receive a 50× boost.
    token_budget:
        Approximate upper bound on tokens for the returned summaries.
    extensions:
        File extensions to consider. Defaults to Python only.
    """

    def __init__(
        self,
        repo_path: str,
        seeds: Sequence[str] | None = None,
        open_files: Sequence[str] | None = None,
        token_budget: int = 1024,
        extensions: Sequence[str] | None = None,
    ) -> None:
        self.repo_path = Path(repo_path).resolve()
        self.seeds: list[str] = list(seeds or [])
        self.open_files: set[str] = set(open_files or [])
        self.token_budget = token_budget
        self.extensions: tuple[str, ...] = tuple(extensions or (".py",))

    # ------------------------------------------------------------------
    # Core ranking
    # ------------------------------------------------------------------

    def rank(self) -> list[RepoMapEntry]:
        """Return a token-budgeted, relevance-ranked list of RepoMapEntry."""
        root = self.repo_path
        if not root.is_dir():
            return []

        # Gather all candidate files
        all_files: list[Path] = []
        for ext in self.extensions:
            all_files.extend(
                p for p in root.rglob(f"*{ext}")
                if ".git" not in p.parts and "__pycache__" not in p.parts
            )

        if not all_files:
            return []

        # Build relative path index
        rel_paths: dict[Path, str] = {}
        known_rel: set[str] = set()
        for p in all_files:
            try:
                rp = str(p.relative_to(root))
            except ValueError:
                rp = str(p)
            rel_paths[p] = rp
            known_rel.add(rp)

        # Read file contents
        contents: dict[str, str] = {}
        for p in all_files:
            rp = rel_paths[p]
            contents[rp] = _read_safe(p)

        # Build import graph: importer → set of importees (by rel path)
        in_degree: dict[str, float] = defaultdict(float)
        for rp, content in contents.items():
            mods = _extract_imports(content)
            for mod in mods:
                target = _module_to_relpath(mod, root, known_rel)
                if target and target != rp:
                    in_degree[target] += 1.0

        # Compute per-file scores
        seed_set = set(self.seeds)
        seed_re = re.compile(r"\b(" + "|".join(re.escape(s) for s in seed_set) + r")\b") if seed_set else None

        entries: list[RepoMapEntry] = []
        for rp, content in contents.items():
            base_score = 1.0 + in_degree.get(rp, 0.0)

            # Seed boost: 10× if any seed found in content
            if seed_re and seed_re.search(content):
                base_score *= 10.0

            # Open-file boost: 50×
            if rp in self.open_files or any(rp.endswith(of) for of in self.open_files):
                base_score *= 50.0

            # Build signature summary (def/class lines)
            defs = _DEF_RE.findall(content)
            symbol_count = len(defs)
            summary = ", ".join(defs[:8])
            if len(defs) > 8:
                summary += f" (+{len(defs) - 8} more)"

            entries.append(RepoMapEntry(
                file_path=rp,
                signature_summary=summary,
                score=base_score,
                symbol_count=symbol_count,
            ))

        # Sort descending
        entries.sort(key=lambda e: e.score, reverse=True)

        # Token-budget truncation
        budget = self.token_budget
        result: list[RepoMapEntry] = []
        for entry in entries:
            tokens_used = _count_tokens(entry.file_path + entry.signature_summary)
            if budget <= 0:
                break
            result.append(entry)
            budget -= tokens_used

        return result
