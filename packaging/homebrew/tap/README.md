# merchloubna70-dot/homebrew-autodev tap

Homebrew tap for [autodev-x](https://github.com/merchloubna70-dot/autodev-x).

## Install

```bash
brew tap merchloubna70-dot/autodev
brew install autodev-x
```

## Status

Pre-release alpha. Formula tracks the latest published PyPI version
(currently 0.1.0a2). Use `pip install --pre autodev-x` for fine-grained
version control.

## Update cadence

After each PyPI publish:
1. Bump `version` to the new PyPI version
2. Update `url` to canonical `files.pythonhosted.org` link
3. Update `sha256` from PyPI metadata
4. Regenerate transitive `resource` blocks via `homebrew-pypi-poet`
5. `brew audit --strict autodev-x`
6. Commit + push

## Source

The canonical formula lives in the autodev-x repo at
`packaging/homebrew/Formula/autodev-x.rb`. This tap mirrors it.

## License

MIT (same as autodev-x).
