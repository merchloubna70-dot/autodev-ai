# Tutorial 07 — A2A Server (Agent-to-Agent)

autodev implements the **Agent-to-Agent (A2A)** protocol, letting external
agents — or other autodev instances — send tasks to it over HTTP.

This tutorial covers:

1. Starting the A2A server
2. Discovering the agent card
3. Registering a remote agent in your roster
4. Sending a task with `a2a-call`

---

## Architecture

```
External agent / autodev instance
        │   HTTP POST /tasks/send
        ▼
autodev a2a-serve (port 8421)
        │
        ▼
ExecutorRouter → Codex CLI / Claude Code CLI / Mock
        │
        ▼
HTTP response (A2ATask with result)
```

---

## Step 1 — Start the A2A server

```bash
autodev a2a-serve --port 8421 --bind 127.0.0.1
```

Expected output:

```
A2A server on http://127.0.0.1:8421
```

The server runs in the foreground. Open a second terminal for the next steps.

To bind to all interfaces (for cross-machine use):

```bash
autodev a2a-serve --port 8421 --bind 0.0.0.0
```

Note: Do not expose port 8421 to the public internet without adding an auth
token (see the Authentication section below).

---

## Step 2 — Discover the agent card

Every A2A-compliant server exposes its capabilities at `GET /.well-known/agent.json`.

```bash
curl -s http://127.0.0.1:8421/.well-known/agent.json | python -m json.tool
```

Example response:

```json
{
  "name": "autodev",
  "transport": "a2a-http",
  "endpoint": "http://127.0.0.1:8421",
  "skills": [
    "deliver-project",
    "fix-bug",
    "roundtable",
    "run-issue",
    "sprint"
  ],
  "version": "0.1.0"
}
```

---

## Step 3 — Register the server in your local roster

```bash
autodev a2a-register \
  --endpoint http://127.0.0.1:8421 \
  --name my-local-autodev \
  --save-to ~/.autodev/a2a-roster.json
```

Expected output:

```json
{
  "name": "my-local-autodev",
  "transport": "a2a-http",
  "endpoint": "http://127.0.0.1:8421",
  "skills": ["deliver-project", "fix-bug", "roundtable", ...]
}
registered to /Users/you/.autodev/a2a-roster.json
```

The roster file is used by `RoundtableAgent` to discover available participants
when recruiting by skill.

---

## Step 4 — Send a task with `a2a-call`

### Simple text task

```bash
autodev a2a-call \
  --endpoint http://127.0.0.1:8421 \
  --skill fix-bug \
  --task-json '{"text": "Fix the off-by-one in aggregate.py p99 calculation"}'
```

### Deliver a project

```bash
autodev a2a-call \
  --endpoint http://127.0.0.1:8421 \
  --skill deliver-project \
  --task-json '{"text": "Deliver a base62 slug library in Rust"}'
```

Expected output (the server echoes the completed A2ATask as JSON):

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "context_id": "...",
  "status": "completed",
  "history": [
    {"role": "user",   "parts": [{"kind": "text", "text": "Fix the off-by-one ..."}]},
    {"role": "agent",  "parts": [{"kind": "text", "text": "run_id=... success=True mock=True"}]}
  ],
  "metadata": {"skill": "fix-bug"}
}
```

---

## Step 5 — End-to-end: two autodev instances

In terminal A, start the first instance acting as a remote worker:

```bash
autodev a2a-serve --port 8421 --bind 127.0.0.1
```

In terminal B, use a second invocation (or a different project) to call it:

```bash
autodev a2a-call \
  --endpoint http://127.0.0.1:8421 \
  --skill roundtable \
  --task-json '{"text": "Should we use SQLite or PostgreSQL for the kanban board?"}'
```

The roundtable runs on the server process and the result is returned to the
caller over HTTP.

---

## Authentication

Set `AUTODEV_A2A_TOKEN` on both the server and the client:

```bash
# Server
AUTODEV_A2A_TOKEN=mysecrettoken autodev a2a-serve --port 8421

# Client
AUTODEV_A2A_TOKEN=mysecrettoken autodev a2a-call \
  --endpoint http://127.0.0.1:8421 \
  --skill fix-bug \
  --task-json '{"text": "..."}'
```

The token is sent as a `Bearer` header and validated by the server. Without
a matching token, requests are rejected with HTTP 401.

---

## Running as a background service

```bash
# Start in background, log to file
nohup autodev a2a-serve --port 8421 > /tmp/autodev-a2a.log 2>&1 &
echo "PID: $!"

# Check it is running
curl -s http://127.0.0.1:8421/.well-known/agent.json | python -m json.tool
```

---

## See also

- [Tutorial 05 — Roundtable party-mode](05-roundtable.md) — uses A2A internally
- [Tutorial 06 — MCP server](06-mcp-server.md)
- [Architecture reference](../architecture.md)
- [FAQ](../faq.md)
