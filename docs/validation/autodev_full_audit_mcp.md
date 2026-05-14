# MCP Server + Apply Guardrail Full Audit

**Round:** full_audit_mcp  
**Date:** 2026-05-14  
**Agent:** PreTag-D  

## Test Results

| Suite | File | Pass | Fail |
|-------|------|------|------|
| MCP Server Smoke | `tests/integration/test_mcp_server_smoke.py` | 10 | 0 |
| Apply Guardrail | `tests/integration/test_mcp_apply_guardrail.py` | 19 | 0 |
| **Total** | | **29** | **0** |

## Guardrail Symbol Inspection (`src/autodev/mcp_server/tools.py`)

| Symbol | Present | Location |
|--------|---------|----------|
| `AUTODEV_MCP_ALLOW_APPLY` env var constant | yes | line 21: `_ENV_ALLOW_APPLY = "AUTODEV_MCP_ALLOW_APPLY"` |
| `allow_apply` parameter (deliver_project) | yes | line 301–308, `"default": False` |
| `allow_apply` parameter (run_issue) | yes | line 418–425, `"default": False` |
| `_check_apply_mode_allowed()` dual-gate | yes | lines 75–96, checks both param AND env var |
| `AUTODEV_MCP_AUDIT_LOG` env var constant | yes | line 22: `_ENV_AUDIT_LOG = "AUTODEV_MCP_AUDIT_LOG"` |
| `_write_audit_log()` called on deny/allow | yes | lines 85, 93, 96 |

## Registered MCP Tools (9 confirmed)

1. `autodev_scan`
2. `autodev_classify_input`
3. `autodev_create_prd`
4. `autodev_deliver_project`
5. `autodev_run_issue`
6. `autodev_report`
7. `autodev_roundtable`
8. `autodev_release_check`
9. `autodev_list_runs`

## Dual-Gate Logic Confirmed

`_check_apply_mode_allowed()` enforces both conditions independently:
- Deny if `allow_apply` param is not `True`
- Deny if `AUTODEV_MCP_ALLOW_APPLY` env var is not `"1"`
- All denials write to audit log before returning
- Only when both pass does `_write_audit_log(..., "allowed")` fire

## Diff vs R3-B

No regression. R3-B established the apply guardrail; all symbols present and tests continue to pass at 29/29 (no new failures introduced).

## Verdict

**mcp_stable_with_dual_gate** — all 29 tests pass, dual-gate guardrail intact, 9 tools registered, audit log path referenced.
