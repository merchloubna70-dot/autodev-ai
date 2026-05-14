# Coverage Gap Prioritization — Cov-F

**Round:** coverage_gap_prioritization
**Date:** 2026-05-14
**Agent:** Cov-F (Prioritizer)
**Baseline:** 1062 passing / 0 failing / 4 xfail / 81% coverage (10884 stmt, 2054 missed)

---

## Sibling Reports Status

None of the five expected sibling reports (Cov-A through Cov-E) were present at dispatch time. This report was derived directly from:
- `autodev_full_audit_quality_ci.json` (PreTag-H) — baseline coverage
- `autodev_full_pre_tag_audit_round.json` + `autodev_pre_tag_go_no_go.json` — release criticality
- `autodev_full_audit_security.json` (PreTag-I) — security surface
- `autodev_full_audit_a2a.json` + `autodev_r2_a2a_http_ssrf_hardening.json` + `autodev_r3_a2a_dns_rebinding_hardening.json` — protocol coverage
- `autodev_full_audit_flow_agent_coverage.json` (PreTag-G) + `autodev_full_audit_executor_isolation.json` (PreTag-F) — flow/agent/executor gaps
- `autodev_r3_mcp_apply_guardrail.json` + `autodev_r3_worker_isolator_symlink_hardening.json` — hardening closure

---

## P0 Gaps (5) — Release-Critical or Security-Critical

| # | Area | Gap | Recommended Test | Est. New Tests | Coverage Delta |
|---|------|-----|-----------------|---------------|---------------|
| 1 | WorkerIsolator F-03 stale xfail | `test_worker_isolator_rejects_escaped_symlink_in_parent_home` is xfail(strict) but R3-H already fixed the escape. Stale annotation is not a regression guard. | Remove xfail from `test_executor_boundary_smoke.py` | 1 (conversion) | 0% |
| 2 | Denylist no-space pipe variants (F-01a/F-01b) | `curl\|bash` / `wget\|bash` (no space) bypass `scan_prompt_for_unsafe()`. Two xfail(strict) tests document the gap but it remains open. | Fix source normalisation + convert 2 xfails to passing | 0 (conversion) | +1% |
| 3 | FACTORY_FORCE_MOCK=1 apply-mode fail-closed (F-02) | `_build_config` forces `allow_mock_executor=False` in apply mode even when `FACTORY_FORCE_MOCK=1`, breaking mock dry-runs used in release gate smoke testing. | Fix `FactoryConfig._build_config()` + remove xfail | 0 (conversion) | +1% |
| 4 | MCP audit log `/tmp` world-writable | `_DEFAULT_AUDIT_LOG = "/tmp/autodev_mcp_audit.log"` — no test asserts a warning is emitted when AUTODEV_MCP_AUDIT_LOG is unset, enabling silent audit-log tampering. | 3 new tests in `test_mcp_apply_guardrail.py` | 3 | +1% |
| 5 | Release workflow token as CLI flag | `release.yml` uses `-p "$PYPI_API_TOKEN"` (flag form, visible in `/proc/<pid>/cmdline`). No policy test enforces TWINE_PASSWORD env-var form. | 1 new test in `test_release_workflow_policy.py` | 1 | 0% |

**P0 total estimated new tests: 5 (3 conversions of xfail + 4 genuinely new)**

---

## P1 Gaps (8) — Core Flow Failure / Executor / Protocol

| # | Area | Gap | Est. New Tests | Coverage Delta |
|---|------|-----|---------------|---------------|
| 1 | `InvestigationFlow` — zero tests | `run()` body fully untested; CLI routes to this flow for GitHub issue URLs | 5 | +1% |
| 2 | `BrownfieldDocFlow` — zero tests | `run()` body fully untested; reachable via document-project | 4 | +1% |
| 3 | `ProjectContextFlow` — schema only | R3-E closure overstated; `run()` body untested | 4 | +1% |
| 4 | `executor_router._auto_route` branch gaps | High-risk/language/file-count heuristics and CLAUDE explicit backend override paths untested | 5 | +1% |
| 5 | `test_redirect_to_private_is_rejected` pre-existing failure | Listed as failing in R2 pre-existing failures; redirect-revalidation path still not reliably tested | 2 | +1% |
| 6 | `reports/delivery_reporter.py` + `release_reporter.py` — zero direct tests | Artifact write, section rendering, template fill untested | 6 | +2% |
| 7 | Non-Python gates — `rust_gate`, `typescript_gate`, `integration_gate` failure paths | Binary-absent, timeout, partial-findings paths untested | 8 | +2% |
| 8 | `context_providers` error paths | Large-file truncation, binary-file diff, encoding-error paths missing | 3 | +1% |

**P1 total estimated new tests: 37**

---

## P2 Gaps (5) — Low-Risk / Optional / Cosmetic

| # | Area | Est. New Tests | Coverage Delta |
|---|------|---------------|---------------|
| 1 | TUI dashboard/widgets (Textual optional dep) rendering | 5 | +1% |
| 2 | Agent edge cases: doc_writer, editorial_reviewer, prfaq, product_manager empty/malformed-response paths | 6 | +1% |
| 3 | `examples/` importability health check | 3 | 0% |
| 4 | Optional-dep deferred-import (distillator, embeddings_index) absent-dep branches | 4 | +1% |
| 5 | Scanner error handling: monorepo_scanner permission-error + symlink-loop | 2 | +1% |

**P2 total estimated new tests: 20**

---

## Summary

| Bucket | Count | Est. New Tests | Est. Coverage Delta |
|--------|-------|---------------|---------------------|
| P0 | 5 | 5 | +2% |
| P1 | 8 | 37 | +10% |
| P2 | 5 | 20 | +4% |
| **Total** | **18** | **62** | **+5%** |

**Current coverage:** 81%
**Expected final coverage after all gaps addressed:** ~86%

---

## should_block_tag: FALSE

All P0 gaps are coverage improvements and documented hardening follow-ups, not newly discovered regressions. The four xfail tests (F-01a, F-01b, F-02, F-03) were documented and tracked across R2/R3/Pre-Tag rounds with full disclosure. All 36 release gate checks pass, pytest is 1062 pass / 0 fail, ruff 0 errors, mypy 0 errors. Pre-Tag N issued "go_after_user_action" with full knowledge of all these gaps. No P0 gap represents an unreported security exploit or a regression from a previously-passing test.

---

## Phase 2 Agent Plan

| Agent | Scope | Est. New Tests |
|-------|-------|---------------|
| **Cov-G** | P0 release-critical: de-xfail F-03; fix denylist no-space variants (F-01a/F-01b); add TWINE_PASSWORD policy test | 3 |
| **Cov-H** | P0 security: fix F-02 FACTORY_FORCE_MOCK apply-mode fail-closed; MCP audit-log /tmp warning tests | 4 |
| **Cov-I** | P1 protocol: fix test_redirect_to_private_is_rejected; _auto_route heuristics branch coverage | 7 |
| **Cov-J** | P1 flow failure: InvestigationFlow, BrownfieldDocFlow, ProjectContextFlow new test files | 13 |
| **Cov-K** | P1 reports/gates/context + P2 sweep: delivery_reporter, release_reporter, gates edge cases, context_provider errors, TUI stubs, examples import health | 35 |
