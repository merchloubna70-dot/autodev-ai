# autodev-ai Packaging Artifact Audit

**Round:** packaging_audit  
**Date:** 2026-05-14  
**Auditor:** Agent H — Release Hardening  
**Verdict:** `with_caveats`

---

## Verdict Summary

GitHub Release and GHCR Docker push are functional on tag push.
Three **blockers** must be resolved before Homebrew tap and macOS `.app` distribution are safe to ship.
PyPI is currently blocked by a missing secret.

---

## Artifact Inventory

| Artifact | Present | Path | Size | Status |
|---|---|---|---|---|
| Wheel | Yes | `dist/autodev_ai-0.1.0-py3-none-any.whl` | 296 KB | PASS |
| sdist | Yes | `dist/autodev_ai-0.1.0.tar.gz` | 468 KB | PASS |
| PyInstaller binary | Yes | `packaging/pyinstaller/dist/autodev` | ~17 MB | PASS (native arch) |
| Docker image (GHCR) | Not yet pushed | `ghcr.io/merchloubna70-dot/autodev-ai` | N/A | Pending tag push |
| Homebrew formula | Yes | `packaging/homebrew/Formula/autodev-ai.rb` | — | BLOCKED (see F-01, F-02) |
| macOS .app | Yes | `packaging/desktop/autodev-ai.app/` | — | BLOCKED (see F-03) |

### Wheel / sdist verification

- `autodev/cli.py` present in wheel: **YES**
- Entry point `autodev = autodev.cli:app` in `entry_points.txt`: **YES**
- sdist sha256 (local build): `1ad26fcffe17d8cf7a9cbb01faa46fc3d6818e159952b7f8a6f3f4bb0ba59a91`

### PyInstaller

- `autodev_entry.py` exists and correctly wraps `from autodev.cli import app`.
- `autodev.spec` references `autodev_entry.py`; spec was recently fixed (commit history confirms).
- `target_arch=None` (native arch). Universal binary requires separate `build-universal-mac.sh` with two venvs.
- Build script installs `pyinstaller` without a version pin — latent reproducibility risk.

### Docker

- Multi-stage build; builder installs wheel into `/install`.
- Non-root user `autodev` created and set with `USER autodev` before `ENTRYPOINT`.
- Healthcheck: `autodev --version`.
- Platforms declared in workflow: `linux/amd64, linux/arm64`.
- Base image `python:3.12-slim` is a floating tag (no digest pin).
- Node.js / npm install is best-effort (`|| true`) — acceptable.
- Live `docker manifest inspect` failed: image not yet pushed to GHCR.

### Homebrew formula

- URL target: **GitHub Release** (not PyPI) — correct approach.
- **Formula repo owner is `macworkers`**; git remote is `merchloubna70-dot`. URL will 404.
- **sha256 in formula** (`744375fb...`) does **not match** local sdist (`1ad26fcf...`). Additionally, the CI-built release sdist will have a different sha256 than the local build anyway.
- Resource blocks (pydantic, typer, rich, etc.) are all pinned to specific versions with sha256s — good.

### macOS .app

- `CFBundleExecutable = launcher`; `Contents/MacOS/launcher` exists — path is consistent.
- Launcher delegates to `~/bin/autodev-ai-open.sh` installed by `install.sh`.
- **`CFBundleShortVersionString = 1.0`** and **`CFBundleVersion = 1.0`** — should be `0.1.0`.
- No codesigning; quarantine removed by `install.sh` via `xattr -dr`.

---

## Version Consistency

| Source | Version |
|---|---|
| `pyproject.toml` | `0.1.0` |
| git tag | `v0.1.0-alpha` |
| GitHub Release title | `v0.1.0-alpha` (auto-generated) |
| GHCR tag (expected from semver pattern) | `0.1.0-alpha` |
| Homebrew formula URL | `v0.1.0` |
| Info.plist | `1.0` |
| **Consistent?** | **NO** |

The `v0.1.0-alpha` tag emits GHCR tag `0.1.0-alpha` (not `0.1.0`) while the wheel installs as `0.1.0`. This is acceptable for a pre-release workflow but must be documented. The `.app` version `1.0` is the primary inconsistency that needs fixing.

---

## Reproducibility Assessment

| Check | Result |
|---|---|
| Docker base image pinned by digest | NO (`python:3.12-slim` floating tag) |
| PyInstaller version pinned | NO (`pip install pyinstaller` with no constraint) |
| Homebrew resources pinned | YES (all have explicit version + sha256) |
| Checksums file for dist/ | NO |

---

## Publishable Status

