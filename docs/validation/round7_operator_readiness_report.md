# Round 7 — Operator Readiness Report

**Agent**: 12 — operator_readiness  
**Project**: autodev-ai v0.1.0a3  
**Date**: 2026-05-14  
**Overall Result**: PARTIAL  

---

## Executive Summary

Documentation broadly supports production-alpha use with no P0 or P1 findings.
Seven P2 findings were identified, primarily around version drift (README/quickstart
still reference v0.1.0a1 artifacts while v0.1.0a3 is current), a missing
`dashboard` command from the "All CLI commands" table, absent security-boundary
prose in `architecture.md` and `a2a.md`, incomplete alpha-limitations disclosure
in the primary README, and two undocumented env vars (`FACTORY_NET_ALLOW`,
`FACTORY_CODEX_CMD` / `FACTORY_CLAUDE_CMD` missing from `configuration.md`).
One P3 finding (Homebrew absent from README install section).

---

## Docs Inventory

| Path | Lines | Covered |
|------|-------|---------|
| README.md | 294 | yes |
| CHANGELOG.md | 190 | yes |
| docs/quickstart.md | 178 | yes |
| docs/configuration.md | 298 | yes |
| docs/architecture.md | 276 | yes |
| docs/troubleshooting.md | 310 | yes |
| docs/faq.md | 255 | yes |
| docs/a2a.md | 103 | yes |
| docs/mcp_server.md | 83 | yes |
| docs/multi_cli_executor.md | 107 | yes |
| docs/project_delivery.md | 41 | yes |
| docs/quality_gate.md | 14 | yes |
| docs/tutorials/01-bug-fix.md | 182 | yes |
| docs/tutorials/02-rust-project.md | 156 | yes |
| docs/tutorials/03-multi-cli-routing.md | 163 | yes |
| docs/tutorials/04-sprint-mode.md | 191 | yes |
| docs/tutorials/05-roundtable.md | 152 | yes |
| docs/tutorials/06-mcp-server.md | 171 | yes |
| docs/tutorials/07-a2a-server.md | 208 | yes |
| docs/release/homebrew_tap_publish_checklist.md | 77 | yes |
| docs/release/pypi_0_1_0a1_publish_checklist.md | 246 | yes |
| docs/release/pypi_0_1_0a1_rollback_plan.md | 249 | yes |
| docs/release/pypi_token_rotation_checklist.md | 93 | yes |
| docs/release_notes/v0.1.0a1.md | 242 | yes |

---

## Rubric 1 — 10-Minute Install + Mock Run

**Result**: PARTIAL

### Step-by-step walkthrough

**Step 1 — Install (quickstart.md line 19):**
```bash
git clone https://github.com/your-org/autodev-ai.git
```
**FAIL** — placeholder org `your-org` instead of actual `https://github.com/merchloubna70-dot/autodev-ai.git`. A new user copying this literally will get a 404. (P2)

**Step 2 — Credentials (quickstart.md):**
- Correctly marks API keys as optional for the demo.
- `FACTORY_FORCE_MOCK` is listed in the table but the demo command relies only on `--allow-mock-executor true`, not `FACTORY_FORCE_MOCK=1` explicitly.
- PASS on "API keys optional" framing; PARTIAL on FACTORY_FORCE_MOCK explicit mention.

**Step 3 — Run demo (quickstart.md line 80-87):**
```bash
autodev deliver-project \
  --project-brief examples/01-mdlines/brief.md \
  --from-scratch true \
  --mode dry-run \
  --executor auto \
  --allow-mock-executor true \
  --repo-path /tmp/mdlines-demo
```
- Command is executable as-written once installed.
- Does NOT set `FACTORY_FORCE_MOCK=1` explicitly; relies on `--allow-mock-executor true` only. Rubric asks for explicit `FACTORY_FORCE_MOCK=1`. The env var is mentioned in the table at Step 2 but not used in the demo command. (P3 — documented, just not in the demo command itself)
- Expected output is accurate.
- PASS on executability.

**Step 4 — Explore artifacts:**
- Artifact tree layout is accurate and complete.
- PASS.

### Summary findings

| Item | Status | Severity |
|------|--------|----------|
| Placeholder clone URL `your-org` in quickstart.md line 19 | FAIL | P2 |
| API keys explicitly optional | PASS | — |
| FACTORY_FORCE_MOCK=1 in demo command | PARTIAL (in table, not in cmd) | P3 |
| Commands match 35-command CLI surface | PASS | — |

