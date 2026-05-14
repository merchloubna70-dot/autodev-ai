# Round 11 — v0.1.0a4 Release Candidate Validation Report

**Date:** 2026-05-14
**Tag:** `v0.1.0a4`
**HEAD commit at tag:** `9759c2e790042ce80af5934444e59d7e30b7d1cb`
**Decision:** PASS — released to PyPI, GHCR, and Homebrew tap

---

## Executive summary

R11 was the validation gate for v0.1.0a4, the alpha pre-release that absorbs nine commits recovered from dead `worktree-agent-*` worktrees (three r6 supply-chain tracks + six r10 coverage tracks). The release closed the supply-chain limitations table that had been open since a1 (SLSA L3, SBOM, cosign image signing, MCP per-caller auth — all now live).

Two real defects surfaced during the gate and were fixed before publish:

1. **`tui/dashboard.action_quit` was sync, breaking `textual.App` override.** Caught by the release-readiness gate's strict mypy (no `--ignore-missing-imports`); the CI lint job's lax mypy had not surfaced it.
2. **`release.yml` had not been migrated to the `setup-autodev` composite action**, so its test job installed only `[dev]` (missing `textual`) and blocked PyPI publish on the first tag push. Together with a stale `Info.plist` (still hardcoded `0.1.0a3`), the first attempt of `v0.1.0a4` was force-retagged onto a3-aware HEAD after both fixes were merged.

Result after retag: all six release workflows (Lint, Test, Release, Docker, SLSA Provenance, SBOM) PASSED. Fresh-venv pip install + Docker pull both report `autodev-ai 0.1.0a4`. Homebrew tap updated and `brew info` resolves the new version.

---

## Per-step results

