"""Hash helpers — sha256 for deterministic test fixtures and audit IDs."""
from __future__ import annotations

import hashlib


def sha256_hex(data: str | bytes) -> str:
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def short_hash(data: str | bytes, n: int = 8) -> str:
    return sha256_hex(data)[:n]
