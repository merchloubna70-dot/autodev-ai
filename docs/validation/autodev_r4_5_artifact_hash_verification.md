# R4.5-D — Published Artifact Hash Verification

**Verdict: `no_tampering_detected_homebrew_safe_to_tap`** — both wheel and sdist sha256 are an **exact** match.

## Computed vs. Expected

```
$ shasum -a 256 autodev_ai-0.1.0a2-py3-none-any.whl autodev_ai-0.1.0a2.tar.gz
4b01686898c225200024a0a0758265792bcbb1b36f3cdc4690b3be3e21778600  autodev_ai-0.1.0a2-py3-none-any.whl
246f5f60810c1832051f9219fd141fe63ce87bbafec0125412d18cea326c291d  autodev_ai-0.1.0a2.tar.gz

Expected (recorded in autodev_post_publish_v0_1_0a2_round.json):
wheel: 4b01686898c225200024a0a0758265792bcbb1b36f3cdc4690b3be3e21778600
sdist: 246f5f60810c1832051f9219fd141fe63ce87bbafec0125412d18cea326c291d
```

Both **EXACT match**.

## Sources

- wheel: https://files.pythonhosted.org/packages/7a/14/855ac0890d696276bde36fea2eeea798e12201c6e77347c8af1a20e9a1c9/autodev_ai-0.1.0a2-py3-none-any.whl
- sdist: https://files.pythonhosted.org/packages/b0/4a/27e49dba9ee2846bff62ee934ee61896a820ba0f4031cc6c4df576b66d9b/autodev_ai-0.1.0a2.tar.gz

## Homebrew Formula Cross-Check

The formula at `packaging/homebrew/Formula/autodev-ai.rb` has:
```ruby
sha256 "246f5f60810c1832051f9219fd141fe63ce87bbafec0125412d18cea326c291d"
```

Matches the sdist sha256 above. **Homebrew formula is safe to tap-publish from a supply-chain integrity standpoint.**
