# Homebrew Tap Publish Checklist

> **What this is**: step-by-step to actually expose autodev-ai via Homebrew so users can `brew install autodev-ai`. Today (R5 prep round) the formula is staged at `packaging/homebrew/tap/Formula/autodev-ai.rb` but NO public tap repo exists yet.

## Prerequisites (already done)

- ✅ PyPI 0.1.0a2 published — formula `url` + `sha256` reference canonical artifacts
- ✅ Formula sha256 backfilled (R4.5 verified exact match)
- ✅ 9 transitive resource sha256s re-verified (R5-D, all 9 pass)
- ✅ Tap mirror dir created at `packaging/homebrew/tap/`

## Steps to Actually Publish (user action)

### 1. Create the tap repo on GitHub

```
URL: https://github.com/new
Repository name: homebrew-autodev
Owner: merchloubna70-dot
Visibility: Public
Initialize: README (or leave empty — we'll push README from our staged copy)
```

The repo MUST be named `homebrew-<tapname>`. Homebrew convention: `<user>/homebrew-<name>` → `brew tap <user>/<name>`. So `merchloubna70-dot/homebrew-autodev` → `brew tap merchloubna70-dot/autodev`.

### 2. Push the staged tap content

```bash
# From the autodev-ai repo:
cd /Users/macworkers/autodev/packaging/homebrew/tap

# Initialize a fresh local repo pointing at the new tap remote
git init
git add Formula/autodev-ai.rb README.md
git -c user.email=tap@example.com -c user.name=tap commit -m "feat: initial tap with autodev-ai 0.1.0a2 formula"
git branch -M main
git remote add origin https://github.com/merchloubna70-dot/homebrew-autodev.git
git push -u origin main
```

### 3. Smoke

```bash
brew tap merchloubna70-dot/autodev
brew install autodev-ai
autodev --version    # → autodev-ai 0.1.0a2
brew test autodev-ai
```

If `brew install` fails on a transitive resource sha256, run R5-D's verification script (or `homebrew-pypi-poet -f autodev-ai`) to regenerate the formula's resource blocks.

### 4. Future updates

After each PyPI publish (e.g. 0.1.0a3):
```bash
# In autodev-ai repo: bump packaging/homebrew/Formula/autodev-ai.rb (version + url + sha256)
# Mirror to tap dir: cp packaging/homebrew/Formula/autodev-ai.rb packaging/homebrew/tap/Formula/
# In homebrew-autodev repo: copy + commit + push
```

## What This Round (R5 prep) Does

- ✅ Creates `packaging/homebrew/tap/Formula/autodev-ai.rb` (mirror of the canonical formula)
- ✅ Creates `packaging/homebrew/tap/README.md` (tap-side README)
- ❌ Does NOT create the GitHub tap repo
- ❌ Does NOT push to a tap repo
- ❌ Does NOT execute `brew install` (would require the tap repo to exist)

## Why we're not auto-creating the tap repo

Creating a public repo under the user's namespace is a non-reversible, visible-to-others action. Per CLAUDE.md guidance: "Actions visible to others or that affect shared state ... by default transparently communicate the action and ask for confirmation before proceeding."

The user can run step 1 + step 2 in ~5 minutes when ready. The artifacts are pre-staged so it's copy-paste.

## Verdict

`tap_assets_staged_user_action_pending`
