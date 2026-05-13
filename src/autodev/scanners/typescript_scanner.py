"""TypeScript / JavaScript project scanner."""
from __future__ import annotations

import json
from pathlib import Path

from ..schemas import Language, LanguageScanResult


class TypeScriptScanner:
    language = Language.TYPESCRIPT

    def scan(self, root: Path) -> LanguageScanResult:
        package_files: list[str] = []
        for cand in ("package.json", "tsconfig.json"):
            if (root / cand).exists():
                package_files.append(cand)
        for p in root.rglob("package.json"):
            try:
                rel = str(p.relative_to(root))
            except ValueError:
                continue
            if "node_modules" in rel.split("/"):
                continue
            if rel not in package_files:
                package_files.append(rel)
            if len(package_files) > 32:
                break

        source_dirs: list[str] = []
        test_dirs: list[str] = []
        for d in root.iterdir():
            if not d.is_dir():
                continue
            if d.name in ("src", "app", "lib", "packages", "apps"):
                source_dirs.append(d.name)
            if d.name in ("tests", "test", "__tests__"):
                test_dirs.append(d.name)

        framework = None
        for pf in package_files:
            if not pf.endswith("package.json"):
                continue
            try:
                data = json.loads((root / pf).read_text(encoding="utf-8"))
            except Exception:
                continue
            deps = {**(data.get("dependencies") or {}), **(data.get("devDependencies") or {})}
            if "vitest" in deps:
                framework = "vitest"
                break
            if "jest" in deps:
                framework = "jest"
                break

        entrypoints: list[str] = []
        for cand in ("src/index.ts", "src/main.ts", "src/cli.ts", "src/index.js"):
            if (root / cand).exists():
                entrypoints.append(cand)

        return LanguageScanResult(
            language=Language.TYPESCRIPT,
            detected=bool(package_files),
            package_files=package_files,
            source_dirs=source_dirs,
            test_dirs=test_dirs,
            entrypoints=entrypoints,
            test_framework=framework,
        )
