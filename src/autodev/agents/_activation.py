"""BMAD-16/18: Activation hooks + per-agent customize.toml loader.

ActivatableAgent mixin — opt-in. Agents that don't inherit this keep working unchanged.
AgentCustomizeLoader — loads 4-layer customize.toml per agent name.
ActivationContext — shared state passed through prepend → run → append pipeline.
"""
from __future__ import annotations

import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from ..schemas import ActivationResult, AgentCustomizeSnapshot

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

try:
    from ..utils.config_stack import _deep_merge  # reuse BMAD-6 helper
except ImportError:  # pragma: no cover
    def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:  # type: ignore[misc]
        """Fallback deep merge (mirrors config_stack._deep_merge logic)."""
        result: dict[str, Any] = dict(base)
        for k, v in override.items():
            if k not in result:
                result[k] = v
            elif isinstance(v, dict) and isinstance(result[k], dict):
                result[k] = _deep_merge(result[k], v)
            elif isinstance(v, list) and isinstance(result[k], list):
                result[k] = list(result[k]) + list(v)
            else:
                result[k] = v
        return result


# ---------------------------------------------------------------------------
# Activation context
# ---------------------------------------------------------------------------


class ActivationContext:
    """Shared mutable state passed through prepend → run → append steps."""

    def __init__(self, agent_name: str, kwargs: dict[str, Any] | None = None) -> None:
        self.agent_name = agent_name
        self.kwargs: dict[str, Any] = dict(kwargs or {})
        self.customize: dict[str, Any] = {}
        self.notes: list[str] = []

    def set_customize(self, data: dict[str, Any]) -> None:
        self.customize = data

    def add_note(self, note: str) -> None:
        self.notes.append(note)


# ---------------------------------------------------------------------------
# Customize loader (BMAD-18)
# ---------------------------------------------------------------------------


class AgentCustomizeLoader:
    """Load per-agent customize.toml from 4 layers (lowest → highest priority):

    (a) <pkg>/agents/<agent_name>/customize.toml   (package default, optional)
    (b) ~/.config/autodev/agents/<agent_name>.toml  (user global)
    (c) <repo>/.autodev/agents/<agent_name>.toml    (project team)
    (d) <repo>/.autodev/agents/<agent_name>.user.toml  (project user)
    """

    def __init__(self, agent_name: str, repo_path: str | Path | None = None) -> None:
        self.agent_name = agent_name
        self._repo = Path(repo_path) if repo_path else None

    def _toml(self, path: Path) -> dict[str, Any]:
        if not path.exists():
            return {}
        if tomllib is None:  # pragma: no cover
            return {}
        try:
            with open(path, "rb") as f:
                return tomllib.load(f)
        except Exception:
            return {}

    def load(self) -> tuple[dict[str, Any], list[str]]:
        """Return (merged_dict, [paths_that_loaded])."""
        merged: dict[str, Any] = {}
        loaded: list[str] = []

        # (a) package default — lives next to this file under agents/<name>/customize.toml
        pkg_path = Path(__file__).parent / self.agent_name / "customize.toml"
        d = self._toml(pkg_path)
        if d:
            merged = _deep_merge(merged, d)
            loaded.append(str(pkg_path))

        # (b) user global
        ug = Path.home() / ".config" / "autodev" / "agents" / f"{self.agent_name}.toml"
        d = self._toml(ug)
        if d:
            merged = _deep_merge(merged, d)
            loaded.append(str(ug))

        # (c) project team
        if self._repo:
            pt = self._repo / ".autodev" / "agents" / f"{self.agent_name}.toml"
            d = self._toml(pt)
            if d:
                merged = _deep_merge(merged, d)
                loaded.append(str(pt))

            # (d) project user
            pu = self._repo / ".autodev" / "agents" / f"{self.agent_name}.user.toml"
            d = self._toml(pu)
            if d:
                merged = _deep_merge(merged, d)
                loaded.append(str(pu))

        return merged, loaded

    def snapshot(self) -> AgentCustomizeSnapshot:
        data, paths = self.load()
        return AgentCustomizeSnapshot(
            agent_name=self.agent_name,
            layers_loaded=paths,
            effective_keys=list(data.keys()),
            persistent_facts=data.get("persistent_facts", []),
            principles=data.get("principles", []),
        )


