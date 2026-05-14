# Project Brief: slug-rs — Base62 Slug Generator

A Rust library crate that converts arbitrary byte sequences or unsigned 64-bit
integers into compact, URL-safe base62 slugs and decodes them back.

## Goals
- Provide a safe, dependency-light Rust library for generating short slugs.
- Support both encode (u64 → slug) and decode (slug → u64) paths.
- Ship a thin CLI binary for manual testing and scripting.

## Users
- Backend Rust developers who need short, human-friendly identifiers for URLs
  or file names.
- CLI users who want a quick slug without writing code.

## Use Cases
- `slug_rs::encode(12345)` returns `"3D7"`.
- `slug_rs::decode("3D7")` returns `Ok(12345)`.
- `cargo run -- encode 12345` prints the slug to stdout.

## MVP Scope
- Library crate with `encode(u64) -> String` and `decode(&str) -> Result<u64, SlugError>`.
- Custom alphabet: `0-9A-Za-z` (standard base62).
- Unit tests covering round-trips, edge cases (0, u64::MAX), and invalid input.
- CLI binary (`src/main.rs`) with `encode` and `decode` subcommands.

## Non-Goals
- UUID → slug conversion.
- Custom alphabets or base other than 62.
- Async or multi-threaded usage patterns.

Delivery boundary: Single Cargo workspace crate, no external dependencies beyond `std`.
