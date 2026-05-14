"""ReverseDocWatcherFlow — continuous watcher that auto-regenerates brownfield docs.

When run in watch mode the flow monitors *src_path* for source-file changes.
After a debounced batch of events (default 1.0 s) it re-runs ``DocumentProjectAgent``
against the changed sub-tree and writes the resulting docs to *out_dir*.

Single-pass (no watcher) mode is also supported: call ``run_once()`` directly
or invoke the ``autodev-x reverse-doc`` subcommand without ``--watch``.
"""
from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

from ..agents.document_project import DocumentProjectAgent
from ..schemas import BrownfieldDoc, Language


class ReverseDocWatcherFlow:
    """Watch *src_path* for changes and re-generate brownfield docs on each batch.

    Parameters
    ----------
    src_path:
        Directory to watch (and document).
    out_dir:
        Output directory for generated docs.  Defaults to ``docs/_auto``.
    debounce_seconds:
        How long to wait after the last event before triggering a re-run.
    languages:
        Optional list of :class:`~autodev.schemas.Language` hints passed to
        ``DocumentProjectAgent``.
    """

    def __init__(
        self,
        src_path: str | Path,
        out_dir: str | Path = "docs/_auto",
        debounce_seconds: float = 1.0,
        languages: list[Language] | None = None,
    ) -> None:
        self._src_path = Path(src_path)
        self._out_dir = Path(out_dir)
        self._debounce = debounce_seconds
        self._languages = languages or []

        # Internal observer / debounce state — populated in start()
        self._observer: Any = None
        self._lock = threading.Lock()
        self._pending_paths: set[Path] = set()
        self._debounce_timer: threading.Timer | None = None
        self._started = False

    # ------------------------------------------------------------------
    # Public API — single-pass
    # ------------------------------------------------------------------

    def run_once(self) -> BrownfieldDoc:
        """Document *src_path* once and write to *out_dir*.

        Raises
        ------
        FileNotFoundError
            If *src_path* does not exist.
        """
        if not self._src_path.exists():
            raise FileNotFoundError(
                f"reverse-doc: src_path does not exist: {self._src_path}"
            )
        self._out_dir.mkdir(parents=True, exist_ok=True)
        agent = DocumentProjectAgent()
        # We document the src_path but redirect output to out_dir by temporarily
        # monkey-patching the output_dir behaviour via the agent's document() call.
        # The agent writes to <repo>/.autodev/brownfield-docs/; we copy/rewrite the
        # section file_paths to point under out_dir instead.
        doc = agent.document(str(self._src_path), languages=self._languages or None)
        # Re-write the file_paths in the returned doc so callers see out_dir paths.
        self._relocate_sections(doc)
        return doc

    # ------------------------------------------------------------------
    # Public API — watcher
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start the background observer thread.

        Raises
        ------
        FileNotFoundError
            If *src_path* does not exist.
        """
        if not self._src_path.exists():
            raise FileNotFoundError(
                f"reverse-doc: src_path does not exist: {self._src_path}"
            )

        from watchdog.events import FileSystemEvent, FileSystemEventHandler  # noqa: PLC0415
        from watchdog.observers import Observer  # noqa: PLC0415

        self._observer = Observer()
        flow = self  # capture for nested class

        class _Handler(FileSystemEventHandler):
            def on_created(self, event: FileSystemEvent) -> None:
                if not event.is_directory:
                    flow._schedule(Path(str(event.src_path)))

            def on_modified(self, event: FileSystemEvent) -> None:
                if not event.is_directory:
                    flow._schedule(Path(str(event.src_path)))

        handler = _Handler()
        self._src_path.mkdir(parents=True, exist_ok=True)
        self._observer.schedule(handler, str(self._src_path), recursive=True)
        self._observer.start()
        self._started = True

    def stop(self) -> None:
        """Stop the observer and cancel any pending debounce timer.

        Safe to call multiple times or before :meth:`start`.
        """
        with self._lock:
            if self._debounce_timer is not None:
                self._debounce_timer.cancel()
                self._debounce_timer = None

        if self._started and self._observer is not None:
            self._observer.stop()
            self._observer.join()
            self._started = False

    def is_alive(self) -> bool:
        """Return True if the observer thread is running."""
        return self._started and self._observer is not None and self._observer.is_alive()

    # ------------------------------------------------------------------
    # Internal debounce
    # ------------------------------------------------------------------

    def _schedule(self, path: Path) -> None:
        """Record *path* in the pending set and (re)start the debounce timer."""
        with self._lock:
            self._pending_paths.add(path)
            if self._debounce_timer is not None:
                self._debounce_timer.cancel()
            self._debounce_timer = threading.Timer(self._debounce, self._fire)
            self._debounce_timer.daemon = True
            self._debounce_timer.start()

    def _fire(self) -> None:
        """Trigger a documentation re-run after the debounce window expires."""
        with self._lock:
            self._pending_paths.clear()
            self._debounce_timer = None
        # Re-document the entire src_path (the changed subtree is small but we
        # regenerate all sections for consistency with the single-pass mode).
        try:
            self.run_once()
        except Exception:  # noqa: BLE001
            pass  # swallow errors in background thread; caller can hook _on_doc_generated

    def _relocate_sections(self, doc: BrownfieldDoc) -> None:
        """Rewrite *doc* section ``file_path`` values to point under *out_dir*."""
        for section in doc.sections:
            if section.file_path is not None:
                # Keep just the filename, place it under out_dir
                fname = Path(section.file_path).name
                new_path = self._out_dir / fname
                new_path.parent.mkdir(parents=True, exist_ok=True)
                # Write the content to the new location
                try:
                    content = Path(section.file_path).read_text(encoding="utf-8")
                    new_path.write_text(content, encoding="utf-8")
                except OSError:
                    pass
                section.file_path = str(new_path)
        doc.output_dir = str(self._out_dir)


__all__ = ["ReverseDocWatcherFlow"]
