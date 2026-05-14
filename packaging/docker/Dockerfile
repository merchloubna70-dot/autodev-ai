# Base image pinned by digest for reproducibility. Update: see packaging/docker/UPDATE.md
# Stage 1: builder — install wheel into /install
FROM python@sha256:401f6e1a67dad31a1bd78e9ad22d0ee0a3b52154e6bd30e90be696bb6a3d7461 AS builder

WORKDIR /build

# Copy the pre-built wheel. Glob pattern survives version bumps.
COPY dist/autodev_x-*.whl /tmp/wheels/

# Install into isolated target directory (no venv overhead).
RUN pip install --no-cache-dir --target /install /tmp/wheels/autodev_x-*.whl \
    && rm -rf /tmp/wheels

# Stage 2: runtime — lean final image
# Base image pinned by digest for reproducibility. Update: see packaging/docker/UPDATE.md
FROM python@sha256:401f6e1a67dad31a1bd78e9ad22d0ee0a3b52154e6bd30e90be696bb6a3d7461 AS final

# Install Node.js (for claude/codex CLIs via npm) — best-effort; binaries
# can also be volume-mounted from the host (see README.md for details).
# If npm-based CLIs are unavailable in your environment, remove the
# apt/npm block and mount the binaries via -v /usr/local/bin/claude:/usr/local/bin/claude:ro
RUN apt-get update && apt-get install -y --no-install-recommends \
        nodejs \
        npm \
    && npm install -g @anthropic-ai/claude-code 2>/dev/null || true \
    && npm install -g @openai/codex 2>/dev/null || true \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder stage
COPY --from=builder /install /usr/local/lib/python3.12/site-packages

# Ensure scripts (e.g. the `autodev-x` console-script entry-point) are on PATH
# pip --target drops scripts into /install/bin; expose them.
COPY --from=builder /install/bin /usr/local/bin

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash autodev

WORKDIR /workspace

# Make the workspace writable by the autodev user
RUN chown autodev:autodev /workspace

ENV PYTHONPATH=/usr/local/lib/python3.12/site-packages

USER autodev

# Healthcheck: verify the CLI is reachable
# autodev-x --version exits 0 when __version__ is defined
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD autodev-x --version || exit 1

ENTRYPOINT ["autodev-x"]
CMD ["--help"]
