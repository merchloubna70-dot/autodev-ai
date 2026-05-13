"""Python project scanner."""
from __future__ import annotations

from pathlib import Path

from ..schemas import Language, LanguageScanResult


class PythonScanner:
    language = Language.PYTHON

    PACKAGE_MARKERS = ("pyproject.toml", "setup.py", "setup.cfg", "requirements.txt")

    def scan(self, root: Path) -> LanguageScanResult:
        package_files: list[str] = []
        for marker in self.PACKAGE_MARKERS:
            if (root / marker).exists():
                package_files.append(marker)
        # Detect any nested pyproject (monorepo case)
        for p in root.rglob("pyproject.toml"):
            rel = str(p.relative_to(root))
            if rel not in package_files:
                package_files.append(rel)
            if len(package_files) > 32:
                break

        source_dirs = [d.name for d in root.iterdir() if d.is_dir() and d.name in ("src", "app", "lib")]
        test_dirs = [d.name for d in root.iterdir() if d.is_dir() and d.name in ("tests", "test")]
        entrypoints: list[str] = []
        for cand in ("main.py", "cli.py", "app.py"):
            for p in root.rglob(cand):
                entrypoints.append(str(p.relative_to(root)))
                if len(entrypoints) >= 8:
                    break

        framework = None
        if any("pytest" in (root / pf).read_text(encoding="utf-8", errors="ignore") for pf in package_files if (root / pf).exists() and (root / pf).is_file()):
            framework = "pytest"

        return LanguageScanResult(
            language=Language.PYTHON,
            detected=bool(package_files) or any(p.suffix == ".py" for p in root.rglob("*.py")),
            package_files=package_files,
            source_dirs=source_dirs,
            test_dirs=test_dirs,
            entrypoints=entrypoints,
            test_framework=framework,
        )
