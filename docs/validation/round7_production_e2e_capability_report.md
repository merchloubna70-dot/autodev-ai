# R7 — Production E2E Capability Validation Round (Final Synthesis)

> **Verdict: `AlphaProductionCapable`**
> autodev-ai v0.1.0a3 is **honestly usable as an alpha** for its documented core (CrewAI-orchestrated software factory with mock pipeline + audit trail + 4-channel distribution). However, **one P0 finding** breaks the documented "resume paused pipeline" feature: `continue-run` is a stub. Combined with 9 P1 findings (mostly graceful-error-handling and 2 narrow security denylist gaps) and 23 P2 findings (docs drift, package hygiene, deterministic-replay), this round recommends **R8 = Production Fix Round** before promoting to beta.

---

## 1. Round Header

| | |
|---|---|
| Round | R7 Production E2E Capability Validation |
| Date | 2026-05-14 |
| Project | autodev-ai @ /Users/macworkers/autodev |
| Version under test | 0.1.0a3 (alpha, PyPI + GitHub Release + Docker + Homebrew all live) |
| Git HEAD | 0a227d4 on main, clean tree |
| Methodology | 12 parallel sonnet agents → Opus synthesis (read-only) |
| Scope | Production capability — not just unit tests passing |
| Total evidence files | 25 (12 md + 12 json + 1 txt) under `docs/validation/round7_*` |

---

## 2. Overall Verdict

**`AlphaProductionCapable`** — chosen over the other three options because:

| Verdict considered | Why not |
|---|---|
| ProductionReady | 1 P0 (continue-run stub) blocks "production durability" claim |
| ProductionReadyWithLimitations | Same — a documented feature being a no-op is not a "limitation" in the well-disclosed sense |
| **AlphaProductionCapable** ← **chosen** | Core mock-first pipeline + security boundaries + distribution all work; resume feature broken but **clearly an alpha-stage gap**, not a foundational defect |
| NotProductionReady | Too harsh — install / CLI surface / mock pipeline / brownfield / A2A / MCP / security 85%+ of capabilities pass |

---

## 3. Capability Matrix (14 dimensions)

