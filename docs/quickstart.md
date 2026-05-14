# 5-Minute Quickstart

Get from `git clone` to a finished demo project in under five minutes.

## Prerequisites

- Python 3.10+
- Git

You do **not** need a running Codex or Claude Code installation for the demo
— `--allow-mock-executor true` activates deterministic stubs that produce
realistic audit artifacts without spending any API quota.

---

## Step 1 — Install

```bash
git clone https://github.com/your-org/autodev-ai.git
cd autodev-ai
pip install -e ".[dev]"
```

Verify:

```bash
autodev --help
```

Expected output (abbreviated):

```
Usage: autodev [OPTIONS] COMMAND [ARGS]...

  CrewAI + Codex CLI + Claude Code CLI multi-CLI software factory

Options:
  --help  Show this message and exit.

Commands:
  deliver-project  Run the Project Delivery Mode flow (brief / PRD / empty repo)
  fix-bug          Run the 4-stage bug-fix flow (reproduce → locate → patch → verify)
  roundtable       Run a BMAD party-mode roundtable ...
  ...
```

---

## Step 2 — Credentials (optional for the demo)

For real Codex CLI execution set:

```bash
export OPENAI_API_KEY="sk-..."
```

For real Claude Code CLI execution set:

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
# or use your Claude Max subscription — claude CLI handles auth automatically
```

Environment variables that control which binaries are used:

| Variable              | Default                              | Purpose                    |
|-----------------------|--------------------------------------|----------------------------|
| `FACTORY_CODEX_BIN`   | `codex`                              | Codex CLI binary path      |
| `FACTORY_CLAUDE_BIN`  | `claude`                             | Claude Code binary path    |
| `FACTORY_FORCE_MOCK`  | _(unset)_                            | Set `1` to force all mocks |

For the 5-minute demo you can skip all of the above — the mock executor is
activated automatically by `--allow-mock-executor true`.

---

## Step 3 — Run the demo project

```bash
autodev deliver-project \
  --project-brief examples/01-mdlines/brief.md \
  --from-scratch true \
  --mode dry-run \
  --executor auto \
  --allow-mock-executor true \
  --repo-path /tmp/mdlines-demo
```

The command runs through seven pipeline stages (classify → PRD → architect →
plan → scaffold → quality-gate → verify) and exits in roughly 10–30 seconds
with mock executors.

Expected terminal output:

```
[autodev] --scale not given; will auto-infer from PRD/brief
run_id=20240514-143012-a1b2c3 mode=dry-run mock=True release=NotReleaseReady
```

`release=NotReleaseReady` is expected and correct for `--mode dry-run` — the
pipeline records that mock execution was used and refuses to claim the run is
production-ready.

---

## Step 4 — Explore the artifacts

```
/tmp/mdlines-demo/.dev-factory/runs/<run_id>/
├── input/
│   ├── classification.json      ← input type: project_delivery / issue / …
│   └── raw_input.md             ← the brief text as received
├── product/
│   ├── product_brief.json       ← structured brief fields
│   ├── prd.md                   ← generated Product Requirements Document
│   └── prd.json                 ← machine-readable PRD
├── architecture/
│   ├── architecture.md          ← high-level design doc
│   ├── module_map.json          ← modules and their responsibilities
│   └── api_contract.json        ← public interfaces
├── planning/
│   ├── milestones.json          ← M1 / M2 / M3 milestone list
│   ├── tasks.json               ← task graph with dependencies
│   └── delivery_plan.md        ← human-readable plan
├── execution/
│   ├── executor_selection_*.json ← which CLI was picked per task, and why
│   ├── execution_calls.jsonl    ← every CLI invocation record
│   └── milestone_*_results.json ← per-milestone outcomes
├── quality/
│   ├── quality_gate.json        ← PASS / FAIL per gate dimension
│   ├── security_review.json     ← security findings
│   └── code_review.json         ← code review notes
├── verification/
│   ├── verification_report.json ← final test / lint pass/fail
│   └── release_check.json       ← ReleaseReady / NotReleaseReady decision
└── delivery/
    ├── README.generated.md      ← project README written by Doc Writer agent
    ├── usage.generated.md       ← usage guide
    ├── release_notes.md         ← change log
    └── final_report.md          ← human-readable end-to-end summary
```

Open `delivery/final_report.md` for a narrative summary:

```bash
cat /tmp/mdlines-demo/.dev-factory/runs/*/delivery/final_report.md
```

---

## What just happened?

```
Brief → [InputClassifier] → [PRDWriter] → [SystemArchitect]
      → [MilestonePlanner] → [TaskDecomposer] → [ExecutorRouter]
      → [QualityGate] → [SecurityReviewer] → [Verifier] → [DocWriter]
      → final_report.md
```

All intermediate state is on disk. If anything fails you can resume with:

```bash
autodev continue-run --run-id <run_id> --repo-path /tmp/mdlines-demo
```

---

## Next steps

- [Tutorial 01 — Bug-fix flow](tutorials/01-bug-fix.md)
- [Tutorial 02 — Rust project](tutorials/02-rust-project.md)
- [Tutorial 03 — Multi-CLI routing](tutorials/03-multi-cli-routing.md)
- [Tutorial 04 — Sprint mode](tutorials/04-sprint-mode.md)
- [Tutorial 05 — Roundtable party-mode](tutorials/05-roundtable.md)
- [Tutorial 06 — MCP server](tutorials/06-mcp-server.md)
- [Tutorial 07 — A2A server](tutorials/07-a2a-server.md)
- [Architecture reference](architecture.md)
- [FAQ](faq.md)
