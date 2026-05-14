"""autodev-x doctor — environment diagnostic checks."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from typing import Any


def _probe_version(binary: str) -> str:
    """Try to get the version string from a binary; return 'absent' if not found."""
    path = shutil.which(binary)
    if path is None:
        return "absent"
    for flag in ("--version", "version", "-v"):
        try:
            result = subprocess.run(  # noqa: S603
                [binary, flag],
                capture_output=True,
                text=True,
                timeout=5,
            )
            output = (result.stdout or result.stderr or "").strip().splitlines()
            if output:
                return output[0][:80]
        except Exception:  # noqa: BLE001
            pass
    return "present (version unknown)"


def run_checks() -> dict[str, Any]:
    """Run all diagnostic checks and return a results dict.

    Returns a dict with keys matching each check name, each value being
    ``{"status": "ok"|"warn"|"fail", "detail": str}``.
    """
    results: dict[str, Any] = {}

    # (a) autodev-x --version
    try:
        from importlib.metadata import PackageNotFoundError
        from importlib.metadata import version as _pkg_version

        v = _pkg_version("autodev-x")
        results["autodev_version"] = {"status": "ok", "detail": f"autodev-x {v}"}
    except PackageNotFoundError:
        results["autodev_version"] = {"status": "warn", "detail": "autodev-x package metadata not found"}

    # (b) Python >= 3.10
    py_ver = sys.version_info
    py_str = f"{py_ver.major}.{py_ver.minor}.{py_ver.micro}"
    if (py_ver.major, py_ver.minor) >= (3, 10):
        results["python_version"] = {"status": "ok", "detail": py_str}
    else:
        results["python_version"] = {"status": "fail", "detail": f"{py_str} (need >=3.10)"}

    # (c) codex and claude on PATH
    for binary in ("codex", "claude"):
        ver = _probe_version(binary)
        status = "ok" if ver != "absent" else "warn"
        results[binary] = {"status": status, "detail": ver}

    # (d) AUTODEV_MCP_ALLOW_APPLY env
    env_val = os.environ.get("AUTODEV_MCP_ALLOW_APPLY")
    if env_val is not None:
        results["AUTODEV_MCP_ALLOW_APPLY"] = {"status": "ok", "detail": f"set ({env_val!r})"}
    else:
        results["AUTODEV_MCP_ALLOW_APPLY"] = {"status": "warn", "detail": "not set (dry-run mode active)"}

    # (e) writable cwd
    try:
        cwd = os.getcwd()
        test_file = os.path.join(cwd, ".autodev_write_probe")
        with open(test_file, "w") as fh:
            fh.write("")
        os.remove(test_file)
        results["writable_cwd"] = {"status": "ok", "detail": cwd}
    except Exception as exc:  # noqa: BLE001
        results["writable_cwd"] = {"status": "fail", "detail": str(exc)}

    # (f) git installed
    git_ver = _probe_version("git")
    results["git"] = {
        "status": "ok" if git_ver != "absent" else "warn",
        "detail": git_ver,
    }

    return results


_STATUS_ICONS = {"ok": "[OK]   ", "warn": "[WARN] ", "fail": "[FAIL] "}


def print_table(results: dict[str, Any]) -> None:
    """Print a clean status table to stdout."""
    col_w = max(len(k) for k in results) + 2
    print(f"\n{'CHECK':<{col_w}}  {'STATUS':<8}  DETAIL")
    print("-" * 72)
    for key, info in results.items():
        icon = _STATUS_ICONS.get(info["status"], "       ")
        print(f"{key:<{col_w}}  {icon}  {info['detail']}")
    print()
