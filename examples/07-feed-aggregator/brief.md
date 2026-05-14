# Project Brief: feed-aggregator — Async Rust RSS/Atom Service

A Rust async service built on Tokio that fetches multiple RSS/Atom feeds on a
schedule, de-duplicates entries, stores them in SQLite, and serves a unified
JSON feed over HTTP.

## Goals
- Demonstrate idiomatic async Rust with Tokio, reqwest, and sqlx.
- Aggregate N feeds concurrently without blocking threads.
- Expose a simple HTTP API for querying stored entries.

## Users
- Developers who want a self-hosted read-it-later backend.
- Teams evaluating Rust async patterns for I/O-heavy microservices.

## Use Cases
- Configure feeds in `config.toml`; the service fetches them every 15 minutes.
- `GET /entries?limit=20` returns the 20 most recent de-duplicated entries as JSON.
- `GET /entries?source=https://example.com/feed.xml` filters by source feed URL.
- `POST /feeds` adds a new feed URL at runtime.

## MVP Scope
- Tokio runtime with `tokio::spawn` fan-out for concurrent feed fetching.
- `reqwest` for HTTP, `quick-xml` or `feed-rs` for parsing RSS/Atom.
- `sqlx` + SQLite for persistent entry storage (title, url, published, source).
- Axum HTTP server exposing `/entries` and `/feeds` endpoints.
- Integration tests using `wiremock` to serve fixture feeds locally.
- `config.toml` with a `[[feeds]]` array.

## Non-Goals
- Full-text search of entry bodies.
- User accounts or per-user feed lists.
- Push notifications or webhooks.

Delivery boundary: Single Cargo workspace, SQLite file-based persistence,
all tests runnable offline via wiremock fixture server.
