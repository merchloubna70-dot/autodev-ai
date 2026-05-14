# Tutorial 01 — Bug-Fix Flow

This tutorial walks through the `fix-bug` command on the `examples/06-log-analyzer`
demo repository, which ships with a pre-planted off-by-one bug in its percentile
calculation.

**Time to complete:** ~5 minutes (with mock executor)

---

## The bug

`examples/06-log-analyzer` contains a Python log-analysis library. The p99
latency computation in `aggregate.py` reads:

```python
sorted_values[int(len(sorted_values) * 0.99)]   # off-by-one — index too high
```

The correct expression is:

```python
sorted_values[int(len(sorted_values) * 0.99) - 1]
```

A failing test `tests/test_aggregate.py::test_p99` already exposes the problem.

---

## Step 1 — Copy the example to a working directory

```bash
cp -r examples/06-log-analyzer /tmp/log-analyzer-demo
```

---

## Step 2 — Run the 4-stage fix-bug flow

```bash
autodev fix-bug \
  --bug "p99 latency is wrong: off-by-one index in sorted_values lookup in aggregate.py" \
  --repo-path /tmp/log-analyzer-demo \
  --languages python \
  --mode dry-run \
  --allow-mock-executor true
```

Expected output:

```
run_id=20240514-143500-d4e5f6 success=True mock=True
```

---

## Stage breakdown

The `fix-bug` command internally runs four stages in sequence:

### Stage 1 — Reproduce

The **ReproduceAgent** converts your free-text `--bug` description into a
structured reproduction scenario: it identifies the affected module, writes a
minimal reproduction script (or points at the existing failing test), and
records its findings to:

```
/tmp/log-analyzer-demo/.dev-factory/runs/<run_id>/
└── execution/
    └── milestone_M1_results.json   ← reproduce stage output
```

Key fields in `milestone_M1_results.json`:

```json
{
  "stage": "reproduce",
  "affected_files": ["aggregate.py"],
  "reproduction_command": "pytest tests/test_aggregate.py::test_p99",
  "error_summary": "IndexError or wrong value at p99 boundary"
}
```

### Stage 2 — Locate

The **RepoExplorerAgent** scans the repository to pinpoint the exact line:

```
└── execution/
    └── milestone_M2_results.json   ← locate stage output
```

```json
{
  "stage": "locate",
  "file": "aggregate.py",
  "line": 42,
  "snippet": "sorted_values[int(len(sorted_values) * 0.99)]",
  "root_cause": "Index overshoots by 1 when len * 0.99 is exact integer"
}
```

### Stage 3 — Patch

The **ExecutorRouter** selects a backend (Codex for a small single-file patch)
and applies the fix. With `--mode dry-run`, the patch is recorded but NOT
written to disk:

```
└── execution/
    ├── executor_selection_patch.json   ← router chose codex, why
    └── execution_calls.jsonl           ← the exact CLI command that would run
```

With `--mode apply` the router actually invokes `codex exec ...` (or `claude
--print ...`) and writes the corrected file.

### Stage 4 — Verify

The **VerifierAgent** runs the test suite against the patched code and records
pass/fail:

```
└── verification/
    ├── verification_report.json
    └── release_check.json
```

```json
{
  "test_command": "pytest tests/",
  "passed": true,
  "mock_execution_used": true,
  "release_decision": "NotReleaseReady"
}
```

`NotReleaseReady` is always set in `dry-run` mode because mock execution cannot
produce real test evidence.

---

## Step 3 — Apply for real (requires Codex CLI or Claude Code CLI)

```bash
autodev fix-bug \
  --bug "p99 latency is wrong: off-by-one index in sorted_values lookup in aggregate.py" \
  --repo-path /tmp/log-analyzer-demo \
  --languages python \
  --mode apply \
  --executor auto
```

The router picks **Codex** (single-file patch, low risk) and runs:

```
codex exec --skip-git-repo-check "Fix off-by-one in aggregate.py p99 calculation..."
```

After success the verifier calls `pytest` and, if tests pass, sets
`release_decision=ReleaseReady`.

---

## Viewing the full audit trail

```bash
# Structured summary
autodev report --run-id <run_id> --repo-path /tmp/log-analyzer-demo

# Raw artifacts
ls /tmp/log-analyzer-demo/.dev-factory/runs/<run_id>/
```

---

## See also

- [Tutorial 02 — Rust project](02-rust-project.md)
- [Tutorial 03 — Multi-CLI routing](03-multi-cli-routing.md) — understand why the router chose Codex here
- [FAQ — What if I have no API key?](../faq.md)
