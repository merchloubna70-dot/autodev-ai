# Homebrew Tap for autodev-ai

This directory contains a Homebrew formula for installing `autodev-ai` on macOS.

## Publishing as a tap

```bash
# 1. Create empty GitHub repo: github.com/macworkers/homebrew-autodev-ai
# 2. Copy Formula/autodev-ai.rb into that repo (at the root Formula/ directory)
# 3. Tap and install:
brew tap macworkers/autodev-ai
brew install autodev-ai
```

> Note: The `homepage` and `url` fields in the formula use placeholder GitHub URLs
> (`https://github.com/macworkers/autodev-ai`). Update them to your real GitHub org/repo
> before publishing the tap.

## Local testing (without publishing)

```bash
# Install directly from local formula file (build from source):
brew install --build-from-source ./packaging/homebrew/Formula/autodev-ai.rb

# Or audit the formula for common issues:
brew audit --strict ./packaging/homebrew/Formula/autodev-ai.rb

# Run the built-in test block:
brew test autodev-ai
```

## Updating the formula

When releasing a new version:

1. Update `url` to point at the new release tarball.
2. Run `shasum -a 256 <new-tarball>` and update `sha256`.
3. Re-run `./packaging/homebrew/refresh-resources.sh` to regenerate `resource` blocks for any updated deps.
4. Replace the `resource` blocks in `Formula/autodev-ai.rb` with the fresh output.

## sha256 status

| Source | sha256 status |
|--------|--------------|
| `autodev_ai-0.1.0.tar.gz` (main url) | **Real** — computed from local `dist/` artifact |
| All 10 runtime deps (pydantic, typer, rich, PyYAML, jinja2, click, mdurl, markdown-it-py, pygments, shellingham) | **Real** — fetched live from PyPI JSON API at formula generation time |

No placeholder sha256 values remain in the current formula.
