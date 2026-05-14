# Changelog

All notable changes to this project will be documented in this file.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

<<<<<<< HEAD
### Added

- SBOM workflow (CycloneDX + SPDX on tag push) — `.github/workflows/sbom.yml`
  generates `sbom.cdx.json` (CycloneDX 1.5) and `sbom.spdx.json` (SPDX 2.3)
  via `anchore/sbom-action` and attaches both as GitHub Release assets on every
  `v*.*.*` tag push and on manual dispatch. Supports EU CRA / US EO 14028
  compliance toolchains (grype, trivy, syft).

||||||| parent of 52f2bfd (r6(cosign): keyless container image signing via Sigstore)
=======
### Added

- cosign keyless image signing (Sigstore) on every tag push — `ghcr.io/merchloubna70-dot/autodev-ai` images now carry detached Fulcio OIDC signatures recorded in the Rekor transparency log; see `docs/release/cosign_verification.md`.

>>>>>>> 52f2bfd (r6(cosign): keyless container image signing via Sigstore)
---

## [0.1.0a3] — 2026-05-14 (Pre-Release)

### Fixed

- **typer dependency warning** — pyproject `typer[all]>=0.9` → `typer>=0.12` +
  explicit `shellingham>=1.5`. Eliminates the
  `WARNING: typer 0.25.1 does not provide the extra 'all'` from
  `pip install` (typer dropped the `[all]` extra in ~0.12; rich+shellingham
  are now bundled directly).
- **`python -m autodev.release_readiness_gate` broken from PyPI install** —
  refactored shim. `src/autodev/release_readiness_gate.py` now contains the
  full 1375-LoC implementation (was a 25-LoC `spec.loader.exec_module` shim
  that failed because `scripts/` is not shipped in the wheel).
  `scripts/release_readiness_gate.py` is now a 10-LoC delegation wrapper
  that imports from the package. Single source of truth.

### Added

- `packaging/homebrew/tap/` — staging directory mirroring the canonical
  formula. Ready for tap publish via
  `docs/release/homebrew_tap_publish_checklist.md` 4-step procedure.
- `docs/release/homebrew_tap_publish_checklist.md` — user procedure for
  creating `merchloubna70-dot/homebrew-autodev` tap repo + push.
- `docs/release/pypi_token_rotation_checklist.md` — 4-step PyPI token
  rotation procedure (recommended after publish flow).
- `tests/integration/test_release_readiness_gate_installed_wheel.py` —
  verifies the module-form gate works from a fresh wheel install.

### Internal

- Test count: 1308 → 1312 (+4 wheel-install integration tests).
- 9 Homebrew transitive resource sha256s independently re-verified
  (pydantic / typer / rich / pyyaml / jinja2 / click / mdurl /
  markdown-it-py / pygments / shellingham — all match).
- 8 stale R2-G/R3-F Homebrew tests EVOLVED to state-aware semantics
  (accept pre-publish OR post-publish state with internal consistency check).
  Test count preserved; behavior tightened.
- gate check `r3_homebrew_publish_time_blocker_clean` accepts both
  pre-publish (placeholder + BLOCKED) and post-publish (real sha256 +
  PyPI url + Backfilled comment) states.

---

## [0.1.0a2] — 2026-05-14 (Pre-Release, first real PyPI publish)

### Fixed
- 5 pre-publish CI blockers discovered and fixed during v0.1.0a1 tag push:
  1. `release.yml` step-level `secrets.if` rejected by GitHub Actions schema
     (split into detector step writing `$GITHUB_OUTPUT` + upload gating on output)
  2. `tomllib` import broke py3.10 collection in R2-AB tests
     (added `sys.version_info` check + `tomli` fallback + `tomli` dev dep)
  3. `test_wheel_cli_version_smoke.py` required pre-built `dist/`
     (added `skip_if_no_dist` marker to all 6 tests)
  4. `mypy` missing from `[project.optional-dependencies].dev`
     (added `mypy>=1.5` to dev extras)
  5. `Dockerfile` hardcoded old version `dist/autodev_ai-0.1.0-*.whl`
     (changed to glob `dist/autodev_ai-*.whl`)

### Added
- Security R4: `secret_redaction.py` masks pypi/anthropic/openai/github/slack
  tokens + PEM blocks in executor stdout/stderr/logs (idempotent, preserves
  first 4 chars for debuggability)
- Security R4: MCP `path_safety.py` preflight validator rejects `.env`,
  `credentials.json`, `*.pem`, `*.key`, secret-in-basename, path traversal
  in 6 MCP handlers (scan / deliver_project / run_issue / report /
  release_check / list_runs)
- Security R4: branch-name injection rejection (11 patterns: `$()`, backtick,
  `;`, `&&`, `||`, `|`, `>`, `<`, newline, leading `-`, whitespace) in
  `worker_isolator` + propagated to `git_adapter` push/checkout/create_branch
- Security R4: MCP `_validate_required_params` pre-dispatch JSON-Schema check
  (returns `-32602 Invalid params` if required field missing)
- R3: `AUTODEV_MCP_ALLOW_APPLY` and `AUTODEV_MCP_AUDIT_LOG` env vars
- `docs/configuration.md` — environment + TOML reference
- `docs/troubleshooting.md` — 12-scenario guide
- `CHANGELOG.md` — this file
- `scripts/coverage_gate.py` — 3-threshold coverage gate (overall 80 /
  release 85 / security 90)

