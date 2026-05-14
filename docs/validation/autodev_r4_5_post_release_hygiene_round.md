# autodev-ai R4.5 Post-Release Hygiene Round — Aggregator

> **Overall: `pass_with_limitations`**
> v0.1.0a2 published on PyPI + GitHub + Docker is fully verified. Homebrew formula sha256 backfilled and matches canonical PyPI. **Zero actual secret leaks in git.** Token rotation checklist generated; rotation itself not executed (user decision).

---

## Headline Verification

| Channel | Status | Evidence |
|---|---|---|
| **PyPI 0.1.0a2** | ✅ **published_verified** | `pip install --pre autodev-ai==0.1.0a2` → `autodev --version` = `autodev-ai 0.1.0a2` |
| **GitHub Release v0.1.0a2** | ✅ **published_verified** | `gh release view` returns 2 assets, prerelease, non-draft |
| **Docker v0.1.0a2** | ✅ **published_verified_with_limitations** | `docker pull` (anon) + `docker run --version` → 0.1.0a2; digest `sha256:6d0fb4a5...`; amd64+arm64 |
| **Artifact hash integrity** | ✅ **exact_match** | both wheel + sdist downloaded and `shasum -a 256` matches recorded hashes byte-for-byte |
| **Homebrew formula** | ⚠️ **formula_ready_tap_pending** | sha256+url backfilled from canonical PyPI; tap repo creation is R5 |
| **Secret hygiene** | ✅ **no_secret_leak_in_git** | 0 PyPI token patterns in git; 0 actual_leak; 4 mitigations confirmed present |
| **Token rotation** | 📋 **checklist_ready_user_action** | rotation recommended; checklist at `docs/release/pypi_token_rotation_checklist.md` |
| **Production enterprise** | ❌ **blocked (R5 scope)** | no SLSA/SBOM/signed-image/per-caller-MCP-auth |

---

## A — PyPI Install Smoke

```bash
$ python3.12 -m venv /tmp/autodev-pypi-final
$ /tmp/autodev-pypi-final/bin/pip install --pre autodev-ai==0.1.0a2
WARNING: typer 0.25.1 does not provide the extra 'all'   # ← R5 cleanup

$ /tmp/autodev-pypi-final/bin/autodev --version
autodev-ai 0.1.0a2  ✓

$ /tmp/autodev-pypi-final/bin/python -m autodev.cli --version
autodev-ai 0.1.0a2  ✓

$ /tmp/autodev-pypi-final/bin/python -m autodev.release_readiness_gate
Traceback (...) — shim broken from PyPI install   # ← R5 cleanup
```

Two non-blocking warnings recorded (typer[all] deprecation + release_readiness_gate shim broken from PyPI install). The primary CLI works.

## B — GitHub Release v0.1.0a2

- URL: https://github.com/merchloubna70-dot/autodev-ai/releases/tag/v0.1.0a2
- Author: `github-actions[bot]`
- Published: 2026-05-14T07:49:34Z
- Assets: 2 (wheel + sdist)
- Body: `**Full Changelog**: ...compare/v0.1.0a1...v0.1.0a2` (no false stable/enterprise claims)
- Workflow run: `release.yml` → success
- Secret-in-logs: none detected (env-block token, no `-p` flag)

## C — Docker v0.1.0a2 Smoke

- `ghcr.io/merchloubna70-dot/autodev-ai:v0.1.0a2`
- digest: `sha256:6d0fb4a571229a30f2fda318a7d5679f0eec4b5dd80cd737dab114847cf65413`
- anon pull works (logged out → pulled)
- `docker run --version` → `autodev-ai 0.1.0a2`
- `docker run --help` exits 0
- multi-arch (linux/amd64 + linux/arm64) preserved from v0.1.0a1 (same docker-publish.yml path)
- Enterprise-blocker: no SLSA, no SBOM, no cosign signature (R5)

## D — Artifact Hash Verification

Downloaded both PyPI artifacts and recomputed sha256 locally:

| File | Recorded | Recomputed | Match |
|---|---|---|---|
| wheel | `4b01686898c2…` | `4b01686898c2…` | ✅ |
| sdist | `246f5f60810c…` | `246f5f60810c…` | ✅ |

No tampering. Homebrew formula uses the sdist sha256 above (verified separately).

## E — Homebrew Formula Static Check

`packaging/homebrew/Formula/autodev-ai.rb`:
```ruby
url    "https://files.pythonhosted.org/packages/b0/4a/.../autodev_ai-0.1.0a2.tar.gz"
sha256 "246f5f60810c1832051f9219fd141fe63ce87bbafec0125412d18cea326c291d"
version "0.1.0a2"
```

- ✅ url → canonical PyPI
- ✅ sha256 → matches PyPI metadata (independently verified in D)
- ✅ version → 0.1.0a2
- ✅ TODO_PUBLISH_SHA256 removed
- ✅ "BLOCKED for publish" comment removed (replaced with backfill provenance note)
- ⚠️ Tap repo (`merchloubna70-dot/homebrew-autodev`) NOT YET CREATED — R5 task
- ⚠️ 9 transitive resource sha256s not re-verified this round (drafted earlier; R5)
- `brew audit [path]` disabled in Homebrew 5.x — formula must be tapped first; deferred to actual tap publish

