# R4-C: Branch Name Injection Hardening

**Agent:** R4-C  
**Date:** 2026-05-14  
**Scope:** Shell-injection hardening for branch names in `WorkerIsolator`, `GitAdapter`  
**Verdict:** PASS — all checks green

---

## Summary

Extended `WorkerIsolator._validate_branch_name()` from its R3-H baseline (which only rejected NUL bytes, `/`, and `..` traversal sequences) to also reject 11 distinct shell-injection patterns. The blanket `/` rejection was replaced with a precise `..`-component-only traversal check, allowing namespace-prefixed branch names (e.g. `feature/foo`) while still blocking path traversal.

---

## 11 Rejection Patterns

| # | Pattern | Description | Example Input |
|---|---------|-------------|---------------|
| 1 | `$(` | Command substitution (dollar-paren) | `feat$(whoami)` |
| 2 | `` ` `` | Command substitution (backtick) | `` feat`whoami` `` |
| 3 | `;` | Shell statement separator | `feat;rm` |
| 4 | `&&` | Shell logical AND | `feat&&malicious` |
| 5 | `\|\|` | Shell logical OR | `feat\|\|malicious` |
| 6 | `\|` | Pipe | `feat\|malicious` |
| 7 | `>` | Output redirection (also `>>`) | `feat>output` |
| 8 | `<` | Input redirection (also `<<`) | `feat<input` |
| 9 | `\n` / `\r` / ctrl chars | Newline, CR, or ASCII control chars (< 0x20) | `feat\nrm` |
| 10 | Leading `-` | Git flag injection | `-feat-leading-dash` |
| 11 | Leading/trailing whitespace | Accidental misuse / bypass attempts | ` feat-space`, `feat-space ` |

NUL byte and `..` traversal (pre-existing from R3-H) are also still rejected.

---

## shell=True Audit

**Result: 0 git-path `shell=True` calls found.**

All git subprocess calls in the codebase use argument lists (not shell strings):
- `worker_isolator.py`: `subprocess.run(["git", "worktree", "add", ...], ...)` — no `shell=True`
- `git_adapter.py`: uses `ShellExecutor` which internally calls `shlex.split()` then `subprocess.run(argv, ...)` — no `shell=True`
- `github_adapter.py`: same `ShellExecutor` path

The `shell=True` pattern appears only in `adversarial_reviewer.py` as a detection rule string (not an execution call).

---

## New Exception Class

`BranchNameInjectionError(WorkerIsolatorPathEscapeError)` — raised for all new injection patterns. Subclasses `WorkerIsolatorPathEscapeError` so existing callers that catch the parent class continue to work unchanged.

---

## Validation Coverage

### Unit tests (`tests/unit/test_branch_name_hardening.py`)

**26 tests total (all pass):**

Rejection tests (19):
- `feat$(whoami)` — dollar-paren command substitution
- `` feat`whoami` `` — backtick command substitution
- `feat;rm` — semicolon separator
- `feat&&malicious` — logical AND
- `feat||malicious` — logical OR
- `feat|malicious` — pipe
- `feat>output` — output redirection
- `feat<input` — input redirection
- `feat\nrm` — newline
- `-feat-leading-dash` — leading dash
- ` feat-leading-space` — leading whitespace
- `feat-trailing-space ` — trailing whitespace
- `feat\x00name` — NUL byte
- `feat/../secret` — `..` traversal via slash
- `feat\rmalicious` — carriage return
- `feat>>output` — append redirection
- `feat<<input` — heredoc redirection
- `BranchNameInjectionError` is subclass of `WorkerIsolatorPathEscapeError`
- Raised exception is specifically `BranchNameInjectionError`

Allow tests (7):
- `feature/foo`
- `fix/issue-123`
- `release/v0.1.0a1`
- `chore/docs-update`
- `main`
- `develop`
- `feat/m1-add-cli`

### Integration tests (`tests/integration/test_security_p0_coverage.py`)

2 xfails removed from `TestWorkerIsolatorBranchNameInjection`:
- `test_worker_isolator_branch_name_rejects_dollar_paren` — now passes
- `test_worker_isolator_branch_name_rejects_backtick` — now passes

---

## Propagation Points

| File | Change |
|------|--------|
| `src/autodev/executors/worker_isolator.py` | Added `BranchNameInjectionError`; rewrote `_validate_branch_name()` with 11 new patterns |
| `src/autodev/adapters/git_adapter.py` | Added `_validate_branch()` helper; called in `push()`, `checkout()`, `create_branch()` |

`commit_agent.py` / `release_manager.py`: branch names are generated internally via `slugify()` and never accept untrusted user input directly; no validation hook needed.

---

## Test Suite Results

| Check | Result |
|-------|--------|
| `pytest tests/unit/test_branch_name_hardening.py` | 26 passed |
| `pytest tests/integration/test_security_p0_coverage.py` | 14 passed (0 xfail) |
| `pytest tests/` (full suite) | 1308 passed, 0 failed |
| `mypy src/autodev` | 0 errors |
| `ruff check .` | 0 errors |
| xfails removed | 2 |

---

## Residual Risk

1. **TOCTOU on worktree cleanup** (pre-existing, documented in module docstring): `shutil.rmtree` is not atomic; an adversary with write access to the parent directory could race a rename between the `is_relative_to` check and the actual `rmtree` call.
2. **`git_adapter.py` string interpolation**: `ShellExecutor` uses `shlex.split()` before passing to subprocess, which prevents shell expansion. However, callers that use `GitAdapter.tag()` or `GitAdapter.add()` with untrusted inputs could still pass injection via `shlex` token splitting rather than shell expansion. Branch-specific methods now validate via `_validate_branch()`.
3. **`slugify()` input**: `CommitAgent.build_artifacts()` builds branch names using `slugify()`; if `slugify()` ever becomes bypassable, the resulting names would reach `git_adapter.push()` which now validates them.
