# PyInstaller packaging for `autodev`

Produces a single self-contained `autodev` binary (~30–60 MB) that runs
without a system Python install.  Users only need the external CLIs
(`claude`, `codex`) on their `PATH` — the Python runtime is fully bundled.

---

## Prerequisites

| Tool | Version | Notes |
|------|---------|-------|
| Python | 3.11+ | Must match the venv used to install autodev |
| PyInstaller | 6.x | Installed automatically by `build.sh`; **not** a runtime dep |
| Xcode CLT | Any | `xcode-select --install` — needed for `lipo` (universal build only) |

---

## Quick build (native arch)

```bash
# From the repo root — create and populate the venv once:
python -m venv .venv
source .venv/bin/activate
pip install -e ".[all]"

# Then build the binary:
cd packaging/pyinstaller
bash build.sh
```

The binary is written to `packaging/pyinstaller/dist/autodev`.

---

## Universal macOS binary (arm64 + x86_64)

You need **two separate Python venvs**, one for each architecture.

```bash
# arm64 venv (native on Apple Silicon)
python3 -m venv .venv-arm64
source .venv-arm64/bin/activate
pip install -e ".[all]"
deactivate

# x86_64 venv (via Rosetta on Apple Silicon, or native on Intel)
arch -x86_64 /usr/bin/python3 -m venv .venv-x64
source .venv-x64/bin/activate
pip install -e ".[all]"
deactivate

# Build the fat binary:
cd packaging/pyinstaller
ARM64_PYTHON=../../.venv-arm64/bin/python \
X86_PYTHON=../../.venv-x64/bin/python \
bash build-universal-mac.sh
```

Output: `packaging/pyinstaller/dist/autodev-universal`

---

## Expected size

| Build | Approximate size |
|-------|-----------------|
| Native (arm64 or x86_64) | 30–50 MB |
| Universal (fat binary) | 60–100 MB |

Size varies with the set of third-party packages installed in the venv.
Heavy optional deps (e.g. `numpy`, `torch`) are excluded by the spec.

---

## Testing the binary

```bash
# Basic sanity check
./dist/autodev --help

# Run a dry-run issue flow
./dist/autodev run-issue --repo-path /path/to/repo --issue-file issue.txt --mode dry-run
```

The smoke test is also run automatically at the end of `build.sh`.

---

## Known issues and caveats

### External CLIs are NOT bundled

`autodev` shells out to `claude` (Claude Code CLI) and `codex` (OpenAI Codex CLI).
These are **not** bundled into the binary — users must have them installed and
on their `PATH`.  The binary will print a clear error message if they are missing
when a flow tries to invoke them.

### First run is slower

PyInstaller single-file binaries unpack themselves to a temp directory on the
first run (the "bootloader unpack" step).  Subsequent runs reuse the cache and
start quickly.  The unpack directory is typically at
`/tmp/_MEIxxxxxx/` (macOS/Linux) or `%TEMP%\_MEIxxxxxx\` (Windows).

### macOS Gatekeeper (unsigned binary)

macOS will quarantine unsigned binaries downloaded from the internet.  To run
the binary locally or distribute it without a signing certificate, strip the
quarantine attribute:

```bash
xattr -dr com.apple.quarantine ./dist/autodev
# or for the universal binary:
xattr -dr com.apple.quarantine ./dist/autodev-universal
```

### Signing and notarizing (optional, recommended for distribution)

To distribute the binary without the quarantine warning, sign and notarize it:

```bash
# 1. Sign with your Developer ID Application certificate
codesign --force --options runtime \
  --sign "Developer ID Application: Your Name (TEAMID)" \
  ./dist/autodev

# 2. Zip for notarization
ditto -c -k --keepParent ./dist/autodev autodev.zip

# 3. Submit for notarization (requires Apple ID + app-specific password)
xcrun notarytool submit autodev.zip \
  --apple-id "you@example.com" \
  --team-id "YOURTEAMID" \
  --password "@keychain:AC_PASSWORD" \
  --wait

# 4. Staple the ticket
xcrun stapler staple ./dist/autodev
```

See [Apple's notarization docs](https://developer.apple.com/documentation/security/notarizing_macos_software_before_distribution)
for full details.

### Rebuilding

`build.sh` passes `--clean --noconfirm` to PyInstaller, so it is safe to run
repeatedly.  Old `dist/` and `build/` directories inside
`packaging/pyinstaller/` are overwritten on each run.

### Adding new hidden imports

If a new dependency is added to `autodev` that PyInstaller can't auto-detect,
add its dotted path to the `_extra_hidden` list in `autodev.spec`.  Third-party
packages that use dynamic imports (e.g. via `importlib`) are the most common
culprits.
