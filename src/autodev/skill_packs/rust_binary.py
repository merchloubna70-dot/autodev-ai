"""Skill pack: Rust CLI binary with clap, anyhow, cargo test."""
from __future__ import annotations

from .base import SkillPack


class RustBinaryPack(SkillPack):
    """Curated template for a Rust CLI binary project."""

    @property
    def name(self) -> str:
        return "rust-binary"

    @property
    def description(self) -> str:
        return "Rust CLI binary with clap, anyhow, cargo test"

    @property
    def brief_template(self) -> str:
        return """\
# Project Brief: {{project_name}}

## Summary
{{project_name}} is a Rust CLI binary that {{summary}}.

## Goals
- Provide a fast, reliable command-line interface
- Ship a single statically-linked binary
- Achieve full `cargo test` coverage on core logic

## Key Features
- {{feature_1}}
- {{feature_2}}

## Stack
- Language: Rust (stable)
- CLI parsing: clap (derive API)
- Error handling: anyhow
- Testing: cargo test + cargo nextest (optional)
- Packaging: cargo dist / GitHub Releases
"""

    @property
    def prd_template(self) -> str:
        return """\
# PRD: {{project_name}}

## 1. Overview
<!-- One paragraph describing the product and its target users. -->

## 2. Problem Statement
<!-- The specific pain point this binary addresses. -->

## 3. Functional Requirements
### 3.1 Commands
<!-- List each subcommand and its behaviour. -->

### 3.2 Flags & Options
<!-- Global flags and per-command options. -->

## 4. Non-Functional Requirements
- Binary size target (e.g. < 5 MB stripped)
- Startup latency target (e.g. < 50 ms cold)
- MSRV (Minimum Supported Rust Version)

## 5. Architecture
- crate layout: `src/main.rs`, `src/cli.rs`, `src/lib.rs`
- Error propagation: `anyhow::Result` throughout
- Configuration: env vars + optional TOML config file

## 6. Milestones
<!-- See milestones_template in RustBinaryPack. -->

## 7. Acceptance Criteria
- `cargo clippy -- -D warnings` clean
- `cargo test` passes
- `--help` renders correct usage
- Binary runs on Linux x86_64 and macOS arm64
"""

    @property
    def milestones_template(self) -> list[str]:
        return [
            "scaffold",
            "cli-parsing",
            "core-impl",
            "tests",
            "ci",
            "release",
        ]

    @property
    def recommended_executor(self) -> str:
        return "auto"

    @property
    def recommended_extras(self) -> list[str]:
        return []
