# autodev A2A Protocol Audit

**Round:** a2a_protocol_audit  
**Date:** 2026-05-14  
**Auditor:** Agent F — Release Hardening  
**Verdict:** `minor_gaps`

---

## Scope

| Component | File |
|---|---|
| Client | `src/autodev/adapters/a2a/client.py` |
| Roster | `src/autodev/adapters/a2a/roster.py` |
| Server | `src/autodev/adapters/a2a/server.py` |
| Handlers | `src/autodev/adapters/a2a/handlers.py` |
| Transport — base | `src/autodev/adapters/a2a/transports/base.py` |
| Transport — local_shell | `src/autodev/adapters/a2a/transports/local_shell.py` |
| Transport — mock | `src/autodev/adapters/a2a/transports/mock.py` |
| Transport — http | `src/autodev/adapters/a2a/transports/http.py` |
| Schemas | `src/autodev/schemas.py` (11 A2A models) |
| Roundtable | `src/autodev/agents/roundtable.py` |

---

## Invariant Check Results

### 1. Party-mode independence — PASS

`RoundtableAgent.discuss()` (roundtable.py line 230) dispatches via:

```python
executor.submit(self._client.send, card, base_task.model_copy(deep=True))
```

Every card receives a deep copy of `base_task`. Agents share no mutable state. The `results_by_card: dict[str, A2ATask]` keyed by `card.name` collects results independently of completion order, and assembly back into `A2AConversation` iterates the original `cards` list for a stable output order. No cross-agent context leakage was found.

### 2. Card-task mapping — PASS

The prior zip-based mapping has been replaced by a `futures: dict[Future, AgentCard]` pattern. `as_completed` resolves to the Future key, and `futures[future]` gives back the originating card. No zip truncation is possible. Comment at line 224 explicitly documents this fix.

### 3. Synthesizer determinism — PASS (with caveat)

`synthesize()` consumes `conversation.messages` in insertion order, which is already stable because `discuss()` iterates `cards` (not the futures dict) when assembling `A2AConversation.messages`. However, `synthesize()` does not internally sort agent messages — it relies entirely on upstream ordering. This is currently correct but fragile. See Finding F4.

### 4. HTTP transport boundary — PARTIAL FAIL

