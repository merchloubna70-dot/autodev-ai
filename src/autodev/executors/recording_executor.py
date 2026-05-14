"""RecordingExecutorWrapper — thin wrapper that adds record/replay to any executor.

Environment variables:
  AUTODEV_RECORD_DIR=/path/to/dir
      When set, every executor call ALSO writes a ``<request_hash>.json`` file
      containing {request, response, timestamp, executor}.  The underlying call
      is unaffected.

  AUTODEV_REPLAY_DIR=/path/to/dir
      When set, executor calls FIRST hash the request, then look for
      ``<hash>.json`` in the directory.  If found, the recorded response is
      returned without invoking the real CLI.  If not found, the call falls
      through to the wrapped executor.

Both variables may be set simultaneously; recording always happens AFTER the
real (or replayed) response is obtained, so replayed responses can be
re-recorded into a different directory if needed.

Hashing is deterministic: sha256 over the JSON-serialised request (sorted
keys, no whitespace).  This makes the same logical request always resolve to
the same filename, regardless of field order or Python dict iteration order.
"""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from ..schemas import ExecutionRequest, ExecutionResult
from .base_executor import BaseExecutor


def _request_hash(request: ExecutionRequest) -> str:
    """Return a stable SHA-256 hex digest for *request*."""
    payload = request.model_dump(mode="json")
    # Sort keys for determinism; separate keys/values compactly
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class RecordingExecutorWrapper(BaseExecutor):
    """Wraps any :class:`BaseExecutor` with optional record/replay behaviour.

    Parameters
    ----------
    wrapped:
        The underlying executor to delegate to when replay is not active or
        when no recording exists for the given request.
    record_dir:
        Directory to write ``<hash>.json`` recording files.  Overrides the
        ``AUTODEV_RECORD_DIR`` environment variable when provided explicitly.
    replay_dir:
        Directory to read ``<hash>.json`` recording files from.  Overrides
        the ``AUTODEV_REPLAY_DIR`` environment variable when provided
        explicitly.

    When *neither* ``record_dir`` nor the env var is set, and *neither*
    ``replay_dir`` nor the env var is set, the wrapper is a pure pass-through
    with zero overhead.
    """

    def __init__(
        self,
        wrapped: BaseExecutor,
        *,
        record_dir: str | os.PathLike | None = None,
        replay_dir: str | os.PathLike | None = None,
    ) -> None:
        self._wrapped = wrapped
        # Resolve directories: explicit args beat env vars; both may be None.
        _record_env = os.environ.get("AUTODEV_RECORD_DIR")
        _replay_env = os.environ.get("AUTODEV_REPLAY_DIR")
        self._record_dir: Path | None = (
            Path(record_dir) if record_dir is not None
            else (Path(_record_env) if _record_env else None)
        )
        self._replay_dir: Path | None = (
            Path(replay_dir) if replay_dir is not None
            else (Path(_replay_env) if _replay_env else None)
        )

    # ------------------------------------------------------------------
    # BaseExecutor API
    # ------------------------------------------------------------------

    @property
    def backend(self):  # type: ignore[override]
        return self._wrapped.backend

    @property
    def is_mock(self) -> bool:  # type: ignore[override]
        return self._wrapped.is_mock

    def is_available(self) -> bool:
        return self._wrapped.is_available()

    def execute(self, request: ExecutionRequest) -> ExecutionResult:
        req_hash = _request_hash(request)

        # --- Replay path ---
        if self._replay_dir is not None:
            recorded_path = self._replay_dir / f"{req_hash}.json"
            if recorded_path.exists():
                raw = json.loads(recorded_path.read_text(encoding="utf-8"))
                result = ExecutionResult.model_validate(raw["response"])
                return result

        # --- Real (or mock) execution ---
        result = self._wrapped.execute(request)

        # --- Record path ---
        if self._record_dir is not None:
            self._record_dir.mkdir(parents=True, exist_ok=True)
            record_payload = {
                "request": request.model_dump(mode="json"),
                "response": result.model_dump(mode="json"),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "executor": type(self._wrapped).__name__,
            }
            # Atomic write via a temp file in the same directory to avoid
            # partial writes visible to concurrent readers.
            target = self._record_dir / f"{req_hash}.json"
            tmp_fd, tmp_path = tempfile.mkstemp(
                dir=self._record_dir, prefix=".tmp-rec-", suffix=".json"
            )
            try:
                with os.fdopen(tmp_fd, "w", encoding="utf-8") as fh:
                    json.dump(record_payload, fh, indent=2)
                os.replace(tmp_path, target)
            except Exception:
                # Best-effort: clean up temp file if rename failed
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
                raise

        return result
