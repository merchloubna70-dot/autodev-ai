"""Command safety / allowlist enforcement.

Used by ShellExecutor, Codex/Claude executors, and SecurityReviewer.
Fail-closed: anything not on the allowlist is rejected.
"""
from __future__ import annotations

import re
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
    "git push",
    "git push origin",
    "gh pr create",
    "gh pr view",
    "gh auth status",
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
    # Force-push / force flags are always denied
    "--force",
    "git push --force",
    "gh --force",
)

# Regex patterns applied *in addition to* (not instead of) DEFAULT_DENYLIST.
# Use these for patterns where a URL or other argument may appear between the
# command verb and the pipe target, making literal substring matching unreliable.
# Each entry is a compiled regex; a match (re.search) on the *raw* command
# string (before pipe-whitespace normalisation) signals a denial.
DEFAULT_DENYLIST_REGEX: tuple[re.Pattern[str], ...] = (
    # curl <any-args> | bash|sh|dash|zsh|python — real-world pipe-to-shell attack
    re.compile(r"curl\b.*\|\s*(bash|sh|dash|zsh|python\d*)\b"),
    # wget <any-args> | bash|sh|dash|zsh|python
    re.compile(r"wget\b.*\|\s*(bash|sh|dash|zsh|python\d*)\b"),
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


def _normalize_pipe_whitespace(text: str) -> str:
    """Collapse optional whitespace around pipe operators to a single space.

    Converts ``curl|bash``, ``curl|bash``, ``curl  |  bash`` all to
    ``curl | bash`` so denylist rules written with spaces match all variants.
    """
    return re.sub(r"\s*\|\s*", " | ", text)


def is_command_denied(
    command: str,
    denylist: tuple[str, ...] = DEFAULT_DENYLIST,
    denylist_regex: tuple[re.Pattern[str], ...] = DEFAULT_DENYLIST_REGEX,
) -> SafetyVerdict:
    # Check literal denylist against pipe-normalised command
    cmd = _normalize_pipe_whitespace(command)
    for rule in denylist:
        if rule in cmd:
            return SafetyVerdict(False, rule, f"matched denylist pattern: {rule!r}")
    # Check regex patterns against the raw command (pre-normalisation) so that
    # URL arguments between the verb and the pipe are correctly matched.
    for pattern in denylist_regex:
        if pattern.search(command):
            return SafetyVerdict(
                False,
                pattern.pattern,
                f"matched denylist regex: {pattern.pattern!r}",
            )
    return SafetyVerdict(True, None, "no denylist match")


def scan_prompt_for_unsafe(prompt: str) -> list[str]:
    """Detect unsafe shell patterns embedded in a generation prompt."""
    normalized = _normalize_pipe_whitespace(prompt)
    flags: list[str] = []
    for rule in DEFAULT_DENYLIST:
        if rule in normalized:
            flags.append(f"prompt contains forbidden pattern: {rule!r}")
    # Also check regex patterns against the raw prompt
    for pattern in DEFAULT_DENYLIST_REGEX:
        if pattern.search(prompt):
            flags.append(f"prompt contains forbidden pattern: {pattern.pattern!r}")
    return flags
