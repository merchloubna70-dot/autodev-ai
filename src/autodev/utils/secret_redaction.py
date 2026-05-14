"""Secret redaction helper — masks credentials before they reach disk or JSON reports.

Usage::

    from autodev.utils.secret_redaction import redact_secrets

    safe_text = redact_secrets(raw_output)

The function is idempotent: ``redact_secrets(redact_secrets(x)) == redact_secrets(x)``.
"""
from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# Named env-var=value patterns
# ---------------------------------------------------------------------------
# Matches  KEY=<value>  where value runs to end-of-line or a whitespace boundary.
_ENV_VAR_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    (name, re.compile(rf"(?i){re.escape(name)}=[^\s]*", re.MULTILINE))
    for name in (
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "PYPI_API_TOKEN",
        "GITHUB_TOKEN",
    )
]

# ---------------------------------------------------------------------------
# Token-prefix patterns  (keep first 4 chars for debuggability)
# ---------------------------------------------------------------------------
_TOKEN_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    # OpenAI / Anthropic style: sk-<anything>  or  sk-ant-<anything>
    ("sk-token", re.compile(r"sk-[A-Za-z0-9\-]{20,}")),
    # GitHub PAT
    ("ghp-token", re.compile(r"ghp_[A-Za-z0-9]{36,}")),
    # GitHub OAuth token
    ("gho-token", re.compile(r"gho_[A-Za-z0-9]{36,}")),
    # PyPI token
    ("pypi-token", re.compile(r"pypi-[A-Za-z0-9\-]{20,}")),
    # Slack bot token
    ("slack-token", re.compile(r"xoxb-[A-Za-z0-9\-]{20,}")),
]

# ---------------------------------------------------------------------------
# PEM private-key block
# ---------------------------------------------------------------------------
_PEM_PATTERN: re.Pattern[str] = re.compile(
    r"-----BEGIN[^-]+PRIVATE KEY-----[\s\S]*?-----END[^-]+PRIVATE KEY-----",
    re.MULTILINE,
)

_REDACTED = "***REDACTED***"
_ALREADY_REDACTED = re.compile(re.escape(_REDACTED))

# Known secret-bearing env var names whose values must always be scrubbed.
_SECRET_ENV_NAMES: frozenset[str] = frozenset({
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "PYPI_API_TOKEN",
    "GITHUB_TOKEN",
    "GITHUB_TOKEN_READ",
    "AWS_SECRET_ACCESS_KEY",
    "AWS_SESSION_TOKEN",
    "DATABASE_URL",
})


def redact_secrets(text: str) -> str:
    """Replace known secret patterns in *text* with ``***REDACTED***``.

    Token-prefix patterns (``sk-``, ``ghp_``, …) keep their first 4 characters
    so the log entry stays debuggable, e.g. ``sk-1***REDACTED***``.

    The function is idempotent.
    """
    if not text:
        return text

    # PEM blocks — replace the entire block
    text = _PEM_PATTERN.sub(_REDACTED, text)

    # Named env-var=value patterns
    for name, pat in _ENV_VAR_PATTERNS:
        text = pat.sub(f"{name}={_REDACTED}", text)

    # Token-prefix patterns — keep first 4 chars
    for _label, pat in _TOKEN_PATTERNS:
        def _replace_token(m: re.Match[str], _pat: re.Pattern[str] = pat) -> str:
            val = m.group(0)
            # If already redacted (short token that somehow matched), skip
            if _REDACTED in val:
                return val
            return val[:4] + _REDACTED

        text = pat.sub(_replace_token, text)

    return text


def redact_env_values(text: str, env: dict[str, str]) -> str:
    """Scrub literal values of secret-bearing environment variables from *text*.

    Applies *after* ``redact_secrets`` to catch arbitrary values that are not
    covered by token-prefix heuristics.  Only env vars whose names appear in
    ``_SECRET_ENV_NAMES`` (case-insensitive) have their values scrubbed.

    Values shorter than 4 characters are skipped to avoid false positives.

    The function is idempotent when combined with ``redact_secrets``.
    """
    if not text or not env:
        return text
    for key, value in env.items():
        if key.upper() not in _SECRET_ENV_NAMES:
            continue
        if not value or len(value) < 4:
            continue
        if _REDACTED in value:
            # Already-redacted placeholder in the env dict — skip
            continue
        text = text.replace(value, _REDACTED)
    return text
