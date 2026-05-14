# autodev-ai Pre-Tag Full Audit — Packaging

**Agent:** PreTag-J  
**Date:** 2026-05-14  
**Scope:** Confirm all packaging artifacts are tag-ready for `v0.1.0a1`. Read-only verification; no commit, no push.

---

## Verification Results (10 checks)

| # | Check | Result |
|---|-------|--------|
| 1 | `dist/autodev_ai-0.1.0a1-py3-none-any.whl` present | PASS |
| 2 | `dist/autodev_ai-0.1.0a1.tar.gz` present | PASS |
| 3 | `twine check dist/*` | PASSED (both wheel + sdist) |
| 4 | Dockerfile both FROM lines have `@sha256:` digest pin | PASS |
| 5 | `packaging/docker/UPDATE.md` exists | PASS |
| 6 | `.github/workflows/docker-publish.yml` multi-arch + tag trigger | PASS |
| 7 | `packaging/pyinstaller/autodev.spec` + `autodev_entry.py` exist | PASS |
| 8 | Homebrew formula: owner=`merchloubna70-dot`, sha256=placeholder, BLOCKED comment | PASS |
| 9 | `packaging/homebrew/PUBLISH_CHECKLIST.md` exists | PASS |
| 10 | `packaging/desktop/autodev-ai.app/Contents/Info.plist` CFBundleShortVersionString | `0.1.0a1` PASS |

---

## Artifact Hashes

| Artifact | SHA-256 |
|----------|---------|
| `autodev_ai-0.1.0a1-py3-none-any.whl` | `395e2102e6eb80269de215bb716c1751d5169dcbb4b2ce42be22fca5a55e5b94` |
| `autodev_ai-0.1.0a1.tar.gz` | `8be1cddf0ed99538fb0bf418eef67946022a2f3fc2aa0767739fbbf3680a8d9c` |

---

## Docker

- **Base image digest (both FROM lines):** `sha256:401f6e1a67dad31a1bd78e9ad22d0ee0a3b52154e6bd30e90be696bb6a3d7461`
- **Platforms:** `linux/amd64,linux/arm64` (Job 2 multi-arch push to GHCR)
- **Tag trigger:** `v*.*.*` — tag push `v0.1.0a1` fires the workflow.

---

## Homebrew Status

**BLOCKED** — intentional and correct:
- `sha256 "TODO_PUBLISH_SHA256"` (placeholder — must be replaced with PyPI sdist hash after publish)
- Four leading comment lines including: `This formula is BLOCKED for publish until PyPI 0.1.0a1 is live and sha256 is computed from PyPI metadata.`
- `url` points to `github.com/merchloubna70-dot/autodev-ai` (NOT `macworkers`) — correct.

---

## Assessment

| Channel | Tag-ready? | Notes |
|---------|-----------|-------|
| PyPI | YES | Wheel hash deterministic (pure-Python). Sdist hash varies per rebuild. `twine check` PASSED. |
| Docker (GHCR) | YES | `v0.1.0a1` tag push triggers multi-arch build+push. Both FROM lines digest-pinned (R3-D). |
| Homebrew | NO (intentional) | Placeholder sha256 + BLOCKED comment. Must update after PyPI publish. |
| macOS .app | YES | Info.plist version `0.1.0a1` confirmed. |
| PyInstaller | YES | `autodev.spec` + `autodev_entry.py` present. |

---

## Diff vs R3-F

No regression. All R2-G + R3-D + R3-F fixes are carried:
- Docker digest pins (R3-D) confirmed on both FROM lines.
- Homebrew owner corrected to `merchloubna70-dot` (R2-G/R3-F BLOCKER-PKG-01/02).
- `twine check` clean — no metadata warnings.

---

## Verdict

**packaging_tag_ready_homebrew_still_blocked**

Pushing tag `v0.1.0a1` will:
1. Trigger `docker-publish.yml` — builds and pushes multi-arch image to GHCR.
2. The pre-built wheel/sdist are `twine check` PASSED and ready for manual `twine upload`.
3. Homebrew publish remains gated — update `sha256` + remove BLOCKED comment only after PyPI publish confirms the final sdist hash.
