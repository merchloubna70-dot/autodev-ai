# R5-C — Homebrew Tap Asset Preparation

**Verdict: `tap_assets_staged_user_action_pending`**

## Staged

Created `packaging/homebrew/tap/`:

```
packaging/homebrew/tap/
├── Formula/
│   └── autodev-ai.rb       (identical mirror of packaging/homebrew/Formula/autodev-ai.rb)
└── README.md               (tap-side README with brew tap + brew install instructions)
```

The tap dir is a 1:1 staging copy of what `merchloubna70-dot/homebrew-autodev` repo should contain after publish. It's NOT a separate copy of the formula — it's a mirror that gets updated in lockstep with the canonical formula.

## Formula state (verified earlier rounds)

| Field | Value | Verified |
|---|---|---|
| version | 0.1.0a2 | ✅ matches PyPI |
| url | canonical PyPI files.pythonhosted.org | ✅ |
| sha256 | `246f5f60810c…` | ✅ R4.5-D + R5-D (independent download + shasum) |
| 9 transitive resource sha256s | all match upstream | ✅ R5-D |

## Why not auto-create the tap repo

Creating a public GitHub repo under a user's namespace is a **non-reversible, visible-to-others action**. Per CLAUDE.md guidance: "Actions visible to others or that affect shared state ... by default transparently communicate the action and ask for confirmation before proceeding."

So I staged the artifacts but did NOT create the remote repo. The user runs ~3 commands (web UI to create empty repo + `git init/add/commit/remote add/push` from `packaging/homebrew/tap/`).

## To Publish (user action)

See `docs/release/homebrew_tap_publish_checklist.md` for the full 4-step procedure. Summary:

1. Create `merchloubna70-dot/homebrew-autodev` repo on github.com (Public, empty)
2. `cd packaging/homebrew/tap && git init && git add . && git commit && git remote add origin … && git push -u origin main`
3. `brew tap merchloubna70-dot/autodev && brew install autodev-ai`
4. `brew test autodev-ai`

After step 3 lands successfully, users can:
```bash
brew tap merchloubna70-dot/autodev
brew install autodev-ai
autodev --version    # → autodev-ai 0.1.0a2
```

## Limitations

- Tap repo doesn't exist yet — `brew tap merchloubna70-dot/autodev` will fail until step 1
- Cannot run end-to-end `brew install autodev-ai` smoke until tap exists
- 9 transitive resource sha256s verified (R5-D), but full Homebrew virtualenv build not exercised this round (would require the tap to be live)
