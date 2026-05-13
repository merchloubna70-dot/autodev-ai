# Architecture

`autodev` orchestrates CrewAI agents over a
multi-CLI executor router (Codex CLI + Claude Code CLI + mocks) to deliver
either a single-issue change or a full project from brief/PRD.

## Top-level flow

```mermaid
flowchart TD
  A[Project Brief / Issue / PRD] --> B[Input Classifier Agent]
  B -->|Issue Mode| C[Issue Analyst Agent]
  B -->|Project Delivery Mode| D[Product Manager Agent]
  D --> E[Requirement Analyst Agent]
  E --> F[PRD Writer Agent]
  C --> G[Repo Explorer Agent]
  F --> G
  G --> H[System Architect Agent]
  H --> I[Milestone Planner Agent]
  I --> J[Task Decomposer Agent]
  J --> K[Scaffolder Agent]
  K --> R[Executor Router]
  R -->|small patch / tests / scaffold| X[Codex CLI Executor]
  R -->|architecture / refactor / cross-language| Y[Claude Code CLI Executor]
  R -->|test environment / missing CLI| Z[Mock Executor]
  X --> M[Quality Gate Agent]
  Y --> M
  Z --> M
  M --> N[Security Reviewer Agent]
  N --> O[Code Reviewer Agent]
  O --> P[Integration Reviewer Agent]
  P --> Q[Verifier Agent]
  Q --> S[Doc Writer Agent]
  S --> T[Release Manager Agent]
  T --> U[Commit Agent]
  U --> V[Delivery Report]
```

## Layers

- `schemas.py` — pydantic models that every other layer reads/writes.
- `executors/` — only place where Codex / Claude CLIs are invoked.
- `scanners/` — read-only repo introspection.
- `gates/` — language and release quality gates.
- `agents/` — CrewAI agents, each with a `.crewai_agent()` and a deterministic
  `.run(…)` / `.review(…)` method.
- `tasks/` — CrewAI `Task` wrappers bound to each agent.
- `flows/` — top-level orchestrations (Issue Mode + Project Delivery Mode +
  single-milestone + release-only).
- `planners/` — project / milestone / task / dependency planners.
- `reports/` — markdown reporters for delivery + release + final report.
- `adapters/` — git / github / filesystem adapters.
- `utils/` — fs, json io, slug, logging, concurrency, command_safety, hashing.

## State & replay

A run owns `<repo>/.dev-factory/runs/<run_id>/`. Every transition writes a
JSON or JSONL record; `RunState.load(...)` rehydrates the run from disk so
`replay`, `continue-run`, and `execute-milestone` can resume work.

## Failure policy

- `dry-run` + `mock_used` ⇒ release_check returns `NotReleaseReady`.
- a failed quality gate ⇒ release_check returns `NotReleaseReady`.
- a failed security review ⇒ release_check returns `Blocked`.
- missing CLI when `allow_mock_executor=false` ⇒ executor returns
  `error_type=cli_missing_fail_closed`, run continues but the failure is
  recorded.

## A2A integration

`RoundtableAgent` implements the BMAD party-mode invariant: multiple independent
agent voices are dispatched in parallel over A2A, each receiving the same task
but running with its own `system_prompt` in an isolated subprocess.

```mermaid
flowchart LR
  RT[RoundtableAgent]
  RT --> AR[AgentRoster]
  AR --> C1[AgentCard: architect]
  AR --> C2[AgentCard: security]
  AR --> C3[AgentCard: performance]
  AR --> C4[AgentCard: ux / style]
  RT --> AC[A2AClient]
  AC -->|card.transport == local-shell| LS[LocalShellTransport\nclaude CLI subprocess]
  AC -->|card.transport == mock| MT[MockTransport\nsha256 keyed on card.name]
  AC -->|card.transport == a2a-http\n⚠ future Step 4| HT[A2AHttpTransport\nHTTP POST to card.endpoint]
  LS --> SUB[claude CLI subprocesses\neach with own system_prompt]
```

Key properties:
- `AgentRoster.default()` seeds five specialist cards (architect/opus, security/sonnet, performance/sonnet, ux/sonnet, style/haiku).
- `A2AClient` caches transport instances and falls back to `MockTransport` for unknown transport names.
- `MockTransport` keys its deterministic response on `sha256(prompt + card_name)` — different cards give different mock answers on the same prompt, proving no roleplay convergence.
- `ParallelSectionReviewer` delegates its synthesis step to `RoundtableAgent` while keeping its file-scan sub-reviewers unchanged.