---

## Rubric 2 — Environment Variable Coverage

**Result**: PARTIAL

### Variables used in src/autodev/

**AUTODEV_** prefix:
- `AUTODEV_MCP_ALLOW_APPLY`
- `AUTODEV_MCP_AUDIT_LOG`
- `AUTODEV_A2A_ALLOW_PRIVATE_NETWORKS`
- `AUTODEV_A2A_TOKEN`

**FACTORY_** prefix:
- `FACTORY_FORCE_MOCK`
- `FACTORY_LOG`
- `FACTORY_CODEX_BIN`
- `FACTORY_CODEX_CMD`
- `FACTORY_CLAUDE_BIN`
- `FACTORY_CLAUDE_CMD`
- `FACTORY_NET_ALLOW`

### Documentation status

| Variable | Documented in configuration.md | Also in other docs |
|----------|-------------------------------|-------------------|
| `AUTODEV_MCP_ALLOW_APPLY` | YES (section 2.2) | CHANGELOG, release_notes |
| `AUTODEV_MCP_AUDIT_LOG` | YES (section 2.2) | CHANGELOG, release_notes |
| `AUTODEV_A2A_ALLOW_PRIVATE_NETWORKS` | YES (section 2.3) | troubleshooting |
| `AUTODEV_A2A_TOKEN` | YES (section 2.3) | a2a_server.md, a2a_http_client.md |
| `FACTORY_FORCE_MOCK` | YES (section 2.1) | quickstart.md, README, faq.md |
| `FACTORY_LOG` | YES (section 2.1) | troubleshooting |
| `FACTORY_CODEX_BIN` | YES (section, via quickstart table) | multi_cli_executor.md |
| `FACTORY_CLAUDE_BIN` | YES (section, via quickstart table) | multi_cli_executor.md |
| `FACTORY_CODEX_CMD` | **NO — NOT in configuration.md** | multi_cli_executor.md only |
| `FACTORY_CLAUDE_CMD` | **NO — NOT in configuration.md** | multi_cli_executor.md only |
| `FACTORY_NET_ALLOW` | **NO — not documented in any user-facing doc** | only in code comments |

### Missing from docs (P2)

- `FACTORY_CODEX_CMD` — used in `config.py` line 73-74 to override `command_template`; documented only in `multi_cli_executor.md`, absent from `configuration.md` env var table.
- `FACTORY_CLAUDE_CMD` — same as above.
- `FACTORY_NET_ALLOW` — set by `network_allowlist.py` and injected into subprocess environments; no user-facing documentation exists.

### Documented but unused

None found — all documented vars have confirmed code usage.

---

## Rubric 3 — CLI Command Coverage

**Result**: PARTIAL

### CLI surface (from src/autodev/cli.py)
35 commands confirmed via `@app.command` decorators:
`run-issue`, `deliver-project`, `classify-input`, `create-prd`, `plan-project`,
`plan-milestones`, `plan-tasks`, `execute-milestone`, `continue-run`, `replay`,
`scan`, `verify`, `release-check`, `report`, `export-delivery`, `push`, `create-pr`,
`fix-bug`, `multi-patch-fix-bug`, `review`, `roundtable`, `mcp-serve`, `a2a-serve`,
`a2a-register`, `a2a-call`, `next`, `design-ux`, `investigate`, `generate-context`,
`document-project`, `sprint-start`, `sprint-status`, `sprint-retro`, `sprint-correct`,
**`dashboard`**

### README "All CLI commands" section (README.md lines 232–267)
Lists **34** commands — `dashboard` is absent.

### Finding

| Issue | Location | Severity |
|-------|----------|----------|
| `dashboard` command exists in CLI but is absent from README "All CLI commands" table | README.md §All CLI commands | P2 |

The `dashboard` command is documented in `troubleshooting.md` (scenario 11: "`autodev dashboard` exits immediately") so it is not completely undocumented, but it is missing from the authoritative command reference table.

No stale/removed commands were found in docs that don't exist in code.

---

## Rubric 4 — Security Boundary Clarity

**Result**: PARTIAL

### SSRF defense for A2A