| Check | Result |
|---|---|
| Default server bind `127.0.0.1` | PASS — `A2AHttpServer.__init__` defaults `bind="127.0.0.1"` |
| `0.0.0.0` warning | PASS — `serve_forever()` prints a loud warning |
| Bearer auth (server-side) | PASS — `_check_auth()` validates `Authorization: Bearer <token>` |
| Bearer auth (client-side) | PASS — `A2AHttpTransport.__init__` reads `AUTODEV_A2A_TOKEN` from env |
| URL scheme validation (client-side) | FAIL — no check; any scheme accepted (file://, ftp://, IMDS) |
| Private IP / SSRF protection (client-side) | FAIL — no host allowlist or RFC-1918 rejection |

### 5. AgentCard validation — PARTIAL FAIL

`AgentCard.name` is a required `str` (no default). `skills` and `transport` are present with sensible defaults. However:
- No validator enforces `endpoint` is non-None/non-empty when `transport == "a2a-http"`.
- An `a2a-http` card with `endpoint=None` silently produces all-FAILED tasks.

### 6. A2ATask error states — PASS

`A2ATaskStatus.FAILED` is handled at every boundary:
- `LocalShellTransport.send_task()`: non-zero exit → FAILED artifact.
- `MockTransport.send_task()`: exception path → FAILED artifact.
- `A2AHttpTransport.send_task()`: HTTP errors, connection errors, parse errors → FAILED.
- `A2AHttpServer._handle_tasks_send()`: handler exception → FAILED task stored and returned.
- `RoundtableAgent.discuss()`: future exception → synthesized FAILED task in `results_by_card`.

### 7. Invalid message handling — SILENTLY IGNORED (partial)

JSON parse failures return HTTP 400 (correct). But `A2ATask.model_validate(data)` failures (invalid task schema) silently construct a minimal stand-in task and proceed to the skill handler, rather than returning 400. Malformed history or parts are swallowed. See Finding F2.

---

## Findings

### F1 — HIGH: No SSRF protection in A2AHttpTransport

`http.py` passes the `endpoint` URL directly to `urllib.request.urlopen` with no scheme check, no host validation, and no RFC-1918 / link-local rejection. An attacker controlling the endpoint (via a malicious discovered AgentCard or API call) could probe internal infrastructure, including cloud IMDS endpoints (`http://169.254.169.254/`).

**Fix:** Before issuing any request, validate that the parsed URL scheme is `http` or `https` and that the hostname does not resolve to a private or link-local address.

### F2 — MEDIUM: Silent fallback on malformed A2ATask (server)

`server.py` lines 236-249: when `A2ATask.model_validate(data)` raises, the server silently builds a minimal task from raw dict fields and forwards it to the skill handler. A completely invalid payload is accepted as a valid task with no 400 response. This makes server-side protocol enforcement impossible.

**Fix:** Catch the Pydantic `ValidationError`, extract its detail, and return `HTTP 400` with the validation error message.

### F3 — MEDIUM: AgentCard missing transport/endpoint cross-validation

No Pydantic `model_validator` enforces that `endpoint` is non-empty when `transport == "a2a-http"`. Registration succeeds silently; all subsequent sends fail with generic FAILED tasks.

**Fix:** Add a `@model_validator(mode="after")` to `AgentCard` that raises `ValueError` when `transport == "a2a-http"` and `endpoint` is falsy.

### F4 — LOW: Synthesizer determinism relies on upstream ordering (fragile)

`synthesize()` iterates `conversation.messages` without sorting — correctness depends on `discuss()` inserting messages in stable card order. A future refactor breaking that assumption would silently produce non-deterministic synthesis output.

**Fix:** Inside `synthesize()`, sort `agent_msgs` by a stable key (e.g., the card-name prefix in the tagged text part) before building `agent_transcript`.

### F5 — LOW: A2ATask.id not validated — SSE newline injection possible

`task.id` is an unconstrained `str`. It is interpolated into SSE event JSON (server.py line ~194). A task ID containing `\n` or `\r\n` could inject spurious SSE event boundaries.

**Fix:** Add a `field_validator` on `A2ATask.id` (and `context_id`) that rejects values containing whitespace or non-UUID characters.

---

## Test Results

```
81 passed, 762 deselected in 15.29s
```

All 81 A2A and roundtable-related tests pass. Tests cover: roster find/persist, schema round-trips, HTTP transport send/poll/discover, local shell fallback-to-mock, server endpoints (agent card, task send, task get, SSE events, bearer auth), and roundtable discuss/synthesize flows.

---

## A2A Schema Inventory (11 models)

| Model | File location |
|---|---|
| `A2APart` | schemas.py:959 |
| `A2AMessage` | schemas.py:967 |
| `A2ATaskStatus` | schemas.py:976 |
| `A2ATask` | schemas.py:985 |
| `AgentCard` | schemas.py:996 |
| `A2ARosterEntry` | schemas.py:1010 |
| `A2AConversation` | schemas.py:1016 |
| `A2AHttpServerConfig` | schemas.py:1044 |
| `A2AServerTaskRecord` | schemas.py:1052 |
| `A2AHttpTransportConfig` | schemas.py:1063 |
| `A2ARemoteAgentRegistration` | schemas.py:1072 |

---

## Summary Table

| Invariant | Status |
|---|---|
| Party-mode independence | PASS |
| Card-task mapping (no zip) | PASS |
| Synthesizer determinism | PASS (fragile) |
| HTTP server localhost default | PASS |
| HTTP bearer auth | PASS |
| HTTP SSRF protection | FAIL |
| AgentCard field validation | PARTIAL |
| Invalid message handling | PARTIAL |
| A2ATaskStatus.FAILED coverage | PASS |
| Test suite (81/81) | PASS |
