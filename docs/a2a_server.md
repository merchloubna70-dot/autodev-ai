# autodev A2A HTTP Server

`autodev` can act as an A2A-compatible HTTP server so external agents (Google ADK, Amazon Bedrock, Azure AI, custom) can send tasks to it.

## Starting the server

```bash
# Local-only (default) — safe for development
autodev a2a-serve --port 8421

# Explicit bind to all interfaces (prints a security warning)
autodev a2a-serve --port 8421 --bind 0.0.0.0
```

Output:

```
A2A server on http://127.0.0.1:8421
```

## Bearer-token authentication

Set the environment variable `AUTODEV_A2A_TOKEN` before starting the server. When set, every request must include `Authorization: Bearer <token>`.

```bash
export AUTODEV_A2A_TOKEN=my-secret-token
autodev a2a-serve --port 8421
```

When the variable is unset or empty, all requests are allowed (suitable for local-only use).

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/.well-known/agent.json` | Returns autodev's AgentCard |
| `POST` | `/tasks/send` | Dispatch a task to a skill handler |
| `GET` | `/tasks/{id}` | Fetch a stored task by ID |
| `GET` | `/tasks/{id}/events` | SSE stream of task status events |

## AgentCard

```bash
curl http://localhost:8421/.well-known/agent.json
```

Response:

```json
{
  "name": "autodev",
  "description": "CrewAI + Codex CLI + Claude Code multi-CLI software factory...",
  "version": "1.0.0",
  "skills": ["deliver-project", "run-issue", "scan", "report", "release-check",
             "roundtable", "classify-input", "create-prd"],
  "transport": "a2a-http",
  "endpoint": "http://127.0.0.1:8421",
  "auth_scheme": "bearer"
}
```

## Sending a task

A task body must include `metadata.skill` to select a handler.

### Example: scan a repo

```bash
curl -X POST http://localhost:8421/tasks/send \
  -H "Content-Type: application/json" \
  -d '{
    "id": "task-001",
    "context_id": "ctx-001",
    "metadata": {"skill": "scan", "repo_path": "."},
    "history": [
      {"message_id": "m1", "role": "user",
       "parts": [{"kind": "text", "text": "scan this repo"}]}
    ]
  }'
```

### Example: classify input

```bash
curl -X POST http://localhost:8421/tasks/send \
  -H "Content-Type: application/json" \
  -d '{
    "id": "task-002",
    "context_id": "ctx-002",
    "metadata": {"skill": "classify-input"},
    "history": [
      {"message_id": "m2", "role": "user",
       "parts": [{"kind": "text", "text": "Fix the login bug in auth.py issue #42"}]}
    ]
  }'
```

### Example: roundtable with auth

```bash
curl -X POST http://localhost:8421/tasks/send \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer my-secret-token" \
  -d '{
    "id": "task-003",
    "context_id": "ctx-003",
    "metadata": {
      "skill": "roundtable",
      "topic": "Should we switch from REST to GraphQL?",
      "skills": ["architecture", "security", "ux"],
      "max_participants": 3
    },
    "history": []
  }'
```

## Fetching a task by ID

```bash
curl http://localhost:8421/tasks/task-001
```

## SSE event stream

```bash
curl -N http://localhost:8421/tasks/task-001/events
```

The server emits two SSE events per task:
1. `task-status` — current status snapshot
2. `task-complete` — full task JSON

## Available skills

| Skill | Handler |
|-------|---------|
| `scan` | `RepoScanner` |
| `classify-input` | `InputClassifierAgent` |
| `create-prd` | PRD writer pipeline (PM + Analyst + Writer) |
| `roundtable` | `RoundtableAgent` |
| `deliver-project` | `ProjectDeliveryFlow` (dry-run, mock-safe) |
| `release-check` | `ReleaseFlow` (requires `run_id` + `repo_path` in metadata) |

## Registering autodev in Google ADK

In your ADK agent configuration, add autodev as a remote A2A agent:

```python
from google.adk.agents import RemoteA2AAgent

autodev = RemoteA2AAgent(
    agent_card_url="http://localhost:8421/.well-known/agent.json",
    auth_headers={"Authorization": "Bearer my-secret-token"},
)
```

## Security notes

- Default bind is `127.0.0.1` (local only). Never expose port 8421 externally without setting `AUTODEV_A2A_TOKEN`.
- Use a reverse proxy (nginx/caddy) with TLS for production deployments.
- The server shuts down cleanly on `SIGTERM`.