- `troubleshooting.md` §5: full explanation and warning. PASS.
- `configuration.md` §2.3: env var table documents `AUTODEV_A2A_ALLOW_PRIVATE_NETWORKS`. PASS.
- `docs/a2a.md`: **missing** — no mention of SSRF guard, private network blocking, or the `AUTODEV_A2A_ALLOW_PRIVATE_NETWORKS` escape hatch. Users reading only `a2a.md` for A2A integration guidance will not encounter this security boundary.
- `docs/architecture.md`: **missing** — no mention of SSRF defense in the A2A integration section.
- **Result**: partial (covered in troubleshooting/config; absent from a2a.md and architecture.md).

### Path safety for MCP

- `CHANGELOG.md` (0.1.0a2 section): documents `path_safety.py` addition. PASS.
- `docs/architecture.md` MCP section: **no mention** of `path_safety.py` or which paths are rejected.
- `docs/mcp_server.md`: **no mention** of path safety restrictions.
- **Result**: partial (CHANGELOG has it; primary reference docs do not).

### Branch injection rejection

- `CHANGELOG.md` (0.1.0a2 section): documents 11-pattern branch injection rejection. PASS.
- `docs/architecture.md` executors section: **no mention**.
- `docs/configuration.md`: **no mention**.
- **Result**: partial (CHANGELOG only).

### Secret redaction in logs

- `CHANGELOG.md` (0.1.0a2 section): documents `secret_redaction.py`. PASS.
- `docs/architecture.md`: **no mention**.
- `docs/mcp_server.md`: **no mention**.
- **Result**: partial (CHANGELOG only; architecture and MCP docs are silent).

### Apply-mode double gate

- `configuration.md` §9: full explanation with both conditions documented. PASS.
- `CHANGELOG.md` (0.1.0a2): documents addition. PASS.
- `docs/mcp_server.md`: **no mention** of apply-gate requirement.
- **Result**: partial (config doc has it; mcp_server.md reference is missing it).

### Summary

| Boundary | architecture.md | a2a.md | mcp_server.md | config.md | troubleshooting.md |
|----------|----------------|--------|--------------|-----------|-------------------|
| SSRF | missing | missing | N/A | PASS | PASS |
| Path safety | missing | N/A | missing | missing | missing |
| Branch injection | missing | N/A | N/A | missing | missing |
| Secret redaction | missing | N/A | missing | missing | missing |
| Apply gate | N/A | N/A | missing | PASS | N/A |

**Findings**: `architecture.md` and `mcp_server.md` lack security boundary prose expected of primary reference documents. (P2 — two counts)

---

## Rubric 5 — Alpha Limitations Disclosure

**Result**: PARTIAL

### SLSA L3 not delivered

- `docs/release_notes/v0.1.0a1.md` line 183: states "egress sandboxing, per-caller MCP authentication tokens, signed Docker images, and SBOM generation are not in scope for this release." PASS in release notes.
- `README.md`: **no mention**. Users reading only README have no visibility.
- **Result**: PARTIAL.

### SBOM not delivered

- Release notes: implicit in "not in scope" statement. PASS.
- `README.md`: **absent**. (P2)

### cosign not signed

- Release notes: implicit. `README.md`: **absent**. (included in P2 above)

### MCP per-caller auth not delivered

- `docs/release_notes/v0.1.0a1.md` line 183: explicitly listed as "not in scope". PASS.
- `docs/mcp_server.md`: **no caveat** that per-caller auth is absent. Users integrating via mcp_server.md have no warning.
- `README.md`: **absent**. (P2)

### macOS Apple Dev ID not signed

- Release notes: "macOS `.app` launcher — signed and notarized status of any `.app` wrapper has not been validated for this release." PASS.
- `README.md`: **absent**. (included in P2 above)

### Coverage at 80.5%, not 90%+

- `CHANGELOG.md` (0.1.0a2): documents "Coverage: 79% → 80.5% line+branch". PASS.
- `README.md`: **no coverage disclosure**. (P2)

### Production enterprise blocked

- `docs/release_notes/v0.1.0a1.md` line 183: "Production or enterprise use is not supported". PASS.
- `README.md` §Status: says only "alpha". Does not enumerate specific blockers for enterprise.
- **Result**: PARTIAL.

### README Status block verdict

