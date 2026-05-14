"""Unit tests for autodev.utils.secret_redaction.

Covers each pattern, idempotency, and normal-text passthrough.
"""
from __future__ import annotations

from autodev.utils.secret_redaction import redact_secrets

_REDACTED = "***REDACTED***"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _has_no_secret(text: str, secret: str) -> bool:
    """Return True if *secret* does not appear in *text*."""
    return secret not in text


def _is_redacted(text: str) -> bool:
    return _REDACTED in text


# ===========================================================================
# 1. OPENAI_API_KEY env-var pattern
# ===========================================================================

class TestOpenAIApiKeyPattern:
    def test_env_var_form_is_masked(self):
        raw = "export OPENAI_API_KEY=sk-proj-abcdefghijklmnopqrstuvwxyz12345"
        result = redact_secrets(raw)
        assert _has_no_secret(result, "sk-proj-abcdefghijklmnopqrstuvwxyz12345")
        assert f"OPENAI_API_KEY={_REDACTED}" in result

    def test_env_var_uppercase_variant(self):
        raw = "OPENAI_API_KEY=sk-live-XYZ123456789ABCDEFGHIJKLMNO"
        result = redact_secrets(raw)
        assert "OPENAI_API_KEY=" in result
        assert "sk-live-XYZ123456789ABCDEFGHIJKLMNO" not in result


# ===========================================================================
# 2. ANTHROPIC_API_KEY env-var pattern
# ===========================================================================

class TestAnthropicApiKeyPattern:
    def test_env_var_form_is_masked(self):
        raw = "ANTHROPIC_API_KEY=sk-ant-fake-anthropic-key-xyz789"
        result = redact_secrets(raw)
        assert _has_no_secret(result, "sk-ant-fake-anthropic-key-xyz789")
        assert f"ANTHROPIC_API_KEY={_REDACTED}" in result

    def test_env_var_in_stderr_multiline(self):
        raw = "Error occurred\nANTHROPIC_API_KEY=sk-ant-api03-secretvalue\nstack trace"
        result = redact_secrets(raw)
        assert "sk-ant-api03-secretvalue" not in result
        assert "Error occurred" in result
        assert "stack trace" in result


# ===========================================================================
# 3. PYPI_API_TOKEN env-var pattern
# ===========================================================================

class TestPypiApiTokenPattern:
    def test_env_var_form_is_masked(self):
        raw = "PYPI_API_TOKEN=pypi-AgEIcHlwaS5vcmcfaketoken123456789"
        result = redact_secrets(raw)
        assert "pypi-AgEIcHlwaS5vcmcfaketoken123456789" not in result
        assert f"PYPI_API_TOKEN={_REDACTED}" in result


# ===========================================================================
# 4. GITHUB_TOKEN env-var pattern
# ===========================================================================

class TestGithubTokenEnvVarPattern:
    def test_env_var_form_is_masked(self):
        raw = "GITHUB_TOKEN=ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890"
        result = redact_secrets(raw)
        assert "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890" not in result
        assert f"GITHUB_TOKEN={_REDACTED}" in result


# ===========================================================================
# 5. sk- token prefix pattern (OpenAI/Anthropic style)
# ===========================================================================

class TestSkTokenPattern:
    def test_bare_sk_token_is_masked(self):
        raw = "Using key sk-abcdefghij1234567890KLMNOPQRSTU"
        result = redact_secrets(raw)
        assert "sk-abcdefghij1234567890KLMNOPQRSTU" not in result
        # First 4 chars are preserved
        assert "sk-a" in result
        assert _REDACTED in result

    def test_sk_ant_token_is_masked(self):
        raw = "token=sk-ant-api03-fakekeyfakekeyfakekeyfakekey"
        result = redact_secrets(raw)
        assert "sk-ant-api03-fakekeyfakekeyfakekeyfakekey" not in result
        assert "sk-a" in result


# ===========================================================================
# 6. GitHub PAT (ghp_)
# ===========================================================================

