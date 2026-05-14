# MCP Server — Per-Caller Authentication & Scope-Based Authorization

## Overview

The autodev MCP server supports two authentication modes:

- **Legacy mode** (default): single shared token via `AUTODEV_A2A_TOKEN`, or no auth on
  stdio. All requests carry `caller_id = "legacy_shared_token"` in audit logs.
- **Per-caller mode**: each caller has its own token + scope set, loaded from a JSON
  registry file pointed to by `AUTODEV_MCP_IDENTITIES`.

## Identity Registry Format

Set `AUTODEV_MCP_IDENTITIES=/path/to/identities.json` to activate per-caller mode.

```json
{
  "ci-bot": {
    "display_name": "CI Pipeline Bot",
    "scopes": ["mcp:read", "mcp:write"],
    "hashed_token": "sha256:<64-hex-chars>",
    "expires_at": "2027-01-01T00:00:00Z"
  },
  "deploy-agent": {
    "display_name": "Deploy Agent",
    "scopes": ["mcp:read", "mcp:write", "mcp:apply"],
    "hashed_token": "sha256:<64-hex-chars>"
  }
}
```

Fields:
- `hashed_token` — `sha256:` prefix + SHA-256 hex digest of the raw Bearer token.
  Generate with: `python3 -c "import hashlib; print('sha256:' + hashlib.sha256(b'YOUR_TOKEN').hexdigest())"`
- `scopes` — list of scopes granted to this caller (see Scope Vocabulary below).
- `display_name` — human-readable label for audit logs (optional, defaults to `caller_id`).
- `expires_at` — optional ISO-8601 expiry datetime. Token rejects after this time.

## Scope Vocabulary

| Scope | Grants access to |
|---|---|
| `mcp:read` | `autodev_scan`, `autodev_list_runs`, `autodev_report`, `autodev_release_check` |
| `mcp:write` | `autodev_classify_input`, `autodev_create_prd`, `autodev_roundtable`, `autodev_run_issue`, `autodev_deliver_project` |
| `mcp:apply` | Required third gate for `mode=apply` on `autodev_deliver_project` and `autodev_run_issue` |

## Apply-Mode Triple Gate

Apply mode (`mode=apply`) now requires ALL three of:

1. **mcp:apply scope** — caller identity must include `mcp:apply` in its scope list.
2. **Server env flag** — `AUTODEV_MCP_ALLOW_APPLY=1` must be set on the server process.
3. **Request opt-in** — `allow_apply=true` must be passed in the tool arguments.

Any missing gate returns `isError: true` with a descriptive denial reason in the content.

In legacy mode the identity automatically has all scopes, so only gates 2 and 3 apply
(preserving backward compatibility with existing single-token deployments).

## Audit Log Enhancement

Every audit log entry now includes a `caller_id` field:

```json
{
  "timestamp": "2026-05-14T10:00:00Z",
  "caller_id": "ci-bot",
  "tool": "autodev_deliver_project",
  "params": {"repo_path": "/repo", "mode": "apply", "allow_apply": true},
  "repo_path": "/repo",
  "decision": "allowed"
}
```

In legacy mode: `"caller_id": "legacy_shared_token"`.

## Backward Compatibility

- If `AUTODEV_MCP_IDENTITIES` is **not set**, the server operates in legacy mode.
- Legacy mode with `AUTODEV_A2A_TOKEN` set: existing deployments continue to work unchanged.
- Legacy mode with no token configured (stdio trust): all requests pass through.
- The existing apply-mode double gate (env + flag) is preserved; the scope check is a
  no-op in legacy mode because `legacy_shared_token` has all scopes.

## Error Codes

| Code | Meaning |
|---|---|
| `-32001` | Unauthorized — missing or invalid Bearer token |
| `-32002` | Forbidden — caller lacks required scope for the tool |

## Environment Variables

| Variable | Purpose |
|---|---|
| `AUTODEV_MCP_IDENTITIES` | Path to per-caller identity registry JSON (activates per-caller mode) |
| `AUTODEV_A2A_TOKEN` | Legacy single shared token (only used when `AUTODEV_MCP_IDENTITIES` is unset) |
| `AUTODEV_MCP_ALLOW_APPLY` | Set to `1` to enable apply-mode (gate 2 of 3) |
| `AUTODEV_MCP_AUDIT_LOG` | Path to append structured audit log entries (default: `/tmp/autodev_mcp_audit.log`) |