`README.md` line 21 says: `> **Status**: alpha — v0.1.0-alpha on GitHub Releases.`
This is a one-line disclosure. It does not enumerate: SLSA L3 absent, SBOM absent, cosign absent, MCP per-caller auth absent, coverage 80.5%, enterprise blocked. All of these appear only in `docs/release_notes/v0.1.0a1.md`.

**Finding**: README alpha limitations disclosure is present but incomplete — 6 specific limitations visible only in release notes, not surfaced in README. (P2)

---

## Rubric 6 — Distribution Channels Accurate

**Result**: PARTIAL

### PyPI

- `README.md` line 27: `pip install --pre autodev-ai` — PASS (works for current 0.1.0a3).
- `README.md` line 29: `pip install https://github.com/.../v0.1.0a1/autodev_ai-0.1.0a1-py3-none-any.whl` — **DRIFT**: links to v0.1.0a1 wheel; current version is v0.1.0a3. A user who copies this URL will install an outdated pre-release. (P2)
- `docs/quickstart.md`: same issue not present (quickstart uses source install).

### GitHub Release

- `README.md` line 21: links to `v0.1.0-alpha` tag which was the original pre-tag; current is `v0.1.0a3`.
- However the URL is `releases/tag/v0.1.0-alpha` which redirects to the now-superseded release. The current canonical release is `v0.1.0a3`.
- **DRIFT**: README Install section links to old release tag. (P2 — same finding as PyPI wheel, same fix)

### Docker

- `README.md` lines 43-44: `ghcr.io/merchloubna70-dot/autodev-ai:0.1.0-alpha`.
- Verified by `docs/validation/autodev_post_publish_v0_1_0a3_round.md`: current published Docker image is `:0.1.0a3` (linux/amd64 + linux/arm64).
- **DRIFT**: README Docker tag is `:0.1.0-alpha`; current is `:0.1.0a3`. (P2)

### Homebrew

- `README.md`: **no Homebrew install instruction at all**.
- `docs/release/homebrew_tap_publish_checklist.md` confirms: Homebrew tap `merchloubna70-dot/homebrew-autodev` is PUBLIC and `brew tap merchloubna70-dot/autodev` works.
- `docs/validation/autodev_post_publish_v0_1_0a3_round.md` confirms: `brew info autodev-ai` shows `stable 0.1.0a3`.
- The task rubric states `brew tap merchloubna70-dot/autodev && brew install autodev-ai` is the expected instruction.
- **README does not document Homebrew as an install channel at all**. (P3 — channel exists but absent from README)

### troubleshooting.md §9

- Still says "blocked until PyPI 0.1.0a1 wheel is published" — this is now stale; Homebrew is published. (P2 — stale troubleshooting step)

---

## All Findings

### P2 Findings (7)

| # | Title | Location | Detail |
|---|-------|----------|--------|
| P2-1 | Quickstart clone URL is a placeholder | docs/quickstart.md line 19 | `github.com/your-org/autodev-ai` should be `github.com/merchloubna70-dot/autodev-ai` |
| P2-2 | README Install wheel link points to v0.1.0a1 | README.md line 29 | Shows `v0.1.0a1` wheel URL; current version is `v0.1.0a3` |
| P2-3 | README Docker tag is `:0.1.0-alpha` | README.md lines 43-44 | Current published Docker tag is `:0.1.0a3` |
| P2-4 | `dashboard` command missing from README "All CLI commands" | README.md §All CLI commands | 34 commands listed; CLI has 35; `dashboard` is absent |
| P2-5 | Security boundaries absent from architecture.md and mcp_server.md | docs/architecture.md, docs/mcp_server.md | SSRF, path_safety, branch injection, secret redaction, apply gate — none appear in primary reference docs |
| P2-6 | README alpha limitations incomplete | README.md | SLSA L3 / SBOM / cosign / MCP per-caller auth / coverage 80.5% / enterprise blocked — all absent from README; only in release_notes |
| P2-7 | troubleshooting.md §9 Homebrew section is stale | docs/troubleshooting.md §9 | States Homebrew "blocked until PyPI 0.1.0a1 published"; tap is now live at `brew tap merchloubna70-dot/autodev` |

### P3 Findings (3)

