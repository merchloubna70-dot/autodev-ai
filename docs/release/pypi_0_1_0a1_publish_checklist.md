# autodev-ai v0.1.0a1 — PyPI Publish Checklist

**Version:** 0.1.0a1
**PyPI project:** `autodev-ai`
**GitHub repo:** `mechloubna70-dot/autodev-ai`
**Prepared:** 2026-05-14
**Status:** READY TO EXECUTE (release engineer sign-off required before each command)

> This checklist is single-use. Work through it top-to-bottom, one step at a time.
> Mark each step `[x]` as you complete it. Do **not** skip ahead.

---

## Section A: PRE-PUBLISH (preflight, ~5 min)

Complete ALL six steps before issuing any publish command.
If any step fails, STOP and resolve before continuing.

- [ ] **A-1 Verify GitHub Secret `PYPI_API_TOKEN`**

  Navigate to:
  ```
  https://github.com/merchloubna70-dot/autodev-ai/settings/secrets/actions
  ```
  Confirm `PYPI_API_TOKEN` appears in the repository secrets list.

  - The token must have **`pypi-autodev-ai` project scope** or be an account-wide
    token with permission to upload to the `autodev-ai` project on PyPI.
  - If the secret is absent: **STOP.** Add it before continuing. Generate a new API
    token at https://pypi.org/manage/account/token/ and paste it as the secret value.

- [ ] **A-2 Confirm release readiness gate (strict-RC) passes**

  Run from the repository root:
  ```bash
  python scripts/release_readiness_gate.py --strict-rc
  echo "exit=$?"  # must be 0
  ```
  Expected output: `36/36 checks passed` with `exit=0`.
  If exit is non-zero: **STOP.** Review the failing check output and resolve.

- [ ] **A-3 Confirm artifact sha256 checksums**

  ```bash
  shasum -a 256 dist/*
  ```
  Cross-check each line against the expected values below.
  The comparison must be **exact, character-for-character**.

  | Artifact type | Expected sha256 |
  |---|---|
  | wheel (`.whl`) | `5f5b51045d22dbbc91c1eeb0f521e0bb54df103a57f8e3065a2fbb3fa6e59205` |
  | sdist (`.tar.gz`) | `243c9fc2ef13df961c76e4021c58a88107fcf4af69bab1810c4938890f48980d` |

  If either hash differs: **STOP.** The `dist/` contents may have been regenerated
  after the gate ran. Re-run the gate and re-confirm checksums before continuing.

- [ ] **A-4 Confirm tag name is free**

  ```bash
  git tag -l v0.1.0a1
  ```
  The command must return **empty output** (no lines).
  If `v0.1.0a1` already exists: **STOP.** A tag name collision means a previous
  release attempt may have partially succeeded. Investigate before proceeding.

- [ ] **A-5 Confirm release notes draft**

  ```bash
  cat docs/release_notes/v0.1.0a1.md
  ```
  Read through the output. Confirm it accurately reflects the current build:
  - Feature list is complete.
  - Known-issues section is up to date.
  - No placeholder text (`TODO`, `TBD`, `FIXME`) remains.

  If notes are incomplete: update `docs/release_notes/v0.1.0a1.md` before continuing.

- [ ] **A-6 Confirm CHANGELOG `## [0.1.0a1]` section is final**

  ```bash
  grep -n "0.1.0a1" CHANGELOG.md | head -5
  ```
  Confirm the section exists and the content is final.
  The heading **must not** appear as `## [Unreleased]` or contain draft markers.

---

## Section B: PUBLISH COMMANDS

Execute in order. Each command is self-contained; read the inline comment before running.

```bash
# B-1. Final preflight: working tree must be clean before tagging.
# Any uncommitted change here is a sign something was modified after the gate ran.
git status --short
# Expected output: empty (no lines). If not empty, STOP.
```

```bash
# B-2. Create the annotated tag.
# If your GPG signing key is configured, add -s to produce a signed tag.
# Omit -s if no GPG key is available — an unsigned annotated tag is acceptable for an alpha.
git tag -a v0.1.0a1 -m "autodev-ai v0.1.0a1 — first PyPI RC"
```

