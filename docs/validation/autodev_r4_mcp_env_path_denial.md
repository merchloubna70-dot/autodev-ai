# R4-A — MCP Preflight Path-Safety Validation

**Round:** R4  
**Agent:** R4-A  
**Date:** 2026-05-14  
**Verdict:** PASS

---

## Threat Model

MCP tools that accept path-like parameters (`repo_path`, `issue_file`, `prd`, `output`, `export_path`) can be abused by a caller who controls those arguments. Without preflight validation, an attacker (or a confused-deputy caller) can supply paths like:

| Attack vector | Example | Risk |
|---|---|---|
| Direct secret-file targeting | `repo_path=/srv/.env` | Handler reads/modifies the env file before any mode check |
| Glob variant | `repo_path=/app/.env.production` | Same; env variant bypasses exact-match guard |
| Certificate/key files | `repo_path=/etc/ssl/id_rsa.key` | Exfiltration of private keys |
| Credential files | `repo_path=/home/user/credentials.json` | Cloud provider auth tokens |
| Basename substring | `repo_path=/tmp/my-secret-file.txt` | Files with "secret"/"token"/"credential" in the name |
| Path traversal | `repo_path=../etc/passwd` | Escape the repo root to OS files |

The preflight check runs **before** any file I/O or flow execution, so the path content is never read.

---

## Implementation

### New module: `src/autodev/mcp_server/path_safety.py`

Exports:
- `MCPPathSafetyError(ValueError)` — raised on violation
- `_validate_safe_path(path, *, role) -> None` — the validator

Rejection rules (applied to the **basename only** to avoid false positives on parent directories like `/Users/secret/dev/repo`):

| Rule | Examples rejected |
|---|---|
| Exact match | `.env`, `credentials.json`, `secrets.toml` |
| Glob `.env.*` | `.env.production`, `.env.local`, `.env.staging` |
| Glob `*.pem` | `server.pem`, `ca.pem` |
| Glob `*.key` | `id_rsa.key`, `server.key` |
| Substring `secret` | `my-secret-file.txt`, `secret_store.db` |
| Substring `token` | `github_token.txt`, `access_token.json` |
| Substring `credential` | `credential_store.db` |
| Path traversal `..` | `../etc/passwd`, `/tmp/a/../../../etc/shadow` |

Error message returned: `"Path rejected: matches secret-file pattern"` — the original path is intentionally omitted.

### Modified: `src/autodev/mcp_server/tools.py`

Preflight call added to handlers: `_handle_scan`, `_handle_deliver_project`, `_handle_run_issue`, `_handle_report`, `_handle_release_check`, `_handle_list_runs`.

Pattern in each handler:
```python
try:
    _validate_safe_path(repo_path, role="repo_path")
except MCPPathSafetyError as exc:
    return {"isError": True, "content": [{"type": "text", "text": str(exc)}]}
```

---

## Test Results

### New test file: `tests/integration/test_mcp_path_secret_denial.py`

**30 tests, 30 passed.**

Breakdown:
- 12 unit rejection tests (`TestValidateSafePathRejects`)
- 7 unit allow-list tests (`TestValidateSafePathAllows`)
- 11 integration handler tests (`TestMCPHandlerPathDenial`)

Specific cases covered (exceeds the 10-test minimum):

| # | Test | Result |
|---|---|---|
| 1 | `.env` rejected | PASS |
| 2 | `.env.production` rejected | PASS |
| 3 | `.env.local` rejected | PASS |
| 4 | `credentials.json` rejected | PASS |
| 5 | `secrets.toml` rejected | PASS |
| 6 | `key.pem` rejected | PASS |
| 7 | `id_rsa.key` rejected | PASS |
| 8 | `my-secret-file.txt` (substring `secret`) rejected | PASS |
| 9 | `../etc/passwd` (path traversal) rejected | PASS |
| 10 | `examples/01-mdlines/brief.md` allowed | PASS |
| 11 | `/tmp/some/regular/repo` allowed | PASS |
| 12 | `/Users/secret/dev/repo` allowed (parent dir, not basename) | PASS |

### xfail markers removed

| Test | File | Old state | New state |
|---|---|---|---|
| `TestMCPPathArgDotEnvDenial::test_mcp_rejects_path_argument_containing_dot_env` | `tests/integration/test_security_p0_coverage.py` | `@pytest.mark.xfail(strict=True, ...)` | Passing test (no xfail) |

No other xfail markers matching `mcp.*\.env` exist in the test suite.

### Full suite

- **1284 passed** (excluding 3 pre-existing failures in `TestWorkerIsolatorBranchNameInjection` and `test_branch_name_with_slash_raises` which are out of R4-A scope)
- `mypy src/autodev`: 0 errors
- `ruff check` on new/modified files: 0 errors

---

## Residual Risk

| Risk | Severity | Notes |
|---|---|---|
| Case sensitivity on case-insensitive filesystems (macOS HFS+, Windows NTFS) | Low | Validator normalises to lowercase via `basename.lower()`, so `.ENV`, `.Env.Production` are caught. No residual on case-insensitive FS. |
| Unicode homoglyphs | Low | A path like `/tmp/．env` (Unicode fullstop) would not be caught. Considered out of scope; MCP caller would need deliberate encoding attack. |
| Symlink to secret file with innocuous name | Medium | `_validate_safe_path("/tmp/innocent-link")` passes if the link target is `.env`; the handler would follow the symlink. Mitigation: use `Path.resolve()` in a future hardening round. |
| Paths without traversal but with `..` literal in a component name | None | PurePosixPath.parts correctly splits; a literal `..` in a non-traversal position is caught. |
| Windows-style `..\\` traversal | Low | `path_str.split("\\")` check covers backslash segments. Not exercised on macOS but logic is present. |
