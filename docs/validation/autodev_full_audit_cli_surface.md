# autodev-ai CLI Surface Audit — Pre-Tag Full Audit Round

**Agent:** PreTag-C
**Date:** 2026-05-14
**Scope:** Confirm 35 CLI subcommands still have working `--help`

---

## Summary

All CLI surface checks passed. No regressions detected vs R1 Agent C.

---

## Check Results

### 1. pytest tests/unit/test_cli_help_surface.py

```
37 passed in 0.36s
```

37/37 tests pass — exceeds minimum requirement of 35.

### 2. autodev --help (exit code)

Exit: **0**

First 3 commands listed in help output:
1. `run-issue` — Run the Issue Mode flow against an existing repo.
2. `deliver-project` — Run the Project Delivery Mode flow (brief / PRD / empty repo).
3. `classify-input`

### 3. autodev --version

```
autodev-ai 0.1.0a1
```

Exit: 0. Matches expected `autodev-ai 0.1.0a1`.

### 4. python -m autodev.cli --help

Exit: **0**. Full command list rendered identically to `autodev --help`.

### 5. python -m autodev.cli --version

```
autodev-ai 0.1.0a1
```

Exit: 0. Module invocation form works correctly.

### 6. @app.command count in src/autodev/cli.py

```
35
```

Exactly 35 `@app.command` decorators found — meets the minimum requirement.

### 7. docs/release_notes/v0.1.0a1.md CLI overview

File present. Contains a CLI overview section with `autodev --help` usage instruction and 5-minute quickstart referencing subcommands including `deliver-project`.

---

## Full Command List (35 subcommands)

| # | Command | Description |
|---|---------|-------------|
| 1 | `run-issue` | Run the Issue Mode flow against an existing repo |
| 2 | `deliver-project` | Run the Project Delivery Mode flow (brief / PRD / empty repo) |
| 3 | `classify-input` | Classify input type |
| 4 | `create-prd` | Create PRD |
| 5 | `plan-project` | Plan project |
| 6 | `plan-milestones` | Plan milestones |
| 7 | `plan-tasks` | Plan tasks |
| 8 | `execute-milestone` | Execute milestone |
| 9 | `continue-run` | Continue a paused run |
| 10 | `replay` | Replay a previous run |
| 11 | `scan` | Scan repository |
| 12 | `verify` | Verify artifacts |
| 13 | `release-check` | Release readiness check |
| 14 | `report` | Generate report |
| 15 | `export-delivery` | Export delivery artifacts |
| 16 | `push` | Push the current branch to origin |
| 17 | `create-pr` | Create a GitHub PR via gh CLI |
| 18 | `fix-bug` | Run the 4-stage bug-fix flow |
| 19 | `multi-patch-fix-bug` | Run multi-patch self-consistency |
| 20 | `review` | Write approved/rejected sentinel for HumanReviewGate |
| 21 | `roundtable` | Run BMAD party-mode roundtable |
| 22 | `mcp-serve` | Start autodev as MCP server on stdio |
| 23 | `a2a-serve` | Start the A2A HTTP server |
| 24 | `a2a-register` | Discover AgentCard from remote A2A endpoint |
| 25 | `a2a-call` | Send A2ATask to remote A2A agent |
| 26 | `next` | Suggest next concrete action |
| 27 | `design-ux` | Run BMAD-Sally-style UX design workflow |
| 28 | `investigate` | Open structured case file for investigation |
| 29 | `generate-context` | Generate project-context.md from repo |
| 30 | `document-project` | Generate brownfield AI-onboarding docs |
| 31 | `sprint-start` | Open new BMAD sprint |
| 32 | `sprint-status` | Report health metrics for current sprint |
| 33 | `sprint-retro` | Run retrospective analysis for given sprint |
| 34 | `sprint-correct` | Analyse impact of change across PRD/Epic/Arch/UX |
| 35 | `dashboard` | Launch the Textual TUI dashboard |

---

## Verdict

**cli_surface_stable** — 37/37 pytest pass, 35/35 commands registered and all respond to `--help` with exit 0. No regression vs R1 Agent C.
