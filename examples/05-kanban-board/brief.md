# Project Brief: kanban-board — TUI + Web Kanban Monorepo

A monorepo combining a Python terminal UI and a TypeScript web frontend for a
simple personal Kanban board, sharing a JSON-file persistence layer.

## Goals
- Demonstrate a polyglot monorepo with coordinated Python and TypeScript workspaces.
- Provide two usable clients (TUI and web) that read/write the same data file.
- Keep the shared schema as a single JSON schema document consumed by both sides.

## Users
- Solo developers who want a lightweight task board without cloud dependencies.
- Teams evaluating monorepo tooling for mixed Python/TypeScript projects.

## Use Cases
- Run `python tui/main.py` to manage cards in the terminal.
- Run `npm run dev` in `web/` to open the board in a browser.
- Both clients read/write `data/board.json` using the shared schema.

## MVP Scope
- Monorepo root with `pyproject.toml`, `package.json`, and `schema/board.schema.json`.
- `tui/`: Python Textual app with three columns (Todo, In Progress, Done),
  add/move/delete card actions, keyboard navigation.
- `web/`: Vite + React SPA with drag-and-drop column layout (no backend server).
- Shared JSON persistence: `data/board.json` written atomically.
- `pytest` for TUI logic; `vitest` for React components.

## Non-Goals
- Multi-user collaboration or real-time sync.
- Cloud storage or database backend.
- Mobile-responsive design beyond basic CSS.

Delivery boundary: Single repository, file-based persistence, all tests runnable
offline without external services.
