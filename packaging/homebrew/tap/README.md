# merchloubna70-dot/homebrew-autodev tap

Homebrew tap for [autodev-ai](https://github.com/merchloubna70-dot/autodev-ai).

## Install

```bash
brew tap merchloubna70-dot/autodev
brew install autodev-ai
```

## Status

Pre-release alpha. Formula tracks the latest published PyPI version
(currently 0.1.0a2). Use `pip install --pre autodev-ai` for fine-grained
version control.

## Update cadence

After each PyPI publish:
1. Bump `version` to the new PyPI version
2. Update `url` to canonical `files.pythonhosted.org` link
3. Update `sha256` from PyPI metadata
4. Regenerate transitive `resource` blocks via `homebrew-pypi-poet`
5. `brew audit --strict autodev-ai`
6. Commit + push

## Source

The canonical formula lives in the autodev-ai repo at
`packaging/homebrew/Formula/autodev-ai.rb`. This tap mirrors it.

## License

MIT (same as autodev-ai).
