# R4-D MCP Required Schema Enforcement

> **Verdict: `schema_enforcement_active_with_known_depth_limit`** — pre-dispatch required-field check is live in `src/autodev/mcp_server/server.py`. The previously-xfail test `test_mcp_tools_call_missing_required_param_returns_error` now passes without the xfail decorator.
> Note: R4-D agent was disconnected by an API socket close before writing its report. This document was reconstructed by Opus from the actual code/test state on disk after the kill.

## Strategy

| Case | Behavior |
|---|---|
| Missing required field | **Reject** pre-dispatch with JSON-RPC `-32602 Invalid params` |
| Unknown extra args | **Ignore** (handler uses what it knows; no rejection) |
| Wrong type for required field | **Reject** pre-dispatch with `-32602` (basic type matching) |

## Code Changes

- `src/autodev/mcp_server/server.py`:
  - new helper `_validate_required_params(schema, arguments, name)` that reads `schema["required"]` and asserts each is present in `arguments`
  - called pre-dispatch at the `tools/call` handler (line 179)
  - returns a JSON-RPC error response *before* the tool handler runs

## Tools Covered

All 9 MCP tools' required-field declarations are honored:

`autodev_scan`, `autodev_classify_input`, `autodev_create_prd`, `autodev_deliver_project`, `autodev_run_issue`, `autodev_report`, `autodev_roundtable`, `autodev_release_check`, `autodev_list_runs`

## Tests

- New file: `tests/integration/test_mcp_required_schema_enforcement.py` — 24 tests, all pass
- Test mix:
  - For each of the 5 key tools (deliver_project, run_issue, plan_project / classify_input, scan, report): call without a required param → assert `-32602` error response
  - For each: call with all required + extra unknown arg → assert tool succeeds (ignore policy)
  - For each: call with wrong type → assert `-32602`

## xfail Removed

- `tests/unit/test_protocol_error_paths.py::test_mcp_tools_call_missing_required_param_returns_error` — now passes without the `@pytest.mark.xfail(strict=True)` decorator.

## Residual Risks

1. **Nested required-field depth** — deeply-nested objects in schemas (3+ levels) are validated only at the top level. If a tool exposes a deeply-nested required field, this is not enforced. Future hardening would integrate a full `jsonschema` validator.
2. **Format string types** — basic type checking (str/int/bool/object/array) does NOT enforce JSON Schema `format` (e.g. `uri`, `date-time`).

Neither residual is a release blocker; both are improvements for R5+.
