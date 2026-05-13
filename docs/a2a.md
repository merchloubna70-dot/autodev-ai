# A2A Integration in autodev

## What is A2A?

**A2A (Agent-to-Agent)** is an open interoperability protocol published by the Linux Foundation in April 2025, now backed by 150+ organisations (Google, Atlassian, Salesforce, and others). The canonical spec lives at <https://a2a-protocol.org>.

A2A defines a JSON-over-HTTP contract for how independent AI agents negotiate tasks, exchange messages, and return structured results — without sharing internal state or model weights. Each agent is a black box that receives a `Task` object (containing a message history), executes independently, and returns a completed `Task`.

## autodev's Compatibility Model

autodev does **not** run an A2A HTTP server by default. Instead it implements the schema layer and a multi-transport client so the same `AgentCard` / `A2ATask` objects work across:

| Transport | Status | When used |
|---|---|---|
| `mock` | Stable | Tests / `FACTORY_FORCE_MOCK=1` |
| `local-shell` | Stable | Dev machines with `claude` CLI available |
| `a2a-http` | Future (Step 4) | Remote agents exposing an A2A endpoint |

The `A2AClient` reads `card.transport` and routes to the correct `BaseA2ATransport`. Unknown transports fall back to `MockTransport` (fail-safe).

## 5 Default AgentCards

`AgentRoster.default()` pre-registers five specialist cards:

| Name | Model hint | Skills |
|---|---|---|
| `architect` | `opus` | design-review, adr, technology-selection, scalability |
| `security` | `sonnet` | sast, owasp, secrets-detection, auth-review, input-validation |
| `performance` | `sonnet` | complexity-analysis, database-query-review, memory-profiling, latency |
| `ux` | `sonnet` | api-review, dx, interface-design, ergonomics, error-messages |
| `style` | `haiku` | code-review, naming-conventions, documentation, formatting |

**System prompts (abbreviated to ≤2 lines each):**

- **architect** — "You are a senior software architect consultant on a non-interactive hotline. Evaluate architecture decisions, trade-offs, and system designs."
- **security** — "You are a senior security engineer on a non-interactive hotline. Identify vulnerabilities, insecure patterns, and compliance gaps."
- **performance** — "You are a senior performance engineer on a non-interactive hotline. Analyze code for performance bottlenecks, inefficient patterns, and scalability limits."
- **ux** — "You are a UX and developer-experience specialist on a non-interactive hotline. Evaluate APIs, CLI interfaces, and code ergonomics from a user-perspective."
- **style** — "You are a code style and readability specialist on a non-interactive hotline. Review code for style consistency, naming conventions, documentation, and readability."

## Using RoundtableAgent from Python

```python
from autodev.agents.roundtable import RoundtableAgent

rt = RoundtableAgent.default() if hasattr(RoundtableAgent, 'default') else RoundtableAgent()
conversation, synth_msg = rt.discuss_and_synthesize(
    topic="Should we switch from REST to gRPC for internal services?",
    needed_skills=["architecture", "security", "perf"],
)
print(synth_msg.parts[0].text)
```

`discuss_and_synthesize` is a convenience wrapper that:
1. Calls `discuss(...)` — fans out the topic to N independent agents in parallel.
2. Calls `synthesize(conversation)` — runs a dedicated synthesizer agent over all responses.

Returns `(A2AConversation, A2AMessage)`.

## Registering a Custom AgentCard

```python
from autodev.schemas import AgentCard
from autodev.adapters.a2a.roster import AgentRoster

roster = AgentRoster.default()
roster.register(AgentCard(
    name="legal",
    description="Legal risk reviewer for contracts and compliance.",
    skills=["gdpr", "contract-review", "risk-assessment"],
    transport="local-shell",
    model_hint="opus",
    system_prompt=(
        "You are a legal risk specialist on a non-interactive hotline. "
        "Flag legal risks, compliance gaps, and contract issues."
    ),
))
```

Pass the custom roster to `RoundtableAgent(roster=roster)`.

## Why This Beats ThreadPoolExecutor-Faking-Multiple-Voices

The **BMAD party-mode invariant** requires that each agent voice be genuinely independent:

> **Each card runs in its OWN subprocess with its OWN `system_prompt`.**

A `ThreadPoolExecutor` that calls the same LLM endpoint with the same system prompt will produce statistically correlated (and often identical) responses — it is roleplay, not independent expertise. autodev enforces independence at two levels:

1. **Transport isolation** — `LocalShellTransport` spawns a separate `claude` CLI subprocess per card. The subprocess inherits only the card's `system_prompt`, not any shared Python state.
2. **Mock determinism keyed on `card.name`** — `MockTransport._mock_response(prompt, card_name)` computes `sha256(prompt + card_name)[:16]`. Different cards on the same prompt produce different (but reproducible) mock keys, so tests prove that card identity drives output divergence.

This means even under `FACTORY_FORCE_MOCK=1`, a test can assert that `architect` and `security` return *different* mock texts for the same topic — which would be impossible if both were served by a single LLM call with a single system prompt.

## Future: A2AHttpTransport (Step 4, not yet implemented)

When a card carries an `endpoint` field (e.g. `"https://agents.example.com/a2a/legal"`), a future `A2AHttpTransport` will POST the `A2ATask` JSON to that URL and poll until the agent returns a completed task. The `A2AClient` transport registry will be extended with:

```python
_TRANSPORT_REGISTRY["a2a-http"] = A2AHttpTransport
```

No changes to `RoundtableAgent` or `AgentCard` are needed — endpoint routing is entirely inside the transport layer.