### Removed
- All 10 `pytest.mark.xfail(strict=True)` markers — each closed by a real
  code fix (not annotation-only). See
  `docs/validation/autodev_r4_xfail_ledger.{md,json}`.

### Internal
- Tests: 1062 → 1308 (+246 over 4 hardening rounds)
- Coverage: 79% → 80.5% line+branch
- 5 release-readiness rounds documented:
  R1 release hardening · R2 PyPI blocker closure · R3 PyPI RC final
  hardening · RC publish prep · R4 security xfail closure

---

## [0.1.0a1] — 2026-05-14 (Pre-Release, superseded by 0.1.0a2)

### Added

#### Core agent pipeline
- CrewAI multi-agent base: 12-agent graph from `InputClassifier` through
  `ReleaseManager` covering PRD, architecture, milestones, tasks, quality gates,
  security review, verification, and doc writing.
- Full audit-trail artifact tree written under
  `<repo>/.dev-factory/runs/<run_id>/` (input / product / architecture /
  planning / execution / quality / verification / delivery).
- Run state machine: `draft → running → paused → done | failed`; runs are
  resumable (`continue-run`) and replayable (`replay`).

#### Multi-CLI executor router
- `ExecutorRouter` — the single entry point for all CLI traffic; routes tasks
  to Codex CLI, Claude Code CLI, or mock executor based on task type, risk
  level, and file count.
- `CodexCliExecutor` — wraps `codex` binary, passes SAFETY BOUNDARY prompt,
  parses JSONL `--json` output into `CodexInnerStep` records.
- `ClaudeCodeExecutor` — wraps `claude` binary for architecture, security,
  long-context refactors, release roll-ups.
- `MockExecutor` / `MockCodexExecutor` — deterministic stand-ins that produce
  realistic artifacts without API keys; engaged automatically when both CLIs are
  absent or via `--allow-mock-executor true`.
- Executor selection: `--executor codex|claude|auto|mock`; `auto` (default)
  picks the best CLI per task type.

#### A2A protocol and roundtable
- A2A HTTP transport with SSRF guard: blocks RFC-1918 / loopback addresses by
  default; override with `AUTODEV_A2A_ALLOW_PRIVATE_NETWORKS=1` (test-only).
- Bearer-auth via `AUTODEV_A2A_TOKEN` environment variable.
- `AgentRoster` with persistent JSON file at `~/.autodev/a2a-roster.json`.
- `autodev a2a-serve` — JSON-RPC 2.0 HTTP server accepting tasks from external
  agents on a configurable port.
- `autodev a2a-register` / `autodev a2a-call` — register a remote card and
  dispatch tasks.
- `autodev roundtable` (party mode) — recruit N specialist agents by skill,
  collect independent analyses, synthesize into a consensus report.

#### MCP server (9 tools)
- `autodev mcp-serve` — JSON-RPC 2.0 MCP server over stdio; compatible with
  Claude Desktop and Claude Code.
- Tools: `scan`, `classify_input`, `create_prd`, `deliver_project`,
  `run_issue`, `report`, `roundtable`, `release_check`, `list_runs`.
- Apply-mode gate: `mode=apply` requires both `allow_apply=true` in the request
  **and** `AUTODEV_MCP_ALLOW_APPLY=1` in the server environment.
- Audit log: every tool invocation appended to `AUTODEV_MCP_AUDIT_LOG` file
  when the env var is set.

#### BMAD sprint mode
- `autodev sprint-start` / `sprint-status` / `sprint-retro` / `sprint-correct`
  — open, monitor, close, and course-correct multi-week sprints.
- BMAD-Sally UX workflow via `autodev design-ux`.

#### Configuration
- `ConfigStack` — 4-layer TOML deep-merge: user-global →
  project-team → project-user → runtime; array-of-tables merging by `code/id`
  key.
- `FACTORY_FORCE_MOCK=1` — forces deterministic mock across all executors and
  agents.
- `FACTORY_LOG` — sets log level (default `INFO`).

#### CLI surface
- 35 CLI subcommands via Typer; every command is fully documented with
  `--help`.
- Shell safety: blocks `rm -rf`, `sudo`, `cat .env`, `curl | bash`, etc. in all
  executor modes.

#### R1 audit + R2 P0 hardening
- R1 documentation audit: identified CHANGELOG, configuration, and
  troubleshooting as missing docs; recorded in
  `docs/validation/autodev_documentation_onboarding_audit.md`.
- R2 P0 closure: SSRF guard on A2A HTTP transport; HMAC-signed MCP audit log
  entries; `AUTODEV_A2A_ALLOW_PRIVATE_NETWORKS` env var; recorded in
  `docs/validation/autodev_r2_*`.

### Notes
- PyPI not yet published; install from the GitHub Release wheel or source.
  See [README § Install](README.md#install).
- `pip install --upgrade autodev-ai==0.1.0a1` requires the `--pre` flag
  because `0.1.0a1` is a pre-release version marker.
- Homebrew tap formula is blocked until the PyPI `0.1.0a1` sha256 is available
  after the first `twine upload`.
- Docker image `ghcr.io/merchloubna70-dot/autodev-ai:0.1.0-alpha` ships Codex
  CLI and Claude Code CLI pre-installed; ~2 GB compressed.

[Unreleased]: https://github.com/merchloubna70-dot/autodev-ai/compare/v0.1.0-alpha...HEAD
[0.1.0a1]: https://github.com/merchloubna70-dot/autodev-ai/releases/tag/v0.1.0-alpha
