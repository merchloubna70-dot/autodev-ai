# Homebrew Formula Activation Checklist

**Status: BLOCKED — do not publish this formula until all steps below are completed.**

This formula is blocked pending live PyPI availability of `autodev-ai 0.1.0a1`.
Complete every step in order before pushing to a Homebrew tap.

## Steps

1. **Confirm PyPI 0.1.0a1 is published**

   ```
   pip index versions autodev-ai --pre
   ```

   Expected output must include `0.1.0a1`. If the package is not listed, stop here.

2. **Obtain the sdist URL and compute sha256**

   Look up the sdist URL from PyPI JSON API:
   ```
   curl -s https://pypi.org/pypi/autodev-ai/0.1.0a1/json | python3 -c \
     "import sys,json; [print(f['url']) for f in json.load(sys.stdin)['urls'] if f['packagetype']=='sdist']"
   ```

   Then compute the sha256:
   ```
   curl -L "<pypi-sdist-url>" | sha256sum
   ```

3. **Update Formula `url` and `sha256` fields**

   In `packaging/homebrew/Formula/autodev-ai.rb`:
   - Replace the `url` value with the canonical PyPI sdist URL (not the GitHub releases URL).
   - Replace `sha256 "TODO_PUBLISH_SHA256"` with the computed sha256 from step 2.

4. **Run `brew audit`**

   ```
   brew audit --formula packaging/homebrew/Formula/autodev-ai.rb
   ```

   Fix any warnings or errors before proceeding.

5. **Install and smoke-test**

   ```
   brew install --build-from-source packaging/homebrew/Formula/autodev-ai.rb
   ```

6. **Verify CLI version**

   ```
   autodev --version
   ```

   Output must match `0.1.0a1`.

7. **Push to a Homebrew tap repository**

   Copy the updated formula to the tap repo (e.g. `homebrew-autodev-ai`) and open a PR or push directly to main, per that repo's contributing guidelines.

## Notes

- PyPI RC readiness and Homebrew publish readiness are **separate gates**.
  Homebrew being blocked does NOT block the PyPI RC verdict.
- The placeholder `sha256 "TODO_PUBLISH_SHA256"` and the BLOCKED comment in the formula
  are intentional honesty markers confirming this formula is not yet tap-ready.
- See `docs/validation/autodev_r3_homebrew_publish_time_blocker.md` for the rationale.
