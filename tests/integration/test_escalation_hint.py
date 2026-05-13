"""Integration tests — assert ESCALATION_HINT is present in both executor boundaries."""
from __future__ import annotations


from crewai_multicli_factory.executors.claude_code_executor import CLAUDE_PROMPT_BOUNDARY
from crewai_multicli_factory.executors.codex_cli_executor import CODEX_PROMPT_BOUNDARY


class TestEscalationHintPresent:
    def test_codex_boundary_has_escalation_hint(self):
        assert "ESCALATION_HINT" in CODEX_PROMPT_BOUNDARY

    def test_claude_boundary_has_escalation_hint(self):
        assert "ESCALATION_HINT" in CLAUDE_PROMPT_BOUNDARY

    def test_codex_boundary_mentions_ask_opus(self):
        assert "ask_opus" in CODEX_PROMPT_BOUNDARY

    def test_claude_boundary_mentions_ask_opus(self):
        assert "ask_opus" in CLAUDE_PROMPT_BOUNDARY

    def test_codex_boundary_mentions_architect(self):
        assert "architect" in CODEX_PROMPT_BOUNDARY

    def test_claude_boundary_mentions_architect(self):
        assert "architect" in CLAUDE_PROMPT_BOUNDARY

    def test_codex_boundary_mentions_reviewer(self):
        assert "reviewer" in CODEX_PROMPT_BOUNDARY

    def test_claude_boundary_mentions_reviewer(self):
        assert "reviewer" in CLAUDE_PROMPT_BOUNDARY

    def test_codex_boundary_mentions_security(self):
        assert "security" in CODEX_PROMPT_BOUNDARY.lower()

    def test_claude_boundary_mentions_security(self):
        assert "security" in CLAUDE_PROMPT_BOUNDARY.lower()

    def test_codex_escalation_block_within_12_lines(self):
        # Count the lines of the ESCALATION_HINT block (from its header to the last call line).
        lines = CODEX_PROMPT_BOUNDARY.splitlines()
        hint_lines = [l for l in lines if l.strip()]  # non-blank lines from hint block
        # Find the ESCALATION_HINT block boundaries
        start = next((i for i, l in enumerate(lines) if "ESCALATION_HINT" in l), None)
        assert start is not None, "ESCALATION_HINT not found in CODEX_PROMPT_BOUNDARY"
        # Count non-empty lines from start to end
        block = [l for l in lines[start:] if l.strip()]
        assert len(block) <= 12, f"ESCALATION_HINT block has {len(block)} non-blank lines, max 12"

    def test_claude_escalation_block_within_12_lines(self):
        lines = CLAUDE_PROMPT_BOUNDARY.splitlines()
        start = next((i for i, l in enumerate(lines) if "ESCALATION_HINT" in l), None)
        assert start is not None, "ESCALATION_HINT not found in CLAUDE_PROMPT_BOUNDARY"
        block = [l for l in lines[start:] if l.strip()]
        assert len(block) <= 12, f"ESCALATION_HINT block has {len(block)} non-blank lines, max 12"
