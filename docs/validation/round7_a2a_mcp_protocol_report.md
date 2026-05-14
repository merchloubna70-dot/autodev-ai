# Round 7 — Agent 8: A2A / MCP Protocol Validation Report

**Date:** 2026-05-14  
**Agent:** a2a_mcp_protocol (Agent 8)  
**Project:** autodev-ai v0.1.0a3 — main HEAD 0a227d4  
**Overall Result:** PASS

---

## Summary

All A2A and MCP protocol-layer production checks passed. Bearer auth (401/401/200 sequence), SSRF denial with IP-pinning and DNS-rebinding mitigation, MCP path safety (14/14 patterns), apply-mode double gate (4/4 scenarios), and all 9 MCP tool schemas are correct.

---

## A2A Coverage

### CLI Help Checks

| Command | Exit | Usage Text Present | Result |
|---|---|---|---|
| `autodev a2a-serve --help` | 0 | Yes | PASS |
| `autodev a2a-register --help` | 0 | Yes | PASS |
| `autodev a2a-call --help` | 0 | Yes | PASS |

### Static Import Smoke Tests

| Module | Classes Imported | Result |
|---|---|---|
| `autodev.adapters.a2a.server` | `A2AHttpServer`, `_A2AHandler`, `_TaskStore`, `_autodev_card` | PASS |
| `autodev.adapters.a2a.client` | `A2AClient` | PASS |
| `autodev.adapters.a2a.roster` | `AgentRoster` | PASS |

### AgentRoster Round-trip Test

- Created AgentRoster with one card (`test-agent`, transport=`a2a-http`, endpoint=`http://127.0.0.1:9999`)
- Saved to temp JSON file
- Loaded into a fresh AgentRoster
- Verified: name, endpoint, capabilities, skills all match
- **Result: PASS**

### Bearer Auth Test

Server started on `127.0.0.1:54321` with `AUTODEV_A2A_TOKEN=test-secret-token`.

| Test | Expected | Actual | Result |
|---|---|---|---|
| No Authorization header | 401 | 401 | PASS |
| `Authorization: Bearer wrong-token` | 401 | 401 | PASS |
| `Authorization: Bearer test-secret-token` | 200 | 200 | PASS |

**AgentCard response on valid token:** Valid JSON with `name=autodev`, `version=1.0.0`, 8 skills listed.

### SSRF Deny Test

The `A2AHttpTransport` implements layered SSRF protection:

1. **URL validation** (`_validate_url`): Checks scheme (http/https only), IP literals directly against `_PRIVATE_NETWORKS` blocklist.
2. **DNS-pinning** (`_resolve_and_pin_host`): Resolves hostname, validates ALL returned addresses, pins the first safe address for the actual connection.
3. **DNS rebinding mitigation**: Custom `_PinnedHTTPHandler`/`_PinnedHTTPSHandler` connect to the pinned IP, never re-consulting DNS.

| Test | Allow Private | Result |
|---|---|---|
| `http://127.0.0.1:PORT` | False (default) | BLOCKED (A2AHttpSSRFError) |
| `http://10.0.0.1/tasks` | False (default) | BLOCKED |
| `http://169.254.169.254/latest/meta-data/` | False (default) | BLOCKED (AWS metadata) |
| `http://127.0.0.1:PORT` | True (AUTODEV_A2A_ALLOW_PRIVATE_NETWORKS=1) | ALLOWED |

**Transport `_make_request` returns `(0, b'')` on SSRF block** — not an exception to caller, but results in `status=FAILED` task.

**AUTODEV_A2A_ALLOW_PRIVATE_NETWORKS documentation:** Set this env var to `"1"` to allow loopback/private connections (integration test escape hatch). Default is blocked. The env var is checked in `A2AHttpTransport.__init__` and stored as `_allow_private_networks`.

Note: The `a2a-call` CLI with `--endpoint http://127.0.0.1:PORT` returns `status=failed` with artifact text `"[A2A-HTTP:remote@...] connection error"` — SSRF is silently blocked (no explicit error code exposed to CLI caller). This is by design (fail closed).

---

## MCP Coverage

### CLI Help

| Command | Exit | Result |
|---|---|---|
| `autodev mcp-serve --help` | 0 | PASS |

### Static Import Smoke Tests

| Module | Symbols | Result |
|---|---|---|
| `autodev.mcp_server.server` | `MCPServer` | PASS |
| `autodev.mcp_server.tools` | `get_tools` | PASS |
| `autodev.mcp_server.path_safety` | `MCPPathSafetyError`, `_validate_safe_path` | PASS |

### Tools Schema Validation

All 9 expected tools present, all have JSON Schema `inputSchema` with `required` params declared:

| Tool | Has Input Schema | Required Params |
|---|---|---|
| `autodev_scan` | Yes | `repo_path` |
| `autodev_classify_input` | Yes | `text` |
| `autodev_create_prd` | Yes | `brief_text` |
| `autodev_deliver_project` | Yes | `repo_path`, `brief_text` |
| `autodev_run_issue` | Yes | `repo_path`, `issue_text` |
| `autodev_report` | Yes | `repo_path`, `run_id` |
| `autodev_roundtable` | Yes | `topic`, `skills` |
| `autodev_release_check` | Yes | `repo_path`, `run_id` |
| `autodev_list_runs` | Yes | `repo_path` |

