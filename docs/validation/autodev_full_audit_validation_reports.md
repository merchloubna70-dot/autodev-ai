# Pre-Tag Full Audit — Validation Reports Self-Audit

**Agent:** PreTag-L  
**Date:** 2026-05-14  
**Scope:** Self-audit of all `docs/validation/` reports for parseability, pair completeness, cross-report consistency, and forbidden phrase absence

---

## 1. File Count by Category

| Category | Files | JSON | MD |
|---|---|---|---|
| R1 (release/cli/executor/security etc.) | 24 | 12 | 12 |
| R2 (`autodev_r2_*`) | 12 | 6 | 6 |
| R3 (`autodev_r3_*`) | 18 | 9 | 9 |
| RC (`autodev_pypi_rc_*` + `pypi_0_1_0a1_*`) | 10 | 5 | 5 |
| Pre-Tag (`autodev_full_audit_*`) | 16 | 8 | 8 |
| Aggregators (`autodev_release_hardening_round`) | 2 | 1 | 1 |
| Orphaned JSON (no matching MD) | 1 | 1 | 0 |
| **Total** | **83** | **42** | **41** |

**R1 sub-reports:** a2a_protocol, ci_quality, cli_surface, documentation_onboarding, executor_boundary, flow_agent_coverage, installation, mcp_server, packaging_artifact, release_readiness_gate, release_topology, security_secret.

**Pre-Tag sub-reports (8 pairs):** full_audit_a2a, full_audit_cli_surface, full_audit_docs_onboarding, full_audit_executor_isolation, full_audit_flow_agent_coverage, full_audit_mcp, full_audit_metadata, full_audit_packaging.

**Orphaned:** `release_readiness_gate_run.json` — machine-generated gate run output (42 checks, overall: pass, strict_pass: true). No author-level .md is expected for this file type. Not a defect.

---

## 2. JSON Parse Status

| Metric | Value |
|---|---|
| Total JSON files | 42 |
| Parsed OK | 42 |
| Parse failures | 0 |

All 42 JSON files pass `python -m json.tool` cleanly.

---

## 3. MD/JSON Pair Completeness

| Check | Result |
|---|---|
| MD files without matching JSON | 0 |
| JSON files without matching MD | 1 (`release_readiness_gate_run.json`) |
| All author-level .md files have a .json | YES |

The one unpaired JSON (`release_readiness_gate_run.json`) is a machine-generated gate-run artifact, not an author-level report. No .md is expected for it.

---

## 4. Verdict Cross-Check

| Round | Expected Verdict | Actual (from JSON) | Consistent? |
|---|---|---|---|
| R1 aggregator | `pass_with_limitations` | `pass_with_limitations` | YES |
| R2 sub-reports | no regressions from R1 | all record `closed`/`hardened`/`corrected` with residual risks noted | YES |
| R3 sub-reports | `pass` or `closed` | `pass` / `closed` / `hardened_with_documented_residual_risk` / `honest_blocker_recorded` | YES |
| RC reports | `pass` | `publishable` / `frozen` / `rc_ready_no_technical_blockers` / `ready_for_tag_push` | YES |

No sub-report contradicts its round's aggregator verdict. No R3 sub-report claims "Homebrew ready" while the aggregator records Homebrew as blocked.

---

## 5. Forbidden Phrase Audit

| Phrase | Raw Hits | All False Positives? | Real Forbidden Claims |
|---|---|---|---|
| `production-ready` | 4 | YES | 0 |
| `enterprise-ready` | 2 | YES | 0 |
| `Homebrew ready` / `Homebrew is ready` | 3 | YES | 0 |

**production-ready:** All 4 hits appear in negation/checklist context: "Did NOT fabricate Docker production-ready", "patterns_checked list", "must not contain: production ready". No affirmative claim.

**enterprise-ready:** Both hits appear in `full_audit_metadata` as items in the forbidden-phrase check table (showing 0 matches found). No affirmative claim.

**Homebrew ready:** All 3 hits appear in phrases that explicitly deny the status: "Did NOT fabricate Homebrew ready", "NOT Homebrew ready — Homebrew remains blocked", "Did NOT write Homebrew pending as Homebrew ready". No affirmative claim.

---

## 6. False PyPI Publish Claims

**Result: 0 false claims.**

Two PyPI-publish-related phrase hits:
1. `full_audit_metadata.json` — "not yet published to PyPI" (accurate negation)
2. `r2_release_workflow_pytest_gate.md` — "No code is published to PyPI until the secret is explicitly set" (gate semantics, not a publish claim)

---

## 7. Homebrew Status Consistency

| Source | Homebrew Status |
|---|---|
| Actual formula file | `sha256 "TODO_PUBLISH_SHA256"` + `BLOCKED for publish` comment |
| R2 `homebrew_metadata_closure.json` | `homebrew_tap_publish_blocked: true` |
| R3 `homebrew_publish_time_blocker.json` | `homebrew_status: blocked_with_reason` / `verdict: honest_blocker_recorded` |
| RC `pypi_0_1_0a1_rc_publish_prep.json` | `homebrew: blocked_with_reason` |
| Pre-Tag `full_audit_packaging.json` | `homebrew_publish_status: blocked_with_reason_pending_pypi_publish` |
| Gate run check `r2_homebrew_sha256_not_stale` | PASS — tests that old fabricated hash `744375fb...` is absent (correct semantics; placeholder `TODO_PUBLISH_SHA256` is the honest replacement) |

All reports consistently record Homebrew as **BLOCKED** pending PyPI publish and sha256 replacement. No report claims Homebrew is unblocked or published.

---

## 8. Summary

| Check | Result |
|---|---|
| All JSON parse | PASS (42/42) |
| MD/JSON pair complete (author-level) | PASS (41/41 MD have JSON) |
| Forbidden phrases — zero real claims | PASS |
| False PyPI publish claims | 0 |
| Homebrew status consistently blocked | PASS |
| Cross-round verdict consistency | PASS |

**Verdict: `validation_reports_self_consistent`**

The validation report corpus is internally consistent, machine-parseable, free of forbidden status claims, free of false publish assertions, and uniformly records Homebrew as BLOCKED with an honest placeholder. The one unpaired JSON is a machine-generated gate-run artifact and is not a defect.