```bash
# B-3. Push the tag to origin.
# This push event triggers .github/workflows/release.yml which builds,
# uploads to PyPI, and creates the GitHub Release.
git push origin v0.1.0a1
```

```bash
# B-4. Watch the workflow run live until it completes.
# The command blocks until the run finishes and prints the result.
gh run watch --repo merchloubna70-dot/autodev-ai
# Expected final status: "completed" with conclusion "success".
# If it fails, see the Rollback Plan before taking any further action.
```

```bash
# B-5. After the workflow shows green, verify the version is visible on PyPI.
pip index versions autodev-ai --pre
# Expected output includes: 0.1.0a1
# Note: PyPI CDN propagation can take 1-2 min after the upload job completes.
```

---

## Section C: POST-PUBLISH VERIFY

Complete all ten steps. Record actual output next to each step as evidence.

- [ ] **C-1 Install in a fresh virtual environment**

  ```bash
  python3 -m venv /tmp/autodev-verify-venv
  source /tmp/autodev-verify-venv/bin/activate
  pip install --pre autodev-ai==0.1.0a1
  ```
  Test against Python 3.10, 3.11, and 3.12 if possible.
  A failure on any supported minor version is a rollback trigger.

- [ ] **C-2 Check installed version via CLI entry point**

  ```bash
  autodev --version
  ```
  Expected output (exact):
  ```
  autodev-ai 0.1.0a1
  ```

- [ ] **C-3 Confirm help text is present**

  ```bash
  autodev --help
  ```
  Expected: output begins with `Usage:` prefix.
  A crash or empty output here is a rollback trigger.

- [ ] **C-4 Check version via module invocation**

  ```bash
  python -m autodev.cli --version
  ```
  Expected output (exact):
  ```
  autodev-ai 0.1.0a1
  ```
  Must match C-2 exactly.

- [ ] **C-5 Run release readiness gate inside the installed package**

  ```bash
  python -m autodev.release_readiness_gate
  ```
  Expected: `36/36` checks pass.
  Any regression from the pre-publish run is a rollback trigger.

- [ ] **C-6 Record the PyPI artifact URL**

  Open and confirm the page loads:
  ```
  https://pypi.org/project/autodev-ai/0.1.0a1/#files
  ```
  Record the full URL here for audit trail: `_______________`

  Confirm the wheel and sdist are both listed.

- [ ] **C-7 Compute Homebrew sha256 from the PUBLISHED PyPI sdist**

  The sha256 used for the Homebrew formula must come from the bytes actually
  served by PyPI (not the local `dist/` copy) because CDN re-packaging can alter
  byte counts in edge cases.

  ```bash
  curl -L "https://files.pythonhosted.org/packages/source/a/autodev-ai/autodev_ai-0.1.0a1.tar.gz" \
    | shasum -a 256
  ```
  Record the output hash: `_______________`

- [ ] **C-8 Update the Homebrew formula**

  Open `packaging/homebrew/Formula/autodev-ai.rb`.
  Update:
  - `url` → the published PyPI source URL (from C-6 `#files` page, copy the `.tar.gz` link)
  - `sha256` → the value computed in C-7

  Refer to `packaging/homebrew/PUBLISH_CHECKLIST.md` steps 3+ for the full
  formula update procedure, including the `head` block and test stanza.

- [ ] **C-9 Audit the Homebrew formula**

  ```bash
  brew audit --formula packaging/homebrew/Formula/autodev-ai.rb
  ```
  Expected: no errors, no warnings.
  Audit failures must be resolved before the Homebrew tap PR is opened.

- [ ] **C-10 Final gate re-run**

  ```bash
  python scripts/release_readiness_gate.py
  ```
  Expected: `36/36` checks pass.
  The `r3_homebrew_publish_time_blocker_clean` check may auto-pass now that the
  formula carries a valid published URL and sha256. If it still fails, add an
  explicit `# publish_completed: 2026-05-14` comment to the formula file, save,
  and re-run.

---

## Sign-off

| Role | Name | Date | Signature |
|---|---|---|---|
| Release Engineer | | | |
| Reviewer | | | |

---

*This file is write-once documentation. Do not modify after the release is live.*
