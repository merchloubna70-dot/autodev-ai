"""Entry wrapper for PyInstaller — avoids relative-import error.

PyInstaller bundles a single script as its entry point. Pointing it directly
at `src/autodev/cli.py` fails at runtime because that module uses relative
imports (`from .agents import ...`). This wrapper imports the CLI via the
fully-qualified `autodev.cli` path so the runtime can resolve relative imports
within the bundled `autodev` package.
"""
from autodev.cli import app

if __name__ == "__main__":
    app()
