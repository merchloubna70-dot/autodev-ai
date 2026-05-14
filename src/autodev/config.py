"""Global / per-run configuration for the software factory."""
from __future__ import annotations

import os
from dataclasses import dataclass, field

from .schemas import ExecutionBackend, ExecutorSelectionPolicy, PipelineMode


@dataclass
class CodexCliExecutorConfig:
    binary: str = "codex"
    # placeholder {prompt} is required; {repo_path} optional
    command_template: str = 'codex exec --skip-git-repo-check {prompt}'
    timeout_seconds: int = 600
    allow_mock_fallback: bool = True


@dataclass
class ClaudeCodeExecutorConfig:
    binary: str = "claude"
    command_template: str = 'claude --print {prompt}'
    timeout_seconds: int = 900
    allow_mock_fallback: bool = True
    allowed_tools: list[str] = field(default_factory=lambda: ["Read", "Edit", "Write", "Bash"])
    disallowed_patterns: list[str] = field(default_factory=lambda: [
        "rm -rf",
        "sudo",
        "chmod 777",
        "cat .env",
        "source .env",
        "printenv",
        "curl | bash",
        "wget | bash",
    ])


@dataclass
class MockFixtureConfig:
    """Configuration for fixture-based mock executor patches."""
    enabled: bool = False
    patches_dir: str | None = None
    default_template: str = ""


@dataclass
class FactoryConfig:
    """Top-level factory configuration."""

    state_dir: str = ".dev-factory"
    default_mode: PipelineMode = PipelineMode.DRY_RUN
    default_backend: ExecutionBackend = ExecutionBackend.AUTO
    allow_mock_executor: bool = True
    fail_fast: bool = True
    continue_and_report: bool = False
    concurrency: int = 3
    commit: bool = False
    push: bool = False
    tag: bool = False
    release: bool = False
    codex: CodexCliExecutorConfig = field(default_factory=CodexCliExecutorConfig)
    claude_code: ClaudeCodeExecutorConfig = field(default_factory=ClaudeCodeExecutorConfig)
    executor_policy: ExecutorSelectionPolicy = field(default_factory=ExecutorSelectionPolicy)

    mock_codex_fixture: MockFixtureConfig = field(default_factory=lambda: MockFixtureConfig())
    mock_claude_fixture: MockFixtureConfig = field(default_factory=lambda: MockFixtureConfig())

    @classmethod
    def from_env(cls) -> FactoryConfig:
        cfg = cls()
        if os.environ.get("FACTORY_CODEX_BIN"):
            cfg.codex.binary = os.environ["FACTORY_CODEX_BIN"]
        if os.environ.get("FACTORY_CODEX_CMD"):
            cfg.codex.command_template = os.environ["FACTORY_CODEX_CMD"]
        if os.environ.get("FACTORY_CLAUDE_BIN"):
            cfg.claude_code.binary = os.environ["FACTORY_CLAUDE_BIN"]
        if os.environ.get("FACTORY_CLAUDE_CMD"):
            cfg.claude_code.command_template = os.environ["FACTORY_CLAUDE_CMD"]
        # FACTORY_FORCE_MOCK=1 must enable mock fallback regardless of mode.
        # This allows CI / test environments to route to mocks even when the
        # pipeline mode is "apply" (which would otherwise harden allow_mock_executor
        # to False).  Only the allow_mock_executor flag is affected; all other
        # apply-mode hardening remains intact.
        if os.environ.get("FACTORY_FORCE_MOCK") == "1":
            cfg.allow_mock_executor = True
        return cfg

    @classmethod
    def from_stack(cls, repo_path: str | None = None) -> FactoryConfig:
        """Build a FactoryConfig by layering TOML config files then env vars.

        Loads 4 layers in priority order:
          1. ~/.config/autodev/config.toml     (user-global)
          2. {repo}/.autodev/config.toml       (project team-base)
          3. {repo}/.autodev/config.user.toml  (project user override)
          4. Environment variables              (runtime, via from_env)

        Missing files are silently skipped.
        """
        from .utils.config_stack import ConfigStack

        # Start from env-layer base (backward compat)
        cfg = cls.from_env()
        stack = ConfigStack(repo_path=repo_path).load()
        return stack.materialize_into(cfg)
