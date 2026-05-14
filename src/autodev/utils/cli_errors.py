"""Friendly CLI error handling for autodev commands.

Provides a decorator and a context manager that translate low-level
exceptions (FileNotFoundError, JSONDecodeError, ValidationError) into
user-readable typer error messages with meaningful exit codes instead of
raw Python tracebacks.

Exit codes
----------
2  — FileNotFoundError (run / file not found)
3  — json.JSONDecodeError (corrupt or unreadable state file)
4  — pydantic.ValidationError (invalid value in state file)
"""
from __future__ import annotations

import functools
import json
import logging
from collections.abc import Callable, Generator
from contextlib import contextmanager
from typing import Any, TypeVar

import typer

_F = TypeVar("_F", bound=Callable[..., Any])

logger = logging.getLogger(__name__)


@contextmanager
def friendly_errors_ctx() -> Generator[None, None, None]:
    """Context manager that converts known exceptions to friendly CLI errors.

    Usage::

        with friendly_errors_ctx():
            run = RunState.load(repo_path, run_id)

    Raises ``typer.Exit`` with a non-zero code on handled exceptions.
    Unknown exceptions are re-raised unchanged so stack traces still appear
    for unexpected bugs.
    """
    try:
        yield
    except typer.Exit:
        raise
    except FileNotFoundError as exc:
        typer.secho(f"Error: {exc}", fg="red", err=True)
        raise typer.Exit(code=2) from None
    except json.JSONDecodeError as exc:
        path = exc.doc[:80] if exc.doc else ""
        typer.secho(
            f"Error: file is corrupt or unreadable ({path}: {exc.msg} at char {exc.pos})",
            fg="red",
            err=True,
        )
        raise typer.Exit(code=3) from None
    except Exception as exc:  # noqa: BLE001
        # Import lazily to avoid a hard dependency at module level when pydantic
        # is not installed (unit-test environments without full deps).
        try:
            from pydantic import ValidationError as _ValidationError  # noqa: PLC0415
        except ImportError:
            _ValidationError = None  # type: ignore[assignment,misc]

        if _ValidationError is not None and isinstance(exc, _ValidationError):
            typer.secho("Error: state file contains invalid values:", fg="red", err=True)
            for err in exc.errors():
                loc = ".".join(str(x) for x in err["loc"])
                typer.secho(f"  - {loc}: {err['msg']}", fg="red", err=True)
            raise typer.Exit(code=4) from None

        # Unknown exception — re-raise so the developer sees the real traceback.
        raise


def friendly_errors(func: _F) -> _F:
    """Decorator version of ``friendly_errors_ctx``.

    Usage::

        @app.command("continue-run")
        @friendly_errors
        def continue_run(...) -> None:
            ...
    """

    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        with friendly_errors_ctx():
            return func(*args, **kwargs)

    return wrapper  # type: ignore[return-value]
