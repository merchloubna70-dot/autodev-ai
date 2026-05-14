# R2-G: Homebrew Formula + macOS App Metadata Closure

**Round:** R2 PyPI Release Blocker Closure  
**Agent:** R2-G  
**Date:** 2026-05-14  
**Verdict:** `metadata_corrected_publish_still_blocked`

---

## What Changed

### BLOCKER-PKG-01 — Homebrew formula `homepage` URL
- **Before:** `https://github.com/macworkers/autodev-ai` (wrong org)
- **After:** `https://github.com/merchloubna70-dot/autodev-ai`

### BLOCKER-PKG-02 — Homebrew formula `url`, `sha256`, `version`
- **`url` before:** `https://github.com/macworkers/autodev-ai/releases/download/v0.1.0/autodev_ai-0.1.0.tar.gz`
- **`url` after:** `https://github.com/merchloubna70-dot/autodev-ai/releases/download/v0.1.0-alpha/autodev_ai-0.1.0.tar.gz`
- **`sha256` before:** `744375fb1fcc6b6e02b9f6b53322999dd8486d2cdd666dd1eddb4239847a52da` (stale, fabricated)
- **`sha256` after:** `REPLACE_WITH_PYPI_0_1_0A1_SDIST_SHA256_AT_PUBLISH_TIME` (explicit placeholder)
- **`version` added:** `"0.1.0a1"` (aligned to pyproject.toml)
- **Leading comment added** warning that `brew tap` is blocked until PyPI 0.1.0a1 is live

### BLOCKER-PKG-03 — macOS `.app` `Info.plist` version strings
- **`CFBundleShortVersionString` before:** `1.0`
- **`CFBundleShortVersionString` after:** `0.1.0a1`
- **`CFBundleVersion` before:** `1.0`
- **`CFBundleVersion` after:** `0.1.0a1`
- All other plist keys (CFBundleIdentifier, CFBundleExecutable, CFBundlePackageType, etc.) left intact

---

## sha256 Status

**Strategy chosen:** `placeholder`

The PyPI 0.1.0a1 sdist has not been published. The stale sha256 `744375fb…` was a leftover from an earlier draft and did not correspond to any published artifact. It has been replaced with the explicit string `REPLACE_WITH_PYPI_0_1_0A1_SDIST_SHA256_AT_PUBLISH_TIME`.

**To update after publish:**
```bash
curl -sL https://files.pythonhosted.org/packages/.../autodev_ai-0.1.0a1.tar.gz | sha256sum
# then substitute the 64-hex result into the formula's sha256 field
```

---

## Homebrew Tap Publish Status

**BLOCKED.** `brew tap` / `brew install` must not be attempted until:
1. PyPI 0.1.0a1 sdist is live at `https://pypi.org/project/autodev-ai/0.1.0a1/`
2. The `sha256` placeholder in `packaging/homebrew/Formula/autodev-ai.rb` is replaced with the real hash
3. The `url` is updated to point at the PyPI sdist (recommended) or the verified GitHub Release tarball

---

## Tests Added

`tests/unit/test_homebrew_formula_metadata.py` — 10 tests covering:
- Formula file exists
- `url`/`homepage` contain `merchloubna70-dot` (not `macworkers`)
- Version `0.1.0a1` is present in formula
- Stale sha256 `744375fb…` is absent
- License is `"MIT"`
- Formula has pending-publish warning comment
- sha256 is a valid placeholder or 64-hex hash
- `CFBundleShortVersionString` == `0.1.0a1`
- `CFBundleVersion` == `0.1.0a1`
- Other plist keys remain intact

---

## Verdict

`metadata_corrected_publish_still_blocked`

All three blockers have been corrected at the metadata level. The Homebrew formula is now internally consistent and carries explicit warnings. No false clearance has been issued. The tap publish gate remains hard-blocked on PyPI availability and sha256 replacement.
