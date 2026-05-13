# A2A HTTP Client — Connecting autodev to External A2A Agents

autodev can act as an **A2A client**, sending tasks to any external agent that
speaks the [A2A protocol](https://a2a-protocol.org/latest/specification/)
over HTTP + JSON-RPC.

## Transport: `a2a-http`

Set `AgentCard.transport = "a2a-http"` and `AgentCard.endpoint = "<base URL>"`
to route tasks through `A2AHttpTransport`. The transport uses stdlib
`urllib.request` — no extra pip dependencies.

### Client-side flow

1. `GET <endpoint>/.well-known/agent.json` — discover capabilities (AgentCard).
2. `POST <endpoint>/tasks/send` — submit an `A2ATask` body (JSON).
3. If the response is not already `completed/failed/canceled`, poll
   `GET <endpoint>/tasks/{id}` at `poll_interval` second intervals until a
   terminal status or `max_poll_attempts` is exhausted.

All methods return `A2ATask`; errors are expressed as `status=FAILED` with a
descriptive text artifact. No exceptions are raised.

## Bearer Authentication

Set the `AUTODEV_A2A_TOKEN` environment variable. The token is sent as:

```
Authorization: Bearer <token>
```

```bash
export AUTODEV_A2A_TOKEN="my-secret-token"
autodev a2a-register --endpoint http://localhost:8421
```

## CLI Commands

### `autodev a2a-register`

Discover an `AgentCard` from a remote endpoint and save it to a local roster
file (`~/.autodev/a2a-roster.json` by default).

```bash
autodev a2a-register --endpoint http://localhost:8421
autodev a2a-register --endpoint http://localhost:8421 --name my-agent --save-to /tmp/roster.json
```

### `autodev a2a-call`

Build an `A2ATask` and send it directly to a remote agent.

```bash
autodev a2a-call --endpoint http://localhost:8421 --skill scan --task-json '{"text": "scan src/"}'
```

## Provider Examples

### Google ADK Agent

Google ADK agents expose a standard A2A endpoint. Discover the card from:

```
GET http://<adk-host>:<port>/.well-known/agent.json
```

Register it:

```bash
export AUTODEV_A2A_TOKEN="<google-adk-bearer-token>"
autodev a2a-register --endpoint http://my-adk-agent.example.com
```

### AWS Bedrock AgentCore

AWS Bedrock AgentCore A2A endpoints follow the same pattern. Use the Bedrock
agent's HTTPS URL and a short-lived AWS SigV4 token or API key passed via
`AUTODEV_A2A_TOKEN`.

```bash
export AUTODEV_A2A_TOKEN="$(aws bedrock-agentcore get-token ...)"
autodev a2a-register --endpoint https://bedrock-agentcore.us-east-1.amazonaws.com/agents/my-agent
```

### Azure AI Foundry

Azure AI Foundry exposes agents at:

```
https://<account>.services.ai.azure.com/agents/v1.0/<deployment>/
```

Pass an Azure Entra token as the bearer token.

## Python API

```python
import os
from autodev.adapters.a2a.transports.http import A2AHttpTransport
from autodev.schemas import AgentCard, A2ATask, A2ATaskStatus

transport = A2AHttpTransport(
    endpoint="http://localhost:8421",
    auth_token=os.environ.get("AUTODEV_A2A_TOKEN"),
    timeout_sec=60,
    poll_interval=1.0,
    max_poll_attempts=60,
)

# Discover capabilities
card = transport.discover_agent_card()   # AgentCard | None
reachable = transport.is_reachable()     # bool

# Send a task
result: A2ATask = transport.send_task(card, my_task)
assert result.status in (A2ATaskStatus.COMPLETED, A2ATaskStatus.FAILED)
```

## Schemas

Two new Pydantic models are available in `autodev.schemas`:

- `A2AHttpTransportConfig` — transport configuration value object.
- `A2ARemoteAgentRegistration` — roster entry for a discovered remote agent.
