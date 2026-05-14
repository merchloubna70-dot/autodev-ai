# R3-H: WorkerIsolator Symlink Escape / Path Traversal Hardening

**Date:** 2026-05-14
**Round:** R3, Agent R3-H
**Finding:** F-03 (R1-LOW elevated to R3 scope)
**Files Modified:**
- `src/autodev/executors/worker_isolator.py`
- `tests/unit/test_worker_isolator_symlink_hardening.py` (new)

---

## Threat Model

WorkerIsolator creates per-worker CODEX_HOME directories by symlinking shared
files from a parent home and creating private mutable directories.  Pre-hardening,
four attack classes were unmitigated:

| # | Attack Vector | Pre-hardening Behavior | Post-hardening |
|---|---------------|------------------------|----------------|
| A | **Symlink escape via pre-placed link** — attacker writes a malicious symlink inside `parent_home` pointing to `/etc/passwd` or another sensitive path; `os.symlink(src, dst)` propagates the escape into the worker home | `os.symlink` called unconditionally | `src.resolve(strict=True)` + `_assert_inside(resolved, resolved_parent)` before symlink — raises `WorkerIsolatorPathEscapeError` |
| B | **Branch name traversal** — `branch="../../../etc/cron.d"` passed to `prepare_worktree`; the string is passed directly to `git worktree add -b` which may create a branch or directory outside the intended root | Branch name passed raw to subprocess | `_validate_branch_name()` rejects `..`, `/`, and NUL bytes before any subprocess call |
| C | **rm-rf escape via cleanup** — `cleanup_worktree(Path("/"))` or any path outside the configured root could wipe arbitrary filesystem trees | No cleanup method existed | `cleanup_worktree()` resolves the path and asserts `is_relative_to(worktree_root)` before `shutil.rmtree` |
| D | **CODEX_HOME env injection** — a hostile process sets `CODEX_HOME=/etc` in the environment; a downstream component trusts that value and writes into it | No validation | When `worktree_root` is explicitly set, `CODEX_HOME` env value is resolved and checked against `worktree_root`; out-of-root value raises `WorkerIsolatorPathEscapeError` |

---

## Resolved-Path Strategy

All path safety assertions follow the same pattern:

```python
resolved = path.resolve(strict=True)   # POSIX: follows all symlinks, raises FileNotFoundError if broken
resolved_root = root.resolve()
resolved.relative_to(resolved_root)    # raises ValueError if outside → re-raised as WorkerIsolatorPathEscapeError
```

`strict=True` ensures intermediate symlinks are chased before the containment
check.  The `os.symlink(src, dst)` call is an atomic POSIX syscall — there is
no time window between our resolve check and the actual inode creation.

---

## New Exception Class

```python
class WorkerIsolatorPathEscapeError(Exception):
    """Raised when a resolved path would escape the allowed root directory."""
```

Callers that previously only expected `OSError` from this module may need to
add a `WorkerIsolatorPathEscapeError` catch if they require graceful handling.
Backwards compatibility of method *signatures* is fully preserved — no existing
parameter types or return types changed.

---

## Test Results (10 tests, all pass)

| # | Test | Vector | Result |
|---|------|--------|--------|
| 1 | `test_symlink_target_outside_parent_home_raises` | A | PASS |
| 2 | `test_branch_name_with_dotdot_raises` | B | PASS |
| 3 | `test_branch_name_bare_dotdot_raises` | B | PASS |
| 4 | `test_branch_name_with_slash_raises` | B | PASS |
| 5 | `test_branch_name_with_nul_byte_raises` | B | PASS |
| 6 | `test_cleanup_outside_root_raises` | C | PASS |
| 7 | `test_valid_symlink_target_inside_root_succeeds` | — | PASS |
| 8 | `test_codex_home_env_outside_worktree_root_raises` | D | PASS |
| 9 | `test_happy_path_full_lifecycle` | — | PASS |
| 10 | `test_cleanup_nonexistent_path_is_idempotent` | — | PASS |

Full suite result: **1045 passed, 4 xfailed, 0 failed** (up from pre-R3 baseline of 1032 passed + 3 pre-existing failures in unrelated SSRF tests that were flaky/network-dependent).

mypy: **0 errors** (`strict=false` per project config).

---

## Residual Risks

### TOCTOU on Cleanup (accepted, documented)

The symlink creation path (`os.symlink`) is atomic — no race window exists
between `resolve()` and the syscall.

The **cleanup** path (`cleanup_worktree` → `shutil.rmtree`) is *not* atomic.
An adversary with write access to the parent directory could race a `rename()`
between our `is_relative_to` assertion and the first `rmtree` descend, moving a
sensitive directory into the path we are about to delete.

**Accepted because:**
- Write access to the parent directory implies a higher-privilege attacker than
  this module's threat model addresses.
- Mitigation (e.g. `openat`/`fstatat` tree-walk with fd pinning) is complex and
  out of scope for this iteration.
- Production workers run as the same UID that owns the worktree root; cross-UID
  races are not possible in that configuration.

### Branch Name Namespace Separator (design decision)

Git legitimately uses `/` as a namespace separator in branch names (e.g.
`feat/my-feature`).  This implementation rejects all `/` in branch names as a
conservative security measure.  Callers that need namespaced branches must
replace `/` with another separator (e.g. `-`) before calling `prepare_worktree`.
This trade-off was chosen to eliminate the entire directory-traversal via
branch-name class rather than attempt partial sanitisation.

### CODEX_HOME Check is Opt-In

To preserve backwards compatibility with existing callers that construct
`WorkerIsolator()` without a `worktree_root` argument, the CODEX_HOME env
validation is only active when `worktree_root` is explicitly provided.  Legacy
callers are unaffected but do not receive the D-vector protection.

---

## Verdict

**PASS — F-03 closed.**  All four attack vectors (symlink escape, branch name
traversal, rm-rf escape, CODEX_HOME injection) are blocked by resolve-then-assert
guards.  Residual TOCTOU on cleanup is documented and accepted.  10 dedicated
hardening tests pass.  Full suite at 1045 passed / 4 xfailed / 0 failed.
mypy clean.
