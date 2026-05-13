# Quality Gate

- `PythonGate`: `pytest`, `ruff check .`. Each tool is skipped (not faked
  as passing) when not installed.
- `RustGate`: `cargo test`, `cargo clippy --workspace --all-targets -- -D
  warnings`.
- `TypeScriptGate`: `{npm|pnpm|yarn} run typecheck` / `lint` / `test`.
- `IntegrationGate`: checks API-contract duplicates, dependency-graph
  drift, cross-language flag.

Each gate emits a `QualityGateResult` with `overall_status` ∈ `{passed,
failed, skipped, not_applicable}`. The reporter writes these verbatim;
it never re-labels them.
