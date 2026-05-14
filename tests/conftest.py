import os
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


# ---------------------------------------------------------------------------
# Stub watchdog into sys.modules so tests that patch it can work even when the
# optional watchdog package is not installed in the current environment.
# ---------------------------------------------------------------------------
def _stub_watchdog() -> None:
    """Inject minimal watchdog stubs into sys.modules if watchdog is missing."""
    try:
        import watchdog  # noqa: F401  # type: ignore[import-untyped]
        return  # real watchdog present — no stub needed
    except ImportError:
        pass

    watchdog_pkg = types.ModuleType("watchdog")
    observers_mod = types.ModuleType("watchdog.observers")
    events_mod = types.ModuleType("watchdog.events")

    class _FileSystemEvent:
        def __init__(self, src_path: str, is_directory: bool = False) -> None:
            self.src_path = src_path
            self.is_directory = is_directory

    class _FileSystemEventHandler:
        def on_created(self, event: object) -> None:
            pass

        def on_modified(self, event: object) -> None:
            pass

    class _Observer:
        def __init__(self) -> None:
            self._alive = False
            self._started = False

        def schedule(self, handler: object, path: str, recursive: bool = False) -> None:
            pass

        def start(self) -> None:
            self._alive = True
            self._started = True

        def stop(self) -> None:
            self._alive = False

        def join(self) -> None:
            pass

        def is_alive(self) -> bool:
            return self._alive

    events_mod.FileSystemEvent = _FileSystemEvent  # type: ignore[attr-defined]
    events_mod.FileSystemEventHandler = _FileSystemEventHandler  # type: ignore[attr-defined]
    observers_mod.Observer = _Observer  # type: ignore[attr-defined]
    watchdog_pkg.observers = observers_mod  # type: ignore[attr-defined]
    watchdog_pkg.events = events_mod  # type: ignore[attr-defined]

    sys.modules.setdefault("watchdog", watchdog_pkg)
    sys.modules.setdefault("watchdog.observers", observers_mod)
    sys.modules.setdefault("watchdog.events", events_mod)


_stub_watchdog()

# Keep tests offline & deterministic.
os.environ.setdefault("FACTORY_LOG", "WARNING")
# Force the executor router to substitute mock executors so tests never call
# real `codex` / `claude` CLIs even when they happen to be installed.
os.environ.setdefault("FACTORY_FORCE_MOCK", "1")
# Allow A2AHttpTransport to connect to localhost in integration tests that
# spin up fake servers on 127.0.0.1.  Production code never sets this env var.
os.environ.setdefault("AUTODEV_A2A_ALLOW_PRIVATE_NETWORKS", "1")
