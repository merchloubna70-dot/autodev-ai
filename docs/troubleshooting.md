# Troubleshooting

Common problems and how to fix them. Each section is self-contained.

---

## 1. Codex CLI missing — `codex: command not found`

**Symptom:** `autodev deliver-project` exits immediately with
`ExecutorRouter: codex not found on PATH`.

**Causes and fixes:**

1. **Not installed.** Install via npm (the official distribution channel):
   ```bash
   npm install -g @openai/codex
   codex --version
   ```

2. **Not on PATH.** `npm global bin` may not be in your shell PATH:
   ```bash
   echo $PATH
   npm bin -g          # prints the global bin directory
   export PATH="$(npm bin -g):$PATH"  # add to ~/.zshrc or ~/.bashrc
   ```

3. **Homebrew.** A Homebrew tap is planned but blocked on the PyPI publish
   (sha256 placeholder; see [scenario 9](#9-homebrew-sha256-placeholder)).
   Use the npm route for now.

4. **Verify the fix:**
   ```bash
   which codex && codex --version
   ```

5. **No Codex at all?** Use mock mode:
   ```bash
   FACTORY_FORCE_MOCK=1 autodev deliver-project \
     --allow-mock-executor true \
     --mode dry-run ...
   ```

---

## 2. Claude CLI missing — `claude: command not found`

**Symptom:** `ExecutorRouter` selects Claude Code for architecture/security tasks
but the binary is absent.

**Fix:**
```bash
# macOS / Linux via npm
npm install -g @anthropic-ai/claude-code
claude --version

# or from GitHub Releases (standalone binary)
# https://github.com/anthropics/claude-code/releases
```

Verify credentials:
```bash
export ANTHROPIC_API_KEY=sk-ant-...
claude auth login   # interactive OAuth flow
```

If you need to run without Claude Code, force a different executor:
```bash
autodev deliver-project ... --executor codex
# or full mock:
autodev deliver-project ... --executor mock
```

---

## 3. Mock fallback not engaging

**Symptom:** You expected mock mode but autodev is calling real CLIs (and failing
because they are absent or unauthenticated).

**Checklist:**
- Confirm `FACTORY_FORCE_MOCK=1` is exported (not just set in a sub-shell):
  ```bash
  export FACTORY_FORCE_MOCK=1
  echo $FACTORY_FORCE_MOCK   # must print 1
  ```
- Pass `--allow-mock-executor true` on the command line; the env var alone is
  sufficient for agent-layer mocking but the executor router also requires the
  explicit CLI flag (or `allow_mock_executor = true` in `config.toml`).
- Verify mock is active by checking the first log line:
  ```bash
  FACTORY_LOG=DEBUG FACTORY_FORCE_MOCK=1 autodev deliver-project ... 2>&1 | grep -i mock
  # Expected: "[autodev] executor=mock"
  ```

---

## 4. MCP stdio debugging

**Symptom:** Claude Desktop shows "autodev server disconnected" or MCP tool calls
return unexpected errors.

**Debugging steps:**

1. Run the server manually and pipe output through `jq`:
   ```bash
   autodev mcp-serve | jq '.'
   # Send a test request (separate terminal):
   echo '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}' | autodev mcp-serve
   ```

2. Check for Python tracebacks:
   ```bash
   autodev mcp-serve 2>&1 | head -50
   ```

3. Enable the audit log to see what is being called:
   ```bash
   AUTODEV_MCP_AUDIT_LOG=/tmp/mcp-debug.jsonl autodev mcp-serve
   tail -f /tmp/mcp-debug.jsonl | jq '.'
   ```

4. Confirm the binary is found by Claude Desktop:
   ```bash
   which autodev
   # The path returned must be on the system PATH that GUI apps see (macOS: /etc/paths or login shell)
   ```

5. After editing `claude_desktop_config.json`, fully quit and relaunch Claude Desktop.

---

## 5. A2A HTTP blocked — SSRF guard rejects private-network address

**Symptom:** `autodev a2a-call` targeting `http://127.0.0.1:8421` (or any
RFC-1918 address) raises `A2ASSRFError: blocked private address`.

**Explanation:** The A2A HTTP transport blocks loopback and private-network
addresses by default to prevent Server-Side Request Forgery attacks.

**For local testing only:**
```bash
export AUTODEV_A2A_ALLOW_PRIVATE_NETWORKS=1
autodev a2a-call --endpoint http://127.0.0.1:8421 --skill fix-bug \
  --task-json '{"text": "Reproduce the latency bug"}'
```

**Warning:** Never set `AUTODEV_A2A_ALLOW_PRIVATE_NETWORKS=1` in a production
deployment or in any environment that has access to internal services. The guard
exists to prevent an attacker-controlled remote agent from pivoting to internal
infrastructure.

---

## 6. mypy type errors

**Symptom:** CI fails with mypy errors, or you want to verify types locally.

```bash
cd /path/to/autodev-ai
source .venv/bin/activate
python -m mypy src/autodev
```

Common patterns and fixes:
- **Missing stubs** — `mypy` may complain about missing stubs for `crewai`,
  `typer`, or `tomllib`; these are suppressed by the `[[tool.mypy.overrides]]`
  section in `pyproject.toml`. If you added a new dependency, add a matching
  `ignore_missing_imports = true` entry.
- **Strict mode in CI** — the project runs `mypy --strict` in CI. Avoid
  `Any` in return types; use `object` or `Union` with explicit narrowing.

---

## 7. ruff lint / format errors

**Symptom:** pre-commit or CI reports ruff violations.

```bash
# Auto-fix most issues
ruff check --fix .
ruff format .
# Check what remains
ruff check .
```

The project uses ruff with the `E`, `F`, `I`, `UP` rule sets. Common culprits:
- `F401` unused imports — remove them or add `# noqa: F401` if re-exported.
- `UP007` — use `X | Y` instead of `Optional[X]` / `Union[X, Y]` in Python ≥ 3.10.

---

## 8. Docker build — "wheel not found"

**Symptom:** `docker build` fails with
`ERROR: autodev_ai-0.1.0a1-py3-none-any.whl: No such file or directory`.

The `Dockerfile` (and Helm chart) expect the wheel to be present in `dist/`
**before** the build context is sent to the daemon.

**Fix:**
```bash
python -m build          # produces dist/autodev_ai-0.1.0a1-py3-none-any.whl
docker build -t autodev-ai:local .
```

If `python -m build` is missing, install it:
```bash
pip install --upgrade build
```

---

## 9. Homebrew sha256 placeholder

**Symptom:** `brew install autodev-ai` (or tapping the formula) fails because
the sha256 in the formula is a placeholder (`PLACEHOLDER_SHA256_PYPI_WHEEL`).

**Explanation:** The Homebrew formula is pre-written but cannot be activated
until the PyPI `0.1.0a1` wheel is published and its SHA-256 is known.

**Workaround until PyPI publish:**
```bash
# Install from the GitHub Release wheel directly
pip install https://github.com/merchloubna70-dot/autodev-ai/releases/download/v0.1.0-alpha/autodev_ai-0.1.0-py3-none-any.whl
```

After the PyPI publish, the formula will be updated with the real sha256 and
`brew install` will work.

---

## 10. PyInstaller — `distutils` or `difflib` excluded

**Symptom:** A PyInstaller-built binary crashes at startup with
`ModuleNotFoundError: No module named 'distutils'` or `'difflib'`.

**Fix:** These modules are excluded by PyInstaller's default hook. Add them to
the spec file's `hiddenimports`:

```python
# autodev.spec
a = Analysis(
    ['src/autodev/__main__.py'],
    hiddenimports=['distutils', 'distutils.version', 'difflib'],
    ...
)
```

Also ensure `setuptools` is installed in the build environment (it ships
`distutils` on Python 3.12+):
```bash
pip install --upgrade setuptools
pyinstaller autodev.spec
```

---

## 11. `autodev dashboard` exits immediately

**Symptom:** `autodev dashboard` prints
`Error: 'textual' package not found. Install with: pip install autodev-ai[tui]`
and exits.

**Explanation:** `textual` (the TUI framework) is an optional dependency. It is
not installed by the default `pip install autodev-ai` command.

**Fix:**
```bash
pip install "autodev-ai[tui]"
# or for a source install:
pip install -e ".[tui]"
```

---

## 12. `pip install --upgrade autodev-ai==0.1.0a1` — no matching distribution

**Symptom:**
```
ERROR: Could not find a satisfying requirement for autodev-ai==0.1.0a1
No matching distribution found for autodev-ai==0.1.0a1
```

**Explanation:** `0.1.0a1` is a pre-release version. By default `pip` skips
pre-releases.

**Fix:** add the `--pre` flag:
```bash
pip install --pre "autodev-ai==0.1.0a1"
# or install the latest pre-release:
pip install --pre autodev-ai
```

When pinning in `requirements.txt` or `pyproject.toml` you do **not** need
`--pre` — the `==0.1.0a1` constraint is exact and pip will install it. The
`--pre` flag is only needed for "latest matching" resolution.

---

## Getting further help

- Check [FAQ](faq.md) for the top 15 questions.
- Read [Architecture reference](architecture.md) to understand why a command
  behaves a certain way.
- Open an issue at
  [github.com/merchloubna70-dot/autodev-ai/issues](https://github.com/merchloubna70-dot/autodev-ai/issues).
- Enable verbose logging for any command:
  ```bash
  FACTORY_LOG=DEBUG autodev <subcommand> ... 2>&1 | less
  ```