class TestGithubPatPattern:
    def test_ghp_token_is_masked(self):
        raw = "auth: ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890abcd"
        result = redact_secrets(raw)
        assert "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890abcd" not in result
        assert "ghp_" in result  # first 4 chars kept
        assert _REDACTED in result


# ===========================================================================
# 7. GitHub OAuth token (gho_)
# ===========================================================================

class TestGithubOAuthPattern:
    def test_gho_token_is_masked(self):
        raw = "oauth: gho_ABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890abcd"
        result = redact_secrets(raw)
        assert "gho_ABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890abcd" not in result
        assert "gho_" in result
        assert _REDACTED in result


# ===========================================================================
# 8. PyPI token (pypi-)
# ===========================================================================

class TestPypiTokenPattern:
    def test_pypi_token_is_masked(self):
        raw = "Uploading with token pypi-AgEIcHlwaS5vcmcABCDEFGHIJ1234567890"
        result = redact_secrets(raw)
        assert "pypi-AgEIcHlwaS5vcmcABCDEFGHIJ1234567890" not in result
        assert "pypi" in result
        assert _REDACTED in result


# ===========================================================================
# 9. Slack bot token (xoxb-)
# ===========================================================================

class TestSlackTokenPattern:
    def test_xoxb_token_is_masked(self):
        raw = "slack token xoxb-EXAMPLE-EXAMPLE-EXAMPLEFAKEPLACEHOLDER"
        result = redact_secrets(raw)
        assert "xoxb-EXAMPLE-EXAMPLE-EXAMPLEFAKEPLACEHOLDER" not in result
        assert "xoxb" in result
        assert _REDACTED in result


# ===========================================================================
# 10. PEM private key block
# ===========================================================================

class TestPemPrivateKeyPattern:
    def test_rsa_private_key_block_is_masked(self):
        raw = (
            "-----BEGIN RSA PRIVATE KEY-----\n"
            "MIIEowIBAAKCAQEA2a3b4c5d6e7f8g9h0i\n"
            "AAABBBCCCDDDEEEFFFGGGHHHIIIJJJ\n"
            "-----END RSA PRIVATE KEY-----"
        )
        result = redact_secrets(raw)
        assert "MIIEowIBAAKCAQEA2a3b4c5d6e7f8g9h0i" not in result
        assert _REDACTED in result

    def test_ec_private_key_block_is_masked(self):
        raw = (
            "key:\n"
            "-----BEGIN EC PRIVATE KEY-----\n"
            "fakekeydatahere1234567890\n"
            "-----END EC PRIVATE KEY-----\n"
            "done"
        )
        result = redact_secrets(raw)
        assert "fakekeydatahere1234567890" not in result
        assert "done" in result
        assert _REDACTED in result


# ===========================================================================
# 11. Idempotency
# ===========================================================================

class TestIdempotency:
    def test_redact_twice_equals_redact_once(self):
        raw = (
            "ANTHROPIC_API_KEY=sk-ant-fake-key-xyz789\n"
            "sk-another-token-abcdefghijklmnopqrst\n"
            "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890abcd"
        )
        once = redact_secrets(raw)
        twice = redact_secrets(once)
        assert once == twice, "redact_secrets is not idempotent"

    def test_already_redacted_text_unchanged(self):
        already = f"OPENAI_API_KEY={_REDACTED}"
        result = redact_secrets(already)
        assert result == already


# ===========================================================================
# 12. Normal text is not broken
# ===========================================================================

class TestNormalTextPassthrough:
    def test_plain_sentence_unchanged(self):
        text = "Task completed successfully. No errors found."
        assert redact_secrets(text) == text

    def test_empty_string_unchanged(self):
        assert redact_secrets("") == ""

    def test_short_sk_prefix_below_threshold_unchanged(self):
        # "sk-abc" is only 6 chars total (prefix 3 + 3 chars) — below 20-char minimum
        text = "sk-abc is not a token"
        assert redact_secrets(text) == text

    def test_json_without_secrets_unchanged(self):
        import json
        data = json.dumps({"task_id": "T-001", "status": "done", "exit_code": 0})
        assert redact_secrets(data) == data
