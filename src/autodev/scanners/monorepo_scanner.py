"""Monorepo detection — packages/, apps/, services/, workspaces."""
from __future__ import annotations

import json
from pathlib import Path


class MonorepoScanner:
    MARKER_DIRS = ("packages", "apps", "services", "crates", "libs", "shared")

    def is_monorepo(self, root: Path) -> bool:
        # explicit workspace declarations
        pkg = root / "package.json"
        if pkg.exists():
            try:
                data = json.loads(pkg.read_text(encoding="utf-8"))
                if "workspaces" in data:
                    return True
            except Exception:
                pass
        cargo = root / "Cargo.toml"
        if cargo.exists():
            try:
                if "[workspace]" in cargo.read_text(encoding="utf-8"):
                    return True
            except Exception:
                pass
        if (root / "pnpm-workspace.yaml").exists() or (root / "lerna.json").exists():
            return True
        # heuristic: marker dirs with sub-packages
        for d in self.MARKER_DIRS:
            sub = root / d
            if sub.exists() and sub.is_dir():
                for child in sub.iterdir():
                    if child.is_dir():
                        if (child / "package.json").exists() or (child / "Cargo.toml").exists() or (child / "pyproject.toml").exists():
                            return True
        return False
