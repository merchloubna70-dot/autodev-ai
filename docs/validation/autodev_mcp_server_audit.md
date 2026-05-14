# autodev MCP Server Audit

**Round:** mcp_server_audit  
**Date:** 2026-05-14  
**Auditor:** Agent E — Release Hardening  
**Transport:** stdio JSON-RPC 2.0  
**Verdict:** `mcp_ready_with_caveats`

---

## 1. Server Overview

`src/autodev/mcp_server/server.py` implements a pure-stdlib stdio JSON-RPC 2.0 server.

- Reads newline-delimited JSON from stdin; writes responses to stdout only.
- All logging goes to stderr, never contaminating the wire protocol.
- Supported methods: `initialize`, `ping`, `tools/list`, `tools/call`.
- Notifications (requests without `id`) are silently accepted and produce no response.
- Unknown methods return `{"error": {"code": -32601, "message": "Method not found: ..."}}`.
- JSON parse failures return `{"error": {"code": -32700, "message": "Parse error: ..."}}` with `id: null`.

CLI entrypoint: `autodev mcp-serve` (defined in `src/autodev/cli.py`, command `mcp-serve`).

---

## 2. Registered Tools (9 total)

| # | Name | Required Inputs | Reads FS | Shells Out | LLM Required |
|---|------|-----------------|----------|------------|-------------|
| 1 | `autodev_scan` | `repo_path` | yes | no | no (agent may call git) |
| 2 | `autodev_classify_input` | `text` | no | no | yes (mock-safe) |
| 3 | `autodev_create_prd` | `brief_text` | no | no | yes (mock-safe) |
| 4 | `autodev_deliver_project` | `repo_path`, `brief_text` | yes | **yes (apply mode)** | yes |
| 5 | `autodev_run_issue` | `repo_path`, `issue_text` | yes | **yes (apply mode)** | yes |
| 6 | `autodev_report` | `repo_path`, `run_id` | yes | no | no |
| 7 | `autodev_roundtable` | `topic`, `skills` | no | **yes (claude CLI)** | yes |
| 8 | `autodev_release_check` | `repo_path`, `run_id` | yes | no | no |
| 9 | `autodev_list_runs` | `repo_path` | yes | no | no |

---

## 3. Live Smoke Test Results

All tests performed by launching `autodev mcp-serve` as a subprocess with stdin/stdout pipes (FACTORY_FORCE_MOCK=1).

| Test | Result |
|------|--------|
| `initialize` handshake | PASS — `protocolVersion: "2024-11-05"`, `serverInfo.name: "autodev"` |
| `tools/list` — 9 tools returned | PASS — exactly 9 tools, all expected names present |
| `tools/call autodev_list_runs` | PASS — returns `isError: false`, content array with JSON list |
| Malformed JSON → parse error | PASS — `code: -32700`, `id: null` |
| Unknown method → method-not-found | PASS — `code: -32601` |
| Unknown tool name → error | PASS — `code: -32601`, tool name echoed in message |
| Notification (no id) → no response | PASS — server produces no response for notification |
| Deeply nested JSON (6 levels) | PASS — no crash, valid response returned |
| `ping` method | PASS — returns `{}` result |
| Shutdown via stdin EOF | PASS — exit code 0 |

**Smoke test file:** `tests/integration/test_mcp_server_smoke.py`  
**Test count:** 10  
**Run command:** `.venv/bin/python -m pytest tests/integration/test_mcp_server_smoke.py -q`  
**Result:** 10 passed in 1.87s

---

## 4. Security and Semantics Checks

### 4.1 Secret Leakage

`tools.py` contains a single `os.environ` access:
```python
def _force_mock() -> bool:
    return os.environ.get("FACTORY_FORCE_MOCK", "0") == "1"
```

This reads a non-secret feature flag only. No `.env` file reads, no API key access, no dotenv imports.

**Secret leakage risk: none.**

### 4.2 Direct Shell Execution

`server.py` and `tools.py` contain **zero** direct subprocess or `os.system` calls. Shell-out occurs inside agents invoked by `autodev_deliver_project`, `autodev_run_issue`, and `autodev_roundtable` — but only when triggered at the agent layer, not at the MCP dispatch layer.

### 4.3 Deep JSON Nesting

A 6-level nested JSON object with 500-char string leaf value was sent to `autodev_list_runs`. The server returned a valid response with no crash. Python's `json.loads` does not enforce nesting depth limits by default; this is safe for normal usage.

---

## 5. Findings

### F-001 (MEDIUM): mode=apply tools shell out with no server-level guardrail

`autodev_deliver_project` and `autodev_run_issue` accept a `mode` parameter. When `mode="apply"`, they invoke Codex CLI or Claude CLI subprocesses and write files to the target `repo_path`. The MCP server has no server-side cap on this — any caller can pass `mode="apply"` to trigger real code execution on the server host.

**Recommendation:** Introduce an env-var override such as `AUTODEV_MCP_MAX_MODE=dry-run` that caps the effective mode server-side, documented in the `mcp-serve` help text.

### F-002 (LOW): autodev_roundtable shells out to real claude CLI by default

Without `FACTORY_FORCE_MOCK=1`, `autodev_roundtable` spawns real `claude` CLI subprocesses. An MCP caller can trigger LLM API spending by calling this tool without any authentication or rate-limiting mechanism in the MCP layer.

**Recommendation:** Add a server-level `AUTODEV_MCP_FORCE_MOCK` flag, or require a tool-call capability claim for LLM-backed tools.

### F-003 (LOW): Tool handler exceptions surface as isError=true, not JSON-RPC errors

When a tool handler raises an exception, the response is:
```json
{"jsonrpc":"2.0","id":N,"result":{"content":[{"type":"text","text":"<exception>"}],"isError":true}}
```

This follows MCP convention but differs from JSON-RPC 2.0 error semantics (no top-level `"error"` key). Clients checking only `"error" in response` will silently miss handler failures.

**Recommendation:** Document this behavior. For production, consider a strict-error mode that maps handler exceptions to `{"error":{"code":-32603,"message":"..."}}`.

### F-004 (INFO): No per-handler timeout or request size limit

The stdin loop in `server.py` has no per-line size cap and no handler timeout. Long-running `tools/call` invocations (e.g. `autodev_deliver_project` in apply mode) block the entire server for their duration.

**Recommendation:** Wrap handlers in `concurrent.futures.ThreadPoolExecutor` with `Future.result(timeout=N)` for production hardening.

---

## 6. Error Code Reference

| Scenario | JSON-RPC Code | Notes |
|----------|--------------|-------|
| Invalid JSON | -32700 | id is null |
| Unknown method | -32601 | Method name echoed |
| Unknown tool in tools/call | -32601 | Tool name echoed |
| Handler exception | isError=true in result | Not a JSON-RPC error at top level |

---

## 7. Verdict

**`mcp_ready_with_caveats`**

The MCP server is protocol-correct and all 9 tools are registered and accessible. The JSON-RPC 2.0 handshake, tools/list, tools/call (safe tool), and all error semantics are verified passing. No secret leakage. Three caveats require attention before production deployment: the mode=apply guardrail gap (F-001), unconstrained LLM spend via roundtable (F-002), and missing handler timeouts (F-004).
