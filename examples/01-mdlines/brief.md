# Project Brief: mdlines — Markdown Line Counter

A minimal Python command-line tool that counts and reports lines in one or more
Markdown files, broken down by section heading.

## Goals
- Provide a single-file Python script usable with no install beyond stdlib.
- Count total lines, blank lines, and code-fence lines per file.
- Support multiple input files and a `--summary` flag for aggregate totals.

## Users
- Technical writers who want quick stats on documentation length.
- Developers auditing generated Markdown output.

## Use Cases
- Run `python mdlines.py README.md` to see a per-section line breakdown.
- Run `python mdlines.py docs/*.md --summary` to print aggregate totals.

## MVP Scope
- Single Python file `mdlines.py`, no third-party dependencies.
- `argparse`-based CLI with positional `files` argument and `--summary` flag.
- Output: table with columns `file | heading | total | blank | code`.
- Exit non-zero when any input file is missing.

## Non-Goals
- Recursive directory traversal.
- JSON or CSV output modes.
- Character or word counts.

Delivery boundary: Single repository, single Python file, stdlib only, no packaging required.
