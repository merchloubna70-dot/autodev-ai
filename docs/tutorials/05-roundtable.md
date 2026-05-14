# Tutorial 05 — Roundtable Party-Mode

The `roundtable` command runs a BMAD party-mode discussion: multiple independent
agent voices are recruited by skill, each receives the same topic, and a
synthesis agent produces a unified recommendation.

Each participant is backed by a real `claude` CLI subprocess (one per agent
card). Set `FACTORY_FORCE_MOCK=1` to use deterministic stubs in CI or when
you have no API key.

---

## Basic usage

```bash
autodev roundtable \
  --topic "Should we add a streaming API to the log-analyzer service?" \
  --skills security,arch \
  --repo-path /tmp/my-project
```

Expected terminal output (abbreviated):

```
Synthesis:
The roundtable reached consensus that a streaming API is feasible but should
be gated behind an opt-in flag. Security raised concerns about unbounded
connection lifetime — recommend a server-side timeout of 30 s. Architecture
noted that the existing NGINX log parser is synchronous; a generator-based
adapter would suffice for MVP without a full async rewrite.

Recommended next step: prototype with a 30 s server timeout + async generator
adapter, then re-evaluate at sprint-002 retro.

wrote /tmp/my-project/.dev-factory/roundtables/rt-20240514-143012-a1b2c3.json
```

---

## Available skill tokens

Pass any comma-separated combination. Common values:

| Token | Agent persona |
|-------|--------------|
| `security` | Security engineer: threat model, OWASP, input validation |
| `arch` | Systems architect: component boundaries, scalability |
| `perf` | Performance engineer: latency, throughput, profiling |
| `ux` | UX designer: user flow, accessibility, error messaging |
| `pm` | Product manager: scope, priority, user value |
| `legal` | Compliance & legal: data handling, licensing |
| `sre` | Site reliability: observability, runbooks, SLOs |
| `qa` | QA engineer: test strategy, edge cases, regression risk |

Custom tokens are accepted — the agent will adopt a persona matching the skill
name if it is not in the list above.

---

## Controlling the participant count

```bash
autodev roundtable \
  --topic "Evaluate three approaches for rate-limiting the public API" \
  --skills security,arch,perf,sre \
  --max-participants 3 \
  --repo-path /tmp/my-project
```

With `--max-participants 3` only the first three skills from the list are
recruited; the fourth (`sre`) is left out. Increase the limit to include all:

```bash
  --max-participants 4
```

Default: `4`.

---

## Mock mode (no API key required)

```bash
FACTORY_FORCE_MOCK=1 autodev roundtable \
  --topic "Caching strategy for the slug decoder" \
  --skills arch,perf \
  --repo-path /tmp/my-project
```

Mock agents produce deterministic canned responses. The conversation and
synthesis are still written to `.dev-factory/roundtables/` exactly as in real
mode, so you can inspect the JSON structure without spending tokens.

---

## Reading the output artifact

The full conversation is saved as JSON:

```
.dev-factory/roundtables/rt-<conversation_id>.json
```

Structure:

```json
{
  "conversation": {
    "conversation_id": "rt-20240514-143012-a1b2c3",
    "participants": [
      {"agent_name": "security", "card": {...}},
      {"agent_name": "arch", "card": {...}}
    ],
    "messages": [
      {"role": "security", "text": "The main risk is ..."},
      {"role": "arch", "text": "From a component standpoint ..."}
    ]
  },
  "synthesis": {
    "role": "synthesizer",
    "parts": [{"kind": "text", "text": "Synthesis: ..."}]
  }
}
```

---

## Integration with sprint mode

Run a roundtable before `sprint-start` to lock in architectural decisions:

```bash
# 1. Gather expert input
autodev roundtable \
  --topic "Database choice for the kanban board: SQLite vs PostgreSQL vs DynamoDB" \
  --skills arch,perf,sre \
  --repo-path /tmp/kanban

# 2. Review synthesis, make decision, start sprint
autodev sprint-start \
  --repo-path /tmp/kanban \
  --goal "Implement kanban board with chosen database" \
  --duration-days 14
```

---

## See also

- [Tutorial 04 — Sprint mode](04-sprint-mode.md)
- [Tutorial 06 — MCP server](06-mcp-server.md)
- [Tutorial 07 — A2A server](07-a2a-server.md)
