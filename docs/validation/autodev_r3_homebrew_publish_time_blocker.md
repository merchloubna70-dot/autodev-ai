# R3 Homebrew Publish-Time Blocker — Validation Record

**Round:** R3-F (RC Final Hardening)
**Date:** 2026-05-14
**Verdict:** `honest_blocker_recorded`
**Status:** NOT "Homebrew ready" — Homebrew remains blocked. PyPI RC gate is NOT contaminated.

---

## What Changed and Why

### Problem

Prior to this change, the release readiness gate conflated two separate concerns:

1. **PyPI RC readiness** — is the Python package ready to publish to PyPI?
2. **Homebrew tap readiness** — is the formula ready to push to a Homebrew tap?

These are **different lifecycle events**. The formula's placeholder sha256
(`REPLACE_WITH_PYPI_0_1_0A1_SDIST_SHA256_AT_PUBLISH_TIME` / `TODO_PUBLISH_SHA256`)
cannot be computed until AFTER PyPI publish succeeds and the sdist URL is known.
Counting that blocker against the PyPI RC strict gate created a logical circularity:
Homebrew was blocked because PyPI was not live, and PyPI was flagged "not ready"
because Homebrew was blocked.

### Resolution

The formula is **honestly blocked**: it carries both a placeholder sha256 and an
explicit `BLOCKED for publish` comment. A step-by-step `PUBLISH_CHECKLIST.md`
documents the exact activation sequence. This is the correct state for a formula
that depends on a not-yet-published PyPI release.

The gate is split into two independent checks (see below). Homebrew block-ness no
longer contaminates the PyPI RC strict-gate verdict.

---

## Artifacts Modified / Created

| Path | Change |
|------|--------|
| `packaging/homebrew/Formula/autodev-ai.rb` | sha256 shortened to `TODO_PUBLISH_SHA256`; added explicit `BLOCKED for publish` comment |
| `packaging/homebrew/PUBLISH_CHECKLIST.md` | New — 7-step activation checklist |
| `tests/unit/test_homebrew_publish_time_blocker.py` | New — 7 tests (all pass) |
| `docs/validation/autodev_r3_homebrew_publish_time_blocker.md` | This document |
| `docs/validation/autodev_r3_homebrew_publish_time_blocker.json` | Machine-readable record |

---

## Gate-Check Spec for R3-I Integration

Two new checks to be added to `scripts/release_readiness_gate.py`:

### Check 1: `r3_homebrew_publish_time_blocker_clean`

**Purpose:** Verify the formula is *honestly* blocked — not accidentally unblocked
or missing its documentation.

**Pass condition (ALL three must be true):**
- `packaging/homebrew/Formula/autodev-ai.rb` sha256 field contains a placeholder
  (matches `TODO_PUBLISH_SHA256` or `REPLACE_WITH_PYPI_0_1_0A1_SDIST_SHA256_AT_PUBLISH_TIME`)
- `packaging/homebrew/Formula/autodev-ai.rb` contains the string `BLOCKED for publish`
- `packaging/homebrew/PUBLISH_CHECKLIST.md` exists

**Fail condition:** Any of the three is absent (e.g., someone replaced sha256 without
running the full checklist, or deleted the BLOCKED comment).

**Category:** `honesty_check` (NOT a "ready" check)
**Blocking:** Yes — if the formula is in an ambiguous state (real sha256 but no checklist
completion evidence) the gate should flag it.

---

### Check 2: `r3_pypi_rc_not_blocked_by_homebrew`

**Purpose:** Meta-gate — ensure Homebrew block-ness is excluded from the PyPI RC
strict-gate verdict when `r3_homebrew_publish_time_blocker_clean` passes.

**Pass condition:**
- `r3_homebrew_publish_time_blocker_clean` passes (formula is honestly blocked)
- PyPI RC strict gate does NOT count Homebrew `blocked_with_reason` status as a
  PyPI RC blocker

**Implementation note for R3-I:** In the gate script, when computing `pypi_rc_verdict`,
skip any check whose `component == "homebrew"` if `r3_homebrew_publish_time_blocker_clean`
is in the passing set. Homebrew should appear in the output as
`status: blocked_with_reason, excluded_from_pypi_rc: true`.

**Category:** `meta_gate`
**Blocking:** No — this check existing and passing means the circularity has been resolved.

---

## Rationale

BLOCKED is acceptable. BLOCKED *and honest* (placeholder + comment + checklist) is the
correct and expected state for a formula awaiting a PyPI release. The only unacceptable
state is *silently* blocked (real sha256 field but the package was never actually published,
or checklist missing).

The test file `tests/unit/test_homebrew_publish_time_blocker.py` enforces honesty at
CI time: if someone replaces the sha256 placeholder with a real hash, `test_formula_sha256_is_placeholder`
will fail, requiring the publisher to verify they have completed all PUBLISH_CHECKLIST.md
steps first.

---

## Test Coverage

| Test | Description | Result |
|------|-------------|--------|
| `test_formula_sha256_is_placeholder` | sha256 is TODO/placeholder | PASS |
| `test_formula_has_blocked_comment` | explicit BLOCKED comment present | PASS |
| `test_publish_checklist_exists_and_has_five_steps` | checklist exists, ≥5 steps | PASS |
| `test_formula_url_points_at_correct_github_user` | URL uses merchloubna70-dot | PASS |
| `test_formula_version_is_0_1_0a1` | version = 0.1.0a1 | PASS |
| `test_publish_checklist_mentions_sha256sum` | checklist has sha256sum step | PASS |
| `test_formula_has_status_pending_comment` | original STATUS comment intact | PASS |
