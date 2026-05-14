"""Module-form shim for the coverage gate.

Run via:

    python -m autodev.coverage_gate

Equivalent to ``python scripts/coverage_gate.py``.
"""
from __future__ import annotations

import sys
from pathlib import Path


def main() -> None:
    repo_root = Path(__file__).resolve().parent.parent.parent
    script = repo_root / "scripts" / "coverage_gate.py"
    if not script.exists():
        sys.stderr.write(f"coverage_gate.py not found at {script}\n")
        sys.exit(1)

    # Execute the script in-process with the same argv.
    ns: dict[str, object] = {"__name__": "__main__", "__file__": str(script)}
    code = compile(script.read_text(encoding="utf-8"), str(script), "exec")
    try:
        exec(code, ns)
    except SystemExit:
        raise


if __name__ == "__main__":
    main()
