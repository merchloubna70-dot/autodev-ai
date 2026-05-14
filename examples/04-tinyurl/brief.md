# Project Brief: tinyurl — Python URL Shortener Service

A lightweight HTTP service that accepts long URLs and returns short codes backed
by a local SQLite database. Demonstrates multi-module Python layout and basic
HTTP API design.

## Goals
- Provide a runnable HTTP server for shortening and resolving URLs.
- Persist mappings in SQLite so data survives restarts.
- Expose a minimal JSON API and a health endpoint.

## Users
- Developers who need a local or self-hosted URL shortener for internal tooling.
- QA engineers testing redirect behaviour in staging environments.

## Use Cases
- `POST /shorten {"url": "https://example.com/very/long/path"}` returns `{"short": "aB3x"}`.
- `GET /r/aB3x` redirects (HTTP 302) to the original URL.
- `GET /health` returns `{"status": "ok"}` for liveness probes.

## MVP Scope
- Multi-module layout: `app/`, `app/db.py`, `app/routes.py`, `app/shortener.py`, `main.py`.
- SQLite persistence via Python `sqlite3` stdlib module.
- Base62 short code generation (6 characters).
- `pytest` test suite covering shorten, resolve, collision handling, and health.
- `requirements.txt` with `flask` (or `fastapi` + `uvicorn`) as the only runtime dep.

## Non-Goals
- User authentication or rate limiting.
- Custom vanity slugs.
- Deployment manifests (Docker, Kubernetes).

Delivery boundary: Single repository, SQLite file-based persistence, no external
infrastructure required to run tests.
