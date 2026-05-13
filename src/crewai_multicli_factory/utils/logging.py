"""Lightweight structured logger."""
from __future__ import annotations

import logging
import os
import sys

_INITIALIZED = False


def get_logger(name: str = "factory") -> logging.Logger:
    global _INITIALIZED
    if not _INITIALIZED:
        level_name = os.environ.get("FACTORY_LOG", "INFO").upper()
        logging.basicConfig(
            level=getattr(logging, level_name, logging.INFO),
            format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
            stream=sys.stderr,
        )
        _INITIALIZED = True
    return logging.getLogger(name)
