"""SearchReplaceParser — parses SEARCH/REPLACE blocks from LLM output.

Block format:
    <<<<<<< SEARCH [file_path]
    <search text>
    =======
    <replace text>
    >>>>>>> REPLACE

- file_path is optional on the SEARCH line; if omitted the parser uses the
  last seen file_path header (``# File: path``) or raises ValueError.
- Path-traversal attempts (``../``) are rejected with ValueError.
- Malformed blocks (missing separator or terminator) are silently skipped so
  the caller receives only valid patches.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from ..executors.patch_executor import FilePatch

_SEARCH_RE = re.compile(r"^<{7}\s*SEARCH\s*(?P<path>.+)?$")
_SEP = "======="
_REPLACE_END = ">>>>>>> REPLACE"


@dataclass
class SearchReplaceParser:
    """Parse ``<<<<<<< SEARCH ... ======= ... >>>>>>> REPLACE`` blocks."""

    def parse(self, text: str) -> list[FilePatch]:
        """Return a list of FilePatch objects extracted from *text*.

        Raises ValueError for path-traversal attempts.
        Silently drops malformed blocks.
        """
        patches: list[FilePatch] = []
        lines = text.splitlines()
        i = 0
        current_file: str | None = None

        while i < len(lines):
            line = lines[i]

            # Track optional ``# File: path`` header so path can be omitted on SEARCH line
            if line.strip().startswith("# File:"):
                current_file = line.strip().removeprefix("# File:").strip()
                i += 1
                continue

            m = _SEARCH_RE.match(line.strip())
            if not m:
                i += 1
                continue

            # Resolve file path
            raw_path = (m.group("path") or "").strip() or current_file
            if not raw_path:
                # No path available — skip this block
                i += 1
                continue

            _validate_path(raw_path)

            i += 1
            # Collect search lines until separator
            search_lines: list[str] = []
            found_sep = False
            while i < len(lines):
                if lines[i].strip() == _SEP:
                    found_sep = True
                    i += 1
                    break
                search_lines.append(lines[i])
                i += 1

            if not found_sep:
                continue  # malformed — skip

            # Collect replace lines until end marker
            replace_lines: list[str] = []
            found_end = False
            while i < len(lines):
                if lines[i].strip() == _REPLACE_END:
                    found_end = True
                    i += 1
                    break
                replace_lines.append(lines[i])
                i += 1

            if not found_end:
                continue  # malformed — skip

            patches.append(
                FilePatch(
                    path=raw_path,
                    new_content="\n".join(replace_lines),
                )
            )

        return patches


def _validate_path(path: str) -> None:
    """Raise ValueError if the path contains traversal sequences."""
    if "../" in path or path.startswith(".."):
        raise ValueError(f"Path traversal rejected: {path!r}")
