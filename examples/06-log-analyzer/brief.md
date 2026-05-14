# Project Brief: log-analyzer — 4-Stage Bug-Fix Demo

A Python log-analysis library that ingests NGINX-style access logs and produces
traffic summaries. The repository is delivered with a pre-planted off-by-one bug
in the percentile calculation, intended to exercise the autodev bug-fix pipeline.

## Goals
- Demonstrate a 4-stage autodev workflow: ingest → parse → aggregate → report.
- Provide a realistic bug for autodev to detect, explain, fix, and verify.
- Produce a human-readable summary report as a text file.

## Users
- Site reliability engineers reviewing daily traffic patterns.
- autodev evaluators testing the bug-fix and test-generation capabilities.

## Use Cases
- `python analyze.py access.log --out report.txt` produces a summary report.
- `python analyze.py access.log --top 10` prints the ten busiest URL paths.
- Running `pytest` catches the pre-planted percentile bug via a failing test.

## MVP Scope
- Four Python modules: `ingest.py`, `parse.py`, `aggregate.py`, `report.py`.
- Pre-planted bug: p99 latency computed as `sorted_values[int(len * 0.99)]`
  (off-by-one; should use `sorted_values[int(len * 0.99) - 1]` or `math.ceil`).
- Failing test `tests/test_aggregate.py::test_p99` that exposes the bug.
- After fix, all tests green; report output verified by a snapshot test.
- Accepts standard NGINX combined log format.

## Non-Goals
- Streaming or tail-follow mode.
- Database storage of parsed results.
- Real-time dashboards.

Delivery boundary: Single repository, stdlib + `pytest` only, bug present in
initial commit and fixed by autodev in a subsequent commit.
