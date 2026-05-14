"""
Thin shim so `python -m autodev.release_readiness_gate` works.

Delegates entirely to scripts/release_readiness_gate.py — no duplicate logic.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_SCRIPT = Path(__file__).parent.parent.parent / "scripts" / "release_readiness_gate.py"


def _load() -> None:
    spec = importlib.util.spec_from_file_location("_rrgate_script", _SCRIPT)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load release_readiness_gate script from {_SCRIPT}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    mod.main()


if __name__ == "__main__":
    _load()
