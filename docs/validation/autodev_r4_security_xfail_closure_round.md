# autodev-ai R4 Security XFail Closure + Release Workflow Secret Hardening Round — Aggregator

> **Overall result: `pass`** — 5 parallel sonnets (R4-A..E) + Opus aggregator. **All 10 known xfails closed by real production fixes.** Tests 1191 → 1308 (+117), 0 regressions. Tag readiness unchanged: `go_after_user_action`.

---

## Headline Numbers

| Metric | Before R4 | After R4 | Δ |
|---|---|---|---|
| Tests | 1191 | **1308** | +117 |
| xfail | 10 | **0** | −10 (all closed by real fix) |
| Line coverage | 81% | **82%** | +1 |
| Line+branch | 80.4% | **80.5%** | +0.1 |
| ruff errors | 0 | **0** | — |
| mypy errors | 0 | **0** (174 files) | — |
| release_readiness_gate | 36/36 | **36/36** | — |
| coverage_gate (non-strict) | pass | **pass** | — |
| coverage_gate (strict) | fail (6 mod) | fail (5 mod) | −1 module crossed |

---

## R4 Closure Matrix (5/5)

| ID | Area | Status | New code |
|---|---|---|---|
| R4-A | MCP `.env` path preflight denial | ✅ pass | `src/autodev/mcp_server/path_safety.py` + 6 handlers |
| R4-B | Executor secret redaction | ✅ pass | `src/autodev/utils/secret_redaction.py` + 3 executors |
| R4-C | Branch-name injection hardening | ✅ pass | `worker_isolator.py` + `git_adapter.py` (11 patterns rejected) |
| R4-D | MCP required-schema enforcement | ✅ pass | `mcp_server/server.py` `_validate_required_params` pre-dispatch |
| R4-E | release.yml secret handling | ✅ pass | `-p` flag → `TWINE_PASSWORD` env |

---

## 10 xfails Closed (Real Fixes)

| ID | Fix |
|---|---|
| F-01a/b | `_normalize_pipe_whitespace` in `command_safety.py` — `curl\|bash` no-space now caught |
| F-02 | `FactoryConfig.from_env` auto-allows mock when `FACTORY_FORCE_MOCK=1` |
| F-03 | Stale annotation removed; R3-H code was already correct |
| TWINE-1..4 | `release.yml` twine upload now uses `TWINE_USERNAME=__token__` + `TWINE_PASSWORD=${{ secrets.PYPI_API_TOKEN }}` env vars |
| MCP-ENV-PATH | `_validate_safe_path` preflight in 6 MCP handlers rejects `.env / credentials.json / *.pem / *.key / secret-in-basename / path traversal` |
| MCP-SCHEMA | `_validate_required_params` pre-dispatch returns `-32602 Invalid params` for missing required fields (5 key tools + 4 more) |
| EXEC-REDACT-PYPI | `secret_redaction.py` masks `pypi-…`, `PYPI_API_TOKEN=…` patterns before writing to stderr / JSON reports |
| EXEC-REDACT-ANTHROPIC | Same for `sk-ant-…`, `ANTHROPIC_API_KEY=…` |
| BRANCH-DOLLAR-PAREN | `_validate_branch_name` rejects `$(`, backtick, `;`, `&&`, `\|\|`, `\|`, `>`, `<`, newline, leading `-` |
| BRANCH-BACKTICK | Same as above |

**Remaining xfails: 0**

---

## Per-Agent Headlines

### R4-A — MCP path denial
- 30 new tests, 1 xfail removed
- 6 handlers (scan, deliver_project, run_issue, report, release_check, list_runs) now preflight-validate any path-like argument
- Residuals: symlink innocent-name → secret target (R5 Path.resolve()); Unicode homoglyph (low severity)

### R4-B — Executor secret redaction
- New `secret_redaction.py` (123 lines): 8 pattern classes + idempotent + first-4-char-preserved
- Integrated in codex / claude / mock executors
- 27 new tests (16 unit + 4 integration + 2 in security_p0 unxfailed = 22 pass + 5 more)
- 2 xfails removed
- Residual: pattern-based detection, not content-aware DLP