## F — Secret Hygiene (full-repo grep)

| Category | Count |
|---|---|
| PyPI token patterns in git | **0** |
| **actual_leak** | **0** |
| placeholder (e.g. `pypi-...` ellipsis) | 7 |
| test_fixture (mock values in `tests/`) | 18 |
| doc_example (illustrative in docs) | 8 |
| tool_pattern_constant (declared in `secret_redaction.py` / `security_reviewer.py`) | 4 |

Mitigations confirmed present:
- ✅ `src/autodev/utils/secret_redaction.py`
- ✅ `src/autodev/mcp_server/path_safety.py`
- ✅ `.gitignore` covers `.env / credentials.json / secrets.toml / *.pem / *.key`
- ✅ `worker_isolator.py::_validate_branch_name`

GH secret metadata (names + updated_at only — values invisible by API):
- `PYPI_API_TOKEN  updated=2026-05-14T07:44:23Z` (timestamp matches when Opus set via stdin pipe earlier in this session)

## G — Token Rotation Checklist

Generated `docs/release/pypi_token_rotation_checklist.md` (+ copy in validation). 4-step procedure:

1. Generate new project-scoped token at https://pypi.org/manage/account/token/
2. `printf '%s' '<token>' | gh secret set PYPI_API_TOKEN --repo …` (stdin pipe, no argv)
3. Revoke OLD token on PyPI (burns the chat-leaked credential)
4. Verify on next tag push

**Rotation NOT executed this round** — by design (user decision). Current token works; rotation is hygiene not blocking.

---

## Release Readiness Matrix — Final

```
internal_dogfood          : allowed
public_beta               : allowed
PyPI 0.1.0a2              : PUBLISHED_VERIFIED
GitHub Release v0.1.0a2   : PUBLISHED_VERIFIED
Docker v0.1.0a2           : PUBLISHED_VERIFIED_WITH_LIMITATIONS
Homebrew                  : FORMULA_READY_TAP_PUBLISH_PENDING
production_enterprise_use : BLOCKED (R5 scope)
```

---

## Remaining Blockers (Operational, not Technical)

1. **Homebrew tap repo creation** — R5. Without `merchloubna70-dot/homebrew-autodev` repo, end users still cannot `brew install autodev-ai`. Formula is ready to push.
2. **Production enterprise readiness** — R5: SLSA + SBOM + per-caller MCP auth + signed Docker.

---

## Remaining Risks (Documented, Non-Blocking)

1. **PyPI token rotation pending** — token was pasted in chat once; checklist provided; user action.
2. **9 transitive resource sha256s** in Homebrew formula not re-verified vs current PyPI versions of pydantic/typer/rich/etc.
3. **Docker `:latest` rolling** — alpha pre-release, pin to `v0.1.0a2` for immutability.
4. **No supply-chain attestation** on Docker (SLSA/SBOM/cosign — R5).
5. **`typer[all]` deprecation warning** on PyPI install (R5: bare `typer>=0.9`).
6. **`autodev.release_readiness_gate` shim broken** from PyPI install (scripts/ not in wheel — R5).

---

## R5 Plan — Recommended Order

| # | Task | Effort |
|---|---|---|
| 1 | Create `merchloubna70-dot/homebrew-autodev` tap repo + push formula | 15 min |
| 2 | Re-verify 9 transitive resource sha256s (homebrew-pypi-poet) | 30 min |
| 3 | **Rotate PYPI_API_TOKEN to project-scoped** | 5 min user + 0 min me |
| 4 | Fix `typer[all]` deprecation in pyproject (bare `typer>=0.9`) | 2 min |
| 5 | Fix `autodev.release_readiness_gate` shim — ship `scripts/` in wheel OR rewrite self-contained | 30 min |
| 6 | SLSA provenance via cosign on Docker images | 2 hr |
| 7 | SBOM generation in release.yml (syft/cyclonedx) | 1 hr |
| 8 | Per-caller MCP auth (bearer/OAuth on stdio transport) | 4 hr |
| 9 | Apple Developer ID signing for macOS .app launcher | 2 hr |
| 10 | Coverage lift on 5 aspirational modules | 6-8 hr |

After R5: candidate to promote `production_enterprise_use: blocked → allowed_with_limitations`.

---

## Quality Red Lines Upheld

- ❌ Did NOT publish new version (v0.1.0a2 was already published in prior round; this round is verify-only)
- ❌ Did NOT create new tag
- ❌ Did NOT yank PyPI release
- ❌ Did NOT request user paste token again
- ❌ Did NOT read or print `PYPI_API_TOKEN` value (only `updated_at` from API)
- ❌ Did NOT write token to any file
- ❌ Did NOT write token rotation as completed (still pending user action)
- ❌ Did NOT write Homebrew as fully published (tap publish remains R5)
- ❌ Did NOT write Docker as production-ready (alpha + no attestation)
- ❌ Did NOT write 0.1.0a2 as stable 1.0
- ❌ Did NOT skip pytest (existing tests passed in CI for v0.1.0a2)
- ❌ Did NOT hide install warnings (typer[all] + release_readiness_gate shim explicitly recorded)
- ❌ Did NOT fabricate sha256 (independent recomputation)
