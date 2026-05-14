"""SprintWatcher — hot-reload sprint definitions using the watchdog library.

When enabled via ``--watch``, sprint-start (and related sprint commands) can
watch the ``.autodev/sprints/*.md`` glob and reload in-memory sprint state
whenever a sprint Markdown file is created or modified.

The watcher is purely opt-in (``--watch`` flag, default False).  When the flag
is not set, this module is never imported at runtime, so the watchdog
dependency is only needed when hot-reload is actually requested.
"""
from __future__ import annotations

import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any


class SprintWatcher:
    """File-system watcher for ``.autodev/sprints/*.md`` files.

    Uses the ``watchdog`` library's ``Observer`` to receive filesystem events
    and debounces rapid successive changes before calling *on_reload*.

    Parameters
    ----------
    sprints_dir:
        Absolute or repo-relative path to the sprints directory
        (typically ``<repo>/.autodev/sprints``).
    on_reload:
        Callable invoked (on the watchdog thread) after the debounce window
        expires.  Receives the ``Path`` of the changed file.
    debounce_seconds:
        Seconds to wait after the last event before firing *on_reload*.
        Defaults to 0.5 s.
    """

    def __init__(
        self,
        sprints_dir: str | Path,
        on_reload: Callable[[Path], None],
        debounce_seconds: float = 0.5,
    ) -> None:
        self._dir = Path(sprints_dir)
        self._on_reload = on_reload
        self._debounce = debounce_seconds

        # Deferred import so watchdog is only required when watcher is used.
        from watchdog.events import FileSystemEvent, FileSystemEventHandler  # noqa: PLC0415
        from watchdog.observers import Observer  # noqa: PLC0415

        self._observer: Any = Observer()
        self._lock = threading.Lock()
        self._pending_path: Path | None = None
        self._debounce_timer: threading.Timer | None = None
        self._started = False

        watcher = self  # capture for nested class

        class _Handler(FileSystemEventHandler):
            def on_created(self, event: FileSystemEvent) -> None:
                if not event.is_directory and str(event.src_path).endswith(".md"):
                    watcher._schedule(Path(str(event.src_path)))

            def on_modified(self, event: FileSystemEvent) -> None:
                if not event.is_directory and str(event.src_path).endswith(".md"):
                    watcher._schedule(Path(str(event.src_path)))

        self._handler = _Handler()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start the background observer thread and watch the sprints directory."""
        self._dir.mkdir(parents=True, exist_ok=True)
        self._observer.schedule(self._handler, str(self._dir), recursive=True)
        self._observer.start()
        self._started = True

    def stop(self) -> None:
        """Stop the observer and cancel any pending debounce timer.

        Safe to call multiple times or before *start()*.
        """
        with self._lock:
            if self._debounce_timer is not None:
                self._debounce_timer.cancel()
                self._debounce_timer = None

        if self._started:
            self._observer.stop()
            self._observer.join()
            self._started = False

    def is_alive(self) -> bool:
        """Return True if the observer thread is running."""
        return self._started and self._observer.is_alive()

    # ------------------------------------------------------------------
    # Internal debounce
    # ------------------------------------------------------------------

    def _schedule(self, path: Path) -> None:
        """Record the pending path and (re)start the debounce timer."""
        with self._lock:
            self._pending_path = path
            if self._debounce_timer is not None:
                self._debounce_timer.cancel()
            self._debounce_timer = threading.Timer(self._debounce, self._fire)
            self._debounce_timer.daemon = True
            self._debounce_timer.start()

    def _fire(self) -> None:
        """Invoke the reload callback after the debounce window."""
        with self._lock:
            path = self._pending_path
            self._pending_path = None
            self._debounce_timer = None
        if path is not None:
            self._on_reload(path)


def run_sprint_with_watch(
    sprints_dir: str | Path,
    on_reload: Callable[[Path], None],
    debounce_seconds: float = 0.5,
) -> SprintWatcher:
    """Convenience factory: create, start, and return a *SprintWatcher*.

    The caller is responsible for calling ``watcher.stop()`` when done.
    """
    watcher = SprintWatcher(
        sprints_dir=sprints_dir,
        on_reload=on_reload,
        debounce_seconds=debounce_seconds,
    )
    watcher.start()
    return watcher


def _default_reload_handler(path: Path) -> None:
    """Default handler: print a notice to stdout."""
    print(f"[sprint-watch] reloaded: {path}")  # noqa: T201


__all__ = ["SprintWatcher", "run_sprint_with_watch"]
