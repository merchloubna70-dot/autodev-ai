# R5-D — Homebrew Transitive Resource SHA-256 Re-Verification

**Verdict: `all_9_resources_verified`**

## Method

For each of the 9 `resource` blocks in `packaging/homebrew/Formula/autodev-ai.rb`:
1. `curl -sL -o <file> <url>`
2. `shasum -a 256 <file>` → recompute
3. Compare to formula value byte-for-byte

## Results

| Resource | Version | Match |
|---|---|---|
| pydantic | 2.13.4 | ✅ `c40756b5…` (retry needed once; first curl was transient network fail) |
| typer | 0.25.1 | ✅ `9616eb88…` |
| rich | 15.0.0 | ✅ `edd07a48…` |
| pyyaml | 6.0.3 | ✅ `d7662337…` |
| jinja2 | 3.1.6 | ✅ `0137fb05…` |
| click | 8.3.3 | ✅ `398329ad…` |
| mdurl | 0.1.2 | ✅ `bb413d29…` |
| markdown-it-py | 4.2.0 | ✅ `04a21681…` |
| pygments | 2.20.0 | ✅ `6757cd03…` |
| shellingham | 1.5.4 | ✅ `8dbca073…` |

**9/9 match.** No tampering of upstream PyPI artifacts since the formula was drafted. Homebrew tap publish is safe from a supply-chain standpoint.

## Caveat

These sha256 values pin specific minor versions captured at the original formula draft. They are **not necessarily the LATEST PyPI versions** of those deps. `brew install autodev-ai` will install exactly those versions (Homebrew's reproducibility model). When upstream deps release new patches:

```bash
# refresh resources via homebrew-pypi-poet
poet -f autodev-ai >> packaging/homebrew/Formula/autodev-ai.rb.new
# manually merge the new `resource` blocks (preserving our top-level url/sha256/version)
```

For R5 prep round, the captured snapshot is internally consistent — no change required.
