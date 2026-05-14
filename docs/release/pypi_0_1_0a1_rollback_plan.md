# autodev-x v0.1.0a1 — Rollback Plan

**Version:** 0.1.0a1
**PyPI project:** `autodev-x`
**GitHub repo:** `merchloubna70-dot/autodev-x`
**Prepared:** 2026-05-14

> This plan covers what to do if v0.1.0a1 must be pulled after it has been
> published to PyPI. Read the entire document before executing any command.
> Decision authority rests with the release engineer; no automated system
> should run these steps.

---

## Section A: When to Roll Back

Initiate rollback if ANY of the following conditions is true:

1. **Install failure on a supported Python version.**
   `pip install --pre autodev-x==0.1.0a1` fails on a clean venv running
   CPython 3.10, 3.11, or 3.12 on a supported platform (Linux x86_64,
   macOS arm64, macOS x86_64, Windows x86_64).

2. **Entry-point crash.**
   `autodev --help` exits non-zero or produces no `Usage:` prefix on a clean install.

3. **CRITICAL security finding post-publish.**
   A vulnerability rated CRITICAL (CVSS ≥ 9.0) is discovered in code or
   dependencies shipped inside the wheel, AND a patch cannot be published
   within the response window agreed with affected parties.

4. **HIGH-severity issue within 24–72 hours.**
   Any HIGH-severity defect (data corruption, auth bypass, silent data loss,
   or crash-on-startup) discovered within 72 hours of the publish timestamp.

5. **Checksum or supply-chain discrepancy.**
   The sha256 of the artifact served by PyPI does not match the value recorded
   in Section A-3 of the publish checklist.

If the issue is cosmetic, documentation-only, or a minor behavioural regression
with a known workaround, prefer publishing a fix as `0.1.0a2` without yanking —
see Section D (Forward-only fix policy).

---

## Section B: PyPI Yank Procedure

> PyPI does NOT delete published files. Yanking marks the version as
> "do not install" for dependency resolvers that respect PEP 592, but any
> user who has already pinned `autodev-x==0.1.0a1` in a lock file will
> continue to download the yanked artifact. Yanking is the correct and
> safe first response — it stops new installs without breaking existing
> pinned environments.

**Option 1 — twine CLI (preferred for auditability):**
```bash
# Replace <short reason> with a plain-English description, e.g.:
#   "install crash on Python 3.10 – see GitHub issue #42"
twine yank --reason "<short reason>" autodev-x==0.1.0a1
```
`twine yank` requires the same credentials used to upload (either the
`PYPI_API_TOKEN` or a local `~/.pypirc` entry for the `autodev-x` project).

**Option 2 — PyPI web UI:**
1. Log in to https://pypi.org with the project owner account.
2. Navigate to:
   ```
   https://pypi.org/manage/project/autodev-x/release/0.1.0a1/
   ```
3. Click **Options** → **Yank this release**.
4. Enter the reason string and confirm.

**Confirm the yank took effect:**
```bash
pip index versions autodev-x --pre
```
Yanked versions appear with a `[YANKED]` suffix in the output.
The version must remain visible (not absent) — absence would indicate
deletion which is not possible on PyPI.

---

## Section C: GitHub Release Rollback

After yanking on PyPI, remove the GitHub Release that was created by the
workflow. This prevents new users from downloading the release assets directly
from GitHub.

```bash
# Delete the GitHub Release (not the git tag — see warning below).
gh release delete v0.1.0a1 --yes --repo merchloubna70-dot/autodev-x
```

> **WARNING — Do NOT delete the git tag `v0.1.0a1`.**
>
> Deleting a tag that has been pushed to the shared remote rewrites the
> shared history reference and can cause confusion for anyone who has
> already fetched it. More importantly, if you intend to publish a
> fix-up release (0.1.0a2), leaving the `v0.1.0a1` tag in place preserves
> the exact commit that was released, which is valuable for debugging.
>
> The only scenario where deleting the tag is justified is if the commit
> itself must be expunged (e.g., a secret was committed). Even then,
> coordinate with all contributors before doing so.

---

## Section D: Forward-Only Fix Policy

PyPI permanently records the `0.1.0a1` version slot and the immutable sha256
hashes uploaded to it. Even after a yank, those hashes remain on record.
**Do not attempt to reuse the `0.1.0a1` version string for a different set of
artifacts** — PyPI will reject the upload, and the attempt itself signals a
process failure to downstream users.

The correct procedure after a yank is:

