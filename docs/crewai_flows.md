# CrewAI Flows

The factory exposes its work as proper CrewAI constructs:

- Each agent module in `agents/` builds a real `crewai.Agent` via
  `_crewai_bridge.make_agent(...)` when CrewAI is installed, and a structural
  stub otherwise so tests / CI can still run.
- Each module in `tasks/` builds a `crewai.Task` (or stub) bound to its
  matching agent.
- Flows in `flows/` assemble a `crewai.Crew` (`make_crew(...)`) and record
  the assembled agent list into
  `execution/crew_assembly.json` for audit.

Imperative orchestration logic (so the factory works without a live LLM) is
implemented in the agents' own `run` / `review` / `parse` methods. The
CrewAI handles are still constructed so dependents can switch them on:
`Crew(...).kickoff()` for autonomous runs.

## Why both

CrewAI provides the role / goal / backstory framing and a high-level
Crew/Task graph. Our pipeline needs deterministic, replayable artifacts
and audit logs, so the agents' methods do the structural work while the
CrewAI objects make the system *visible* and extensible.
