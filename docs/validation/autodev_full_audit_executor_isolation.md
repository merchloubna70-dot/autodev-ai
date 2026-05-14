# Full Audit: Executor Router + Worker Isolation + Denylist Hardening

**Date:** 2026-05-14
**Agent:** PreTag-F
**Build on:** R1-D + R3-H (no re-work)

---

## Test Results

| Suite | Pass | xfail |
|---|---|---|
| `test_executor_boundary_smoke.py` | 13 | 4 |
| `test_worker_isolator_symlink_hardening.py` | 10 | 0 |
| `test_executor_router.py` | 12 | 0 |
| **Total** | **35** | **4** |

Command: `python -m pytest tests/unit/test_executor_boundary_smoke.py tests/unit/test_worker_isolator_symlink_hardening.py tests/unit/test_executor_router.py -q`
Result: `35 passed, 4 xfailed`

---

## Mock Smoke (FACTORY_FORCE_MOCK=1)

```
FACTORY_FORCE_MOCK=1 python -m autodev.cli classify-input \
  --input examples/01-mdlines/brief.md
```

Exit code: **0**. Output confirms `project_delivery_flow` routing via mock executor path — both real CLIs report `is_available()=False` under `FACTORY_FORCE_MOCK=1`.

---

## Worker Isolator Defenses (src/autodev/executors/worker_isolator.py)

All four R3-H defenses confirmed present:

| Defense | Location | Mechanism |
|---|---|---|
| `WorkerIsolatorPathEscapeError` | line 52 | Dedicated exception; raised by all escape vectors |
| `resolve(strict=True)` + `is_relative_to` | lines 301-302 | Each symlink src resolved strictly; `_assert_inside()` enforces parent boundary before `os.symlink` |
| Branch-name validation | lines 184-217 | `_validate_branch_name()` rejects `..`, `/`, and NUL bytes before any subprocess call |
| `cleanup_worktree` validates inside root | lines 435-437 | `path.resolve()` checked via `_assert_inside(resolved, resolved_root)` before `shutil.rmtree` |

TOCTOU note (POSIX): `os.symlink` creation is atomic so F-03 attack surface is closed. `shutil.rmtree` cleanup is not atomic — a concurrent rename between the `is_relative_to` check and rmtree remains a theoretical race. Accepted and documented in module docstring.

---

## Denylist Coverage (src/autodev/utils/command_safety.py DEFAULT_DENYLIST)

All required patterns present:

- `rm -rf` — line 46
- `sudo` — line 47
- `chmod 777` — line 48
- `curl | bash` — line 49 (with spaces; see F-01 gap below)
- `wget | bash` — line 50 (with spaces; see F-01 gap below)
- `eval` — line 51
- `exec ` — line 52 (with trailing space to avoid false positives on `execute`)
- `cat .env` — line 54

Additional patterns: `source .env`, `printenv`, ` env `, `> /etc/`, `; rm `, `&& rm `, `| rm `, `mkfs`, `--force`, `git push --force`, `gh --force`.

---

## Executor Router Modes (src/autodev/executors/executor_router.py)

| Mode | Selection | Fallback |
|---|---|---|
| `auto` | `ExecutionBackend.AUTO` → `_auto_route()` (task_type / risk / language / file-count) | Via `_maybe_mock()` |
| `codex` | `request.backend == CODEX` | Mock when binary absent + `allow_mock=True` |
| `claude` | `request.backend == CLAUDE_CODE` | Mock when binary absent + `allow_mock=True` |
| `mock` | `MOCK_CODEX` / `MOCK_CLAUDE` directly, or fallback from above | N/A |

Fail-closed: if real CLI missing and `allow_mock=False`, router returns `exit_code=127`, `error_type="cli_missing_fail_closed"`. Verified by `test_fail_closed_without_allow_mock_even_with_force_mock`.

---

## Residual Risks (4 xfail)

### F-01a — `curl|bash` no-space bypass
`DEFAULT_DENYLIST` contains `"curl | bash"` (spaces). `scan_prompt_for_unsafe("curl|bash")` returns empty — substring match fails without spaces.
**Fix needed:** add no-space variants or normalise whitespace before scan.

### F-01b — `wget|bash` no-space bypass
Identical gap to F-01a for `wget|bash`.
**Fix needed:** same as F-01a.

### F-02 — `FACTORY_FORCE_MOCK=1` fails-closed in `apply` mode
When the CLI sets `mode=apply` and `allow_mock=None`, `_build_config()` forces `allow_mock_executor=False`. Combined with `FACTORY_FORCE_MOCK=1` (both real CLIs absent), the router fail-closes instead of routing to mock.
**Fix needed:** `FactoryConfig.from_env()` or `_build_config()` must respect `FACTORY_FORCE_MOCK=1` by overriding `allow_mock_executor=True` regardless of pipeline mode.

### F-03 — Stale xfail annotation
`test_worker_isolator_rejects_escaped_symlink_in_parent_home` is marked `xfail` with reason "currently silently re-symlinks". R3-H already fixed this — the code now raises `WorkerIsolatorPathEscapeError` correctly (confirmed via `--runxfail`). The xfail annotation is stale and should be removed or converted to a passing test.
**Fix needed:** remove the `@pytest.mark.xfail` decorator from this test.

---

## Diff vs R3-H

No regression. All 10 `test_worker_isolator_symlink_hardening` tests pass clean. All 12 `test_executor_router` tests pass clean. F-03 code fix confirmed working. The 4 xfail residuals were already documented pre-tag and carry forward unchanged.

**Verdict: executor_boundary_solid_with_4_documented_xfail**