| Channel | Ready | Notes |
|---|---|---|
| PyPI | NO | `PYPI_API_TOKEN` secret not set; step guarded by `if: env.PYPI_API_TOKEN != ''` |
| Docker GHCR | YES | Triggers on `v*.*.*` tag push; `GITHUB_TOKEN` has `packages: write` |
| Homebrew | NO | Two blockers: wrong owner + sha256 mismatch |
| GitHub Release | YES | `release.yml` attaches `dist/*` via `softprops/action-gh-release@v2` |

---

## Findings

### F-01 — BLOCKER: Homebrew formula sha256 mismatch

Formula `sha256` does not match the local sdist, and will diverge further because CI rebuilds the sdist fresh. `brew install` will reject the download with a checksum error.

**Fix:** After the CI release build completes and uploads the sdist to the GitHub Release, compute `shasum -a 256 autodev_ai-0.1.0.tar.gz` on the downloaded file and update `Formula/autodev-ai.rb`. Consider using `refresh-resources.sh` or `homebrew-pypi-poet` to regenerate the full formula atomically post-release.

---

### F-02 — BLOCKER: Homebrew formula URL points at wrong GitHub owner

`url` field uses `github.com/macworkers/autodev-ai` but the git remote is `github.com/merchloubna70-dot/autodev-ai`. The release asset does not exist at the formula URL; `brew install` will 404.

**Fix:** Replace `macworkers` with `merchloubna70-dot` in `url` and `homepage` fields.

---

### F-03 — BLOCKER: Info.plist version mismatch

`CFBundleShortVersionString = 1.0` and `CFBundleVersion = 1.0` in `packaging/desktop/autodev-ai.app/Contents/Info.plist`; pyproject.toml is `0.1.0`. macOS Gatekeeper, Spotlight, and Software Update all read plist version.

**Fix:** Update both keys to `0.1.0`.

---

### F-04 — WARNING: Git tag alpha suffix not reflected in wheel version

Tag `v0.1.0-alpha` causes GHCR tag `0.1.0-alpha` but PyPI version `0.1.0` (release). Semantic mismatch between Docker and PyPI.

**Fix:** Either tag as `v0.1.0` for GA release, or change `pyproject.toml version = "0.1.0a1"` to align with PEP 440 pre-release convention.

---

### F-05 — WARNING: Docker base image not pinned by digest

`FROM python:3.12-slim` uses a floating tag; a silent layer update breaks reproducibility.

**Fix:** Pin to `FROM python:3.12-slim@sha256:<digest>` for hermetic CI builds.

---

### F-06 — WARNING: PyInstaller version not pinned

`build.sh` runs `pip install --quiet pyinstaller` with no version constraint.

**Fix:** Pin to `pip install --quiet "pyinstaller>=6.0,<7"` or add to `requirements-build.txt`.

---

### F-07 — INFO: GHCR multi-arch cannot be verified pre-push

`docker manifest inspect ghcr.io/merchloubna70-dot/autodev-ai:latest` returned an error — image not yet pushed.

**Fix:** After first tag push, run manifest inspect to confirm `linux/amd64` + `linux/arm64` are both listed.

---

### F-08 — INFO: No checksums file for dist artifacts

`dist/` contains wheel and sdist but no `SHA256SUMS`. `build.sh` prints sha256 to stdout but does not write a file.

**Fix:** Add `shasum -a 256 dist/* > dist/SHA256SUMS` as a post-build step.

---

### F-09 — INFO: PyPI badge in README but package not published

README badge links to `https://pypi.org/project/autodev-ai/` but `PYPI_API_TOKEN` secret is not configured.

**Fix:** Either add the secret and publish, or replace the badge with a "coming soon" placeholder until the first PyPI release.

---

## Files Inspected

- `packaging/docker/Dockerfile`
- `packaging/pyinstaller/autodev.spec`
- `packaging/pyinstaller/build.sh`
- `packaging/pyinstaller/build-universal-mac.sh`
- `packaging/pyinstaller/autodev_entry.py`
- `packaging/homebrew/Formula/autodev-ai.rb`
- `packaging/homebrew/refresh-resources.sh`
- `packaging/desktop/autodev-ai.app/Contents/Info.plist`
- `packaging/desktop/autodev-ai.app/Contents/MacOS/launcher`
- `packaging/desktop/install.sh`
- `.github/workflows/docker-publish.yml`
- `.github/workflows/release.yml`
- `dist/autodev_ai-0.1.0-py3-none-any.whl` (zipfile listing + metadata extraction)
- `dist/autodev_ai-0.1.0.tar.gz` (tarfile listing)
- `pyproject.toml`