| # | Capability | Rating | Evidence |
|---|---|---|---|
| 1 | **Installability** | `pass_with_limitations` | 2/2 venv smokes pass; PyPI 0.1.0a3 verified; one P1 = host Python 3.12.13 pyexpat ABI mismatch (macOS-only, fixed by `brew reinstall python@3.12`) |
| 2 | **CLI Surface Stability** | `pass_with_limitations` | **35/35 commands** load, all help works, 0 import crashes; P2 = every invocation emits 2 pydantic `protected_namespaces` warnings |
| 3 | **Mock E2E Pipeline** | `pass_with_limitations` | 8/8 scenarios (A-H) exit 0; full 8-subdir audit tree generated (44 artifacts/run); P2 = `--project-brief` requires a file path, not inline string |
| 4 | **State Recovery** | `fail` ← **P0** | `continue-run` is a STUB at `cli.py:332-341` — only echoes remaining milestone IDs, no actual execution. Documented feature broken. |
| 5 | **Replayability** | `partial` | replay exits 0 but is **non-deterministic** (regenerates content) AND **mutates originals in-place** (no snapshot). 2× P2. |
| 6 | **Executor Boundary** | `pass_with_limitations` | 0 Agent→subprocess bypasses, 0 `os.system`/`shell=True` real uses, all 10 branch-injection attacks rejected. P1 = `command_safety` denylist uses literal substring match (`curl URL \| bash` slips through denylist but fail-closed allowlist catches it). |
| 7 | **Security Abuse Resistance** | `partial` | **38/40 attacks rejected**. P1 = `path_safety` permits absolute `/etc/passwd` (no `..` check). P1 = `id_rsa` (no extension) bypasses MCP secret-path block. SSRF 10/10 OK, secret-redaction 9/9 OK. |
| 8 | **A2A Protocol Readiness** | `pass_with_limitations` | Bearer auth 401/401/200 verified; SSRF deny (`A2AHttpSSRFError`) on 127.0.0.1 + 10.x + 169.254.x. P3 = `--port 0` ephemeral not supported. |
| 9 | **MCP Protocol Readiness** | `pass_with_limitations` | 9/9 MCP tools present with `inputSchema`; path_safety 14/14 deny; apply-mode 4/4 gate cases correct. P2 = same protected_namespaces warning. |
| 10 | **Release Packaging** | `pass_with_limitations` | Wheel (320KB) + sdist (839KB) build, twine PASSED both; install smokes both pass. P2 (×3) = stale `dist/autodev_ai-0.1.0a2-py3-none-any.whl` in main repo / `Info.plist` still at 0.1.0a1 / Docker target name drift. |
| 11 | **CI Parity** | `pass_with_limitations` | 1290/1295 local tests pass (5 fail = host pyexpat issue, not code); ruff+mypy 0 errors; `twine check` PASSED. **P1 (×2)** = coverage_gate.py exists but no CI workflow invokes it; `pytest.mark.integration` unregistered (warnings on every CI run). |
| 12 | **Brownfield Handling** | `pass_with_limitations` | 6/6 scenarios pass; **source files NOT mutated outside `.dev-factory/`** ✓; full audit tree ✓; final report references correct bug. P2 = `investigate` greps from process CWD, not `--repo-path` (evidence came from autodev repo's `.venv`, not brownfield). |
| 13 | **Operator Documentation** | `partial` | 7 P2 docs-drift findings: README wheel link → v0.1.0a1 (should be a3), Docker tag stale (`:0.1.0-alpha`), `dashboard` missing from README CLI table, security boundaries absent from architecture.md/mcp_server.md, alpha limitations thin, quickstart placeholder `your-org` not replaced, troubleshooting Homebrew step still says "blocked". |
| 14 | **Observability / Auditability** | `pass` | Every run writes 8-subdir audit tree under `.dev-factory/runs/<run_id>/`; secret redaction validated on 9/9 patterns; A2A audit log via HMAC; MCP audit via `AUTODEV_MCP_AUDIT_LOG`. |

**Rating distribution**: `pass` ×1 / `pass_with_limitations` ×10 / `partial` ×2 / `fail` ×1.

---

## 4. Finding Severity Summary

| Severity | Count | Definition |
|---|---|---|
| **P0** — blocks production | **1** | continue-run stub (Agent 5) |
| **P1** — blocks public alpha | **9** | 3× continue-run/replay graceful error handling, 2× security denylist gaps (path absolute, id_rsa, curl-pipe), 2× CI parity (coverage gate not enforced, pytest marker unregistered), 1× host env (pyexpat), 1× SSRF allowlist defaults |
| **P2** — affects reliability | **23** | Docs drift (7), pydantic warnings (3), package hygiene (3), replay determinism (2), CLI UX (3), assorted (5) |
| **P3** — UX / polish | **6** | error message friendliness, port 0 support, env var documentation |
| **P4** — backlog | **1** | FACTORY_NET_ALLOW undocumented |

---

## 5. P0/P1 Detailed Roster

### P0 (1)

| ID | Title | File:Line | Owner agent |
|---|---|---|---|
| P0-01 | `continue-run` is a non-functional stub | `src/autodev/cli.py:332-341` | A5 continue_replay |

### P1 (9)

| ID | Title | Owner agent | Fix scope |
|---|---|---|---|
| P1-01 | Missing run_id surfaces raw `FileNotFoundError` traceback | A5 | CLI exception handler (~10 LoC) |
| P1-02 | Corrupted run_state.json surfaces raw `JSONDecodeError` traceback | A5 | CLI exception handler (~10 LoC) |
| P1-03 | Invalid enum field surfaces raw Pydantic `ValidationError` traceback | A5 | CLI exception handler (~15 LoC) |
| P1-04 | `command_safety` denylist literal-substring miss (`curl URL \| bash`) | A6 / A7 | regex-ify denylist (~20 LoC) — fail-closed allowlist masks but denylist is dead |
| P1-05 | `path_safety` permits absolute paths like `/etc/passwd` | A7 | add `Path.is_absolute()` reject (~5 LoC) |
| P1-06 | SSH key names without extension (`id_rsa`) not in MCP secret-path block | A7 | extend `_EXACT_REJECT` (~5 LoC) |
| P1-07 | `coverage_gate.py` exists but no CI workflow invokes it — coverage thresholds (80/85/90) entirely manual | A10 | add coverage gate step to `.github/workflows/lint.yml` (~10 LoC) |
| P1-08 | `pytest.mark.integration` not registered → `PytestUnknownMarkWarning` on every CI run | A10 | add to `pyproject.toml [tool.pytest.ini_options].markers` (~2 LoC) |
| P1-09 | Host Python 3.12.13 pyexpat ABI mismatch on this Mac (CI ubuntu unaffected) | A2 / A10 | **host-environment, no code fix** — instruct user to `brew reinstall python@3.12` |

P1-09 is a host-only issue. The other 8 are code/config fixes.

---

## 6. Command-Run Aggregate

(Aggregated across 12 agents' `commands_run` arrays.)

| Bucket | Count |
|---|---|
| Total commands executed | ~210 |
| Exit 0 (pass) | ~180 (≈ 86%) |
| Non-zero exit (failure or expected-rejection) | ~30 |
| Skipped (environment: no docker buildx multi-arch, etc.) | ~5 |

Note: "Non-zero exit" includes intentional rejection tests (e.g., security abuse tests where rejection = success). Of the ~30 non-zero exits, only Agent 5's 4 error scenarios + Agent 5's continue-run stub are true regressions. The rest are by-design.

---

## 7. R8 Recommendation

**Next round: `R8 Production Fix Round`** — NOT a release-candidate validation. Reasons:

1. P0 must be closed before any beta promotion (continue-run is documented; users will hit it)
2. P1×8 code/config fixes are mostly tiny (under 100 LoC total)
3. After R8 fixes land, run **R9 = Release Candidate Validation** (re-run R7 matrix to confirm green) before considering 0.1.0b1 or 0.2.0

### Suggested R8 minimum fix list (priority order)

| # | Fix | Files | LoC est | Hours |
|---|---|---|---|---|
| 1 | continue-run real implementation (call milestone_flow for remaining milestones) | `cli.py`, `flows/milestone_flow.py` | ~80 | 2-3 h |
| 2 | CLI exception wrapper (`@catch_friendly` decorator for FileNotFound / JSONDecodeError / ValidationError) | `cli.py`, new `utils/cli_errors.py` | ~60 | 1 h |
| 3 | `command_safety` denylist → regex (`curl\s+.*\|\s*ba?sh`) | `utils/command_safety.py` | ~30 | 30 min |
| 4 | `path_safety` absolute-path reject + SSH key names | `mcp_server/path_safety.py` | ~15 | 20 min |
| 5 | Coverage gate in lint.yml | `.github/workflows/lint.yml`, `scripts/coverage_gate.py` | ~20 | 30 min |
| 6 | Register `pytest.mark.integration` | `pyproject.toml` | ~3 | 5 min |
| 7 | Replay snapshot-then-execute (write artifacts to runs/<id>/replays/<ts>/ instead of overwriting) | `flows/replay_flow.py` | ~50 | 1-2 h |
| 8 | Suppress pydantic `protected_namespaces` warnings | `schemas.py` | ~5 | 10 min |
| 9 | Docs drift fixes (README wheel link, Docker tag, dashboard, security boundaries, Homebrew install, alpha limitations) | `README.md`, `docs/*.md` | ~150 | 2 h |
| 10 | Clean stale `dist/` + update `.app/Info.plist` to 0.1.0a3 | `dist/`, `packaging/desktop/` | minor | 15 min |
| **Total** | | | **~410 LoC** | **~8-10 h** |

No P0/P1 from R7 should be left for R9. P2/P3/P4 can be bundled or deferred at discretion.

---

## 8. What Did NOT Fail

To balance the picture, here's what works well — these are the alpha's load-bearing capabilities and they all checked out:

- **35/35 CLI commands** load and produce help text without crash
- **Mock pipeline end-to-end** in 8 scenarios produces full audit tree under `.dev-factory/runs/<run_id>/` with 44 artifacts
- **0 Agent→subprocess bypasses of ExecutorRouter** — the architecture's central invariant holds
- **Brownfield repo handling** keeps source files untouched in mock mode (verified by `find -newer`)
- **All 4 distribution channels live and installable**: PyPI / GitHub Release / Docker (amd64+arm64) / Homebrew tap
- **MCP apply-mode double gate**: 4/4 combinations correct (only `allow_apply=true` + `AUTODEV_MCP_ALLOW_APPLY=1` permits)
- **A2A bearer auth**: 401/401/200 verified on no-token / wrong-token / right-token
- **SSRF defense**: 10/10 (127.0.0.1, localhost, 169.254.169.254, RFC-1918, ::1, 0.0.0.0)
- **Branch-injection rejection**: 10/10 (`$()`, `;`, backtick, `&&`, `|`, redirects, newline, leading dash)
- **Secret redaction**: 9/9 patterns (Anthropic/OpenAI/GitHub/Slack/PyPI tokens, PEM blocks)
- **MCP path safety**: 14/14 secret/traversal paths denied
- **Wheel + sdist** both build cleanly, `twine check` PASSED, install smoke produces `autodev-ai 0.1.0a3`
- **CI parity**: 1290 tests pass locally with same toolchain as CI (excluding host pyexpat issue)

---

## 9. Evidence Files

See companion file `round7_production_e2e_capability_evidence_index.md` for the full per-agent file listing with summaries.

---

## 10. Quality Red Lines Upheld (This Round)

- ❌ **Did NOT modify any source code** (only synthesis report files written)
- ❌ **Did NOT commit or push anything** (no git changes)
- ❌ **Did NOT touch PyPI / GitHub Release / Docker / Homebrew** publish artifacts
- ❌ **Did NOT read or print real secrets** (PYPI_API_TOKEN, ANTHROPIC_API_KEY, OPENAI_API_KEY, GITHUB_TOKEN)
- ❌ **Did NOT auto-fix** any P0/P1 finding — produced repair plan instead per user red line
- ❌ **Did NOT execute** any dangerous attack — security tests verified rejection without actual harm; canary `/tmp/r7-security-sandbox/rmtest-A2` confirmed intact
- ❌ **Did NOT skip** test categories — all 14 capability dimensions evaluated
- ❌ **Did NOT inflate** the verdict — chose `AlphaProductionCapable` over the more flattering `ProductionReadyWithLimitations`
