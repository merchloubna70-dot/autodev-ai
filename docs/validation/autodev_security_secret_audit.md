# autodev-ai Security & Secret Audit

**Round:** security_secret_audit  
**Date:** 2026-05-14  
**Auditor:** Agent J — autodev-ai Release Hardening  
**Verdict:** `safe_with_fixes`  
**True leaks:** 0  
**Findings total:** 15

---

## Summary

No real credentials were found in the repository. All key-pattern hits are either test fixtures or documentation placeholders. Production subprocess calls never use `shell=True`. The allowlist/denylist system is fail-closed. Three fixes are required before release.

---

## 1. Secret Material Findings

| File | Line | Pattern | Classification | Severity | Notes |
|---|---|---|---|---|---|
| `tests/unit/test_severity_findings_in_reviewers.py` | 18 | `AKIA[0-9A-Z]{16}` | test_fixture | info | Fake key `AKIA1234567890EXAMPLE` written to `tmp_path` to exercise `SecurityReviewerAgent`. Never at rest. |
| `docs/quickstart.md` | 54 | `OPENAI_API_KEY=` | doc_example | info | Placeholder `sk-...` — not a real key. |
| `docs/quickstart.md` | 60 | `ANTHROPIC_API_KEY=` | doc_example | info | Placeholder `sk-ant-...` — not a real key. |
| `docs/faq.md` | 56 | `ANTHROPIC_API_KEY=` | doc_example | info | Placeholder export in FAQ. |
| `docs/tutorials/06-mcp-server.md` | 122-124 | `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` | doc_example | info | JSON config snippet with placeholder values. |
| `src/autodev/agents/security_reviewer.py` | 35-41 | `SECRET_PATTERNS` tuple entries | safe_use | info | Detection patterns used by the scanner — not credentials. |
| `src/autodev/agents/parallel_section_reviewer.py` | 24 | `_SECRET_PATTERNS` tuple | safe_use | info | Detection patterns. |

**True leaks found: 0**

### Gaps in `SECRET_PATTERNS` (security_reviewer.py)

- `SECRET_PATTERNS` includes `claude_api_key` and `anthropic_api_key` (snake_case) but **not** the uppercase env-var forms `OPENAI_API_KEY` and `ANTHROPIC_API_KEY`. A file containing `export OPENAI_API_KEY=sk-real-key` would be missed.
- **Fix:** Add `"OPENAI_API_KEY"` and `"ANTHROPIC_API_KEY"` to `SECRET_PATTERNS`.

### `.gitignore` gap

`.gitignore` excludes `.venv/`, `dist/`, `build/` etc. but does **not** exclude `.env`, `*.env`, `credentials.json`, or `secrets.toml`. If a developer creates a local `.env` file it would be unguarded from accidental `git add .`.

- **Fix:** Add `.env`, `*.env`, `credentials.json`, `secrets.toml` to `.gitignore`.

---

## 2. Dangerous Shell Patterns

### shell=True usage

**Count in `src/`: 0**

The two lines containing `shell=True` in `src/autodev/agents/adversarial_reviewer.py` (lines 38-39) are string literals inside a detection-pattern tuple — they are not subprocess invocations.

All `subprocess.run` calls in production code (shell_executor, worker_isolator, gate runners, adapters) use list argv via `shlex.split` — no shell expansion.

### eval / exec / os.system

All occurrences in `src/` are string literals inside detection-pattern tuples in `adversarial_reviewer.py`. No actual `eval()`, `exec()`, or `os.system()` calls exist in production code.

### rm -rf / sudo / chmod 777 / curl|bash

These strings appear only in:
- `src/autodev/config.py` — `DANGEROUS_COMMANDS` constant (denylist)
- `src/autodev/utils/command_safety.py` — `DEFAULT_DENYLIST` constant
- `src/autodev/executors/claude_code_executor.py` / `codex_cli_executor.py` — system prompt instructions

All are denylist constants or prompt text; none are executed.

### Minor gap: branch-name injection vector

`worker_isolator.prepare_worktree` passes `branch` directly to `git worktree add` as a list argument (safe from shell injection) but does not validate that `branch` contains only safe chars. A branch name with embedded NUL or unusual unicode could cause git to misbehave.

- **Severity:** low
- **Fix:** Add `re.match(r'^[A-Za-z0-9/_.-]+$', branch)` guard in `prepare_worktree`.

---

## 3. Environment Variables

### All env vars read by `src/`

| Var | File | Documented? |
|---|---|---|
| `ANTHROPIC_API_KEY` | `agents/clarification_gate.py` | yes — quickstart.md, faq.md |
| `AUTODEV_A2A_TOKEN` | `adapters/a2a/server.py`, `adapters/a2a/client.py`, `cli.py` | yes — a2a_server.md, a2a_http_client.md, tutorials/07 |
| `FACTORY_CLAUDE_BIN` | `config.py` | yes — multi_cli_executor.md, faq.md |
| `FACTORY_CLAUDE_CMD` | `config.py` | yes — multi_cli_executor.md |
| `FACTORY_CODEX_BIN` | `config.py` | yes — quickstart.md, multi_cli_executor.md |
| `FACTORY_CODEX_CMD` | `config.py` | yes — multi_cli_executor.md |
| `FACTORY_FORCE_MOCK` | multiple | yes — quickstart.md, mcp_server.md, tutorials/03, tutorials/05, tutorials/06 |
| `FACTORY_LOG` | `utils/logging.py` | **NO** |
| `OPENAI_API_KEY` | `agents/clarification_gate.py` | yes — quickstart.md, tutorials/06 |

