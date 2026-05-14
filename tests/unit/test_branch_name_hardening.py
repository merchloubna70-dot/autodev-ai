"""Unit tests for branch-name shell-injection hardening (R4-C).

Covers all 11 rejection patterns added by R4-C:
  1. $(  — command substitution (dollar-paren)
  2. `   — command substitution (backtick)
  3. ;   — shell statement separator
  4. &&  — shell logical AND
  5. ||  — shell logical OR
  6. |   — pipe
  7. >   — redirection (output)
  8. <   — redirection (input)
  9. \\n  — newline (control char)
  10. -   — leading dash (git flag injection)
  11. whitespace — leading or trailing whitespace

And 4 legitimate branch names that must still be accepted:
  - feature/foo
  - fix/issue-123
  - release/v0.1.0a1
  - chore/docs-update
"""
from __future__ import annotations

import pytest

from autodev.executors.worker_isolator import (
    BranchNameInjectionError,
    WorkerIsolator,
    WorkerIsolatorPathEscapeError,
)

# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _reject(branch: str) -> None:
    """Assert that *branch* raises WorkerIsolatorPathEscapeError (or subclass)."""
    with pytest.raises(WorkerIsolatorPathEscapeError):
        WorkerIsolator._validate_branch_name(branch)


def _allow(branch: str) -> None:
    """Assert that *branch* passes validation (no exception raised)."""
    WorkerIsolator._validate_branch_name(branch)  # must not raise


# ===========================================================================
# Rejection tests — 11 injection patterns
# ===========================================================================


class TestBranchNameRejections:
    """_validate_branch_name must reject each of these inputs."""

    def test_rejects_dollar_paren_command_substitution(self):
        """feat$(whoami) contains $( command substitution."""
        _reject("feat$(whoami)")

    def test_rejects_backtick_command_substitution(self):
        """feat`whoami` contains backtick command substitution."""
        _reject("feat`whoami`")

    def test_rejects_semicolon_statement_separator(self):
        """feat;rm -rf / uses ; to inject a second command."""
        _reject("feat;rm")

    def test_rejects_double_ampersand_logical_and(self):
        """feat&&malicious uses && to chain commands."""
        _reject("feat&&malicious")

    def test_rejects_double_pipe_logical_or(self):
        """feat||malicious uses || to chain commands."""
        _reject("feat||malicious")

    def test_rejects_pipe(self):
        """feat|malicious uses a bare pipe."""
        _reject("feat|malicious")

    def test_rejects_output_redirection(self):
        """feat>output uses > redirection."""
        _reject("feat>output")

    def test_rejects_input_redirection(self):
        """feat<input uses < redirection."""
        _reject("feat<input")

    def test_rejects_newline_in_branch_name(self):
        """A branch name containing a newline must be rejected."""
        _reject("feat\nrm")

    def test_rejects_leading_dash(self):
        """-feat-leading-dash starts with - and would be parsed as a git flag."""
        _reject("-feat-leading-dash")

    def test_rejects_leading_whitespace(self):
        """ feat-leading-space starts with a space."""
        _reject(" feat-leading-space")

    def test_rejects_trailing_whitespace(self):
        """feat-trailing-space  ends with a space."""
        _reject("feat-trailing-space ")

    def test_rejects_nul_byte(self):
        """NUL byte in branch name must be rejected (pre-existing check)."""
        _reject("feat\x00name")

    def test_rejects_dotdot_traversal(self):
        """.. path traversal component must be rejected."""
        _reject("feat/../secret")

    def test_rejects_carriage_return(self):
        """\\r is a control character and must be rejected."""
        _reject("feat\rmalicious")

    def test_rejects_append_redirection(self):
        """>> is covered by the > check."""
        _reject("feat>>output")

    def test_rejects_heredoc_redirection(self):
        """<< is covered by the < check."""
        _reject("feat<<input")

    # BranchNameInjectionError must be a subclass of WorkerIsolatorPathEscapeError
    def test_branch_injection_error_is_subclass(self):
        """BranchNameInjectionError must be a WorkerIsolatorPathEscapeError subclass."""
        assert issubclass(BranchNameInjectionError, WorkerIsolatorPathEscapeError)

    def test_raised_exception_is_branch_injection_error(self):
        """The exception raised for $() is specifically BranchNameInjectionError."""
        with pytest.raises(BranchNameInjectionError):
            WorkerIsolator._validate_branch_name("feat$(whoami)")


# ===========================================================================
# Allow tests — 6 legitimate branch names
# ===========================================================================


class TestBranchNameAllowed:
    """Legitimate branch names must pass _validate_branch_name without exception."""

    def test_allows_feature_slash_foo(self):
        """feature/foo is a standard namespace-prefixed branch name."""
        _allow("feature/foo")

    def test_allows_fix_issue_123(self):
        """fix/issue-123 is a common bugfix branch pattern."""
        _allow("fix/issue-123")

    def test_allows_release_v0_1_0a1(self):
        """release/v0.1.0a1 is a typical release branch name."""
        _allow("release/v0.1.0a1")

    def test_allows_chore_docs_update(self):
        """chore/docs-update is a standard chore branch name."""
        _allow("chore/docs-update")

    def test_allows_main(self):
        """main is the standard default branch name."""
        _allow("main")

    def test_allows_develop(self):
        """develop is a common long-lived branch name."""
        _allow("develop")

    def test_allows_feat_m1_add_cli(self):
        """feat/m1-add-cli is a milestone-scoped feature branch."""
        _allow("feat/m1-add-cli")
