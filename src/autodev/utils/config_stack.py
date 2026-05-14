"""ConfigStack — 4-layer TOML deep-merge for autodev.

Layer order (lowest → highest priority):
  1. ~/.config/autodev/config.toml          (user-global)
  2. {repo}/.autodev/config.toml            (project team-base)
  3. {repo}/.autodev/config.user.toml       (project user override; git-ignored)
  4. runtime dict injected via CLI/env       (runtime)
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

if sys.version_info >= (3, 11):
    import tomllib
else:
    try:
        import tomllib  # type: ignore[no-redef]
    except ImportError:
        try:
            import tomli as tomllib  # type: ignore[no-redef,import-not-found]
        except ImportError:
            tomllib = None  # type: ignore[assignment]


def _is_array_of_tables(v: Any) -> bool:
    return isinstance(v, list) and bool(v) and isinstance(v[0], dict)


def _aot_key(item: dict[str, Any]) -> Any:
    """Return the merge key for an array-of-tables item (code > id > None)."""
    return item.get("code", item.get("id"))


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Recursively merge *override* into *base* (returns a new dict)."""
    result: dict[str, Any] = dict(base)
    for k, v in override.items():
        if k not in result:
            result[k] = v
        elif isinstance(v, dict) and isinstance(result[k], dict):
            result[k] = _deep_merge(result[k], v)
        elif _is_array_of_tables(v) and _is_array_of_tables(result[k]):
            # Merge by code/id key; append entries whose key is not in base.
            merged: list[dict[str, Any]] = list(result[k])
            for item in v:
                key = _aot_key(item)
                if key is not None:
                    for i, existing in enumerate(merged):
                        if _aot_key(existing) == key:
                            merged[i] = _deep_merge(existing, item)
                            break
                    else:
                        merged.append(item)
                else:
                    merged.append(item)
            result[k] = merged
        elif isinstance(v, list) and isinstance(result[k], list):
            # Plain lists: append
            result[k] = list(result[k]) + list(v)
        else:
            # Scalar override
            result[k] = v
    return result


def _load_toml(path: Path) -> tuple[dict[str, Any], bool]:
    """Load a TOML file; return (data, loaded).  Missing file → ({}, False)."""
    if not path.exists():
        return {}, False
    if tomllib is None:
        raise RuntimeError(
            "tomllib is not available (Python < 3.11 and tomli not installed)."
        )
    with open(path, "rb") as f:
        return tomllib.load(f), True


class ConfigStack:
    """Load and deep-merge up to 4 TOML config layers."""

    USER_GLOBAL_PATH = Path.home() / ".config" / "autodev" / "config.toml"

    def __init__(self, repo_path: str | Path | None = None, runtime: dict[str, Any] | None = None) -> None:
        self._repo_path = Path(repo_path) if repo_path else None
        self._runtime: dict[str, Any] = dict(runtime or {})
        self._merged: dict[str, Any] = {}
        self._layers: list[dict[str, Any]] = [
            {"name": "user-global", "path": str(self.USER_GLOBAL_PATH), "loaded": False, "keys_count": 0},
            {"name": "project-team", "path": None, "loaded": False, "keys_count": 0},
            {"name": "project-user", "path": None, "loaded": False, "keys_count": 0},
            {"name": "runtime", "path": None, "loaded": False, "keys_count": 0},
        ]

    def load(self) -> ConfigStack:
        """Load all layers and build the merged config.  Returns self for chaining."""
        merged: dict[str, Any] = {}

        # Layer 1 — user-global
        data, ok = _load_toml(self.USER_GLOBAL_PATH)
        self._layers[0]["loaded"] = ok
        self._layers[0]["keys_count"] = len(data)
        merged = _deep_merge(merged, data)

        # Layer 2 — project team-base
        if self._repo_path:
            p2 = self._repo_path / ".autodev" / "config.toml"
            data2, ok2 = _load_toml(p2)
            self._layers[1]["path"] = str(p2)
            self._layers[1]["loaded"] = ok2
            self._layers[1]["keys_count"] = len(data2)
            merged = _deep_merge(merged, data2)

        # Layer 3 — project user override
        if self._repo_path:
            p3 = self._repo_path / ".autodev" / "config.user.toml"
            data3, ok3 = _load_toml(p3)
            self._layers[2]["path"] = str(p3)
            self._layers[2]["loaded"] = ok3
            self._layers[2]["keys_count"] = len(data3)
            merged = _deep_merge(merged, data3)

        # Layer 4 — runtime
        runtime_count = len(self._runtime)
        self._layers[3]["loaded"] = runtime_count > 0
        self._layers[3]["keys_count"] = runtime_count
        merged = _deep_merge(merged, self._runtime)

        self._merged = merged
        return self

    def get(self, key: str, default: Any = None) -> Any:
        """Get a top-level key from the merged config."""
        return self._merged.get(key, default)

    @property
    def data(self) -> dict[str, Any]:
        return self._merged

    @property
    def layers(self) -> list[dict[str, Any]]:
        return self._layers

    def materialize_into(self, factory_config: Any) -> Any:
        """Overlay scalar config values onto a FactoryConfig instance.

        Supports flat scalar keys that map to FactoryConfig attributes, plus
        dotted sub-sections ``codex.*`` and ``claude_code.*``.
        """

        top_scalar_keys = {
            "state_dir",
            "allow_mock_executor",
            "fail_fast",
            "continue_and_report",
            "concurrency",
            "commit",
            "push",
            "tag",
            "release",
        }
        for k in top_scalar_keys:
            if k in self._merged:
                setattr(factory_config, k, self._merged[k])

        if "codex" in self._merged and isinstance(self._merged["codex"], dict):
            for ck, cv in self._merged["codex"].items():
                if hasattr(factory_config.codex, ck):
                    setattr(factory_config.codex, ck, cv)

        if "claude_code" in self._merged and isinstance(self._merged["claude_code"], dict):
            for ck, cv in self._merged["claude_code"].items():
                if hasattr(factory_config.claude_code, ck):
                    setattr(factory_config.claude_code, ck, cv)

        return factory_config
