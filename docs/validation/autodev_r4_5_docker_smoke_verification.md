# R4.5-C — Docker Published Image Smoke

**Verdict: `docker_pull_and_smoke_pass_alpha_image`**

## Smoke

```bash
$ docker logout ghcr.io
Removing login credentials for ghcr.io

$ docker pull ghcr.io/merchloubna70-dot/autodev-ai:v0.1.0a2
Digest: sha256:6d0fb4a571229a30f2fda318a7d5679f0eec4b5dd80cd737dab114847cf65413
Status: Image is up to date for ghcr.io/merchloubna70-dot/autodev-ai:v0.1.0a2

$ docker run --rm ghcr.io/merchloubna70-dot/autodev-ai:v0.1.0a2 --version
autodev-ai 0.1.0a2

$ docker run --rm ghcr.io/merchloubna70-dot/autodev-ai:v0.1.0a2 --help
 Usage: autodev [OPTIONS] COMMAND [ARGS]...   (exit 0)
```

- ✅ Anonymous pull works (no `docker login` needed)
- ✅ Digest captured: `sha256:6d0fb4a571229a30f2fda318a7d5679f0eec4b5dd80cd737dab114847cf65413`
- ✅ `--version` prints `autodev-ai 0.1.0a2`
- ✅ `--help` exits 0

## Multi-arch

Previously confirmed on v0.1.0a1 (linux/amd64 + linux/arm64). The same `docker-publish.yml` workflow path produced v0.1.0a2, so multi-arch coverage is preserved.

## Limitations (alpha image, NOT enterprise-ready)

1. Alpha pre-release — pin to `v0.1.0a2` explicitly; `:latest` is rolling
2. NO SLSA provenance attestation (R5)
3. NO SBOM in image (R5)
4. NOT cosign-signed (R5)
5. Base image (python@sha256:401f6e1a…) is digest-pinned (good); no rotation schedule (R5)

## Production Enterprise — NOT Ready

The image works for development and dogfooding. Enterprise use is **blocked** pending R5 supply-chain hardening:

- cosign/sigstore signature
- SBOM (syft/cyclonedx)
- runtime attestation
- rotation schedule for base image digest
