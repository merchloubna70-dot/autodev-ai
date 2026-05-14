# PyPI Token Rotation Checklist

> **When to do this**: any time a PyPI API token MAY have been exposed.
> **For autodev-x specifically**: the original v0.1.0a2 publish token was pasted into a chat session once. The token was set via `printf | gh secret set` (no file write, no echo, no argv exposure), and the repo audit (R4.5-F) confirmed zero token traces in git-tracked content. As defense-in-depth best practice, rotate.

---

## Why Rotate

| Threat | Was the token exposed to it? | Recommendation |
|---|---|---|
| Token in git history / commit | NO — audit confirmed 0 occurrences | — |
| Token in validation report / log | NO — audit confirmed | — |
| Token in `/proc/<pid>/cmdline` (process listing) | NO — used `printf … \| gh secret set` (stdin pipe) | — |
| Token in shell history | NO (only typed into chat input) | — |
| Token in chat history with the AI assistant | **YES** — it was pasted once | **Rotate** (this checklist) |
| Token in GitHub Actions logs | NO — GitHub auto-masks `secrets.PYPI_API_TOKEN` references in run logs | — |

The chat exposure is the only real residual. Treat it as a "lateral channel" leak: if anyone accesses your chat history (your account, your local cache, OS-level forensics), they'd see it. **Rotating eliminates that risk class.**

---

## Step-by-Step

### 1. Generate a new project-scoped token (preferred — minimum privilege)

The original token was **Entire account** scope (necessary for first publish since the project didn't exist on PyPI yet). Now that `autodev-x 0.1.0a2` is published, you can scope a new token to JUST that project.

1. Go to https://pypi.org/manage/account/token/
2. Click **Add API token**
3. Token name: `autodev-x-project-scoped`
4. Scope: dropdown → **Project: autodev-x** (now available since the project exists)
5. **Create token**
6. Copy the new `pypi-...` value — **page closes = token lost**

### 2. Update the GitHub repo secret (via `gh` CLI, stdin pipe)

Open a terminal on your local machine (DO NOT paste the token into chat or any file):

```bash
printf '%s' '<paste the new pypi-... token here>' | \
  gh secret set PYPI_API_TOKEN --repo merchloubna70-dot/autodev-x

# Verify (name only — value is invisible to API by design):
gh api repos/merchloubna70-dot/autodev-x/actions/secrets \
  --jq '.secrets[] | "\(.name)  updated=\(.updated_at)"'
# Expected output: PYPI_API_TOKEN  updated=<ISO timestamp of right now>
```

The `printf | gh secret set` form keeps the token in stdin only — never in `argv` (`ps aux`), never in shell history (if you have `setopt HIST_IGNORE_SPACE` then prefix the line with a space), never in any file.

### 3. Revoke the OLD token on PyPI

1. Go to https://pypi.org/manage/account/token/
2. Find the token named `autodev-x-publish` (the original, Entire account scope)
3. Click **Remove**
4. Confirm

This burns the old token. Any process that still has it cached can no longer use it.

### 4. Verify the new token works (next publish)

The next time you `git push origin v0.1.0aN` for some new version, `release.yml`'s `twine upload` step will use the NEW token. If it fails with 401, the secret wasn't updated correctly — re-run step 2.

You don't need to re-publish v0.1.0a2 to test this — the gate is idempotent.

---

## Anti-Patterns (Do Not Do)

- ❌ Paste the new token back into chat to verify (chat is the original leakage channel)
- ❌ Write the token into any file in the repo (even `.env` or `.gitignore`-ed)
- ❌ Use `gh secret set --body '<token>'` (token would briefly appear in `/proc/<pid>/cmdline`)
- ❌ `echo $PYPI_TOKEN > somewhere` (token persists on disk)
- ❌ Skip step 3 (revoking old token) — leaving it valid means the original leak channel still has live credentials
- ❌ Use a single account-wide token long-term (use project-scoped per PyPI minimum-privilege guidance)

## When to Do This Round Again

Anytime:
- Token has been visible in any other context (CI log, terminal screenshot, support session)
- A team member with token access leaves
- 90 days have passed (general best practice for long-lived bearer credentials)
- You see a `pip install autodev-x==<unexpected-version>` published from an unknown source

---

## State of Rotation (this round)

- **Old token (chat-exposed)**: STILL ACTIVE (not yet revoked)
- **New token**: NOT YET CREATED
- **Recommendation**: do the 4 steps above when convenient (5 minutes)
- **autodev-x release pipeline status**: works with current token; rotation is hygiene, not blocking
