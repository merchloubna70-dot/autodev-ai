"""autodev-ai package."""
from __future__ import annotations

from importlib.metadata import version as _v

try:
    __version__ = _v("autodev-ai")
except Exception:
    __version__ = "0.0.0+local"

__all__ = ["__version__"]
