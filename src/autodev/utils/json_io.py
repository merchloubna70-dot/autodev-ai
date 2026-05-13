"""Structured JSON / JSONL I/O with pydantic compatibility."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from pydantic import BaseModel


def _default(obj: Any) -> Any:
    if isinstance(obj, BaseModel):
        return obj.model_dump(mode="json")
    if hasattr(obj, "value"):  # Enum
        return obj.value
    if hasattr(obj, "isoformat"):
        return obj.isoformat()
    raise TypeError(f"unserializable: {type(obj).__name__}")


def dumps(obj: Any) -> str:
    return json.dumps(obj, indent=2, ensure_ascii=False, default=_default)


def write_json(path: str | os.PathLike, obj: Any) -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(dumps(obj), encoding="utf-8")
    return p


def read_json(path: str | os.PathLike) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def append_jsonl(path: str | os.PathLike, obj: Any) -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(obj, ensure_ascii=False, default=_default)
    with p.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")
    return p


def read_jsonl(path: str | os.PathLike) -> list[Any]:
    p = Path(path)
    if not p.exists():
        return []
    out: list[Any] = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        out.append(json.loads(line))
    return out
