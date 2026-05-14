# Pre-Tag Full Audit — Docs & Onboarding (PreTag-K)

**Round:** full_audit_docs_onboarding  
**Agent:** PreTag-K  
**Date:** 2026-05-14  
**Build on:** R1-I + R3-G + RC-D (not re-done)

---

## 1. Doc File Presence (12 checks)

| File | Present | Notes |
|------|---------|-------|
| `README.md` | YES | pip install URL contains `0.1.0a1`; `--pre` documented |
| `CHANGELOG.md` | YES | `## [0.1.0a1] — 2026-05-14 (Pre-Release)` confirmed |
| `docs/configuration.md` | YES | 9,136 bytes (>>500 chars) |
| `docs/troubleshooting.md` | YES | 8,746 bytes (>>500 chars) |
| `docs/quickstart.md` | YES | Present |
| `docs/architecture.md` | YES | Present |
| `docs/faq.md` | YES | Present |
| `docs/tutorials/` (5–7 files) | YES | 7 files: 01–07 |
| `docs/release_notes/v0.1.0a1.md` | YES | 1,946 words (~1900 target) |
| `docs/release/pypi_0_1_0a1_publish_checklist.md` | YES | Present |
| `docs/release/pypi_0_1_0a1_rollback_plan.md` | YES | Present |
| `examples/README.md` + 10 brief files | YES | 10 dirs each with `brief.md` |

All 12 checks: PASS.

---

## 2. Forbidden Phrase Scan

Scope: README.md, docs/configuration.md, docs/troubleshooting.md, docs/quickstart.md, docs/architecture.md, docs/faq.md, docs/tutorials/*, docs/release_notes/v0.1.0a1.md, docs/release/*, examples/README.md

| Forbidden phrase | Hits | Verdict |
|-----------------|------|---------|
| `production-ready` (promotional claim) | 0 promotional | 2 hits in quickstart.md:102 and faq.md:202 — both in explicitly negative/warning context ("refuses to claim the run is production-ready"; "conditions prevented marking the run as production-ready"). Not promotional. PASS |
| `enterprise-ready` | 0 | PASS |
| `Homebrew tap available` / `brew install autodev-ai` (promotional) | 0 promotional | 2 diagnostic/warning uses: release_notes warns "Do not attempt `brew install autodev-ai`; it will fail"; troubleshooting describes the failure symptom. Not promotional. PASS |
| `available on PyPI now` | 0 | PASS |
| `production-grade` (in security claims) | 0 | PASS |

All 5 forbidden phrase checks: PASS (0 promotional hits).

---

## 3. Required Phrase Checks

| Required item | Present | Location |
|--------------|---------|----------|
| `--allow-mock-executor` documented | YES | README.md lines 66, 116, 125 |
| `FACTORY_FORCE_MOCK` documented | YES | docs/configuration.md lines 64, 71, 170 |
| `AUTODEV_MCP_ALLOW_APPLY` documented | YES | docs/configuration.md lines 83, 219, 287 |
| `dashboard` command listed | YES | docs/troubleshooting.md lines 258–260 (`autodev dashboard`) |
| Mock fallback `NotReleaseReady` warning | YES | README.md line 207; quickstart.md lines 97–102; faq.md Q13 |

All 5 required phrase checks: PASS.

---

## 4. Key Detail Checks

- **pip install URL:** `https://github.com/merchloubna70-dot/autodev-ai/releases/download/v0.1.0a1/autodev_ai-0.1.0a1-py3-none-any.whl` — contains `0.1.0a1`. PASS.
- **`--pre` flag:** README documents `pip install --pre autodev-ai` (once published on PyPI). PASS.
- **CHANGELOG Pre-Release marker:** `## [0.1.0a1] — 2026-05-14 (Pre-Release)` confirmed. PASS.
- **Release notes word count:** 1,946 words (target ~1,900). PASS.
- **Tutorials count:** 7 files (01-bug-fix.md through 07-a2a-server.md). Within 5–7 range. PASS.
- **Examples briefs:** 10 directories (01-mdlines through 10-prfaq-product), each containing `brief.md`. PASS.

---

## 5. Diff vs RC-D

No regression detected. Release notes `docs/release_notes/v0.1.0a1.md` (1,946 words) intact. Publish checklist and rollback plan unchanged from RC-D. Configuration and troubleshooting docs both substantially larger than 500-char minimum (9,136 and 8,746 bytes respectively).

---

## Verdict

**docs_tag_ready_honest**

All 12 doc files present with correct content. Zero promotional forbidden phrases. All 5 required phrases documented. Release notes honest (pre-release framing throughout). No regression vs RC-D.
