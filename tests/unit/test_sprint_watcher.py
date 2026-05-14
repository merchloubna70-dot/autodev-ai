"""Unit tests for SprintWatcher (autodev._watcher).

These tests use a mock watchdog Observer so that watchdog does not need to
spawn real OS-level inotify/kqueue threads during the test suite.
"""
from __future__ import annotations

import threading
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_observer():
    """Return a mock watchdog Observer that does nothing real."""
    obs = MagicMock()
    obs.is_alive.return_value = True
    return obs


def _make_mock_event(path: str, is_directory: bool = False):
    """Return a mock watchdog FileSystemEvent-like object."""
    evt = MagicMock()
    evt.src_path = path
    evt.is_directory = is_directory
    return evt


# ---------------------------------------------------------------------------
# Test 1 — watcher detects file create
# ---------------------------------------------------------------------------


def test_watcher_detects_file_create(tmp_path: Path) -> None:
    """on_reload is called when a .md file-created event fires."""
    sprints_dir = tmp_path / ".autodev" / "sprints"
    sprints_dir.mkdir(parents=True, exist_ok=True)

    received: list[Path] = []

    def _reload(p: Path) -> None:
        received.append(p)

    mock_obs = _make_mock_observer()
    with patch("watchdog.observers.Observer", return_value=mock_obs):
        from autodev._watcher import SprintWatcher

        watcher = SprintWatcher(sprints_dir=sprints_dir, on_reload=_reload, debounce_seconds=0.05)
        watcher.start()

        # Simulate a "created" filesystem event via internal handler
        created_file = str(sprints_dir / "sprint-001.md")
        evt = _make_mock_event(created_file)
        watcher._handler.on_created(evt)

        # Wait for debounce timer to fire
        time.sleep(0.3)

        watcher.stop()

    assert len(received) == 1
    assert received[0] == Path(created_file)


# ---------------------------------------------------------------------------
# Test 2 — watcher detects file modify
# ---------------------------------------------------------------------------


def test_watcher_detects_file_modify(tmp_path: Path) -> None:
    """on_reload is called when a .md file-modified event fires."""
    sprints_dir = tmp_path / ".autodev" / "sprints"
    sprints_dir.mkdir(parents=True, exist_ok=True)

    received: list[Path] = []

    def _reload(p: Path) -> None:
        received.append(p)

    mock_obs = _make_mock_observer()
    with patch("watchdog.observers.Observer", return_value=mock_obs):
        from autodev._watcher import SprintWatcher

        watcher = SprintWatcher(sprints_dir=sprints_dir, on_reload=_reload, debounce_seconds=0.05)
        watcher.start()

        md_file = str(sprints_dir / "sprint-002.md")
        evt = _make_mock_event(md_file)
        watcher._handler.on_modified(evt)

        time.sleep(0.3)
        watcher.stop()

    assert len(received) == 1
    assert received[0] == Path(md_file)


# ---------------------------------------------------------------------------
# Test 3 — debounce collapses rapid-fire events into one callback
# ---------------------------------------------------------------------------


def test_watcher_debounce_works(tmp_path: Path) -> None:
    """Rapid successive events in the debounce window result in a single callback."""
    sprints_dir = tmp_path / ".autodev" / "sprints"
    sprints_dir.mkdir(parents=True, exist_ok=True)

    call_count = 0

    def _reload(p: Path) -> None:
        nonlocal call_count
        call_count += 1

    mock_obs = _make_mock_observer()
    with patch("watchdog.observers.Observer", return_value=mock_obs):
        from autodev._watcher import SprintWatcher

        # Use a slightly longer debounce so rapid events are definitely collapsed
        watcher = SprintWatcher(sprints_dir=sprints_dir, on_reload=_reload, debounce_seconds=0.1)
        watcher.start()

        md_file = str(sprints_dir / "sprint-001.md")
        evt = _make_mock_event(md_file)

        # Fire 5 events in rapid succession
        for _ in range(5):
            watcher._handler.on_modified(evt)

        # Wait slightly past debounce window
        time.sleep(0.5)
        watcher.stop()

    # All 5 rapid events should collapse to exactly 1 callback
    assert call_count == 1, f"Expected 1 callback, got {call_count}"


# ---------------------------------------------------------------------------
# Test 4 — watcher.stop() releases resources
# ---------------------------------------------------------------------------


def test_watcher_stop_releases_resources(tmp_path: Path) -> None:
    """stop() calls Observer.stop() and Observer.join() and clears _started."""
    sprints_dir = tmp_path / ".autodev" / "sprints"
    sprints_dir.mkdir(parents=True, exist_ok=True)

    mock_obs = _make_mock_observer()
    mock_obs.is_alive.side_effect = [True, False]  # alive → stopped

    with patch("watchdog.observers.Observer", return_value=mock_obs):
        from autodev._watcher import SprintWatcher

        watcher = SprintWatcher(sprints_dir=sprints_dir, on_reload=lambda p: None)
        watcher.start()
        assert watcher._started is True

        watcher.stop()

    # Observer.stop() and Observer.join() must both be called
    mock_obs.stop.assert_called_once()
    mock_obs.join.assert_called_once()
    assert watcher._started is False


# ---------------------------------------------------------------------------
# Test 5 — non-.md events are ignored
# ---------------------------------------------------------------------------


def test_watcher_ignores_non_md_files(tmp_path: Path) -> None:
    """on_reload is NOT called for non-Markdown file events."""
    sprints_dir = tmp_path / ".autodev" / "sprints"
    sprints_dir.mkdir(parents=True, exist_ok=True)

    received: list[Path] = []

    def _reload(p: Path) -> None:
        received.append(p)

    mock_obs = _make_mock_observer()
    with patch("watchdog.observers.Observer", return_value=mock_obs):
        from autodev._watcher import SprintWatcher

        watcher = SprintWatcher(sprints_dir=sprints_dir, on_reload=_reload, debounce_seconds=0.05)
        watcher.start()

        # Simulate a .json file change — should be ignored
        json_evt = _make_mock_event(str(sprints_dir / "state.json"))
        watcher._handler.on_modified(json_evt)

        # Simulate a directory event — should be ignored
        dir_evt = _make_mock_event(str(sprints_dir / "sprint-001"), is_directory=True)
        watcher._handler.on_created(dir_evt)

        time.sleep(0.3)
        watcher.stop()

    assert received == [], f"Expected no callbacks, got {received}"


# ---------------------------------------------------------------------------
# Test 6 — stop() is idempotent
# ---------------------------------------------------------------------------


def test_watcher_stop_is_idempotent(tmp_path: Path) -> None:
    """Calling stop() twice does not raise."""
    sprints_dir = tmp_path / ".autodev" / "sprints"
    sprints_dir.mkdir(parents=True, exist_ok=True)

    mock_obs = _make_mock_observer()
    mock_obs.is_alive.return_value = True

    with patch("watchdog.observers.Observer", return_value=mock_obs):
        from autodev._watcher import SprintWatcher

        watcher = SprintWatcher(sprints_dir=sprints_dir, on_reload=lambda p: None)
        watcher.start()
        watcher.stop()
        # Second stop must not raise
        watcher.stop()
