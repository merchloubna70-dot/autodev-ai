# autodev-ai PyPI 0.1.0a1 RC Publish Preparation — Final Aggregator

> **Overall result: `pass`** — PyPI 0.1.0a1 RC is technically ready. Only an operational step (user adds `PYPI_API_TOKEN` GitHub secret) remains before tag push will publish.
> 7-agent round (RC-A/B/C/D/E sonnets + RC-F/G Opus aggregator).
> Predecessors: R1 → R2 → R3 release hardening rounds, all `pass_with_limitations` → R3 `pass` → RC `pass`.

---

## TL;DR — Go / No-Go

| Channel | Verdict | Why |
|---|---|---|
| **PyPI 0.1.0a1 RC readiness** | ✅ GO | 36/36 gate pass; metadata + classifiers + URLs + dist hashes all confirmed |
| **PyPI actual publish** | ✅ GO **after** PYPI_API_TOKEN set | release.yml's twine upload step is guarded by `if: secrets.PYPI_API_TOKEN != ''` |
| **Docker v0.1.0a1 multi-arch image** | ✅ GO | docker-publish.yml triggers on same tag; ghcr.io public |
| **Homebrew tap publish** | ❌ NO-GO | formula sha256 still placeholder; unblocks 5 min after PyPI publish |
| **Production enterprise use** | ❌ NO-GO | scope-deferred to R4 (SLSA, SBOM, MCP auth, etc.) |

**Recommend tag push now**: **No** — first set the GitHub Secret, then push the tag.

---

## Final Artifact Hashes (immutable)

```
wheel  : dist/autodev_ai-0.1.0a1-py3-none-any.whl
         sha256 = 395e2102e6eb80269de215bb716c1751d5169dcbb4b2ce42be22fca5a55e5b94

sdist  : dist/autodev_ai-0.1.0a1.tar.gz
         sha256 = 0a84c81e38ee9dfa95112e487932af52e599ea27d6943e0aa33b390dfc2fd410

twine check     : PASSED for both
fresh-venv test : pip install + autodev --version → autodev-ai 0.1.0a1
pip show test   : Home-page + License + classifiers populated
```

(These are the **final** hashes after metadata fixes. The preflight build hashes — `5f5b51…` wheel / `243c9f…` sdist — recorded in autodev_pypi_rc_artifact_build.{md,json} are now superseded.)

---

## RC Closure Matrix

| Item | Status | Evidence |
|---|---|---|
| Metadata freeze | ✅ frozen (3 findings closed by Opus inline) | `autodev_pypi_rc_metadata_freeze.{md,json}` |
| Artifact build | ✅ wheel + sdist twine-clean | `autodev_pypi_rc_artifact_build.{md,json}` |
| release.yml audit | ✅ ready_for_tag_push | `autodev_pypi_rc_release_workflow_audit.{md,json}` |
| Release notes | ✅ drafted (1,946 words, 15 sections) | `docs/release_notes/v0.1.0a1.md` |
| Publish checklist | ✅ 6+5+10 step | `docs/release/pypi_0_1_0a1_publish_checklist.md` |
| Rollback plan | ✅ PyPI yank + GH delete + Docker repoint + forward-only | `docs/release/pypi_0_1_0a1_rollback_plan.md` |
| Final gate run | ✅ 36/36 pass, all 4 strict modes exit 0 | `autodev_pypi_rc_release_gate_final.{md,json}` |

---

## Metadata Fixes Applied During This Round

RC-A initially reported the metadata as `inconsistencies` with 3 findings. Opus applied all 3 fixes inline:

**F-1 — classifiers added** (14 trove classifiers):
- Development Status :: 3 - Alpha
- License :: OSI Approved :: MIT License
- Programming Language :: Python :: 3.10 / 3.11 / 3.12
- Topic :: Software Development :: Code Generators / Build Tools
- Typing :: Typed
- …(others)

**F-2 — `[project.urls]` added** (5 URLs):
- Homepage / Repository / Issues / Changelog / Documentation, all pointing at `merchloubna70-dot/autodev-ai`

