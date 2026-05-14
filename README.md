# autodev-ai

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python ≥3.10](https://img.shields.io/badge/python-%E2%89%A53.10-blue)](https://www.python.org)
[![PyPI](https://img.shields.io/pypi/v/autodev-ai)](https://pypi.org/project/autodev-ai/)

**A multi-CLI software factory powered by CrewAI agents, Codex CLI, and Claude Code CLI.**

From a one-paragraph project brief to milestone-driven, gate-protected delivery — with a full
audit trail, A2A agent networking, MCP server support, and sprint-mode planning.

---

<!-- 30-sec demo gif placeholder -->
<!-- ![autodev demo](docs/assets/demo.gif) -->

---

## Install

> **Status**: alpha — [`v0.1.0-alpha`](https://github.com/merchloubna70-dot/autodev-ai/releases/tag/v0.1.0-alpha) on GitHub Releases.
> PyPI publish gated on user feedback; install from wheel or source for now.

From the GitHub Release wheel:

```bash
pip install https://github.com/merchloubna70-dot/autodev-ai/releases/download/v0.1.0-alpha/autodev_ai-0.1.0-py3-none-any.whl
```

From source:

```bash
git clone https://github.com/merchloubna70-dot/autodev-ai.git
cd autodev-ai
pip install -e ".[dev]"
```

Docker (codex + claude pre-installed, ~2 GB):

```bash
docker pull ghcr.io/merchloubna70-dot/autodev-ai:0.1.0-alpha
docker run --rm ghcr.io/merchloubna70-dot/autodev-ai:0.1.0-alpha --help
```

Optional — real CrewAI runtime:

```bash
pip install -e ".[crewai]"
```

---

## 5-minute quickstart

No API key required — the mock executor generates realistic artifacts instantly.

```bash
# Deliver a full project from a brief (dry-run, mock mode)
autodev deliver-project \
  --project-brief examples/01-mdlines/brief.md \
  --from-scratch true \
  --mode dry-run \
  --executor auto \
  --allow-mock-executor true \
  --repo-path /tmp/mdlines-demo

# Explore what was produced
ls /tmp/mdlines-demo/.dev-factory/runs/*/delivery/
cat /tmp/mdlines-demo/.dev-factory/runs/*/delivery/final_report.md
```

Expected output:

```
[autodev] --scale not given; will auto-infer from PRD/brief
run_id=20240514-143012-a1b2c3 mode=dry-run mock=True release=NotReleaseReady
```

See the full [5-minute quickstart guide](docs/quickstart.md).

---

## Features

### CrewAI agents — full pipeline coverage

A structured agent graph converts any input (brief / PRD / GitHub issue / bug
description) into structured delivery artifacts:

```
InputClassifier → ProductManager → PRDWriter → SystemArchitect
    → MilestonePlanner → TaskDecomposer → ExecutorRouter
    → QualityGate → SecurityReviewer → Verifier → DocWriter
    → ReleaseManager → audit artifacts on disk
```

### Multi-CLI executor routing

All CLI traffic passes through a single `ExecutorRouter`. It automatically
selects between **Codex CLI** (mechanical writes, small patches, tests,
scaffolds) and **Claude Code CLI** (architecture, long-context refactors,
security reviews, release roll-ups).

```bash
autodev deliver-project ... --executor auto    # smart routing (default)
autodev deliver-project ... --executor codex   # force Codex for everything
autodev deliver-project ... --executor claude  # force Claude Code for everything
```

| Task type | Default backend |
|-----------|----------------|
| Scaffold, test generation, small patch | Codex CLI |
| Architecture, refactor, security, docs, release | Claude Code CLI |
| Either CLI missing + `--allow-mock-executor true` | Mock (deterministic) |

### 4-stage bug-fix flow

```bash
autodev fix-bug \
  --bug "p99 latency is wrong: off-by-one index in aggregate.py" \
  --repo-path /tmp/log-analyzer \
  --mode dry-run \
  --allow-mock-executor true
```

Stages: **Reproduce → Locate → Patch → Verify**. Every step produces a
structured JSON artifact. See [Tutorial 01 — Bug-fix flow](docs/tutorials/01-bug-fix.md).

### BMAD-derived sprint mode

Plan and track multi-week sprints with course-correction support:

```bash
autodev sprint-start  --goal "Deliver MVP slug library" --duration-days 10
autodev sprint-status
autodev sprint-retro  --sprint-id sprint-001
autodev sprint-correct --sprint-id sprint-001 --change "Add JSON output mode"
```

See [Tutorial 04 — Sprint mode](docs/tutorials/04-sprint-mode.md).

### Roundtable party-mode (A2A)

Recruit N specialist agents by skill, get independent analysis, synthesize:

```bash
autodev roundtable \
  --topic "SQLite vs PostgreSQL for the kanban board" \
  --skills security,arch,perf \
  --repo-path /tmp/my-project
```

Set `FACTORY_FORCE_MOCK=1` for CI / no-API-key usage. See
[Tutorial 05 — Roundtable](docs/tutorials/05-roundtable.md).

### MCP server — use autodev from Claude Desktop

```bash
autodev mcp-serve   # JSON-RPC 2.0 over stdio
```

Add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "autodev": {
      "command": "autodev",
      "args": ["mcp-serve"]
    }
  }
}
```

See [Tutorial 06 — MCP server](docs/tutorials/06-mcp-server.md).

### A2A server — accept tasks from external agents

```bash
autodev a2a-serve --port 8421
autodev a2a-call --endpoint http://127.0.0.1:8421 --skill fix-bug \
  --task-json '{"text": "Fix the percentile bug"}'
```

See [Tutorial 07 — A2A server](docs/tutorials/07-a2a-server.md).

### Full audit trail

Every run writes a structured artifact tree under
`<repo>/.dev-factory/runs/<run_id>/`:

```
input/ product/ architecture/ planning/ execution/
quality/ verification/ delivery/ run_state.json
```

Runs are resumable (`autodev continue-run`), replayable (`autodev replay`),
and support milestone-by-milestone execution (`autodev execute-milestone`).

### Safety baked in

- No business code calls `codex` or `claude` directly — only `ExecutorRouter`
- Shell executor blocks `rm -rf`, `sudo`, `cat .env`, `curl | bash`, etc. in all modes
- `--commit`, `--push`, `--tag` are off by default — opt in explicitly
- `release_check` returns `NotReleaseReady` when mock execution or `dry-run` was used
- `final_report.md` never relabels a failed gate as passed

---

## Multi-CLI routing table

| Task type | Default backend | Why |
|-----------|----------------|-----|
| scaffold | Codex | Small mechanical writes |
| test | Codex | Targeted unit-test additions |
| feature (≤5 files, low/medium risk) | Codex | Fast, deterministic |
| feature (>5 files or high risk) | Claude Code | Long-context reasoning |
| refactor | Claude Code | Multi-file coherence |
| architecture | Claude Code | System design |
| integration (single-language) | Codex | Targeted API changes |
| integration (cross-language) | Claude Code | Contract reasoning |
| security | Claude Code | Deeper threat review |
| docs | Claude Code | Tone and cohesion |
| release | Claude Code | Evidence roll-up |

---

## All CLI commands

```
autodev deliver-project    — Brief/PRD → full project delivery
autodev run-issue          — GitHub issue → structured change
autodev fix-bug            — 4-stage bug-fix: reproduce/locate/patch/verify
autodev multi-patch-fix-bug — Generate N patch candidates, vote for best
autodev execute-milestone  — Run a single milestone from a completed plan
autodev continue-run       — Resume a failed run from last checkpoint
autodev replay             — Re-run a stage from a checkpoint
autodev scan               — Scan repo for context
autodev verify             — Run verification on a completed run
autodev release-check      — Evaluate release readiness
autodev report             — Print run summary
autodev export-delivery    — Export delivery artifacts to a directory
autodev push               — Push committed changes to remote
autodev create-pr          — Open a GitHub PR for a completed run
autodev sprint-start       — Open a new sprint
autodev sprint-status      — Check sprint health metrics
autodev sprint-retro       — Run a retrospective
autodev sprint-correct     — Analyse mid-sprint change impact
autodev roundtable         — Party-mode A2A discussion by skill
autodev mcp-serve          — Start MCP server over stdio
autodev a2a-serve          — Start A2A HTTP server
autodev a2a-register       — Register a remote A2A agent
autodev a2a-call           — Send a task to a remote A2A agent
autodev next               — Suggest next action from run state
autodev design-ux          — BMAD-Sally UX design workflow
autodev investigate        — Open a structured investigation case
autodev generate-context   — Generate project-context.md from repo
autodev document-project   — Generate brownfield AI-onboarding docs
autodev classify-input     — Classify a brief/issue into mode + metadata
autodev create-prd         — Generate a PRD from a brief
autodev plan-project       — Generate a project plan from PRD
autodev plan-milestones    — Generate milestones from a project plan
autodev plan-tasks         — Generate tasks from milestones
autodev review             — Approve/reject a paused human-review gate
```

---

## Documentation

| Doc | Contents |
|-----|----------|
| [5-minute quickstart](docs/quickstart.md) | Install → credentials → first run → explore artifacts |
| [Tutorial 01 — Bug-fix flow](docs/tutorials/01-bug-fix.md) | 4-stage fix-bug on log-analyzer |
| [Tutorial 02 — Rust project](docs/tutorials/02-rust-project.md) | Deliver slug-rs from brief |
| [Tutorial 03 — Multi-CLI routing](docs/tutorials/03-multi-cli-routing.md) | ExecutorRouter internals |
| [Tutorial 04 — Sprint mode](docs/tutorials/04-sprint-mode.md) | sprint-start / status / retro / correct |
| [Tutorial 05 — Roundtable](docs/tutorials/05-roundtable.md) | Party-mode A2A discussion |
| [Tutorial 06 — MCP server](docs/tutorials/06-mcp-server.md) | Claude Desktop integration |
| [Tutorial 07 — A2A server](docs/tutorials/07-a2a-server.md) | HTTP agent-to-agent |
| [Architecture reference](docs/architecture.md) | Layers, flows, audit trail, failure policy |
| [Configuration](docs/configuration.md) | ConfigStack 4-layer TOML, env vars, Codex/Claude CLI auth, MCP, A2A |
| [Troubleshooting](docs/troubleshooting.md) | 12 common problems and fixes |
| [FAQ](docs/faq.md) | Top 15 questions |
| [CHANGELOG](CHANGELOG.md) | Release history |
| [Contributing](docs/contributing.md) | How to contribute |

---

## License

MIT.