1. Fix the defect in source code.
2. Bump `version` in `pyproject.toml`:
   ```toml
   version = "0.1.0a2"
   ```
3. Add a `## [0.1.0a2]` section to `CHANGELOG.md` that includes a
   `### Fixed` entry referencing the yank reason.
4. Rebuild the distribution:
   ```bash
   python -m build
   ```
5. Run `python scripts/release_readiness_gate.py --strict-rc` and confirm
   `36/36` passes against the new artifacts.
6. Follow `docs/release/pypi_0_1_0a1_publish_checklist.md` from Section A
   again, substituting `0.1.0a2` everywhere `0.1.0a1` appears.

---

## Section E: Docker / ghcr Rollback

The Docker image published alongside the release is stored at:
```
ghcr.io/merchloubna70-dot/autodev-x:0.1.0a1
```

Individual image layers pushed to ghcr.io are **immutable by digest**.
The `:0.1.0a1` tag itself cannot be deleted via the API without registry
admin access, but the rolling `:latest` pointer can be moved immediately.

**Repoint `:latest` to the previous known-good image:**
```bash
# Find the digest of the last known-good build.
# Replace <previous-sha> with the sha256 digest from the prior release
# (check the GitHub Packages page or your release log).
docker pull ghcr.io/merchloubna70-dot/autodev-x@sha256:<previous-sha>
docker tag  ghcr.io/merchloubna70-dot/autodev-x@sha256:<previous-sha> \
            ghcr.io/merchloubna70-dot/autodev-x:latest
docker push ghcr.io/merchloubna70-dot/autodev-x:latest
```

Users who pin to `:latest` will receive the previous good image on their
next `docker pull`. Users who pin to `:0.1.0a1` will continue to receive
the recalled image until they update their pin — communicate clearly in
the recall notice (Section F) that they must change their pin.

---

## Section F: Notifications

Complete all notification steps **within 2 hours of the yank**.

- [ ] **F-1 Open a GitHub Issue**

  Title format:
  ```
  [v0.1.0a1 RECALLED] <one-line reason>
  ```
  Body must include:
  - The yank reason (same text passed to `twine yank --reason`).
  - A link to the PyPI release page confirming the `[YANKED]` status.
  - A link to the planned fix version (`0.1.0a2`) if the fix PR is already open.
  - Affected platforms and Python versions, if known.

- [ ] **F-2 Update CHANGELOG**

  In `CHANGELOG.md`, add a **Yanked** note directly under the `## [0.1.0a1]`
  heading. Do **not** delete the section. Example:

  ```markdown
  ## [0.1.0a1] — 2026-05-14 [YANKED]

  > **Yanked** on <date>. Reason: <reason>. Use `0.1.0a2` or later.

  ### Added
  ...original content unchanged...
  ```

- [ ] **F-3 Announce through appropriate channels**

  Announce the recall on whichever channels were used to promote the release
  (Slack workspace, Mastodon/Twitter/X, mailing list, Discord). The announcement
  must include:
  - What is recalled and why.
  - What users should do (remove the pin, wait for `0.1.0a2`).
  - Expected timeline for the fix.

- [ ] **F-4 Update internal status tracking**

  If your team uses a release tracker (Linear, Jira, Notion, GitHub Project),
  mark the `0.1.0a1` release card as `RECALLED` and link the GitHub Issue
  from F-1.

---

## Quick-Reference Decision Tree

```
Defect discovered after publish
        │
        ├─ Severity < HIGH and workaround exists?
        │         └─ Publish 0.1.0a2 with fix. No yank. Annotate CHANGELOG.
        │
        └─ Severity HIGH/CRITICAL, install fails, or supply-chain issue?
                  │
                  ├─ 1. Yank PyPI (Section B)
                  ├─ 2. Delete GitHub Release (Section C — keep the tag)
                  ├─ 3. Repoint :latest Docker tag (Section E)
                  ├─ 4. Notify (Section F)
                  └─ 5. Publish 0.1.0a2 with fix (Section D)
```

---

*This file is write-once documentation. Do not modify after rollback is complete
(except to add the post-incident summary at the bottom of this file).*

---

## Post-Incident Summary (fill in if rollback was executed)

| Field | Value |
|---|---|
| Recall initiated by | |
| Recall timestamp | |
| Reason | |
| PyPI yank confirmed | |
| GitHub Release deleted | |
| Docker :latest repointed | |
| Notifications sent | |
| Fix version | |
| Fix published | |
| Incident closed | |