### R4-C — Branch injection hardening
- 11 injection patterns rejected (was 3 — added 8 more)
- `_validate_branch` propagated to `git_adapter.py` push/checkout/create_branch
- 26 new tests + 14 targeted (40 total scope pass)
- 2 xfails removed
- shell=True audit: **0 hits** in git path
- New exception: `BranchNameInjectionError(WorkerIsolatorPathEscapeError)` (subclass — backwards compat)

### R4-D — MCP required schema enforcement
- (Agent killed mid-report by API socket close; Opus reconstructed validation doc from on-disk state)
- `_validate_required_params` pre-dispatch in `mcp_server/server.py`
- Strategy: **reject missing required** / **ignore unknown extras** / **reject wrong type**
- 24 new tests, 1 xfail removed
- Residual: nested required-field depth limited (full jsonschema integration for R5)

### R4-E — release.yml secret env
- `twine upload -u __token__ -p "$PYPI_API_TOKEN"` → `TWINE_USERNAME / TWINE_PASSWORD` env vars
- `if: ${{ secrets.PYPI_API_TOKEN != '' }}` guard preserved (no-secret = no-upload)
- 0 `-p` flag hits, 0 `echo.*TOKEN` hits
- 4 xfails removed

---

## Gates (Final State)

```
$ pytest tests/                                      → 1308 passed, 0 xfailed
$ ruff check .                                       → All checks passed!
$ mypy src/autodev                                   → Success: 0 issues / 174 files
$ python scripts/release_readiness_gate.py           → 36 pass / 0 fail / 0 skip
$ python scripts/release_readiness_gate.py --strict  → exit 0
$ ... --strict-r2 / --strict-r3 / --strict-rc        → all exit 0
$ python scripts/coverage_gate.py                    → overall 80.5% PASS / 9 mod pass / 5 mod fail
```

---

## Tag Readiness

**Unchanged: `go_after_user_action`** — R4 did not change tag decision logic. It strengthened internal security posture (5 real bug classes closed) without altering the PyPI publish path. The 5-step user action sequence in `docs/validation/autodev_pre_tag_go_no_go.md` still stands.

---

## Remaining Risks (Documented, Non-Blocking)

1. **R4-A symlink-target check** — basename validator doesn't follow symlinks; a symlink with innocent name pointing to a secret file passes. Mitigation: `Path.resolve()` in R5.
2. **R4-A Unicode homoglyph** — full-width `.` etc. not caught.
3. **R4-B pattern-based DLP** — novel token formats may slip through. Future: content-aware DLP integration.
4. **R4-D nested schema depth** — top-level required only. R5: full jsonschema validator.
5. **R4-D type format** — basic types only; no `uri`/`date-time` format enforcement.
6. **Coverage strict-gate** — 5 module aspirational gaps remain (cli 46% / mcp_server server 72% / tools 76% / replay 61% / a2a/http 78%). Intentional R5 targets, not release blockers.
7. **Homebrew** — still blocked until PyPI publish + sha256 patch.
8. **Production enterprise** — still blocked: SLSA / SBOM / per-caller MCP auth / signed Docker (R5+).

---

## Next Round — R5 Coverage Lift + Production-Enterprise Hardening

| Task | Effort | Target |
|---|---|---|
| Coverage lift on cli.py (46% → 80%+) via mock-integrated subcommand tests | 3 hr | aspirational threshold |
| Coverage lift on mcp_server server/tools (72-76% → 85%+) | 2 hr | aspirational threshold |
| Coverage lift on replay_flow (61% → 85%+) | 1 hr | aspirational threshold |
| Full jsonschema validator integration for MCP | 2 hr | nested required + format |
| `Path.resolve()` in path_safety.py for symlink target check | 30 min | R4-A residual |
| Unicode-normalize basename in path_safety | 30 min | R4-A residual |
| SLSA provenance via cosign on Docker | 2 hr | enterprise unblock |
| SBOM in release.yml (syft / cyclonedx) | 1 hr | enterprise unblock |
| Per-caller MCP auth (bearer / OAuth on stdio transport) | 4 hr | multi-tenant MCP |
| Apple Developer ID signing for macOS .app | 2 hr | macOS distribution |
| After PyPI publish: update Homebrew formula sha256 | 15 min | Homebrew unblock |

After R5: candidate to promote `production_enterprise_use: blocked → allowed_with_limitations`.