| Step | Subject | Result | Evidence |
|---|---|---|---|
| 1 | confirm main clean | PASS | `git status --short` empty at start of round; HEAD at `a83e939` (later advanced to `9759c2e`) |
| 2 | local gate (ruff/mypy/pytest/build/twine) | PASS | ruff `0 errors`; mypy `no issues found in 176 source files`; pytest `2026 passed, 6 skipped, 0 failed`; build produced `autodev_ai-0.1.0a4-py3-none-any.whl` + `.tar.gz`; twine `PASSED` |
| 3 | release-check `--strict / --strict-r2 / --strict-r3 / --strict-rc` | PASS | All four modes 36/36 pass post-mypy-fix; first run found `mypy_passes` + `r3_mypy_clean` failure → fixed in commit `cf02c72` |
| 4 | release notes | PASS | `docs/release_notes/v0.1.0a4.md` (this round's drafted notes) |
| 5 | version bump | PASS | `pyproject.toml` 0.1.0a3 → 0.1.0a4; `README.md` x4 occurrences; `Info.plist` x2 occurrences (added in fix commit `9759c2e` after first tag broke on plist drift) |
| 6+7 | tag + push | PASS (after retag) | First tag pushed at `764dfa4`, Release workflow failed in test job (composite-action drift). Tag deleted, fix commits `a621408` + `9759c2e` pushed, tag recreated at `9759c2e`. Final tag confirmed by `git show v0.1.0a4`. |
| 8 | post-publish verify (pip + docker + CLI) | PASS | Fresh venv `uv pip install --pre autodev-ai==0.1.0a4` → `autodev --version` reports `autodev-ai 0.1.0a4`; `autodev --help` lists all subcommands; `autodev release-check --help` shows `--run-id` / `--repo-path` flags. `docker pull ghcr.io/merchloubna70-dot/autodev-ai:v0.1.0a4` → image digest `sha256:62a716aaebb2f7c853055a39d37f4f64fa455e04f4fc92ca724dff11a6b1a44d`; `docker run --rm <image> --version` → `autodev-ai 0.1.0a4`. |
| 9 | Homebrew formula bump + smoke | PASS (caveat) | Both `packaging/homebrew/Formula/autodev-ai.rb` and `packaging/homebrew/tap/Formula/autodev-ai.rb` bumped (version, url, sha256). sdist sha256 `5c876cce67a0193bae82a5f518e827429dffa35618ca3f40f5fbad21ec5e7a3e` independently re-verified via `curl + shasum -a 256`. `brew style` clean. Tap repo `merchloubna70-dot/homebrew-autodev` updated (commit `b477f4d`); `brew update && brew info merchloubna70-dot/autodev/autodev-ai` resolves to `stable 0.1.0a4`. **Local `brew install` smoke blocked** by an unrelated macOS system Python issue (homebrew `python@3.12` bottle was built against libexpat ≥2.7 ABI; this machine's `/usr/lib/libexpat.1.dylib` is 2.6 — symbol `_XML_SetAllocTrackerActivationThreshold` missing). Issue is independent of the formula and would not affect a fresh macOS host or CI. |
| 10 | final report | PASS | This document + accompanying JSON |

---

## Released artifacts

| Channel | Identifier | Verification |
|---|---|---|
| PyPI wheel | `autodev_ai-0.1.0a4-py3-none-any.whl` (337,033 bytes) | sha256 `7dda66495d8251d08c1da44b69e93f8d0fc2792fb424acff9da713081b4e5049` |
| PyPI sdist | `autodev_ai-0.1.0a4.tar.gz` (1,020,669 bytes) | sha256 `5c876cce67a0193bae82a5f518e827429dffa35618ca3f40f5fbad21ec5e7a3e` |
| GHCR image | `ghcr.io/merchloubna70-dot/autodev-ai:v0.1.0a4` | digest `sha256:62a716aaebb2f7c853055a39d37f4f64fa455e04f4fc92ca724dff11a6b1a44d`; multi-arch (amd64+arm64) |
| GitHub Release | `v0.1.0a4` | wheel + sdist attached via `softprops/action-gh-release@v3`; SBOM (CycloneDX 1.5 + SPDX 2.3) and SLSA in-toto attestation attached by separate workflows |
| Homebrew tap | `merchloubna70-dot/homebrew-autodev` HEAD `b477f4d` | `brew info` resolves to 0.1.0a4 |

---

## Supply-chain attestations live for the first time

- **SLSA L3 provenance** — `.slsa-attestation` produced by `slsa-framework/slsa-github-generator` reusable workflow; attached to GitHub Release. Verify with `slsa-verifier verify-artifact ... --source-uri github.com/merchloubna70-dot/autodev-ai --source-tag v0.1.0a4`.
- **cosign keyless image signature** — Fulcio OIDC certificate + Rekor transparency log entry for `ghcr.io/merchloubna70-dot/autodev-ai:v0.1.0a4`. Verify with `cosign verify ... --certificate-identity-regexp='https://github.com/merchloubna70-dot/autodev-ai/.+' --certificate-oidc-issuer=https://token.actions.githubusercontent.com`.
- **SBOM** — CycloneDX 1.5 + SPDX 2.3 generated by `anchore/sbom-action` and attached to the Release.

---

## Workflows on tag `v0.1.0a4` (HEAD `9759c2e`)

| Workflow | Status | Duration |
|---|---|---|
| Lint | success | ~1m |
| Test | success | ~1m 20s |
| Release (test + publish jobs) | success | ~2m |
| Docker — Build & Publish to GHCR | success | ~5m |
| SLSA Provenance | success | ~3m |
| SBOM | success | ~1m |

---

## Defects discovered and fixed during R11

| Commit | Defect | Detection signal | Fix |
|---|---|---|---|
| `cf02c72` | `tui/dashboard.action_quit` signature mismatch with `textual.App` superclass (sync vs `async def`) | release-readiness-gate strict mypy (`mypy src/autodev` without `--ignore-missing-imports`) | Changed signature to `async def action_quit` |
| `a621408` | `.github/workflows/release.yml` not migrated to the `setup-autodev` composite action; still installed `[dev]` only and broke on `textual` import in the test job | First tag push: Release workflow failed in test job after `v0.1.0a4` push | Migrated release.yml to use `./.github/actions/setup-autodev` composite |
| `9759c2e` | `packaging/desktop/autodev-ai.app/Contents/Info.plist` `CFBundleShortVersionString` / `CFBundleVersion` lagged `pyproject.toml` at 0.1.0a3 | `test_homebrew_formula_metadata.py::test_plist_*_matches_pyproject` (BLOCKER-PKG-03) on the first tag push | Bumped both fields to 0.1.0a4 |

---

## Lessons captured (memory updates)

1. **CI workflow drift surface is larger than two files.** R11 found a third workflow (`release.yml`) carrying the same `[dev]` vs `[dev,tui]` drift that was previously cleaned in `test.yml` and `lint.yml`. The new `setup-autodev` composite action now centralizes the install step, so future extras additions live in exactly one place.
2. **Lax CI mypy hides real override-signature bugs.** CI runs `mypy --ignore-missing-imports --no-strict-optional`; that suppresses errors against unresolved third-party bases. The release-readiness gate runs `mypy src/autodev` without those flags and surfaced the `textual.App.action_quit` override mismatch. Recommend keeping the strict gate run as the release blocker even if CI stays lax.
3. **PyInstaller `Info.plist` is a third version-string surface.** `pyproject.toml` and `__init__.py` (via `importlib.metadata`) are usually the canonical pair, but `Info.plist` also has hard-coded `CFBundleShortVersionString` + `CFBundleVersion`. Bumping pyproject without plist is caught by a metadata test, but only when CI runs the full suite. Local pytest must include the metadata test in the dev loop, not just module-level tests.
4. **First-tag retag is acceptable for a clean failure.** The original `v0.1.0a4` tag at `764dfa4` produced zero PyPI artifacts (test job blocked publish) and zero GitHub Release rows; SLSA / SBOM ran on a doomed source revision. Deleting and recreating the tag at `9759c2e` was strictly destructive on metadata that nothing downstream had observed yet. Decision recorded for the next pre-release: a *first* tag retag is fine when artifact count is zero; subsequent retag would require version bump.

---

## Sign-off

R11 PASSES the release validation gate. `v0.1.0a4` is available via:

```bash
pip install --pre autodev-ai==0.1.0a4
brew install merchloubna70-dot/autodev/autodev-ai
docker pull ghcr.io/merchloubna70-dot/autodev-ai:v0.1.0a4
```

Next strategic decision (out of R11 scope): when to cut `0.1.0` final.
