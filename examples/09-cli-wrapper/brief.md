# Project Brief: cli-wrapper — git Stats Reporter

A Python command-line tool that wraps `git` to produce human-friendly
contribution statistics for a repository: commits per author, files changed,
and hot-spot files by churn rate.

## Goals
- Invoke `git log` and `git diff` via subprocess and parse their output reliably.
- Produce readable tabular output and an optional JSON export.
- Demonstrate best practices for wrapping an existing CLI tool.

## Users
- Engineering managers who want a quick team contribution summary.
- Developers auditing which files change most often in a codebase.

## Use Cases
- `git-stats --repo . --since 30d` prints a table of commits and lines changed per author.
- `git-stats --repo . --hot-spots 10` lists the 10 files with the highest churn.
- `git-stats --repo . --out report.json` exports the full dataset as JSON.

## MVP Scope
- Single entry-point script `git_stats/cli.py` with `click`-based argument parsing.
- `git_stats/git.py`: subprocess wrappers for `git log --numstat` and `git diff`.
- `git_stats/report.py`: aggregation logic producing `AuthorStats` and `FileChurn` dataclasses.
- `git_stats/render.py`: tabulate-based terminal rendering and JSON serialiser.
- `pytest` suite with fixture git repos created via `pygit2` or `gitpython` in temp dirs.
- `pyproject.toml` with `click`, `tabulate` runtime deps; `pygit2` or `gitpython` for tests.

## Non-Goals
- GitHub/GitLab API integration.
- Blame-level attribution.
- Support for non-git VCS.

Delivery boundary: Single repository, requires `git` binary on PATH, all tests
runnable offline using in-process fixture repositories.