Missing vs spec: **none**  
Extra (not in spec): **none**

### Path Safety Deny Tests

`_validate_safe_path` was tested against 14 cases (all passed):

| Path | Expected | Result |
|---|---|---|
| `.env` | reject | PASS |
| `config.pem` | reject | PASS |
| `../../etc/passwd` | reject (traversal) | PASS |
| `.env.production` | reject | PASS |
| `.env.local` | reject | PASS |
| `secret_key.txt` | reject | PASS |
| `my.token` | reject | PASS |
| `credentials.json` | reject | PASS |
| `/valid/repo/path` | allow | PASS |
| `/home/user/project` | allow | PASS |
| `relative/path` | allow | PASS |
| `secrets.toml` | reject | PASS |
| `server.key` | reject | PASS |
| `app_credential_store` | reject | PASS |

### Apply-Mode Double Gate Tests

`_check_apply_mode_allowed` verified with 4 scenarios (all passed):

| allow_apply param | AUTODEV_MCP_ALLOW_APPLY env | Expected | Result |
|---|---|---|---|
| `True` | Not set | DENY | PASS |
| `False` | `"1"` | DENY | PASS |
| `True` | `"1"` | PERMIT | PASS |
| Missing (falsy) | `"1"` | DENY | PASS |

Audit log entries emitted to stderr and `/tmp/autodev_mcp_audit.log` for all decisions (including allowed).

---

## Subprocess Cleanup

All A2A servers started during testing were explicitly killed after each test. After cleanup, no `a2a-serve` or `mcp-serve` processes remained. Other agent processes (from parallel agents) were present but not from this agent.

---

## Findings

### P2 — Pydantic model_hint namespace warning

`AgentCard.model_hint` and `AgentSpec.model_settings` fields conflict with Pydantic's protected `model_` namespace prefix, causing `UserWarning` on every import. Harmless but noisy in production logs.

**Fix:** Add `model_config = ConfigDict(protected_namespaces=())` to `AgentCard` and `AgentSpec`.

### P3 — SSRF block not surfaced as explicit error to CLI caller

When `a2a-call` targets a private/loopback address, the SSRF is silently absorbed and surfaces as `status=failed` with `"connection error"` artifact text — not an explicit "SSRF blocked" message. Acceptable security-by-default behavior (fail closed), but could improve diagnostics.

### P3 — a2a-serve does not support `--port 0` (auto-assign)

`--port` is declared as `INTEGER` with default 8421. Port 0 for OS auto-assignment is not supported. Ephemeral port strategy requires picking an explicit high port. Validated with port 54321.

---

## Commands Run

| Command | Exit | Notes |
|---|---|---|
| `autodev a2a-serve --help` | 0 | Usage text present |
| `autodev a2a-register --help` | 0 | Usage text present |
| `autodev a2a-call --help` | 0 | Usage text present |
| `autodev mcp-serve --help` | 0 | Usage text present |
| `python3.11 -c "from autodev.adapters.a2a.server import ..."` | 0 | All classes imported |
| `python3.11 -c "from autodev.adapters.a2a.client import ..."` | 0 | A2AClient imported |
| `python3.11 -c "from autodev.adapters.a2a.roster import ..."` | 0 | AgentRoster imported |
| `python3.11` (roster round-trip test) | 0 | save/load/validate pass |
| `autodev a2a-serve --port 54321 --bind 127.0.0.1` (with token) | N/A | Served on port 54321 |
| `curl` (no token) | — | 401 |
| `curl` (wrong token) | — | 401 |
| `curl` (right token) | — | 200, valid JSON |
| `python3.11` (SSRF direct tests) | 0 | 127.0.0.1, 10.x, 169.254.x all blocked |
| `python3.11` (path_safety tests) | 0 | 14/14 pass |
| `python3.11` (apply-mode gate tests) | 0 | 4/4 pass |
| `python3.11` (tools schema enumeration) | 0 | 9/9 tools, all schemas valid |
| `pkill -f "autodev a2a-serve"` | — | Cleanup |

---

## Evidence Files

- `/Users/macworkers/autodev/src/autodev/adapters/a2a/server.py` — A2AHttpServer, bearer auth, `_check_auth`
- `/Users/macworkers/autodev/src/autodev/adapters/a2a/client.py` — A2AClient transport dispatch
- `/Users/macworkers/autodev/src/autodev/adapters/a2a/roster.py` — AgentRoster save/load
- `/Users/macworkers/autodev/src/autodev/adapters/a2a/transports/http.py` — SSRF protection, DNS pinning
- `/Users/macworkers/autodev/src/autodev/mcp_server/server.py` — MCPServer JSON-RPC loop
- `/Users/macworkers/autodev/src/autodev/mcp_server/tools.py` — 9 tools, apply-mode gate
- `/Users/macworkers/autodev/src/autodev/mcp_server/path_safety.py` — path safety validator
