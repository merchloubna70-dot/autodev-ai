"""Assert that both prompt boundary constants include the CONVENTIONS block."""
from __future__ import annotations

from crewai_multicli_factory.executors.codex_cli_executor import CODEX_PROMPT_BOUNDARY
from crewai_multicli_factory.executors.claude_code_executor import CLAUDE_PROMPT_BOUNDARY


def test_codex_boundary_mentions_agents_md():
    assert "AGENTS.md" in CODEX_PROMPT_BOUNDARY


def test_codex_boundary_mentions_cursor_rules():
    assert ".cursor/rules" in CODEX_PROMPT_BOUNDARY or "CONVENTIONS" in CODEX_PROMPT_BOUNDARY


def test_claude_boundary_mentions_agents_md():
    assert "AGENTS.md" in CLAUDE_PROMPT_BOUNDARY


def test_claude_boundary_mentions_cursor_rules():
    assert ".cursor/rules" in CLAUDE_PROMPT_BOUNDARY or "CONVENTIONS" in CLAUDE_PROMPT_BOUNDARY
