# Updating the Docker Base Image Digest

The `Dockerfile` pins the `python:3.12-slim` base image by its sha256 digest to ensure
fully reproducible builds. Floating tags like `python:3.12-slim` can change without
notice; a digest pin guarantees you always build from exactly the same layer tree.

## When to Update

Update the pinned digest when:

- A new Python **patch release** is published (e.g. 3.12.x → 3.12.x+1) and you want
  the latest bugfixes or stdlib improvements.
- A **CVE fix** is published in the base image (check Docker Hub security advisories or
  `docker scout cves python:3.12-slim`).
- Routine **quarterly refresh** to pick up accumulated OS-level security patches.

## Commands to Fetch the New Digest

```bash
# 1. Pull the latest tag to refresh the local manifest
docker pull python:3.12-slim

# 2. Read back the canonical digest reference
docker inspect python:3.12-slim --format '{{index .RepoDigests 0}}'
# Example output: python@sha256:401f6e1a67dad31a1bd78e9ad22d0ee0a3b52154e6bd30e90be696bb6a3d7461
```

The output is already in the `<image>@sha256:<hash>` form ready to paste.

## Where to Update

Open `packaging/docker/Dockerfile` and replace **both** `FROM` lines (builder stage and
runtime stage) with the new digest string obtained above. Both stages must use the same
digest so the layer cache is shared and the two stages are identical.

```dockerfile
# Before
FROM python@sha256:<old-digest> AS builder
...
FROM python@sha256:<old-digest>

# After
FROM python@sha256:<new-digest> AS builder
...
FROM python@sha256:<new-digest>
```

Also update the digest recorded in `docs/validation/autodev_r3_docker_digest_pinning.md`
and its companion `.json` file so the audit trail stays current.

## How to Test

After updating the digest, verify the image builds successfully:

```bash
# Build from the packaging/docker directory (wheel must exist in dist/ first)
docker build packaging/docker/ -t autodev-x:digest-update-smoke

# Run the unit test suite to confirm the new digest passes structural checks
.venv/bin/python -m pytest tests/unit/test_docker_digest_pinning.py -v
```

A passing build plus green tests confirms the new digest is valid and the Dockerfile
is well-formed.

## Notes

- Never use a floating tag (`python:3.12-slim` without `@sha256:`) in a production
  `Dockerfile`. Tags are mutable; digests are immutable content addresses.
- The digest changes even for security-only rebuilds of the same tag, so always
  re-fetch rather than copying a digest from an old document.
- The `docker scout` CLI (available as a Docker Desktop plugin) can show you whether
  the currently pinned digest has any known CVEs before you decide to update.
