# Add JSON output to the CLI

The CLI currently prints human-readable text. Add an optional `--json`
flag that emits results as JSON for downstream tooling.

## Acceptance Criteria

- `crewai-factory scan --json` emits valid JSON.
- Unit tests cover both text and JSON modes.

Impacted areas: cli, scan command, tests

Labels: enhancement, cli