| # | Title | Location | Detail |
|---|-------|----------|--------|
| P3-1 | FACTORY_FORCE_MOCK=1 not in demo command | docs/quickstart.md | Rubric asks for explicit env var in demo; quickstart uses `--allow-mock-executor true` only |
| P3-2 | FACTORY_CODEX_CMD / FACTORY_CLAUDE_CMD absent from configuration.md | docs/configuration.md | Used in config.py; documented in multi_cli_executor.md only; configuration.md env var table is incomplete |
| P3-3 | Homebrew absent from README Install section | README.md §Install | `brew tap merchloubna70-dot/autodev && brew install autodev-ai` is a live channel not mentioned in README |

### P4 Findings (1)

| # | Title | Location | Detail |
|---|-------|----------|--------|
| P4-1 | FACTORY_NET_ALLOW undocumented | docs/ | Set by network_allowlist.py; passed to subprocess envs; no user-facing documentation exists; internal use only |

---

## Rubric Summary Table

| Rubric | Result | Key Issues |
|--------|--------|-----------|
| 1. 10-min quickstart | PARTIAL | Placeholder clone URL (P2); FACTORY_FORCE_MOCK not in demo cmd (P3) |
| 2. Env var coverage | PARTIAL | FACTORY_CODEX_CMD/CLAUDE_CMD absent from config.md (P3); FACTORY_NET_ALLOW undocumented (P4) |
| 3. CLI command coverage | PARTIAL | `dashboard` missing from README command table (P2) |
| 4. Security boundary clarity | PARTIAL | architecture.md and mcp_server.md lack SSRF/path_safety/branch_inject/redact prose (P2) |
| 5. Alpha limitations disclosure | PARTIAL | README status block is minimal; 6 specific limitations only in release_notes (P2) |
| 6. Distribution channels | PARTIAL | README wheel link stale (P2); Docker tag stale (P2); Homebrew absent from README (P3); troubleshooting §9 stale (P2) |

---

## Evidence Files Consulted

- `/Users/macworkers/autodev/README.md`
- `/Users/macworkers/autodev/CHANGELOG.md`
- `/Users/macworkers/autodev/docs/quickstart.md`
- `/Users/macworkers/autodev/docs/configuration.md`
- `/Users/macworkers/autodev/docs/architecture.md`
- `/Users/macworkers/autodev/docs/troubleshooting.md`
- `/Users/macworkers/autodev/docs/faq.md`
- `/Users/macworkers/autodev/docs/a2a.md`
- `/Users/macworkers/autodev/docs/a2a_server.md`
- `/Users/macworkers/autodev/docs/a2a_http_client.md`
- `/Users/macworkers/autodev/docs/mcp_server.md`
- `/Users/macworkers/autodev/docs/multi_cli_executor.md`
- `/Users/macworkers/autodev/docs/project_delivery.md`
- `/Users/macworkers/autodev/docs/quality_gate.md`
- `/Users/macworkers/autodev/docs/release_notes/v0.1.0a1.md`
- `/Users/macworkers/autodev/docs/release/homebrew_tap_publish_checklist.md`
- `/Users/macworkers/autodev/docs/release/pypi_0_1_0a1_publish_checklist.md`
- `/Users/macworkers/autodev/docs/validation/autodev_post_publish_v0_1_0a3_round.md`
- `/Users/macworkers/autodev/docs/validation/round7_cli_surface_contract_report.md`
- `/Users/macworkers/autodev/src/autodev/cli.py` (command surface, grep only)
- `/Users/macworkers/autodev/src/autodev/config.py` (env var grep)
- `/Users/macworkers/autodev/src/autodev/executors/network_allowlist.py` (env var grep)

---

## Greps Run

```bash
grep -rohE 'AUTODEV_[A-Z_]+' src/autodev/ | sort -u
# → AUTODEV_A2A_ALLOW_PRIVATE_NETWORKS AUTODEV_A2A_TOKEN AUTODEV_MCP_ALLOW_APPLY AUTODEV_MCP_AUDIT_LOG

grep -rohE 'FACTORY_[A-Z_]+' src/autodev/ | sort -u
# → FACTORY_CLAUDE_BIN FACTORY_CLAUDE_CMD FACTORY_CODEX_BIN FACTORY_CODEX_CMD FACTORY_FORCE_MOCK FACTORY_LOG FACTORY_NET_ALLOW

grep '@app.command' src/autodev/cli.py | grep -oE '"[^"]+"' | tr -d '"'
# → 35 commands, including dashboard
```
