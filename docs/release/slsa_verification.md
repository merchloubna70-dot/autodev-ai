# SLSA L3 Provenance Verification

`autodev-ai` publishes **SLSA Level 3** provenance attestations with every
tagged release (`v*.*.*`). This document explains what that means and how to
verify a release artifact as a consumer.

---

## What is SLSA?

[SLSA](https://slsa.dev) (Supply-chain Levels for Software Artifacts) is a
security framework that defines graduated levels of build integrity guarantees:

| Level | What it guarantees |
|-------|--------------------|
| L1 | Build script exists; provenance is documented but self-signed |
| L2 | Hosted build service; provenance signed by the build platform |
| **L3** | **Hardened build; provenance non-forgeable via OIDC ephemeral key** |
| L4 | Hermetic, reproducible builds (not yet widely implemented) |

**L3 is the practical gold standard for open-source projects today.**

---

## Why L3 Matters

At SLSA L3 the provenance is backed by **GitHub Actions OIDC** (OpenID
Connect). When the `slsa-github-generator` reusable workflow runs, GitHub's
OIDC provider mints a short-lived certificate that:

- Identifies the exact **workflow file** (`slsa.yml`) and its **ref/SHA**
- Identifies the **runner** and **repository**
- Is signed by Sigstore's **Fulcio** CA — an ephemeral, publicly-logged key

Because the private key never leaves the ephemeral runner and the certificate
is recorded in the **Rekor** transparency log, no human — not even a
repository owner — can forge a valid provenance for a different commit,
workflow, or repository.

The attestation format is **in-toto** ([in-toto.io](https://in-toto.io)):
a SLSA `provenance` predicate encoded as a JSON envelope signed with DSSE
(Dead Simple Signing Envelope), published as `<artifact>.intoto.jsonl`.

---

## What Gets Attached to Each Release

After a tag push `v*.*.*` the GitHub Release will contain:

```
autodev_ai-0.1.0a3-py3-none-any.whl
autodev_ai-0.1.0a3.tar.gz
autodev_ai-0.1.0a3-py3-none-any.whl.intoto.jsonl
autodev_ai-0.1.0a3.tar.gz.intoto.jsonl
```

The `.intoto.jsonl` files are the signed provenance envelopes — one per
artifact.

---

## One-Command Consumer Verification

Install the verifier:

```bash
# macOS
brew install slsa-framework/tap/slsa-verifier

# Linux — download from https://github.com/slsa-framework/slsa-verifier/releases
```

Verify a wheel:

```bash
slsa-verifier verify-artifact autodev_ai-0.1.0a3-py3-none-any.whl \
  --provenance-path autodev_ai-0.1.0a3-py3-none-any.whl.intoto.jsonl \
  --source-uri github.com/merchloubna70-dot/autodev-ai \
  --source-tag v0.1.0a3
```

A successful verification prints:

```
Verified signature against tlog entry index ... at URL: https://rekor.sigstore.dev/...
Verified build using builder "https://github.com/slsa-framework/slsa-github-generator/...@refs/tags/v2.0.0" at commit <sha>
PASSED: Verified SLSA provenance
```

This attestation proves: **"this wheel was built from `<commit>` by
`.github/workflows/slsa.yml` on a GitHub-hosted runner — any tampering
of the artifact or provenance file will be detected."**

---

## References

- SLSA specification: <https://slsa.dev/spec/v1.0>
- slsa-github-generator: <https://github.com/slsa-framework/slsa-github-generator>
- slsa-verifier: <https://github.com/slsa-framework/slsa-verifier>
- in-toto attestation framework: <https://in-toto.io>
- Sigstore/Rekor transparency log: <https://rekor.sigstore.dev>
