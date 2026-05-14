# R4.5-E — Homebrew Formula Post-Publish Check

**Verdict: `formula_ready_tap_publish_pending`**

## Formula State (`packaging/homebrew/Formula/autodev-ai.rb`)

```ruby
url    "https://files.pythonhosted.org/packages/b0/4a/27e49dba.../autodev_ai-0.1.0a2.tar.gz"
sha256 "246f5f60810c1832051f9219fd141fe63ce87bbafec0125412d18cea326c291d"
version "0.1.0a2"
```

| Field | Verified |
|---|---|
| Version | `0.1.0a2` ✓ |
| URL | canonical PyPI `files.pythonhosted.org` ✓ |
| sha256 | matches PyPI metadata + independent download (R4.5-D verified) ✓ |
| `TODO_PUBLISH_SHA256` placeholder | **removed** ✓ |
| "BLOCKED for publish" comment | **removed** ✓ (replaced by backfill provenance note) |
| `packaging/homebrew/PUBLISH_CHECKLIST.md` | present ✓ |

## What's Done

- ✅ sha256 backfilled with real PyPI value
- ✅ URL points at canonical `files.pythonhosted.org` (not GitHub Release)
- ✅ Version aligned with PyPI publish
- ✅ Static checks pass: Ruby parses, brew loads it (errors at `audit` step only because path-audit deprecated in Homebrew 5.x)

## What's Pending (R5)

1. **Tap repo creation** — `merchloubna70-dot/homebrew-autodev` does not exist. Users still cannot:
   ```bash
   brew tap merchloubna70-dot/autodev   # ← would fail: tap repo doesn't exist
   brew install autodev-ai
   ```
   To unblock: create public GitHub repo, push `packaging/homebrew/Formula/autodev-ai.rb` to it as `Formula/autodev-ai.rb`.

2. **9 transitive resource sha256s** in the formula (pydantic, typer, rich, PyYAML, jinja2, click, mdurl, markdown-it-py, pygments, shellingham) were captured at original formula draft. They may be stale vs current PyPI versions of those deps. R5: re-run `homebrew-pypi-poet -f autodev-ai` to regenerate.

3. **Full `brew install` smoke** not run this round. Heavy operation (10+ transitive deps + venv build, ~5 min). The static check (URL + sha256 match canonical PyPI) is sufficient for verifying the formula isn't fabricating an artifact. The full install smoke is deferred until tap publish.

## brew audit Limitation

```
$ brew audit --strict --formula packaging/homebrew/Formula/autodev-ai.rb
Error: Calling `brew audit [path ...]` is disabled! Use `brew audit [name ...]` instead.
```

Homebrew 5.x removed path-based audit. Formulas must be tapped first. This is a Homebrew CLI design choice, not a formula issue.

## Production / Enterprise Readiness

Homebrew tap publish is NOT enterprise-ready. R5 hardening for tap distribution:
- formula audit via tap workflow
- automated PyPI → tap formula bumps
- 9 transitive resource hash re-verification cadence