**F-3 — README pip URL fixed**:
- Old: `…/releases/download/v0.1.0-alpha/autodev_ai-0.1.0-py3-none-any.whl` (would 404 after publish)
- New: `pip install --pre autodev-ai` (preferred) + `…/releases/download/v0.1.0a1/autodev_ai-0.1.0a1-py3-none-any.whl` (fallback)

After fixes: rebuilt dist, retested twine, retested fresh-venv install, retested gate. All green. **Verdict: frozen.**

---

## Release Workflow Audit — Highlights

`release.yml` job chain: `test (ruff + mypy + pytest)` → `publish (build + twine check + GitHub Release + conditional twine upload)`.

**Token safety:**
- `if: ${{ secrets.PYPI_API_TOKEN != '' }}` guard on twine upload — accidental publish prevented when secret unset
- No step prints or persists the token
- 1 LOW finding: token passed as `-p $PYPI_API_TOKEN` CLI flag (briefly visible in `/proc/<pid>/cmdline`). Mitigated by GitHub runner log masking. Acceptable for alpha; switch to `TWINE_PASSWORD` env var in R4.

**Behavior:**
- Token SET → tests pass → PyPI upload + GitHub Release
- Token UNSET → tests pass → GitHub Release only (PyPI step skipped)

So a **dry-run tag push is safe** even without the secret — it produces a GitHub Release with artifacts but no PyPI upload. You can verify end-to-end CI behavior before committing to PyPI publish.

---

## Required User Actions (Exact Steps)

### Step 1 — Add GitHub Secret

URL: https://github.com/merchloubna70-dot/autodev-ai/settings/secrets/actions

