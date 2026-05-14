# autodev Protocol Coverage Audit

**Round:** protocol_coverage  
**Date:** 2026-05-14  
**Auditor:** Cov-D (Phase 1 — read-only; no tests written)

---

## Summary

| Surface | Covered | Total | Coverage |
|---------|---------|-------|----------|
| MCP | 9 | 13 | 69% |
| A2A | 9 | 14 | 64% |
| Schemas | 2 | 6 | 33% |
| **Total** | **20** | **33** | **61%** |

---

## MCP (9/13 covered)

**Source files audited:**
- `tests/integration/test_mcp_server_smoke.py`
- `tests/integration/test_mcp_apply_guardrail.py`
- `tests/unit/test_mcp_server.py`

| Scenario | Covered | Test location |
|----------|---------|---------------|
| handshake initialize | YES | test_mcp_server.py, test_mcp_server_smoke.py |
| tools/list | YES | test_mcp_server.py, test_mcp_server_smoke.py |
| tools/call valid | YES | test_mcp_server.py (scan, classify, roundtable, list_runs) |
| tools/call invalid tool name | YES | test_mcp_server.py, test_mcp_server_smoke.py |
| tools/call missing required param | **NO** | — |
| malformed JSON (parse error) | YES | test_mcp_server.py, test_mcp_server_smoke.py |
| missing method field (jsonrpc+id but no method key) | **NO** | Listed in smoke docstring, never implemented |
| unknown method | YES | test_mcp_server_smoke.py |
| apply mode denied (both gates) | YES | test_mcp_apply_guardrail.py (6 denial tests) |
| apply mode allowed with guardrail | YES | test_mcp_apply_guardrail.py (4 allowed tests) |
| tool internal error → isError:true | **NO** | Only isError:false is asserted on success paths |
| notification (no id) handling | YES | test_mcp_server_smoke.py |
| shutdown handling | YES | test_mcp_server_smoke.py |

**Apply guardrail coverage is thorough** (both parameter gate and env-var gate, audit log, default path, invalid mode). The three gaps are all low-level JSON-RPC protocol error paths.

---

## A2A (9/14 covered)

**Source files audited:**
- `tests/unit/test_a2a_schema.py`
- `tests/unit/test_a2a_http_transport.py`
- `tests/unit/test_a2a_http_ssrf_hardening.py`
- `tests/unit/test_a2a_dns_rebinding_hardening.py`
- `tests/unit/test_a2a_local_shell_transport.py`
- `tests/unit/test_a2a_server.py`
- `tests/unit/test_a2a_roster.py`
- `tests/unit/test_roundtable_agent.py`
- `tests/integration/test_a2a_roundtable_e2e.py`
- `tests/integration/test_a2a_http_roundtrip.py`

| Scenario | Covered | Test location |
|----------|---------|---------------|
| AgentCard valid construction | YES | test_a2a_schema.py |
| AgentCard missing required field rejected | **NO** | — |
| A2ATask valid lifecycle | YES | test_a2a_schema.py, test_a2a_http_transport.py |
| A2AMessage invalid role/status rejected | **NO** | role is unconstrained str; no rejection test |
| mock transport happy path | YES | test_a2a_local_shell_transport.py |
| local_shell transport | YES | test_a2a_local_shell_transport.py |
| http transport happy path | YES | test_a2a_http_transport.py, test_a2a_http_roundtrip.py |
| http transport SSRF rejection (file/ftp/localhost/private/metadata) | YES | test_a2a_http_ssrf_hardening.py (9 sub-cases) |
| http transport DNS rebinding (public-then-private) | YES | test_a2a_dns_rebinding_hardening.py (10 cases) |
| http redirect to private rejected | YES | test_a2a_http_ssrf_hardening.py + test_a2a_dns_rebinding_hardening.py |
| http unreachable endpoint → FAILED task | YES | test_a2a_http_transport.py::test_send_task_unreachable_returns_failed |
| http timeout (max poll exhausted, server stays WORKING) | **NO** | Unreachable-host is covered; server-stays-WORKING not tested |
| roundtable party-mode independence (deep copy verified) | **NO** | Same context_id checked but mutation isolation not verified |
| roundtable synthesizer deterministic | YES | test_roundtable_agent.py + test_a2a_roundtable_e2e.py |

**SSRF + DNS rebinding coverage is excellent** (13 SSRF + 10 rebinding tests). The gaps are schema-level validation and one poll-exhaustion scenario.

---

## Schemas (2/6 covered)

**Source files audited:**
- `tests/unit/test_a2a_schema.py`
- `tests/unit/test_mcp_server.py` (MCPToolHandlerResult / MCPServerStatus importability)

| Scenario | Covered | Test location |
|----------|---------|---------------|
| pydantic model construction with valid data | YES | test_a2a_schema.py (all A2A models), test_mcp_server.py |
| missing required field rejected | **NO** | No test anywhere asserts ValidationError on missing required field |
| invalid enum value rejected | **NO** | A2ATaskStatus valid values confirmed; invalid never tested |
| nested model invalid rejected | **NO** | A2APart nesting only exercised with valid data |
| serialization → deserialization roundtrip | YES | test_a2a_schema.py::test_a2a_message_roundtrip |
| backward-compat for v0.1.0a1 schemas exported | **NO** | No frozen-snapshot import test; no __all__ guard |

Schema validation coverage is the weakest area in the codebase: only the happy-path construction and one roundtrip exist. All rejection paths are untested.

---

## Top 5 Uncovered Scenarios (Priority Order)

| # | Scenario | Surface | P-Priority | Rationale |
|---|----------|---------|-----------|-----------|
| 1 | **Pydantic missing required field rejected** | Schemas | P1 | Affects every model; a silent regression (e.g. removing a default) would go undetected |
| 2 | **tool internal error → structured isError:true** | MCP | P1 | Consumers (Claude, Cursor) depend on `isError:true` to distinguish tool failure from protocol error; untested handler exceptions could surface as unstructured crashes |
| 3 | **A2AMessage invalid role / A2ATaskStatus invalid enum via model_validate** | A2A / Schemas | P1 | Wire-format validation: a misbehaving remote agent sending `"role": "root"` or `"status": "unknown"` is never exercised |
| 4 | **http poll timeout (server stays WORKING until max attempts exhausted → FAILED)** | A2A | P2 | The unreachable-server path is covered, but the "slow server that never finishes" path leaves the retry budget logic untested |
| 5 | **MCP missing method field (well-formed JSON but no "method" key)** | MCP | P2 | Listed in smoke-test module docstring as a covered case but no test function was ever written; a JSON-RPC -32600 "Invalid Request" code path is dark |

---

## Notes for Phase 2 (Cov-I)

- Schema rejection tests should be added to `tests/unit/test_a2a_schema.py` using `pytest.raises(ValidationError)`.
- The tool-internal-error test belongs in `tests/unit/test_mcp_server.py` (mock a handler to raise, assert `isError:true` in result).
- The poll-exhaustion test fits in `tests/unit/test_a2a_http_transport.py` with a fake server that always returns `"status": "working"`.
- The missing-method-field test belongs in `tests/integration/test_mcp_server_smoke.py` as `test_missing_method_field_error()`.
- Backward-compat schema test: freeze a dict snapshot of key v0.1.0a1 fields and assert `model_validate` succeeds after any future schema change.
