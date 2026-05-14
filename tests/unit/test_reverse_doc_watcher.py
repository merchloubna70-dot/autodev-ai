"""Unit tests for ReverseDocWatcherFlow.

watchdog is an optional runtime dependency; the conftest.py in the tests root
stubs it into sys.modules when the package is not installed so that mock-based
tests work even in lean CI environments.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_observer() -> MagicMock:
    """Return a mock watchdog Observer that does nothing real."""
    obs = MagicMock()
    obs.is_alive.return_value = True
    return obs


def _make_mock_event(path: str, is_directory: bool = False) -> MagicMock:
    """Return a mock watchdog FileSystemEvent-like object."""
    evt = MagicMock()
    evt.src_path = path
    evt.is_directory = is_directory
    return evt


def _simple_repo(tmp_path: Path) -> Path:
    """Create a minimal Python repo layout for documentation tests."""
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "test-proj"\ndescription = "A test project"\n',
        encoding="utf-8",
    )
    pkg = tmp_path / "test_proj"
    pkg.mkdir()
    (pkg / "__init__.py").write_text('"""test_proj package."""\n', encoding="utf-8")
    return tmp_path


# ---------------------------------------------------------------------------
# Test 1 — single-pass mode produces docs
# ---------------------------------------------------------------------------


def test_single_pass_mode_works(tmp_path: Path) -> None:
    """run_once() documents the src_path and writes to out_dir."""
    repo = _simple_repo(tmp_path)
    out_dir = tmp_path / "docs" / "_auto"

    from autodev.flows.reverse_doc_watcher_flow import ReverseDocWatcherFlow

    flow = ReverseDocWatcherFlow(src_path=repo, out_dir=out_dir)
    doc = flow.run_once()

    assert doc.repo_path == str(repo.resolve())
    assert len(doc.sections) > 0
    assert doc.output_dir == str(out_dir)
    # At least one section file should exist under out_dir
    assert out_dir.exists()
    written_files = list(out_dir.glob("*.md"))
    assert len(written_files) > 0


# ---------------------------------------------------------------------------
# Test 2 — watcher detects file change and fires callback
# ---------------------------------------------------------------------------


def test_watcher_detects_file_change(tmp_path: Path) -> None:
    """After a file-modified event, _fire() is eventually called."""
    repo = _simple_repo(tmp_path)
    out_dir = tmp_path / "docs" / "_auto"

    fired: list[bool] = []

    from autodev.flows.reverse_doc_watcher_flow import ReverseDocWatcherFlow

    flow = ReverseDocWatcherFlow(src_path=repo, out_dir=out_dir, debounce_seconds=0.05)

    # Patch _fire to record calls without actually re-running the agent
    def _patched_fire() -> None:
        fired.append(True)

    flow._fire = _patched_fire  # type: ignore[method-assign]
    flow.start()

    # Simulate a file-modified event via _schedule
    py_file = Path(repo / "test_proj" / "__init__.py")
    flow._schedule(py_file)

    # Wait for debounce timer to fire
    time.sleep(0.4)

    flow.stop()

    assert len(fired) >= 1, "Expected _fire() to be called at least once"


# ---------------------------------------------------------------------------
# Test 3 — debounce coalesces rapid-fire changes into one call
# ---------------------------------------------------------------------------


def test_debounce_coalesces_rapid_changes(tmp_path: Path) -> None:
    """Multiple rapid file events within the debounce window fire only once."""
    repo = _simple_repo(tmp_path)
    out_dir = tmp_path / "docs" / "_auto"

    call_count = 0

    from autodev.flows.reverse_doc_watcher_flow import ReverseDocWatcherFlow

    flow = ReverseDocWatcherFlow(src_path=repo, out_dir=out_dir, debounce_seconds=0.15)

    def _patched_fire() -> None:
        nonlocal call_count
        call_count += 1

    flow._fire = _patched_fire  # type: ignore[method-assign]
    flow.start()

    py_file = Path(repo / "test_proj" / "__init__.py")

    # Fire 8 events in rapid succession — all within the debounce window
    for _ in range(8):
        flow._schedule(py_file)

    # Wait well past the debounce window
    time.sleep(0.6)

    flow.stop()

    assert call_count == 1, f"Expected exactly 1 call after debounce, got {call_count}"


# ---------------------------------------------------------------------------
# Test 4 — watcher.stop() releases observer
# ---------------------------------------------------------------------------


def test_watcher_stop_releases_observer(tmp_path: Path) -> None:
    """stop() calls Observer.stop() and Observer.join() exactly once."""
    repo = _simple_repo(tmp_path)
    out_dir = tmp_path / "docs" / "_auto"

    # Replace the stub Observer with a MagicMock for precise assertion
    mock_obs = _make_mock_observer()
    original_observer = sys.modules["watchdog.observers"].Observer  # type: ignore[attr-defined]
    sys.modules["watchdog.observers"].Observer = lambda: mock_obs  # type: ignore[attr-defined]

    try:
        from autodev.flows.reverse_doc_watcher_flow import ReverseDocWatcherFlow

        flow = ReverseDocWatcherFlow(src_path=repo, out_dir=out_dir)
        flow.start()

        assert flow._started is True
        assert flow.is_alive() is True

        flow.stop()
    finally:
        sys.modules["watchdog.observers"].Observer = original_observer  # type: ignore[attr-defined]

    mock_obs.stop.assert_called_once()
    mock_obs.join.assert_called_once()
    assert flow._started is False


# ---------------------------------------------------------------------------
# Test 5 — malformed / missing src_path raises FileNotFoundError
# ---------------------------------------------------------------------------


def test_malformed_src_path_raises_clean_error(tmp_path: Path) -> None:
    """run_once() with a non-existent src_path raises FileNotFoundError."""
    from autodev.flows.reverse_doc_watcher_flow import ReverseDocWatcherFlow

    missing = tmp_path / "does_not_exist" / "nowhere"
    flow = ReverseDocWatcherFlow(src_path=missing, out_dir=tmp_path / "out")

    with pytest.raises(FileNotFoundError, match="src_path does not exist"):
        flow.run_once()


# ---------------------------------------------------------------------------
# Test 6 — stop() is idempotent (safe to call twice)
# ---------------------------------------------------------------------------


def test_watcher_stop_is_idempotent(tmp_path: Path) -> None:
    """Calling stop() twice does not raise an exception."""
    repo = _simple_repo(tmp_path)
    out_dir = tmp_path / "docs" / "_auto"

    from autodev.flows.reverse_doc_watcher_flow import ReverseDocWatcherFlow

    flow = ReverseDocWatcherFlow(src_path=repo, out_dir=out_dir)
    flow.start()
    flow.stop()
    # Second call must not raise
    flow.stop()


# ---------------------------------------------------------------------------
# Test 7 — start() with missing src_path raises FileNotFoundError
# ---------------------------------------------------------------------------


def test_watcher_start_missing_src_raises(tmp_path: Path) -> None:
    """start() raises FileNotFoundError when src_path does not exist."""
    from autodev.flows.reverse_doc_watcher_flow import ReverseDocWatcherFlow

    missing = tmp_path / "ghost" / "dir"
    flow = ReverseDocWatcherFlow(src_path=missing, out_dir=tmp_path / "out")

    with pytest.raises(FileNotFoundError, match="src_path does not exist"):
        flow.start()


# ---------------------------------------------------------------------------
# Test 8 — pending_paths accumulates across multiple _schedule calls
# ---------------------------------------------------------------------------


def test_pending_paths_accumulate(tmp_path: Path) -> None:
    """Multiple _schedule calls before debounce fires accumulate all paths."""
    repo = _simple_repo(tmp_path)
    out_dir = tmp_path / "docs" / "_auto"

    from autodev.flows.reverse_doc_watcher_flow import ReverseDocWatcherFlow

    flow = ReverseDocWatcherFlow(src_path=repo, out_dir=out_dir, debounce_seconds=10.0)

    def _patched_fire() -> None:
        pass  # don't actually fire

    flow._fire = _patched_fire  # type: ignore[method-assign]
    flow.start()

    paths = [
        Path(repo / "a.py"),
        Path(repo / "b.py"),
        Path(repo / "c.py"),
    ]
    for p in paths:
        flow._schedule(p)

    # Cancel the timer so it doesn't fire during the assertion
    with flow._lock:
        if flow._debounce_timer is not None:
            flow._debounce_timer.cancel()
            flow._debounce_timer = None

    assert flow._pending_paths == set(paths)

    flow.stop()
