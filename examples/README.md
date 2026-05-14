# autodev Example Briefs

Ten representative project briefs ordered from simplest to most complex.
Each lives in its own subdirectory and follows the same structure as
`tests/fixtures/prd_project/project_brief.md`.

Run any example with:

```bash
bash examples/scripts/run_example.sh <EXAMPLE_DIR>
# e.g.
bash examples/scripts/run_example.sh 01-mdlines
```

## Table of Contents

| # | Brief name | Complexity | Language(s) | Est. time | Scale | Key concepts |
|---|------------|------------|-------------|-----------|-------|--------------|
| 01 | mdlines | Trivial | Python | 15 min | ~50 LOC | Single-file CLI, argparse, file I/O |
| 02 | slug-rs | Simple | Rust | 30 min | ~80 LOC | Library crate, base62, unit tests |
| 03 | hello-ts | Simple | TypeScript | 30 min | ~60 LOC | CLI with ts-node, typed args, ESM |
| 04 | tinyurl | Moderate | Python | 1 h | ~200 LOC | HTTP service, SQLite, multi-module |
| 05 | kanban-board | Moderate | Python + TypeScript | 2 h | ~500 LOC | Monorepo, TUI + web, shared schema |
| 06 | log-analyzer | Moderate | Python | 1.5 h | ~300 LOC | Bug-fix demo, 4-stage pipeline |
| 07 | feed-aggregator | Advanced | Rust | 3 h | ~600 LOC | Async tokio, HTTP client, SQLite |
| 08 | pdf-extractor | Advanced | Python | 2 h | ~400 LOC | Library, external deps, packaging |
| 09 | cli-wrapper | Advanced | Python | 2 h | ~350 LOC | Wrap existing CLI (git), parsing, tests |
| 10 | prfaq-product | Strategic | Markdown / any | 4 h | N/A | PRFAQ/BMAD-6, product strategy, no code |
