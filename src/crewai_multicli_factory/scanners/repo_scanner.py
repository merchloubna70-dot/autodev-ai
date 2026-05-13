"""Top-level repository scanner — composes per-language scanners."""
from __future__ import annotations

from pathlib import Path

from ..schemas import Language, RepoScanResult
from ..utils.fs import is_empty_dir
from .monorepo_scanner import MonorepoScanner
from .python_scanner import PythonScanner
from .rust_scanner import RustScanner
from .typescript_scanner import TypeScriptScanner


class RepoScanner:
    def __init__(self):
        self.python = PythonScanner()
        self.rust = RustScanner()
        self.typescript = TypeScriptScanner()
        self.monorepo = MonorepoScanner()

    def scan(self, repo_path: str) -> RepoScanResult:
        root = Path(repo_path).resolve()
        if not root.exists():
            root.mkdir(parents=True, exist_ok=True)
        empty = is_empty_dir(root)
        results = {
            Language.PYTHON.value: self.python.scan(root),
            Language.RUST.value: self.rust.scan(root),
            Language.TYPESCRIPT.value: self.typescript.scan(root),
        }
        detected = [Language(k) for k, v in results.items() if v.detected]
        top_level = [p.name for p in root.iterdir() if p.is_dir() and not p.name.startswith(".")]
        return RepoScanResult(
            repo_path=str(root),
            is_empty=empty,
            is_monorepo=self.monorepo.is_monorepo(root) if not empty else False,
            detected_languages=detected,
            language_results=results,
            top_level_dirs=top_level,
            has_git=(root / ".git").exists(),
        )