# ---------------------------------------------------------------------------
# ActivatableAgent mixin (BMAD-16)
# ---------------------------------------------------------------------------


HookCallable = Callable[[ActivationContext], None]


class ActivatableAgent:
    """Opt-in mixin adding prepend/append hooks and customize.toml loading.

    Subclasses set:
        activation_steps_prepend: list[HookCallable] = []
        activation_steps_append:  list[HookCallable] = []
        _activation_agent_name:   str   (defaults to class name snake-cased)

    The .activate() method orchestrates:
        1. Load customize.toml 4-layer stack → ctx.customize
        2. Run each prepend hook
        3. Delegate to .run(**ctx.kwargs)   (subclass must implement run())
        4. Run each append hook
        5. Return ActivationResult
    """

    activation_steps_prepend: list[HookCallable] = []
    activation_steps_append: list[HookCallable] = []

    @property
    def _activation_agent_name(self) -> str:
        import re
        name = type(self).__name__
        # CamelCase → snake_case, strip common suffixes
        name = re.sub(r"Agent$", "", name)
        name = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", name)
        name = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", name).lower()
        return name

    def activate(self, ctx: ActivationContext | None = None, **kwargs: Any) -> ActivationResult:
        """Run full activation lifecycle and return ActivationResult."""
        if ctx is None:
            ctx = ActivationContext(agent_name=self._activation_agent_name, kwargs=kwargs)

        agent_name = ctx.agent_name or self._activation_agent_name
        prepend_run: list[str] = []
        append_run: list[str] = []
        errors: list[str] = []
        t0 = time.monotonic()

        # Step 1: load customize.toml
        try:
            loader = AgentCustomizeLoader(agent_name)
            merged, _paths = loader.load()
            ctx.set_customize(merged)
        except Exception as exc:  # pragma: no cover
            errors.append(f"customize-load: {exc}")

        # Step 2: prepend hooks
        for hook in (self.activation_steps_prepend or []):
            name = getattr(hook, "__name__", repr(hook))
            try:
                hook(ctx)
                prepend_run.append(name)
            except Exception as exc:
                errors.append(f"prepend:{name}: {exc}")
                duration_ms = int((time.monotonic() - t0) * 1000)
                return ActivationResult(
                    agent_name=agent_name,
                    success=False,
                    duration_ms=duration_ms,
                    prepend_steps_run=prepend_run,
                    append_steps_run=append_run,
                    errors=errors,
                )

        # Step 3: delegate to run()
        result_summary = ""
        try:
            run_result = self.run(**ctx.kwargs)  # type: ignore[attr-defined]
            result_summary = repr(run_result)[:200] if run_result is not None else ""
        except Exception as exc:
            errors.append(f"run: {exc}")
            duration_ms = int((time.monotonic() - t0) * 1000)
            return ActivationResult(
                agent_name=agent_name,
                success=False,
                duration_ms=duration_ms,
                prepend_steps_run=prepend_run,
                append_steps_run=append_run,
                result_summary=result_summary,
                errors=errors,
            )

        # Step 4: append hooks
        for hook in (self.activation_steps_append or []):
            name = getattr(hook, "__name__", repr(hook))
            try:
                hook(ctx)
                append_run.append(name)
            except Exception as exc:
                errors.append(f"append:{name}: {exc}")

        duration_ms = int((time.monotonic() - t0) * 1000)
        return ActivationResult(
            agent_name=agent_name,
            success=not errors,
            duration_ms=duration_ms,
            prepend_steps_run=prepend_run,
            append_steps_run=append_run,
            result_summary=result_summary,
            errors=errors,
        )
