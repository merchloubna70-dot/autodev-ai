# autodev MCP Server

autodev can be registered as an MCP (Model Context Protocol) server so that
Cursor, Claude Code, or any MCP-compatible client can invoke autodev's flows
as tools.

## Transport

stdio JSON-RPC 2.0 (line-delimited).  No extra dependencies — pure stdlib.

## Starting the server manually

```bash
autodev mcp-serve
```

Or pipe a request directly:

```bash
echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{}}}' \
  | autodev mcp-serve
```

## Registering in Claude Desktop / Claude Code

Add the following to `~/Library/Application Support/Claude/claude_desktop_config.json`
(macOS) or the equivalent on your platform:

```json
{
  "mcpServers": {
    "autodev": {
      "command": "autodev",
      "args": ["mcp-serve"]
    }
  }
}
```

If the `autodev` binary is not on `PATH`, use its absolute path:

```json
{
  "mcpServers": {
    "autodev": {
      "command": "/path/to/.venv/bin/autodev",
      "args": ["mcp-serve"]
    }
  }
}
```

## Registering in Cursor

Open **Settings → MCP → Add Server** and enter:

- **Name**: `autodev`
- **Command**: `autodev mcp-serve`  (or the absolute path above)
- **Transport**: `stdio`

## Available tools

| Tool | Description |
|------|-------------|
| `autodev_scan` | Scan a repo → `RepoScanResult` |
| `autodev_classify_input` | Classify free text → `InputClassification` |
| `autodev_create_prd` | Brief → PRD Markdown |
| `autodev_deliver_project` | Full delivery flow (dry-run or apply) |
| `autodev_run_issue` | Issue pipeline flow |
| `autodev_report` | Generate final delivery report |
| `autodev_roundtable` | BMAD party-mode multi-agent discussion |
| `autodev_release_check` | Release readiness check |
| `autodev_list_runs` | List recent run IDs for a repo |

## Security boundaries

| Boundary | Detail |
|----------|--------|
| **Path safety** | Tool calls that specify `repo_path` are validated by `mcp_server/path_safety.py` before any flow executes. Paths outside allowed roots are rejected. |
| **Apply-mode double gate** | `mode=apply` requires **both** `allow_apply=true` in the request body **and** `AUTODEV_MCP_ALLOW_APPLY=1` in the server's environment. Satisfying only one condition is not sufficient. |
| **Secret redaction** | All executor output piped through the MCP server passes through `utils/secret_redaction.py`; API keys and tokens are redacted before appearing in tool responses or audit logs. |
| **Per-caller authentication** | Per-caller auth tokens are **not implemented** in this alpha release. Any process that can connect to the stdio server has full tool access. Do not expose the server over a shared socket or network transport without an external auth proxy. |
| **Audit logging** | Set `AUTODEV_MCP_AUDIT_LOG=/path/to/audit.jsonl` to record every tool invocation (tool name, args, repo_path, outcome, timestamp) as an append-only JSONL file. |

## Notes

- **Long-running tools** (`autodev_deliver_project`, `autodev_run_issue`) execute
  synchronously in v1.  Future versions will emit `notifications/progress`
  JSON-RPC notifications during execution.
- Use `mode: "dry-run"` (the default) to plan without writing any files.
- Set `FACTORY_FORCE_MOCK=1` to run all tools offline with deterministic mock
  responses — useful in CI or testing.
- All logging goes to **stderr**; stdout is reserved for JSON-RPC protocol traffic.
