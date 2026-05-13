"""Rust project scanner."""
from __future__ import annotations

from pathlib import Path

from ..schemas import Language, LanguageScanResult


class RustScanner:
    language = Language.RUST

    def scan(self, root: Path) -> LanguageScanResult:
        package_files: list[str] = []
        for p in root.rglob("Cargo.toml"):
            try:
                rel = str(p.relative_to(root))
            except ValueError:
                continue
            package_files.append(rel)
            if len(package_files) > 32:
                break
        source_dirs: list[str] = []
        for p in root.rglob("src"):
            if p.is_dir():
                try:
                    rel = str(p.relative_to(root))
                except ValueError:
                    continue
                if "target" in rel.split("/"):
                    continue
                source_dirs.append(rel)
                if len(source_dirs) >= 8:
                    break
        test_dirs: list[str] = []
        for p in root.rglob("tests"):
            if p.is_dir():
                try:
                    test_dirs.append(str(p.relative_to(root)))
                except ValueError:
                    continue
        entrypoints = []
        for p in root.rglob("main.rs"):
            try:
                entrypoints.append(str(p.relative_to(root)))
            except ValueError:
                continue
        return LanguageScanResult(
            language=Language.RUST,
            detected=bool(package_files),
            package_files=package_files,
            source_dirs=source_dirs,
            test_dirs=test_dirs,
            entrypoints=entrypoints,
            test_framework="cargo test" if package_files else None,
        )
