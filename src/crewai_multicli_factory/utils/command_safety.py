"""Command safety / allowlist enforcement.

Used by ShellExecutor, Codex/Claude executors, and SecurityReviewer.
Fail-closed: anything not on the allowlist is rejected.
"""
from __future__ import annotations

import shlex
from dataclasses import dataclass

DEFAULT_ALLOWLIST: tuple[str, ...] = (
    "pytest",
    "uv run pytest",
    "ruff check .",
    "uv run ruff check .",
    "mypy .",
    "uv run mypy .",
    "cargo test",
    "cargo clippy --workspace --all-targets -- -D warnings",
    "cargo fmt --check",
    "npm test",
    "npm run lint",
    "npm run typecheck",
    "npm run build",
    "pnpm test",
    "pnpm lint",
    "pnpm typecheck",
    "pnpm build",
    "yarn test",
    "yarn lint",
    "yarn typecheck",
    "yarn build",
    "git status",
    "git diff",
    "git add",
    "git commit",
    "git tag",
)

DEFAULT_DENYLIST: tuple[str, ...] = (
    "rm -rf",
    "sudo",
    "chmod 777",
    "curl | bash",
    "wget | bash",
    "eval",
    "exec ",
    "source .env",
    "cat .env",
    "printenv",
    " env ",
    "> /etc/",
    "; rm ",
    "&& rm ",
    "| rm ",
    "mkfs",
)


@dataclass
class SafetyVerdict:
    allowed: bool
    matched_rule: str | None
    reason: str


def is_command_allowed(command: str, allowlist: tuple[str, ...] = DEFAULT_ALLOWLIST) -> SafetyVerdict:
    cmd = command.strip()
    if not cmd:
        return SafetyVerdict(False, None, "empty command")
    # deny first
    deny = is_command_denied(cmd)
    if not deny.allowed:
        return deny
    for rule in allowlist:
        if cmd == rule or cmd.startswith(rule + " ") or cmd.startswith(rule):
            return SafetyVerdict(True, rule, "matched allowlist")
    # also allow exact prefix splits (e.g., `cargo test --no-fail-fast`)
    head = shlex.split(cmd, posix=True)[0:2]
    head_str = " ".join(head)
    for rule in allowlist:
        rhead = " ".join(rule.split()[0:2])
        if head_str == rhead:
            return SafetyVerdict(True, rule, f"matched allowlist prefix '{rhead}'")
    return SafetyVerdict(False, None, "command not on allowlist (fail-closed)")


def is_command_denied(command: str, denylist: tuple[str, ...] = DEFAULT_DENYLIST) -> SafetyVerdict:
    cmd = command
    for rule in denylist:
        if rule in cmd:
            return SafetyVerdict(False, rule, f"matched denylist pattern: {rule!r}")
    return SafetyVerdict(True, None, "no denylist match")


def scan_prompt_for_unsafe(prompt: str) -> list[str]:
    """Detect unsafe shell patterns embedded in a generation prompt."""
    flags: list[str] = []
    for rule in DEFAULT_DENYLIST:
        if rule in prompt:
            flags.append(f"prompt contains forbidden pattern: {rule!r}")
    return flags