### Undocumented env vars: 1

**`FACTORY_LOG`** (`src/autodev/utils/logging.py` line 14):
```python
level_name = os.environ.get("FACTORY_LOG", "INFO").upper()
```
Controls the package log level. Default `INFO`. Accepts `DEBUG`, `WARNING`, `ERROR`, `CRITICAL`.

- **Fix:** Add `FACTORY_LOG` to the env-var reference table in `docs/quickstart.md`.

---

## 4. Path Traversal / Temp Dir

### `PatchExecutor` — SAFE

`patch_executor.py` uses `(repo_root / patch.path).resolve()` followed by `target.relative_to(repo_root)`. Path-escape attempts are silently skipped (continue). Correct pattern.

### `FilesystemAdapter`, `RepoScanner`, `RepoMap` — SAFE

All resolve `repo_path` via `Path(repo_path).resolve()` at construction; subsequent joins stay within the resolved root.

### `/tmp/` usage in `worker_isolator.py` — LOW

Docstring examples reference `/tmp/workers/...` as illustrative paths. Callers determine the actual `worker_root`; the class itself imposes no restriction. Callers should anchor `worker_root` to a controlled base directory (e.g., a directory under the project root or an explicitly user-approved temp area).

---

## 5. Archive Extraction

**No `tarfile.extractall` or `zipfile.extractall` calls found anywhere in the repository.**  
`tar_extraction_safe: true`

---

## 6. Executor & Security Component Review

### `executor_router.py`

- Fail-closed: when real CLI missing and `allow_mock=False`, returns `exit_code=127` with `error_type="cli_missing_fail_closed"` — does not silently succeed.
- Security/Architecture/Release/Docs task types are hard-locked to Claude backend; not subject to budget bias.
- Mock substitution requires explicit `allow_mock=True` opt-in.
- **Assessment: SOUND**

### `worker_isolator.py`

- Immutable shared files (auth.json, config.toml, models_cache.json, etc.) are symlinked read-only from parent CODEX_HOME; mutable state is per-worker private dirs.
- No `shell=True`; git commands use list argv.
- Minor gap: branch-name sanitization (see Section 2).
- **Assessment: SOUND with low-severity gap**

### `command_safety.py`

- Fail-closed: anything not on `DEFAULT_ALLOWLIST` is rejected.
- `DEFAULT_DENYLIST` covers: `rm -rf`, `sudo`, `chmod 777`, `curl | bash`, `wget | bash`, `eval`, `exec `, `source .env`, `cat .env`, `printenv`, `> /etc/`, `; rm`, `&& rm`, `| rm`, `mkfs`, `--force`, `git push --force`.
- `scan_prompt_for_unsafe` also scans generation prompts for denylist patterns.
- Minor gap: `curl | sh` and `wget | sh` not explicitly listed (only `curl | bash` and `wget | bash` present); in practice the shell executor uses `shlex.split` so these would be blocked anyway.
- **Assessment: SOUND**

### `FILE_SCAN_DENYLIST` in `security_reviewer.py`

Derived from `DEFAULT_DENYLIST` minus `eval` and `exec ` (which produce false positives in source code). Correct approach.

Gaps:
1. `SECRET_PATTERNS` missing uppercase `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` env-var forms (see Section 1).
2. No `gho_` (GitHub OAuth token) pattern in `SECRET_PATTERNS` (only `ghp_` PAT covered).

---

## 7. Package / pip-audit

`pyproject.toml` does not include `pip-audit` in dev dependencies. No pip-audit step is referenced in any CI/CD config.

- **Fix:** Add `pip-audit>=2.7` to `[project.optional-dependencies] dev` and integrate `uv run pip-audit` into the release gate or CI workflow.

---

## Required Fixes Before Release

| Priority | Fix | File |
|---|---|---|
| P0 | Add `.env`, `*.env`, `credentials.json`, `secrets.toml` to `.gitignore` | `.gitignore` |
| P0 | Add `FACTORY_LOG` to env-var reference table | `docs/quickstart.md` |
| P1 | Add `OPENAI_API_KEY` and `ANTHROPIC_API_KEY` uppercase forms to `SECRET_PATTERNS` | `src/autodev/agents/security_reviewer.py` |
| P1 | Add `gho_` GitHub OAuth pattern to `SECRET_PATTERNS` | `src/autodev/agents/security_reviewer.py` |
| P2 | Add branch-name sanitization in `prepare_worktree` | `src/autodev/executors/worker_isolator.py` |
| P2 | Add `pip-audit` to dev deps and CI | `pyproject.toml` |

---

## Verdict

**`safe_with_fixes`**

- True credential leaks: **0**
- `subprocess shell=True` in production: **0**
- `tarfile/zipfile.extractall` without filter: **0 (not used)**
- Path-traversal protection: present in PatchExecutor, FilesystemAdapter
- Undocumented env vars: 1 (`FACTORY_LOG`)
- Top 3 dangerous patterns found (all safe uses): `AKIA...` test fixture, denylist pattern strings in adversarial/security reviewers, `/tmp/` in worker_isolator docstring examples