- New repository secret
- Name: `PYPI_API_TOKEN`
- Value: PyPI API token (generate at https://pypi.org/manage/account/token/, scope to `autodev-ai` or account-wide)

### Step 2 — Push the tag

```bash
git status --short                                          # expect empty
git tag -a v0.1.0a1 -m "autodev-ai v0.1.0a1 — first PyPI RC"
git push origin v0.1.0a1                                     # triggers release.yml
```

### Step 3 — Watch the workflow

```bash
gh run watch --repo merchloubna70-dot/autodev-ai
```

### Step 4 — Verify after green

```bash
pip index versions autodev-ai --pre                          # expect 0.1.0a1
python3.12 -m venv /tmp/verify && /tmp/verify/bin/pip install --pre autodev-ai==0.1.0a1
/tmp/verify/bin/autodev --version                            # autodev-ai 0.1.0a1
```

### Step 5 — Update Homebrew (5-min step after PyPI live)

```bash
curl -L "https://files.pythonhosted.org/packages/source/a/autodev-ai/autodev_ai-0.1.0a1.tar.gz" \
  | shasum -a 256
# patch packaging/homebrew/Formula/autodev-ai.rb:
#   replace TODO_PUBLISH_SHA256 with the hash above
#   remove the "BLOCKED" leading comment
brew audit --formula packaging/homebrew/Formula/autodev-ai.rb
```

See `packaging/homebrew/PUBLISH_CHECKLIST.md` for the full 7-step Homebrew activation procedure.

---

## Remaining Limitations (Honest)

1. **PyPI 0.1.0a1 not yet published** — gates only on the user-driven steps above. No technical blockers.
2. **Homebrew tap BLOCKED** — formula sha256 is placeholder. Unblocks 5 min after PyPI publish per step 5.
3. **Production enterprise use** — 4 documented residuals (egress proxy SSRF; kernel BGP/anycast; MCP audit log world-writable default; cleanup TOCTOU) + 4 deferred features (SLSA / SBOM / per-caller MCP auth / signed Docker). Scope-deferred to R4.
4. **Docker `:latest` is rolling** — base image *inside* Dockerfile is digest-pinned, but the published `:latest` tag is mutable. Users wanting immutable refs should pull `0.1.0a1`.
5. **macOS .app launcher** — signed/notarized status not validated this round.

---

## Files Created / Modified This Round

**Created** (9 files):
- `docs/release_notes/v0.1.0a1.md` (1,946 words)
- `docs/release/pypi_0_1_0a1_publish_checklist.md`
- `docs/release/pypi_0_1_0a1_rollback_plan.md`
- `docs/validation/autodev_pypi_rc_metadata_freeze.{md,json}`
- `docs/validation/autodev_pypi_rc_artifact_build.{md,json}`
- `docs/validation/autodev_pypi_rc_release_workflow_audit.{md,json}`
- `docs/validation/autodev_pypi_rc_release_gate_final.{md,json}`
- `docs/validation/autodev_pypi_0_1_0a1_rc_publish_prep.{md,json}` ← this aggregator

**Modified** (4 files):
- `pyproject.toml` — +14 classifiers + 5 `[project.urls]`
- `README.md` — pip URL 0.1.0 → 0.1.0a1 + `--pre` documentation
- `dist/*` — rebuilt with new metadata (sha256s captured above)

---

## Validation Commands (Reproducible)

```bash
python --version                                            # 3.12
git status --short                                          # empty
ruff check .                                                # All checks passed!
mypy src/autodev                                            # Success: 0 issues / 171 files
pytest tests/                                               # 1062 passed, 4 xfailed
rm -rf dist build && python -m build                        # success
twine check dist/*                                          # PASSED + PASSED
shasum -a 256 dist/*                                        # final hashes
python scripts/release_readiness_gate.py                    # 36 pass / 0 fail / 0 skip
python scripts/release_readiness_gate.py --strict           # exit 0
python scripts/release_readiness_gate.py --strict-r2        # exit 0
python scripts/release_readiness_gate.py --strict-r3        # exit 0
python scripts/release_readiness_gate.py --strict-rc        # exit 0
python -m autodev.release_readiness_gate                    # exit 0
```

---

## Quality Red Lines Upheld

- ❌ Did NOT actually publish to PyPI (no twine upload from this prep round)
- ❌ Did NOT create a real `v0.1.0a1` git tag (preserved for user action)
- ❌ Did NOT push any tag to origin
- ❌ Did NOT fabricate `PYPI_API_TOKEN` presence (explicitly documented as user step 1)
- ❌ Did NOT write `Homebrew pending` as `Homebrew ready` (formula carries `BLOCKED` comment + placeholder sha256)
- ❌ Did NOT write `RC ready` as `already published` (every published-state claim is conditional on the user action)
- ❌ Did NOT skip pytest
- ❌ Did NOT lower release gate (gate now 36 checks vs R3's 36; same coverage maintained)
- ❌ Did NOT leak any secret (token never logged, never persisted, conditional twine upload only)
- ❌ Did NOT reuse a released version (0.1.0a1 is fresh; 0.1.0 was the placeholder pre-PEP-440 string in earlier rounds, never published)
- ❌ Did NOT promote production_enterprise_use to anything but `blocked`
- ❌ Did NOT write only the aggregator (5 RC sub-reports + 2 release docs + 1 aggregator)

---

## Recommended Next Step — User-Driven

1. Set `PYPI_API_TOKEN` GitHub secret (~2 min)
2. Read `docs/release_notes/v0.1.0a1.md` end-to-end (~5 min) and edit if anything reads wrong
3. Push the tag per `docs/release/pypi_0_1_0a1_publish_checklist.md` Section B
4. After PyPI publish + GitHub Release: run Section C verification + Section 5 Homebrew sha256 patch

## Recommended Next Round — R4 Enterprise Hardening (after publish)

| Task | Effort | Unblocks |
|---|---|---|
| SLSA provenance via cosign on Docker images | 2 hr | enterprise + supply-chain |
| SBOM generation in release.yml (syft / cyclonedx) | 1 hr | enterprise + compliance |
| Per-caller MCP auth (bearer / OAuth) | 4 hr | multi-tenant MCP |
| Egress sandbox docs for codex/claude shells | 1 hr | enterprise threat model |
| Switch twine upload to `TWINE_PASSWORD` env var | 5 min | LOW finding cleanup |
| Move MCP audit log default off /tmp + mode 0600 | 30 min | audit log integrity |
| WorkerIsolator fd-pin alternative for atomic cleanup | 4 hr | cleanup race elimination |
| Apple Developer ID signing for macOS .app launcher | 2 hr | macOS distribution |
