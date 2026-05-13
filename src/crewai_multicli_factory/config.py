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

    @classmethod
    def from_env(cls) -> "FactoryConfig":
        cfg = cls()
        if os.environ.get("FACTORY_CODEX_BIN"):
            cfg.codex.binary = os.environ["FACTORY_CODEX_BIN"]
        if os.environ.get("FACTORY_CODEX_CMD"):
            cfg.codex.command_template = os.environ["FACTORY_CODEX_CMD"]
        if os.environ.get("FACTORY_CLAUDE_BIN"):
            cfg.claude_code.binary = os.environ["FACTORY_CLAUDE_BIN"]
        if os.environ.get("FACTORY_CLAUDE_CMD"):
            cfg.claude_code.command_template = os.environ["FACTORY_CLAUDE_CMD"]
        return cfg
