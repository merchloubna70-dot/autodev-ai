# Tutorial 06 — Running autodev as an MCP Server

autodev can expose its capabilities as a **Model Context Protocol (MCP)**
server over stdio. This lets Claude Desktop (or any MCP-compatible client)
call autodev tools directly from a conversation.

---

## How it works

The `mcp-serve` command starts a JSON-RPC 2.0 loop on stdin/stdout. The
MCP server exposes autodev's pipeline commands as callable tools. Claude
Desktop launches the process, sends requests, and receives responses — all
transparently.

```
Claude Desktop
     │  JSON-RPC 2.0 over stdio
     ▼
autodev mcp-serve
     │
     ▼
ExecutorRouter → Codex CLI / Claude Code CLI / Mock
```

---

## Step 1 — Verify the command exists

```bash
autodev mcp-serve --help
```

Expected output:

```
Usage: autodev mcp-serve [OPTIONS]

  Start autodev as an MCP server on stdio (JSON-RPC 2.0).

  Reads JSON-RPC requests line-by-line from stdin and writes responses to
  stdout. All logging goes to stderr.
```

---

## Step 2 — Register with Claude Desktop

Open (or create) your Claude Desktop configuration file:

- **macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows:** `%APPDATA%\Claude\claude_desktop_config.json`
- **Linux:** `~/.config/Claude/claude_desktop_config.json`

Add the following entry inside the `"mcpServers"` object:

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

If `autodev` is not on your system `PATH`, use the full absolute path to the
binary. To find it:

```bash
which autodev
# e.g. /Users/you/.venv/bin/autodev
```

Then:

```json
{
  "mcpServers": {
    "autodev": {
      "command": "/Users/you/.venv/bin/autodev",
      "args": ["mcp-serve"]
    }
  }
}
```

---

## Step 3 — Restart Claude Desktop

Quit and reopen Claude Desktop. autodev will appear in the MCP tools panel.

---

## Step 4 — Use autodev tools from Claude

In a Claude Desktop conversation, you can now ask Claude to invoke autodev
capabilities directly. For example:

> "Use autodev to create a project plan from this brief: [paste brief text]"

Claude will call the appropriate autodev MCP tool (`deliver-project`,
`fix-bug`, `roundtable`, etc.) and stream results back into the conversation.

---

## Environment variables for the MCP process

Claude Desktop inherits the environment from its launch context, which on
macOS is usually sparse. If your credentials are not picked up automatically,
set them in the config:

```json
{
  "mcpServers": {
    "autodev": {
      "command": "/Users/you/.venv/bin/autodev",
      "args": ["mcp-serve"],
      "env": {
        "OPENAI_API_KEY": "sk-...",
        "ANTHROPIC_API_KEY": "sk-ant-...",
        "FACTORY_FORCE_MOCK": "0"
      }
    }
  }
}
```

For mock-only mode (no API keys required):

```json
{
  "mcpServers": {
    "autodev": {
      "command": "autodev",
      "args": ["mcp-serve"],
      "env": {
        "FACTORY_FORCE_MOCK": "1"
      }
    }
  }
}
```

---

## Testing the MCP server manually

You can smoke-test the server without Claude Desktop by piping JSON-RPC
requests on stdin:

```bash
echo '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}' \
  | autodev mcp-serve 2>/dev/null
```

Expected (abbreviated):

```json
{"jsonrpc":"2.0","id":1,"result":{"tools":[{"name":"deliver_project",...},{"name":"fix_bug",...}]}}
```

---

## See also

- [Tutorial 07 — A2A server](07-a2a-server.md)
- [Tutorial 05 — Roundtable party-mode](05-roundtable.md)
- [FAQ — How to use my own Anthropic Max subscription](../faq.md)
