# AutoDev Pre-Tag Security Audit — Full Secret & Dangerous-Pattern Scan

**Agent:** PreTag-I  
**Round:** full_audit_security  
**Date:** 2026-05-14  
**Verdict:** safe_to_tag (with one low-severity gitignore gap noted)

---

## Summary

True secret leaks: **0**. No AWS keys, GitHub PATs, Google API keys, PEM private keys, or OpenAI-style keys committed in source, scripts, tests, or workflow files. All 4 required SSRF/isolation hardening symbols confirmed present. DEFAULT_DENYLIST covers all 8 required dangerous patterns.

One low-severity gap found: `.gitignore` does not enumerate `.env`, `credentials.json`, or `secrets.toml`. None of those files currently exist in the repo (confirmed by `find`), so there is no active leak — but the omission should be remediated before the tag is cut.

---

## A. Secret Pattern Scan Results

| Pattern | Hits | Classifications |
|---------|------|-----------------|
| `AKIA[0-9A-Z]{16}` | 1 | test_fixture |
| `ghp_[A-Za-z0-9]{36+}` | 0 | — |
| `gho_[A-Za-z0-9]{36+}` | 0 | — |
| `AIzaSy[A-Za-z0-9_-]{33}` | 0 | — |
| `sk-[A-Za-z0-9]{20+}` | 0 | — |
| `-----BEGIN.*PRIVATE KEY` | 2 | safe_use (denylist strings in reviewer agents) |
| `OPENAI_API_KEY=` | 1 | doc_example (placeholder `sk-...`) |
| `ANTHROPIC_API_KEY=` | 4 | doc_example (placeholder `sk-ant-...`) |
| `PYPI_API_TOKEN=` | 1 | safe_use (GitHub Actions `${{ secrets.PYPI_API_TOKEN }}`) |

**Total by classification:** test_fixture=1, doc_example=5, safe_use=2, suspect_leak=0, true_leak=0

### Detail: AKIA hit

`tests/unit/test_severity_findings_in_reviewers.py:18` — writes the literal string `AKIA1234567890EXAMPLE` to a pytest `tmp_path` file to exercise `SecurityReviewerAgent` detection. Intentional test infrastructure; no real credential.

### Detail: `-----BEGIN PRIVATE KEY` hits

Both hits are string literals inside denylist constant tuples in `src/autodev/agents/parallel_section_reviewer.py:23` and `src/autodev/agents/security_reviewer.py:35`. These are pattern-matching strings used to detect PEM keys in submitted code, not actual private keys.

---

## B. Dangerous Shell Pattern Scan

### Source directory (`src/`) — all clear

| Pattern | `src/` hits | Classification |
|---------|-------------|----------------|
| `subprocess.run(...shell=True)` | 0 | — |
| `os.system(` | 0 | — |
| `eval(` | 0 | — |
| `exec(` | 0 | — |
| `rm -rf` (in code) | 0 | — |
| `sudo` (in code) | 0 | — |
| `chmod 777` | 0 | — |
| `curl \| bash` / `wget \| sh` | 0 | — |
| `tempfile.mktemp` | 0 | — |

All `rm -rf`, `sudo`, `chmod 777`, `curl \| bash`, `wget \| bash`, `eval`, `exec`, `cat .env` occurrences in `src/` are **denylist constant strings** inside `command_safety.py` and `config.py` — used to block those commands, not execute them.

`adversarial_reviewer.py` pattern tuples (`subprocess.*shell=True`, `eval(`, `exec(`, `os.system(`) are regex patterns for code-review detection, not live calls.

### Test fixtures

`tests/unit/test_adversarial_reviewer.py:43,95` and `tests/integration/test_parallel_review_5sections.py:48` contain `subprocess.run(cmd, shell=True)` and `eval(user_input)` as string literals inside test input data to validate that the reviewer catches them. Correct behavior.

---

## C. SSRF / Private IP Scan

All private IP occurrences in `src/` are inside the SSRF blocklist in `src/autodev/adapters/a2a/transports/http.py:96-100` — the four RFC-1918 / link-local ranges are enumerated as **rejected** subnets, not as target addresses.

`127.0.0.1` in `src/autodev/cli.py:678` and `src/autodev/schemas.py:1045` are default bind addresses for the local server (loopback-only — more restrictive than `0.0.0.0`).

Test files use `127.0.0.1` for fake server fixtures; `conftest.py:15-16` explicitly documents this is test-only and production code never sets the relevant env var.

---

## D. Mitigation Verification

| Symbol / Guard | File | Status |
|---------------|------|--------|
| `A2AHttpSSRFError` | `src/autodev/adapters/a2a/transports/http.py:86` | PRESENT |
| `_resolve_and_pin_host` | `src/autodev/adapters/a2a/transports/http.py:187` | PRESENT |
| `_PinnedHTTPHandler` | `src/autodev/adapters/a2a/transports/http.py:289` | PRESENT |
| `_PinnedHTTPSHandler` | `src/autodev/adapters/a2a/transports/http.py:320` | PRESENT |
| `WorkerIsolatorPathEscapeError` | `src/autodev/executors/worker_isolator.py:52` | PRESENT |
| `AUTODEV_MCP_ALLOW_APPLY` dual-gate | `src/autodev/mcp_server/tools.py:21,76,281,305,399,422` | PRESENT |
| `DEFAULT_DENYLIST` complete | `src/autodev/utils/command_safety.py:45-59` | PRESENT |

`DEFAULT_DENYLIST` confirmed entries: `rm -rf`, `sudo`, `chmod 777`, `curl \| bash`, `wget \| bash`, `eval`, `exec `, `source .env`, `cat .env`, `printenv`, `> /etc/`, `; rm `, `&& rm `, `\| rm `.

---

## E. .gitignore Compliance

| File | In .gitignore | Present on disk |
|------|--------------|-----------------|
| `.env` | NO | No |
| `credentials.json` | NO | No |
| `secrets.toml` | NO | No |

**Finding (low severity):** The repo `.gitignore` does not list `.env`, `credentials.json`, or `secrets.toml`. No such files exist in the working tree today, so there is no active leak. However, the omission creates a safety gap: a contributor who creates any of these files could accidentally commit it.

**Recommended remediation (before tag):** append three lines to `.gitignore`:
```
.env
credentials.json
secrets.toml
```

---

## Top 3 Findings

1. **[LOW]** `.gitignore` missing `.env` / `credentials.json` / `secrets.toml` entries — no current file exposure but should be fixed before tagging.
2. **[INFO]** `AKIA1234567890EXAMPLE` in test fixture (`tests/unit/test_severity_findings_in_reviewers.py:18`) — intentional, not a real credential.
3. **[INFO]** Placeholder API key strings (`sk-ant-...`, `sk-...`) in 5 documentation files — clearly placeholder examples, no real key material.

---

## Env Vars Read

- `AUTODEV_MCP_ALLOW_APPLY` — read from `os.environ` in `tools.py`, no hardcoded value
- `ANTHROPIC_API_KEY` — only in documentation as placeholder text
- `OPENAI_API_KEY` — only in documentation as placeholder text
- `PYPI_API_TOKEN` — GitHub Actions secret reference `${{ secrets.PYPI_API_TOKEN }}` only, not hardcoded

---

## Verdict

**safe_to_tag** — zero true leaks, zero suspect leaks, all 4 hardening symbols confirmed present, all dangerous-pattern denylist entries verified. One low-severity gitignore gap (`.env` / `credentials.json` / `secrets.toml` not listed) should be remediated but does not block the tag given no such files exist on disk.
