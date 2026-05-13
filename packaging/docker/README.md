# autodev-ai Docker Image

## Build locally

```bash
bash packaging/docker/build.sh
```

## Pull from GHCR

```bash
docker pull ghcr.io/macworkers/autodev-ai:latest
```

## Run

```bash
# Basic help
docker run --rm ghcr.io/macworkers/autodev-ai:latest --help

# Deliver a project with a brief file in the current directory
docker run --rm \
    -v $PWD:/workspace \
    ghcr.io/macworkers/autodev-ai:latest \
    deliver-project --project-brief brief.md --mode dry-run
```

## codex + claude CLI dependency

`codex` (`@openai/codex`) and `claude` (`@anthropic-ai/claude-code`) are **NOT bundled**
in the image by default because of license and binary-size constraints. The Dockerfile
attempts a best-effort `npm install -g` at build time; if those packages are unavailable
(private registry, network restrictions, etc.) the build still succeeds and the CLIs
simply won't be present.

**Recommended alternatives:**

### Option A — mount binaries from the host

```bash
docker run --rm \
    -v $PWD:/workspace \
    -v $(which codex):/usr/local/bin/codex:ro \
    -v $(which claude):/usr/local/bin/claude:ro \
    ghcr.io/macworkers/autodev-ai:latest --help
```

### Option B — mount config directories

```bash
docker run --rm \
    -v $PWD:/workspace \
    -v ~/.codex:/home/autodev/.codex:ro \
    -v ~/.config/claude:/home/autodev/.config/claude:ro \
    ghcr.io/macworkers/autodev-ai:latest --help
```

### Option C — derive a custom image

```dockerfile
FROM ghcr.io/macworkers/autodev-ai:latest
USER root
RUN npm install -g @anthropic-ai/claude-code @openai/codex
USER autodev
```

## Multi-arch

Images are built for `linux/amd64` and `linux/arm64` via GitHub Actions and pushed
to `ghcr.io/macworkers/autodev-ai` on every `v*.*.*` tag.
